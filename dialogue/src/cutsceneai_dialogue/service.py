from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
from pathlib import PurePosixPath
from typing import Protocol

from cutsceneai_cir import Project

from .audio import inspect_wav
from .errors import DialogueAudioError, DialogueInputError, DialogueOutputError
from .models import (
    AudioProvenance,
    DialogueClip,
    DialogueCue,
    DialogueManifest,
    DialogueRenderPlan,
    DialogueSource,
    DialogueWarning,
    SpeechSynthesisRequest,
    VoiceProfile,
    WavMetadata,
)
from .planning import plan_project


@dataclass(frozen=True, slots=True)
class RecordedAudioInput:
    data: bytes
    filename: str


@dataclass(frozen=True, slots=True)
class SpeechBackendResult:
    data: bytes
    provider: str
    model: str
    voice: str
    request_id: str | None = None


class SpeechBackend(Protocol):
    async def synthesize(self, request: SpeechSynthesisRequest) -> SpeechBackendResult: ...


@dataclass(frozen=True, slots=True)
class DialogueBundle:
    project: Project
    manifest: DialogueManifest
    audio_files: Mapping[str, bytes]


def _portable_uri(project_id: str, filename: str) -> str:
    return f"cutsceneai://dialogue/{project_id}/{filename}"


def _safe_filename(filename: str) -> str:
    return PurePosixPath(filename.replace("\\", "/")).name


def _set_audio_uri(project: Project, scene_id: str, beat_id: str, index: int, uri: str) -> None:
    scene = next(scene for scene in project.scenes if scene.id == scene_id)
    beat = next(beat for beat in scene.beats if beat.id == beat_id)
    dialogue = beat.performances[index].dialogue
    if dialogue is None:
        raise DialogueInputError("Dialogue cue no longer matches the supplied CIR project.")
    dialogue.audio_uri = uri


def _clip(
    *,
    cue: DialogueCue,
    metadata: WavMetadata,
    provenance: AudioProvenance,
    uri: str,
    relative_path: str,
    fps: int,
) -> tuple[DialogueClip, DialogueWarning | None]:
    end = Decimal(str(cue.start_seconds)) + Decimal(str(metadata.duration_seconds))
    end_seconds = float(end)
    end_frame = max(
        cue.start_frame + 1,
        int((end * fps).quantize(Decimal("1"), rounding=ROUND_CEILING)),
    )
    fits = end <= Decimal(str(cue.beat_end_seconds)) + Decimal("1e-9")
    warning = None
    if not fits:
        warning = DialogueWarning(
            code="audio_exceeds_beat",
            cue_id=cue.cue_id,
            message=(f"Audio ends at {end_seconds:g}s, after beat end {cue.beat_end_seconds:g}s."),
        )
    return (
        DialogueClip(
            cue_id=cue.cue_id,
            scene_id=cue.scene_id,
            beat_id=cue.beat_id,
            character_id=cue.character_id,
            text=cue.text,
            language=cue.language,
            uri=uri,
            relative_path=relative_path,
            start_seconds=cue.start_seconds,
            end_seconds=end_seconds,
            start_frame=cue.start_frame,
            end_frame=end_frame,
            beat_end_seconds=cue.beat_end_seconds,
            fits_within_beat=fits,
            wav=metadata,
            provenance=provenance,
        ),
        warning,
    )


def _validate_plan_for_render(project: Project, *, replace_existing: bool) -> DialogueRenderPlan:
    plan = plan_project(project)
    if not plan.cues:
        raise DialogueInputError("The CIR project contains no dialogue to render.")
    existing = [cue.cue_id for cue in plan.cues if cue.existing_audio_uri is not None]
    if existing and not replace_existing:
        raise DialogueInputError(
            "Dialogue already has audio URIs; pass replace_existing=True to replace: "
            + ", ".join(existing)
        )
    return plan


def build_recorded_bundle(
    project: Project,
    recordings: Mapping[str, RecordedAudioInput],
    *,
    replace_existing: bool = False,
) -> DialogueBundle:
    """Bind user-provided WAV recordings to every planned dialogue cue."""

    plan = _validate_plan_for_render(project, replace_existing=replace_existing)
    expected = {cue.cue_id for cue in plan.cues}
    supplied = set(recordings)
    missing = sorted(expected - supplied)
    unknown = sorted(supplied - expected)
    if missing or unknown:
        details: list[str] = []
        if missing:
            details.append("missing recordings: " + ", ".join(missing))
        if unknown:
            details.append("unknown recordings: " + ", ".join(unknown))
        raise DialogueInputError("; ".join(details))

    updated = project.model_copy(deep=True)
    clips: list[DialogueClip] = []
    warnings = list(plan.warnings)
    files: dict[str, bytes] = {}
    for cue in plan.cues:
        recording = recordings[cue.cue_id]
        metadata = inspect_wav(recording.data)
        relative_path = f"audio/{cue.output_filename}"
        uri = _portable_uri(project.id, cue.output_filename)
        provenance = AudioProvenance(
            source=DialogueSource.RECORDED,
            ai_generated=False,
            original_filename=_safe_filename(recording.filename),
        )
        clip, warning = _clip(
            cue=cue,
            metadata=metadata,
            provenance=provenance,
            uri=uri,
            relative_path=relative_path,
            fps=plan.fps,
        )
        clips.append(clip)
        if warning is not None:
            warnings.append(warning)
        files[relative_path] = recording.data
        _set_audio_uri(updated, cue.scene_id, cue.beat_id, cue.performance_index, uri)

    manifest = DialogueManifest(
        project_id=project.id,
        fps=plan.fps,
        ai_voice_disclosure_required=False,
        clips=clips,
        warnings=warnings,
    )
    return DialogueBundle(project=updated, manifest=manifest, audio_files=files)


class DialogueEngine:
    def __init__(self, backend: SpeechBackend) -> None:
        self._backend = backend

    async def synthesize_project(
        self,
        project: Project,
        *,
        default_voice: VoiceProfile,
        voices: Mapping[str, VoiceProfile] | None = None,
        replace_existing: bool = False,
    ) -> DialogueBundle:
        """Generate WAV audio for every dialogue cue and return a portable bundle."""

        plan = _validate_plan_for_render(project, replace_existing=replace_existing)
        voice_map = dict(voices or {})
        character_ids = {character.id for character in project.characters}
        unknown_profiles = sorted(set(voice_map) - character_ids)
        if unknown_profiles:
            raise DialogueInputError(
                "Voice profiles reference unknown characters: " + ", ".join(unknown_profiles)
            )

        updated = project.model_copy(deep=True)
        clips: list[DialogueClip] = []
        warnings = list(plan.warnings)
        files: dict[str, bytes] = {}
        for cue in plan.cues:
            profile = voice_map.get(cue.character_id, default_voice)
            if len(cue.text) > 4096:
                raise DialogueInputError(
                    f"Dialogue cue '{cue.cue_id}' exceeds the 4096-character TTS limit."
                )
            request = SpeechSynthesisRequest(
                cue_id=cue.cue_id,
                text=cue.text,
                language=cue.language,
                voice=profile.voice,
                instructions=profile.instructions,
                speed=profile.speed,
            )
            result = await self._backend.synthesize(request)
            if not all(value.strip() for value in (result.provider, result.model, result.voice)):
                raise DialogueOutputError(
                    f"Speech provider returned incomplete provenance for '{cue.cue_id}'."
                )
            try:
                metadata = inspect_wav(result.data)
            except DialogueAudioError as exc:
                raise DialogueOutputError(
                    f"Speech provider returned invalid WAV audio for '{cue.cue_id}': {exc}"
                ) from exc

            relative_path = f"audio/{cue.output_filename}"
            uri = _portable_uri(project.id, cue.output_filename)
            provenance = AudioProvenance(
                source=DialogueSource.TTS,
                ai_generated=True,
                provider=result.provider,
                model=result.model,
                voice=result.voice,
                instructions=profile.instructions,
                speed=profile.speed,
                request_id=result.request_id,
            )
            clip, warning = _clip(
                cue=cue,
                metadata=metadata,
                provenance=provenance,
                uri=uri,
                relative_path=relative_path,
                fps=plan.fps,
            )
            clips.append(clip)
            if warning is not None:
                warnings.append(warning)
            files[relative_path] = result.data
            _set_audio_uri(updated, cue.scene_id, cue.beat_id, cue.performance_index, uri)

        manifest = DialogueManifest(
            project_id=project.id,
            fps=plan.fps,
            ai_voice_disclosure_required=True,
            clips=clips,
            warnings=warnings,
        )
        return DialogueBundle(project=updated, manifest=manifest, audio_files=files)
