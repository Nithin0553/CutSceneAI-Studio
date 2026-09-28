from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from cutsceneai_training.rotations import rotation_6d_to_matrix
from cutsceneai_training.smpl_ingestion import ingest_smpl_npz
from cutsceneai_training.smpl_source import MotionRights
from cutsceneai_training.turn_candidates import materialize_turn_candidates
from cutsceneai_training.turn_mining import mine_canonical_record


def _write_turn_source(path: Path) -> None:
    yaws = np.concatenate(
        [
            np.zeros(10),
            np.linspace(0.0, math.pi / 2.0, 31),
            np.full(10, math.pi / 2.0),
        ]
    )
    global_orient = np.zeros((yaws.shape[0], 3), dtype=np.float64)
    global_orient[:, 1] = yaws
    np.savez(
        path,
        global_orient=global_orient,
        body_pose=np.zeros((yaws.shape[0], 63), dtype=np.float64),
        transl=np.zeros((yaws.shape[0], 3), dtype=np.float64),
        fps=np.array([30.0]),
    )


def _research_rights() -> MotionRights:
    return MotionRights(
        rights_status="owned",
        training_use_status="allowed",
        model_distribution_status="allowed",
        review_status="allowed",
    )


def test_materialized_target_matches_observed_final_facing(tmp_path: Path) -> None:
    source = tmp_path / "turn.npz"
    _write_turn_source(source)

    record_dir = tmp_path / "record"
    ingest_smpl_npz(
        source,
        record_dir,
        source_dataset="owned-fixture",
        source_family_id="capture-session-a",
        rights=_research_rights(),
        usage_pool="research",
        source_forward_axis="-z",
    )
    mined = mine_canonical_record(record_dir)
    assert mined["candidate_count"] == 1

    output = tmp_path / "dataset"
    manifest = materialize_turn_candidates(record_dir, output)
    assert manifest["sample_count"] == 1
    assert manifest["source_family_id"] == "capture-session-a"

    sample = manifest["samples"][0]
    sample_dir = output / sample["split"] / sample["sample_id"]
    example = json.loads((sample_dir / "example.json").read_text())

    entities = {
        item["entity_id"]: item
        for item in example["conditioning"]["scene_conditioning"]["entities"]
    }
    target = np.asarray(
        entities["target-marker"]["transform"]["position_m"],
        dtype=np.float64,
    )
    root_position = np.load(sample_dir / "root_position_m.npy")
    root_rotation = np.load(sample_dir / "root_rotation_6d_columns.npy")

    final_root = root_position[-1].astype(np.float64)
    desired = target - final_root
    desired[1] = 0.0
    desired /= np.linalg.norm(desired)

    rotation = rotation_6d_to_matrix(root_rotation[-1])
    actual = rotation @ np.array([0.0, 0.0, -1.0], dtype=np.float64)
    actual[1] = 0.0
    actual /= np.linalg.norm(actual)

    assert float(np.dot(actual, desired)) == pytest.approx(1.0, abs=1e-6)
    assert example["targets"]["contact_gaze"]["available"] is False
    assert example["targets"]["camera"]["available"] is False
    assert (
        example["metadata"]["target_proxy"]["kind"]
        == "synthetic_directional_proxy"
    )
    assert (
        example["metadata"]["quality"]["training_eligibility"]
        == "review_candidate"
    )


def test_materialized_clip_rebases_root_translation(tmp_path: Path) -> None:
    source = tmp_path / "turn.npz"
    _write_turn_source(source)

    record_dir = tmp_path / "record"
    ingest_smpl_npz(
        source,
        record_dir,
        source_dataset="owned-fixture",
        source_family_id="capture-session-b",
        rights=_research_rights(),
        usage_pool="research",
        source_forward_axis="-z",
    )
    mine_canonical_record(record_dir)
    output = tmp_path / "dataset"
    manifest = materialize_turn_candidates(record_dir, output)

    sample = manifest["samples"][0]
    sample_dir = output / sample["split"] / sample["sample_id"]
    root_position = np.load(sample_dir / "root_position_m.npy")

    assert np.allclose(root_position[0], [0.0, 0.0, 0.0])


def test_same_source_family_gets_same_split(tmp_path: Path) -> None:
    splits: list[str] = []
    for index in range(2):
        source = tmp_path / f"turn-{index}.npz"
        _write_turn_source(source)
        record_dir = tmp_path / f"record-{index}"
        ingest_smpl_npz(
            source,
            record_dir,
            source_dataset="owned-fixture",
            source_family_id="shared-capture-family",
            rights=_research_rights(),
            usage_pool="research",
            source_forward_axis="-z",
        )
        mine_canonical_record(record_dir)
        manifest = materialize_turn_candidates(
            record_dir,
            tmp_path / f"dataset-{index}",
        )
        splits.append(str(manifest["split"]))

    assert splits[0] == splits[1]
