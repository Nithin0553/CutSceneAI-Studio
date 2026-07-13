from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256

from cutsceneai_cir import Project, validate_project_model

from .models import (
    CameraCut,
    EntityKind,
    PerformanceCue,
    PlaceholderShape,
    PreviewEntity,
    PreviewManifest,
    PreviewScene,
    PreviewWarning,
)


def seconds_to_frame(seconds: float | Decimal, fps: int) -> int:
    """Convert seconds to the nearest frame with explicit half-up rounding."""

    value = seconds if isinstance(seconds, Decimal) else Decimal(str(seconds))
    return int((value * fps).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _frame_range(
    start_seconds: float, duration_seconds: float, fps: int, limit: int
) -> tuple[int, int]:
    end_seconds = Decimal(str(start_seconds)) + Decimal(str(duration_seconds))
    start_frame = min(seconds_to_frame(start_seconds, fps), limit - 1)
    end_frame = min(seconds_to_frame(end_seconds, fps), limit)
    return start_frame, max(start_frame + 1, end_frame)


def _placeholder_color(entity_id: str) -> str:
    digest = sha256(entity_id.encode("utf-8")).digest()
    channels = tuple(80 + channel % 128 for channel in digest[:3])
    return "#" + "".join(f"{channel:02X}" for channel in channels)


def compile_project(project: Project) -> PreviewManifest:
    """Compile a valid CIR project into a deterministic, engine-neutral preview manifest."""

    validate_project_model(project)
    fps = project.settings.fps
    entities: list[PreviewEntity] = []
    warnings: list[PreviewWarning] = []

    for character in project.characters:
        entities.append(
            PreviewEntity(
                id=character.id,
                name=character.name,
                kind=EntityKind.CHARACTER,
                placeholder_shape=PlaceholderShape.CAPSULE,
                placeholder_color=_placeholder_color(character.id),
                initial_transform=character.initial_transform,
            )
        )
        warnings.append(
            PreviewWarning(
                code="placeholder_character",
                entity_id=character.id,
                message=f"Character '{character.id}' uses a capsule placeholder.",
            )
        )

    for item in project.environment:
        entities.append(
            PreviewEntity(
                id=item.id,
                name=item.name,
                kind=EntityKind.ENVIRONMENT,
                asset_uri=item.asset_uri,
                placeholder_shape=PlaceholderShape.BOX,
                placeholder_color=_placeholder_color(item.id),
                initial_transform=item.initial_transform,
            )
        )
        if item.asset_uri is None:
            warnings.append(
                PreviewWarning(
                    code="placeholder_environment",
                    entity_id=item.id,
                    message=f"Environment object '{item.id}' uses a box placeholder.",
                )
            )

    scenes: list[PreviewScene] = []
    for scene in project.scenes:
        duration_frames = max(1, seconds_to_frame(scene.duration_seconds, fps))
        cues: list[PerformanceCue] = []
        for beat in scene.beats:
            for performance in beat.performances:
                start_frame, end_frame = _frame_range(
                    beat.start_seconds, beat.duration_seconds, fps, duration_frames
                )
                dialogue_start_frame = None
                if performance.dialogue is not None:
                    dialogue_start = Decimal(str(beat.start_seconds)) + Decimal(
                        str(performance.dialogue.start_offset_seconds)
                    )
                    dialogue_start_frame = seconds_to_frame(dialogue_start, fps)
                cues.append(
                    PerformanceCue(
                        beat_id=beat.id,
                        start_frame=start_frame,
                        end_frame=end_frame,
                        character_id=performance.character_id,
                        motion_prompt=performance.motion.prompt,
                        motion_style=performance.motion.style,
                        emotion=performance.facial.emotion,
                        emotion_intensity=performance.facial.intensity,
                        lip_sync=performance.facial.lip_sync,
                        dialogue=(
                            performance.dialogue.text
                            if performance.dialogue is not None
                            else None
                        ),
                        dialogue_start_frame=dialogue_start_frame,
                        look_at_id=performance.look_at_id,
                    )
                )

        cuts: list[CameraCut] = []
        for shot in scene.shots:
            start_frame, end_frame = _frame_range(
                shot.start_seconds, shot.duration_seconds, fps, duration_frames
            )
            cuts.append(
                CameraCut(
                    shot_id=shot.id,
                    beat_ids=shot.beat_ids,
                    start_frame=start_frame,
                    end_frame=end_frame,
                    purpose=shot.purpose,
                    description=shot.description,
                    subject_ids=shot.subject_ids,
                    framing=shot.camera.framing,
                    angle=shot.camera.angle,
                    movement=shot.camera.movement,
                    lens_mm=shot.camera.lens_mm,
                    target_ids=shot.camera.target_ids,
                    composition=shot.camera.composition,
                    transform=shot.camera.transform,
                )
            )
        scenes.append(
            PreviewScene(
                id=scene.id,
                title=scene.title,
                location=scene.location,
                duration_frames=duration_frames,
                performance_cues=cues,
                camera_cuts=cuts,
            )
        )

    return PreviewManifest(
        project_id=project.id,
        project_name=project.name,
        settings=project.settings,
        entities=entities,
        scenes=scenes,
        warnings=warnings,
    )
