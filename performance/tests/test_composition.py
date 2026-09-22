from __future__ import annotations

import math

import pytest

from cutsceneai_performance._geometry import Quaternion, Vector3
from cutsceneai_performance.composition import CanonicalSceneTransform, compose_body_sequence
from cutsceneai_performance.models import BodyGenerationRequest, ModelProvenance
from cutsceneai_performance.motion import (
    CANONICAL_HUMANOID_JOINTS,
    BodyMotionArtifact,
    BodyMotionSample,
)
from cutsceneai_performance.providers import NormalizedArtifact


_HASH = "0" * 64


def _rotations(value: Quaternion) -> list[Quaternion]:
    return [value.model_copy(deep=True) for _ in CANONICAL_HUMANOID_JOINTS]


def _motion(
    roots: list[tuple[float, float, float]],
    rotations: list[Quaternion],
) -> BodyMotionArtifact:
    return BodyMotionArtifact(
        fps=24,
        frame_count=len(roots),
        samples=[
            BodyMotionSample(
                frame_index=index,
                root_translation=Vector3(x=root[0], y=root[1], z=root[2]),
                joint_rotations=_rotations(rotations[index]),
            )
            for index, root in enumerate(roots)
        ],
    )


def _request(
    semantic_id: str,
    *,
    start: int,
    end: int,
    target: str | None = None,
    prompt: str = "Generate motion.",
) -> BodyGenerationRequest:
    return BodyGenerationRequest(
        semantic_id=semantic_id,
        start_frame=start,
        end_frame=end,
        prompt=prompt,
        prompt_sha256=_HASH,
        configuration_sha256=_HASH,
        seed=1,
        provider="fixture",
        model="fixture-model",
        model_revision="r1",
        prompt_version="body-v0.1",
        actor_binding_id="actor:guard",
        source_performance_cue_id="performance:scene:beat:guard:01",
        skeleton_profile="cutsceneai-humanoid-v1",
        target_binding_id=target,
    )


def _normalized(
    request: BodyGenerationRequest,
    motion: BodyMotionArtifact,
) -> NormalizedArtifact[BodyMotionArtifact]:
    return NormalizedArtifact(
        request_semantic_id=request.semantic_id,
        artifact=motion,
        provenance=ModelProvenance(
            provider=request.provider,
            model=request.model,
            model_revision=request.model_revision,
            prompt_sha256=request.prompt_sha256,
            configuration_sha256=request.configuration_sha256,
            seed=request.seed,
            deterministic_algorithms=True,
        ),
    )




def _rotate(rotation: Quaternion, vector: Vector3) -> Vector3:
    ux, uy, uz = rotation.x, rotation.y, rotation.z
    vx, vy, vz = vector.x, vector.y, vector.z
    dot_uv = ux * vx + uy * vy + uz * vz
    dot_uu = ux * ux + uy * uy + uz * uz
    cross_x = uy * vz - uz * vy
    cross_y = uz * vx - ux * vz
    cross_z = ux * vy - uy * vx
    scale = rotation.w * rotation.w - dot_uu
    return Vector3(
        x=2.0 * dot_uv * ux + scale * vx + 2.0 * rotation.w * cross_x,
        y=2.0 * dot_uv * uy + scale * vy + 2.0 * rotation.w * cross_y,
        z=2.0 * dot_uv * uz + scale * vz + 2.0 * rotation.w * cross_z,
    )


def _multiply(first: Quaternion, second: Quaternion) -> Quaternion:
    ax, ay, az, aw = first.x, first.y, first.z, first.w
    bx, by, bz, bw = second.x, second.y, second.z, second.w
    values = (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )
    length = math.sqrt(sum(value * value for value in values))
    return Quaternion(
        x=values[0] / length,
        y=values[1] / length,
        z=values[2] / length,
        w=values[3] / length,
    )


def _ground_direction(value: Vector3) -> tuple[float, float]:
    length = math.hypot(value.x, value.z)
    return value.x / length, value.z / length


def test_compositor_rebases_root_and_blends_entry_pose() -> None:
    identity = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
    quarter_turn = Quaternion(
        x=0.0,
        y=math.sqrt(0.5),
        z=0.0,
        w=math.sqrt(0.5),
    )
    opposite = Quaternion(x=0.0, y=1.0, z=0.0, w=0.0)

    first = _request("body:scene:beat:guard:01:walk", start=0, end=2)
    second = _request("body:scene:beat:guard:01:stop", start=2, end=4)

    first_motion = _motion(
        [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0)],
        [identity, quarter_turn],
    )
    second_motion = _motion(
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)],
        [opposite, opposite],
    )

    result = compose_body_sequence(
        [first, second],
        {
            first.semantic_id: _normalized(first, first_motion),
            second.semantic_id: _normalized(second, second_motion),
        },
        blend_frames=2,
    )

    composed_first = result[first.semantic_id].artifact
    composed_second = result[second.semantic_id].artifact

    assert composed_second.samples[0].root_translation == composed_first.samples[-1].root_translation
    assert composed_second.samples[-1].root_translation == Vector3(x=3.0, y=0.0, z=0.0)
    assert (
        composed_second.samples[0].joint_rotations[0]
        == composed_first.samples[-1].joint_rotations[0]
    )
    assert composed_second.samples[-1].joint_rotations[0] == opposite

    # Composition must not mutate provider-normalized input.
    assert second_motion.samples[0].root_translation == Vector3(x=0.0, y=0.0, z=0.0)


def test_target_facing_hold_locks_root_and_pelvis_heading() -> None:
    identity = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
    quarter_turn = Quaternion(
        x=0.0,
        y=math.sqrt(0.5),
        z=0.0,
        w=math.sqrt(0.5),
    )
    opposite = Quaternion(x=0.0, y=1.0, z=0.0, w=0.0)

    turn = _request(
        "body:scene:beat:guard:01:turn",
        start=0,
        end=2,
        target="actor:door",
        prompt="Action: turn toward the door Style: cautious.",
    )
    hold = _request(
        "body:scene:beat:guard:01:hold",
        start=2,
        end=5,
        target="actor:door",
        prompt="Action: hold a cautious stance facing the door Style: cautious.",
    )

    result = compose_body_sequence(
        [turn, hold],
        {
            turn.semantic_id: _normalized(
                turn,
                _motion(
                    [(0.0, 0.0, 0.0), (0.1, 0.0, 0.0)],
                    [identity, quarter_turn],
                ),
            ),
            hold.semantic_id: _normalized(
                hold,
                _motion(
                    [(0.0, 0.0, 0.0), (0.2, 0.4, -0.2), (0.4, 0.8, -0.5)],
                    [opposite, quarter_turn, identity],
                ),
            ),
        },
        blend_frames=2,
    )

    composed_turn = result[turn.semantic_id].artifact
    composed_hold = result[hold.semantic_id].artifact
    anchor_root = composed_turn.samples[-1].root_translation
    anchor_pelvis = composed_turn.samples[-1].joint_rotations[0]

    assert all(sample.root_translation == anchor_root for sample in composed_hold.samples)
    assert all(sample.joint_rotations[0] == anchor_pelvis for sample in composed_hold.samples)



def test_turn_is_not_misclassified_as_hold_from_larger_performance_context() -> None:
    identity = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
    quarter_turn = Quaternion(
        x=0.0,
        y=math.sqrt(0.5),
        z=0.0,
        w=math.sqrt(0.5),
    )

    turn = _request(
        "body:scene:beat:guard:01:guard_turn_to_door",
        start=0,
        end=3,
        target="actor:door",
        prompt=(
            "Generate novel full-body motion. "
            "Action: turn toward the door "
            "Style: cautious. "
            "This is one atomic phase of the larger performance: "
            "Turn toward the door, settle into a cautious stance, and remain facing it."
        ),
    )

    motion = _motion(
        [(0.0, 0.0, 0.0), (0.05, 0.0, 0.0), (0.1, 0.0, 0.0)],
        [identity, quarter_turn, quarter_turn],
    )

    result = compose_body_sequence(
        [turn],
        {turn.semantic_id: _normalized(turn, motion)},
    )[turn.semantic_id].artifact

    assert result.samples[-1].root_translation.x == pytest.approx(0.1)
    assert result.samples[-1].joint_rotations[0] == quarter_turn

def test_compositor_rejects_missing_artifact() -> None:
    request = _request("body:scene:beat:guard:01:walk", start=0, end=2)

    with pytest.raises(ValueError, match="Missing normalized body artifacts"):
        compose_body_sequence([request], {})


def test_target_facing_turn_ends_facing_canonical_target() -> None:
    identity = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
    turn = _request(
        "body:scene:beat:guard:01:turn",
        start=0,
        end=3,
        target="actor:door",
        prompt="Action: turn toward the door Style: cautious.",
    )
    source = _motion(
        [(0.0, 0.0, 0.0), (0.05, 0.0, 0.0), (0.1, 0.0, 0.0)],
        [identity, identity, identity],
    )
    transforms = {
        "actor:guard": CanonicalSceneTransform(
            position=Vector3(x=0.0, y=0.0, z=-5.0),
            rotation=identity,
        ),
        "actor:door": CanonicalSceneTransform(
            position=Vector3(x=2.0, y=0.0, z=1.0),
            rotation=identity,
        ),
    }

    result = compose_body_sequence(
        [turn],
        {turn.semantic_id: _normalized(turn, source)},
        scene_transforms=transforms,
    )[turn.semantic_id].artifact

    assert result.samples[0].joint_rotations[0] == identity
    final = result.samples[-1]
    world_root = Vector3(
        x=transforms["actor:guard"].position.x + final.root_translation.x,
        y=transforms["actor:guard"].position.y + final.root_translation.y,
        z=transforms["actor:guard"].position.z + final.root_translation.z,
    )
    desired = Vector3(
        x=transforms["actor:door"].position.x - world_root.x,
        y=0.0,
        z=transforms["actor:door"].position.z - world_root.z,
    )
    actual = _rotate(
        final.joint_rotations[0],
        Vector3(x=0.0, y=0.0, z=-1.0),
    )
    actual_xz = _ground_direction(actual)
    desired_xz = _ground_direction(desired)
    assert actual_xz[0] == pytest.approx(desired_xz[0], abs=1e-6)
    assert actual_xz[1] == pytest.approx(desired_xz[1], abs=1e-6)


def test_target_facing_turn_respects_actor_initial_rotation() -> None:
    identity = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
    half = math.radians(90.0) / 2.0
    actor_rotation = Quaternion(
        x=0.0,
        y=math.sin(half),
        z=0.0,
        w=math.cos(half),
    )
    turn = _request(
        "body:scene:beat:guard:01:turn-rotated",
        start=0,
        end=3,
        target="actor:door",
        prompt="Action: pivot toward the door Style: cautious.",
    )
    source = _motion(
        [(0.0, 0.0, 0.0), (0.0, 0.0, -0.5), (0.0, 0.0, -1.0)],
        [identity, identity, identity],
    )
    transforms = {
        "actor:guard": CanonicalSceneTransform(
            position=Vector3(x=3.0, y=0.0, z=4.0),
            rotation=actor_rotation,
        ),
        "actor:door": CanonicalSceneTransform(
            position=Vector3(x=-2.0, y=0.0, z=6.0),
            rotation=identity,
        ),
    }

    result = compose_body_sequence(
        [turn],
        {turn.semantic_id: _normalized(turn, source)},
        scene_transforms=transforms,
    )[turn.semantic_id].artifact
    final = result.samples[-1]
    world_offset = _rotate(actor_rotation, final.root_translation)
    world_root = Vector3(
        x=transforms["actor:guard"].position.x + world_offset.x,
        y=transforms["actor:guard"].position.y + world_offset.y,
        z=transforms["actor:guard"].position.z + world_offset.z,
    )
    world_pelvis = _multiply(actor_rotation, final.joint_rotations[0])
    actual = _rotate(world_pelvis, Vector3(x=0.0, y=0.0, z=-1.0))
    desired = Vector3(
        x=transforms["actor:door"].position.x - world_root.x,
        y=0.0,
        z=transforms["actor:door"].position.z - world_root.z,
    )
    actual_xz = _ground_direction(actual)
    desired_xz = _ground_direction(desired)
    assert actual_xz[0] == pytest.approx(desired_xz[0], abs=1e-6)
    assert actual_xz[1] == pytest.approx(desired_xz[1], abs=1e-6)


def test_target_facing_turn_rejects_coincident_target() -> None:
    identity = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
    turn = _request(
        "body:scene:beat:guard:01:turn-coincident",
        start=0,
        end=2,
        target="actor:door",
        prompt="Action: turn toward the door Style: cautious.",
    )
    source = _motion(
        [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0)],
        [identity, identity],
    )
    transforms = {
        "actor:guard": CanonicalSceneTransform(
            position=Vector3(x=1.0, y=0.0, z=2.0),
            rotation=identity,
        ),
        "actor:door": CanonicalSceneTransform(
            position=Vector3(x=1.0, y=0.0, z=2.0),
            rotation=identity,
        ),
    }

    with pytest.raises(ValueError, match="target direction"):
        compose_body_sequence(
            [turn],
            {turn.semantic_id: _normalized(turn, source)},
            scene_transforms=transforms,
        )
