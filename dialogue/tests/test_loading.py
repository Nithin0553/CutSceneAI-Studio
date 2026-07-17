from __future__ import annotations

import asyncio
from io import BytesIO
import json
from zipfile import ZipFile

import pytest
from cutsceneai_cir import Project
from cutsceneai_dialogue import (
    DialogueInputError,
    DialogueEngine,
    RecordedAudioInput,
    SpeechBackendResult,
    VoiceProfile,
    build_recorded_bundle,
    load_dialogue_bundle,
    plan_project,
    render_dialogue_bundle,
)

from dialogue.tests.helpers import make_wav


def _bundle_bytes(project: Project) -> bytes:
    recordings = {
        cue.cue_id: RecordedAudioInput(
            data=make_wav(duration_seconds=1.0), filename=f"{cue.cue_id}.wav"
        )
        for cue in plan_project(project).cues
    }
    return render_dialogue_bundle(build_recorded_bundle(project, recordings))


def _rewrite(
    data: bytes,
    *,
    updates: dict[str, bytes] | None = None,
    additions: dict[str, bytes] | None = None,
) -> bytes:
    updates = updates or {}
    additions = additions or {}
    source = BytesIO(data)
    output = BytesIO()
    with ZipFile(source) as existing, ZipFile(output, "w") as rewritten:
        for name in existing.namelist():
            rewritten.writestr(name, updates.get(name, existing.read(name)))
        for name, value in additions.items():
            rewritten.writestr(name, value)
    return output.getvalue()


def test_load_dialogue_bundle_verifies_and_restores_portable_contract(
    project: Project,
) -> None:
    loaded = load_dialogue_bundle(_bundle_bytes(project))

    assert loaded.project.id == "office-dialogue"
    assert len(loaded.manifest.clips) == 2
    assert set(loaded.audio_files) == {
        "audio/dialogue-scene-meeting-beat-confrontation-mina-1.wav",
        "audio/dialogue-scene-meeting-beat-confrontation-arjun-2.wav",
    }
    assert all(not clip.provenance.ai_generated for clip in loaded.manifest.clips)


@pytest.mark.parametrize("name", ["../escape.wav", "/absolute.wav", "audio\\bad.wav"])
def test_load_dialogue_bundle_rejects_unsafe_archive_paths(project: Project, name: str) -> None:
    data = _rewrite(_bundle_bytes(project), additions={name: b"unsafe"})

    with pytest.raises(DialogueInputError, match="unsafe archive path"):
        load_dialogue_bundle(data)


def test_load_dialogue_bundle_rejects_unexpected_entries(project: Project) -> None:
    data = _rewrite(_bundle_bytes(project), additions={"notes.txt": b"not declared"})

    with pytest.raises(DialogueInputError, match="unexpected: notes.txt"):
        load_dialogue_bundle(data)


def test_load_dialogue_bundle_rejects_duplicate_archive_paths(project: Project) -> None:
    data = _bundle_bytes(project)
    with pytest.warns(UserWarning, match="Duplicate name"):
        duplicate = _rewrite(data, additions={"project.cir.json": b"{}"})

    with pytest.raises(DialogueInputError, match="duplicate archive paths"):
        load_dialogue_bundle(duplicate)


def test_load_dialogue_bundle_rejects_tampered_wav(project: Project) -> None:
    data = _bundle_bytes(project)
    with ZipFile(BytesIO(data)) as archive:
        audio_path = next(name for name in archive.namelist() if name.endswith("mina-1.wav"))
        audio = bytearray(archive.read(audio_path))
    audio[-1] ^= 0x01

    tampered = _rewrite(data, updates={audio_path: bytes(audio)})

    with pytest.raises(DialogueInputError, match="metadata or timing is inconsistent"):
        load_dialogue_bundle(tampered)


def test_load_dialogue_bundle_rejects_manifest_timing_drift(project: Project) -> None:
    data = _bundle_bytes(project)
    with ZipFile(BytesIO(data)) as archive:
        manifest = json.loads(archive.read("dialogue.manifest.json"))
    manifest["clips"][0]["end_frame"] += 1
    tampered = _rewrite(
        data,
        updates={
            "dialogue.manifest.json": json.dumps(manifest).encode("utf-8"),
        },
    )

    with pytest.raises(DialogueInputError, match="metadata or timing is inconsistent"):
        load_dialogue_bundle(tampered)


def test_load_dialogue_bundle_requires_at_least_one_clip(project: Project) -> None:
    data = _bundle_bytes(project)
    with ZipFile(BytesIO(data)) as archive:
        manifest = json.loads(archive.read("dialogue.manifest.json"))
    manifest["clips"] = []
    tampered = _rewrite(
        data,
        updates={
            "dialogue.manifest.json": json.dumps(manifest).encode("utf-8"),
        },
    )

    with pytest.raises(DialogueInputError, match="contains no audio clips"):
        load_dialogue_bundle(tampered)


class _FakeSpeechBackend:
    async def synthesize(self, request: object) -> SpeechBackendResult:
        return SpeechBackendResult(
            data=make_wav(duration_seconds=0.5),
            provider="fake",
            model="speech-v1",
            voice=str(getattr(request, "voice")),
            request_id="req-1",
        )


def test_load_dialogue_bundle_verifies_ai_voice_disclosure(project: Project) -> None:
    bundle = asyncio.run(
        DialogueEngine(_FakeSpeechBackend()).synthesize_project(
            project, default_voice=VoiceProfile(voice="cedar")
        )
    )
    data = render_dialogue_bundle(bundle)

    loaded = load_dialogue_bundle(data)
    assert loaded.manifest.ai_voice_disclosure_required is True

    tampered = _rewrite(
        data,
        updates={"AI_VOICE_DISCLOSURE.txt": b"No disclosure here.\n"},
    )
    with pytest.raises(DialogueInputError, match="missing its required notice"):
        load_dialogue_bundle(tampered)


@pytest.mark.parametrize("data", [b"", b"not a zip archive"])
def test_load_dialogue_bundle_rejects_unreadable_payload(data: bytes) -> None:
    with pytest.raises(DialogueInputError):
        load_dialogue_bundle(data)
