from __future__ import annotations

import asyncio
import json
import math
import os
import re
import shlex
import subprocess
from typing import Any, TypeVar
import urllib.error
import urllib.request

from cutsceneai_performance import (
    ARKIT_52_CURVES,
    BodyGenerationRequest,
    BodyMotionArtifact,
    CameraCurveArtifact,
    CameraCurveSample,
    CameraGenerationRequest,
    FacialCurveArtifact,
    FacialCurveSample,
    FacialGenerationRequest,
    GenerationModelConfig,
    HumanMLXYZMotion,
    PerformanceCompilerConfig,
    ProviderArtifact,
    Quaternion,
    SMPLXAxisAngleMotion,
    Vector3,
    humanml_xyz_to_canonical,
    smplx_axis_angle_to_canonical,
)
from pydantic import BaseModel, ValidationError


ArtifactT = TypeVar("ArtifactT", bound=BaseModel)
_MAX_PROVIDER_OUTPUT_BYTES = 32 * 1024 * 1024
_DEFAULT_TIMEOUT_SECONDS = 180.0


class PerformanceProviderConfigurationError(RuntimeError):
    pass


class PerformanceProviderExecutionError(RuntimeError):
    pass


def performance_compiler_config(experiment_seed: int) -> PerformanceCompilerConfig:
    return PerformanceCompilerConfig(
        experiment_seed=experiment_seed,
        body=GenerationModelConfig(
            provider=os.getenv("CUTSCENEAI_BODY_PROVIDER", "unconfigured-body"),
            model=os.getenv("CUTSCENEAI_BODY_MODEL", "unconfigured"),
            model_revision=os.getenv("CUTSCENEAI_BODY_MODEL_REVISION", "unconfigured"),
            prompt_version=os.getenv("CUTSCENEAI_BODY_PROMPT_VERSION", "body-v0.1"),
            deterministic_algorithms=os.getenv("CUTSCENEAI_BODY_DETERMINISTIC", "true").lower()
            not in {"0", "false", "no"},
        ),
        facial=GenerationModelConfig(
            provider="cutsceneai-procedural-facial",
            model="arkit52-baseline-v0.1",
            model_revision="0.1.0",
            prompt_version="facial-v0.1",
            deterministic_algorithms=True,
        ),
        camera=GenerationModelConfig(
            provider="cutsceneai-procedural-camera",
            model="cinematic-baseline-v0.1",
            model_revision="0.1.0",
            prompt_version="camera-v0.1",
            deterministic_algorithms=True,
        ),
    )


def _fps_from_prompt(prompt: str) -> int:
    matches = re.findall(r"\bat\s+(\d{1,3})\s+fps\b", prompt, re.IGNORECASE)
    if not matches:
        return 24
    return max(1, min(240, int(matches[-1])))


def _provider_artifact(
    request: BodyGenerationRequest | FacialGenerationRequest | CameraGenerationRequest,
    artifact: ArtifactT,
    *,
    deterministic_algorithms: bool,
) -> ProviderArtifact[ArtifactT]:
    return ProviderArtifact(
        request_semantic_id=request.semantic_id,
        artifact=artifact,
        provider=request.provider,
        model=request.model,
        model_revision=request.model_revision,
        prompt_sha256=request.prompt_sha256,
        configuration_sha256=request.configuration_sha256,
        seed=request.seed,
        generated_at_inference=True,
        retrieved_pre_authored_clip=False,
        deterministic_algorithms=deterministic_algorithms,
    )


def _parse_argv_environment(
    name: str,
    raw: str | None,
) -> list[str] | None:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = shlex.split(raw, posix=os.name != "nt")
    if (
        not isinstance(parsed, list)
        or not parsed
        or not all(isinstance(item, str) and item.strip() for item in parsed)
    ):
        raise PerformanceProviderConfigurationError(
            f"{name} must be a non-empty JSON argv array or a command line."
        )
    return parsed


class ExternalCanonicalBodyBackend:
    """Execute a user-configured canonical body provider over JSON.

    The provider must return a CutSceneAI BodyMotionArtifact and echo the immutable
    generation-request identity fields. The backend supports either a local argv
    command or a server-side HTTPS endpoint. No shell is used.
    """

    def __init__(
        self,
        *,
        command: list[str] | None = None,
        url: str | None = None,
        bearer_token: str | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        health_url: str | None = None,
        health_command: list[str] | None = None,
        health_timeout_seconds: float = 5.0,
    ) -> None:
        self.command = command
        self.url = url
        self.bearer_token = bearer_token
        self.timeout_seconds = timeout_seconds
        self.health_url = health_url
        self.health_command = health_command
        self.health_timeout_seconds = health_timeout_seconds

    @classmethod
    def from_environment(cls) -> ExternalCanonicalBodyBackend:
        command = _parse_argv_environment(
            "CUTSCENEAI_BODY_PROVIDER_COMMAND",
            os.getenv("CUTSCENEAI_BODY_PROVIDER_COMMAND"),
        )
        health_command = _parse_argv_environment(
            "CUTSCENEAI_BODY_PROVIDER_HEALTH_COMMAND",
            os.getenv("CUTSCENEAI_BODY_PROVIDER_HEALTH_COMMAND"),
        )

        url = os.getenv("CUTSCENEAI_BODY_PROVIDER_URL")
        token = os.getenv("CUTSCENEAI_BODY_PROVIDER_TOKEN")
        health_url = os.getenv("CUTSCENEAI_BODY_PROVIDER_HEALTH_URL")
        timeout_raw = os.getenv("CUTSCENEAI_BODY_PROVIDER_TIMEOUT_SECONDS")
        health_timeout_raw = os.getenv("CUTSCENEAI_BODY_PROVIDER_HEALTH_TIMEOUT_SECONDS")
        timeout = _DEFAULT_TIMEOUT_SECONDS
        health_timeout = 5.0
        if timeout_raw:
            try:
                timeout = float(timeout_raw)
            except ValueError as exc:
                raise PerformanceProviderConfigurationError(
                    "CUTSCENEAI_BODY_PROVIDER_TIMEOUT_SECONDS must be numeric."
                ) from exc
        if timeout <= 0 or timeout > 1800:
            raise PerformanceProviderConfigurationError(
                "Body provider timeout must be between 0 and 1800 seconds."
            )
        if health_timeout_raw:
            try:
                health_timeout = float(health_timeout_raw)
            except ValueError as exc:
                raise PerformanceProviderConfigurationError(
                    "CUTSCENEAI_BODY_PROVIDER_HEALTH_TIMEOUT_SECONDS must be numeric."
                ) from exc
        if health_timeout <= 0 or health_timeout > 120:
            raise PerformanceProviderConfigurationError(
                "Body provider health timeout must be between 0 and 120 seconds."
            )
        return cls(
            command=command,
            url=url,
            bearer_token=token,
            timeout_seconds=timeout,
            health_url=health_url,
            health_command=health_command,
            health_timeout_seconds=health_timeout,
        )

    @property
    def configured(self) -> bool:
        return bool(self.command or self.url)

    def probe_health(
        self,
        *,
        expected_provider: str,
        expected_model: str,
        expected_revision: str,
    ) -> tuple[bool | None, str | None, dict[str, object]]:
        if self.health_command:
            try:
                completed = subprocess.run(
                    self.health_command,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=self.health_timeout_seconds,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                return False, "unreachable", {"error": str(exc)}
            if completed.returncode != 0:
                detail = completed.stderr.decode("utf-8", errors="replace")[-4000:]
                return (
                    False,
                    "unhealthy",
                    {
                        "exit_code": completed.returncode,
                        "error": detail,
                    },
                )
            raw = completed.stdout
            if len(raw) > 256 * 1024:
                return (
                    False,
                    "invalid-health-response",
                    {"error": "Provider health response exceeded 256 KiB."},
                )
            return self._validate_health_identity(
                raw,
                expected_provider=expected_provider,
                expected_model=expected_model,
                expected_revision=expected_revision,
            )

        if not self.health_url:
            return None, None, {}
        if not self.health_url.lower().startswith(
            ("https://", "http://127.0.0.1", "http://localhost")
        ):
            raise PerformanceProviderConfigurationError(
                "Remote body provider health URLs must use HTTPS; "
                "HTTP is permitted only for localhost."
            )

        headers = {"Accept": "application/json"}
        if self.bearer_token:
            headers["Authorization"] = "Bearer " + self.bearer_token
        request = urllib.request.Request(
            self.health_url,
            headers=headers,
            method="GET",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.health_timeout_seconds,
            ) as response:
                raw = response.read(256 * 1024 + 1)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return False, "unreachable", {"error": str(exc)}

        if len(raw) > 256 * 1024:
            return (
                False,
                "invalid-health-response",
                {"error": "Provider health response exceeded 256 KiB."},
            )
        return self._validate_health_identity(
            raw,
            expected_provider=expected_provider,
            expected_model=expected_model,
            expected_revision=expected_revision,
        )

    @staticmethod
    def _validate_health_identity(
        raw: bytes,
        *,
        expected_provider: str,
        expected_model: str,
        expected_revision: str,
    ) -> tuple[bool, str, dict[str, object]]:
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return False, "invalid-health-response", {"error": str(exc)}
        if not isinstance(value, dict):
            return (
                False,
                "invalid-health-response",
                {"error": "Provider health response must be a JSON object."},
            )

        expected = {
            "provider": expected_provider,
            "model": expected_model,
            "model_revision": expected_revision,
        }
        mismatches = {
            key: {"expected": expected_value, "actual": value.get(key)}
            for key, expected_value in expected.items()
            if value.get(key) != expected_value
        }
        if mismatches:
            return False, "identity-mismatch", {"mismatches": mismatches, **value}

        status = str(value.get("status") or "reachable")
        ready = status.lower() in {"ready", "reachable", "ok", "cold"}
        return ready, status, value

    async def generate_body(
        self,
        request: BodyGenerationRequest,
    ) -> ProviderArtifact[BodyMotionArtifact]:
        payload = {
            "protocol_version": "cutsceneai.provider.v0.1",
            "kind": "body_motion",
            "request": request.model_dump(mode="json"),
        }
        response = await self._invoke(payload)
        return self._parse_response(request, response)

    async def _invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.command:
            return await self._invoke_command(payload)
        if self.url:
            return await asyncio.to_thread(self._invoke_http, payload)
        raise PerformanceProviderConfigurationError(
            "No body motion provider is configured. Set CUTSCENEAI_BODY_PROVIDER_COMMAND "
            "or CUTSCENEAI_BODY_PROVIDER_URL."
        )

    async def _invoke_command(self, payload: dict[str, Any]) -> dict[str, Any]:
        assert self.command is not None
        try:
            process = await asyncio.create_subprocess_exec(
                *self.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            raise PerformanceProviderExecutionError(
                f"Unable to start body provider command: {exc}"
            ) from exc

        input_data = (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=input_data),
                timeout=self.timeout_seconds,
            )
        except TimeoutError as exc:
            process.kill()
            try:
                await asyncio.wait_for(process.communicate(), timeout=5.0)
            except TimeoutError:
                pass
            raise PerformanceProviderExecutionError(
                f"Body provider exceeded {self.timeout_seconds:g}s timeout."
            ) from exc

        if len(stdout) > _MAX_PROVIDER_OUTPUT_BYTES:
            raise PerformanceProviderExecutionError(
                "Body provider output exceeded the 32 MiB safety limit."
            )
        if process.returncode != 0:
            error = stderr.decode("utf-8", errors="replace")[-4000:]
            raise PerformanceProviderExecutionError(
                f"Body provider exited with code {process.returncode}: {error}"
            )
        return self._decode_json(stdout)

    def _invoke_http(self, payload: dict[str, Any]) -> dict[str, Any]:
        assert self.url is not None
        if not self.url.lower().startswith(("https://", "http://127.0.0.1", "http://localhost")):
            raise PerformanceProviderConfigurationError(
                "Remote body provider URLs must use HTTPS; HTTP is permitted only for localhost."
            )
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.bearer_token:
            headers["Authorization"] = "Bearer " + self.bearer_token
        request = urllib.request.Request(self.url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                length = response.headers.get("Content-Length")
                if length is not None and int(length) > _MAX_PROVIDER_OUTPUT_BYTES:
                    raise PerformanceProviderExecutionError(
                        "Body provider response exceeded the 32 MiB safety limit."
                    )
                raw = response.read(_MAX_PROVIDER_OUTPUT_BYTES + 1)
        except urllib.error.HTTPError as exc:
            detail = exc.read(4000).decode("utf-8", errors="replace")
            raise PerformanceProviderExecutionError(
                f"Body provider HTTP {exc.code}: {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise PerformanceProviderExecutionError(
                f"Body provider request failed: {exc.reason}"
            ) from exc

        if len(raw) > _MAX_PROVIDER_OUTPUT_BYTES:
            raise PerformanceProviderExecutionError(
                "Body provider response exceeded the 32 MiB safety limit."
            )
        return self._decode_json(raw)

    @staticmethod
    def _decode_json(raw: bytes) -> dict[str, Any]:
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PerformanceProviderExecutionError(
                "Body provider did not return valid UTF-8 JSON."
            ) from exc
        if not isinstance(value, dict):
            raise PerformanceProviderExecutionError("Body provider response must be a JSON object.")
        return value

    @staticmethod
    def _parse_response(
        request: BodyGenerationRequest,
        response: dict[str, Any],
    ) -> ProviderArtifact[BodyMotionArtifact]:
        required = {
            "request_semantic_id",
            "provider",
            "model",
            "model_revision",
            "prompt_sha256",
            "configuration_sha256",
            "seed",
            "generated_at_inference",
            "retrieved_pre_authored_clip",
            "deterministic_algorithms",
            "artifact",
        }
        missing = sorted(required - response.keys())
        if missing:
            raise PerformanceProviderExecutionError(
                "Body provider response is missing fields: " + ", ".join(missing)
            )
        artifact_format = str(response.get("artifact_format", "cutsceneai.motion+json"))
        try:
            if artifact_format == "cutsceneai.motion+json":
                artifact = BodyMotionArtifact.model_validate(response["artifact"])
            elif artifact_format == "smplx-axis-angle-v0.1":
                smplx = SMPLXAxisAngleMotion.model_validate(response["artifact"])
                artifact = smplx_axis_angle_to_canonical(smplx)
            elif artifact_format == "humanml-xyz-v0.1":
                humanml = HumanMLXYZMotion.model_validate(response["artifact"])
                artifact = humanml_xyz_to_canonical(humanml)
            else:
                raise PerformanceProviderExecutionError(
                    f"Body provider returned unsupported artifact_format '{artifact_format}'."
                )
        except ValidationError as exc:
            raise PerformanceProviderExecutionError(
                f"Body provider returned an invalid '{artifact_format}' artifact: {exc}"
            ) from exc
        return ProviderArtifact(
            request_semantic_id=str(response["request_semantic_id"]),
            artifact=artifact,
            provider=str(response["provider"]),
            model=str(response["model"]),
            model_revision=str(response["model_revision"]),
            prompt_sha256=str(response["prompt_sha256"]),
            configuration_sha256=str(response["configuration_sha256"]),
            seed=int(response["seed"]),
            generated_at_inference=response["generated_at_inference"] is True,
            retrieved_pre_authored_clip=response["retrieved_pre_authored_clip"] is True,
            deterministic_algorithms=bool(response["deterministic_algorithms"]),
        )


class ProceduralFacialBackend:
    """Deterministic ARKit-52 baseline for orchestration and ablation studies."""

    async def generate_facial(
        self,
        request: FacialGenerationRequest,
    ) -> ProviderArtifact[FacialCurveArtifact]:
        frame_count = request.end_frame - request.start_frame
        index = {name: position for position, name in enumerate(ARKIT_52_CURVES)}
        samples: list[FacialCurveSample] = []
        phase = (request.seed % 997) / 997.0
        emotion = request.emotion.lower()

        for frame in range(frame_count):
            values = [0.0] * len(ARKIT_52_CURVES)
            t = frame / max(frame_count - 1, 1)
            envelope = math.sin(math.pi * t)
            intensity = request.emotion_intensity * envelope

            if any(word in emotion for word in ("happy", "joy", "smile", "pleased")):
                values[index["mouth_smile_left"]] = 0.62 * intensity
                values[index["mouth_smile_right"]] = 0.62 * intensity
                values[index["cheek_squint_left"]] = 0.22 * intensity
                values[index["cheek_squint_right"]] = 0.22 * intensity
            elif any(word in emotion for word in ("sad", "sorrow", "upset")):
                values[index["mouth_frown_left"]] = 0.48 * intensity
                values[index["mouth_frown_right"]] = 0.48 * intensity
                values[index["brow_inner_up"]] = 0.35 * intensity
            elif any(word in emotion for word in ("angry", "anger", "frustrated")):
                values[index["brow_down_left"]] = 0.48 * intensity
                values[index["brow_down_right"]] = 0.48 * intensity
                values[index["mouth_press_left"]] = 0.3 * intensity
                values[index["mouth_press_right"]] = 0.3 * intensity
            elif any(word in emotion for word in ("surprise", "shocked", "astonished")):
                values[index["brow_inner_up"]] = 0.55 * intensity
                values[index["eye_wide_left"]] = 0.45 * intensity
                values[index["eye_wide_right"]] = 0.45 * intensity
                values[index["jaw_open"]] = 0.42 * intensity

            blink_period = 72 + int(request.seed % 29)
            blink_center = int((0.35 + 0.3 * phase) * blink_period)
            blink_distance = abs((frame % blink_period) - blink_center)
            blink = max(0.0, 1.0 - blink_distance / 2.0)
            values[index["eye_blink_left"]] = max(values[index["eye_blink_left"]], blink)
            values[index["eye_blink_right"]] = max(values[index["eye_blink_right"]], blink)

            if request.lip_sync and request.dialogue_text:
                speech = max(0.0, math.sin((frame + phase * 7.0) * 0.72))
                punctuation_scale = (
                    0.85 if request.dialogue_text.strip().endswith((".", "?", "!")) else 1.0
                )
                values[index["jaw_open"]] = max(
                    values[index["jaw_open"]],
                    min(0.72, 0.12 + 0.42 * speech * punctuation_scale),
                )
                values[index["mouth_funnel"]] = 0.12 * (1.0 - speech)
                values[index["mouth_pucker"]] = 0.08 * (0.5 + 0.5 * speech)

            samples.append(FacialCurveSample(frame_index=frame, weights=values))

        artifact = FacialCurveArtifact(
            fps=_fps_from_prompt(request.prompt),
            frame_count=frame_count,
            samples=samples,
        )
        return _provider_artifact(
            request,
            artifact,
            deterministic_algorithms=True,
        )


class ProceduralCameraBackend:
    """Deterministic camera baseline; intended as a reproducible ablation, not learned AI."""

    async def generate_camera(
        self,
        request: CameraGenerationRequest,
    ) -> ProviderArtifact[CameraCurveArtifact]:
        frame_count = request.end_frame - request.start_frame
        prompt = request.prompt.lower()
        movement = 0.0
        if any(token in prompt for token in ("dolly", "push", "move", "track")):
            movement = 0.6
        lateral = 0.0
        if any(token in prompt for token in ("pan", "orbit", "arc")):
            lateral = 0.8

        samples: list[CameraCurveSample] = []
        for frame in range(frame_count):
            t = frame / max(frame_count - 1, 1)
            ease = t * t * (3.0 - 2.0 * t)
            samples.append(
                CameraCurveSample(
                    frame_index=frame,
                    position=Vector3(
                        x=(ease - 0.5) * lateral,
                        y=1.65,
                        z=4.0 - ease * movement,
                    ),
                    rotation=Quaternion(x=0.0, y=0.0, z=0.0, w=1.0),
                    focal_length_mm=request.lens_mm,
                )
            )

        artifact = CameraCurveArtifact(
            fps=_fps_from_prompt(request.prompt),
            frame_count=frame_count,
            samples=samples,
        )
        return _provider_artifact(
            request,
            artifact,
            deterministic_algorithms=True,
        )
