from __future__ import annotations

import asyncio
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

from fastapi.testclient import TestClient
import pytest

from app.api.dialogue import get_dialogue_engine
from app.main import app
from app.services import openai_speech
from app.services.openai_speech import OpenAISpeechBackend
from cutsceneai_dialogue import (
    DialogueConfigurationError,
    DialogueEngine,
    DialogueInputError,
    DialogueOutputError,
    DialogueProviderError,
    SpeechBackendResult,
    SpeechSynthesisRequest,
)


EXAMPLE = Path(__file__).parents[2] / "cir" / "examples" / "office-dialogue.cir.json"


def payload() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def make_wav() -> bytes:
    import wave

    output = BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(8_000)
        wav_file.writeframes(b"\0" * 8_000 * 2)
    return output.getvalue()


class FakeSpeechBackend:
    async def synthesize(self, request: SpeechSynthesisRequest) -> SpeechBackendResult:
        return SpeechBackendResult(
            data=make_wav(),
            provider="fake",
            model="fake-speech",
            voice=request.voice,
            request_id="req-test",
        )


def test_dialogue_plan_endpoint_returns_deterministic_cues() -> None:
    response = TestClient(app).post("/api/v1/dialogue/plan", json=payload())

    assert response.status_code == 200
    body = response.json()
    assert body["dialogue_version"] == "0.1.0"
    assert [cue["start_frame"] for cue in body["cues"]] == [120, 216]


@pytest.mark.parametrize("invalid", [[], {"bad": "payload"}])
def test_dialogue_plan_endpoint_reports_structural_errors(invalid: object) -> None:
    response = TestClient(app).post("/api/v1/dialogue/plan", json=invalid)
    assert response.status_code == 422
    assert response.json()["valid"] is False


def test_dialogue_plan_endpoint_reports_domain_errors() -> None:
    value = payload()
    value["scenes"][0]["shots"][0]["purpose"] = "action"
    response = TestClient(app).post("/api/v1/dialogue/plan", json=value)
    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "missing_establishing_shot"


def test_dialogue_synthesize_endpoint_returns_portable_zip() -> None:
    app.dependency_overrides[get_dialogue_engine] = lambda: DialogueEngine(FakeSpeechBackend())
    try:
        response = TestClient(app).post(
            "/api/v1/dialogue/synthesize",
            json={
                "project": payload(),
                "default_voice": {"voice": "cedar"},
                "voices": {"mina": {"voice": "marin", "instructions": "Firm."}},
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["x-cutsceneai-dialogue-clips"] == "2"
    assert response.headers["x-cutsceneai-ai-voice-disclosure"] == "required"
    with ZipFile(BytesIO(response.content)) as archive:
        assert "AI_VOICE_DISCLOSURE.txt" in archive.namelist()
        project = json.loads(archive.read("project.cir.json"))
        assert project["scenes"][0]["beats"][1]["performances"][0]["dialogue"][
            "audio_uri"
        ].startswith("cutsceneai://dialogue/")


class FailingEngine:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def synthesize_project(self, *_args: object, **_kwargs: object) -> object:
        raise self.error


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (DialogueInputError("bad input"), 422, "invalid_dialogue_request"),
        (DialogueConfigurationError("no key"), 503, "speech_not_configured"),
        (
            DialogueProviderError("provider", retryable=True, request_id="req-2"),
            502,
            "provider_error",
        ),
        (DialogueOutputError("bad wav"), 502, "invalid_provider_output"),
    ],
)
def test_dialogue_synthesize_endpoint_maps_engine_errors(
    error: Exception, status: int, code: str
) -> None:
    app.dependency_overrides[get_dialogue_engine] = lambda: FailingEngine(error)
    try:
        response = TestClient(app).post("/api/v1/dialogue/synthesize", json={"project": payload()})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == status
    assert response.json()["code"] == code


def test_dialogue_synthesize_endpoint_rejects_domain_invalid_cir() -> None:
    value = payload()
    value["scenes"][0]["shots"][0]["purpose"] = "action"
    app.dependency_overrides[get_dialogue_engine] = lambda: FailingEngine(
        AssertionError("engine should not run")
    )
    try:
        response = TestClient(app).post("/api/v1/dialogue/synthesize", json={"project": value})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_cir"


class FakeStreamingResponse:
    def __init__(self) -> None:
        self.headers = {"x-request-id": "req-openai"}

    async def __aenter__(self) -> FakeStreamingResponse:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def read(self) -> bytes:
        return make_wav()


class FakeCreate:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.kwargs: dict[str, object] = {}

    def __call__(self, **kwargs: object) -> FakeStreamingResponse:
        self.kwargs = kwargs
        if self.error is not None:
            raise self.error
        return FakeStreamingResponse()


def fake_client(create: FakeCreate) -> object:
    return SimpleNamespace(
        audio=SimpleNamespace(
            speech=SimpleNamespace(with_streaming_response=SimpleNamespace(create=create))
        )
    )


def speech_request(*, instructions: str | None = "Calm and direct.") -> SpeechSynthesisRequest:
    return SpeechSynthesisRequest(
        cue_id="dialogue-test",
        text="Hello.",
        language="en",
        voice="marin",
        instructions=instructions,
    )


def test_openai_speech_adapter_requests_wav_and_preserves_request_id() -> None:
    create = FakeCreate()
    backend = OpenAISpeechBackend(fake_client(create), model="speech-test")
    result = asyncio.run(backend.synthesize(speech_request()))

    assert create.kwargs == {
        "model": "speech-test",
        "voice": "marin",
        "input": "Hello.",
        "response_format": "wav",
        "speed": 1.0,
        "instructions": "Calm and direct.",
    }
    assert result.provider == "openai"
    assert result.request_id == "req-openai"
    assert result.data.startswith(b"RIFF")


def test_openai_speech_adapter_omits_empty_instructions() -> None:
    create = FakeCreate()
    backend = OpenAISpeechBackend(fake_client(create), model="speech-test")
    asyncio.run(backend.synthesize(speech_request(instructions=None)))
    assert "instructions" not in create.kwargs


def test_openai_speech_adapter_reports_missing_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_client() -> object:
        raise openai_speech.openai.OpenAIError("missing key")

    monkeypatch.setattr(openai_speech, "AsyncOpenAI", fail_client)
    backend = OpenAISpeechBackend(model="speech-test")
    with pytest.raises(DialogueConfigurationError, match="OPENAI_API_KEY"):
        backend._get_client()


@pytest.mark.parametrize(
    ("kind", "retryable", "request_id"),
    [
        ("connection", True, None),
        ("rate", True, "req-rate"),
        ("status", False, "req-status"),
        ("server", True, "req-server"),
    ],
)
def test_openai_speech_adapter_maps_provider_errors(
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    retryable: bool,
    request_id: str | None,
) -> None:
    class ConnectionError(Exception):
        pass

    class RateError(Exception):
        def __init__(self) -> None:
            self.request_id = "req-rate"

    class StatusError(Exception):
        def __init__(self, status_code: int, value: str) -> None:
            self.status_code = status_code
            self.request_id = value

    monkeypatch.setattr(openai_speech.openai, "APIConnectionError", ConnectionError)
    monkeypatch.setattr(openai_speech.openai, "RateLimitError", RateError)
    monkeypatch.setattr(openai_speech.openai, "APIStatusError", StatusError)
    errors = {
        "connection": ConnectionError(),
        "rate": RateError(),
        "status": StatusError(400, "req-status"),
        "server": StatusError(503, "req-server"),
    }
    backend = OpenAISpeechBackend(fake_client(FakeCreate(errors[kind])), model="speech-test")

    with pytest.raises(DialogueProviderError) as raised:
        asyncio.run(backend.synthesize(speech_request()))
    assert raised.value.retryable is retryable
    assert raised.value.request_id == request_id
