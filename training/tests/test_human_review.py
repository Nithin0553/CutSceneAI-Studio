from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from cutsceneai_training.amass_pilot import run_amass_turn_pilot
from cutsceneai_training.human_review import review_turn_sample
from cutsceneai_training.turn_qa import evaluate_turn_dataset


def _write_amass_turn(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    yaws = np.concatenate(
        [
            np.zeros(10),
            np.linspace(0.0, math.pi / 2.0, 31),
            np.full(10, math.pi / 2.0),
        ]
    )
    poses = np.zeros((yaws.shape[0], 156), dtype=np.float64)
    poses[:, 1] = yaws
    np.savez(
        path,
        poses=poses,
        trans=np.zeros((yaws.shape[0], 3), dtype=np.float64),
        mocap_framerate=np.array([30.0]),
    )


def _pilot_sample(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "amass"
    _write_amass_turn(source / "CMU" / "subject01" / "turn_poses.npz")
    work = tmp_path / "work"
    run_amass_turn_pilot(source, work, limit=1, license_confirmed=True)
    dataset = work / "turn-candidates"
    sample = next(path.parent for path in dataset.rglob("example.json"))
    return dataset, sample


def test_approved_review_makes_automated_pass_sample_training_ready(
    tmp_path: Path,
) -> None:
    dataset, sample = _pilot_sample(tmp_path)

    review = review_turn_sample(
        sample,
        status="approved",
        reviewer="test-reviewer",
        note="Motion is visually acceptable for the research turn baseline.",
    )
    report = evaluate_turn_dataset(dataset)

    assert review["status"] == "approved"
    assert report["automated_qa_pass_count"] == 1
    assert report["human_review_pass_count"] == 1
    assert report["training_ready_count"] == 1

    example = json.loads((sample / "example.json").read_text())
    assert (
        example["metadata"]["quality"]["training_eligibility"]
        == "human_approved_candidate"
    )
    assert example["metadata"]["quality"]["human_review"]["reviewer"] == "test-reviewer"


def test_rejected_review_never_makes_sample_training_ready(tmp_path: Path) -> None:
    dataset, sample = _pilot_sample(tmp_path)

    review_turn_sample(
        sample,
        status="rejected",
        reviewer="test-reviewer",
        note="Turn contains an unacceptable motion artifact.",
    )
    report = evaluate_turn_dataset(dataset)

    assert report["automated_qa_pass_count"] == 1
    assert report["human_review_pass_count"] == 0
    assert report["training_ready_count"] == 0
