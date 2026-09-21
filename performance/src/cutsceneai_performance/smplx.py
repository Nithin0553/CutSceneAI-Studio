from __future__ import annotations

import math
from typing import Literal, Self

from pydantic import Field, model_validator

from ._geometry import Quaternion, Vector3
from .models import PerformanceModel
from .motion import BodyMotionArtifact, BodyMotionSample, CANONICAL_HUMANOID_JOINTS


SMPL22_JOINTS = CANONICAL_HUMANOID_JOINTS


class SMPLXAxisAngleMotion(PerformanceModel):
    """Minimal SMPL/SMPL-X body motion needed for CutSceneAI canonicalization."""

    format_version: Literal["0.1.0"] = "0.1.0"
    fps: int = Field(ge=1, le=240)
    source_forward_axis: Literal["+z", "-z"] = "+z"
    global_orient: list[list[float]] = Field(min_length=1)
    body_pose: list[list[float]] = Field(min_length=1)
    transl: list[list[float]] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_shapes(self) -> Self:
        frame_count = len(self.global_orient)
        if len(self.body_pose) != frame_count or len(self.transl) != frame_count:
            raise ValueError("SMPL-X arrays must have identical frame counts.")
        if any(len(item) != 3 for item in self.global_orient):
            raise ValueError("global_orient must contain one axis-angle vec3 per frame.")
        if any(len(item) != 63 for item in self.body_pose):
            raise ValueError("body_pose must contain 21 SMPL-X axis-angle joints (63 values).")
        if any(len(item) != 3 for item in self.transl):
            raise ValueError("transl must contain one vec3 per frame.")
        return self


def smplx_axis_angle_to_canonical(motion: SMPLXAxisAngleMotion) -> BodyMotionArtifact:
    """Convert SMPL-X 22-joint axis-angle motion into CutSceneAI canonical body motion.

    SMPL-X root plus 21 body joints uses the same semantic joint ordering as the
    CutSceneAI humanoid profile. Root translation becomes an offset from frame zero.
    A +Z-forward source is rotated 180 degrees around Y into CutSceneAI -Z forward.
    """

    origin = motion.transl[0]
    basis = Quaternion(x=0.0, y=1.0, z=0.0, w=0.0)
    basis_inverse = Quaternion(x=0.0, y=-1.0, z=0.0, w=0.0)

    samples: list[BodyMotionSample] = []
    for frame_index, (root_axis, pose_values, translation) in enumerate(
        zip(motion.global_orient, motion.body_pose, motion.transl, strict=True)
    ):
        rotations = [_axis_angle_to_quaternion(root_axis)]
        rotations.extend(
            _axis_angle_to_quaternion(pose_values[index : index + 3])
            for index in range(0, 63, 3)
        )
        if motion.source_forward_axis == "+z":
            rotations = [
                _multiply_quaternion(
                    _multiply_quaternion(basis, rotation),
                    basis_inverse,
                )
                for rotation in rotations
            ]

        root = (
            translation[0] - origin[0],
            translation[1] - origin[1],
            translation[2] - origin[2],
        )
        if motion.source_forward_axis == "+z":
            root = (-root[0], root[1], -root[2])

        samples.append(
            BodyMotionSample(
                frame_index=frame_index,
                root_translation=Vector3(x=root[0], y=root[1], z=root[2]),
                joint_rotations=rotations,
            )
        )

    return BodyMotionArtifact(
        fps=motion.fps,
        frame_count=len(samples),
        samples=samples,
    )


def _axis_angle_to_quaternion(value: list[float]) -> Quaternion:
    x, y, z = value
    angle = math.sqrt(x * x + y * y + z * z)
    if angle < 1e-12:
        return Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
    scale = math.sin(angle / 2.0) / angle
    return Quaternion(
        x=x * scale,
        y=y * scale,
        z=z * scale,
        w=math.cos(angle / 2.0),
    )


def _multiply_quaternion(first: Quaternion, second: Quaternion) -> Quaternion:
    return Quaternion(
        x=first.w * second.x
        + first.x * second.w
        + first.y * second.z
        - first.z * second.y,
        y=first.w * second.y
        - first.x * second.z
        + first.y * second.w
        + first.z * second.x,
        z=first.w * second.z
        + first.x * second.y
        - first.y * second.x
        + first.z * second.w,
        w=first.w * second.w
        - first.x * second.x
        - first.y * second.y
        - first.z * second.z,
    )
