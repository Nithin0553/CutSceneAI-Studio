#!/usr/bin/env python3
"""CutSceneAI canonical body provider for Tencent HY-Motion 1.0.

This process keeps HY-Motion loaded once and exposes CutSceneAI's strict body-provider
JSON protocol over HTTP. It intentionally converts the model's first 22 SMPL-H local
joint rotations into the CutSceneAI humanoid joint order instead of routing motion
through FBX.
"""

from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import threading
from typing import Any


PROTOCOL_VERSION = "cutsceneai.provider.v0.1"
CANONICAL_SKELETON = "cutsceneai-humanoid-v1"
HY_MOTION_FPS = 30
MAX_REQUEST_BYTES = 2 * 1024 * 1024
MAX_DURATION_SECONDS = 12.0
BASIS_PROFILE = "smpl-rh-y-up-plus-z_to_cutsceneai-rh-y-up-minus-z-v0.1"


def _required_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string.")
    return value.strip()


def _required_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer.")
    return value


def _request_duration(request: dict[str, Any]) -> float:
    start = _required_int(request.get("start_frame"), "request.start_frame")
    end = _required_int(request.get("end_frame"), "request.end_frame")
    if end <= start:
        raise ValueError("request.end_frame must be greater than request.start_frame.")

    prompt = _required_string(request.get("prompt"), "request.prompt")
    import re

    matches = re.findall(r"Duration:\s*(\d+)\s+frames\s+at\s+(\d+)\s+fps", prompt)
    if not matches:
        raise ValueError(
            "Body request prompt is missing the compiler's explicit 'Duration: N frames at F fps' "
            "instruction."
        )
    prompt_frames, prompt_fps = (int(item) for item in matches[-1])
    request_frames = end - start
    if prompt_frames != request_frames:
        raise ValueError(
            f"Body request duration mismatch: window={request_frames} frames, "
            f"prompt={prompt_frames} frames."
        )
    if not 1 <= prompt_fps <= 240:
        raise ValueError("Body request FPS must be between 1 and 240.")
    duration = request_frames / prompt_fps
    if duration > MAX_DURATION_SECONDS:
        raise ValueError(
            f"HY-Motion provider supports at most {MAX_DURATION_SECONDS:g}s per generated segment; "
            f"request requires {duration:.3f}s."
        )
    return duration


def _normalize_quaternion_signs(quaternions: Any) -> Any:
    """Make xyzw quaternion signs continuous independently for every joint."""

    import numpy as np

    output = np.array(quaternions, dtype=np.float64, copy=True)
    for joint_index in range(output.shape[1]):
        for frame_index in range(1, output.shape[0]):
            if float(np.dot(output[frame_index - 1, joint_index], output[frame_index, joint_index])) < 0:
                output[frame_index, joint_index] *= -1.0
    return output


def _canonical_artifact(model_output: dict[str, Any]) -> dict[str, Any]:
    """Convert HY-Motion local 6D rotations and root translation to canonical JSON."""

    import numpy as np
    from scipy.spatial.transform import Rotation
    from hymotion.utils.geometry import rot6d_to_rotation_matrix

    rot6d = model_output.get("rot6d")
    transl = model_output.get("transl")
    if rot6d is None or transl is None:
        raise RuntimeError("HY-Motion output omitted rot6d or transl.")

    if hasattr(rot6d, "detach"):
        rot6d = rot6d.detach().cpu()
    if hasattr(transl, "detach"):
        transl = transl.detach().cpu()

    if tuple(rot6d.shape[:1]) != (1,) or rot6d.ndim != 4 or rot6d.shape[2:] != (22, 6):
        raise RuntimeError(f"Unexpected HY-Motion rot6d shape: {tuple(rot6d.shape)}")
    if tuple(transl.shape[:1]) != (1,) or transl.ndim != 3 or transl.shape[2] != 3:
        raise RuntimeError(f"Unexpected HY-Motion transl shape: {tuple(transl.shape)}")
    if rot6d.shape[1] != transl.shape[1]:
        raise RuntimeError("HY-Motion rotation and translation sample counts differ.")

    matrices = rot6d_to_rotation_matrix(rot6d[0]).cpu().numpy().astype(np.float64)
    translations = transl[0].cpu().numpy().astype(np.float64)

    # HY-Motion emits SMPL-H local rotations in a RH/Y-up basis whose animation
    # convention is treated here as +Z-forward. CutSceneAI canonical motion is
    # RH/Y-up/-Z-forward. A basis reflection must therefore conjugate rotations,
    # while translations are reflected directly.
    basis = np.diag([1.0, 1.0, -1.0])
    matrices = np.einsum("ab,fjbc,cd->fjad", basis, matrices, basis)
    translations = translations @ basis.T

    # Canonical clips are reference-pose offsets rather than arbitrary model-space
    # world positions. Preserve displacement while pinning the generated segment's
    # first root sample to the local origin.
    translations = translations - translations[:1]

    quaternions = Rotation.from_matrix(matrices.reshape(-1, 3, 3)).as_quat()
    quaternions = quaternions.reshape(matrices.shape[0], 22, 4)
    quaternions = _normalize_quaternion_signs(quaternions)

    if not np.isfinite(translations).all() or not np.isfinite(quaternions).all():
        raise RuntimeError("HY-Motion output contains non-finite canonical values.")

    norms = np.linalg.norm(quaternions, axis=-1)
    if float(np.max(np.abs(norms - 1.0))) > 1e-4:
        raise RuntimeError("HY-Motion quaternion conversion produced non-unit rotations.")

    samples = []
    for frame_index in range(matrices.shape[0]):
        root = translations[frame_index]
        rotations = quaternions[frame_index]
        samples.append(
            {
                "frame_index": frame_index,
                "root_translation": {
                    "x": float(root[0]),
                    "y": float(root[1]),
                    "z": float(root[2]),
                },
                "joint_rotations": [
                    {
                        "x": float(item[0]),
                        "y": float(item[1]),
                        "z": float(item[2]),
                        "w": float(item[3]),
                    }
                    for item in rotations
                ],
            }
        )

    return {
        "artifact_version": "0.1.0",
        "fps": HY_MOTION_FPS,
        "frame_count": len(samples),
        "skeleton_profile": CANONICAL_SKELETON,
        "coordinate_space": {
            "distance_unit": "meter",
            "handedness": "right",
            "up_axis": "y",
            "forward_axis": "-z",
            "rotation_representation": "quaternion_xyzw",
        },
        "rotation_space": "reference-pose-relative-parent-local",
        "root_translation_space": "reference-pose-offset",
        "samples": samples,
    }


class HYMotionProvider:
    def __init__(
        self,
        *,
        repository_root: Path,
        model_path: Path,
        provider_id: str,
        model_id: str,
        model_revision: str,
        cfg_scale: float,
        validation_steps: int | None,
        deterministic_algorithms: bool,
        use_special_game_feat: bool,
    ) -> None:
        self.repository_root = repository_root.resolve()
        self.model_path = model_path.resolve()
        self.provider_id = provider_id
        self.model_id = model_id
        self.model_revision = model_revision
        self.cfg_scale = cfg_scale
        self.validation_steps = validation_steps
        self.deterministic_algorithms = deterministic_algorithms
        self.use_special_game_feat = use_special_game_feat
        self._lock = threading.Lock()
        self._runtime: Any | None = None

    def load(self) -> None:
        if self._runtime is not None:
            return

        config_path = self.model_path / "config.yml"
        checkpoint_path = self.model_path / "latest.ckpt"
        if not config_path.is_file():
            raise FileNotFoundError(f"HY-Motion config not found: {config_path}")
        if not checkpoint_path.is_file():
            raise FileNotFoundError(f"HY-Motion checkpoint not found: {checkpoint_path}")

        import sys

        repo_text = str(self.repository_root)
        if repo_text not in sys.path:
            sys.path.insert(0, repo_text)

        from hymotion.utils.t2m_runtime import T2MRuntime

        runtime = T2MRuntime(
            config_path=str(config_path),
            ckpt_name=str(checkpoint_path),
            disable_prompt_engineering=True,
        )
        if self.validation_steps is not None:
            for pipeline in runtime.pipelines:
                pipeline.validation_steps = self.validation_steps
        self._runtime = runtime

    def health(self) -> dict[str, Any]:
        loaded = self._runtime is not None
        return {
            "status": "ready" if loaded else "loading",
            "protocol_version": PROTOCOL_VERSION,
            "provider": self.provider_id,
            "model": self.model_id,
            "model_revision": self.model_revision,
            "source_fps": HY_MOTION_FPS,
            "canonical_skeleton": CANONICAL_SKELETON,
            "basis_profile": BASIS_PROFILE,
            "loaded": loaded,
        }

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("protocol_version") != PROTOCOL_VERSION:
            raise ValueError("Unsupported CutSceneAI provider protocol version.")
        if payload.get("kind") != "body_motion":
            raise ValueError("HY-Motion provider only accepts body_motion requests.")

        request = payload.get("request")
        if not isinstance(request, dict):
            raise ValueError("request must be a JSON object.")

        semantic_id = _required_string(request.get("semantic_id"), "request.semantic_id")
        prompt = _required_string(request.get("prompt"), "request.prompt")
        prompt_sha256 = _required_string(
            request.get("prompt_sha256"), "request.prompt_sha256"
        )
        configuration_sha256 = _required_string(
            request.get("configuration_sha256"), "request.configuration_sha256"
        )
        provider = _required_string(request.get("provider"), "request.provider")
        model = _required_string(request.get("model"), "request.model")
        model_revision = _required_string(
            request.get("model_revision"), "request.model_revision"
        )
        seed = _required_int(request.get("seed"), "request.seed")
        skeleton = _required_string(
            request.get("skeleton_profile"), "request.skeleton_profile"
        )

        if skeleton != CANONICAL_SKELETON:
            raise ValueError(
                f"Unsupported skeleton_profile '{skeleton}', expected '{CANONICAL_SKELETON}'."
            )
        expected_identity = (self.provider_id, self.model_id, self.model_revision)
        supplied_identity = (provider, model, model_revision)
        if supplied_identity != expected_identity:
            raise ValueError(
                "Generation request provider identity does not match the loaded HY-Motion service. "
                f"Expected {expected_identity!r}, got {supplied_identity!r}."
            )
        if not 0 <= seed <= 2**32 - 1:
            raise ValueError("request.seed is outside the uint32 range.")

        duration = _request_duration(request)
        self.load()
        assert self._runtime is not None

        with self._lock:
            result = self._runtime.generate_motion(
                text=prompt,
                seeds_csv=str(seed),
                duration=duration,
                cfg_scale=self.cfg_scale,
                output_format="dict",
                original_text=prompt,
                use_special_game_feat=self.use_special_game_feat,
            )
        if not isinstance(result, tuple) or len(result) != 3:
            raise RuntimeError("Unexpected HY-Motion runtime result signature.")
        model_output = result[2]
        if not isinstance(model_output, dict):
            raise RuntimeError("HY-Motion runtime did not return a motion dictionary.")

        artifact = _canonical_artifact(model_output)
        return {
            "request_semantic_id": semantic_id,
            "provider": provider,
            "model": model,
            "model_revision": model_revision,
            "prompt_sha256": prompt_sha256,
            "configuration_sha256": configuration_sha256,
            "seed": seed,
            "generated_at_inference": True,
            "retrieved_pre_authored_clip": False,
            "deterministic_algorithms": self.deterministic_algorithms,
            "artifact": artifact,
        }


class ProviderHTTPServer(ThreadingHTTPServer):
    provider: HYMotionProvider
    bearer_token: str | None


class Handler(BaseHTTPRequestHandler):
    server: ProviderHTTPServer

    def _json(self, status: HTTPStatus, body: dict[str, Any]) -> None:
        data = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self) -> bool:
        token = self.server.bearer_token
        if token is None:
            return True
        return self.headers.get("Authorization") == f"Bearer {token}"

    def do_GET(self) -> None:
        if self.path != "/health":
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        if not self._authorized():
            self._json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return
        self._json(HTTPStatus.OK, self.server.provider.health())

    def do_POST(self) -> None:
        if self.path != "/v1/body":
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        if not self._authorized():
            self._json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return

        raw_length = self.headers.get("Content-Length")
        try:
            length = int(raw_length or "0")
        except ValueError:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_content_length"})
            return
        if length <= 0 or length > MAX_REQUEST_BYTES:
            self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "request_too_large"})
            return

        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Request body must be a JSON object.")
            response = self.server.provider.generate(payload)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            self._json(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {"error": "invalid_request", "detail": str(exc)},
            )
            return
        except Exception as exc:
            self.log_error("generation failed: %s", exc)
            self._json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": "generation_failed", "detail": f"{type(exc).__name__}: {exc}"},
            )
            return

        self._json(HTTPStatus.OK, response)

    def log_message(self, format: str, *args: Any) -> None:
        print("[cutsceneai-hymotion] " + format % args, flush=True)


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--hymotion-repo",
        default=os.getenv("HYMOTION_REPO"),
        required=os.getenv("HYMOTION_REPO") is None,
    )
    parser.add_argument(
        "--model-path",
        default=os.getenv("HYMOTION_MODEL_PATH"),
        required=os.getenv("HYMOTION_MODEL_PATH") is None,
    )
    parser.add_argument("--host", default=os.getenv("CUTSCENEAI_HYMOTION_HOST", "127.0.0.1"))
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("CUTSCENEAI_HYMOTION_PORT", "8765")),
    )
    parser.add_argument(
        "--provider-id",
        default=os.getenv("CUTSCENEAI_HYMOTION_PROVIDER_ID", "tencent-hymotion"),
    )
    parser.add_argument(
        "--model-id",
        default=os.getenv("CUTSCENEAI_HYMOTION_MODEL_ID", "HY-Motion-1.0-Lite"),
    )
    parser.add_argument(
        "--model-revision",
        default=os.getenv("CUTSCENEAI_HYMOTION_MODEL_REVISION"),
        required=os.getenv("CUTSCENEAI_HYMOTION_MODEL_REVISION") is None,
    )
    parser.add_argument(
        "--cfg-scale",
        type=float,
        default=float(os.getenv("CUTSCENEAI_HYMOTION_CFG_SCALE", "5.0")),
    )
    parser.add_argument(
        "--validation-steps",
        type=int,
        default=int(os.getenv("CUTSCENEAI_HYMOTION_VALIDATION_STEPS", "50")),
    )
    args = parser.parse_args()

    if not 1 <= args.port <= 65535:
        raise SystemExit("port must be between 1 and 65535")
    if not math.isfinite(args.cfg_scale) or args.cfg_scale <= 0:
        raise SystemExit("cfg-scale must be a positive finite number")

    token = os.getenv("CUTSCENEAI_HYMOTION_TOKEN")
    if args.host not in {"127.0.0.1", "localhost", "::1"} and not token:
        raise SystemExit(
            "CUTSCENEAI_HYMOTION_TOKEN is required when binding the provider beyond loopback."
        )

    provider = HYMotionProvider(
        repository_root=Path(args.hymotion_repo),
        model_path=Path(args.model_path),
        provider_id=args.provider_id,
        model_id=args.model_id,
        model_revision=args.model_revision,
        cfg_scale=args.cfg_scale,
        validation_steps=args.validation_steps,
        deterministic_algorithms=_bool_env(
            "CUTSCENEAI_HYMOTION_DETERMINISTIC_ALGORITHMS", False
        ),
        use_special_game_feat=_bool_env("CUTSCENEAI_HYMOTION_GAME_FEATURE", True),
    )
    print(
        "Loading HY-Motion once for CutSceneAI. "
        f"model={args.model_id} revision={args.model_revision}",
        flush=True,
    )
    provider.load()

    server = ProviderHTTPServer((args.host, args.port), Handler)
    server.provider = provider
    server.bearer_token = token
    print(
        f"CutSceneAI HY-Motion provider ready at http://{args.host}:{args.port}/v1/body",
        flush=True,
    )
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
