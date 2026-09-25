from __future__ import annotations

import math

import pytest

from cutsceneai_performance import (
    BodyGenerationRequest,
    BodyMotionArtifact,
    BodyMotionSample,
    CameraGenerationRequest,
    CanonicalSceneTransform,
    Quaternion,
    Vector3,
    synthesize_reference_body_sequence,
    synthesize_reference_camera_sequence,
)


_HASH = "0" * 64
_NAMES = (
    "pelvis", "left_hip", "right_hip", "spine1", "left_knee",
    "right_knee", "spine2", "left_ankle", "right_ankle", "spine3",
    "left_foot", "right_foot", "neck", "left_collar", "right_collar",
    "head", "left_shoulder", "right_shoulder", "left_elbow",
    "right_elbow", "left_wrist", "right_wrist",
)
_OFFSETS = (
    (0.0, 0.0, 0.0), (-0.15, -0.10, 0.0), (0.15, -0.10, 0.0),
    (0.0, 0.20, 0.0), (-0.15, -0.50, 0.0), (0.15, -0.50, 0.0),
    (0.0, 0.40, 0.0), (-0.15, -0.90, 0.0), (0.15, -0.90, 0.0),
    (0.0, 0.60, 0.0), (-0.15, -0.95, -0.10), (0.15, -0.95, -0.10),
    (0.0, 0.80, 0.0), (-0.12, 0.65, 0.0), (0.12, 0.65, 0.0),
    (0.0, 0.98, 0.0), (-0.25, 0.65, 0.0), (0.25, 0.65, 0.0),
    (-0.45, 0.40, 0.0), (0.45, 0.40, 0.0), (-0.55, 0.15, 0.0),
    (0.55, 0.15, 0.0),
)


def _identity() -> Quaternion:
    return Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)


def _body_request(
    name: str,
    start: int,
    end: int,
    action: str,
    *,
    target: str | None = None,
) -> BodyGenerationRequest:
    return BodyGenerationRequest(
        semantic_id=f"body:scene:beat:guard:01:{name}",
        start_frame=start,
        end_frame=end,
        prompt=f"Generate novel full-body motion. Action: {action} Style: natural.",
        prompt_sha256=_HASH,
        configuration_sha256=_HASH,
        seed=1,
        provider="fixture",
        model="fixture",
        model_revision="r1",
        prompt_version="v1",
        actor_binding_id="actor:guard",
        source_performance_cue_id="performance:scene:beat:guard:01",
        skeleton_profile="cutsceneai-humanoid-v1",
        target_binding_id=target,
    )


def _camera_request(
    name: str,
    start: int,
    end: int,
    prompt: str,
    *,
    targets: list[str],
) -> CameraGenerationRequest:
    return CameraGenerationRequest(
        semantic_id=f"camera:scene:{name}",
        start_frame=start,
        end_frame=end,
        prompt=prompt,
        prompt_sha256=_HASH,
        configuration_sha256=_HASH,
        seed=1,
        provider="fixture",
        model="fixture",
        model_revision="r1",
        prompt_version="v1",
        camera_binding_id=f"camera:{name}",
        source_camera_cut_id=f"shot:{name}",
        subject_binding_ids=["actor:guard"],
        target_binding_ids=targets,
        lens_mm=50.0,
    )


def _motion(frame_count: int, *, walk: bool) -> BodyMotionArtifact:
    samples = []
    for frame in range(frame_count):
        root = Vector3(
            x=0.0,
            y=0.0,
            z=(-0.08 * frame if walk else 0.0),
        )
        positions = [
            Vector3(x=root.x + x, y=root.y + y, z=root.z + z)
            for x, y, z in _OFFSETS
        ]
        samples.append(
            BodyMotionSample(
                frame_index=frame,
                root_translation=root,
                joint_rotations=[_identity() for _ in _NAMES],
                joint_positions=positions,
            )
        )
    return BodyMotionArtifact(fps=24, frame_count=frame_count, samples=samples)


def _requests() -> list[BodyGenerationRequest]:
    return [
        _body_request("walk", 0, 10, "walk steadily through the hallway"),
        _body_request("stop", 10, 14, "decelerate and stop walking"),
        _body_request("listen", 14, 18, "hold a guarded listening pose"),
        _body_request(
            "turn", 18, 24, "turn toward the door", target="actor:door"
        ),
        _body_request(
            "hold", 24, 30, "hold a cautious stance facing the door",
            target="actor:door",
        ),
    ]


def _transforms() -> dict[str, CanonicalSceneTransform]:
    half_turn = Quaternion(x=0.0, y=1.0, z=0.0, w=0.0)
    return {
        "actor:guard": CanonicalSceneTransform(
            position=Vector3(x=0.0, y=0.0, z=-5.0),
            rotation=half_turn,
        ),
        "actor:door": CanonicalSceneTransform(
            position=Vector3(x=2.85, y=1.1, z=1.0),
            rotation=_identity(),
        ),
        "actor:hallway": CanonicalSceneTransform(
            position=Vector3(x=0.0, y=0.0, z=0.0),
            rotation=_identity(),
        ),
    }


def test_reference_body_is_continuous_planted_and_target_facing() -> None:
    requests = _requests()
    sources = {
        request.semantic_id: _motion(
            request.end_frame - request.start_frame,
            walk=request.semantic_id.endswith(":walk"),
        )
        for request in requests
    }

    result = synthesize_reference_body_sequence(
        requests,
        sources,
        scene_transforms=_transforms(),
        fps=24,
    )

    walk = result[requests[0].semantic_id]
    stop = result[requests[1].semantic_id]
    listen = result[requests[2].semantic_id]
    turn = result[requests[3].semantic_id]
    hold = result[requests[4].semantic_id]

    assert stop.samples[-1].root_translation.z < walk.samples[-1].root_translation.z
    assert all(
        sample.root_translation == listen.samples[0].root_translation
        for sample in listen.samples
    )
    assert all(
        sample.joint_positions == listen.samples[0].joint_positions
        for sample in listen.samples
    )

    left_foot = _NAMES.index("left_foot")
    assert all(
        sample.joint_positions is not None
        and sample.joint_positions[left_foot]
        == turn.samples[0].joint_positions[left_foot]
        for sample in turn.samples
    )
    assert turn.samples[-1].joint_rotations[0] != turn.samples[0].joint_rotations[0]
    assert all(
        sample.root_translation == hold.samples[0].root_translation
        for sample in hold.samples
    )
    assert all(
        sample.joint_rotations == hold.samples[0].joint_rotations
        for sample in hold.samples
    )


def test_reference_body_uses_one_fixed_skeleton() -> None:
    requests = _requests()
    sources = {
        request.semantic_id: _motion(
            request.end_frame - request.start_frame,
            walk=request.semantic_id.endswith(":walk"),
        )
        for request in requests
    }
    result = synthesize_reference_body_sequence(
        requests,
        sources,
        scene_transforms=_transforms(),
        fps=24,
    )

    parents = next(iter(result.values())).parent_indices
    reference: list[float | None] = [None] * len(parents)
    for motion in result.values():
        for sample in motion.samples:
            assert sample.joint_positions is not None
            for index, parent in enumerate(parents):
                if parent < 0:
                    continue
                a = sample.joint_positions[index]
                b = sample.joint_positions[parent]
                length = math.dist((a.x, a.y, a.z), (b.x, b.y, b.z))
                if reference[index] is None:
                    reference[index] = length
                assert length == pytest.approx(reference[index], abs=1e-8)


def test_reference_cameras_stage_actor_and_bound_door() -> None:
    requests = _requests()
    sources = {
        request.semantic_id: _motion(
            request.end_frame - request.start_frame,
            walk=request.semantic_id.endswith(":walk"),
        )
        for request in requests
    }
    body = synthesize_reference_body_sequence(
        requests,
        sources,
        scene_transforms=_transforms(),
        fps=24,
    )
    cameras = [
        _camera_request(
            "wide", 0, 8, "wide establishing shot", targets=["actor:hallway"]
        ),
        _camera_request(
            "reaction", 8, 16, "medium_close_up reaction", targets=["actor:guard"]
        ),
        _camera_request(
            "door", 16, 22, "environment_detail insert of door", targets=["actor:door"]
        ),
        _camera_request(
            "ots", 22, 30, "over_the_shoulder dialogue", targets=["actor:guard", "actor:door"]
        ),
    ]

    result = synthesize_reference_camera_sequence(
        cameras,
        requests,
        body,
        scene_transforms=_transforms(),
        fps=24,
    )

    starts = [result[request.semantic_id].samples[0].position for request in cameras]
    assert len({(item.x, item.y, item.z) for item in starts}) == len(cameras)
    door_rotation = result[cameras[2].semantic_id].samples[0].rotation
    assert door_rotation != _identity()
    for artifact in result.values():
        for sample in artifact.samples:
            q = sample.rotation
            magnitude = math.sqrt(q.x * q.x + q.y * q.y + q.z * q.z + q.w * q.w)
            assert magnitude == pytest.approx(1.0, abs=1e-8)
