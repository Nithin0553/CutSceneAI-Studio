from __future__ import annotations

import math
from typing import Literal, Self

from pydantic import Field, model_validator

from .models import CoordinateSpace, Identifier, PerformanceModel

CANONICAL_HUMANOID_JOINTS = (
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
CANONICAL_HUMANOID_PARENTS = (
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
MOTION_RESAMPLING_METHOD: Literal["endpoint-preserving-linear-slerp-v1"] = (
    "endpoint-preserving-linear-slerp-v1"
)
MOTION_FLOAT_PRECISION = 9
QUATERNION_UNIT_TOLERANCE = 1e-5


class Vector3(PerformanceModel):
    x: float
    y: float
    z: float


class Quaternion(PerformanceModel):
    x: float
    y: float
    z: float
    w: float

    @model_validator(mode="after")
    def validate_unit_length(self) -> Self:
        length = math.sqrt(
            math.fsum(component * component for component in _quat(self))
        )
        if abs(length - 1.0) > QUATERNION_UNIT_TOLERANCE:
            raise ValueError("Quaternion must have unit length within 1e-5.")
        return self


class BodyMotionSample(PerformanceModel):
    frame_index: int = Field(ge=0)
    root_translation: Vector3
    joint_rotations: list[Quaternion] = Field(
        min_length=len(CANONICAL_HUMANOID_JOINTS),
        max_length=len(CANONICAL_HUMANOID_JOINTS),
    )


class MotionResamplingRecord(PerformanceModel):
    method: Literal["endpoint-preserving-linear-slerp-v1"] = MOTION_RESAMPLING_METHOD
    source_fps: int = Field(ge=1, le=240)
    source_frame_count: int = Field(gt=0)


class BodyMotionArtifact(PerformanceModel):
    artifact_version: Literal["0.1.0"] = "0.1.0"
    skeleton_profile: Literal["cutsceneai-humanoid-v1"] = "cutsceneai-humanoid-v1"
    coordinate_space: CoordinateSpace = Field(default_factory=CoordinateSpace)
    fps: int = Field(ge=1, le=240)
    frame_count: int = Field(gt=0)
    joint_names: list[Identifier] = Field(
        default_factory=lambda: list(CANONICAL_HUMANOID_JOINTS),
        min_length=len(CANONICAL_HUMANOID_JOINTS),
        max_length=len(CANONICAL_HUMANOID_JOINTS),
        json_schema_extra={"const": list(CANONICAL_HUMANOID_JOINTS)},
    )
    parent_indices: list[int] = Field(
        default_factory=lambda: list(CANONICAL_HUMANOID_PARENTS),
        min_length=len(CANONICAL_HUMANOID_PARENTS),
        max_length=len(CANONICAL_HUMANOID_PARENTS),
        json_schema_extra={"const": list(CANONICAL_HUMANOID_PARENTS)},
    )
    samples: list[BodyMotionSample] = Field(min_length=1)
    resampling: MotionResamplingRecord | None = None

    @model_validator(mode="after")
    def validate_motion_contract(self) -> Self:
        if tuple(self.joint_names) != CANONICAL_HUMANOID_JOINTS:
            raise ValueError(
                "joint_names must exactly match cutsceneai-humanoid-v1 order."
            )
        if tuple(self.parent_indices) != CANONICAL_HUMANOID_PARENTS:
            raise ValueError(
                "parent_indices must exactly match cutsceneai-humanoid-v1 hierarchy."
            )
        if self.frame_count != len(self.samples):
            raise ValueError("frame_count must equal the number of motion samples.")
        expected_indices = list(range(self.frame_count))
        if [sample.frame_index for sample in self.samples] != expected_indices:
            raise ValueError(
                "Motion sample frame_index values must be contiguous from zero."
            )
        return self


def resample_body_motion(
    motion: BodyMotionArtifact,
    *,
    target_fps: int,
    target_frame_count: int,
) -> BodyMotionArtifact:
    """Fit motion to an exact frame window using linear translation and quaternion SLERP."""

    if not 1 <= target_fps <= 240:
        raise ValueError("target_fps must be between 1 and 240.")
    if target_frame_count < 1:
        raise ValueError("target_frame_count must be greater than zero.")
    if motion.fps == target_fps and motion.frame_count == target_frame_count:
        return motion.model_copy(deep=True)

    samples = [
        _sample_at(motion, target_index, target_frame_count)
        for target_index in range(target_frame_count)
    ]
    return BodyMotionArtifact(
        fps=target_fps,
        frame_count=target_frame_count,
        samples=samples,
        resampling=MotionResamplingRecord(
            source_fps=motion.fps,
            source_frame_count=motion.frame_count,
        ),
    )


def _sample_at(
    motion: BodyMotionArtifact,
    target_index: int,
    target_frame_count: int,
) -> BodyMotionSample:
    if motion.frame_count == 1 or target_frame_count == 1:
        source_position = 0.0
    else:
        source_position = (
            target_index * (motion.frame_count - 1) / (target_frame_count - 1)
        )
    lower_index = math.floor(source_position)
    upper_index = min(lower_index + 1, motion.frame_count - 1)
    alpha = source_position - lower_index
    lower = motion.samples[lower_index]
    upper = motion.samples[upper_index]
    return BodyMotionSample(
        frame_index=target_index,
        root_translation=_lerp_vector(
            lower.root_translation, upper.root_translation, alpha
        ),
        joint_rotations=[
            _slerp_quaternion(first, second, alpha)
            for first, second in zip(
                lower.joint_rotations,
                upper.joint_rotations,
                strict=True,
            )
        ],
    )


def _lerp_vector(first: Vector3, second: Vector3, alpha: float) -> Vector3:
    return Vector3(
        x=_stable_float(first.x + (second.x - first.x) * alpha),
        y=_stable_float(first.y + (second.y - first.y) * alpha),
        z=_stable_float(first.z + (second.z - first.z) * alpha),
    )


def _slerp_quaternion(
    first: Quaternion, second: Quaternion, alpha: float
) -> Quaternion:
    first_values = _quat(first)
    second_values = _quat(second)
    dot = math.fsum(a * b for a, b in zip(first_values, second_values, strict=True))
    if dot < 0.0:
        second_values = (
            -second_values[0],
            -second_values[1],
            -second_values[2],
            -second_values[3],
        )
        dot = -dot
    dot = max(-1.0, min(1.0, dot))
    if dot > 0.9995:
        values = (
            first_values[0] + (second_values[0] - first_values[0]) * alpha,
            first_values[1] + (second_values[1] - first_values[1]) * alpha,
            first_values[2] + (second_values[2] - first_values[2]) * alpha,
            first_values[3] + (second_values[3] - first_values[3]) * alpha,
        )
    else:
        theta = math.acos(dot)
        sin_theta = math.sin(theta)
        first_weight = math.sin((1.0 - alpha) * theta) / sin_theta
        second_weight = math.sin(alpha * theta) / sin_theta
        values = (
            first_weight * first_values[0] + second_weight * second_values[0],
            first_weight * first_values[1] + second_weight * second_values[1],
            first_weight * first_values[2] + second_weight * second_values[2],
            first_weight * first_values[3] + second_weight * second_values[3],
        )
    normalized = _normalize_quaternion(values)
    return Quaternion(
        x=_stable_float(normalized[0]),
        y=_stable_float(normalized[1]),
        z=_stable_float(normalized[2]),
        w=_stable_float(normalized[3]),
    )


def _quat(value: Quaternion) -> tuple[float, float, float, float]:
    return (value.x, value.y, value.z, value.w)


def _normalize_quaternion(
    values: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    length = math.sqrt(math.fsum(component * component for component in values))
    return (
        values[0] / length,
        values[1] / length,
        values[2] / length,
        values[3] / length,
    )


def _stable_float(value: float) -> float:
    rounded = round(value, MOTION_FLOAT_PRECISION)
    return 0.0 if rounded == 0.0 else rounded
