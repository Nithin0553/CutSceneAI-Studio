from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from cutsceneai_cir import Project
from cutsceneai_parity import compile_semantics
from cutsceneai_performance._geometry import Quaternion, Vector3
from cutsceneai_performance.composition import (
    CanonicalSceneTransform,
    compose_body_sequence,
)
from cutsceneai_performance.models import ModelProvenance, PerformanceGenerationPlan
from cutsceneai_performance.motion import BodyMotionArtifact, resample_body_motion
from cutsceneai_performance.providers import NormalizedArtifact


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


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


def _angle_deg(first: Vector3, second: Vector3) -> float:
    first_len = math.hypot(first.x, first.z)
    second_len = math.hypot(second.x, second.z)
    if first_len <= 1e-9 or second_len <= 1e-9:
        raise ValueError("Cannot compare zero-length ground-plane directions.")
    dot = (
        first.x * second.x + first.z * second.z
    ) / (first_len * second_len)
    return math.degrees(math.acos(max(-1.0, min(1.0, dot))))


def _quat_angle_deg(first: Quaternion, second: Quaternion) -> float:
    dot = abs(
        first.x * second.x
        + first.y * second.y
        + first.z * second.z
        + first.w * second.w
    )
    return math.degrees(2.0 * math.acos(max(-1.0, min(1.0, dot))))


def _scene_transforms(project: Project) -> dict[str, CanonicalSceneTransform]:
    semantics = compile_semantics(project)
    entity_by_source = {
        entity.source_entity_id: entity.binding_id
        for entity in semantics.scenes[0].entities
    }
    transforms: dict[str, CanonicalSceneTransform] = {}
    for entity in [*project.characters, *project.environment]:
        transform = entity.initial_transform
        transforms[entity_by_source[entity.id]] = CanonicalSceneTransform(
            position=Vector3(
                x=transform.position.x,
                y=transform.position.y,
                z=transform.position.z,
            ),
            rotation=Quaternion(
                x=transform.rotation.x,
                y=transform.rotation.y,
                z=transform.rotation.z,
                w=transform.rotation.w,
            ),
        )
    return transforms


def _saved_body_paths(run_dir: Path) -> dict[str, Path]:
    output: dict[str, Path] = {}
    for metadata_path in (run_dir / "body-provider-outputs").glob("*.metadata.json"):
        metadata = _load_json(metadata_path)
        semantic_id = str(metadata["request_semantic_id"])
        artifact_file = str(metadata["artifact_file"])
        output[semantic_id] = metadata_path.parent / artifact_file
    return output


def _provenance(request) -> ModelProvenance:
    return ModelProvenance(
        provider=request.provider,
        model=request.model,
        model_revision=request.model_revision,
        prompt_sha256=request.prompt_sha256,
        configuration_sha256=request.configuration_sha256,
        seed=request.seed,
        deterministic_algorithms=True,
    )


def _phase_request(plan: PerformanceGenerationPlan, token: str):
    matches = [item for item in plan.body_requests if token in item.semantic_id]
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one body request containing '{token}', found {len(matches)}."
        )
    return matches[0]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify CutSceneAI target-facing composition against a saved performance run."
    )
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--turn-motion", type=Path)
    parser.add_argument("--hold-motion", type=Path)
    parser.add_argument("--turn-phase", default="guard_turn_to_door")
    parser.add_argument("--hold-phase", default="guard_hold_at_door")
    args = parser.parse_args()

    run_dir = args.run_dir.resolve()
    project = Project.model_validate_json(
        (run_dir / "input.cir.json").read_text(encoding="utf-8-sig")
    )
    plan = PerformanceGenerationPlan.model_validate_json(
        (run_dir / "generation.plan.json").read_text(encoding="utf-8-sig")
    )
    saved_paths = _saved_body_paths(run_dir)

    turn_request = _phase_request(plan, args.turn_phase)
    hold_request = _phase_request(plan, args.hold_phase)
    if args.turn_motion is not None:
        saved_paths[turn_request.semantic_id] = args.turn_motion.resolve()
    if args.hold_motion is not None:
        saved_paths[hold_request.semantic_id] = args.hold_motion.resolve()

    normalized: dict[str, NormalizedArtifact[BodyMotionArtifact]] = {}
    for request in plan.body_requests:
        try:
            motion_path = saved_paths[request.semantic_id]
        except KeyError as exc:
            raise ValueError(
                f"No saved motion found for '{request.semantic_id}'."
            ) from exc
        raw = BodyMotionArtifact.model_validate_json(
            motion_path.read_text(encoding="utf-8-sig")
        )
        artifact = resample_body_motion(
            raw,
            target_fps=plan.fps,
            target_frame_count=request.end_frame - request.start_frame,
        )
        normalized[request.semantic_id] = NormalizedArtifact(
            request_semantic_id=request.semantic_id,
            artifact=artifact,
            provenance=_provenance(request),
        )

    transforms = _scene_transforms(project)
    composed = compose_body_sequence(
        plan.body_requests,
        normalized,
        scene_transforms=transforms,
    )

    turn = composed[turn_request.semantic_id].artifact
    hold = composed[hold_request.semantic_id].artifact
    actor_transform = transforms[turn_request.actor_binding_id]
    if turn_request.target_binding_id is None:
        raise ValueError("Turn request has no target binding.")
    target_transform = transforms[turn_request.target_binding_id]

    final = turn.samples[-1]
    world_offset = _rotate(actor_transform.rotation, final.root_translation)
    world_root = Vector3(
        x=actor_transform.position.x + world_offset.x,
        y=actor_transform.position.y + world_offset.y,
        z=actor_transform.position.z + world_offset.z,
    )
    world_pelvis = _multiply(actor_transform.rotation, final.joint_rotations[0])
    actual_forward = _rotate(
        world_pelvis,
        Vector3(x=0.0, y=0.0, z=-1.0),
    )
    desired_forward = Vector3(
        x=target_transform.position.x - world_root.x,
        y=0.0,
        z=target_transform.position.z - world_root.z,
    )
    facing_error = _angle_deg(actual_forward, desired_forward)

    requests = sorted(
        plan.body_requests,
        key=lambda item: (item.start_frame, item.end_frame, item.semantic_id),
    )
    print("TARGET_FACING_VERIFY=PASS" if facing_error <= 0.1 else "TARGET_FACING_VERIFY=FAIL")
    print(f"TURN_PHASE={turn_request.semantic_id}")
    print(f"TARGET={turn_request.target_binding_id}")
    print(
        "TURN_END_WORLD_ROOT="
        f"({world_root.x:.6f},{world_root.y:.6f},{world_root.z:.6f})"
    )
    print(
        "TARGET_WORLD_POSITION="
        f"({target_transform.position.x:.6f},{target_transform.position.y:.6f},"
        f"{target_transform.position.z:.6f})"
    )
    print(f"FINAL_FACING_ERROR_DEG={facing_error:.9f}")

    for previous_request, current_request in zip(requests, requests[1:], strict=False):
        previous = composed[previous_request.semantic_id].artifact.samples[-1]
        current = composed[current_request.semantic_id].artifact.samples[0]
        dx = current.root_translation.x - previous.root_translation.x
        dy = current.root_translation.y - previous.root_translation.y
        dz = current.root_translation.z - previous.root_translation.z
        root_jump = math.sqrt(dx * dx + dy * dy + dz * dz)
        pelvis_jump = _quat_angle_deg(
            previous.joint_rotations[0],
            current.joint_rotations[0],
        )
        print(
            f"BOUNDARY={previous_request.semantic_id}->{current_request.semantic_id} "
            f"ROOT_JUMP_M={root_jump:.9f} PELVIS_JUMP_DEG={pelvis_jump:.9f}"
        )

    hold_root = hold.samples[0].root_translation
    hold_pelvis = hold.samples[0].joint_rotations[0]
    max_root_drift = 0.0
    max_pelvis_drift = 0.0
    for sample in hold.samples:
        dx = sample.root_translation.x - hold_root.x
        dy = sample.root_translation.y - hold_root.y
        dz = sample.root_translation.z - hold_root.z
        max_root_drift = max(max_root_drift, math.sqrt(dx * dx + dy * dy + dz * dz))
        max_pelvis_drift = max(
            max_pelvis_drift,
            _quat_angle_deg(hold_pelvis, sample.joint_rotations[0]),
        )
    print(f"HOLD_MAX_ROOT_DRIFT_M={max_root_drift:.9f}")
    print(f"HOLD_MAX_PELVIS_DRIFT_DEG={max_pelvis_drift:.9f}")
    return 0 if facing_error <= 0.1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
