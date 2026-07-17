from __future__ import annotations

from decimal import Decimal, ROUND_CEILING
from io import BytesIO
import json
from math import isclose
from pathlib import PurePosixPath
from typing import Any
from zipfile import BadZipFile, ZIP_DEFLATED, ZIP_STORED, ZipFile

from pydantic import ValidationError

from cutsceneai_cir import CIRValidationError, validate_project

from .audio import inspect_wav
from .errors import DialogueAudioError, DialogueInputError
from .models import DialogueManifest
from .planning import plan_project
from .service import DialogueBundle


MAX_DIALOGUE_BUNDLE_BYTES = 100 * 1024 * 1024
MAX_DIALOGUE_BUNDLE_ENTRIES = 256
MAX_DIALOGUE_BUNDLE_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
_SUPPORTED_COMPRESSION = frozenset({ZIP_STORED, ZIP_DEFLATED})


def _safe_member_name(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        bool(name)
        and "\\" not in name
        and not path.is_absolute()
        and path.as_posix() == name
        and all(part not in {"", ".", ".."} for part in path.parts)
    )


def _json_object(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DialogueInputError(f"{label} is not valid UTF-8 JSON.") from exc
    if not isinstance(value, dict):
        raise DialogueInputError(f"{label} must contain a JSON object.")
    return value


def _archive_files(data: bytes) -> dict[str, bytes]:
    if not data:
        raise DialogueInputError("Dialogue bundle is empty.")
    if len(data) > MAX_DIALOGUE_BUNDLE_BYTES:
        raise DialogueInputError(
            f"Dialogue bundle exceeds the {MAX_DIALOGUE_BUNDLE_BYTES}-byte v0.1 limit."
        )

    try:
        with ZipFile(BytesIO(data), "r") as archive:
            members = archive.infolist()
            names = [member.filename for member in members]
            if len(members) > MAX_DIALOGUE_BUNDLE_ENTRIES:
                raise DialogueInputError("Dialogue bundle contains too many archive entries.")
            if len(set(names)) != len(names):
                raise DialogueInputError("Dialogue bundle contains duplicate archive paths.")

            total_size = 0
            for member in members:
                if member.is_dir() or not _safe_member_name(member.filename):
                    raise DialogueInputError(
                        f"Dialogue bundle contains an unsafe archive path: {member.filename!r}."
                    )
                if member.flag_bits & 0x1:
                    raise DialogueInputError("Encrypted dialogue bundle entries are not supported.")
                if member.compress_type not in _SUPPORTED_COMPRESSION:
                    raise DialogueInputError(
                        "Dialogue bundle uses an unsupported ZIP compression method."
                    )
                total_size += member.file_size
                if total_size > MAX_DIALOGUE_BUNDLE_UNCOMPRESSED_BYTES:
                    raise DialogueInputError(
                        "Dialogue bundle expands beyond the v0.1 uncompressed-size limit."
                    )
            return {member.filename: archive.read(member) for member in members}
    except DialogueInputError:
        raise
    except (BadZipFile, EOFError, NotImplementedError, OSError, RuntimeError, ValueError) as exc:
        raise DialogueInputError("Dialogue bundle is not a readable ZIP archive.") from exc


def _expected_end_frame(start_seconds: float, duration_seconds: float, fps: int) -> int:
    end = Decimal(str(start_seconds)) + Decimal(str(duration_seconds))
    return int((end * fps).quantize(Decimal("1"), rounding=ROUND_CEILING))


def load_dialogue_bundle(data: bytes) -> DialogueBundle:
    """Load and fully verify a portable Dialogue v0.1 ZIP bundle.

    The loader treats the archive as untrusted input: paths, entry counts, expanded size, public
    contracts, CIR relationships, WAV metadata, hashes, and exact timing are checked before a
    :class:`DialogueBundle` is returned to an engine adapter.
    """

    files = _archive_files(data)
    required_contracts = {"project.cir.json", "dialogue.manifest.json"}
    if not required_contracts.issubset(files):
        missing_contracts = ", ".join(sorted(required_contracts - set(files)))
        raise DialogueInputError(
            f"Dialogue bundle is missing required entries: {missing_contracts}."
        )

    try:
        project = validate_project(_json_object(files["project.cir.json"], "project.cir.json"))
        manifest = DialogueManifest.model_validate(
            _json_object(files["dialogue.manifest.json"], "dialogue.manifest.json")
        )
    except (ValidationError, CIRValidationError) as exc:
        raise DialogueInputError(f"Dialogue bundle contract validation failed: {exc}") from exc

    clip_paths = [clip.relative_path for clip in manifest.clips]
    cue_ids = [clip.cue_id for clip in manifest.clips]
    if not manifest.clips:
        raise DialogueInputError("Dialogue bundle contains no audio clips.")
    if len(set(clip_paths)) != len(clip_paths) or len(set(cue_ids)) != len(cue_ids):
        raise DialogueInputError("Dialogue manifest contains duplicate clip identities.")

    expected_paths = required_contracts | set(clip_paths)
    if manifest.ai_voice_disclosure_required:
        expected_paths.add("AI_VOICE_DISCLOSURE.txt")
    actual_paths = set(files)
    if actual_paths != expected_paths:
        details: list[str] = []
        missing_paths = sorted(expected_paths - actual_paths)
        unknown = sorted(actual_paths - expected_paths)
        if missing_paths:
            details.append("missing: " + ", ".join(missing_paths))
        if unknown:
            details.append("unexpected: " + ", ".join(unknown))
        raise DialogueInputError(
            "Dialogue bundle entries do not match its manifest (" + "; ".join(details) + ")."
        )

    if manifest.project_id != project.id or manifest.fps != project.settings.fps:
        raise DialogueInputError(
            "Dialogue manifest project identity or frame rate does not match CIR."
        )
    generated_audio_present = any(clip.provenance.ai_generated for clip in manifest.clips)
    if manifest.ai_voice_disclosure_required != generated_audio_present:
        raise DialogueInputError("Dialogue bundle AI-voice disclosure metadata is inconsistent.")
    if manifest.ai_voice_disclosure_required:
        try:
            disclosure = files["AI_VOICE_DISCLOSURE.txt"].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DialogueInputError("AI voice disclosure is not valid UTF-8 text.") from exc
        if "AI-generated" not in disclosure:
            raise DialogueInputError("AI voice disclosure text is missing its required notice.")

    cues = {cue.cue_id: cue for cue in plan_project(project).cues}
    if set(cues) != set(cue_ids):
        raise DialogueInputError(
            "Dialogue manifest clips do not exactly match the CIR dialogue cues."
        )

    audio_files: dict[str, bytes] = {}
    for clip in manifest.clips:
        cue = cues[clip.cue_id]
        expected_uri = f"cutsceneai://dialogue/{project.id}/{cue.output_filename}"
        if (
            clip.scene_id != cue.scene_id
            or clip.beat_id != cue.beat_id
            or clip.character_id != cue.character_id
            or clip.text != cue.text
            or clip.language != cue.language
            or clip.start_frame != cue.start_frame
            or not isclose(clip.start_seconds, cue.start_seconds, abs_tol=1e-9)
            or not isclose(clip.beat_end_seconds, cue.beat_end_seconds, abs_tol=1e-9)
            or clip.relative_path != f"audio/{cue.output_filename}"
            or clip.uri != expected_uri
            or cue.existing_audio_uri != expected_uri
        ):
            raise DialogueInputError(f"Dialogue clip '{clip.cue_id}' does not match its CIR cue.")

        audio_data = files[clip.relative_path]
        try:
            metadata = inspect_wav(audio_data)
        except DialogueAudioError as exc:
            raise DialogueInputError(
                f"Dialogue clip '{clip.cue_id}' contains invalid WAV audio: {exc}"
            ) from exc
        expected_end_seconds = cue.start_seconds + metadata.duration_seconds
        expected_end_frame = max(
            cue.start_frame + 1,
            _expected_end_frame(cue.start_seconds, metadata.duration_seconds, manifest.fps),
        )
        expected_fits = expected_end_seconds <= cue.beat_end_seconds + 1e-9
        if (
            clip.wav != metadata
            or not isclose(clip.end_seconds, expected_end_seconds, abs_tol=1e-9)
            or clip.end_frame != expected_end_frame
            or clip.fits_within_beat != expected_fits
        ):
            raise DialogueInputError(
                f"Dialogue clip '{clip.cue_id}' WAV metadata or timing is inconsistent."
            )
        audio_files[clip.relative_path] = audio_data

    return DialogueBundle(project=project, manifest=manifest, audio_files=audio_files)
