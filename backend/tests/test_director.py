import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.director import get_director_service
from app.main import app
from app.services.director import (
    DirectorBackendResult,
    DirectorConfigurationError,
    DirectorOutputError,
    DirectorProviderError,
    DirectorService,
)
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

    async def edit(self, current: Project, instruction: str) -> DirectorBackendResult:
        assert current.id
        assert instruction
        return DirectorBackendResult(self.value, "fake", "fake-model", "req-edit")


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


def test_service_validates_and_stamps_edit_generation_metadata() -> None:
    result = asyncio.run(
        DirectorService(FakeBackend(project())).edit(
            project(),
            "Hold the final reaction two seconds longer.",
        )
    )
    assert result.project.generation.generator == "fake-director"
    assert result.project.generation.prompt_version == "director-edit-v0.1"
    assert result.request_id == "req-edit"


def test_openai_adapter_requests_typed_project_for_edit() -> None:
    responses = FakeResponses(project())
    backend = OpenAIDirectorBackend(SimpleNamespace(responses=responses), model="test-model")
    result = asyncio.run(
        backend.edit(
            project(),
            "Move the close-up later without changing the dialogue.",
        )
    )
    assert responses.kwargs["text_format"] is Project
    assert responses.kwargs["model"] == "test-model"
    payload = responses.kwargs["input"]
    assert isinstance(payload, list)
    assert "CURRENT CIR:" in payload[1]["content"]
    assert "Move the close-up later" in payload[1]["content"]
    assert result.request_id == "req-openai"


def test_edit_endpoint_returns_validated_revised_cir() -> None:
    app.dependency_overrides[get_director_service] = lambda: DirectorService(FakeBackend(project()))
    try:
        response = TestClient(app).post(
            "/api/v1/director/edit",
            json={
                "project": project().model_dump(mode="json"),
                "instruction": "Hold the final reaction two seconds longer.",
            },
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["project"]["generation"]["prompt_version"] == "director-edit-v0.1"
    assert body["request_id"] == "req-edit"


def test_service_rejects_domain_invalid_edit_output() -> None:
    value = project()
    value.scenes[0].shots = [
        shot for shot in value.scenes[0].shots if shot.purpose.value != "establishing"
    ]
    with pytest.raises(DirectorOutputError, match="Edited CIR failed domain validation"):
        asyncio.run(
            DirectorService(FakeBackend(value)).edit(
                project(),
                "Remove the establishing shot.",
            )
        )


class ConfigurationFailingService:
    async def generate(self, prompt: str) -> DirectorBackendResult:
        raise DirectorConfigurationError("director configuration missing")

    async def edit(self, current: Project, instruction: str) -> DirectorBackendResult:
        raise DirectorConfigurationError("director configuration missing")


class OutputFailingService:
    async def generate(self, prompt: str) -> DirectorBackendResult:
        raise DirectorOutputError("invalid structured output")

    async def edit(self, current: Project, instruction: str) -> DirectorBackendResult:
        raise DirectorOutputError("invalid structured output")


class ProviderFailingEditService:
    async def edit(self, current: Project, instruction: str) -> DirectorBackendResult:
        raise DirectorProviderError(
            "edit provider unavailable",
            retryable=False,
            request_id="edit-failure",
        )


@pytest.mark.parametrize(
    ("path", "service", "expected_code"),
    [
        ("/api/v1/director/generate", ConfigurationFailingService(), "director_not_configured"),
        ("/api/v1/director/generate", OutputFailingService(), "invalid_provider_output"),
        ("/api/v1/director/edit", ConfigurationFailingService(), "director_not_configured"),
        ("/api/v1/director/edit", OutputFailingService(), "invalid_provider_output"),
    ],
)
def test_director_endpoints_map_configuration_and_output_errors(
    path: str, service, expected_code: str
) -> None:
    app.dependency_overrides[get_director_service] = lambda: service
    payload = (
        {"prompt": "Stage an office dialogue with two coworkers."}
        if path.endswith("generate")
        else {
            "project": project().model_dump(mode="json"),
            "instruction": "Hold the reaction longer.",
        }
    )
    try:
        response = TestClient(app).post(path, json=payload)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code in {502, 503}
    assert response.json()["code"] == expected_code


def test_edit_endpoint_maps_provider_error() -> None:
    app.dependency_overrides[get_director_service] = lambda: ProviderFailingEditService()
    try:
        response = TestClient(app).post(
            "/api/v1/director/edit",
            json={
                "project": project().model_dump(mode="json"),
                "instruction": "Hold the reaction longer.",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert response.json() == {
        "code": "provider_error",
        "message": "edit provider unavailable",
        "retryable": False,
        "request_id": "edit-failure",
    }
