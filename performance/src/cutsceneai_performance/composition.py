from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
import re

from ._geometry import Quaternion, Vector3, slerp_quaternion
from .models import BodyGenerationRequest
from .motion import BodyMotionArtifact, BodyMotionSample
from .providers import NormalizedArtifact
from .retargeting import invert_quaternion, multiply_quaternions

BODY_ENTRY_BLEND_FRAMES = 6
_CANONICAL_FORWARD = Vector3(x=0.0, y=0.0, z=-1.0)
_IDENTITY = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
_EPSILON = 1e-9


@dataclass(frozen=True, slots=True)
class CanonicalSceneTransform:
    position: Vector3
    rotation: Quaternion


def compose_body_sequence(
    requests: Sequence[BodyGenerationRequest],
    artifacts: Mapping[str, NormalizedArtifact[BodyMotionArtifact]],
    *,
    blend_frames: int = BODY_ENTRY_BLEND_FRAMES,
    scene_transforms: Mapping[str, CanonicalSceneTransform] | None = None,
) -> dict[str, NormalizedArtifact[BodyMotionArtifact]]:
    """Compose independently generated phases into actor-continuous canonical motion.

    Provider clips may begin in independent local root frames. This pass rebases those
    clips into one continuous actor trajectory, blends phase-entry poses, constrains
    target-facing turn phases toward canonical scene targets when transforms are
    available, and locks target-facing holds so model drift cannot move or rotate the
    actor while it is meant to remain still.
    """

    if blend_frames < 0:
        raise ValueError("blend_frames must be non-negative.")

    missing = [
        request.semantic_id
        for request in requests
        if request.semantic_id not in artifacts
    ]
    if missing:
        raise ValueError("Missing normalized body artifacts: " + ", ".join(missing))

    by_actor: dict[str, list[BodyGenerationRequest]] = defaultdict(list)
    for request in requests:
        by_actor[request.actor_binding_id].append(request)

    composed: dict[str, NormalizedArtifact[BodyMotionArtifact]] = {}
    for actor_binding_id, actor_requests in by_actor.items():
        actor_requests.sort(
            key=lambda item: (item.start_frame, item.end_frame, item.semantic_id)
        )
        previous_end: BodyMotionSample | None = None
        previous_root_velocity: Vector3 | None = None

        for request in actor_requests:
            normalized = artifacts[request.semantic_id]
            motion = normalized.artifact.model_copy(deep=True)

            synthesized_hold = False
            synthesized_turn = False
            if previous_end is not None and _is_stationary_hold(request):
                # Stateful holds/listens are constraints on the incoming performance
                # state, not independent motions. Reusing the planted incoming pose
                # prevents a text-to-motion provider from inventing a crouch, stand-up,
                # or unrelated gesture during a phase whose semantic job is stillness.
                motion = _hold_previous_pose(motion, previous_end)
                synthesized_hold = True
            elif (
                previous_end is not None
                and _is_target_facing_turn(request)
                and scene_transforms is not None
            ):
                # A target turn is likewise conditioned on the pose that precedes it.
                # Pivot the incoming stance toward the bound target instead of asking an
                # independently generated clip to supply both transition context and
                # scene-relative orientation.
                motion = _pivot_turn_from_previous_pose(
                    motion,
                    previous_end,
                    actor_binding_id=actor_binding_id,
                    target_binding_id=request.target_binding_id,
                    scene_transforms=scene_transforms,
                )
                synthesized_turn = True
            elif previous_end is not None:
                motion = _rebase_root(motion, previous_end.root_translation)
                motion = _stitch_entry_trajectory(
                    motion,
                    previous_end,
                    previous_root_velocity,
                    blend_frames=blend_frames,
                )
                motion = _blend_entry_pose(
                    motion,
                    previous_end,
                    blend_frames=blend_frames,
                )

            if _is_locomotion(request) and scene_transforms is not None:
                motion = _align_locomotion_root(
                    motion,
                    actor_binding_id=actor_binding_id,
                    target_binding_id=request.target_binding_id,
                    scene_transforms=scene_transforms,
                )

            if (
                not synthesized_turn
                and _is_target_facing_turn(request)
                and scene_transforms is not None
            ):
                motion = _constrain_turn_to_target(
                    motion,
                    actor_binding_id=actor_binding_id,
                    target_binding_id=request.target_binding_id,
                    scene_transforms=scene_transforms,
                )

            if not synthesized_hold and _is_target_facing_hold(request):
                motion = _lock_stationary_root_and_heading(motion)

            composed[request.semantic_id] = NormalizedArtifact(
                request_semantic_id=normalized.request_semantic_id,
                artifact=motion,
                provenance=normalized.provenance,
            )
            previous_end = motion.samples[-1]
            previous_root_velocity = _ending_root_velocity(motion)

    return composed


def _rebase_root(motion: BodyMotionArtifact, anchor: Vector3) -> BodyMotionArtifact:
    first = motion.samples[0].root_translation
    offset = Vector3(
        x=anchor.x - first.x,
        y=anchor.y - first.y,
        z=anchor.z - first.z,
    )

    samples = []
    for sample in motion.samples:
        root_translation = _add_vector(sample.root_translation, offset)
        joint_positions = (
            [
                _add_vector(position, offset)
                for position in sample.joint_positions
            ]
            if sample.joint_positions is not None
            else None
        )
        samples.append(
            sample.model_copy(
                update={
                    "root_translation": root_translation,
                    "joint_positions": joint_positions,
                },
                deep=True,
            )
        )
    return motion.model_copy(update={"samples": samples}, deep=True)


def _ending_root_velocity(motion: BodyMotionArtifact) -> Vector3 | None:
    if motion.frame_count < 2:
        return None
    return _scale_vector(
        _subtract_vector(
            motion.samples[-1].root_translation,
            motion.samples[-2].root_translation,
        ),
        float(motion.fps),
    )


def _stitch_entry_trajectory(
    motion: BodyMotionArtifact,
    previous_end: BodyMotionSample,
    previous_velocity: Vector3 | None,
    *,
    blend_frames: int,
) -> BodyMotionArtifact:
    """Blend sampled root velocity across a phase boundary and integrate forward."""

    count = min(blend_frames, motion.frame_count)
    if count <= 0 or previous_velocity is None:
        return motion

    previous_step = _scale_vector(previous_velocity, 1.0 / float(motion.fps))
    previous_position = previous_end.root_translation
    transition_samples: list[BodyMotionSample] = []

    for index in range(count):
        sample = motion.samples[index]
        if motion.frame_count > 1:
            if index == 0:
                source_step = _subtract_vector(
                    motion.samples[1].root_translation,
                    motion.samples[0].root_translation,
                )
            else:
                source_step = _subtract_vector(
                    motion.samples[index].root_translation,
                    motion.samples[index - 1].root_translation,
                )
        else:
            source_step = previous_step

        alpha = (index + 1) / count
        blended_step = _lerp_vector(previous_step, source_step, alpha)
        root_translation = _add_vector(previous_position, blended_step)
        root_edit = _subtract_vector(root_translation, sample.root_translation)
        joint_positions = (
            [
                _add_vector(position, root_edit)
                for position in sample.joint_positions
            ]
            if sample.joint_positions is not None
            else None
        )
        transition_samples.append(
            sample.model_copy(
                update={
                    "root_translation": root_translation,
                    "joint_positions": joint_positions,
                },
                deep=True,
            )
        )
        previous_position = root_translation

    tail_offset = _subtract_vector(
        transition_samples[-1].root_translation,
        motion.samples[count - 1].root_translation,
    )
    samples = list(transition_samples)
    for sample in motion.samples[count:]:
        root_translation = _add_vector(sample.root_translation, tail_offset)
        joint_positions = (
            [
                _add_vector(position, tail_offset)
                for position in sample.joint_positions
            ]
            if sample.joint_positions is not None
            else None
        )
        samples.append(
            sample.model_copy(
                update={
                    "root_translation": root_translation,
                    "joint_positions": joint_positions,
                },
                deep=True,
            )
        )

    return motion.model_copy(update={"samples": samples}, deep=True)


def _blend_entry_pose(
    motion: BodyMotionArtifact,
    previous_end: BodyMotionSample,
    *,
    blend_frames: int,
) -> BodyMotionArtifact:
    count = min(blend_frames, motion.frame_count)
    if count <= 0:
        return motion

    samples: list[BodyMotionSample] = []
    for index, sample in enumerate(motion.samples):
        if index >= count:
            samples.append(sample.model_copy(deep=True))
            continue

        alpha = (index + 1) / count
        rotations = [
            slerp_quaternion(previous, current, alpha)
            for previous, current in zip(
                previous_end.joint_rotations,
                sample.joint_rotations,
                strict=True,
            )
        ]

        joint_positions = sample.joint_positions
        if (
            previous_end.joint_positions is not None
            and sample.joint_positions is not None
        ):
            joint_positions = []
            for previous_position, current_position in zip(
                previous_end.joint_positions,
                sample.joint_positions,
                strict=True,
            ):
                previous_relative = _subtract_vector(
                    previous_position,
                    previous_end.root_translation,
                )
                current_relative = _subtract_vector(
                    current_position,
                    sample.root_translation,
                )
                blended_relative = _lerp_vector(
                    previous_relative,
                    current_relative,
                    alpha,
                )
                joint_positions.append(
                    _add_vector(sample.root_translation, blended_relative)
                )

        samples.append(
            sample.model_copy(
                update={
                    "joint_rotations": rotations,
                    "joint_positions": joint_positions,
                },
                deep=True,
            )
        )

    return motion.model_copy(update={"samples": samples}, deep=True)


def _atomic_action_text(request: BodyGenerationRequest) -> str:
    match = re.search(
        r"Action:\s*(.+?)\s+Style:",
        request.prompt,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return (match.group(1) if match is not None else request.prompt).lower()


def _is_locomotion(request: BodyGenerationRequest) -> bool:
    text = _atomic_action_text(request)
    if any(token in text for token in ("stop", "halt", "stand", "hold", "listen")):
        return False
    return any(
        token in text
        for token in ("walk", "run", "jog", "advance", "approach", "proceed")
    )


def _align_locomotion_root(
    motion: BodyMotionArtifact,
    *,
    actor_binding_id: str,
    target_binding_id: str | None,
    scene_transforms: Mapping[str, CanonicalSceneTransform],
) -> BodyMotionArtifact:
    """Rotate provider root travel onto the scene-intended locomotion heading.

    The body pose remains unchanged relative to its root. When source XYZ geometry is
    present, each sample receives the same root-translation edit so root_translation
    and joint_positions remain one coherent canonical pose.
    """

    first = motion.samples[0].root_translation
    final = motion.samples[-1].root_translation
    displacement = Vector3(
        x=final.x - first.x,
        y=0.0,
        z=final.z - first.z,
    )
    distance = math.hypot(displacement.x, displacement.z)
    if distance <= _EPSILON:
        return motion

    current = _normalize_ground_direction(
        displacement,
        label=f"locomotion displacement '{actor_binding_id}'",
    )
    desired = _CANONICAL_FORWARD

    if target_binding_id is not None:
        try:
            actor_transform = scene_transforms[actor_binding_id]
        except KeyError as exc:
            raise ValueError(
                f"Missing canonical scene transform for actor '{actor_binding_id}'."
            ) from exc
        try:
            target_transform = scene_transforms[target_binding_id]
        except KeyError as exc:
            raise ValueError(
                f"Missing canonical scene transform for target '{target_binding_id}'."
            ) from exc

        entry_world_offset = _rotate_vector(actor_transform.rotation, first)
        entry_world = Vector3(
            x=actor_transform.position.x + entry_world_offset.x,
            y=actor_transform.position.y + entry_world_offset.y,
            z=actor_transform.position.z + entry_world_offset.z,
        )
        world_target_direction = Vector3(
            x=target_transform.position.x - entry_world.x,
            y=0.0,
            z=target_transform.position.z - entry_world.z,
        )
        desired = _rotate_vector(
            invert_quaternion(actor_transform.rotation),
            world_target_direction,
        )
        desired = _normalize_ground_direction(
            Vector3(x=desired.x, y=0.0, z=desired.z),
            label=f"locomotion target direction '{target_binding_id}'",
        )

    dot = max(-1.0, min(1.0, current.x * desired.x + current.z * desired.z))
    cross_y = current.z * desired.x - current.x * desired.z
    yaw = math.atan2(cross_y, dot)
    if abs(yaw) <= _EPSILON:
        return motion

    half = yaw / 2.0
    correction = Quaternion(
        x=0.0,
        y=math.sin(half),
        z=0.0,
        w=math.cos(half),
    )

    samples: list[BodyMotionSample] = []
    for sample in motion.samples:
        delta = Vector3(
            x=sample.root_translation.x - first.x,
            y=0.0,
            z=sample.root_translation.z - first.z,
        )
        rotated = _rotate_vector(correction, delta)
        root_translation = Vector3(
            x=first.x + rotated.x,
            y=sample.root_translation.y,
            z=first.z + rotated.z,
        )
        root_edit = _subtract_vector(root_translation, sample.root_translation)
        joint_positions = (
            [
                _add_vector(position, root_edit)
                for position in sample.joint_positions
            ]
            if sample.joint_positions is not None
            else None
        )
        samples.append(
            sample.model_copy(
                update={
                    "root_translation": root_translation,
                    "joint_positions": joint_positions,
                },
                deep=True,
            )
        )

    return motion.model_copy(update={"samples": samples}, deep=True)


def _is_target_facing_turn(request: BodyGenerationRequest) -> bool:
    if request.target_binding_id is None:
        return False
    text = _atomic_action_text(request)
    return any(token in text for token in ("turn", "pivot", "rotate"))


def _is_stationary_hold(request: BodyGenerationRequest) -> bool:
    text = _atomic_action_text(request)
    if any(
        token in text
        for token in ("walk", "run", "jog", "advance", "approach", "proceed", "turn", "pivot", "rotate")
    ):
        return False
    return (
        ("hold" in text and any(token in text for token in ("pose", "stance", "still", "position", "listen")))
        or ("remain" in text and any(token in text for token in ("still", "facing", "stance", "position")))
        or ("listen" in text and any(token in text for token in ("hold", "still", "pose", "guarded")))
    )


def _is_target_facing_hold(request: BodyGenerationRequest) -> bool:
    if request.target_binding_id is None:
        return False
    text = _atomic_action_text(request)
    return (
        any(token in text for token in ("hold", "remain", "stand"))
        and any(token in text for token in ("facing", "toward", "still", "stance"))
    )


def _hold_previous_pose(
    motion: BodyMotionArtifact,
    previous_end: BodyMotionSample,
) -> BodyMotionArtifact:
    samples = [
        previous_end.model_copy(
            update={"frame_index": sample.frame_index},
            deep=True,
        )
        for sample in motion.samples
    ]
    return motion.model_copy(update={"samples": samples}, deep=True)


def _pivot_turn_from_previous_pose(
    motion: BodyMotionArtifact,
    previous_end: BodyMotionSample,
    *,
    actor_binding_id: str,
    target_binding_id: str | None,
    scene_transforms: Mapping[str, CanonicalSceneTransform],
) -> BodyMotionArtifact:
    if target_binding_id is None:
        return motion
    try:
        actor_transform = scene_transforms[actor_binding_id]
    except KeyError as exc:
        raise ValueError(
            f"Missing canonical scene transform for actor '{actor_binding_id}'."
        ) from exc
    try:
        target_transform = scene_transforms[target_binding_id]
    except KeyError as exc:
        raise ValueError(
            f"Missing canonical scene transform for target '{target_binding_id}'."
        ) from exc

    world_root_offset = _rotate_vector(
        actor_transform.rotation,
        previous_end.root_translation,
    )
    world_root = Vector3(
        x=actor_transform.position.x + world_root_offset.x,
        y=actor_transform.position.y + world_root_offset.y,
        z=actor_transform.position.z + world_root_offset.z,
    )
    desired = _normalize_ground_direction(
        Vector3(
            x=target_transform.position.x - world_root.x,
            y=0.0,
            z=target_transform.position.z - world_root.z,
        ),
        label=f"target direction '{target_binding_id}'",
    )

    previous_world_pelvis = multiply_quaternions(
        actor_transform.rotation,
        previous_end.joint_rotations[0],
    )
    current = _rotate_vector(previous_world_pelvis, _CANONICAL_FORWARD)
    current = _normalize_ground_direction(
        Vector3(x=current.x, y=0.0, z=current.z),
        label=f"actor heading '{actor_binding_id}'",
    )

    dot = max(-1.0, min(1.0, current.x * desired.x + current.z * desired.z))
    cross_y = current.z * desired.x - current.x * desired.z
    yaw = math.atan2(cross_y, dot)
    if abs(yaw) <= _EPSILON:
        return _hold_previous_pose(motion, previous_end)

    half = yaw / 2.0
    world_correction = Quaternion(
        x=0.0,
        y=math.sin(half),
        z=0.0,
        w=math.cos(half),
    )
    local_correction = multiply_quaternions(
        multiply_quaternions(
            invert_quaternion(actor_transform.rotation),
            world_correction,
        ),
        actor_transform.rotation,
    )

    pivot = previous_end.root_translation
    if previous_end.joint_positions is not None:
        preferred_foot = "left_foot" if yaw >= 0.0 else "right_foot"
        try:
            pivot_index = motion.joint_names.index(preferred_foot)
        except ValueError:
            pivot_index = -1
        if pivot_index >= 0:
            pivot = previous_end.joint_positions[pivot_index]

    samples: list[BodyMotionSample] = []
    denominator = max(1, motion.frame_count - 1)
    for index, source_sample in enumerate(motion.samples):
        t = index / denominator
        alpha = t * t * (3.0 - 2.0 * t)
        correction = slerp_quaternion(_IDENTITY, local_correction, alpha)
        root_translation = _add_vector(
            pivot,
            _rotate_vector(
                correction,
                _subtract_vector(previous_end.root_translation, pivot),
            ),
        )
        rotations = [
            rotation.model_copy(deep=True)
            for rotation in previous_end.joint_rotations
        ]
        rotations[0] = multiply_quaternions(
            correction,
            previous_end.joint_rotations[0],
        )
        joint_positions = (
            [
                _add_vector(
                    pivot,
                    _rotate_vector(
                        correction,
                        _subtract_vector(position, pivot),
                    ),
                )
                for position in previous_end.joint_positions
            ]
            if previous_end.joint_positions is not None
            else None
        )
        samples.append(
            previous_end.model_copy(
                update={
                    "frame_index": source_sample.frame_index,
                    "root_translation": root_translation,
                    "joint_rotations": rotations,
                    "joint_positions": joint_positions,
                },
                deep=True,
            )
        )

    return motion.model_copy(update={"samples": samples}, deep=True)


def _constrain_turn_to_target(
    motion: BodyMotionArtifact,
    *,
    actor_binding_id: str,
    target_binding_id: str | None,
    scene_transforms: Mapping[str, CanonicalSceneTransform],
) -> BodyMotionArtifact:
    if target_binding_id is None:
        return motion
    try:
        actor_transform = scene_transforms[actor_binding_id]
    except KeyError as exc:
        raise ValueError(
            f"Missing canonical scene transform for actor '{actor_binding_id}'."
        ) from exc
    try:
        target_transform = scene_transforms[target_binding_id]
    except KeyError as exc:
        raise ValueError(
            f"Missing canonical scene transform for target '{target_binding_id}'."
        ) from exc

    final = motion.samples[-1]
    world_root_offset = _rotate_vector(
        actor_transform.rotation,
        final.root_translation,
    )
    world_root = Vector3(
        x=actor_transform.position.x + world_root_offset.x,
        y=actor_transform.position.y + world_root_offset.y,
        z=actor_transform.position.z + world_root_offset.z,
    )
    desired = Vector3(
        x=target_transform.position.x - world_root.x,
        y=0.0,
        z=target_transform.position.z - world_root.z,
    )
    desired = _normalize_ground_direction(
        desired,
        label=f"target direction '{target_binding_id}'",
    )

    final_world_pelvis = multiply_quaternions(
        actor_transform.rotation,
        final.joint_rotations[0],
    )
    current = _rotate_vector(final_world_pelvis, _CANONICAL_FORWARD)
    current = _normalize_ground_direction(
        Vector3(x=current.x, y=0.0, z=current.z),
        label=f"actor heading '{actor_binding_id}'",
    )

    dot = max(-1.0, min(1.0, current.x * desired.x + current.z * desired.z))
    cross_y = current.z * desired.x - current.x * desired.z
    yaw = math.atan2(cross_y, dot)
    if abs(yaw) <= _EPSILON:
        return motion

    half = yaw / 2.0
    world_correction = Quaternion(
        x=0.0,
        y=math.sin(half),
        z=0.0,
        w=math.cos(half),
    )
    local_correction = multiply_quaternions(
        multiply_quaternions(
            invert_quaternion(actor_transform.rotation),
            world_correction,
        ),
        actor_transform.rotation,
    )

    samples: list[BodyMotionSample] = []
    denominator = max(1, motion.frame_count - 1)
    for index, sample in enumerate(motion.samples):
        if index == 0:
            samples.append(sample.model_copy(deep=True))
            continue

        t = index / denominator
        alpha = t * t * (3.0 - 2.0 * t)
        correction = slerp_quaternion(_IDENTITY, local_correction, alpha)
        rotations = [
            rotation.model_copy(deep=True)
            for rotation in sample.joint_rotations
        ]
        rotations[0] = multiply_quaternions(correction, rotations[0])
        joint_positions = (
            [
                _add_vector(
                    sample.root_translation,
                    _rotate_vector(
                        correction,
                        _subtract_vector(position, sample.root_translation),
                    ),
                )
                for position in sample.joint_positions
            ]
            if sample.joint_positions is not None
            else None
        )
        samples.append(
            sample.model_copy(
                update={
                    "joint_rotations": rotations,
                    "joint_positions": joint_positions,
                },
                deep=True,
            )
        )

    return motion.model_copy(update={"samples": samples}, deep=True)


def _lock_stationary_root_and_heading(motion: BodyMotionArtifact) -> BodyMotionArtifact:
    anchor_root = motion.samples[0].root_translation.model_copy(deep=True)
    anchor_pelvis = motion.samples[0].joint_rotations[0].model_copy(deep=True)

    samples: list[BodyMotionSample] = []
    for sample in motion.samples:
        rotations = [
            rotation.model_copy(deep=True)
            for rotation in sample.joint_rotations
        ]
        correction = multiply_quaternions(
            anchor_pelvis,
            invert_quaternion(sample.joint_rotations[0]),
        )
        rotations[0] = Quaternion(
            x=anchor_pelvis.x,
            y=anchor_pelvis.y,
            z=anchor_pelvis.z,
            w=anchor_pelvis.w,
        )
        joint_positions = (
            [
                _add_vector(
                    anchor_root,
                    _rotate_vector(
                        correction,
                        _subtract_vector(position, sample.root_translation),
                    ),
                )
                for position in sample.joint_positions
            ]
            if sample.joint_positions is not None
            else None
        )
        samples.append(
            sample.model_copy(
                update={
                    "root_translation": anchor_root.model_copy(deep=True),
                    "joint_rotations": rotations,
                    "joint_positions": joint_positions,
                },
                deep=True,
            )
        )

    return motion.model_copy(update={"samples": samples}, deep=True)


def _scale_vector(value: Vector3, amount: float) -> Vector3:
    return Vector3(
        x=value.x * amount,
        y=value.y * amount,
        z=value.z * amount,
    )


def _add_vector(first: Vector3, second: Vector3) -> Vector3:
    return Vector3(
        x=first.x + second.x,
        y=first.y + second.y,
        z=first.z + second.z,
    )


def _subtract_vector(first: Vector3, second: Vector3) -> Vector3:
    return Vector3(
        x=first.x - second.x,
        y=first.y - second.y,
        z=first.z - second.z,
    )


def _lerp_vector(first: Vector3, second: Vector3, alpha: float) -> Vector3:
    return Vector3(
        x=first.x + (second.x - first.x) * alpha,
        y=first.y + (second.y - first.y) * alpha,
        z=first.z + (second.z - first.z) * alpha,
    )


def _rotate_vector(rotation: Quaternion, vector: Vector3) -> Vector3:
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


def _normalize_ground_direction(value: Vector3, *, label: str) -> Vector3:
    length = math.hypot(value.x, value.z)
    if length <= _EPSILON:
        raise ValueError(f"{label} is undefined on the ground plane.")
    return Vector3(x=value.x / length, y=0.0, z=value.z / length)
