import asyncio
from io import BytesIO
import json
from pathlib import Path
import sys
import urllib.error

from cutsceneai_cir import Project
from cutsceneai_performance import compile_generation_plan
import pytest

import app.services.performance_providers as providers
from app.services.performance_providers import (
    ExternalCanonicalBodyBackend,
    PerformanceProviderConfigurationError,
    PerformanceProviderExecutionError,
    ProceduralCameraBackend,
    ProceduralFacialBackend,
    performance_compiler_config,
)


FIXTURE = Path(__file__).resolve().parents[2] / "cir" / "examples" / "office-dialogue.cir.json"


def _project() -> Project:
    return Project.model_validate_json(FIXTURE.read_text(encoding="utf-8"))


def _plan():
    return compile_generation_plan(_project(), config=performance_compiler_config(20260812))


def _body_request():
    return _plan().body_requests[0]


def _valid_body_response() -> dict[str, object]:
    request = _body_request()
    frame_count = request.end_frame - request.start_frame
    identity = {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}
    return {
        "request_semantic_id": request.semantic_id,
        "provider": request.provider,
        "model": request.model,
        "model_revision": request.model_revision,
        "prompt_sha256": request.prompt_sha256,
        "configuration_sha256": request.configuration_sha256,
        "seed": request.seed,
        "generated_at_inference": True,
        "retrieved_pre_authored_clip": False,
        "deterministic_algorithms": True,
        "artifact": {
            "fps": 24,
            "frame_count": frame_count,
            "samples": [
                {
                    "frame_index": frame,
                    "root_translation": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "joint_rotations": [identity for _ in range(22)],
                }
                for frame in range(frame_count)
            ],
        },
    }


def test_provider_environment_configuration_guards(monkeypatch) -> None:
    for key in (
        "CUTSCENEAI_BODY_PROVIDER_COMMAND",
        "CUTSCENEAI_BODY_PROVIDER_URL",
        "CUTSCENEAI_BODY_PROVIDER_TOKEN",
        "CUTSCENEAI_BODY_PROVIDER_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(key, raising=False)

    assert ExternalCanonicalBodyBackend.from_environment().configured is False

    monkeypatch.setenv("CUTSCENEAI_BODY_PROVIDER_COMMAND", "python provider.py")
    parsed = ExternalCanonicalBodyBackend.from_environment()
    assert parsed.command is not None
    assert parsed.command[0].lower().startswith("python")

    monkeypatch.setenv("CUTSCENEAI_BODY_PROVIDER_COMMAND", "[]")
    with pytest.raises(PerformanceProviderConfigurationError, match="non-empty"):
        ExternalCanonicalBodyBackend.from_environment()

    monkeypatch.delenv("CUTSCENEAI_BODY_PROVIDER_COMMAND", raising=False)
    monkeypatch.setenv("CUTSCENEAI_BODY_PROVIDER_TIMEOUT_SECONDS", "not-a-number")
    with pytest.raises(PerformanceProviderConfigurationError, match="numeric"):
        ExternalCanonicalBodyBackend.from_environment()

    monkeypatch.setenv("CUTSCENEAI_BODY_PROVIDER_TIMEOUT_SECONDS", "0")
    with pytest.raises(PerformanceProviderConfigurationError, match="between"):
        ExternalCanonicalBodyBackend.from_environment()


def test_provider_requires_configuration_and_rejects_insecure_remote_url() -> None:
    request = _body_request()

    with pytest.raises(PerformanceProviderConfigurationError, match="No body motion provider"):
        asyncio.run(ExternalCanonicalBodyBackend().generate_body(request))

    backend = ExternalCanonicalBodyBackend(url="http://example.com/body")
    with pytest.raises(PerformanceProviderConfigurationError, match="must use HTTPS"):
        asyncio.run(backend.generate_body(request))


def test_provider_command_start_failure_timeout_and_nonzero(tmp_path: Path) -> None:
    request = _body_request()

    missing = ExternalCanonicalBodyBackend(command=[str(tmp_path / "missing-executable")])
    with pytest.raises(PerformanceProviderExecutionError, match="Unable to start"):
        asyncio.run(missing.generate_body(request))

    sleepy = tmp_path / "sleepy.py"
    sleepy.write_text("import time\ntime.sleep(0.2)\n", encoding="utf-8")
    timeout = ExternalCanonicalBodyBackend(
        command=[sys.executable, str(sleepy)],
        timeout_seconds=0.01,
    )
    with pytest.raises(PerformanceProviderExecutionError, match="exceeded"):
        asyncio.run(timeout.generate_body(request))

    failing = tmp_path / "failing.py"
    failing.write_text(
        "import sys\nsys.stderr.write('synthetic provider failure')\nsys.exit(7)\n",
        encoding="utf-8",
    )
    nonzero = ExternalCanonicalBodyBackend(command=[sys.executable, str(failing)])
    with pytest.raises(PerformanceProviderExecutionError, match="code 7"):
        asyncio.run(nonzero.generate_body(request))


def test_provider_decode_and_contract_guards() -> None:
    with pytest.raises(PerformanceProviderExecutionError, match="valid UTF-8 JSON"):
        ExternalCanonicalBodyBackend._decode_json(b"{invalid")

    with pytest.raises(PerformanceProviderExecutionError, match="JSON object"):
        ExternalCanonicalBodyBackend._decode_json(b"[]")

    request = _body_request()
    with pytest.raises(PerformanceProviderExecutionError, match="missing fields"):
        ExternalCanonicalBodyBackend._parse_response(request, {"artifact": {}})

    invalid = _valid_body_response()
    invalid["artifact"] = {"fps": 24, "frame_count": 1, "samples": []}
    with pytest.raises(PerformanceProviderExecutionError, match="invalid canonical motion"):
        ExternalCanonicalBodyBackend._parse_response(request, invalid)


class _FakeHttpResponse:
    def __init__(self, data: bytes, content_length: int | None = None) -> None:
        self._data = data
        self.headers = {}
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        return False

    def read(self, limit: int) -> bytes:
        return self._data[:limit]


def test_provider_https_success_token_and_transport_failures(monkeypatch) -> None:
    payload = {"kind": "body_motion"}
    response = json.dumps(_valid_body_response()).encode("utf-8")
    captured: dict[str, object] = {}

    def success(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return _FakeHttpResponse(response, len(response))

    monkeypatch.setattr(providers.urllib.request, "urlopen", success)
    backend = ExternalCanonicalBodyBackend(
        url="https://motion.example.test/generate",
        bearer_token="secret",
        timeout_seconds=12,
    )
    value = backend._invoke_http(payload)
    assert value["request_semantic_id"] == _body_request().semantic_id
    assert captured["timeout"] == 12
    request = captured["request"]
    assert request.get_header("Authorization") == "Bearer secret"

    monkeypatch.setattr(
        providers.urllib.request,
        "urlopen",
        lambda request, timeout: _FakeHttpResponse(
            b"{}",
            providers._MAX_PROVIDER_OUTPUT_BYTES + 1,
        ),
    )
    with pytest.raises(PerformanceProviderExecutionError, match="32 MiB"):
        backend._invoke_http(payload)

    def network_failure(request, timeout):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(providers.urllib.request, "urlopen", network_failure)
    with pytest.raises(PerformanceProviderExecutionError, match="offline"):
        backend._invoke_http(payload)

    def http_failure(request, timeout):
        raise urllib.error.HTTPError(
            backend.url,
            503,
            "unavailable",
            hdrs=None,
            fp=BytesIO(b"provider unavailable"),
        )

    monkeypatch.setattr(providers.urllib.request, "urlopen", http_failure)
    with pytest.raises(PerformanceProviderExecutionError, match="HTTP 503"):
        backend._invoke_http(payload)


def test_procedural_facial_baseline_covers_emotion_and_lipsync_modes() -> None:
    source = _plan().facial_requests[0]
    backend = ProceduralFacialBackend()
    index = {name: position for position, name in enumerate(providers.ARKIT_52_CURVES)}

    expected = {
        "happy": "mouth_smile_left",
        "sad": "mouth_frown_left",
        "angry": "brow_down_left",
        "surprise": "eye_wide_left",
    }
    for emotion, curve in expected.items():
        request = source.model_copy(
            update={
                "emotion": emotion,
                "emotion_intensity": 1.0,
                "lip_sync": False,
                "dialogue_text": None,
            }
        )
        result = asyncio.run(backend.generate_facial(request))
        middle = result.artifact.samples[len(result.artifact.samples) // 2]
        assert middle.weights[index[curve]] > 0

    lipsync = source.model_copy(
        update={
            "emotion": "neutral",
            "emotion_intensity": 0.0,
            "lip_sync": True,
            "dialogue_text": "Who is there?",
        }
    )
    lip_result = asyncio.run(backend.generate_facial(lipsync))
    assert max(sample.weights[index["jaw_open"]] for sample in lip_result.artifact.samples) > 0.1
    assert lip_result.generated_at_inference is True
    assert lip_result.retrieved_pre_authored_clip is False


def test_procedural_camera_baseline_covers_static_and_moving_prompts() -> None:
    source = _plan().camera_requests[0]
    backend = ProceduralCameraBackend()

    moving = source.model_copy(
        update={"prompt": source.prompt + " dolly forward and pan at 30 fps"}
    )
    moving_result = asyncio.run(backend.generate_camera(moving))
    assert moving_result.artifact.fps == 30
    first = moving_result.artifact.samples[0].position
    last = moving_result.artifact.samples[-1].position
    assert first.x != last.x
    assert first.z != last.z

    static = source.model_copy(update={"prompt": "Locked camera."})
    static_result = asyncio.run(backend.generate_camera(static))
    assert static_result.artifact.fps == 24
    assert static_result.artifact.samples[0].position == static_result.artifact.samples[-1].position

    assert providers._fps_from_prompt("at 999 fps") == 240
    assert providers._fps_from_prompt("at 0 fps") == 1
