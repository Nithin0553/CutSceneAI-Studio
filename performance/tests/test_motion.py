from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import pytest
from cutsceneai_performance import (
    CANONICAL_HUMANOID_JOINTS,
    CANONICAL_HUMANOID_PARENTS,
    MOTION_RESAMPLING_METHOD,
    BodyMotionArtifact,
    BodyMotionSample,
    Quaternion,
    Vector3,
    body_motion_artifact_sha256,
    render_body_motion,
    resample_body_motion,
)
from pydantic import ValidationError


def rotations(value: Quaternion) -> list[Quaternion]:
    return [value.model_copy(deep=True) for _ in CANONICAL_HUMANOID_JOINTS]


def motion_artifact(
    *,
    second_rotation: Quaternion | None = None,
) -> BodyMotionArtifact:
    identity = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
    turn = second_rotation or Quaternion(x=0.0, y=1.0, z=0.0, w=0.0)
    return BodyMotionArtifact(
        fps=20,
        frame_count=2,
        samples=[
            BodyMotionSample(
                frame_index=0,
                root_translation=Vector3(x=0.0, y=0.0, z=0.0),
                joint_rotations=rotations(identity),
            ),
            BodyMotionSample(
                frame_index=1,
                root_translation=Vector3(x=2.0, y=4.0, z=-2.0),
                joint_rotations=rotations(turn),
            ),
        ],
    )


def test_body_motion_artifact_declares_canonical_engine_neutral_profile() -> None:
    motion = motion_artifact()

    assert tuple(motion.joint_names) == CANONICAL_HUMANOID_JOINTS
    assert tuple(motion.parent_indices) == CANONICAL_HUMANOID_PARENTS
    assert motion.coordinate_space.handedness == "right"
    assert motion.coordinate_space.forward_axis == "-z"
    assert motion.samples[0].joint_rotations[0].w == 1.0


def test_motion_render_and_file_hash_are_deterministic() -> None:
    motion = motion_artifact()

    assert render_body_motion(motion) == render_body_motion(motion)
    assert body_motion_artifact_sha256(motion) == body_motion_artifact_sha256(motion)
    assert len(body_motion_artifact_sha256(motion)) == 64


def test_resampler_fits_exact_frame_window_and_preserves_endpoints() -> None:
    source = motion_artifact()

    result = resample_body_motion(source, target_fps=24, target_frame_count=3)

    assert result.fps == 24
    assert result.frame_count == 3
    assert result.resampling is not None
    assert result.resampling.method == MOTION_RESAMPLING_METHOD
    assert result.resampling.source_fps == 20
    assert result.resampling.source_frame_count == 2
    assert result.samples[0].root_translation == source.samples[0].root_translation
    assert result.samples[-1].root_translation == source.samples[-1].root_translation
    assert result.samples[1].root_translation == Vector3(x=1.0, y=2.0, z=-1.0)
    midpoint = result.samples[1].joint_rotations[0]
    assert midpoint.y == pytest.approx(math.sqrt(0.5), abs=1e-9)
    assert midpoint.w == pytest.approx(math.sqrt(0.5), abs=1e-9)
    assert render_body_motion(result) == render_body_motion(
        resample_body_motion(source, target_fps=24, target_frame_count=3)
    )


def test_resampler_uses_shortest_quaternion_path_and_linear_near_path() -> None:
    equivalent_identity = Quaternion(x=0.0, y=0.0, z=0.0, w=-1.0)
    source = motion_artifact(second_rotation=equivalent_identity)

    result = resample_body_motion(source, target_fps=24, target_frame_count=3)

    assert result.samples[1].joint_rotations[0] == Quaternion(
        x=0.0,
        y=0.0,
        z=0.0,
        w=1.0,
    )


def test_resampler_handles_single_source_or_target_frame() -> None:
    source = motion_artifact()
    one_frame = BodyMotionArtifact(
        fps=20,
        frame_count=1,
        samples=[source.samples[0]],
    )

    repeated = resample_body_motion(one_frame, target_fps=24, target_frame_count=3)
    reduced = resample_body_motion(source, target_fps=24, target_frame_count=1)

    assert [sample.root_translation.x for sample in repeated.samples] == [0.0, 0.0, 0.0]
    assert reduced.samples == [source.samples[0]]
    assert reduced.samples[0].frame_index == 0


def test_resampler_returns_independent_copy_when_shape_is_current() -> None:
    source = motion_artifact()

    result = resample_body_motion(source, target_fps=20, target_frame_count=2)

    assert result == source
    assert result is not source
    assert result.samples[0] is not source.samples[0]


@pytest.mark.parametrize(
    ("target_fps", "target_frame_count", "message"),
    [
        (0, 2, "target_fps"),
        (241, 2, "target_fps"),
        (24, 0, "target_frame_count"),
    ],
)
def test_resampler_rejects_invalid_target_shape(
    target_fps: int,
    target_frame_count: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        resample_body_motion(
            motion_artifact(),
            target_fps=target_fps,
            target_frame_count=target_frame_count,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda payload: payload["joint_names"].reverse(),
            "joint_names",
        ),
        (
            lambda payload: payload["parent_indices"].reverse(),
            "parent_indices",
        ),
        (
            lambda payload: payload.update(frame_count=3),
            "frame_count",
        ),
        (
            lambda payload: payload["samples"][1].update(frame_index=0),
            "contiguous",
        ),
        (
            lambda payload: payload["samples"][0]["joint_rotations"].pop(),
            "at least 22 items",
        ),
        (
            lambda payload: payload["samples"][0]["joint_rotations"][0].update(w=0.5),
            "unit length",
        ),
        (
            lambda payload: payload["samples"][0]["root_translation"].update(
                x=math.inf
            ),
            "finite number",
        ),
    ],
)
def test_body_motion_rejects_malformed_artifacts(
    mutation: Callable[[dict[str, Any]], None],
    message: str,
) -> None:
    payload = motion_artifact().model_dump(mode="json")
    mutation(payload)

    with pytest.raises(ValidationError, match=message):
        BodyMotionArtifact.model_validate(payload)
