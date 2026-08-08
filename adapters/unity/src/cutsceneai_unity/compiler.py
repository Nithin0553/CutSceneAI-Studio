from __future__ import annotations

import re
from collections.abc import Iterable

from cutsceneai_cir import CameraAngle, CameraFraming, Project, validate_project_model
from cutsceneai_parity import EntityKind, TimelineSemantics, compile_semantics
from cutsceneai_preview import compile_project as compile_preview

from .conversion import convert_position, convert_transform
from .models import (
    UnityActorBinding,
    UnityAnimationSection,
    UnityAssetMap,
    UnityAudioSection,
    UnityCameraCut,
    UnityExportPlan,
    UnityExportWarning,
    UnityPrimitive,
    UnitySceneTimeline,
    UnityVector,
)


DEFAULT_TIMELINE_PATH = "Assets/CutSceneAI/Timelines"
DEFAULT_SCENE_PATH = "Assets/CutSceneAI/Scenes"

_CAMERA_DISTANCE_M = {
    CameraFraming.EXTREME_WIDE: 9.0,
    CameraFraming.WIDE: 6.0,
    CameraFraming.MEDIUM_WIDE: 4.5,
    CameraFraming.MEDIUM: 3.5,
    CameraFraming.MEDIUM_CLOSE_UP: 2.5,
    CameraFraming.CLOSE_UP: 1.8,
    CameraFraming.EXTREME_CLOSE_UP: 1.0,
    CameraFraming.OVER_THE_SHOULDER: 2.5,
    CameraFraming.POINT_OF_VIEW: 0.5,
    CameraFraming.INSERT: 1.2,
}

_CAMERA_HEIGHT_M = {
    CameraAngle.EYE_LEVEL: 0.0,
    CameraAngle.LOW: -0.8,
    CameraAngle.HIGH: 1.6,
    CameraAngle.DUTCH: 0.0,
    CameraAngle.OVERHEAD: 5.0,
}


def _validate_asset_folder(path: str, name: str) -> None:
    if not re.fullmatch(r"Assets(?:/[A-Za-z0-9_.-]+)+", path):
        raise ValueError(f"{name} must be a normalized Unity Assets path")


def _unity_name(value: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", value)
    if not words:
        raise ValueError(
            "Unity asset name requires at least one alphanumeric character"
        )
    return "".join(word[:1].upper() + word[1:] for word in words)


def _average(points: Iterable[UnityVector]) -> UnityVector:
    values = list(points)
    if not values:
        return UnityVector()
    count = float(len(values))
    return UnityVector(
        x=sum(point.x for point in values) / count,
        y=sum(point.y for point in values) / count,
        z=sum(point.z for point in values) / count,
    )


def _infer_camera_position(
    look_at: UnityVector, framing: CameraFraming, angle: CameraAngle
) -> UnityVector:
    return UnityVector(
        x=look_at.x + (1.1 if framing is CameraFraming.OVER_THE_SHOULDER else 0.0),
        y=look_at.y + _CAMERA_HEIGHT_M[angle],
        z=look_at.z - _CAMERA_DISTANCE_M[framing],
    )


def _asset_maps(
    project: Project, asset_map: UnityAssetMap | None
) -> tuple[dict[str, str], dict[str, str], dict[str, tuple[str, int]]]:
    if asset_map is None:
        return {}, {}, {}
    if asset_map.project_id != project.id:
        raise ValueError(
            f"Unity asset map project '{asset_map.project_id}' does not match CIR project "
            f"'{project.id}'."
        )
    return (
        {item.source_entity_id: item.prefab_path for item in asset_map.entities},
        {item.cue_id: item.asset_path for item in asset_map.animations},
        {item.cue_id: (item.asset_path, item.end_frame) for item in asset_map.audio},
    )


def _validate_mapping_keys(
    *,
    entity_assets: dict[str, str],
    animation_assets: dict[str, str],
    audio_assets: dict[str, tuple[str, int]],
    semantics: TimelineSemantics,
) -> None:
    entity_ids = {
        entity.source_entity_id
        for scene in semantics.scenes
        for entity in scene.entities
    }
    performance_ids = {
        cue.cue_id for scene in semantics.scenes for cue in scene.performance_cues
    }
    dialogue_ids = {
        cue.cue_id for scene in semantics.scenes for cue in scene.dialogue_cues
    }
    unknown = (
        [("entity", value) for value in entity_assets.keys() - entity_ids]
        + [("animation", value) for value in animation_assets.keys() - performance_ids]
        + [("audio", value) for value in audio_assets.keys() - dialogue_ids]
    )
    if unknown:
        kind, value = sorted(unknown)[0]
        raise ValueError(f"Unity asset map references unknown {kind} key '{value}'.")


def compile_project(
    project: Project,
    *,
    asset_map: UnityAssetMap | None = None,
    timeline_path: str = DEFAULT_TIMELINE_PATH,
    scene_path: str = DEFAULT_SCENE_PATH,
) -> UnityExportPlan:
    """Compile validated CIR into a deterministic Unity Timeline editor plan."""

    validate_project_model(project)
    _validate_asset_folder(timeline_path, "timeline_path")
    _validate_asset_folder(scene_path, "scene_path")
    semantics = compile_semantics(project)
    preview = compile_preview(project)
    entity_assets, animation_assets, audio_assets = _asset_maps(project, asset_map)
    _validate_mapping_keys(
        entity_assets=entity_assets,
        animation_assets=animation_assets,
        audio_assets=audio_assets,
        semantics=semantics,
    )
    preview_entity_by_id = {entity.id: entity for entity in preview.entities}
    semantic_scene_by_id = {scene.source_scene_id: scene for scene in semantics.scenes}
    warnings: list[UnityExportWarning] = []
    sequences: list[UnitySceneTimeline] = []

    for scene in project.scenes:
        semantic_scene = semantic_scene_by_id[scene.id]
        actors: list[UnityActorBinding] = []
        for entity in semantic_scene.entities:
            preview_entity = preview_entity_by_id[entity.source_entity_id]
            prefab_path = entity_assets.get(entity.source_entity_id)
            placeholder = prefab_path is None
            actors.append(
                UnityActorBinding(
                    binding_id=entity.binding_id,
                    source_entity_id=entity.source_entity_id,
                    display_name=f"CSA_ACT_{_unity_name(entity.source_entity_id)}",
                    kind=entity.kind,
                    prefab_path=prefab_path,
                    placeholder=placeholder,
                    placeholder_primitive=(
                        UnityPrimitive.CAPSULE
                        if entity.kind is EntityKind.CHARACTER
                        else UnityPrimitive.CUBE
                    ),
                    transform=convert_transform(preview_entity.initial_transform),
                )
            )
            if placeholder:
                warnings.append(
                    UnityExportWarning(
                        code="placeholder_entity",
                        source_id=entity.source_entity_id,
                        message=(
                            f"Entity '{entity.source_entity_id}' uses an editable Unity "
                            "primitive because no prefab mapping was supplied."
                        ),
                    )
                )

        animations = [
            UnityAnimationSection(
                cue_id=cue.cue_id,
                actor_binding_id=cue.actor_binding_id,
                start_frame=cue.start_frame,
                end_frame=cue.end_frame,
                asset_path=animation_assets.get(cue.cue_id),
                placeholder=cue.cue_id not in animation_assets,
            )
            for cue in semantic_scene.performance_cues
        ]
        for animation in animations:
            if animation.placeholder:
                warnings.append(
                    UnityExportWarning(
                        code="placeholder_animation",
                        source_id=animation.cue_id,
                        message=(
                            f"Performance '{animation.cue_id}' uses an editable empty Animation "
                            "Clip because no Unity AnimationClip mapping was supplied."
                        ),
                    )
                )

        audio_sections: list[UnityAudioSection] = []
        for cue in semantic_scene.dialogue_cues:
            mapping = audio_assets.get(cue.cue_id)
            if mapping is None:
                warnings.append(
                    UnityExportWarning(
                        code="dialogue_metadata_only",
                        source_id=cue.cue_id,
                        message=(
                            f"Dialogue '{cue.cue_id}' remains semantic metadata because no "
                            "Unity AudioClip mapping was supplied."
                        ),
                    )
                )
                continue
            asset_path, end_frame = mapping
            if end_frame <= cue.start_frame:
                raise ValueError(
                    f"Unity audio mapping '{cue.cue_id}' must end after frame "
                    f"{cue.start_frame}."
                )
            if end_frame > cue.window_end_frame:
                raise ValueError(
                    f"Unity audio mapping '{cue.cue_id}' ends at frame {end_frame}, beyond "
                    f"its CIR window ending at {cue.window_end_frame}."
                )
            audio_sections.append(
                UnityAudioSection(
                    cue_id=cue.cue_id,
                    actor_binding_id=cue.actor_binding_id,
                    start_frame=cue.start_frame,
                    end_frame=end_frame,
                    asset_path=asset_path,
                )
            )

        point_by_binding = {
            actor.binding_id: actor.transform.position_m for actor in actors
        }
        cameras: list[UnityCameraCut] = []
        shot_by_id = {shot.id: shot for shot in scene.shots}
        for cut in semantic_scene.camera_cuts:
            target_ids = cut.target_binding_ids or cut.subject_binding_ids
            look_at = _average(point_by_binding[item] for item in target_ids)
            source_shot = shot_by_id[cut.source_shot_id]
            position = (
                convert_position(source_shot.camera.transform.position)
                if source_shot.camera.transform is not None
                else _infer_camera_position(look_at, cut.framing, cut.angle)
            )
            cameras.append(
                UnityCameraCut(
                    cut_id=cut.cut_id,
                    source_shot_id=cut.source_shot_id,
                    display_name=f"CSA_CAM_{_unity_name(cut.source_shot_id)}",
                    start_frame=cut.start_frame,
                    end_frame=cut.end_frame,
                    lens_mm=cut.lens_mm,
                    position_m=position,
                    look_at_m=look_at,
                )
            )

        suffix = _unity_name(scene.id)
        sequences.append(
            UnitySceneTimeline(
                source_scene_id=scene.id,
                title=scene.title,
                asset_name=f"TL_{suffix}",
                timeline_asset_path=f"{timeline_path}/TL_{suffix}.playable",
                scene_asset_path=f"{scene_path}/SC_{suffix}.unity",
                duration_frames=semantic_scene.duration_frames,
                actors=actors,
                animation_sections=animations,
                audio_sections=audio_sections,
                cameras=cameras,
            )
        )

    return UnityExportPlan(
        project_id=project.id,
        project_name=project.name,
        fps=project.settings.fps,
        semantics=semantics,
        sequences=sequences,
        warnings=warnings,
    )
