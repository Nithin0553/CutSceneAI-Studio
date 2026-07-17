from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import json
import re
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from cutsceneai_dialogue import (
    AI_VOICE_DISCLOSURE_TEXT,
    DialogueBundle,
    DialogueClip,
    DialogueInputError,
    DialogueOutputError,
    load_dialogue_bundle,
    plan_project,
    render_dialogue_bundle,
    render_dialogue_manifest,
)

from .compiler import DEFAULT_PACKAGE_PATH, compile_project
from .models import (
    UnrealAudioImport,
    UnrealAudioSection,
    UnrealExportPlan,
    UnrealExportWarning,
)
from .rendering import render_unreal_import_script
from .serialization import render_unreal_plan


DEFAULT_AUDIO_PACKAGE_PATH = "/Game/CutSceneAI/Audio"
_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
_PACKAGE_PATH_PATTERN = re.compile(r"/Game(?:/[A-Za-z][A-Za-z0-9_]*)+")


@dataclass(frozen=True)
class UnrealDialogueImportPackage:
    dialogue_bundle: DialogueBundle
    plan: UnrealExportPlan


def _validate_package_path(package_path: str) -> None:
    if _PACKAGE_PATH_PATTERN.fullmatch(package_path) is None:
        raise DialogueInputError(
            "Unreal audio package path must start with /Game and contain only safe asset "
            "segments."
        )


def _unreal_name(value: str) -> str:
    return "".join(
        part[:1].upper() + part[1:]
        for part in re.split(r"[^A-Za-z0-9]+", value)
        if part
    )


def _canonical_bundle(bundle: DialogueBundle) -> DialogueBundle:
    try:
        return load_dialogue_bundle(render_dialogue_bundle(bundle))
    except DialogueOutputError as exc:
        raise DialogueInputError(
            f"Dialogue bundle is internally inconsistent: {exc}"
        ) from exc


def _audio_import(clip: DialogueClip, destination_path: str) -> UnrealAudioImport:
    asset_name = f"SW_{_unreal_name(clip.cue_id)}"
    asset_path = f"{destination_path}/{asset_name}.{asset_name}"
    return UnrealAudioImport(
        source_cue_id=clip.cue_id,
        source_uri=clip.uri,
        source_relative_path=clip.relative_path,
        source_sha256=clip.wav.sha256,
        destination_path=destination_path,
        asset_name=asset_name,
        asset_path=asset_path,
    )


def compile_dialogue_bundle(
    bundle: DialogueBundle,
    *,
    sequence_package_path: str = DEFAULT_PACKAGE_PATH,
    audio_package_path: str = DEFAULT_AUDIO_PACKAGE_PATH,
) -> UnrealDialogueImportPackage:
    """Compile a verified portable dialogue bundle into an Unreal 5.8 import package."""

    verified = _canonical_bundle(bundle)
    _validate_package_path(audio_package_path)
    project = verified.project.model_copy(deep=True)
    planned_cues = {cue.cue_id: cue for cue in plan_project(project).cues}
    audio_imports = [
        _audio_import(clip, audio_package_path) for clip in verified.manifest.clips
    ]
    if len({item.asset_path for item in audio_imports}) != len(audio_imports):
        raise DialogueInputError(
            "Dialogue cue IDs collide after conversion to Unreal Sound Wave names."
        )
    import_by_cue_id = {item.source_cue_id: item for item in audio_imports}

    scenes = {scene.id: scene for scene in project.scenes}
    for clip in verified.manifest.clips:
        cue = planned_cues[clip.cue_id]
        scene = scenes[cue.scene_id]
        beat = next(item for item in scene.beats if item.id == cue.beat_id)
        performance = beat.performances[cue.performance_index]
        if performance.character_id != cue.character_id or performance.dialogue is None:
            raise DialogueInputError(
                f"Dialogue cue '{cue.cue_id}' no longer resolves to its CIR performance."
            )
        performance.dialogue.audio_uri = import_by_cue_id[cue.cue_id].asset_path

    plan = compile_project(project, package_path=sequence_package_path)
    sequence_by_scene_id = {
        sequence.source_scene_id: sequence for sequence in plan.sequences
    }
    for clip in verified.manifest.clips:
        cue = planned_cues[clip.cue_id]
        sequence = sequence_by_scene_id[cue.scene_id]
        if clip.end_frame > sequence.duration_frames:
            raise DialogueInputError(
                f"Dialogue clip '{clip.cue_id}' ends at frame {clip.end_frame}, beyond sequence "
                f"'{sequence.asset_name}' at frame {sequence.duration_frames}."
            )

        actor_binding_id = next(
            actor.binding_id
            for actor in sequence.actors
            if actor.source_entity_id == cue.character_id
        )
        asset_path = import_by_cue_id[clip.cue_id].asset_path
        matching_indexes = [
            index
            for index, section in enumerate(sequence.audio_sections)
            if section.source_beat_id == cue.beat_id
            and section.actor_binding_id == actor_binding_id
            and section.asset_path == asset_path
            and section.start_frame == clip.start_frame
        ]
        if len(matching_indexes) != 1:
            raise DialogueInputError(
                f"Dialogue cue '{clip.cue_id}' did not compile to exactly one Unreal audio "
                "section."
            )
        index = matching_indexes[0]
        section_data = sequence.audio_sections[index].model_dump(mode="json")
        sequence.audio_sections[index] = UnrealAudioSection.model_validate(
            {
                **section_data,
                "source_cue_id": clip.cue_id,
                "end_frame": clip.end_frame,
                "timing_source": "dialogue_manifest",
            }
        )
        if not clip.fits_within_beat:
            plan.warnings.append(
                UnrealExportWarning(
                    code="dialogue_audio_exceeds_beat",
                    source_id=clip.cue_id,
                    message=(
                        f"Dialogue clip '{clip.cue_id}' extends beyond its CIR beat; v0.6 "
                        "preserves the complete WAV duration in Sequencer."
                    ),
                )
            )

    plan_data = plan.model_dump(mode="json")
    plan_data["audio_imports"] = [
        item.model_dump(mode="json") for item in audio_imports
    ]
    validated_plan = UnrealExportPlan.model_validate(plan_data)
    return UnrealDialogueImportPackage(dialogue_bundle=verified, plan=validated_plan)


def _write_entry(archive: ZipFile, path: str, data: bytes) -> None:
    entry = ZipInfo(path, date_time=_ZIP_TIMESTAMP)
    entry.compress_type = ZIP_DEFLATED
    entry.external_attr = 0o644 << 16
    archive.writestr(entry, data)


def render_unreal_dialogue_import_package(
    package: UnrealDialogueImportPackage,
) -> bytes:
    """Render a deterministic Unreal import ZIP containing the plan, importer, and WAV files."""

    bundle = package.dialogue_bundle
    imports = package.plan.audio_imports
    expected_paths = {item.source_relative_path for item in imports}
    if expected_paths != set(bundle.audio_files):
        raise DialogueOutputError(
            "Unreal audio imports do not exactly match the dialogue bundle WAV files."
        )
    if {item.source_cue_id for item in imports} != {
        clip.cue_id for clip in bundle.manifest.clips
    }:
        raise DialogueOutputError(
            "Unreal audio imports do not exactly match the dialogue manifest clips."
        )
    clip_by_cue_id = {clip.cue_id: clip for clip in bundle.manifest.clips}
    for audio_import in imports:
        clip = clip_by_cue_id[audio_import.source_cue_id]
        if (
            audio_import.source_uri != clip.uri
            or audio_import.source_relative_path != clip.relative_path
            or audio_import.source_sha256 != clip.wav.sha256
        ):
            raise DialogueOutputError(
                f"Unreal audio import '{audio_import.source_cue_id}' does not match its "
                "dialogue clip."
            )

    project_json = (
        json.dumps(bundle.project.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n"
    )
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        _write_entry(
            archive,
            "cutsceneai-unreal-import.py",
            render_unreal_import_script(package.plan).encode("utf-8"),
        )
        _write_entry(
            archive,
            "unreal.plan.json",
            render_unreal_plan(package.plan).encode("utf-8"),
        )
        _write_entry(archive, "project.cir.json", project_json.encode("utf-8"))
        _write_entry(
            archive,
            "dialogue.manifest.json",
            render_dialogue_manifest(bundle.manifest).encode("utf-8"),
        )
        if bundle.manifest.ai_voice_disclosure_required:
            _write_entry(
                archive,
                "AI_VOICE_DISCLOSURE.txt",
                AI_VOICE_DISCLOSURE_TEXT.encode("utf-8"),
            )
        for path, data in sorted(bundle.audio_files.items()):
            _write_entry(archive, path, data)
    return output.getvalue()
