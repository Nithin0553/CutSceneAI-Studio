from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import uuid

from cutsceneai_cir import Project
from cutsceneai_parity import compile_semantics
from cutsceneai_performance._geometry import Quaternion, Vector3
from cutsceneai_performance.bundle import (
    PerformanceBundle,
    load_performance_bundle,
    render_performance_bundle,
    verify_performance_bundle,
)
from cutsceneai_performance.composition import (
    CanonicalSceneTransform,
    compose_body_sequence,
)
from cutsceneai_performance.models import (
    ArtifactFormat,
    ArtifactKind,
    ArtifactReference,
    ModelProvenance,
    PerformanceGenerationPlan,
)
from cutsceneai_performance.motion import (
    BodyMotionArtifact,
    render_body_motion,
    resample_body_motion,
)
from cutsceneai_performance.providers import NormalizedArtifact
from cutsceneai_performance.serialization import render_performance_package
from app.models.performance_runtime import (
    PerformanceRunRecord,
    PerformanceRunStatus,
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _scene_transforms(project: Project) -> dict[str, CanonicalSceneTransform]:
    semantics = compile_semantics(project)
    if len(semantics.scenes) != 1:
        raise ValueError("Saved-run recomposition requires exactly one semantic scene.")
    binding_by_source = {
        entity.source_entity_id: entity.binding_id
        for entity in semantics.scenes[0].entities
    }
    output: dict[str, CanonicalSceneTransform] = {}
    for entity in [*project.characters, *project.environment]:
        transform = entity.initial_transform
        output[binding_by_source[entity.id]] = CanonicalSceneTransform(
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
    return output


def _saved_body_paths(run_dir: Path) -> dict[str, Path]:
    output: dict[str, Path] = {}
    source = run_dir / "body-provider-outputs"
    for metadata_path in source.glob("*.metadata.json"):
        metadata = _load_json(metadata_path)
        semantic_id = str(metadata["request_semantic_id"])
        artifact_file = str(metadata["artifact_file"])
        output[semantic_id] = source / artifact_file
    return output


def _request_containing(plan: PerformanceGenerationPlan, token: str):
    matches = [request for request in plan.body_requests if token in request.semantic_id]
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one body request containing '{token}', found {len(matches)}."
        )
    return matches[0]


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


def _portable_child_run_path(source: PerformanceRunRecord, run_id: str) -> str:
    source_path = PurePosixPath(source.run_directory.replace("\\", "/"))
    if source_path.name == source.run_id:
        return str(source_path.parent / run_id)
    return str(source_path.parent / run_id)


def _copy_optional(source_dir: Path, destination_dir: Path, filename: str) -> None:
    source = source_dir / filename
    if source.exists():
        shutil.copy2(source, destination_dir / filename)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create a verified derived CutSceneAI performance run by recomposing saved body "
            "provider outputs without invoking the body model again."
        )
    )
    parser.add_argument("--source-run-dir", type=Path, required=True)
    parser.add_argument("--turn-motion", type=Path)
    parser.add_argument("--hold-motion", type=Path)
    parser.add_argument("--turn-phase", default="guard_turn_to_door")
    parser.add_argument("--hold-phase", default="guard_hold_at_door")
    args = parser.parse_args()

    source_dir = args.source_run_dir.resolve()
    source_record = PerformanceRunRecord.model_validate_json(
        (source_dir / "run.json").read_text(encoding="utf-8-sig")
    )
    if source_record.status is not PerformanceRunStatus.SUCCEEDED:
        raise ValueError("Source performance run must have succeeded.")

    project = Project.model_validate_json(
        (source_dir / "input.cir.json").read_text(encoding="utf-8-sig")
    )
    source_bundle = load_performance_bundle(
        (source_dir / "performance.bundle.zip").read_bytes()
    )
    plan = source_bundle.plan
    if project.id != plan.project_id or source_record.project_id != project.id:
        raise ValueError("Source run, CIR, and performance bundle project identities diverge.")

    motion_paths = _saved_body_paths(source_dir)
    if args.turn_motion is not None:
        request = _request_containing(plan, args.turn_phase)
        motion_paths[request.semantic_id] = args.turn_motion.resolve()
    if args.hold_motion is not None:
        request = _request_containing(plan, args.hold_phase)
        motion_paths[request.semantic_id] = args.hold_motion.resolve()

    normalized: dict[str, NormalizedArtifact[BodyMotionArtifact]] = {}
    for request in plan.body_requests:
        try:
            motion_path = motion_paths[request.semantic_id]
        except KeyError as exc:
            raise ValueError(
                f"Missing saved provider body motion for '{request.semantic_id}'."
            ) from exc
        raw_motion = BodyMotionArtifact.model_validate_json(
            motion_path.read_text(encoding="utf-8-sig")
        )
        artifact = resample_body_motion(
            raw_motion,
            target_fps=plan.fps,
            target_frame_count=request.end_frame - request.start_frame,
        )
        normalized[request.semantic_id] = NormalizedArtifact(
            request_semantic_id=request.semantic_id,
            artifact=artifact,
            provenance=_provenance(request),
        )

    composed = compose_body_sequence(
        plan.body_requests,
        normalized,
        scene_transforms=_scene_transforms(project),
    )

    artifact_files = dict(source_bundle.artifact_files)
    request_by_id = {request.semantic_id: request for request in plan.body_requests}
    rebuilt_body_tracks = []
    for track in source_bundle.package.body_tracks:
        request = request_by_id[track.semantic_id]
        body = composed[track.semantic_id]
        data = render_body_motion(body.artifact).encode("utf-8")
        reference = ArtifactReference(
            kind=ArtifactKind.BODY_MOTION,
            format=ArtifactFormat.CUTSCENEAI_MOTION_JSON,
            relative_path=track.artifact.relative_path,
            sha256=_sha256(data),
            byte_length=len(data),
        )
        artifact_files[track.artifact.relative_path] = data
        rebuilt_body_tracks.append(
            track.model_copy(
                update={
                    "artifact": reference,
                    "sample_count": body.artifact.frame_count,
                    "provenance": body.provenance,
                },
                deep=True,
            )
        )

    package = source_bundle.package.model_copy(
        update={"body_tracks": rebuilt_body_tracks},
        deep=True,
    )
    derived_bundle = PerformanceBundle(
        plan=source_bundle.plan.model_copy(deep=True),
        package=package,
        artifact_files=artifact_files,
    )
    verify_performance_bundle(derived_bundle)
    bundle_bytes = render_performance_bundle(derived_bundle)
    # Round-trip through the strict loader so the derived artifact is proven portable.
    load_performance_bundle(bundle_bytes)

    run_id = str(uuid.uuid4())
    destination = source_dir.parent / run_id
    destination.mkdir(parents=False, exist_ok=False)

    now = datetime.now(UTC).isoformat()
    derived_record = source_record.model_copy(
        update={
            "run_id": run_id,
            "status": PerformanceRunStatus.SUCCEEDED,
            "created_at_utc": now,
            "completed_at_utc": now,
            "run_directory": _portable_child_run_path(source_record, run_id),
            "bundle_sha256": _sha256(bundle_bytes),
            "bundle_byte_length": len(bundle_bytes),
            "warnings": [
                *source_record.warnings,
                f"Derived from performance run {source_record.run_id} by deterministic body recomposition; no body inference was executed.",
            ],
            "error": None,
        },
        deep=True,
    )

    shutil.copy2(source_dir / "input.cir.json", destination / "input.cir.json")
    shutil.copy2(source_dir / "generation.plan.json", destination / "generation.plan.json")
    _copy_optional(source_dir, destination, "provider-readiness.json")
    _copy_optional(source_dir, destination, "dialogue.manifest.json")
    (destination / "performance.bundle.zip").write_bytes(bundle_bytes)
    (destination / "performance.package.json").write_text(
        render_performance_package(derived_bundle.package),
        encoding="utf-8",
        newline="\n",
    )
    (destination / "run.json").write_text(
        derived_record.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (destination / "derived-from.json").write_text(
        json.dumps(
            {
                "derivation_version": "0.1.0",
                "source_run_id": source_record.run_id,
                "derived_run_id": run_id,
                "body_inference_executed": False,
                "turn_motion_override": (
                    str(args.turn_motion.resolve()) if args.turn_motion is not None else None
                ),
                "hold_motion_override": (
                    str(args.hold_motion.resolve()) if args.hold_motion is not None else None
                ),
                "bundle_sha256": _sha256(bundle_bytes),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print("CUTSCENEAI_DERIVED_RUN=PASS")
    print(f"SOURCE_RUN_ID={source_record.run_id}")
    print(f"DERIVED_RUN_ID={run_id}")
    print(f"DERIVED_RUN_DIR={destination}")
    print(f"BUNDLE_SHA256={_sha256(bundle_bytes)}")
    print("BODY_INFERENCE_EXECUTED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
