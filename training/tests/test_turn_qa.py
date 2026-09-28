from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

import numpy as np

from cutsceneai_training.amass_pilot import run_amass_turn_pilot
from cutsceneai_training.turn_qa import evaluate_turn_dataset, evaluate_turn_sample


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


def _pilot(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "amass"
    _write_amass_turn(source / "CMU" / "subject01" / "turn_poses.npz")
    work = tmp_path / "work"
    run_amass_turn_pilot(
        source,
        work,
        limit=1,
        license_confirmed=True,
    )
    dataset = work / "turn-candidates"
    sample = next(path.parent for path in dataset.rglob("example.json"))
    return dataset, sample


def test_valid_candidate_passes_automated_qa_but_waits_for_human_review(
    tmp_path: Path,
) -> None:
    dataset, _ = _pilot(tmp_path)

    report = evaluate_turn_dataset(dataset)

    assert report["sample_count"] == 1
    assert report["automated_qa_pass_count"] == 1
    assert report["human_review_pass_count"] == 0
    assert report["training_ready_count"] == 0
    assert report["family_split_ok"] is True
    assert report["automated_dataset_pass"] is True


def test_wrong_target_direction_fails_facing_qa(tmp_path: Path) -> None:
    _, sample = _pilot(tmp_path)
    example_path = sample / "example.json"
    example = json.loads(example_path.read_text())

    for entity in example["conditioning"]["scene_conditioning"]["entities"]:
        if entity["entity_id"] == "target-marker":
            entity["transform"]["position_m"] = [5.0, 0.0, 0.0]
    example_path.write_text(json.dumps(example, indent=2, sort_keys=True) + "\n")

    result = evaluate_turn_sample(sample)

    assert result["facing_ok"] is False
    assert result["automated_qa_pass"] is False
    assert result["training_ready"] is False


def test_family_split_leakage_is_detected(tmp_path: Path) -> None:
    dataset, sample = _pilot(tmp_path)
    example = json.loads((sample / "example.json").read_text())
    original_split = example["identity"]["split"]
    other_split = "test" if original_split != "test" else "val"

    duplicate = dataset / other_split / f"{sample.name}-duplicate"
    shutil.copytree(sample, duplicate)
    duplicate_example_path = duplicate / "example.json"
    duplicate_example = json.loads(duplicate_example_path.read_text())
    duplicate_example["identity"]["sample_id"] += "-duplicate"
    duplicate_example["identity"]["split"] = other_split
    duplicate_example_path.write_text(
        json.dumps(duplicate_example, indent=2, sort_keys=True) + "\n"
    )

    report = evaluate_turn_dataset(dataset)

    assert report["family_split_ok"] is False
    assert duplicate_example["identity"]["family_id"] in report["family_split_leakage"]
    assert report["automated_dataset_pass"] is False
