from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from cutsceneai_training import GuardTurnDatasetConfig, generate_guard_turn_dataset


def _rotation_matrix_from_6d(value: np.ndarray) -> np.ndarray:
    first = value[:3].astype(np.float64)
    second = value[3:6].astype(np.float64)
    first /= np.linalg.norm(first)
    second = second - first * np.dot(first, second)
    second /= np.linalg.norm(second)
    third = np.cross(first, second)
    return np.column_stack((first, second, third))


def test_guard_turn_dataset_is_deterministic(tmp_path: Path) -> None:
    config = GuardTurnDatasetConfig(
        seed=42,
        num_families=4,
        variants_per_family=2,
    )
    first = generate_guard_turn_dataset(tmp_path / "a", config=config)
    second = generate_guard_turn_dataset(tmp_path / "b", config=config)

    assert first["dataset_fingerprint"] == second["dataset_fingerprint"]
    assert first["split_counts"] == second["split_counts"]

    for record in first["samples"]:
        relative = Path(record["split"]) / record["sample_id"]
        left = tmp_path / "a" / relative
        right = tmp_path / "b" / relative
        assert (left / "example.json").read_bytes() == (
            right / "example.json"
        ).read_bytes()

        first_example = json.loads((left / "example.json").read_text())
        for artifact in first_example["artifacts"].values():
            assert (left / artifact["relative_path"]).read_bytes() == (
                right / artifact["relative_path"]
            ).read_bytes()


def test_family_members_never_cross_splits(tmp_path: Path) -> None:
    manifest = generate_guard_turn_dataset(
        tmp_path,
        config=GuardTurnDatasetConfig(
            seed=7,
            num_families=12,
            variants_per_family=3,
        ),
    )

    split_by_family: dict[str, set[str]] = {}
    for sample in manifest["samples"]:
        split_by_family.setdefault(sample["family_id"], set()).add(sample["split"])

    assert all(len(splits) == 1 for splits in split_by_family.values())
    assert manifest["split_counts"]["train"] > 0
    assert manifest["split_counts"]["val"] > 0
    assert manifest["split_counts"]["test"] > 0


def test_final_root_faces_bound_door(tmp_path: Path) -> None:
    manifest = generate_guard_turn_dataset(
        tmp_path,
        config=GuardTurnDatasetConfig(
            seed=11,
            num_families=3,
            variants_per_family=1,
        ),
    )
    record = manifest["samples"][0]
    sample_dir = tmp_path / record["split"] / record["sample_id"]
    example = json.loads((sample_dir / "example.json").read_text())

    entities = {
        item["entity_id"]: item
        for item in example["conditioning"]["scene_conditioning"]["entities"]
    }
    guard = np.asarray(
        entities["guard"]["transform"]["position_m"],
        dtype=np.float64,
    )
    door = np.asarray(
        entities["door"]["transform"]["position_m"],
        dtype=np.float64,
    )
    desired = door - guard
    desired[1] = 0.0
    desired /= np.linalg.norm(desired)

    root_rotations = np.load(sample_dir / "root_rotation_6d_columns.npy")
    rotation = _rotation_matrix_from_6d(root_rotations[-1])
    actual = rotation @ np.array([0.0, 0.0, -1.0])
    actual[1] = 0.0
    actual /= np.linalg.norm(actual)

    dot = float(np.clip(np.dot(actual, desired), -1.0, 1.0))
    error_deg = math.degrees(math.acos(dot))
    assert error_deg < 1e-3


def test_turn_preserves_at_least_one_support_foot(tmp_path: Path) -> None:
    manifest = generate_guard_turn_dataset(
        tmp_path,
        config=GuardTurnDatasetConfig(
            seed=99,
            num_families=3,
            variants_per_family=1,
        ),
    )
    record = manifest["samples"][0]
    sample_dir = tmp_path / record["split"] / record["sample_id"]

    left = np.load(sample_dir / "left_foot_contact.npy").astype(bool)
    right = np.load(sample_dir / "right_foot_contact.npy").astype(bool)

    assert np.all(left | right)


def test_contract_dataset_is_not_marked_training_ready(tmp_path: Path) -> None:
    manifest = generate_guard_turn_dataset(
        tmp_path,
        config=GuardTurnDatasetConfig(
            seed=5,
            num_families=3,
            variants_per_family=1,
        ),
    )

    assert manifest["status"] == "contract_validation_only"
    assert manifest["training_eligibility"] == "contract_validation_only"
    assert manifest["usage_pool"] == "research"
