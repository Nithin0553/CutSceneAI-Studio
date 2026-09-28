from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from cutsceneai_training.amass_pilot import (
    discover_amass_motion_files,
    run_amass_turn_pilot,
)


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


def test_amass_pilot_requires_license_confirmation(tmp_path: Path) -> None:
    source = tmp_path / "amass"
    _write_amass_turn(source / "CMU" / "subject01" / "turn_poses.npz")

    with pytest.raises(ValueError, match="license confirmation"):
        run_amass_turn_pilot(
            source,
            tmp_path / "work",
            license_confirmed=False,
        )


def test_discovers_only_amass_pose_files(tmp_path: Path) -> None:
    source = tmp_path / "amass"
    _write_amass_turn(source / "CMU" / "subject01" / "turn_poses.npz")
    np.savez(source / "ignore.npz", value=np.array([1.0]))

    files = discover_amass_motion_files(source)

    assert [path.name for path in files] == ["turn_poses.npz"]


def test_amass_pilot_produces_research_only_turn_candidate(tmp_path: Path) -> None:
    source = tmp_path / "amass"
    motion = source / "CMU" / "subject01" / "turn_poses.npz"
    _write_amass_turn(motion)

    work = tmp_path / "work"
    manifest = run_amass_turn_pilot(
        source,
        work,
        limit=1,
        license_confirmed=True,
    )

    assert manifest["status"] == "research_only"
    assert manifest["usage_pool"] == "research"
    assert manifest["source_file_count"] == 1
    assert manifest["turn_candidate_count"] == 1
    assert manifest["materialized_sample_count"] == 1
    assert manifest["training_eligibility"] == "review_candidates_only"
    assert manifest["sources"][0]["source_family_id"] == "amass:CMU/subject01"

    record_path = (
        work
        / "records"
        / "CMU"
        / "subject01"
        / "turn_poses"
        / "record.json"
    )
    record = json.loads(record_path.read_text())

    assert record["rights"]["rights_status"] == "research_only"
    assert record["rights"]["training_use_status"] == "allowed"
    assert record["rights"]["model_distribution_status"] == "unclear"
    assert record["rights"]["redistribution_status"] == "not_allowed"
    assert record["rights"]["usage_pool"] == "research"
