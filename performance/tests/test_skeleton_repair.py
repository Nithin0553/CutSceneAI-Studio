from __future__ import annotations

import math

from cutsceneai_performance import (
    BodyMotionArtifact,
    BodyMotionSample,
    CANONICAL_HUMANOID_PARENTS,
    Quaternion,
    Vector3,
    estimate_reference_bone_lengths,
    normalize_actor_skeleton,
)


_OFFSETS = (
    (0.0, 0.0, 0.0),
    (0.2, -0.1, 0.0),
    (-0.2, -0.1, 0.0),
    (0.0, 0.2, 0.0),
    (0.0, -0.4, 0.1),
    (0.0, -0.4, 0.1),
    (0.0, 0.2, 0.0),
    (0.0, -0.4, -0.1),
    (0.0, -0.4, -0.1),
    (0.0, 0.2, 0.0),
    (0.0, -0.05, 0.2),
    (0.0, -0.05, 0.2),
    (0.0, 0.2, 0.0),
    (0.15, 0.05, 0.0),
    (-0.15, 0.05, 0.0),
    (0.0, 0.2, 0.0),
    (0.25, 0.0, 0.0),
    (-0.25, 0.0, 0.0),
    (0.25, 0.0, 0.0),
    (-0.25, 0.0, 0.0),
    (0.25, 0.0, 0.0),
    (-0.25, 0.0, 0.0),
)


def _positions(scale: float) -> list[Vector3]:
    positions: list[Vector3] = []
    for index, parent in enumerate(CANONICAL_HUMANOID_PARENTS):
        if parent < 0:
            positions.append(Vector3(x=0.0, y=1.0, z=0.0))
            continue
        ox, oy, oz = _OFFSETS[index]
        source = positions[parent]
        positions.append(
            Vector3(
                x=source.x + ox * scale,
                y=source.y + oy * scale,
                z=source.z + oz * scale,
            )
        )
    return positions


def _motion(scales: list[float]) -> BodyMotionArtifact:
    identity = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
    return BodyMotionArtifact(
        fps=20,
        frame_count=len(scales),
        samples=[
            BodyMotionSample(
                frame_index=index,
                root_translation=Vector3(x=0.0, y=1.0, z=0.0),
                joint_rotations=[identity for _ in range(22)],
                joint_positions=_positions(scale),
            )
            for index, scale in enumerate(scales)
        ],
    )


def _bone_length(sample: BodyMotionSample, joint: int) -> float:
    parent = CANONICAL_HUMANOID_PARENTS[joint]
    a = sample.joint_positions[joint]
    b = sample.joint_positions[parent]
    return math.sqrt(
        (a.x - b.x) ** 2
        + (a.y - b.y) ** 2
        + (a.z - b.z) ** 2
    )


def test_reference_lengths_use_robust_actor_wide_median() -> None:
    first = _motion([1.0, 1.2])
    second = _motion([0.8, 1.0])

    lengths = estimate_reference_bone_lengths([first, second])

    # The four scale samples are 0.8, 1.0, 1.0, 1.2, so the median is 1.0.
    assert lengths[1] == _bone_length(first.samples[0], 1)


def test_normalize_actor_skeleton_makes_bone_lengths_frame_invariant() -> None:
    motions = {
        "body:walk": _motion([0.8, 1.3]),
        "body:listen": _motion([1.5, 0.7]),
    }

    repaired = normalize_actor_skeleton(motions)
    lengths = estimate_reference_bone_lengths(list(motions.values()))

    for motion in repaired.values():
        for sample in motion.samples:
            for joint, parent in enumerate(CANONICAL_HUMANOID_PARENTS):
                if parent < 0:
                    continue
                assert _bone_length(sample, joint) == lengths[joint]


def test_normalization_preserves_per_frame_bone_direction() -> None:
    motion = _motion([0.8, 1.3])
    repaired = normalize_actor_skeleton({"body:walk": motion})["body:walk"]

    for before, after in zip(motion.samples, repaired.samples, strict=True):
        joint = 4
        parent = CANONICAL_HUMANOID_PARENTS[joint]
        before_delta = (
            before.joint_positions[joint].x - before.joint_positions[parent].x,
            before.joint_positions[joint].y - before.joint_positions[parent].y,
            before.joint_positions[joint].z - before.joint_positions[parent].z,
        )
        after_delta = (
            after.joint_positions[joint].x - after.joint_positions[parent].x,
            after.joint_positions[joint].y - after.joint_positions[parent].y,
            after.joint_positions[joint].z - after.joint_positions[parent].z,
        )
        cross = (
            before_delta[1] * after_delta[2] - before_delta[2] * after_delta[1],
            before_delta[2] * after_delta[0] - before_delta[0] * after_delta[2],
            before_delta[0] * after_delta[1] - before_delta[1] * after_delta[0],
        )
        assert math.sqrt(sum(value * value for value in cross)) < 1e-9
