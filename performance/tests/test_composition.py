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


def _joint_positions(root: Vector3) -> list[Vector3]:
    offsets = [
        Vector3(x=0.0, y=0.0, z=0.0),
        Vector3(x=-0.2, y=0.0, z=0.0),
        Vector3(x=0.2, y=0.0, z=0.0),
        Vector3(x=0.0, y=0.3, z=0.0),
    ]
    values = [
        Vector3(x=root.x + offset.x, y=root.y + offset.y, z=root.z + offset.z)
        for offset in offsets
    ]
    while len(values) < len(CANONICAL_HUMANOID_JOINTS):
        values.append(root.model_copy(deep=True))
    return values


def _motion_with_positions(
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
                joint_positions=_joint_positions(
                    Vector3(x=root[0], y=root[1], z=root[2])
                ),
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

    assert composed_second.samples[0].root_translation.x > composed_first.samples[-1].root_translation.x
    assert composed_second.samples[-1].root_translation.x > composed_second.samples[0].root_translation.x
    assert (
        composed_second.samples[0].joint_rotations[0]
        != composed_first.samples[-1].joint_rotations[0]
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
    anchor_root = composed_hold.samples[0].root_translation
    anchor_pelvis = composed_hold.samples[0].joint_rotations[0]

    assert anchor_root == composed_turn.samples[-1].root_translation
    assert anchor_pelvis == composed_turn.samples[-1].joint_rotations[0]
    assert all(sample.root_translation == anchor_root for sample in composed_hold.samples)
    assert all(sample.joint_rotations == composed_turn.samples[-1].joint_rotations for sample in composed_hold.samples)



def test_stationary_listen_reuses_previous_composed_pose() -> None:
    identity = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
    opposite = Quaternion(x=0.0, y=1.0, z=0.0, w=0.0)
    stop = _request(
        "body:scene:beat:guard:01:stop",
        start=0,
        end=2,
        prompt="Action: decelerate and stop walking Style: restrained.",
    )
    listen = _request(
        "body:scene:beat:guard:01:listen",
        start=2,
        end=5,
        prompt="Action: hold a guarded listening pose Style: tense stillness.",
    )

    result = compose_body_sequence(
        [stop, listen],
        {
            stop.semantic_id: _normalized(
                stop,
                _motion_with_positions(
                    [(0.0, 0.0, 0.0), (0.1, 0.0, 0.0)],
                    [identity, identity],
                ),
            ),
            listen.semantic_id: _normalized(
                listen,
                _motion_with_positions(
                    [(0.0, 0.0, 0.0), (0.5, 0.4, 0.2), (1.0, 0.8, 0.4)],
                    [opposite, opposite, opposite],
                ),
            ),
        },
    )

    previous = result[stop.semantic_id].artifact.samples[-1]
    composed_listen = result[listen.semantic_id].artifact
    for sample in composed_listen.samples:
        assert sample.root_translation == previous.root_translation
        assert sample.joint_rotations == previous.joint_rotations
        assert sample.joint_positions == previous.joint_positions


def test_scene_conditioned_turn_with_previous_pose_pivots_from_previous_stance() -> None:
    identity = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
    opposite = Quaternion(x=0.0, y=1.0, z=0.0, w=0.0)
    stop = _request(
        "body:scene:beat:guard:01:stop",
        start=0,
        end=2,
        prompt="Action: stop walking Style: restrained.",
    )
    turn = _request(
        "body:scene:beat:guard:01:turn",
        start=2,
        end=5,
        target="actor:door",
        prompt="Action: turn toward the door Style: cautious.",
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

    source_turn = _motion_with_positions(
        [(0.0, 0.0, 0.0), (0.8, 0.5, 0.5), (1.5, 1.0, 1.0)],
        [opposite, opposite, opposite],
    )
    result = compose_body_sequence(
        [stop, turn],
        {
            stop.semantic_id: _normalized(
                stop,
                _motion_with_positions(
                    [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0)],
                    [identity, identity],
                ),
            ),
            turn.semantic_id: _normalized(turn, source_turn),
        },
        scene_transforms=transforms,
    )

    previous = result[stop.semantic_id].artifact.samples[-1]
    composed_turn = result[turn.semantic_id].artifact
    assert composed_turn.samples[0].root_translation == previous.root_translation
    assert composed_turn.samples[0].joint_positions == previous.joint_positions
    assert composed_turn.samples[-1].joint_rotations[1] == previous.joint_rotations[1]
    assert composed_turn.samples[-1].root_translation != source_turn.samples[-1].root_translation

    foot_index = CANONICAL_HUMANOID_JOINTS.index("left_foot")
    pivot = previous.joint_positions[foot_index]
    assert all(
        sample.joint_positions is not None
        and sample.joint_positions[foot_index] == pivot
        for sample in composed_turn.samples
    )

    final = composed_turn.samples[-1]
    desired = Vector3(
        x=transforms["actor:door"].position.x - final.root_translation.x,
        y=0.0,
        z=transforms["actor:door"].position.z
        - (transforms["actor:guard"].position.z + final.root_translation.z),
    )
    actual = _rotate(
        final.joint_rotations[0],
        Vector3(x=0.0, y=0.0, z=-1.0),
    )
    actual_xz = _ground_direction(actual)
    desired_xz = _ground_direction(desired)
    assert actual_xz[0] == pytest.approx(desired_xz[0], abs=1e-6)
    assert actual_xz[1] == pytest.approx(desired_xz[1], abs=1e-6)


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


def test_scene_conditioned_walk_root_is_aligned_to_canonical_forward() -> None:
    identity = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
    walk = _request(
        "body:scene:beat:guard:01:walk",
        start=0,
        end=3,
        prompt="Action: walk cautiously through the hallway Style: cautious.",
    )
    source = _motion(
        [(0.0, 0.0, 0.0), (0.1, 0.0, 1.0), (0.2, 0.0, 2.0)],
        [identity, identity, identity],
    )
    transforms = {
        "actor:guard": CanonicalSceneTransform(
            position=Vector3(x=0.0, y=0.0, z=-5.0),
            rotation=identity,
        ),
    }

    result = compose_body_sequence(
        [walk],
        {walk.semantic_id: _normalized(walk, source)},
        scene_transforms=transforms,
    )[walk.semantic_id].artifact

    first = result.samples[0].root_translation
    final = result.samples[-1].root_translation
    displacement = Vector3(
        x=final.x - first.x,
        y=0.0,
        z=final.z - first.z,
    )
    direction = _ground_direction(displacement)
    assert direction[0] == pytest.approx(0.0, abs=1e-6)
    assert direction[1] == pytest.approx(-1.0, abs=1e-6)
    assert math.hypot(displacement.x, displacement.z) == pytest.approx(
        math.hypot(0.2, 2.0),
        abs=1e-6,
    )
    assert result.samples[-1].joint_rotations[0] == identity


def test_scene_conditioned_walk_root_respects_actor_world_rotation() -> None:
    identity = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
    half_turn = Quaternion(x=0.0, y=1.0, z=0.0, w=0.0)
    walk = _request(
        "body:scene:beat:guard:01:walk",
        start=0,
        end=2,
        prompt="Action: walk down the hallway Style: cautious.",
    )
    source = _motion(
        [(0.0, 0.0, 0.0), (0.0, 0.0, 2.0)],
        [identity, identity],
    )
    transforms = {
        "actor:guard": CanonicalSceneTransform(
            position=Vector3(x=0.0, y=0.0, z=-5.0),
            rotation=half_turn,
        ),
    }

    result = compose_body_sequence(
        [walk],
        {walk.semantic_id: _normalized(walk, source)},
        scene_transforms=transforms,
    )[walk.semantic_id].artifact

    local_displacement = result.samples[-1].root_translation
    world_displacement = _rotate(half_turn, local_displacement)
    direction = _ground_direction(world_displacement)
    assert direction[0] == pytest.approx(0.0, abs=1e-6)
    assert direction[1] == pytest.approx(1.0, abs=1e-6)


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


def test_compositor_keeps_xyz_atomic_through_rebase_and_entry_blend() -> None:
    identity = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
    opposite = Quaternion(x=0.0, y=1.0, z=0.0, w=0.0)
    first = _request("body:scene:beat:guard:01:walk-xyz", start=0, end=2)
    second = _request("body:scene:beat:guard:01:stop-xyz", start=2, end=4)

    result = compose_body_sequence(
        [first, second],
        {
            first.semantic_id: _normalized(
                first,
                _motion_with_positions(
                    [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0)],
                    [identity, identity],
                ),
            ),
            second.semantic_id: _normalized(
                second,
                _motion_with_positions(
                    [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)],
                    [opposite, opposite],
                ),
            ),
        },
        blend_frames=2,
    )

    composed_first = result[first.semantic_id].artifact
    composed_second = result[second.semantic_id].artifact
    first_end = composed_first.samples[-1]
    second_start = composed_second.samples[0]

    assert second_start.root_translation != first_end.root_translation
    assert second_start.joint_positions != first_end.joint_positions
    for sample in composed_second.samples:
        assert sample.joint_positions is not None
        assert sample.joint_positions[0] == sample.root_translation


def test_locomotion_alignment_translates_xyz_with_root_edit() -> None:
    identity = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
    walk = _request(
        "body:scene:beat:guard:01:walk-xyz-align",
        start=0,
        end=3,
        prompt="Action: walk through the hallway Style: cautious.",
    )
    source = _motion_with_positions(
        [(0.0, 0.0, 0.0), (0.1, 0.0, 1.0), (0.2, 0.0, 2.0)],
        [identity, identity, identity],
    )
    transforms = {
        "actor:guard": CanonicalSceneTransform(
            position=Vector3(x=0.0, y=0.0, z=0.0),
            rotation=identity,
        ),
    }

    result = compose_body_sequence(
        [walk],
        {walk.semantic_id: _normalized(walk, source)},
        scene_transforms=transforms,
    )[walk.semantic_id].artifact

    for original, composed in zip(source.samples, result.samples, strict=True):
        assert composed.joint_positions is not None
        root_edit = Vector3(
            x=composed.root_translation.x - original.root_translation.x,
            y=composed.root_translation.y - original.root_translation.y,
            z=composed.root_translation.z - original.root_translation.z,
        )
        for original_position, composed_position in zip(
            original.joint_positions,
            composed.joint_positions,
            strict=True,
        ):
            assert composed_position == Vector3(
                x=original_position.x + root_edit.x,
                y=original_position.y + root_edit.y,
                z=original_position.z + root_edit.z,
            )


def test_target_turn_rotates_xyz_with_pelvis_heading() -> None:
    identity = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
    turn = _request(
        "body:scene:beat:guard:01:turn-xyz",
        start=0,
        end=3,
        target="actor:door",
        prompt="Action: turn toward the door Style: cautious.",
    )
    source = _motion_with_positions(
        [(0.0, 0.0, 0.0)] * 3,
        [identity, identity, identity],
    )
    transforms = {
        "actor:guard": CanonicalSceneTransform(
            position=Vector3(x=0.0, y=0.0, z=0.0),
            rotation=identity,
        ),
        "actor:door": CanonicalSceneTransform(
            position=Vector3(x=2.0, y=0.0, z=2.0),
            rotation=identity,
        ),
    }

    result = compose_body_sequence(
        [turn],
        {turn.semantic_id: _normalized(turn, source)},
        scene_transforms=transforms,
    )[turn.semantic_id].artifact

    final = result.samples[-1]
    assert final.joint_positions is not None
    source_left_hip = source.samples[-1].joint_positions[1]
    final_left_hip = final.joint_positions[1]
    source_offset = Vector3(
        x=source_left_hip.x - source.samples[-1].root_translation.x,
        y=source_left_hip.y - source.samples[-1].root_translation.y,
        z=source_left_hip.z - source.samples[-1].root_translation.z,
    )
    final_offset = Vector3(
        x=final_left_hip.x - final.root_translation.x,
        y=final_left_hip.y - final.root_translation.y,
        z=final_left_hip.z - final.root_translation.z,
    )
    expected_offset = _rotate(final.joint_rotations[0], source_offset)
    assert final_offset.x == pytest.approx(expected_offset.x, abs=1e-6)
    assert final_offset.y == pytest.approx(expected_offset.y, abs=1e-6)
    assert final_offset.z == pytest.approx(expected_offset.z, abs=1e-6)


def test_target_hold_locks_xyz_root_and_heading_atomically() -> None:
    identity = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
    quarter_turn = Quaternion(
        x=0.0,
        y=math.sqrt(0.5),
        z=0.0,
        w=math.sqrt(0.5),
    )
    hold = _request(
        "body:scene:beat:guard:01:hold-xyz",
        start=0,
        end=3,
        target="actor:door",
        prompt="Action: remain still facing toward the door Style: cautious.",
    )
    source = _motion_with_positions(
        [(0.0, 0.0, 0.0), (0.4, 0.0, 0.2), (0.8, 0.0, 0.5)],
        [identity, quarter_turn, quarter_turn],
    )

    result = compose_body_sequence(
        [hold],
        {hold.semantic_id: _normalized(hold, source)},
    )[hold.semantic_id].artifact

    anchor_root = result.samples[0].root_translation
    anchor_rotation = result.samples[0].joint_rotations[0]
    for sample in result.samples:
        assert sample.root_translation == anchor_root
        assert sample.joint_rotations[0] == anchor_rotation
        assert sample.joint_positions is not None
        assert sample.joint_positions[0] == anchor_root


def test_phase_entry_velocity_blends_without_zero_step_boundary() -> None:
    identity = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
    first = _request("body:scene:beat:guard:01:fast", start=0, end=3)
    second = _request("body:scene:beat:guard:01:slow", start=3, end=6)

    result = compose_body_sequence(
        [first, second],
        {
            first.semantic_id: _normalized(
                first,
                _motion_with_positions(
                    [(0.0, 0.0, 0.0), (0.5, 0.0, 0.0), (1.0, 0.0, 0.0)],
                    [identity, identity, identity],
                ),
            ),
            second.semantic_id: _normalized(
                second,
                _motion_with_positions(
                    [(0.0, 0.0, 0.0), (0.1, 0.0, 0.0), (0.2, 0.0, 0.0)],
                    [identity, identity, identity],
                ),
            ),
        },
        blend_frames=3,
    )

    previous = result[first.semantic_id].artifact
    current = result[second.semantic_id].artifact
    previous_step = previous.samples[-1].root_translation.x - previous.samples[-2].root_translation.x
    boundary_step = current.samples[0].root_translation.x - previous.samples[-1].root_translation.x
    next_step = current.samples[1].root_translation.x - current.samples[0].root_translation.x
    final_step = current.samples[2].root_translation.x - current.samples[1].root_translation.x

    assert previous_step == pytest.approx(0.5)
    assert 0.1 < boundary_step < previous_step
    assert final_step == pytest.approx(0.1)
    assert previous_step > boundary_step > next_step > final_step - 1e-9
    assert current.samples[0].joint_positions[0] == current.samples[0].root_translation
