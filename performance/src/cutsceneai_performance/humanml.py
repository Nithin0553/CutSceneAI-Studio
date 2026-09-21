from __future__ import annotations

import math
from typing import Literal, Self

from pydantic import Field, model_validator

from ._geometry import Quaternion, Vector3
from .models import PerformanceModel
from .motion import BodyMotionArtifact, BodyMotionSample, CANONICAL_HUMANOID_JOINTS


HUMANML_SOURCE_FPS = 20
HUMANML_POSITION_CONVERSION_METHOD = "cutsceneai-position-to-parent-local-swing-v0.2"

_HUMANML_RAW_OFFSETS = (
    (0.0, 0.0, 0.0),
    (1.0, 0.0, 0.0),
    (-1.0, 0.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, -1.0, 0.0),
    (0.0, -1.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, -1.0, 0.0),
    (0.0, -1.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, 0.0, 1.0),
    (0.0, 0.0, 1.0),
    (0.0, 1.0, 0.0),
    (1.0, 0.0, 0.0),
    (-1.0, 0.0, 0.0),
    (0.0, 0.0, 1.0),
    (0.0, -1.0, 0.0),
    (0.0, -1.0, 0.0),
    (0.0, -1.0, 0.0),
    (0.0, -1.0, 0.0),
    (0.0, -1.0, 0.0),
    (0.0, -1.0, 0.0),
)

_PRIMARY_CHILD = {
    1: 4,
    2: 5,
    3: 6,
    4: 7,
    5: 8,
    6: 9,
    7: 10,
    8: 11,
    9: 12,
    12: 15,
    13: 16,
    14: 17,
    16: 18,
    17: 19,
    18: 20,
    19: 21,
}

_PARENT_INDICES = (
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

_EPSILON = 1e-10


class HumanMLXYZMotion(PerformanceModel):
    """HumanML3D joint positions emitted by the official MDM text-to-motion path."""

    format_version: Literal["0.1.0"] = "0.1.0"
    fps: Literal[20] = HUMANML_SOURCE_FPS
    source_distance_unit: Literal["meter"] = "meter"
    source_handedness: Literal["right"] = "right"
    source_up_axis: Literal["y"] = "y"
    source_forward_axis: Literal["+z"] = "+z"
    frame_count: int = Field(gt=0)
    joint_names: list[str] = Field(
        default_factory=lambda: list(CANONICAL_HUMANOID_JOINTS),
        min_length=22,
        max_length=22,
    )
    positions: list[list[list[float]]] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_motion(self) -> Self:
        if self.frame_count != len(self.positions):
            raise ValueError(
                "frame_count must equal the number of HumanML position frames."
            )
        if tuple(self.joint_names) != CANONICAL_HUMANOID_JOINTS:
            raise ValueError(
                "HumanML joint_names must exactly match the CutSceneAI 22-joint order."
            )
        for frame_index, frame in enumerate(self.positions):
            if len(frame) != 22:
                raise ValueError(
                    f"HumanML frame {frame_index} must contain exactly 22 joints."
                )
            for joint_index, position in enumerate(frame):
                if len(position) != 3:
                    raise ValueError(
                        f"HumanML frame {frame_index} joint {joint_index} must be a vec3."
                    )
                if not all(math.isfinite(float(value)) for value in position):
                    raise ValueError(
                        f"HumanML frame {frame_index} joint {joint_index} is not finite."
                    )
        return self


def humanml_xyz_to_canonical(motion: HumanMLXYZMotion) -> BodyMotionArtifact:
    """Convert MDM HumanML XYZ joints to CutSceneAI parent-local canonical motion.

    This is a deterministic geometric reconstruction from positions. It intentionally
    produces swing-only joint rotations because XYZ positions do not encode bone twist.
    Provider provenance must therefore distinguish this conversion from models that
    directly generate local joint rotations.
    """

    reference_directions = _reference_directions()
    previous_local: list[tuple[float, float, float, float] | None] = [None] * 22
    samples: list[BodyMotionSample] = []
    first_root = _source_position(motion.positions[0][0])

    for frame_index, raw_frame in enumerate(motion.positions):
        positions = [_source_position(position) for position in raw_frame]
        root_world = _root_orientation(positions)
        world_rotations: list[tuple[float, float, float, float]] = [
            _identity_quaternion()
        ] * 22
        local_rotations: list[tuple[float, float, float, float]] = [
            _identity_quaternion()
        ] * 22

        world_rotations[0] = root_world
        local_rotations[0] = _continuous_quaternion(previous_local[0], root_world)

        for joint_index in range(1, 22):
            parent_index = _PARENT_INDICES[joint_index]
            parent_world = world_rotations[parent_index]
            child_index = _PRIMARY_CHILD.get(joint_index)
            if child_index is None:
                world_rotation = parent_world
                local_rotation = _identity_quaternion()
            else:
                expected_world = _rotate_vector(
                    parent_world,
                    reference_directions[joint_index],
                )
                observed_world = _normalize_vector(
                    _subtract(positions[child_index], positions[joint_index]),
                    label=f"frame {frame_index} joint {joint_index} bone",
                )
                swing_world = _quaternion_from_to(expected_world, observed_world)
                world_rotation = _normalize_quaternion(
                    _multiply_quaternion(swing_world, parent_world)
                )
                local_rotation = _normalize_quaternion(
                    _multiply_quaternion(
                        _inverse_quaternion(parent_world),
                        world_rotation,
                    )
                )

            world_rotations[joint_index] = world_rotation
            local_rotations[joint_index] = _continuous_quaternion(
                previous_local[joint_index],
                local_rotation,
            )

        previous_local = list(local_rotations)
        root = _subtract(positions[0], first_root)
        samples.append(
            BodyMotionSample(
                frame_index=frame_index,
                root_translation=Vector3(x=root[0], y=root[1], z=root[2]),
                joint_rotations=[
                    Quaternion(x=value[0], y=value[1], z=value[2], w=value[3])
                    for value in local_rotations
                ],
            )
        )

    return BodyMotionArtifact(
        fps=motion.fps,
        frame_count=motion.frame_count,
        samples=samples,
    )


def _reference_directions() -> list[tuple[float, float, float]]:
    directions = [(0.0, 1.0, 0.0)] * 22
    for joint_index, child_index in _PRIMARY_CHILD.items():
        directions[joint_index] = _normalize_vector(
            _source_position(_HUMANML_RAW_OFFSETS[child_index]),
            label=f"reference joint {joint_index}",
        )
    return directions


def _source_position(
    value: list[float] | tuple[float, float, float],
) -> tuple[float, float, float]:
    if len(value) != 3:
        raise ValueError("HumanML source positions must contain exactly three values.")
    # The validated S02 boundary records HumanML as RH/Y-up/+Z-forward and the
    # canonical contract as RH/Y-up/-Z-forward. This reflection matches the
    # established CutSceneAI provider/engine coordinate boundary.
    return (float(value[0]), float(value[1]), -float(value[2]))


def _root_orientation(
    positions: list[tuple[float, float, float]],
) -> tuple[float, float, float, float]:
    right = _normalize_vector(
        _subtract(positions[1], positions[2]),
        label="root hip axis",
    )
    up_seed = _normalize_vector(
        _subtract(positions[3], positions[0]),
        label="root spine axis",
    )
    up = _subtract(up_seed, _scale(right, _dot(up_seed, right)))
    up = _normalize_vector(up, label="orthogonal root up axis")
    positive_z = _normalize_vector(_cross(right, up), label="root +Z axis")
    up = _normalize_vector(_cross(positive_z, right), label="root corrected up axis")
    return _quaternion_from_basis(right, up, positive_z)


def _quaternion_from_basis(
    x_axis: tuple[float, float, float],
    y_axis: tuple[float, float, float],
    z_axis: tuple[float, float, float],
) -> tuple[float, float, float, float]:
    m00, m10, m20 = x_axis
    m01, m11, m21 = y_axis
    m02, m12, m22 = z_axis
    trace = m00 + m11 + m22

    if trace > 0.0:
        scale = math.sqrt(trace + 1.0) * 2.0
        value = (
            (m21 - m12) / scale,
            (m02 - m20) / scale,
            (m10 - m01) / scale,
            0.25 * scale,
        )
    elif m00 > m11 and m00 > m22:
        scale = math.sqrt(1.0 + m00 - m11 - m22) * 2.0
        value = (
            0.25 * scale,
            (m01 + m10) / scale,
            (m02 + m20) / scale,
            (m21 - m12) / scale,
        )
    elif m11 > m22:
        scale = math.sqrt(1.0 + m11 - m00 - m22) * 2.0
        value = (
            (m01 + m10) / scale,
            0.25 * scale,
            (m12 + m21) / scale,
            (m02 - m20) / scale,
        )
    else:
        scale = math.sqrt(1.0 + m22 - m00 - m11) * 2.0
        value = (
            (m02 + m20) / scale,
            (m12 + m21) / scale,
            0.25 * scale,
            (m10 - m01) / scale,
        )
    return _normalize_quaternion(value)


def _quaternion_from_to(
    source: tuple[float, float, float],
    target: tuple[float, float, float],
) -> tuple[float, float, float, float]:
    first = _normalize_vector(source, label="source direction")
    second = _normalize_vector(target, label="target direction")
    dot = max(-1.0, min(1.0, _dot(first, second)))
    if dot > 1.0 - 1e-9:
        return _identity_quaternion()
    if dot < -1.0 + 1e-9:
        axis = _stable_orthogonal_axis(first)
        return (axis[0], axis[1], axis[2], 0.0)

    cross = _cross(first, second)
    return _normalize_quaternion((cross[0], cross[1], cross[2], 1.0 + dot))


def _stable_orthogonal_axis(
    value: tuple[float, float, float],
) -> tuple[float, float, float]:
    candidates = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    basis = min(candidates, key=lambda candidate: abs(_dot(value, candidate)))
    return _normalize_vector(_cross(value, basis), label="antiparallel rotation axis")


def _rotate_vector(
    quaternion: tuple[float, float, float, float],
    vector: tuple[float, float, float],
) -> tuple[float, float, float]:
    vector_quaternion = (vector[0], vector[1], vector[2], 0.0)
    rotated = _multiply_quaternion(
        _multiply_quaternion(quaternion, vector_quaternion),
        _inverse_quaternion(quaternion),
    )
    return (rotated[0], rotated[1], rotated[2])


def _multiply_quaternion(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    ax, ay, az, aw = first
    bx, by, bz, bw = second
    return (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )


def _inverse_quaternion(
    value: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    return (-value[0], -value[1], -value[2], value[3])


def _normalize_quaternion(
    value: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    length = math.sqrt(sum(component * component for component in value))
    if length <= _EPSILON:
        raise ValueError("Quaternion magnitude is zero.")
    return tuple(component / length for component in value)  # type: ignore[return-value]


def _continuous_quaternion(
    previous: tuple[float, float, float, float] | None,
    current: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    normalized = _normalize_quaternion(current)
    if previous is None or _dot4(previous, normalized) >= 0.0:
        return normalized
    return tuple(-component for component in normalized)  # type: ignore[return-value]


def _normalize_vector(
    value: tuple[float, float, float],
    *,
    label: str,
) -> tuple[float, float, float]:
    length = math.sqrt(_dot(value, value))
    if length <= _EPSILON:
        raise ValueError(f"{label} has zero length.")
    return (value[0] / length, value[1] / length, value[2] / length)


def _subtract(
    first: tuple[float, float, float],
    second: tuple[float, float, float],
) -> tuple[float, float, float]:
    return (
        first[0] - second[0],
        first[1] - second[1],
        first[2] - second[2],
    )


def _scale(
    value: tuple[float, float, float],
    amount: float,
) -> tuple[float, float, float]:
    return (value[0] * amount, value[1] * amount, value[2] * amount)


def _dot(
    first: tuple[float, float, float], second: tuple[float, float, float]
) -> float:
    return first[0] * second[0] + first[1] * second[1] + first[2] * second[2]


def _dot4(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    return sum(a * b for a, b in zip(first, second, strict=True))


def _cross(
    first: tuple[float, float, float],
    second: tuple[float, float, float],
) -> tuple[float, float, float]:
    return (
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    )


def _identity_quaternion() -> tuple[float, float, float, float]:
    return (0.0, 0.0, 0.0, 1.0)
