from __future__ import annotations

import math
import statistics
from collections.abc import Mapping, Sequence

from ._geometry import Vector3
from .motion import BodyMotionArtifact


_EPSILON = 1e-9


def _subtract(a: Vector3, b: Vector3) -> Vector3:
    return Vector3(x=a.x - b.x, y=a.y - b.y, z=a.z - b.z)


def _add(a: Vector3, b: Vector3) -> Vector3:
    return Vector3(x=a.x + b.x, y=a.y + b.y, z=a.z + b.z)


def _scale(value: Vector3, scalar: float) -> Vector3:
    return Vector3(
        x=value.x * scalar,
        y=value.y * scalar,
        z=value.z * scalar,
    )


def _length(value: Vector3) -> float:
    return math.sqrt(value.x * value.x + value.y * value.y + value.z * value.z)


def estimate_reference_bone_lengths(
    motions: Sequence[BodyMotionArtifact],
) -> tuple[float, ...]:
    """Estimate one robust fixed skeleton from geometry-bearing body motions.

    Medians are taken across all supplied frames so provider noise and phase-entry
    blending do not redefine body proportions frame by frame.
    """

    if not motions:
        raise ValueError("At least one motion is required.")

    names = tuple(motions[0].joint_names)
    parents = tuple(motions[0].parent_indices)
    samples_by_joint: list[list[float]] = [[] for _ in names]

    for motion in motions:
        if tuple(motion.joint_names) != names or tuple(motion.parent_indices) != parents:
            raise ValueError("All motions must use the same canonical skeleton.")
        for sample in motion.samples:
            if sample.joint_positions is None:
                raise ValueError(
                    "Skeleton normalization requires joint_positions on every sample."
                )
            for joint_index, parent_index in enumerate(parents):
                if parent_index < 0:
                    continue
                delta = _subtract(
                    sample.joint_positions[joint_index],
                    sample.joint_positions[parent_index],
                )
                length = _length(delta)
                if length > _EPSILON:
                    samples_by_joint[joint_index].append(length)

    lengths: list[float] = []
    for joint_index, parent_index in enumerate(parents):
        if parent_index < 0:
            lengths.append(0.0)
            continue
        values = samples_by_joint[joint_index]
        if not values:
            raise ValueError(
                f"Cannot estimate non-zero bone length for joint '{names[joint_index]}'."
            )
        lengths.append(float(statistics.median(values)))

    return tuple(lengths)


def project_motion_to_fixed_skeleton(
    motion: BodyMotionArtifact,
    bone_lengths: Sequence[float],
) -> BodyMotionArtifact:
    """Project XYZ geometry onto fixed bone lengths while preserving bone directions."""

    if len(bone_lengths) != len(motion.joint_names):
        raise ValueError("bone_lengths must match the canonical joint count.")

    parents = tuple(motion.parent_indices)
    fallback_directions: list[Vector3 | None] = [None] * len(parents)

    for joint_index, parent_index in enumerate(parents):
        if parent_index < 0:
            continue
        for sample in motion.samples:
            if sample.joint_positions is None:
                raise ValueError(
                    "Skeleton normalization requires joint_positions on every sample."
                )
            delta = _subtract(
                sample.joint_positions[joint_index],
                sample.joint_positions[parent_index],
            )
            magnitude = _length(delta)
            if magnitude > _EPSILON:
                fallback_directions[joint_index] = _scale(delta, 1.0 / magnitude)
                break
        if fallback_directions[joint_index] is None:
            raise ValueError(
                f"Joint '{motion.joint_names[joint_index]}' has no usable bone direction."
            )

    repaired_samples = []
    for sample in motion.samples:
        if sample.joint_positions is None:
            raise ValueError(
                "Skeleton normalization requires joint_positions on every sample."
            )

        source_positions = sample.joint_positions
        repaired: list[Vector3 | None] = [None] * len(source_positions)

        for joint_index, parent_index in enumerate(parents):
            if parent_index < 0:
                repaired[joint_index] = source_positions[joint_index].model_copy()
                continue

            source_delta = _subtract(
                source_positions[joint_index],
                source_positions[parent_index],
            )
            magnitude = _length(source_delta)
            direction = (
                _scale(source_delta, 1.0 / magnitude)
                if magnitude > _EPSILON
                else fallback_directions[joint_index]
            )
            parent_position = repaired[parent_index]
            if parent_position is None or direction is None:
                raise ValueError("Canonical skeleton hierarchy is not parent-before-child.")

            repaired[joint_index] = _add(
                parent_position,
                _scale(direction, float(bone_lengths[joint_index])),
            )

        repaired_samples.append(
            sample.model_copy(
                update={"joint_positions": repaired},
                deep=True,
            )
        )

    return motion.model_copy(update={"samples": repaired_samples}, deep=True)


def normalize_actor_skeleton(
    motions: Mapping[str, BodyMotionArtifact],
) -> dict[str, BodyMotionArtifact]:
    """Normalize all phases for one actor to one fixed canonical skeleton."""

    if not motions:
        raise ValueError("At least one actor motion is required.")
    lengths = estimate_reference_bone_lengths(list(motions.values()))
    return {
        semantic_id: project_motion_to_fixed_skeleton(motion, lengths)
        for semantic_id, motion in motions.items()
    }
