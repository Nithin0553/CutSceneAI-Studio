from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import pickle
import subprocess
import sys
import tempfile


PROVIDER_ID = "motionmaster-cvpr2026"
MODEL_ID = "mllm_single_3b"


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"Required environment variable is missing: {name}")
    return value.strip()


def _as_float_lists(value, *, width: int, name: str) -> list[list[float]]:
    if hasattr(value, "tolist"):
        array = value.tolist()
    else:
        array = value
    if not isinstance(array, list) or not array:
        raise RuntimeError(
            f"MotionMaster output '{name}' must be a non-empty ndarray or list."
        )
    result: list[list[float]] = []
    for row in array:
        if not isinstance(row, list) or len(row) != width:
            raise RuntimeError(
                f"MotionMaster output '{name}' must have shape [frames,{width}]."
            )
        result.append([float(item) for item in row])
    return result


def _health() -> dict[str, object]:
    root = Path(_require_env("CUTSCENEAI_MOTIONMASTER_ROOT")).resolve()
    revision = _require_env("CUTSCENEAI_MOTIONMASTER_REVISION")
    source_fps = int(_require_env("CUTSCENEAI_MOTIONMASTER_SOURCE_FPS"))
    source_forward_axis = _require_env("CUTSCENEAI_MOTIONMASTER_FORWARD_AXIS")
    if source_fps < 1 or source_fps > 240:
        raise RuntimeError("CUTSCENEAI_MOTIONMASTER_SOURCE_FPS must be between 1 and 240.")
    if source_forward_axis not in {"+z", "-z"}:
        raise RuntimeError(
            "CUTSCENEAI_MOTIONMASTER_FORWARD_AXIS must be '+z' or '-z'."
        )

    required_paths = [
        root / "infer.py",
        Path(
            os.getenv(
                "CUTSCENEAI_MOTIONMASTER_MLLM_PATH",
                str(root / "checkpoints" / "mllm_single_3b"),
            )
        ),
        Path(
            os.getenv(
                "CUTSCENEAI_MOTIONMASTER_TOKENIZER_PATH",
                str(root / "checkpoints" / "tokenizer.pt"),
            )
        ),
        Path(
            os.getenv(
                "CUTSCENEAI_MOTIONMASTER_STATS_PATH",
                str(root / "checkpoints" / "norm_stats.npz"),
            )
        ),
        Path(
            os.getenv(
                "CUTSCENEAI_MOTIONMASTER_SMPLX_PATH",
                str(root / "checkpoints" / "smplx_model"),
            )
        ),
        root / "src" / "human_body_prior_repo" / "support_data" / "dowloads" / "V02_05",
    ]
    missing = [str(path) for path in required_paths if not path.exists()]
    if missing:
        raise RuntimeError(
            "MotionMaster health check is missing required paths: " + ", ".join(missing)
        )

    try:
        import torch
        import transformers
        import pytorch3d  # noqa: F401
        import human_body_prior  # noqa: F401
    except Exception as exc:
        raise RuntimeError(
            f"MotionMaster Python dependencies are incomplete: {type(exc).__name__}: {exc}"
        ) from exc

    if not torch.cuda.is_available():
        raise RuntimeError("MotionMaster requires a CUDA-capable GPU; torch.cuda.is_available() is false.")

    device_name = torch.cuda.get_device_name(0)
    total_memory = torch.cuda.get_device_properties(0).total_memory

    return {
        "status": "ready",
        "provider": PROVIDER_ID,
        "model": MODEL_ID,
        "model_revision": revision,
        "source_fps": source_fps,
        "source_forward_axis": source_forward_axis,
        "cuda": True,
        "cuda_device": device_name,
        "cuda_memory_bytes": int(total_memory),
        "torch_version": str(torch.__version__),
        "transformers_version": str(transformers.__version__),
    }


def _run_motionmaster(request: dict[str, object]) -> dict[str, object]:
    root = Path(_require_env("CUTSCENEAI_MOTIONMASTER_ROOT")).resolve()
    infer = root / "infer.py"
    if not infer.is_file():
        raise RuntimeError(f"MotionMaster infer.py was not found: {infer}")

    source_fps = int(_require_env("CUTSCENEAI_MOTIONMASTER_SOURCE_FPS"))
    if source_fps < 1 or source_fps > 240:
        raise RuntimeError("CUTSCENEAI_MOTIONMASTER_SOURCE_FPS must be between 1 and 240.")

    source_forward_axis = os.getenv(
        "CUTSCENEAI_MOTIONMASTER_FORWARD_AXIS",
        "+z",
    ).strip()
    if source_forward_axis not in {"+z", "-z"}:
        raise RuntimeError(
            "CUTSCENEAI_MOTIONMASTER_FORWARD_AXIS must be '+z' or '-z'."
        )

    revision = _require_env("CUTSCENEAI_MOTIONMASTER_REVISION")
    if request.get("provider") != PROVIDER_ID:
        raise RuntimeError(
            f"Provider identity mismatch: request={request.get('provider')!r}, "
            f"wrapper={PROVIDER_ID!r}."
        )
    if request.get("model") != MODEL_ID:
        raise RuntimeError(
            f"Model identity mismatch: request={request.get('model')!r}, "
            f"wrapper={MODEL_ID!r}."
        )
    if request.get("model_revision") != revision:
        raise RuntimeError(
            "Model revision mismatch between Studio and MotionMaster wrapper."
        )

    mllm_path = Path(
        os.getenv(
            "CUTSCENEAI_MOTIONMASTER_MLLM_PATH",
            str(root / "checkpoints" / "mllm_single_3b"),
        )
    )
    tokenizer_path = Path(
        os.getenv(
            "CUTSCENEAI_MOTIONMASTER_TOKENIZER_PATH",
            str(root / "checkpoints" / "tokenizer.pt"),
        )
    )
    stats_path = Path(
        os.getenv(
            "CUTSCENEAI_MOTIONMASTER_STATS_PATH",
            str(root / "checkpoints" / "norm_stats.npz"),
        )
    )
    smplx_path = Path(
        os.getenv(
            "CUTSCENEAI_MOTIONMASTER_SMPLX_PATH",
            str(root / "checkpoints" / "smplx_model"),
        )
    )
    for path in (mllm_path, tokenizer_path, stats_path, smplx_path):
        if not path.exists():
            raise RuntimeError(f"MotionMaster dependency is missing: {path}")

    prompt = str(request.get("prompt") or "").strip()
    if not prompt:
        raise RuntimeError("CutSceneAI body request prompt is empty.")

    with tempfile.TemporaryDirectory(prefix="cutsceneai-motionmaster-") as temp_dir:
        output_path = Path(temp_dir) / "motion.pkl"
        command = [
            sys.executable,
            str(infer),
            "--text",
            prompt,
            "--output",
            str(output_path),
            "--mllm_path",
            str(mllm_path),
            "--tokenizer_pt",
            str(tokenizer_path),
            "--stats_npz",
            str(stats_path),
            "--smplx_path",
            str(smplx_path),
        ]
        timeout_seconds = float(
            os.getenv("CUTSCENEAI_MOTIONMASTER_INFERENCE_TIMEOUT_SECONDS", "1200")
        )
        completed = subprocess.run(
            command,
            cwd=root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout)[-8000:]
            raise RuntimeError(
                f"MotionMaster inference failed with code {completed.returncode}: {detail}"
            )
        if not output_path.is_file():
            raise RuntimeError("MotionMaster reported success but produced no output pickle.")

        with output_path.open("rb") as handle:
            output = pickle.load(handle)

    if not isinstance(output, dict):
        raise RuntimeError("MotionMaster output pickle must contain a dictionary.")
    global_orient = _as_float_lists(
        output.get("global_orient"),
        width=3,
        name="global_orient",
    )
    body_pose = _as_float_lists(
        output.get("body_pose"),
        width=63,
        name="body_pose",
    )
    transl = _as_float_lists(
        output.get("transl"),
        width=3,
        name="transl",
    )
    if not (len(global_orient) == len(body_pose) == len(transl)):
        raise RuntimeError("MotionMaster output arrays have inconsistent frame counts.")

    return {
        "fps": source_fps,
        "source_forward_axis": source_forward_axis,
        "global_orient": global_orient,
        "body_pose": body_pose,
        "transl": transl,
    }


def main() -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(
        "--health",
        action="store_true",
        help="Validate MotionMaster dependencies and CUDA without running inference.",
    )
    args = parser.parse_args()

    try:
        if args.health:
            json.dump(_health(), sys.stdout, separators=(",", ":"))
            sys.stdout.write("\n")
            return 0

        payload = json.load(sys.stdin)
        if payload.get("protocol_version") != "cutsceneai.provider.v0.1":
            raise RuntimeError("Unsupported CutSceneAI provider protocol version.")
        if payload.get("kind") != "body_motion":
            raise RuntimeError("MotionMaster wrapper only accepts body_motion requests.")
        request = payload.get("request")
        if not isinstance(request, dict):
            raise RuntimeError("CutSceneAI provider payload is missing its request object.")

        artifact = _run_motionmaster(request)
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
            "artifact_format": "smplx-axis-angle-v0.1",
            "artifact": artifact,
        }
        json.dump(response, sys.stdout, separators=(",", ":"))
        sys.stdout.write("\n")
        return 0
    except Exception as exc:
        print(f"CUTSCENEAI_MOTIONMASTER_PROVIDER_ERROR={type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
