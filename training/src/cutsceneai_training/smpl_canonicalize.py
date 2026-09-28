from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .canonical_rig import validate_canonical_rig_profile
from .resampling import resample_rotation_matrices, resample_vectors
from .rotations import (
    axis_angle_to_matrix,
    canonical_basis,
    change_rotation_basis,
    matrix_to_rotation_6d,
)
from .smpl_source import SMPLSourceMotion


@dataclass(frozen=True)
class CanonicalSMPLMotion:
    root_position_m: np.ndarray
    root_rotation_6d_columns: np.ndarray
    joint_rotations_6d_columns: np.ndarray
    source_fps: float
    target_fps: int
    translation_origin_policy: str
    source_forward_axis: str
    source_record_id: str

    @property
    def frame_count(self) -> int:
        return int(self.root_position_m.shape[0])


def canonicalize_smpl_motion(
    source: SMPLSourceMotion,
    *,
    target_fps: int = 30,
    translation_origin_policy: str = "first_frame_zero",
) -> CanonicalSMPLMotion:
    source.validate()
    validate_canonical_rig_profile()
    if target_fps != 30:
        raise ValueError("CutSceneAI canonical training motion v0.1 requires 30 fps.")
    if translation_origin_policy not in {"first_frame_zero", "preserve_source_origin"}:
        raise ValueError(
            "translation_origin_policy must be 'first_frame_zero' or "
            "'preserve_source_origin'."
        )

    basis = canonical_basis(source.source_forward_axis)
    frame_count = int(np.asarray(source.global_orient).shape[0])
    body_pose = source.body_pose_21x3()

    root_rotations = np.empty((frame_count, 3, 3), dtype=np.float64)
    joint_rotations = np.empty((frame_count, 22, 3, 3), dtype=np.float64)
    identity = np.eye(3, dtype=np.float64)

    for frame in range(frame_count):
        source_root = axis_angle_to_matrix(
            np.asarray(source.global_orient[frame], dtype=np.float64)
        )
        root_rotations[frame] = change_rotation_basis(source_root, basis)

        joint_rotations[frame, 0] = identity
        for joint in range(21):
            source_local = axis_angle_to_matrix(body_pose[frame, joint])
            joint_rotations[frame, joint + 1] = change_rotation_basis(
                source_local,
                basis,
            )

    translation = np.asarray(source.transl, dtype=np.float64)
    canonical_translation = (basis @ translation.T).T
    if translation_origin_policy == "first_frame_zero":
        canonical_translation = canonical_translation - canonical_translation[0]

    root_position_30 = resample_vectors(
        canonical_translation,
        source_fps=source.fps,
        target_fps=target_fps,
    )
    root_rotation_30 = resample_rotation_matrices(
        root_rotations,
        source_fps=source.fps,
        target_fps=target_fps,
    )
    joint_rotation_30 = resample_rotation_matrices(
        joint_rotations,
        source_fps=source.fps,
        target_fps=target_fps,
    )

    root_rotation_6d = np.empty((root_rotation_30.shape[0], 6), dtype=np.float32)
    joint_rotation_6d = np.empty(
        (joint_rotation_30.shape[0], 22, 6),
        dtype=np.float32,
    )

    for frame in range(root_rotation_30.shape[0]):
        root_rotation_6d[frame] = matrix_to_rotation_6d(root_rotation_30[frame])
        for joint in range(22):
            joint_rotation_6d[frame, joint] = matrix_to_rotation_6d(
                joint_rotation_30[frame, joint]
            )

    return CanonicalSMPLMotion(
        root_position_m=root_position_30,
        root_rotation_6d_columns=root_rotation_6d,
        joint_rotations_6d_columns=joint_rotation_6d,
        source_fps=float(source.fps),
        target_fps=target_fps,
        translation_origin_policy=translation_origin_policy,
        source_forward_axis=source.source_forward_axis,
        source_record_id=source.source_record_id,
    )
