import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.director import get_director_service
from app.main import app
from app.services.director import DirectorBackendResult, DirectorOutputError, DirectorService
from app.services.director import DirectorProviderError
from app.services.openai_director import OpenAIDirectorBackend
from cutsceneai_cir import Project

FIXTURE = Path(__file__).parents[2] / "cir" / "examples" / "office-dialogue.cir.json"


def project() -> Project:
    return Project.model_validate_json(FIXTURE.read_text(encoding="utf-8"))


class FakeBackend:
    def __init__(self, value: Project) -> None:
        self.value = value

    async def generate(self, prompt: str) -> DirectorBackendResult:
        assert prompt
        return DirectorBackendResult(self.value, "fake", "fake-model", "req-1")


def test_service_validates_and_stamps_generation_metadata() -> None:
    result = asyncio.run(
        DirectorService(FakeBackend(project())).generate("Stage an office dialogue.")
    )
    assert result.project.generation.generator == "fake-director"
    assert result.project.generation.prompt_version == "director-v0.1"


def test_service_rejects_domain_invalid_output() -> None:
    value = project()
    value.scenes[0].shots = [
        shot for shot in value.scenes[0].shots if shot.purpose.value != "establishing"
    ]
    with pytest.raises(DirectorOutputError, match="failed domain validation"):
        asyncio.run(DirectorService(FakeBackend(value)).generate("Stage an office dialogue."))


class FakeResponses:
    def __init__(self, parsed: Project | None) -> None:
        self.parsed = parsed
        self.kwargs: dict[str, object] = {}

    async def parse(self, **kwargs: object) -> object:
        self.kwargs = kwargs
        return SimpleNamespace(output_parsed=self.parsed, _request_id="req-openai")


def test_openai_adapter_requests_typed_project() -> None:
    responses = FakeResponses(project())
    backend = OpenAIDirectorBackend(SimpleNamespace(responses=responses), model="test-model")
    result = asyncio.run(backend.generate("Stage an office dialogue with two coworkers."))
    assert responses.kwargs["text_format"] is Project
    assert responses.kwargs["model"] == "test-model"
    assert result.request_id == "req-openai"


def test_openai_adapter_rejects_empty_structured_output() -> None:
    backend = OpenAIDirectorBackend(
        SimpleNamespace(responses=FakeResponses(None)), model="test-model"
    )
    with pytest.raises(DirectorOutputError, match="no structured CIR"):
        asyncio.run(backend.generate("Stage an office dialogue with two coworkers."))


def test_generate_endpoint_returns_validated_cir() -> None:
    app.dependency_overrides[get_director_service] = lambda: DirectorService(FakeBackend(project()))
    try:
        response = TestClient(app).post(
            "/api/v1/director/generate",
            json={"prompt": "Stage an office dialogue with two coworkers."},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["project"]["generation"]["generator"] == "fake-director"


class FailingService:
    async def generate(self, prompt: str) -> DirectorBackendResult:
        raise DirectorProviderError("temporary failure", retryable=True, request_id="req-fail")


def test_generate_endpoint_maps_provider_error() -> None:
    app.dependency_overrides[get_director_service] = lambda: FailingService()
    try:
        response = TestClient(app).post(
            "/api/v1/director/generate",
            json={"prompt": "Stage an office dialogue with two coworkers."},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 502
    assert response.json() == {
        "code": "provider_error",
        "message": "temporary failure",
        "retryable": True,
        "request_id": "req-fail",
    }
