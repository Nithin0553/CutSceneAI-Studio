from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any


PROVIDER_ID = "mdm-local"
MODEL_ID = "humanml-encoder-512-50steps"
HUMANML_FPS = 20
KNOWN_CHECKPOINT_SHA256 = (
    "0fbdc8547c8f262b8838645586790b55f983d90db3bb7ed58e4b5d49429587ca"
)
JOINT_NAMES = (
    "pelvis",
    "left_hip",
    "right_hip",
    "spine1",
    "left_knee",
    "right_knee",
    "spine2",
    "left_ankle",
    "right_ankle",
    "spine3",
    "left_foot",
    "right_foot",
    "neck",
    "left_collar",
    "right_collar",
    "head",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
)


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"Required environment variable is missing: {name}")
    return value.strip()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _mdm_root() -> Path:
    root = Path(_require_env("CUTSCENEAI_MDM_ROOT")).resolve()
    if not (root / "sample" / "generate.py").is_file():
        raise RuntimeError(
            "CUTSCENEAI_MDM_ROOT must point to the MDM source checkout containing "
            f"sample/generate.py; got {root}."
        )
    return root


def _checkpoint() -> Path:
    checkpoint = Path(_require_env("CUTSCENEAI_MDM_CHECKPOINT")).resolve()
    if not checkpoint.is_file():
        raise RuntimeError(f"MDM checkpoint was not found: {checkpoint}")
    expected = (
        os.getenv(
            "CUTSCENEAI_MDM_CHECKPOINT_SHA256",
            KNOWN_CHECKPOINT_SHA256,
        )
        .strip()
        .lower()
    )
    actual = _file_sha256(checkpoint)
    if actual != expected:
        raise RuntimeError(
            f"MDM checkpoint SHA-256 mismatch. Expected {expected}, got {actual}."
        )
    return checkpoint


def _validate_identity(request: dict[str, Any]) -> str:
    revision = _require_env("CUTSCENEAI_MDM_REVISION")
    expected = (PROVIDER_ID, MODEL_ID, revision)
    actual = (
        request.get("provider"),
        request.get("model"),
        request.get("model_revision"),
    )
    if actual != expected:
        raise RuntimeError(
            "Body generation request identity does not match the configured MDM runtime. "
            f"Expected {expected!r}; got {actual!r}."
        )
    return revision


def _target_fps(prompt: str) -> int:
    matches = re.findall(r"\bat\s+(\d{1,3})\s+fps\b", prompt, re.IGNORECASE)
    if not matches:
        return 24
    return max(1, min(240, int(matches[-1])))


def _motion_duration(request: dict[str, Any]) -> float:
    start = int(request["start_frame"])
    end = int(request["end_frame"])
    if end <= start:
        raise RuntimeError(
            "Body generation request end_frame must be greater than start_frame."
        )
    duration = (end - start) / _target_fps(str(request.get("prompt") or ""))
    maximum = float(os.getenv("CUTSCENEAI_MDM_MAX_DURATION_SECONDS", "9.8"))
    if maximum <= 0.0 or maximum > 9.8:
        raise RuntimeError(
            "CUTSCENEAI_MDM_MAX_DURATION_SECONDS must be greater than zero and no more "
            "than the HumanML MDM maximum of 9.8 seconds."
        )
    if duration <= 0.0 or duration > maximum:
        raise RuntimeError(
            f"MDM request duration is {duration:.3f}s but this provider accepts at most "
            f"{maximum:.3f}s. Split the CIR performance cue into shorter body segments."
        )
    return duration


def _motion_prompt(request: dict[str, Any]) -> str:
    prompt = str(request.get("prompt") or "").strip()
    if not prompt:
        raise RuntimeError("CutSceneAI body request prompt is empty.")

    action = re.search(
        r"Action:\s*(.+?)\s+Style:",
        prompt,
        flags=re.IGNORECASE | re.DOTALL,
    )
    style = re.search(
        r"Style:\s*(.+?)\.\s+Emotion:",
        prompt,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if action is not None and action.group(1).strip():
        action_text = re.sub(r"\s+", " ", action.group(1)).strip().rstrip(".")
        action_lower = action_text.lower()
        target_binding_id = str(request.get("target_binding_id") or "").strip()

        # MDM never sees the bound engine transform, so target-relative language such as
        # "turn toward the door" is underspecified for the model. Ask it for the physical
        # motion primitive only; the target binding remains on the canonical request and is
        # resolved later by CutSceneAI's constraint/composition stage.
        if target_binding_id and re.search(r"\b(turn|pivot|rotate)\b", action_lower):
            action_text = (
                "turn the whole body in place to face a distinctly different direction, "
                "using a clear planted-foot pivot without walking forward"
            )
        elif (
            target_binding_id
            and re.search(r"\b(hold|remain|stand)\b", action_lower)
            and re.search(r"\b(facing|toward|still|stance)\b", action_lower)
        ):
            action_text = (
                "stand upright and remain still in place in a cautious alert stance, "
                "with only subtle natural body sway and no stepping or root travel"
            )

        style_text = (
            re.sub(r"\s+", " ", style.group(1)).strip().rstrip(".")
            if style is not None and style.group(1).strip()
            else ""
        )
        if style_text and style_text.lower() != "natural":
            return f"{action_text}. Perform the motion in a {style_text} manner."
        return action_text + "."
    return re.sub(r"\s+", " ", prompt).strip()[:1000]


def _results_path(output_dir: Path) -> Path:
    direct = output_dir / "results.npy"
    if direct.is_file():
        return direct
    matches = list(output_dir.rglob("results.npy"))
    if len(matches) != 1:
        raise RuntimeError(
            "MDM inference did not produce exactly one results.npy under "
            f"{output_dir}; found {len(matches)}."
        )
    return matches[0]


def _extract_positions(path: Path, prompt: str) -> tuple[list[list[list[float]]], int]:
    import numpy as np

    loaded = np.load(path, allow_pickle=True)
    if hasattr(loaded, "item"):
        payload = loaded.item()
    else:
        payload = loaded
    if not isinstance(payload, dict):
        raise RuntimeError(
            "MDM results.npy must contain the official results dictionary."
        )

    motion = payload.get("motion")
    lengths = payload.get("lengths")
    texts = payload.get("text")
    if motion is None or lengths is None:
        raise RuntimeError("MDM results.npy is missing motion or lengths.")
    if getattr(motion, "ndim", None) != 4:
        raise RuntimeError(
            "MDM HumanML motion must have shape [samples,22,3,frames]; "
            f"got {getattr(motion, 'shape', None)}."
        )
    if motion.shape[0] != 1 or motion.shape[1] != 22 or motion.shape[2] != 3:
        raise RuntimeError(
            "MDM provider requires exactly one HumanML XYZ sample with shape "
            f"[1,22,3,frames]; got {motion.shape}."
        )

    length = int(lengths[0])
    if length <= 0 or length > motion.shape[3]:
        raise RuntimeError(
            f"MDM reported invalid sample length {length} for tensor {motion.shape}."
        )

    if texts is not None and len(texts) > 0:
        generated_text = str(texts[0]).strip()
        if generated_text and generated_text != prompt:
            raise RuntimeError(
                "MDM results text does not match the requested motion prompt. "
                f"Expected {prompt!r}; got {generated_text!r}."
            )

    sample = motion[0, :, :, :length]
    if not np.isfinite(sample).all():
        raise RuntimeError("MDM generated non-finite HumanML joint positions.")
    positions = sample.transpose(2, 0, 1).astype(float).tolist()
    return positions, length


def _generate(request: dict[str, Any]) -> dict[str, Any]:
    _validate_identity(request)
    root = _mdm_root()
    checkpoint = _checkpoint()
    prompt = _motion_prompt(request)
    duration = _motion_duration(request)
    seed = int(request["seed"])

    with tempfile.TemporaryDirectory(prefix="cutsceneai-mdm-") as temporary:
        output_dir = Path(temporary) / "output"
        command = [
            sys.executable,
            "-m",
            "sample.generate",
            "--model_path",
            str(checkpoint),
            "--text_prompt",
            prompt,
            "--num_samples",
            "1",
            "--num_repetitions",
            "1",
            "--seed",
            str(seed),
            "--motion_length",
            f"{duration:.6f}",
            "--output_dir",
            str(output_dir),
        ]
        device = os.getenv("CUTSCENEAI_MDM_DEVICE", "").strip()
        if device:
            command.extend(["--device", device])

        timeout = float(os.getenv("CUTSCENEAI_MDM_INFERENCE_TIMEOUT_SECONDS", "1200"))
        if timeout <= 0.0 or timeout > 7200.0:
            raise RuntimeError(
                "CUTSCENEAI_MDM_INFERENCE_TIMEOUT_SECONDS must be between 0 and 7200."
            )

        completed = subprocess.run(
            command,
            cwd=root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout)[-12000:]
            raise RuntimeError(
                f"MDM inference failed with code {completed.returncode}: {detail}"
            )

        positions, frame_count = _extract_positions(
            _results_path(output_dir),
            prompt,
        )

    return {
        "fps": HUMANML_FPS,
        "source_distance_unit": "meter",
        "source_handedness": "right",
        "source_up_axis": "y",
        "source_forward_axis": "+z",
        "frame_count": frame_count,
        "joint_names": list(JOINT_NAMES),
        "positions": positions,
    }


def _health() -> dict[str, Any]:
    root = _mdm_root()
    checkpoint = _checkpoint()
    revision = _require_env("CUTSCENEAI_MDM_REVISION")

    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    try:
        import numpy
        import torch
        from utils import parser_util  # noqa: F401
    except Exception as exc:
        raise RuntimeError(
            f"MDM Python environment is incomplete: {type(exc).__name__}: {exc}"
        ) from exc

    return {
        "status": "ready",
        "provider": PROVIDER_ID,
        "model": MODEL_ID,
        "model_revision": revision,
        "checkpoint_sha256": _file_sha256(checkpoint),
        "source_fps": HUMANML_FPS,
        "cuda_available": bool(torch.cuda.is_available()),
        "cuda_device": (
            torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
        ),
        "numpy_version": str(numpy.__version__),
        "torch_version": str(torch.__version__),
        "source_root": str(root),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--health",
        action="store_true",
        help="Validate the retained MDM runtime without running inference.",
    )
    args = parser.parse_args()

    try:
        if args.health:
            json.dump(_health(), sys.stdout, separators=(",", ":"))
            sys.stdout.write("\n")
            return 0

        envelope = json.load(sys.stdin)
        if envelope.get("protocol_version") != "cutsceneai.provider.v0.1":
            raise RuntimeError("Unsupported CutSceneAI provider protocol version.")
        if envelope.get("kind") != "body_motion":
            raise RuntimeError("MDM wrapper only accepts body_motion requests.")
        request = envelope.get("request")
        if not isinstance(request, dict):
            raise RuntimeError(
                "CutSceneAI provider payload is missing its request object."
            )

        artifact = _generate(request)
        response = {
            "request_semantic_id": request["semantic_id"],
            "provider": request["provider"],
            "model": request["model"],
            "model_revision": request["model_revision"],
            "prompt_sha256": request["prompt_sha256"],
            "configuration_sha256": request["configuration_sha256"],
            "seed": request["seed"],
            "generated_at_inference": True,
            "retrieved_pre_authored_clip": False,
            "deterministic_algorithms": False,
            "artifact_format": "humanml-xyz-v0.1",
            "artifact": artifact,
        }
        json.dump(response, sys.stdout, separators=(",", ":"))
        sys.stdout.write("\n")
        return 0
    except Exception as exc:
        print(
            f"CUTSCENEAI_MDM_PROVIDER_ERROR={type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
