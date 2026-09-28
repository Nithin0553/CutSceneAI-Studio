from __future__ import annotations

import numpy as np

from .geometry import JOINT_NAMES


CANONICAL_RIG_PROFILE_ID = "cutsceneai-humanoid-v1"

CANONICAL_PARENT_INDICES = (
    -1,
    0,
    0,
    0,
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    9,
    9,
    12,
    13,
    14,
    16,
    17,
    18,
    19,
)

CANONICAL_REFERENCE_OFFSET_DIRECTIONS = np.asarray(
    [
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [-1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, -1.0, 0.0],
        [0.0, -1.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, -1.0, 0.0],
        [0.0, -1.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
        [0.0, 0.0, 1.0],
        [0.0, 1.0, 0.0],
        [1.0, 0.0, 0.0],
        [-1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0],
        [0.0, -1.0, 0.0],
        [0.0, -1.0, 0.0],
        [0.0, -1.0, 0.0],
        [0.0, -1.0, 0.0],
        [0.0, -1.0, 0.0],
        [0.0, -1.0, 0.0],
    ],
    dtype=np.float32,
)

IDENTITY_ROTATION_6D = np.asarray(
    [1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
    dtype=np.float32,
)


def validate_canonical_rig_profile() -> None:
    if len(JOINT_NAMES) != 22:
        raise ValueError("Canonical rig must contain exactly 22 joints.")
    if len(CANONICAL_PARENT_INDICES) != len(JOINT_NAMES):
        raise ValueError("Canonical parent table must match joint count.")
    if CANONICAL_REFERENCE_OFFSET_DIRECTIONS.shape != (22, 3):
        raise ValueError(
            "Canonical reference offset directions must have shape [22, 3]."
        )
    if CANONICAL_PARENT_INDICES[0] != -1:
        raise ValueError("Canonical pelvis must be the root joint.")
    for index, parent in enumerate(CANONICAL_PARENT_INDICES[1:], start=1):
        if parent < 0 or parent >= index:
            raise ValueError(
                f"Canonical joint {index} has invalid parent index {parent}."
            )

    lengths = np.linalg.norm(CANONICAL_REFERENCE_OFFSET_DIRECTIONS[1:], axis=1)
    if not np.allclose(lengths, 1.0, atol=1e-7):
        raise ValueError(
            "Canonical v0.1 reference offsets are direction-only unit vectors."
        )


def neutral_joint_rotations(frame_count: int = 1) -> np.ndarray:
    if frame_count < 1:
        raise ValueError("frame_count must be positive.")
    return np.broadcast_to(
        IDENTITY_ROTATION_6D,
        (frame_count, len(JOINT_NAMES), 6),
    ).copy()
