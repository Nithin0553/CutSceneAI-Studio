from __future__ import annotations

from cutsceneai_parity import SemanticScene, TimelineSemantics

from .bundle import PerformanceBundle, verify_performance_bundle
from .errors import PerformanceOutputError


def verify_performance_bundle_semantics(
    bundle: PerformanceBundle,
    semantics: TimelineSemantics,
) -> SemanticScene:
    """Bind one verified v0.1 bundle to its exact engine-neutral timeline semantics."""

    verify_performance_bundle(bundle)
    if len(semantics.scenes) != 1:
        raise PerformanceOutputError(
            "Performance bundle v0.1 requires exactly one semantic scene."
        )
    scene = semantics.scenes[0]
    package = bundle.package
    identity = (
        semantics.cir_schema_version,
        semantics.project_id,
        semantics.cir_fingerprint_sha256,
        semantics.fps,
        scene.duration_frames,
    )
    package_identity = (
        package.cir_schema_version,
        package.project_id,
        package.cir_fingerprint_sha256,
        package.fps,
        package.duration_frames,
    )
    if identity != package_identity:
        raise PerformanceOutputError(
            "Performance bundle identity or timeline does not match timeline semantics."
        )

    expected_body = sorted(
        (cue.cue_id, cue.actor_binding_id, cue.start_frame, cue.end_frame)
        for cue in scene.performance_cues
    )
    actual_body = sorted(
        (
            track.source_performance_cue_id,
            track.actor_binding_id,
            track.start_frame,
            track.end_frame,
        )
        for track in package.body_tracks
    )
    if actual_body != expected_body:
        raise PerformanceOutputError(
            "Performance body tracks do not exactly match timeline semantics."
        )

    dialogue_ids = {cue.cue_id for cue in scene.dialogue_cues}
    expected_facial = sorted(
        (
            cue.cue_id,
            cue.actor_binding_id,
            cue.start_frame,
            cue.end_frame,
            (
                dialogue_id
                if (dialogue_id := cue.cue_id.replace("performance:", "dialogue:", 1))
                in dialogue_ids
                else None
            ),
        )
        for cue in scene.performance_cues
    )
    actual_facial = sorted(
        (
            track.source_performance_cue_id,
            track.actor_binding_id,
            track.start_frame,
            track.end_frame,
            track.source_dialogue_cue_id,
        )
        for track in package.facial_tracks
    )
    if actual_facial != expected_facial:
        raise PerformanceOutputError(
            "Performance facial tracks do not exactly match timeline semantics."
        )

    expected_camera = sorted(
        (
            cut.cut_id,
            f"camera:{cut.source_shot_id}",
            cut.start_frame,
            cut.end_frame,
        )
        for cut in scene.camera_cuts
    )
    actual_camera = sorted(
        (
            track.source_camera_cut_id,
            track.camera_binding_id,
            track.start_frame,
            track.end_frame,
        )
        for track in package.camera_tracks
    )
    if actual_camera != expected_camera:
        raise PerformanceOutputError(
            "Performance camera tracks do not exactly match timeline semantics."
        )

    expected_audio = sorted(
        (cue.cue_id, cue.actor_binding_id, cue.start_frame)
        for cue in scene.dialogue_cues
    )
    actual_audio = sorted(
        (track.dialogue_cue_id, track.actor_binding_id, track.start_frame)
        for track in package.audio_tracks
    )
    if actual_audio != expected_audio:
        raise PerformanceOutputError(
            "Performance audio tracks do not exactly match timeline semantics."
        )
    window_end_by_id = {cue.cue_id: cue.window_end_frame for cue in scene.dialogue_cues}
    if any(
        track.end_frame > window_end_by_id[track.dialogue_cue_id]
        for track in package.audio_tracks
    ):
        raise PerformanceOutputError(
            "Performance audio track exceeds its semantic dialogue window."
        )
    return scene.model_copy(deep=True)
