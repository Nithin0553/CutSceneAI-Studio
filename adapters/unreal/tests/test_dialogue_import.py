from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path
import sys
from types import ModuleType
import wave
from zipfile import ZipFile

import pytest
from cutsceneai_cir import Project
from cutsceneai_dialogue import (
    DialogueEngine,
    DialogueInputError,
    RecordedAudioInput,
    SpeechBackendResult,
    VoiceProfile,
    build_recorded_bundle,
    plan_project,
)
from cutsceneai_unreal import (
    compile_dialogue_bundle,
    render_unreal_dialogue_import_package,
)


def _wav(*, duration_seconds: float = 1.0, sample_rate: int = 8_000) -> bytes:
    output = BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\0" * round(duration_seconds * sample_rate) * 2)
    return output.getvalue()


def _package(project: Project, *, duration_seconds: float = 1.0):
    recordings = {
        cue.cue_id: RecordedAudioInput(
            data=_wav(duration_seconds=duration_seconds),
            filename=f"{cue.character_id}.wav",
        )
        for cue in plan_project(project).cues
    }
    bundle = build_recorded_bundle(project, recordings)
    return compile_dialogue_bundle(bundle)


def test_compile_dialogue_bundle_maps_portable_wavs_and_exact_timing(
    cir_project: Project,
) -> None:
    package = _package(cir_project)
    plan = package.plan

    assert plan.adapter_version == "0.6.0"
    assert [item.asset_name for item in plan.audio_imports] == [
        "SW_DialogueSceneMeetingBeatConfrontationMina1",
        "SW_DialogueSceneMeetingBeatConfrontationArjun2",
    ]
    assert [item.destination_path for item in plan.audio_imports] == [
        "/Game/CutSceneAI/Audio",
        "/Game/CutSceneAI/Audio",
    ]
    assert all(
        item.source_uri.startswith("cutsceneai://") for item in plan.audio_imports
    )

    sections = plan.sequences[0].audio_sections
    assert [(item.start_frame, item.end_frame) for item in sections] == [
        (120, 144),
        (216, 240),
    ]
    assert [item.source_cue_id for item in sections] == [
        "dialogue-scene-meeting-beat-confrontation-mina-1",
        "dialogue-scene-meeting-beat-confrontation-arjun-2",
    ]
    assert all(item.timing_source == "dialogue_manifest" for item in sections)
    assert all(
        item.asset_path.startswith("/Game/CutSceneAI/Audio/SW_") for item in sections
    )

    portable_dialogue = (
        package.dialogue_bundle.project.scenes[0].beats[1].performances[0].dialogue
    )
    assert portable_dialogue is not None
    assert portable_dialogue.audio_uri is not None
    assert portable_dialogue.audio_uri.startswith("cutsceneai://")


def test_compile_dialogue_bundle_rejects_audio_beyond_sequence(
    cir_project: Project,
) -> None:
    with pytest.raises(DialogueInputError, match="beyond sequence"):
        _package(cir_project, duration_seconds=20.0)


def test_unreal_dialogue_package_is_deterministic_and_self_contained(
    cir_project: Project,
) -> None:
    package = _package(cir_project)

    first = render_unreal_dialogue_import_package(package)
    second = render_unreal_dialogue_import_package(package)

    assert first == second
    with ZipFile(BytesIO(first)) as archive:
        assert archive.namelist() == [
            "cutsceneai-unreal-import.py",
            "unreal.plan.json",
            "project.cir.json",
            "dialogue.manifest.json",
            "audio/dialogue-scene-meeting-beat-confrontation-arjun-2.wav",
            "audio/dialogue-scene-meeting-beat-confrontation-mina-1.wav",
        ]
        script = archive.read("cutsceneai-unreal-import.py").decode("utf-8")
        compile(script, "cutsceneai-unreal-import.py", "exec")
        assert "unreal.AssetImportTask" in script
        assert 'task.set_editor_property("replace_existing", False)' in script
        assert "Bundled WAV checksum does not match" in script


class _FakeSpeechBackend:
    async def synthesize(self, request: object) -> SpeechBackendResult:
        return SpeechBackendResult(
            data=_wav(duration_seconds=0.5),
            provider="fake",
            model="speech-v1",
            voice=str(getattr(request, "voice")),
            request_id="req-1",
        )


def test_unreal_dialogue_package_retains_ai_disclosure(cir_project: Project) -> None:
    dialogue_bundle = asyncio.run(
        DialogueEngine(_FakeSpeechBackend()).synthesize_project(
            cir_project, default_voice=VoiceProfile(voice="cedar")
        )
    )
    package = compile_dialogue_bundle(dialogue_bundle)

    with ZipFile(BytesIO(render_unreal_dialogue_import_package(package))) as archive:
        disclosure = archive.read("AI_VOICE_DISCLOSURE.txt").decode("utf-8")
        assert "AI-generated" in disclosure


def test_generated_importer_preflights_and_imports_verified_wavs(
    cir_project: Project, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package_data = render_unreal_dialogue_import_package(_package(cir_project))
    with ZipFile(BytesIO(package_data)) as archive:
        archive.extractall(tmp_path)
    script_path = tmp_path / "cutsceneai-unreal-import.py"
    script = script_path.read_text(encoding="utf-8")

    class SoundBase:
        pass

    class SoundWave(SoundBase):
        pass

    class AssetImportTask:
        def __init__(self) -> None:
            self.properties: dict[str, object] = {}

        def set_editor_property(self, name: str, value: object) -> None:
            self.properties[name] = value

    imported_tasks: list[AssetImportTask] = []

    class AssetTools:
        @staticmethod
        def import_asset_tasks(tasks: list[AssetImportTask]) -> None:
            imported_tasks.extend(tasks)

    class AssetToolsHelpers:
        @staticmethod
        def get_asset_tools() -> AssetTools:
            return AssetTools()

    class EditorAssetLibrary:
        conflicts: set[str] = set()

        @classmethod
        def does_asset_exist(cls, path: str) -> bool:
            return path in cls.conflicts

        @staticmethod
        def load_asset(path: str) -> SoundWave:
            assert path.startswith("/Game/CutSceneAI/Audio/SW_")
            return SoundWave()

    messages: list[str] = []
    unreal = ModuleType("unreal")
    unreal.AssetImportTask = AssetImportTask
    unreal.AssetToolsHelpers = AssetToolsHelpers
    unreal.EditorAssetLibrary = EditorAssetLibrary
    unreal.SoundBase = SoundBase
    unreal.log = messages.append
    monkeypatch.setitem(sys.modules, "unreal", unreal)

    namespace = {
        "__file__": str(script_path),
        "__name__": "cutsceneai_generated_importer",
    }
    exec(script, namespace)
    namespace["_preflight_import"]()
    imported = namespace["_import_audio_assets"]()

    assert len(imported_tasks) == 2
    assert len(imported) == 2
    assert all(task.properties["automated"] is True for task in imported_tasks)
    assert all(task.properties["replace_existing"] is False for task in imported_tasks)
    assert all(task.properties["save"] is True for task in imported_tasks)
    assert len(messages) == 2

    first_target = namespace["PLAN"]["audio_imports"][0]["asset_path"]
    EditorAssetLibrary.conflicts.add(first_target)
    with pytest.raises(RuntimeError, match="Refusing to replace existing assets"):
        namespace["_preflight_import"]()


def test_generated_importer_detects_wav_tampering(
    cir_project: Project, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package_data = render_unreal_dialogue_import_package(_package(cir_project))
    with ZipFile(BytesIO(package_data)) as archive:
        archive.extractall(tmp_path)
    script_path = tmp_path / "cutsceneai-unreal-import.py"
    script = script_path.read_text(encoding="utf-8")

    class EditorAssetLibrary:
        @staticmethod
        def does_asset_exist(path: str) -> bool:
            return False

    unreal = ModuleType("unreal")
    unreal.EditorAssetLibrary = EditorAssetLibrary
    monkeypatch.setitem(sys.modules, "unreal", unreal)
    namespace = {
        "__file__": str(script_path),
        "__name__": "cutsceneai_generated_importer",
    }
    exec(script, namespace)

    source = tmp_path / namespace["PLAN"]["audio_imports"][0]["source_relative_path"]
    source.write_bytes(source.read_bytes() + b"tampered")

    with pytest.raises(RuntimeError, match="checksum does not match"):
        namespace["_preflight_import"]()
