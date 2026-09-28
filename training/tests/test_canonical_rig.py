from __future__ import annotations

import math

import numpy as np

from cutsceneai_training.canonical_rig import (
    CANONICAL_PARENT_INDICES,
    CANONICAL_REFERENCE_OFFSET_DIRECTIONS,
    IDENTITY_ROTATION_6D,
    neutral_joint_rotations,
    validate_canonical_rig_profile,
)
from cutsceneai_training.rotations import (
    axis_angle_to_matrix,
    canonical_basis,
    change_rotation_basis,
    matrix_to_rotation_6d,
    rotation_6d_to_matrix,
)
from cutsceneai_training.smpl_canonicalize import canonicalize_smpl_motion
from cutsceneai_training.smpl_source import SMPLSourceMotion


def _neutral_smpl(frames: int = 2) -> SMPLSourceMotion:
    return SMPLSourceMotion(
        global_orient=np.zeros((frames, 3), dtype=np.float64),
        body_pose=np.zeros((frames, 63), dtype=np.float64),
        transl=np.zeros((frames, 3), dtype=np.float64),
        fps=30.0,
        source_forward_axis="+z",
        source_record_id="neutral.npz",
    )


def test_canonical_rig_profile_is_structurally_valid() -> None:
    validate_canonical_rig_profile()

    assert len(CANONICAL_PARENT_INDICES) == 22
    assert CANONICAL_REFERENCE_OFFSET_DIRECTIONS.shape == (22, 3)
    assert np.allclose(
        np.linalg.norm(CANONICAL_REFERENCE_OFFSET_DIRECTIONS[1:], axis=1),
        1.0,
    )


def test_neutral_rotation_table_is_identity() -> None:
    neutral = neutral_joint_rotations(frame_count=3)

    assert neutral.shape == (3, 22, 6)
    assert np.allclose(neutral, IDENTITY_ROTATION_6D)


def test_neutral_smpl_maps_to_identity_canonical_joint_deltas() -> None:
    motion = canonicalize_smpl_motion(_neutral_smpl())

    assert np.allclose(
        motion.joint_rotations_6d_columns,
        neutral_joint_rotations(frame_count=motion.frame_count),
        atol=1e-6,
    )
    assert np.allclose(
        motion.root_rotation_6d_columns,
        np.broadcast_to(IDENTITY_ROTATION_6D, (motion.frame_count, 6)),
        atol=1e-6,
    )


def test_smpl_global_orientation_does_not_leak_into_pelvis_local_delta() -> None:
    source = _neutral_smpl()
    source.global_orient[1] = [0.0, math.pi / 2.0, 0.0]

    motion = canonicalize_smpl_motion(source)

    assert not np.allclose(motion.root_rotation_6d_columns[1], IDENTITY_ROTATION_6D)
    assert np.allclose(
        motion.joint_rotations_6d_columns[1, 0],
        IDENTITY_ROTATION_6D,
        atol=1e-6,
    )


def test_plus_z_basis_conversion_is_proper_rotation() -> None:
    basis = canonical_basis("+z")

    assert np.allclose(basis.T @ basis, np.eye(3), atol=1e-8)
    assert np.linalg.det(basis) == np.float64(1.0)
    assert np.allclose(
        basis @ np.array([0.0, 0.0, 1.0]),
        [0.0, 0.0, -1.0],
    )


def test_local_axis_delta_is_conjugated_into_canonical_basis() -> None:
    source_rotation = axis_angle_to_matrix(
        np.array([math.pi / 4.0, 0.0, 0.0], dtype=np.float64)
    )
    basis = canonical_basis("+z")

    canonical = change_rotation_basis(source_rotation, basis)
    encoded = matrix_to_rotation_6d(canonical)
    decoded = rotation_6d_to_matrix(encoded)

    expected = axis_angle_to_matrix(
        np.array([-math.pi / 4.0, 0.0, 0.0], dtype=np.float64)
    )
    assert np.allclose(decoded, expected, atol=1e-6)
