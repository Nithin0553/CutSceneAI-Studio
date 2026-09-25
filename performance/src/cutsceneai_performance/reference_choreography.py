from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
import math
import re

from ._geometry import Quaternion, Vector3, slerp_quaternion
from .camera import CameraCurveArtifact, CameraCurveSample
from .composition import CanonicalSceneTransform
from .models import BodyGenerationRequest, CameraGenerationRequest
from .motion import (
    CANONICAL_HUMANOID_JOINTS,
    BodyMotionArtifact,
    BodyMotionSample,
)
from .retargeting import invert_quaternion, multiply_quaternions
from .skeleton_repair import estimate_reference_bone_lengths, normalize_actor_skeleton


_EPSILON = 1e-9
_CANONICAL_FORWARD = Vector3(x=0.0, y=0.0, z=-1.0)
_WORLD_UP = Vector3(x=0.0, y=1.0, z=0.0)


def synthesize_reference_body_sequence(
    requests: Sequence[BodyGenerationRequest],
    source_artifacts: Mapping[str, BodyMotionArtifact],
    *,
    scene_transforms: Mapping[str, CanonicalSceneTransform],
    fps: int,
) -> dict[str, BodyMotionArtifact]:
    """Build a deterministic scene-conditioned body performance.

    Locomotion keeps the provider-generated gait texture after fixed-skeleton
    normalization. Stateful cinematic phases are synthesized from the incoming
    pose: stop settles into a planted stance, listen/hold preserve that stance,
    and target turns pivot the same pose toward the bound scene target.
    """

    if fps <= 0:
        raise ValueError("fps must be positive.")
    if not requests:
        raise ValueError("At least one body request is required.")

    request_by_id = {request.semantic_id: request for request in requests}
    missing = sorted(set(request_by_id) - set(source_artifacts))
    if missing:
        raise ValueError(
            "Reference choreography is missing source artifacts: "
            + ", ".join(missing)
        )

    by_actor: dict[str, list[BodyGenerationRequest]] = defaultdict(list)
    for request in requests:
        by_actor[request.actor_binding_id].append(request)

    result: dict[str, BodyMotionArtifact] = {}
    for actor_binding_id, actor_requests in by_actor.items():
        actor_requests.sort(
            key=lambda item: (item.start_frame, item.end_frame, item.semantic_id)
        )
        _validate_actor_windows(actor_requests)

        actor_sources = normalize_actor_skeleton(
            {
                request.semantic_id: source_artifacts[request.semantic_id]
                for request in actor_requests
            }
        )
        if any(
            artifact.fps != fps
            or artifact.frame_count != request.end_frame - request.start_frame
            for request, artifact in (
                (request, actor_sources[request.semantic_id])
                for request in actor_requests
            )
        ):
            raise ValueError(
                "Reference choreography requires source artifacts already normalized "
                "to the generation-plan frame rate and windows."
            )

        neutral_request = next(
            (
                request
                for request in actor_requests
                if _is_locomotion(request)
                and actor_sources[request.semantic_id].samples[0].joint_positions
                is not None
            ),
            actor_requests[0],
        )
        neutral_sample = actor_sources[neutral_request.semantic_id].samples[0]
        if neutral_sample.joint_positions is None:
            raise ValueError(
                "Reference choreography requires canonical joint_positions."
            )
        neutral_offsets = [
            _subtract(position, neutral_sample.root_translation)
            for position in neutral_sample.joint_positions
        ]
        neutral_rotations = [
            rotation.model_copy(deep=True)
            for rotation in neutral_sample.joint_rotations
        ]
        bone_lengths = estimate_reference_bone_lengths(
            list(actor_sources.values())
        )

        actor_samples: dict[int, BodyMotionSample] = {}
        previous: BodyMotionSample | None = None
        previous_previous: BodyMotionSample | None = None

        for request in actor_requests:
            source = actor_sources[request.semantic_id]
            action = _atomic_action_text(request)
            generated: list[BodyMotionSample]

            if _is_locomotion(request):
                generated = _locomotion_samples(source, previous)
            elif previous is not None and _is_stop(action):
                generated = _settle_stop_samples(
                    source,
                    previous,
                    previous_previous,
                    neutral_offsets=neutral_offsets,
                    neutral_rotations=neutral_rotations,
                    bone_lengths=bone_lengths,
                )
            elif (
                previous is not None
                and _is_target_turn(request, action)
            ):
                generated = _target_turn_samples(
                    source,
                    previous,
                    actor_binding_id=actor_binding_id,
                    target_binding_id=request.target_binding_id,
                    scene_transforms=scene_transforms,
                )
            elif previous is not None and _is_stationary(action):
                generated = _hold_samples(source, previous)
            else:
                generated = _fallback_samples(source, previous)

            for offset, sample in enumerate(generated):
                global_frame = request.start_frame + offset
                if global_frame in actor_samples:
                    raise ValueError(
                        f"Overlapping body requests for '{actor_binding_id}' "
                        f"at frame {global_frame}."
                    )
                actor_samples[global_frame] = sample.model_copy(
                    update={"frame_index": global_frame},
                    deep=True,
                )

            previous_previous = (
                actor_samples.get(request.end_frame - 2)
                if request.end_frame - request.start_frame >= 2
                else previous
            )
            previous = actor_samples[request.end_frame - 1]

        for request in actor_requests:
            samples = [
                actor_samples[frame].model_copy(
                    update={"frame_index": frame - request.start_frame},
                    deep=True,
                )
                for frame in range(request.start_frame, request.end_frame)
            ]
            result[request.semantic_id] = BodyMotionArtifact(
                fps=fps,
                frame_count=len(samples),
                samples=samples,
            )

    return result


def synthesize_reference_camera_sequence(
    camera_requests: Sequence[CameraGenerationRequest],
    body_requests: Sequence[BodyGenerationRequest],
    body_artifacts: Mapping[str, BodyMotionArtifact],
    *,
    scene_transforms: Mapping[str, CanonicalSceneTransform],
    fps: int,
) -> dict[str, CameraCurveArtifact]:
    """Stage deterministic world-space cameras from scene bindings and body pose."""

    if fps <= 0:
        raise ValueError("fps must be positive.")
    if not camera_requests:
        raise ValueError("At least one camera request is required.")

    body_by_actor: dict[
        str, list[tuple[BodyGenerationRequest, BodyMotionArtifact]]
    ] = defaultdict(list)
    for request in body_requests:
        try:
            artifact = body_artifacts[request.semantic_id]
        except KeyError as exc:
            raise ValueError(
                f"Missing reference body artifact '{request.semantic_id}'."
            ) from exc
        body_by_actor[request.actor_binding_id].append((request, artifact))
    for tracks in body_by_actor.values():
        tracks.sort(key=lambda item: item[0].start_frame)

    actor_ids = set(body_by_actor)
    if not actor_ids:
        raise ValueError("Reference cameras require at least one body actor.")

    result: dict[str, CameraCurveArtifact] = {}
    for request in camera_requests:
        primary_actor = next(
            (
                binding_id
                for binding_id in [
                    *request.subject_binding_ids,
                    *request.target_binding_ids,
                ]
                if binding_id in actor_ids
            ),
            sorted(actor_ids)[0],
        )
        environment_target = next(
            (
                binding_id
                for binding_id in request.target_binding_ids
                if binding_id not in actor_ids
                and binding_id in scene_transforms
            ),
            None,
        )
        prompt = request.prompt.lower()
        samples: list[CameraCurveSample] = []
        for local_frame in range(request.end_frame - request.start_frame):
            timeline_frame = request.start_frame + local_frame
            pose = _world_actor_pose(
                primary_actor,
                timeline_frame,
                body_by_actor,
                scene_transforms,
            )
            pelvis = pose[_joint_index("pelvis")]
            head = pose[_joint_index("head")]
            spine3 = pose[_joint_index("spine3")]
            neck = pose[_joint_index("neck")]
            chest = _scale(_add(spine3, neck), 0.5)
            forward, right = _pose_axes(pose)

            if (
                "insert" in prompt
                or "environment_detail" in prompt
                or "door detail" in prompt
            ) and environment_target is not None:
                focus = scene_transforms[environment_target].position
                toward_actor = _ground_normalized(
                    _subtract(pelvis, focus),
                    fallback=_scale(forward, -1.0),
                )
                side = _ground_normalized(
                    _cross(_WORLD_UP, toward_actor),
                    fallback=right,
                )
                position = _add(
                    _add(
                        _add(focus, _scale(toward_actor, 1.8)),
                        _scale(_WORLD_UP, 0.35),
                    ),
                    _scale(side, 0.2),
                )
                target = _add(focus, Vector3(x=0.0, y=0.1, z=0.0))
            elif (
                "over_the_shoulder" in prompt
                or "over the shoulder" in prompt
            ) and environment_target is not None:
                position = _add(
                    _add(
                        _add(head, _scale(forward, -0.72)),
                        _scale(right, 0.30),
                    ),
                    _scale(_WORLD_UP, 0.06),
                )
                target = scene_transforms[environment_target].position
            elif (
                "medium_close_up" in prompt
                or "reaction" in prompt
                or "close up" in prompt
            ):
                position = _add(
                    _add(
                        _add(head, _scale(forward, 2.35)),
                        _scale(right, 0.85),
                    ),
                    _scale(_WORLD_UP, 0.10),
                )
                target = _add(head, Vector3(x=0.0, y=-0.05, z=0.0))
            elif "wide" in prompt or "establish" in prompt:
                position = _add(
                    _add(
                        _add(chest, _scale(forward, -5.2)),
                        _scale(right, 2.4),
                    ),
                    _scale(_WORLD_UP, 1.05),
                )
                target = _add(chest, _scale(forward, 1.2))
            else:
                position = _add(
                    _add(
                        _add(chest, _scale(forward, -3.15)),
                        _scale(right, -1.05),
                    ),
                    _scale(_WORLD_UP, 0.55),
                )
                target = chest

            samples.append(
                CameraCurveSample(
                    frame_index=local_frame,
                    position=position,
                    rotation=_look_at_quaternion(position, target),
                    focal_length_mm=request.lens_mm,
                )
            )

        result[request.semantic_id] = CameraCurveArtifact(
            fps=fps,
            frame_count=len(samples),
            samples=samples,
        )
    return result


def _validate_actor_windows(requests: Sequence[BodyGenerationRequest]) -> None:
    previous_end: int | None = None
    for request in requests:
        if previous_end is not None and request.start_frame < previous_end:
            raise ValueError(
                f"Overlapping body request '{request.semantic_id}'."
            )
        previous_end = request.end_frame


def _locomotion_samples(
    source: BodyMotionArtifact,
    previous: BodyMotionSample | None,
) -> list[BodyMotionSample]:
    if previous is None:
        return [sample.model_copy(deep=True) for sample in source.samples]
    offset = _subtract(
        previous.root_translation,
        source.samples[0].root_translation,
    )
    result = []
    for sample in source.samples:
        positions = (
            [_add(position, offset) for position in sample.joint_positions]
            if sample.joint_positions is not None
            else None
        )
        result.append(
            sample.model_copy(
                update={
                    "root_translation": _add(sample.root_translation, offset),
                    "joint_positions": positions,
                },
                deep=True,
            )
        )
    return result


def _settle_stop_samples(
    source: BodyMotionArtifact,
    previous: BodyMotionSample,
    previous_previous: BodyMotionSample | None,
    *,
    neutral_offsets: Sequence[Vector3],
    neutral_rotations: Sequence[Quaternion],
    bone_lengths: Sequence[float],
) -> list[BodyMotionSample]:
    if previous.joint_positions is None:
        raise ValueError("Reference stop requires canonical joint_positions.")

    previous_local = [
        _subtract(position, previous.root_translation)
        for position in previous.joint_positions
    ]
    velocity = (
        _subtract(previous.root_translation, previous_previous.root_translation)
        if previous_previous is not None
        else Vector3(x=0.0, y=0.0, z=0.0)
    )
    velocity = Vector3(x=velocity.x, y=0.0, z=velocity.z)

    root = previous.root_translation.model_copy(deep=True)
    samples: list[BodyMotionSample] = []
    count = source.frame_count
    for index in range(count):
        t = (index + 1) / max(1, count)
        alpha = _smoothstep(t)
        decay = (1.0 - t) ** 1.7
        root = _add(root, _scale(velocity, decay))
        root = Vector3(
            x=root.x,
            y=previous.root_translation.y * (1.0 - alpha),
            z=root.z,
        )
        candidate = [
            _add(
                root,
                _lerp(previous_relative, neutral_relative, alpha),
            )
            for previous_relative, neutral_relative in zip(
                previous_local,
                neutral_offsets,
                strict=True,
            )
        ]
        positions = _project_positions(candidate, bone_lengths, source.parent_indices)
        rotations = [
            slerp_quaternion(old, neutral, alpha)
            for old, neutral in zip(
                previous.joint_rotations,
                neutral_rotations,
                strict=True,
            )
        ]
        samples.append(
            BodyMotionSample(
                frame_index=index,
                root_translation=root,
                joint_rotations=rotations,
                joint_positions=positions,
            )
        )
    return samples


def _target_turn_samples(
    source: BodyMotionArtifact,
    previous: BodyMotionSample,
    *,
    actor_binding_id: str,
    target_binding_id: str | None,
    scene_transforms: Mapping[str, CanonicalSceneTransform],
) -> list[BodyMotionSample]:
    if target_binding_id is None:
        return _hold_samples(source, previous)
    if previous.joint_positions is None:
        raise ValueError("Reference target turn requires canonical joint_positions.")
    try:
        actor_transform = scene_transforms[actor_binding_id]
        target_transform = scene_transforms[target_binding_id]
    except KeyError as exc:
        raise ValueError(
            f"Missing canonical scene transform for target turn: {exc.args[0]}"
        ) from exc

    world_root = _add(
        actor_transform.position,
        _rotate_vector(actor_transform.rotation, previous.root_translation),
    )
    desired_world = Vector3(
        x=target_transform.position.x - world_root.x,
        y=0.0,
        z=target_transform.position.z - world_root.z,
    )
    desired_local = _rotate_vector(
        invert_quaternion(actor_transform.rotation),
        desired_world,
    )
    desired_local = _ground_normalized(
        desired_local,
        fallback=_CANONICAL_FORWARD,
    )
    current_forward, _ = _pose_axes(previous.joint_positions)
    dot = max(
        -1.0,
        min(
            1.0,
            current_forward.x * desired_local.x
            + current_forward.z * desired_local.z,
        ),
    )
    cross_y = (
        current_forward.z * desired_local.x
        - current_forward.x * desired_local.z
    )
    yaw = math.atan2(cross_y, dot)
    if abs(yaw) <= _EPSILON:
        return _hold_samples(source, previous)

    foot_name = "left_foot" if yaw >= 0.0 else "right_foot"
    pivot = previous.joint_positions[_joint_index(foot_name)]
    count = source.frame_count
    samples: list[BodyMotionSample] = []
    for index in range(count):
        t = index / max(1, count - 1)
        angle = yaw * _smoothstep(t)
        correction = _yaw_quaternion(angle)
        root = _add(
            pivot,
            _rotate_y(_subtract(previous.root_translation, pivot), angle),
        )
        positions = [
            _add(
                pivot,
                _rotate_y(_subtract(position, pivot), angle),
            )
            for position in previous.joint_positions
        ]
        rotations = [
            rotation.model_copy(deep=True)
            for rotation in previous.joint_rotations
        ]
        rotations[0] = multiply_quaternions(
            correction,
            previous.joint_rotations[0],
        )
        samples.append(
            BodyMotionSample(
                frame_index=index,
                root_translation=root,
                joint_rotations=rotations,
                joint_positions=positions,
            )
        )
    return samples


def _hold_samples(
    source: BodyMotionArtifact,
    previous: BodyMotionSample,
) -> list[BodyMotionSample]:
    return [
        previous.model_copy(update={"frame_index": index}, deep=True)
        for index in range(source.frame_count)
    ]


def _fallback_samples(
    source: BodyMotionArtifact,
    previous: BodyMotionSample | None,
) -> list[BodyMotionSample]:
    return _locomotion_samples(source, previous)


def _world_actor_pose(
    actor_binding_id: str,
    timeline_frame: int,
    body_by_actor: Mapping[
        str, Sequence[tuple[BodyGenerationRequest, BodyMotionArtifact]]
    ],
    scene_transforms: Mapping[str, CanonicalSceneTransform],
) -> list[Vector3]:
    try:
        tracks = body_by_actor[actor_binding_id]
        actor_transform = scene_transforms[actor_binding_id]
    except KeyError as exc:
        raise ValueError(
            f"Missing actor data for reference camera: {exc.args[0]}"
        ) from exc

    request, artifact = min(
        tracks,
        key=lambda item: _frame_distance(timeline_frame, item[0]),
    )
    local_index = min(
        max(timeline_frame - request.start_frame, 0),
        artifact.frame_count - 1,
    )
    sample = artifact.samples[local_index]
    if sample.joint_positions is None:
        raise ValueError("Reference cameras require canonical joint_positions.")
    world_positions = [
        _add(
            actor_transform.position,
            _rotate_vector(actor_transform.rotation, position),
        )
        for position in sample.joint_positions
    ]
    ground_y = min(
        world_positions[_joint_index("left_foot")].y,
        world_positions[_joint_index("right_foot")].y,
    )
    lift = actor_transform.position.y - ground_y
    if abs(lift) <= _EPSILON:
        return world_positions
    return [
        _add(position, Vector3(x=0.0, y=lift, z=0.0))
        for position in world_positions
    ]


def _frame_distance(frame: int, request: BodyGenerationRequest) -> int:
    if request.start_frame <= frame < request.end_frame:
        return 0
    if frame < request.start_frame:
        return request.start_frame - frame
    return frame - (request.end_frame - 1)


def _pose_axes(positions: Sequence[Vector3]) -> tuple[Vector3, Vector3]:
    pelvis = positions[_joint_index("pelvis")]
    left_hip = positions[_joint_index("left_hip")]
    right_hip = positions[_joint_index("right_hip")]
    spine = positions[_joint_index("spine1")]

    right = _normalized(
        _subtract(right_hip, left_hip),
        fallback=Vector3(x=1.0, y=0.0, z=0.0),
    )
    up_seed = _normalized(
        _subtract(spine, pelvis),
        fallback=_WORLD_UP,
    )
    up = _subtract(up_seed, _scale(right, _dot(up_seed, right)))
    up = _normalized(up, fallback=_WORLD_UP)
    forward = _normalized(
        _cross(up, right),
        fallback=_CANONICAL_FORWARD,
    )
    forward = _ground_normalized(forward, fallback=_CANONICAL_FORWARD)
    right = _ground_normalized(
        _cross(forward, _WORLD_UP),
        fallback=right,
    )
    return forward, right


def _look_at_quaternion(origin: Vector3, target: Vector3) -> Quaternion:
    forward = _normalized(
        _subtract(target, origin),
        fallback=_CANONICAL_FORWARD,
    )
    right = _normalized(
        _cross(forward, _WORLD_UP),
        fallback=Vector3(x=1.0, y=0.0, z=0.0),
    )
    up = _normalized(
        _cross(right, forward),
        fallback=_WORLD_UP,
    )
    z_axis = _scale(forward, -1.0)
    return _quaternion_from_basis(right, up, z_axis)


def _quaternion_from_basis(
    x_axis: Vector3,
    y_axis: Vector3,
    z_axis: Vector3,
) -> Quaternion:
    m00, m10, m20 = x_axis.x, x_axis.y, x_axis.z
    m01, m11, m21 = y_axis.x, y_axis.y, y_axis.z
    m02, m12, m22 = z_axis.x, z_axis.y, z_axis.z
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
    length = math.sqrt(sum(component * component for component in value))
    if length <= _EPSILON:
        return Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
    return Quaternion(
        x=value[0] / length,
        y=value[1] / length,
        z=value[2] / length,
        w=value[3] / length,
    )


def _project_positions(
    source: Sequence[Vector3],
    bone_lengths: Sequence[float],
    parents: Sequence[int],
) -> list[Vector3]:
    repaired: list[Vector3] = [position.model_copy(deep=True) for position in source]
    for joint_index, parent_index in enumerate(parents):
        if parent_index < 0:
            repaired[joint_index] = source[joint_index].model_copy(deep=True)
            continue
        direction = _subtract(source[joint_index], source[parent_index])
        fallback = Vector3(x=0.0, y=-1.0, z=0.0)
        direction = _normalized(direction, fallback=fallback)
        repaired[joint_index] = _add(
            repaired[parent_index],
            _scale(direction, float(bone_lengths[joint_index])),
        )
    return repaired


def _atomic_action_text(request: BodyGenerationRequest) -> str:
    match = re.search(
        r"Action:\s*(.+?)\s+Style:",
        request.prompt,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return (match.group(1) if match is not None else request.prompt).lower()


def _is_locomotion(request: BodyGenerationRequest) -> bool:
    text = _atomic_action_text(request)
    if any(token in text for token in ("stop", "halt", "listen", "hold", "stand")):
        return False
    return any(
        token in text
        for token in ("walk", "run", "jog", "advance", "approach", "proceed")
    )


def _is_stop(action: str) -> bool:
    return any(token in action for token in ("stop", "halt", "decelerate"))


def _is_target_turn(request: BodyGenerationRequest, action: str) -> bool:
    return request.target_binding_id is not None and any(
        token in action for token in ("turn", "pivot", "rotate")
    )


def _is_stationary(action: str) -> bool:
    return any(
        token in action
        for token in ("listen", "hold", "remain", "stand still", "wait")
    )


def _joint_index(name: str) -> int:
    return CANONICAL_HUMANOID_JOINTS.index(name)


def _smoothstep(value: float) -> float:
    t = max(0.0, min(1.0, value))
    return t * t * (3.0 - 2.0 * t)


def _yaw_quaternion(angle: float) -> Quaternion:
    half = angle / 2.0
    return Quaternion(
        x=0.0,
        y=math.sin(half),
        z=0.0,
        w=math.cos(half),
    )


def _rotate_y(value: Vector3, angle: float) -> Vector3:
    cosine = math.cos(angle)
    sine = math.sin(angle)
    return Vector3(
        x=cosine * value.x + sine * value.z,
        y=value.y,
        z=-sine * value.x + cosine * value.z,
    )


def _rotate_vector(rotation: Quaternion, value: Vector3) -> Vector3:
    ux, uy, uz = rotation.x, rotation.y, rotation.z
    vx, vy, vz = value.x, value.y, value.z
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


def _ground_normalized(value: Vector3, *, fallback: Vector3) -> Vector3:
    return _normalized(
        Vector3(x=value.x, y=0.0, z=value.z),
        fallback=fallback,
    )


def _normalized(value: Vector3, *, fallback: Vector3) -> Vector3:
    length = math.sqrt(value.x * value.x + value.y * value.y + value.z * value.z)
    if length <= _EPSILON:
        return fallback.model_copy(deep=True)
    return Vector3(x=value.x / length, y=value.y / length, z=value.z / length)


def _dot(first: Vector3, second: Vector3) -> float:
    return first.x * second.x + first.y * second.y + first.z * second.z


def _cross(first: Vector3, second: Vector3) -> Vector3:
    return Vector3(
        x=first.y * second.z - first.z * second.y,
        y=first.z * second.x - first.x * second.z,
        z=first.x * second.y - first.y * second.x,
    )


def _add(first: Vector3, second: Vector3) -> Vector3:
    return Vector3(
        x=first.x + second.x,
        y=first.y + second.y,
        z=first.z + second.z,
    )


def _subtract(first: Vector3, second: Vector3) -> Vector3:
    return Vector3(
        x=first.x - second.x,
        y=first.y - second.y,
        z=first.z - second.z,
    )


def _scale(value: Vector3, scalar: float) -> Vector3:
    return Vector3(
        x=value.x * scalar,
        y=value.y * scalar,
        z=value.z * scalar,
    )


def _lerp(first: Vector3, second: Vector3, alpha: float) -> Vector3:
    return Vector3(
        x=first.x + (second.x - first.x) * alpha,
        y=first.y + (second.y - first.y) * alpha,
        z=first.z + (second.z - first.z) * alpha,
    )
