from decimal import Decimal, ROUND_HALF_UP

from cutsceneai_cir import Project, validate_project_model

from .models import DialogueCue, DialogueRenderPlan, DialogueWarning


def seconds_to_frame(seconds: float | Decimal, fps: int) -> int:
    """Convert seconds to a frame using explicit half-up rounding."""

    value = seconds if isinstance(seconds, Decimal) else Decimal(str(seconds))
    return int((value * fps).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def plan_project(project: Project) -> DialogueRenderPlan:
    """Collect every CIR dialogue line into a stable, provider-neutral render plan."""

    validate_project_model(project)
    cues: list[DialogueCue] = []
    warnings: list[DialogueWarning] = []

    for scene in project.scenes:
        for beat in scene.beats:
            beat_start = Decimal(str(beat.start_seconds))
            beat_end = beat_start + Decimal(str(beat.duration_seconds))
            for performance_index, performance in enumerate(beat.performances):
                dialogue = performance.dialogue
                if dialogue is None:
                    continue
                start = beat_start + Decimal(str(dialogue.start_offset_seconds))
                cue_id = (
                    f"dialogue-{scene.id}-{beat.id}-{performance.character_id}-"
                    f"{performance_index + 1}"
                )
                cues.append(
                    DialogueCue(
                        cue_id=cue_id,
                        scene_id=scene.id,
                        beat_id=beat.id,
                        character_id=performance.character_id,
                        performance_index=performance_index,
                        text=dialogue.text,
                        language=dialogue.language,
                        start_seconds=float(start),
                        start_frame=seconds_to_frame(start, project.settings.fps),
                        beat_end_seconds=float(beat_end),
                        output_filename=f"{cue_id}.wav",
                        existing_audio_uri=dialogue.audio_uri,
                    )
                )
                if start >= beat_end:
                    warnings.append(
                        DialogueWarning(
                            code="dialogue_start_out_of_range",
                            cue_id=cue_id,
                            message=(
                                f"Dialogue starts at {float(start):g}s, at or after beat "
                                f"end {float(beat_end):g}s."
                            ),
                        )
                    )
                if dialogue.audio_uri is not None:
                    warnings.append(
                        DialogueWarning(
                            code="existing_audio_uri",
                            cue_id=cue_id,
                            message=(
                                "Dialogue already has an audio URI; synthesis requires an explicit "
                                "replace-existing choice."
                            ),
                        )
                    )

    return DialogueRenderPlan(
        project_id=project.id,
        fps=project.settings.fps,
        cues=cues,
        warnings=warnings,
    )
