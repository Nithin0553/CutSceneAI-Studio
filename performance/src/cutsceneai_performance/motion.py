from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from ._geometry import Quaternion, Vector3, interpolate_vector3, slerp_quaternion
from ._resampling import (
    TRANSFORM_RESAMPLING_METHOD,
    resolve_sample_window,
    validate_resampling_target,
)
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
    TRANSFORM_RESAMPLING_METHOD
)


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

    validate_resampling_target(
        target_fps=target_fps,
        target_frame_count=target_frame_count,
    )
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
    lower_index, upper_index, alpha = resolve_sample_window(
        source_frame_count=motion.frame_count,
        target_index=target_index,
        target_frame_count=target_frame_count,
    )
    lower = motion.samples[lower_index]
    upper = motion.samples[upper_index]
    return BodyMotionSample(
        frame_index=target_index,
        root_translation=interpolate_vector3(
            lower.root_translation, upper.root_translation, alpha
        ),
        joint_rotations=[
            slerp_quaternion(first, second, alpha)
            for first, second in zip(
                lower.joint_rotations,
                upper.joint_rotations,
                strict=True,
            )
        ],
    )
