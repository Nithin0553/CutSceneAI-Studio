from __future__ import annotations

from collections import defaultdict
import re
from collections.abc import Mapping, Sequence

from ._geometry import Quaternion, Vector3, slerp_quaternion
from .models import BodyGenerationRequest
from .motion import BodyMotionArtifact, BodyMotionSample
from .providers import NormalizedArtifact

BODY_ENTRY_BLEND_FRAMES = 6


def compose_body_sequence(
    requests: Sequence[BodyGenerationRequest],
    artifacts: Mapping[str, NormalizedArtifact[BodyMotionArtifact]],
    *,
    blend_frames: int = BODY_ENTRY_BLEND_FRAMES,
) -> dict[str, NormalizedArtifact[BodyMotionArtifact]]:
    """Compose independently generated phases into actor-continuous canonical motion.

    The provider is allowed to generate every atomic phase in its own local root frame.
    This pass converts those independent clips into reference-pose offsets for the whole
    actor performance, blends phase entry poses, and locks target-facing hold phases so
    model drift cannot move or rotate the actor while it is meant to remain still.

    Target-facing *direction* is intentionally not invented here. It requires the bound
    scene object's transform and is handled by the later target-constraint stage.
    """

    if blend_frames < 0:
        raise ValueError("blend_frames must be non-negative.")

    missing = [request.semantic_id for request in requests if request.semantic_id not in artifacts]
    if missing:
        raise ValueError("Missing normalized body artifacts: " + ", ".join(missing))

    by_actor: dict[str, list[BodyGenerationRequest]] = defaultdict(list)
    for request in requests:
        by_actor[request.actor_binding_id].append(request)

    composed: dict[str, NormalizedArtifact[BodyMotionArtifact]] = {}
    for actor_requests in by_actor.values():
        actor_requests.sort(key=lambda item: (item.start_frame, item.end_frame, item.semantic_id))
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
            # Preserve the boundary pose bit-for-bit. Calling the quaternion
            # interpolator with alpha=0 would still normalize/round the value,
            # introducing a tiny numerical discontinuity at the phase boundary.
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


def _is_target_facing_hold(request: BodyGenerationRequest) -> bool:
    if request.target_binding_id is None:
        return False

    # Only classify the atomic action, not the larger-performance context appended
    # later in the prompt. Otherwise a turn phase can inherit words such as
    # "remain facing" from the enclosing performance and be incorrectly frozen.
    match = re.search(
        r"Action:\s*(.+?)\s+Style:",
        request.prompt,
        flags=re.IGNORECASE | re.DOTALL,
    )
    text = (match.group(1) if match is not None else request.prompt).lower()
    return (
        any(token in text for token in ("hold", "remain", "stand"))
        and any(token in text for token in ("facing", "toward", "still", "stance"))
    )


def _lock_stationary_root_and_heading(motion: BodyMotionArtifact) -> BodyMotionArtifact:
    anchor_root = motion.samples[0].root_translation.model_copy(deep=True)
    anchor_pelvis = motion.samples[0].joint_rotations[0].model_copy(deep=True)

    samples: list[BodyMotionSample] = []
    for sample in motion.samples:
        rotations = [rotation.model_copy(deep=True) for rotation in sample.joint_rotations]
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
