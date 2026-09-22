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

        for request in actor_requests:
            normalized = artifacts[request.semantic_id]
            motion = normalized.artifact.model_copy(deep=True)

            if previous_end is not None:
                motion = _rebase_root(motion, previous_end.root_translation)
                motion = _blend_entry_pose(
                    motion,
                    previous_end,
                    blend_frames=blend_frames,
                )

            if _is_target_facing_turn(request) and scene_transforms is not None:
                motion = _constrain_turn_to_target(
                    motion,
                    actor_binding_id=actor_binding_id,
                    target_binding_id=request.target_binding_id,
                    scene_transforms=scene_transforms,
                )

            if _is_target_facing_hold(request):
                motion = _lock_stationary_root_and_heading(motion)

            composed[request.semantic_id] = NormalizedArtifact(
                request_semantic_id=normalized.request_semantic_id,
                artifact=motion,
                provenance=normalized.provenance,
            )
            previous_end = motion.samples[-1]

    return composed


def _rebase_root(motion: BodyMotionArtifact, anchor: Vector3) -> BodyMotionArtifact:
    first = motion.samples[0].root_translation
    dx = anchor.x - first.x
    dy = anchor.y - first.y
    dz = anchor.z - first.z

    samples = [
        sample.model_copy(
            update={
                "root_translation": Vector3(
                    x=sample.root_translation.x + dx,
                    y=sample.root_translation.y + dy,
                    z=sample.root_translation.z + dz,
                )
            },
            deep=True,
        )
        for sample in motion.samples
    ]
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

        if index == 0:
            rotations = [
                rotation.model_copy(deep=True)
                for rotation in previous_end.joint_rotations
            ]
        else:
            alpha = 1.0 if count == 1 else index / (count - 1)
            rotations = [
                slerp_quaternion(previous, current, alpha)
                for previous, current in zip(
                    previous_end.joint_rotations,
                    sample.joint_rotations,
                    strict=True,
                )
            ]
        samples.append(
            sample.model_copy(
                update={"joint_rotations": rotations},
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


def _is_target_facing_turn(request: BodyGenerationRequest) -> bool:
    if request.target_binding_id is None:
        return False
    text = _atomic_action_text(request)
    return any(token in text for token in ("turn", "pivot", "rotate"))


def _is_target_facing_hold(request: BodyGenerationRequest) -> bool:
    if request.target_binding_id is None:
        return False
    text = _atomic_action_text(request)
    return (
        any(token in text for token in ("hold", "remain", "stand"))
        and any(token in text for token in ("facing", "toward", "still", "stance"))
    )


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
        samples.append(
            sample.model_copy(
                update={"joint_rotations": rotations},
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
        rotations[0] = Quaternion(
            x=anchor_pelvis.x,
            y=anchor_pelvis.y,
            z=anchor_pelvis.z,
            w=anchor_pelvis.w,
        )
        samples.append(
            sample.model_copy(
                update={
                    "root_translation": anchor_root.model_copy(deep=True),
                    "joint_rotations": rotations,
                },
                deep=True,
            )
        )

    return motion.model_copy(update={"samples": samples}, deep=True)


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
