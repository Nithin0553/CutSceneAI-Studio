from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from cutsceneai_training.smpl_canonicalize import canonicalize_smpl_motion
from cutsceneai_training.smpl_ingestion import ingest_smpl_npz
from cutsceneai_training.smpl_source import MotionRights, SMPLSourceMotion, load_smpl_npz


def _matrix_from_6d(value: np.ndarray) -> np.ndarray:
    first = np.asarray(value[:3], dtype=np.float64)
    second = np.asarray(value[3:6], dtype=np.float64)
    first /= np.linalg.norm(first)
    second = second - first * np.dot(first, second)
    second /= np.linalg.norm(second)
    third = np.cross(first, second)
    return np.column_stack((first, second, third))


def _yaw_error_deg(rotation_6d: np.ndarray, expected_yaw: float) -> float:
    rotation = _matrix_from_6d(rotation_6d)
    actual = rotation @ np.array([0.0, 0.0, -1.0])
    expected = np.array(
        [-math.sin(expected_yaw), 0.0, -math.cos(expected_yaw)],
        dtype=np.float64,
    )
    actual[1] = 0.0
    actual /= np.linalg.norm(actual)
    expected /= np.linalg.norm(expected)
    dot = float(np.clip(np.dot(actual, expected), -1.0, 1.0))
    return math.degrees(math.acos(dot))


def _source(*, fps: float = 30.0, frames: int = 2) -> SMPLSourceMotion:
    return SMPLSourceMotion(
        global_orient=np.zeros((frames, 3), dtype=np.float64),
        body_pose=np.zeros((frames, 63), dtype=np.float64),
        transl=np.zeros((frames, 3), dtype=np.float64),
        fps=fps,
        source_forward_axis="-z",
        source_record_id="fixture.npz",
    )


def test_global_orientation_is_separate_from_pelvis_local_rotation() -> None:
    source = _source()
    source.global_orient[1] = [0.0, math.pi / 2.0, 0.0]

    motion = canonicalize_smpl_motion(source)

    assert _yaw_error_deg(motion.root_rotation_6d_columns[0], 0.0) < 1e-4
    assert _yaw_error_deg(motion.root_rotation_6d_columns[1], math.pi / 2.0) < 1e-4

    identity_6d = np.array([1.0, 0.0, 0.0, 0.0, 1.0, 0.0], dtype=np.float32)
    assert np.allclose(
        motion.joint_rotations_6d_columns[:, 0],
        identity_6d,
        atol=1e-6,
    )


def test_body_pose_starts_at_canonical_joint_one() -> None:
    source = _source()
    source.body_pose[1, 0:3] = [math.pi / 4.0, 0.0, 0.0]

    motion = canonicalize_smpl_motion(source)

    identity_6d = np.array([1.0, 0.0, 0.0, 0.0, 1.0, 0.0], dtype=np.float32)
    assert np.allclose(motion.joint_rotations_6d_columns[1, 0], identity_6d)
    assert not np.allclose(motion.joint_rotations_6d_columns[1, 1], identity_6d)


def test_plus_z_source_basis_converts_translation_without_reflection() -> None:
    source = _source()
    source = SMPLSourceMotion(
        global_orient=source.global_orient,
        body_pose=source.body_pose,
        transl=np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 2.0]], dtype=np.float64),
        fps=30.0,
        source_forward_axis="+z",
        source_record_id="fixture.npz",
    )

    motion = canonicalize_smpl_motion(source)

    assert np.allclose(motion.root_position_m[0], [0.0, 0.0, 0.0])
    assert np.allclose(motion.root_position_m[-1], [-1.0, 0.0, -2.0])


def test_resampling_preserves_first_and_last_root_orientation() -> None:
    source = _source(fps=60.0, frames=3)
    source.global_orient[0] = [0.0, 0.0, 0.0]
    source.global_orient[1] = [0.0, math.pi / 4.0, 0.0]
    source.global_orient[2] = [0.0, math.pi / 2.0, 0.0]

    motion = canonicalize_smpl_motion(source)

    assert motion.frame_count == 2
    assert _yaw_error_deg(motion.root_rotation_6d_columns[0], 0.0) < 1e-4
    assert _yaw_error_deg(motion.root_rotation_6d_columns[-1], math.pi / 2.0) < 1e-4


def test_production_candidate_requires_cleared_training_and_model_use() -> None:
    with pytest.raises(ValueError, match="production_candidate"):
        MotionRights(
            rights_status="research_only",
            training_use_status="allowed",
            model_distribution_status="not_allowed",
        ).validate(usage_pool="production_candidate")

    MotionRights(
        rights_status="owned",
        training_use_status="allowed",
        model_distribution_status="allowed",
    ).validate(usage_pool="production_candidate")


def test_loads_common_poses_trans_npz_layout(tmp_path: Path) -> None:
    path = tmp_path / "capture.npz"
    poses = np.zeros((3, 66), dtype=np.float64)
    poses[-1, 1] = math.pi / 2.0
    np.savez(
        path,
        poses=poses,
        trans=np.zeros((3, 3), dtype=np.float64),
        mocap_framerate=np.array([60.0]),
    )

    source = load_smpl_npz(path)

    assert source.global_orient.shape == (3, 3)
    assert source.body_pose.shape == (3, 63)
    assert source.fps == 60.0


def test_ingestion_is_deterministic_and_auditable(tmp_path: Path) -> None:
    source_path = tmp_path / "capture.npz"
    global_orient = np.zeros((3, 3), dtype=np.float64)
    global_orient[-1, 1] = math.pi / 2.0
    np.savez(
        source_path,
        global_orient=global_orient,
        body_pose=np.zeros((3, 63), dtype=np.float64),
        transl=np.zeros((3, 3), dtype=np.float64),
        fps=np.array([60.0]),
    )
    rights = MotionRights(
        rights_status="owned",
        training_use_status="allowed",
        model_distribution_status="allowed",
        review_status="allowed",
    )

    first = ingest_smpl_npz(
        source_path,
        tmp_path / "first",
        source_dataset="owned-fixture",
        rights=rights,
        usage_pool="production_candidate",
    )
    second = ingest_smpl_npz(
        source_path,
        tmp_path / "second",
        source_dataset="owned-fixture",
        rights=rights,
        usage_pool="production_candidate",
    )

    assert first == second
    assert first["canonicalization"]["root_orientation_explicit"] is True
    assert first["canonicalization"]["pelvis_local_policy"] == "identity_root_articulation"
    assert first["rights"]["usage_pool"] == "production_candidate"

    first_json = json.loads((tmp_path / "first" / "record.json").read_text())
    second_json = json.loads((tmp_path / "second" / "record.json").read_text())
    assert first_json == second_json

    for artifact in first["artifacts"].values():
        assert (tmp_path / "first" / artifact["relative_path"]).read_bytes() == (
            tmp_path / "second" / artifact["relative_path"]
        ).read_bytes()
