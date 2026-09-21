from __future__ import annotations

from collections.abc import Sequence
import math
from typing import Any


CANONICAL_JOINT_NAMES = (
    "pelvis",
    "left_hip",
    "right_hip",
    "spine1",
    "left_knee",
    "right_knee",
    "spine2",
    "left_ankle",
    "right_ankle",
    "spine3",
    "left_foot",
    "right_foot",
    "neck",
    "left_collar",
    "right_collar",
    "head",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
)

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

_HY_MOTION_JOINT_COUNT = 22
_HY_MOTION_SOURCE_FPS = 30


def _finite(value: float, *, label: str) -> float:
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{label} must be finite.")
    return numeric


def _normalize_quaternion(
    quaternion: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    length = math.sqrt(sum(component * component for component in quaternion))
    if length <= 1e-12:
        raise ValueError("Quaternion magnitude is zero.")
    return tuple(component / length for component in quaternion)  # type: ignore[return-value]


def _axis_angle_to_quaternion(
    axis_angle: Sequence[float],
) -> tuple[float, float, float, float]:
    if len(axis_angle) != 3:
        raise ValueError("Axis-angle rotations must contain exactly three values.")

    x = _finite(axis_angle[0], label="axis-angle x")
    y = _finite(axis_angle[1], label="axis-angle y")
    z = _finite(axis_angle[2], label="axis-angle z")
    angle = math.sqrt(x * x + y * y + z * z)
    if angle <= 1e-12:
        return (0.0, 0.0, 0.0, 1.0)

    scale = math.sin(angle * 0.5) / angle
    return _normalize_quaternion(
        (
            x * scale,
            y * scale,
            z * scale,
            math.cos(angle * 0.5),
        )
    )


def _source_to_cutsceneai_quaternion(
    quaternion: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    """Convert HY-Motion +Z-forward rotations to CutSceneAI -Z-forward coordinates.

    HY-Motion's public SMPL-H representation is right-handed, meter-scale, Y-up,
    with +Z forward. CutSceneAI's canonical contract is right-handed, meter-scale,
    Y-up, with -Z forward. Conjugating a rotation matrix by the Z reflection maps
    quaternion (x, y, z, w) to (-x, -y, z, w).
    """

    x, y, z, w = quaternion
    return _normalize_quaternion((-x, -y, z, w))


def _continuous_quaternion(
    previous: tuple[float, float, float, float] | None,
    current: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    if previous is None:
        return current
    dot = sum(first * second for first, second in zip(previous, current, strict=True))
    if dot >= 0.0:
        return current
    return tuple(-component for component in current)  # type: ignore[return-value]


def _frame_axis_angles(frame: Sequence[Any]) -> list[Sequence[float]]:
    if len(frame) >= _HY_MOTION_JOINT_COUNT and all(
        isinstance(value, Sequence) and not isinstance(value, (str, bytes))
        for value in frame[:_HY_MOTION_JOINT_COUNT]
    ):
        joints = list(frame[:_HY_MOTION_JOINT_COUNT])
        if any(len(joint) != 3 for joint in joints):
            raise ValueError("Nested HY-Motion pose joints must each contain three values.")
        return joints

    flat = list(frame)
    required = _HY_MOTION_JOINT_COUNT * 3
    if len(flat) < required:
        raise ValueError(
            f"HY-Motion pose frame contains {len(flat)} values; at least {required} are required."
        )
    return [flat[index : index + 3] for index in range(0, required, 3)]


def convert_hymotion_smplh_to_cutsceneai(
    poses: Sequence[Sequence[Any]],
    translations: Sequence[Sequence[float]],
    *,
    source_fps: int = _HY_MOTION_SOURCE_FPS,
) -> dict[str, Any]:
    """Convert HY-Motion's SMPL-H pose output into CutSceneAI canonical body motion.

    The first 22 SMPL-H joints have the exact semantic order used by
    cutsceneai-humanoid-v1. HY-Motion stores local joint rotations as axis-angle
    vectors and absolute global root translation. CutSceneAI stores reference-pose
    relative parent-local quaternions plus root displacement from the first frame.
    """

    if source_fps < 1 or source_fps > 240:
        raise ValueError("source_fps must be between 1 and 240.")
    if not poses:
        raise ValueError("HY-Motion output contains no pose frames.")
    if len(poses) != len(translations):
        raise ValueError("HY-Motion pose and translation frame counts must match.")

    first_translation = translations[0]
    if len(first_translation) != 3:
        raise ValueError("HY-Motion translations must contain exactly three values.")
    origin_x = _finite(first_translation[0], label="translation x")
    origin_y = _finite(first_translation[1], label="translation y")
    origin_z = _finite(first_translation[2], label="translation z")

    previous_quaternions: list[tuple[float, float, float, float] | None] = [
        None
    ] * _HY_MOTION_JOINT_COUNT
    samples: list[dict[str, Any]] = []

    for frame_index, (pose_frame, translation) in enumerate(
        zip(poses, translations, strict=True)
    ):
        if len(translation) != 3:
            raise ValueError("HY-Motion translations must contain exactly three values.")
        x = _finite(translation[0], label="translation x") - origin_x
        y = _finite(translation[1], label="translation y") - origin_y
        z = _finite(translation[2], label="translation z") - origin_z

        joint_rotations: list[dict[str, float]] = []
        for joint_index, axis_angle in enumerate(_frame_axis_angles(pose_frame)):
            source_quaternion = _axis_angle_to_quaternion(axis_angle)
            converted = _source_to_cutsceneai_quaternion(source_quaternion)
            converted = _continuous_quaternion(
                previous_quaternions[joint_index],
                converted,
            )
            previous_quaternions[joint_index] = converted
            qx, qy, qz, qw = converted
            joint_rotations.append({"x": qx, "y": qy, "z": qz, "w": qw})

        samples.append(
            {
                "frame_index": frame_index,
                "root_translation": {"x": x, "y": y, "z": -z},
                "joint_rotations": joint_rotations,
            }
        )

    return {
        "artifact_version": "0.1.0",
        "skeleton_profile": "cutsceneai-humanoid-v1",
        "coordinate_space": {
            "distance_unit": "meter",
            "handedness": "right",
            "up_axis": "y",
            "forward_axis": "-z",
            "rotation_representation": "quaternion_xyzw",
        },
        "root_translation_space": "reference-pose-offset",
        "joint_rotation_space": "reference-pose-relative-parent-local",
        "fps": source_fps,
        "frame_count": len(samples),
        "joint_names": list(CANONICAL_JOINT_NAMES),
        "parent_indices": list(CANONICAL_PARENT_INDICES),
        "samples": samples,
    }
