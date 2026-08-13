from __future__ import annotations

import hashlib
import re

from cutsceneai_performance import (
    ARKIT_52_BLENDSHAPE_NAMES,
    ARKIT_52_CURVES,
    CANONICAL_HUMANOID_JOINTS,
    CANONICAL_HUMANOID_PARENTS,
    PerformanceBundle,
    decode_performance_bundle,
    render_performance_bundle,
    verify_performance_bundle_semantics,
)

from .conversion import convert_position, convert_quaternion
from .models import UnityExportPlan
from .performance_models import (
    UNITY_HUMANOID_BONES,
    UnityBodyKeyframe,
    UnityCameraKeyframe,
    UnityFacialCurveBinding,
    UnityFacialKeyframe,
    UnityGeneratedAudioTrack,
    UnityGeneratedBodyTrack,
    UnityGeneratedCameraTrack,
    UnityGeneratedFacialTrack,
    UnityJointBinding,
    UnityPerformanceMapping,
)


DEFAULT_GENERATED_PERFORMANCE_PATH = "Assets/CutSceneAI/GeneratedPerformance"


def _asset_name(value: str) -> str:
    return "".join(
        word[:1].upper() + word[1:] for word in re.findall(r"[A-Za-z0-9]+", value)
    )


def _validate_export_plan(
    bundle: PerformanceBundle,
    export_plan: UnityExportPlan,
) -> str:
    scene = verify_performance_bundle_semantics(bundle, export_plan.semantics)
    if (
        export_plan.project_id != bundle.package.project_id
        or export_plan.fps != bundle.package.fps
        or len(export_plan.sequences) != 1
    ):
        raise ValueError(
            "Unity export plan identity or frame rate does not match the performance bundle."
        )
    sequence = export_plan.sequences[0]
    if (
        sequence.source_scene_id != scene.source_scene_id
        or sequence.duration_frames != scene.duration_frames
    ):
        raise ValueError(
            "Unity export plan scene does not match performance timeline semantics."
        )
    expected_actors = sorted(
        (item.binding_id, item.source_entity_id) for item in scene.entities
    )
    actual_actors = sorted(
        (item.binding_id, item.source_entity_id) for item in sequence.actors
    )
    if actual_actors != expected_actors:
        raise ValueError(
            "Unity actor bindings do not exactly match performance timeline semantics."
        )
    expected_cameras = sorted(
        (track.source_camera_cut_id, track.start_frame, track.end_frame)
        for track in bundle.package.camera_tracks
    )
    actual_cameras = sorted(
        (item.cut_id, item.start_frame, item.end_frame) for item in sequence.cameras
    )
    if actual_cameras != expected_cameras:
        raise ValueError(
            "Unity camera cuts do not exactly match generated camera tracks."
        )
    return scene.source_scene_id


def compile_performance_bundle(
    bundle: PerformanceBundle,
    *,
    export_plan: UnityExportPlan,
    target_path: str = DEFAULT_GENERATED_PERFORMANCE_PATH,
) -> UnityPerformanceMapping:
    """Convert one verified package into a deterministic Unity 6 mapping plan."""

    if not re.fullmatch(r"Assets(?:/[A-Za-z0-9_.-]+)+", target_path):
        raise ValueError("target_path must be a normalized Unity Assets path.")
    source_scene_id = _validate_export_plan(bundle, export_plan)
    decoded = decode_performance_bundle(bundle)
    package = bundle.package
    joint_bindings = [
        UnityJointBinding(
            source_joint_name=source_name,
            target_human_bone=target_name,
            parent_index=parent_index,
        )
        for source_name, target_name, parent_index in zip(
            CANONICAL_HUMANOID_JOINTS,
            UNITY_HUMANOID_BONES,
            CANONICAL_HUMANOID_PARENTS,
            strict=True,
        )
    ]
    curve_bindings = [
        UnityFacialCurveBinding(
            source_curve_name=source_name,
            target_blendshape_name=target_name,
        )
        for source_name, target_name in zip(
            ARKIT_52_CURVES,
            ARKIT_52_BLENDSHAPE_NAMES,
            strict=True,
        )
    ]

    body_tracks = []
    for body_track in package.body_tracks:
        body_artifact = decoded.body_artifacts[body_track.semantic_id]
        body_tracks.append(
            UnityGeneratedBodyTrack(
                semantic_id=body_track.semantic_id,
                actor_binding_id=body_track.actor_binding_id,
                source_performance_cue_id=body_track.source_performance_cue_id,
                start_frame=body_track.start_frame,
                end_frame=body_track.end_frame,
                source_artifact=body_track.artifact.model_copy(deep=True),
                provenance=body_track.provenance.model_copy(deep=True),
                source_skeleton_profile="cutsceneai-humanoid-v1",
                target_animation_path=(
                    f"{target_path}/Body/AN_{_asset_name(body_track.semantic_id)}.anim"
                ),
                joint_bindings=[item.model_copy(deep=True) for item in joint_bindings],
                keyframes=[
                    UnityBodyKeyframe(
                        timeline_frame=body_track.start_frame + sample.frame_index,
                        root_position_m=convert_position(sample.root_translation),
                        joint_rotations=[
                            convert_quaternion(rotation)
                            for rotation in sample.joint_rotations
                        ],
                    )
                    for sample in body_artifact.samples
                ],
            )
        )

    facial_tracks = []
    for facial_track in package.facial_tracks:
        facial_artifact = decoded.facial_artifacts[facial_track.semantic_id]
        facial_tracks.append(
            UnityGeneratedFacialTrack(
                semantic_id=facial_track.semantic_id,
                actor_binding_id=facial_track.actor_binding_id,
                source_performance_cue_id=facial_track.source_performance_cue_id,
                source_dialogue_cue_id=facial_track.source_dialogue_cue_id,
                start_frame=facial_track.start_frame,
                end_frame=facial_track.end_frame,
                source_artifact=facial_track.artifact.model_copy(deep=True),
                provenance=facial_track.provenance.model_copy(deep=True),
                source_curve_profile="arkit-52",
                target_animation_path=(
                    f"{target_path}/Face/FA_{_asset_name(facial_track.semantic_id)}.anim"
                ),
                curve_bindings=[item.model_copy(deep=True) for item in curve_bindings],
                keyframes=[
                    UnityFacialKeyframe(
                        timeline_frame=facial_track.start_frame + sample.frame_index,
                        weights=list(sample.weights),
                    )
                    for sample in facial_artifact.samples
                ],
            )
        )

    camera_tracks = []
    for camera_track in package.camera_tracks:
        camera_artifact = decoded.camera_artifacts[camera_track.semantic_id]
        camera_tracks.append(
            UnityGeneratedCameraTrack(
                semantic_id=camera_track.semantic_id,
                camera_binding_id=camera_track.camera_binding_id,
                source_camera_cut_id=camera_track.source_camera_cut_id,
                start_frame=camera_track.start_frame,
                end_frame=camera_track.end_frame,
                source_artifact=camera_track.artifact.model_copy(deep=True),
                provenance=camera_track.provenance.model_copy(deep=True),
                sensor_width_mm=camera_artifact.sensor_width_mm,
                sensor_height_mm=camera_artifact.sensor_height_mm,
                keyframes=[
                    UnityCameraKeyframe(
                        timeline_frame=camera_track.start_frame + sample.frame_index,
                        position_m=convert_position(sample.position),
                        rotation=convert_quaternion(sample.rotation),
                        focal_length_mm=sample.focal_length_mm,
                    )
                    for sample in camera_artifact.samples
                ],
            )
        )

    audio_tracks = [
        UnityGeneratedAudioTrack(
            dialogue_cue_id=track.dialogue_cue_id,
            actor_binding_id=track.actor_binding_id,
            start_frame=track.start_frame,
            end_frame=track.end_frame,
            source_artifact=track.artifact.model_copy(deep=True),
            target_audio_path=(
                f"{target_path}/Audio/{_asset_name(track.dialogue_cue_id)}.wav"
            ),
        )
        for track in package.audio_tracks
    ]
    return UnityPerformanceMapping(
        source_bundle_sha256=hashlib.sha256(
            render_performance_bundle(bundle)
        ).hexdigest(),
        project_id=package.project_id,
        cir_fingerprint_sha256=package.cir_fingerprint_sha256,
        source_scene_id=source_scene_id,
        fps=package.fps,
        duration_frames=package.duration_frames,
        body_tracks=body_tracks,
        facial_tracks=facial_tracks,
        camera_tracks=camera_tracks,
        audio_tracks=audio_tracks,
    )
