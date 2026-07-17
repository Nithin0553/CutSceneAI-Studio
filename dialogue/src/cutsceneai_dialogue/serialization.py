import json
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from .errors import DialogueOutputError
from .models import DialogueManifest, DialogueRenderPlan
from .service import DialogueBundle


_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
AI_VOICE_DISCLOSURE_TEXT = (
    "This bundle contains AI-generated speech. Clearly disclose to end users that the voice "
    "they hear is AI-generated and not a human voice.\n"
)


def render_dialogue_plan(plan: DialogueRenderPlan) -> str:
    return json.dumps(plan.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"


def render_dialogue_manifest(manifest: DialogueManifest) -> str:
    return json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"


def _write_entry(archive: ZipFile, path: str, data: bytes) -> None:
    entry = ZipInfo(path, date_time=_ZIP_TIMESTAMP)
    entry.compress_type = ZIP_DEFLATED
    entry.external_attr = 0o644 << 16
    archive.writestr(entry, data)


def render_dialogue_bundle(bundle: DialogueBundle) -> bytes:
    """Render a byte-for-byte deterministic portable dialogue bundle."""

    expected_paths = [clip.relative_path for clip in bundle.manifest.clips]
    if len(set(expected_paths)) != len(expected_paths):
        raise DialogueOutputError("Dialogue manifest contains duplicate audio paths.")
    if set(bundle.audio_files) != set(expected_paths):
        raise DialogueOutputError(
            "Dialogue bundle audio files do not exactly match the manifest clip paths."
        )

    output = BytesIO()
    with ZipFile(output, "w") as archive:
        project_json = (
            json.dumps(bundle.project.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
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
