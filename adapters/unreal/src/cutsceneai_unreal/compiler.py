from __future__ import annotations

import re
from collections.abc import Iterable

from cutsceneai_cir import (
    CameraAngle,
    CameraFraming,
    CameraMovement,
    PerformancePlan,
    Project,
    validate_project_model,
)
from cutsceneai_preview import (
    PerformanceCue,
    PreviewEntity,
    compile_project as compile_preview,
)

from .conversion import convert_transform, look_at_quaternion
from .models import (
    UnrealActorBinding,
    UnrealActorKind,
    UnrealCameraBinding,
    UnrealExportPlan,
    UnrealExportWarning,
    UnrealPerformanceCue,
    UnrealSceneSequence,
    UnrealTransform,
    UnrealVector,
)


DEFAULT_PACKAGE_PATH = "/Game/CutSceneAI/Sequences"
CHARACTER_CLASS_PATH = "/Script/Engine.Character"
STATIC_MESH_ACTOR_CLASS_PATH = "/Script/Engine.StaticMeshActor"

_CAMERA_DISTANCE_CM = {
    CameraFraming.EXTREME_WIDE: 900.0,
    CameraFraming.WIDE: 600.0,
    CameraFraming.MEDIUM_WIDE: 450.0,
    CameraFraming.MEDIUM: 350.0,
    CameraFraming.MEDIUM_CLOSE_UP: 250.0,
    CameraFraming.CLOSE_UP: 180.0,
    CameraFraming.EXTREME_CLOSE_UP: 100.0,
    CameraFraming.OVER_THE_SHOULDER: 250.0,
    CameraFraming.POINT_OF_VIEW: 50.0,
    CameraFraming.INSERT: 120.0,
}

_CAMERA_HEIGHT_CM = {
    CameraAngle.EYE_LEVEL: 0.0,
    CameraAngle.LOW: -80.0,
    CameraAngle.HIGH: 160.0,
    CameraAngle.DUTCH: 0.0,
    CameraAngle.OVERHEAD: 500.0,
}


def compile_project(
    project: Project, *, package_path: str = DEFAULT_PACKAGE_PATH
) -> UnrealExportPlan:
    """Compile validated CIR into a deterministic Unreal Sequencer import plan."""

    validate_project_model(project)
    _validate_package_path(package_path)
    preview = compile_preview(project)
    warnings: list[UnrealExportWarning] = []
    actor_bindings = _compile_actors(project, preview.entities, warnings)
    binding_by_entity = {
        binding.source_entity_id: binding.binding_id for binding in actor_bindings
    }
    point_by_entity = {
        entity.id: _entity_target_point(entity) for entity in preview.entities
    }

    source_scene_by_id = {scene.id: scene for scene in project.scenes}
    sequences: list[UnrealSceneSequence] = []
    for preview_scene in preview.scenes:
        source_scene = source_scene_by_id[preview_scene.id]
        source_performances = [
            (beat.id, performance)
            for beat in source_scene.beats
            for performance in beat.performances
        ]
        if len(source_performances) != len(preview_scene.performance_cues):
            raise RuntimeError("Preview and CIR performance timelines diverged.")

        performance_cues = [
            _compile_performance_cue(
                preview_cue=preview_cue,
                source_beat_id=source_beat_id,
                source_performance=source_performance,
                binding_by_entity=binding_by_entity,
            )
            for preview_cue, (source_beat_id, source_performance) in zip(
                preview_scene.performance_cues, source_performances, strict=True
            )
        ]
        if performance_cues:
            warnings.append(
                UnrealExportWarning(
                    code="performance_metadata_only",
                    source_id=source_scene.id,
                    message=(
                        "Performance cues are imported as editable Sequencer markers; "
                        "animation and audio asset binding is a later adapter phase."
                    ),
                )
            )

        cameras: list[UnrealCameraBinding] = []
        for cut in preview_scene.camera_cuts:
            target_ids = cut.target_ids or cut.subject_ids
            look_at = _average_points(
                point_by_entity[target_id] for target_id in target_ids
            )
            if cut.transform is None:
                inferred = True
                transform = _infer_camera_transform(
                    look_at=look_at,
                    framing=cut.framing,
                    angle=cut.angle,
                )
                warnings.append(
                    UnrealExportWarning(
                        code="inferred_camera_transform",
                        source_id=cut.shot_id,
                        message=(
                            f"Camera '{cut.shot_id}' had no CIR transform; the adapter "
                            "generated a deterministic blocking pose."
                        ),
                    )
                )
            else:
                inferred = False
                transform = convert_transform(cut.transform)

            if cut.movement is not CameraMovement.STATIC:
                warnings.append(
                    UnrealExportWarning(
                        code="camera_movement_metadata_only",
                        source_id=cut.shot_id,
                        message=(
                            f"Camera movement '{cut.movement.value}' is retained as metadata; "
                            "v0.1 imports a blocking pose for manual keyframing."
                        ),
                    )
                )

            cameras.append(
                UnrealCameraBinding(
                    binding_id=f"camera:{cut.shot_id}",
                    source_shot_id=cut.shot_id,
                    source_beat_ids=cut.beat_ids,
                    display_name=f"CAM_{_unreal_name(cut.shot_id)}",
                    start_frame=cut.start_frame,
                    end_frame=cut.end_frame,
                    purpose=cut.purpose,
                    description=cut.description,
                    framing=cut.framing,
                    angle=cut.angle,
                    movement=cut.movement,
                    lens_mm=cut.lens_mm,
                    subject_binding_ids=[
                        binding_by_entity[subject_id] for subject_id in cut.subject_ids
                    ],
                    target_binding_ids=[
                        binding_by_entity[target_id] for target_id in target_ids
                    ],
                    composition=cut.composition,
                    transform=transform,
                    look_at_location_cm=look_at,
                    inferred_transform=inferred,
                )
            )

        sequences.append(
            UnrealSceneSequence(
                source_scene_id=source_scene.id,
                title=source_scene.title,
                location=source_scene.location,
                asset_name=f"LS_{_unreal_name(source_scene.id)}",
                package_path=package_path,
                duration_frames=preview_scene.duration_frames,
                actors=actor_bindings,
                performance_cues=performance_cues,
                cameras=cameras,
            )
        )

    return UnrealExportPlan(
        project_id=project.id,
        project_name=project.name,
        source_settings=project.settings,
        sequences=sequences,
        warnings=warnings,
    )


def _compile_actors(
    project: Project,
    entities: list[PreviewEntity],
    warnings: list[UnrealExportWarning],
) -> list[UnrealActorBinding]:
    environment_by_id = {item.id: item for item in project.environment}
    bindings: list[UnrealActorBinding] = []
    for entity in entities:
        if entity.kind.value == "character":
            asset_path = None
            placeholder = True
            kind = UnrealActorKind.CHARACTER
            actor_class_path = CHARACTER_CLASS_PATH
            warnings.append(
                UnrealExportWarning(
                    code="placeholder_character",
                    source_id=entity.id,
                    message=f"Character '{entity.id}' imports as an Unreal Character placeholder.",
                )
            )
        else:
            source_item = environment_by_id[entity.id]
            asset_path = _unreal_asset_path(source_item.asset_uri)
            placeholder = asset_path is None
            kind = UnrealActorKind.ENVIRONMENT
            actor_class_path = STATIC_MESH_ACTOR_CLASS_PATH
            if source_item.asset_uri is not None and asset_path is None:
                warnings.append(
                    UnrealExportWarning(
                        code="unsupported_asset_uri",
                        source_id=entity.id,
                        message=(
                            f"Asset URI '{source_item.asset_uri}' is not an Unreal /Game path; "
                            "a placeholder will be imported."
                        ),
                    )
                )
            elif placeholder:
                warnings.append(
                    UnrealExportWarning(
                        code="placeholder_environment",
                        source_id=entity.id,
                        message=(
                            f"Environment object '{entity.id}' imports as a StaticMeshActor "
                            "placeholder."
                        ),
                    )
                )

        bindings.append(
            UnrealActorBinding(
                binding_id=f"actor:{entity.id}",
                source_entity_id=entity.id,
                display_name=f"ACT_{_unreal_name(entity.id)}",
                kind=kind,
                actor_class_path=actor_class_path,
                asset_path=asset_path,
                placeholder=placeholder,
                transform=convert_transform(entity.initial_transform),
            )
        )
    return bindings


def _compile_performance_cue(
    *,
    preview_cue: PerformanceCue,
    source_beat_id: str,
    source_performance: PerformancePlan,
    binding_by_entity: dict[str, str],
) -> UnrealPerformanceCue:
    dialogue = source_performance.dialogue
    return UnrealPerformanceCue(
        source_beat_id=source_beat_id,
        actor_binding_id=binding_by_entity[source_performance.character_id],
        start_frame=preview_cue.start_frame,
        end_frame=preview_cue.end_frame,
        motion_prompt=source_performance.motion.prompt,
        motion_style=source_performance.motion.style,
        motion_asset_uri=source_performance.motion.asset_uri,
        emotion=source_performance.facial.emotion,
        emotion_intensity=source_performance.facial.intensity,
        facial_asset_uri=source_performance.facial.asset_uri,
        lip_sync=source_performance.facial.lip_sync,
        dialogue=dialogue.text if dialogue is not None else None,
        dialogue_language=dialogue.language if dialogue is not None else None,
        dialogue_audio_uri=dialogue.audio_uri if dialogue is not None else None,
        dialogue_start_frame=preview_cue.dialogue_start_frame,
        look_at_binding_id=(
            binding_by_entity[source_performance.look_at_id]
            if source_performance.look_at_id is not None
            else None
        ),
    )


def _entity_target_point(entity: PreviewEntity) -> UnrealVector:
    point = convert_transform(entity.initial_transform).location_cm
    if entity.kind.value == "character":
        return UnrealVector(x=point.x, y=point.y, z=point.z + 160.0)
    return point


def _average_points(points: Iterable[UnrealVector]) -> UnrealVector:
    values = list(points)
    if not values:
        return UnrealVector()
    count = float(len(values))
    return UnrealVector(
        x=sum(point.x for point in values) / count,
        y=sum(point.y for point in values) / count,
        z=sum(point.z for point in values) / count,
    )


def _infer_camera_transform(
    *, look_at: UnrealVector, framing: CameraFraming, angle: CameraAngle
) -> UnrealTransform:
    lateral = 80.0 if framing is CameraFraming.OVER_THE_SHOULDER else 0.0
    location = UnrealVector(
        x=look_at.x - _CAMERA_DISTANCE_CM[framing],
        y=look_at.y + lateral,
        z=look_at.z + _CAMERA_HEIGHT_CM[angle],
    )
    return UnrealTransform(
        location_cm=location,
        rotation=look_at_quaternion(location, look_at),
        scale=UnrealVector(x=1.0, y=1.0, z=1.0),
    )


def _unreal_asset_path(asset_uri: str | None) -> str | None:
    if asset_uri is None or not asset_uri.startswith("/Game/"):
        return None
    return asset_uri


def _unreal_name(value: str) -> str:
    return "".join(
        part[:1].upper() + part[1:] for part in re.split(r"[-_]", value) if part
    )


def _validate_package_path(package_path: str) -> None:
    if re.fullmatch(r"/Game(?:/[A-Za-z][A-Za-z0-9_]*)+", package_path) is None:
        raise ValueError(
            "Unreal package path must start with /Game and contain only safe asset segments."
        )
