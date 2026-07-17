from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

from cutsceneai_cir import Project
from cutsceneai_dialogue import (
    AudioProvenance,
    DialogueSource,
    dialogue_manifest_json_schema,
    dialogue_plan_json_schema,
    plan_project,
    render_dialogue_plan,
    write_dialogue_schemas,
)
from cutsceneai_dialogue.cli import main
from jsonschema import Draft202012Validator
import pytest
from pydantic import ValidationError

from dialogue.tests.helpers import FIXTURE, make_wav


def test_provenance_enforces_recorded_and_tts_invariants() -> None:
    with pytest.raises(ValidationError, match="provider, model, voice"):
        AudioProvenance(source=DialogueSource.TTS, ai_generated=True)
    with pytest.raises(ValidationError, match="must be marked"):
        AudioProvenance(
            source=DialogueSource.TTS,
            ai_generated=False,
            provider="fake",
            model="v1",
            voice="cedar",
        )
    with pytest.raises(ValidationError, match="Recorded audio"):
        AudioProvenance(source=DialogueSource.RECORDED, ai_generated=True)


def test_schemas_validate_examples_and_reject_extra_fields(project: Project) -> None:
    plan = plan_project(project)
    plan_schema = dialogue_plan_json_schema()
    manifest_schema = dialogue_manifest_json_schema()

    Draft202012Validator.check_schema(plan_schema)
    Draft202012Validator.check_schema(manifest_schema)
    Draft202012Validator(plan_schema).validate(plan.model_dump(mode="json"))
    invalid = plan.model_dump(mode="json")
    invalid["unexpected"] = True
    assert list(Draft202012Validator(plan_schema).iter_errors(invalid))
    assert "DialogueRenderPlan" in plan_schema["title"]
    assert "DialogueManifest" in manifest_schema["title"]


def test_renderers_and_schema_writer_are_stable(project: Project, tmp_path: Path) -> None:
    plan = plan_project(project)
    assert render_dialogue_plan(plan).endswith("\n")
    plan_path, manifest_path = write_dialogue_schemas(
        tmp_path / "nested" / "plan.json", tmp_path / "manifest.json"
    )
    assert json.loads(plan_path.read_text())["$id"].endswith("render-plan.schema.json")
    assert json.loads(manifest_path.read_text())["$id"].endswith("manifest.schema.json")


def test_cli_prints_plan_and_writes_recorded_bundle(
    project: Project, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["plan", str(FIXTURE)]) == 0
    stdout = capsys.readouterr().out
    assert json.loads(stdout)["project_id"] == "office-dialogue"

    plan_output = tmp_path / "plan.json"
    assert main(["plan", str(FIXTURE), "--output", str(plan_output)]) == 0
    assert plan_output.exists()

    args = ["bundle-recorded", str(FIXTURE)]
    for cue in plan_project(project).cues:
        wav_path = tmp_path / f"{cue.cue_id}.wav"
        wav_path.write_bytes(make_wav())
        args.extend(["--recording", f"{cue.cue_id}={wav_path}"])
    output = tmp_path / "bundle.zip"
    args.extend(["--output", str(output)])
    assert main(args) == 0
    with ZipFile(BytesIO(output.read_bytes())) as archive:
        assert "dialogue.manifest.json" in archive.namelist()


@pytest.mark.parametrize(
    "recording",
    ["invalid", "cue=/does/not/exist.wav"],
)
def test_cli_reports_recording_errors(
    recording: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "bundle.zip"
    result = main(
        [
            "bundle-recorded",
            str(FIXTURE),
            "--recording",
            recording,
            "--output",
            str(output),
        ]
    )
    assert result == 2
    assert "cutsceneai-dialogue:" in capsys.readouterr().err


def test_cli_rejects_duplicate_recording(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    wav_path = tmp_path / "line.wav"
    wav_path.write_bytes(make_wav())
    value = f"cue={wav_path}"
    result = main(
        [
            "bundle-recorded",
            str(FIXTURE),
            "--recording",
            value,
            "--recording",
            value,
            "--output",
            str(tmp_path / "bundle.zip"),
        ]
    )
    assert result == 2
    assert "more than once" in capsys.readouterr().err
