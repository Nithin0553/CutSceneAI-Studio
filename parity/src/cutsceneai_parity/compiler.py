from __future__ import annotations

import hashlib
import json

from cutsceneai_cir import PerformancePlan, Project, validate_project_model
from cutsceneai_preview import compile_project as compile_preview

from .models import (
    EntityKind,
    SemanticCameraCut,
    SemanticDialogueCue,
    SemanticEntity,
    SemanticPerformanceCue,
    SemanticScene,
    TimelineSemantics,
)


def _canonical_json_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def cir_fingerprint(project: Project) -> str:
    """Return the canonical SHA-256 identity of a validated CIR project."""

    validate_project_model(project)
    return _canonical_json_sha256(project.model_dump(mode="json"))


def _performance_id(
    scene_id: str, beat_id: str, performance: PerformancePlan, ordinal: int
) -> str:
    return f"performance:{scene_id}:{beat_id}:{performance.character_id}:{ordinal:02d}"


def _dialogue_id(performance_id: str) -> str:
    return performance_id.replace("performance:", "dialogue:", 1)


def _motion_intent_sha256(performance: PerformancePlan) -> str:
    return _canonical_json_sha256(
        {
            "motion": performance.motion.model_dump(mode="json"),
            "facial": performance.facial.model_dump(mode="json"),
            "look_at_id": performance.look_at_id,
        }
    )


def compile_semantics(project: Project) -> TimelineSemantics:
    """Compile validated CIR into the engine-neutral parity contract."""

    validate_project_model(project)
    preview = compile_preview(project)
    binding_by_entity = {entity.id: f"actor:{entity.id}" for entity in preview.entities}
    entity_kind = {
        entity.id: (
            EntityKind.CHARACTER
            if entity.kind.value == "character"
            else EntityKind.ENVIRONMENT
        )
        for entity in preview.entities
    }
    preview_scene_by_id = {scene.id: scene for scene in preview.scenes}
    scenes: list[SemanticScene] = []

    for scene in project.scenes:
        preview_scene = preview_scene_by_id[scene.id]
        source_performances = [
            (beat.id, ordinal, performance)
            for beat in scene.beats
            for ordinal, performance in enumerate(beat.performances, start=1)
        ]
        if len(source_performances) != len(preview_scene.performance_cues):
            raise RuntimeError("Preview and CIR performance timelines diverged.")

        performances: list[SemanticPerformanceCue] = []
        dialogues: list[SemanticDialogueCue] = []
        for preview_cue, (beat_id, ordinal, performance) in zip(
            preview_scene.performance_cues, source_performances, strict=True
        ):
            cue_id = _performance_id(scene.id, beat_id, performance, ordinal)
            actor_binding_id = binding_by_entity[performance.character_id]
            performances.append(
                SemanticPerformanceCue(
                    cue_id=cue_id,
                    source_beat_id=beat_id,
                    actor_binding_id=actor_binding_id,
                    start_frame=preview_cue.start_frame,
                    end_frame=preview_cue.end_frame,
                    motion_intent_sha256=_motion_intent_sha256(performance),
                    look_at_binding_id=(
                        binding_by_entity[performance.look_at_id]
                        if performance.look_at_id is not None
                        else None
                    ),
                )
            )
            if performance.dialogue is not None:
                if preview_cue.dialogue_start_frame is None:
                    raise RuntimeError("Preview omitted a CIR dialogue start frame.")
                dialogues.append(
                    SemanticDialogueCue(
                        cue_id=_dialogue_id(cue_id),
                        source_beat_id=beat_id,
                        actor_binding_id=actor_binding_id,
                        start_frame=preview_cue.dialogue_start_frame,
                        window_end_frame=preview_cue.end_frame,
                        text_sha256=hashlib.sha256(
                            performance.dialogue.text.encode("utf-8")
                        ).hexdigest(),
                        language=performance.dialogue.language,
                    )
                )

        camera_cuts = [
            SemanticCameraCut(
                cut_id=f"camera:{scene.id}:{cut.shot_id}",
                source_shot_id=cut.shot_id,
                source_beat_ids=cut.beat_ids,
                start_frame=cut.start_frame,
                end_frame=cut.end_frame,
                purpose=cut.purpose,
                framing=cut.framing,
                angle=cut.angle,
                movement=cut.movement,
                lens_mm=cut.lens_mm,
                subject_binding_ids=[
                    binding_by_entity[entity_id] for entity_id in cut.subject_ids
                ],
                target_binding_ids=[
                    binding_by_entity[entity_id]
                    for entity_id in (cut.target_ids or cut.subject_ids)
                ],
            )
            for cut in preview_scene.camera_cuts
        ]

        scenes.append(
            SemanticScene(
                source_scene_id=scene.id,
                duration_frames=preview_scene.duration_frames,
                entities=[
                    SemanticEntity(
                        binding_id=binding_by_entity[entity.id],
                        source_entity_id=entity.id,
                        kind=entity_kind[entity.id],
                    )
                    for entity in preview.entities
                ],
                performance_cues=performances,
                dialogue_cues=dialogues,
                camera_cuts=camera_cuts,
            )
        )

    return TimelineSemantics(
        cir_fingerprint_sha256=cir_fingerprint(project),
        project_id=project.id,
        fps=project.settings.fps,
        scenes=scenes,
    )
