from __future__ import annotations

import json
import os
from pathlib import Path
import pickle
import subprocess
import sys


WRAPPER = Path(__file__).resolve().parents[2] / "tools" / "providers" / "motionmaster_provider.py"


def _request() -> dict[str, object]:
    return {
        "protocol_version": "cutsceneai.provider.v0.1",
        "kind": "body_motion",
        "request": {
            "semantic_id": "body:scene1:beat1:actor1",
            "start_frame": 0,
            "end_frame": 48,
            "prompt": "Generate novel full-body motion. Action: walk forward and stop.",
            "prompt_sha256": "a" * 64,
            "configuration_sha256": "b" * 64,
            "seed": 123,
            "provider": "motionmaster-cvpr2026",
            "model": "mllm_single_3b",
            "model_revision": "fixture-revision",
            "prompt_version": "body-v0.1",
            "actor_binding_id": "actor:guard",
            "source_performance_cue_id": "performance:scene1:beat1:actor1",
            "skeleton_profile": "cutsceneai-humanoid-v1",
            "look_at_binding_id": None,
        },
    }


def _fake_motionmaster_root(tmp_path: Path) -> Path:
    root = tmp_path / "MotionMaster"
    checkpoints = root / "checkpoints"
    (checkpoints / "mllm_single_3b").mkdir(parents=True)
    (checkpoints / "smplx_model").mkdir()
    (checkpoints / "tokenizer.pt").write_bytes(b"tokenizer")
    (checkpoints / "norm_stats.npz").write_bytes(b"stats")
    infer = root / "infer.py"
    infer.write_text(
        """
import argparse
import pickle

parser = argparse.ArgumentParser()
parser.add_argument("--text")
parser.add_argument("--output")
parser.add_argument("--mllm_path")
parser.add_argument("--tokenizer_pt")
parser.add_argument("--stats_npz")
parser.add_argument("--smplx_path")
args = parser.parse_args()

payload = {
    "global_orient": [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
    "body_pose": [[0.0] * 63, [0.0] * 63],
    "transl": [[0.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
}
with open(args.output, "wb") as handle:
    pickle.dump(payload, handle)
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return root


def test_motionmaster_wrapper_emits_smplx_provider_protocol(tmp_path: Path) -> None:
    root = _fake_motionmaster_root(tmp_path)
    env = os.environ.copy()
    env.update(
        {
            "CUTSCENEAI_MOTIONMASTER_ROOT": str(root),
            "CUTSCENEAI_MOTIONMASTER_SOURCE_FPS": "30",
            "CUTSCENEAI_MOTIONMASTER_REVISION": "fixture-revision",
            "CUTSCENEAI_MOTIONMASTER_FORWARD_AXIS": "+z",
        }
    )

    result = subprocess.run(
        [sys.executable, str(WRAPPER)],
        input=json.dumps(_request()),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["artifact_format"] == "smplx-axis-angle-v0.1"
    assert response["provider"] == "motionmaster-cvpr2026"
    assert response["model"] == "mllm_single_3b"
    assert response["model_revision"] == "fixture-revision"
    assert response["generated_at_inference"] is True
    assert response["retrieved_pre_authored_clip"] is False
    assert response["deterministic_algorithms"] is False
    assert response["artifact"]["fps"] == 30
    assert len(response["artifact"]["body_pose"][0]) == 63


def test_motionmaster_wrapper_rejects_identity_mismatch(tmp_path: Path) -> None:
    root = _fake_motionmaster_root(tmp_path)
    request = _request()
    request["request"]["model"] = "wrong-model"
    env = os.environ.copy()
    env.update(
        {
            "CUTSCENEAI_MOTIONMASTER_ROOT": str(root),
            "CUTSCENEAI_MOTIONMASTER_SOURCE_FPS": "30",
            "CUTSCENEAI_MOTIONMASTER_REVISION": "fixture-revision",
        }
    )

    result = subprocess.run(
        [sys.executable, str(WRAPPER)],
        input=json.dumps(request),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=False,
        timeout=30,
    )

    assert result.returncode == 1
    assert "Model identity mismatch" in result.stderr
