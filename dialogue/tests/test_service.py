from __future__ import annotations

import asyncio
from dataclasses import replace
from io import BytesIO
import json
from zipfile import ZipFile

import pytest
from cutsceneai_cir import Project
from cutsceneai_dialogue import (
    DialogueEngine,
    DialogueInputError,
    DialogueOutputError,
    RecordedAudioInput,
    SpeechBackendResult,
    VoiceProfile,
    build_recorded_bundle,
    plan_project,
    render_dialogue_bundle,
)

from dialogue.tests.helpers import make_wav


def recordings(project: Project, *, duration_seconds: float = 1.0) -> dict[str, RecordedAudioInput]:
    return {
        cue.cue_id: RecordedAudioInput(
            data=make_wav(duration_seconds=duration_seconds),
            filename=f"../unsafe/{cue.character_id}.wav",
        )
        for cue in plan_project(project).cues
    }


def test_recorded_bundle_updates_project_and_preserves_provenance(project: Project) -> None:
    bundle = build_recorded_bundle(project, recordings(project))

    assert len(bundle.manifest.clips) == 2
    assert bundle.manifest.ai_voice_disclosure_required is False
    assert bundle.manifest.clips[0].provenance.source.value == "recorded"
    assert bundle.manifest.clips[0].provenance.original_filename == "mina.wav"
    assert bundle.manifest.clips[0].start_frame == 120
    assert bundle.manifest.clips[0].end_frame == 144
    assert bundle.manifest.clips[0].fits_within_beat is True
    updated_dialogue = bundle.project.scenes[0].beats[1].performances[0].dialogue
    original_dialogue = project.scenes[0].beats[1].performances[0].dialogue
    assert updated_dialogue is not None
    assert original_dialogue is not None
    assert updated_dialogue.audio_uri == (
        "cutsceneai://dialogue/office-dialogue/dialogue-scene-meeting-beat-confrontation-mina-1.wav"
    )
    assert original_dialogue.audio_uri is None


def test_recorded_bundle_is_byte_for_byte_deterministic(project: Project) -> None:
    bundle = build_recorded_bundle(project, recordings(project))

    first = render_dialogue_bundle(bundle)
    second = render_dialogue_bundle(bundle)

    assert first == second
    with ZipFile(BytesIO(first)) as archive:
        assert archive.namelist() == [
            "project.cir.json",
            "dialogue.manifest.json",
            "audio/dialogue-scene-meeting-beat-confrontation-arjun-2.wav",
            "audio/dialogue-scene-meeting-beat-confrontation-mina-1.wav",
        ]
        manifest = json.loads(archive.read("dialogue.manifest.json"))
        assert manifest["project_id"] == "office-dialogue"


def test_bundle_renderer_requires_exact_manifest_audio_paths(project: Project) -> None:
    bundle = build_recorded_bundle(project, recordings(project))
    with pytest.raises(DialogueOutputError, match="exactly match"):
        render_dialogue_bundle(replace(bundle, audio_files={"../unsafe.wav": make_wav()}))

    duplicate = bundle.manifest.model_copy(deep=True)
    duplicate.clips.append(duplicate.clips[0])
    with pytest.raises(DialogueOutputError, match="duplicate audio paths"):
        render_dialogue_bundle(replace(bundle, manifest=duplicate))


def test_recorded_bundle_reports_audio_overrun(project: Project) -> None:
    bundle = build_recorded_bundle(project, recordings(project, duration_seconds=10.0))

    assert [warning.code for warning in bundle.manifest.warnings] == [
        "audio_exceeds_beat",
        "audio_exceeds_beat",
    ]
    assert bundle.manifest.clips[0].fits_within_beat is False


def test_end_frame_rounds_up_to_preserve_the_complete_wave(project: Project) -> None:
    bundle = build_recorded_bundle(project, recordings(project, duration_seconds=1.02))
    assert bundle.manifest.clips[0].end_seconds == 6.02
    assert bundle.manifest.clips[0].end_frame == 145


@pytest.mark.parametrize(
    ("transform", "message"),
    [
        (
            lambda values: {
                key: value for index, (key, value) in enumerate(values.items()) if index
            },
            "missing recordings",
        ),
        (
            lambda values: {
                **values,
                "dialogue-unknown-beat-character-1": next(iter(values.values())),
            },
            "unknown recordings",
        ),
    ],
)
def test_recorded_bundle_requires_exact_cue_mapping(
    project: Project, transform: object, message: str
) -> None:
    values = recordings(project)
    mapped = transform(values)  # type: ignore[operator]
    with pytest.raises(DialogueInputError, match=message):
        build_recorded_bundle(project, mapped)


def test_render_requires_dialogue_and_explicit_replacement(project: Project) -> None:
    no_dialogue = project.model_copy(deep=True)
    for beat in no_dialogue.scenes[0].beats:
        for performance in beat.performances:
            performance.dialogue = None
    with pytest.raises(DialogueInputError, match="contains no dialogue"):
        build_recorded_bundle(no_dialogue, {})

    with_audio = project.model_copy(deep=True)
    existing = with_audio.scenes[0].beats[1].performances[0].dialogue
    assert existing is not None
    existing.audio_uri = "/Game/Existing.Existing"
    with pytest.raises(DialogueInputError, match="replace_existing=True"):
        build_recorded_bundle(with_audio, recordings(with_audio))
    replaced = build_recorded_bundle(with_audio, recordings(with_audio), replace_existing=True)
    assert replaced.manifest.clips[0].uri.startswith("cutsceneai://")


class FakeSpeechBackend:
    def __init__(self, data: bytes | None = None, *, provider: str = "fake") -> None:
        self.data = data or make_wav(duration_seconds=0.5)
        self.provider = provider
        self.requests: list[object] = []

    async def synthesize(self, request: object) -> SpeechBackendResult:
        self.requests.append(request)
        voice = getattr(request, "voice")
        return SpeechBackendResult(
            data=self.data,
            provider=self.provider,
            model="speech-v1",
            voice=voice,
            request_id="req-1",
        )


def test_tts_engine_uses_per_character_voices_and_disclosure(project: Project) -> None:
    backend = FakeSpeechBackend()
    bundle = asyncio.run(
        DialogueEngine(backend).synthesize_project(
            project,
            default_voice=VoiceProfile(voice="cedar"),
            voices={"mina": VoiceProfile(voice="marin", instructions="Firm and restrained.")},
        )
    )

    assert [getattr(request, "voice") for request in backend.requests] == ["marin", "cedar"]
    assert bundle.manifest.ai_voice_disclosure_required is True
    assert bundle.manifest.clips[0].provenance.model == "speech-v1"
    assert bundle.manifest.clips[0].provenance.instructions == "Firm and restrained."
    with ZipFile(BytesIO(render_dialogue_bundle(bundle))) as archive:
        disclosure = archive.read("AI_VOICE_DISCLOSURE.txt").decode()
        assert "AI-generated" in disclosure


def test_tts_engine_rejects_unknown_voice_profile(project: Project) -> None:
    with pytest.raises(DialogueInputError, match="unknown characters"):
        asyncio.run(
            DialogueEngine(FakeSpeechBackend()).synthesize_project(
                project,
                default_voice=VoiceProfile(voice="cedar"),
                voices={"ghost": VoiceProfile(voice="marin")},
            )
        )


def test_tts_engine_rejects_oversized_text(project: Project) -> None:
    dialogue = project.scenes[0].beats[1].performances[0].dialogue
    assert dialogue is not None
    dialogue.text = "x" * 4097
    with pytest.raises(DialogueInputError, match="4096-character"):
        asyncio.run(
            DialogueEngine(FakeSpeechBackend()).synthesize_project(
                project, default_voice=VoiceProfile(voice="cedar")
            )
        )


def test_tts_engine_rejects_invalid_provider_audio(project: Project) -> None:
    with pytest.raises(DialogueOutputError, match="invalid WAV"):
        asyncio.run(
            DialogueEngine(FakeSpeechBackend(b"not-wave")).synthesize_project(
                project, default_voice=VoiceProfile(voice="cedar")
            )
        )


def test_tts_engine_rejects_incomplete_provider_provenance(project: Project) -> None:
    with pytest.raises(DialogueOutputError, match="incomplete provenance"):
        asyncio.run(
            DialogueEngine(FakeSpeechBackend(provider=" ")).synthesize_project(
                project, default_voice=VoiceProfile(voice="cedar")
            )
        )
