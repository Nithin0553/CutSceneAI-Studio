import json
from pathlib import Path
import runpy
import sys

from jsonschema import Draft202012Validator

from cutsceneai_cir import Project
from cutsceneai_parity import (
    EngineName,
    EngineTimelineReadback,
    JSON_SCHEMA_DIALECT,
    READBACK_SCHEMA_ID,
    REPORT_SCHEMA_ID,
    SEMANTICS_SCHEMA_ID,
    compile_semantics,
    engine_readback_json_schema,
    parity_report_json_schema,
    render_engine_readback,
    render_engine_readback_json_schema,
    render_parity_report_json_schema,
    render_timeline_semantics,
    render_timeline_semantics_json_schema,
    timeline_semantics_json_schema,
    write_json_schema,
)
from cutsceneai_parity.cli import main


PARITY_ROOT = Path(__file__).resolve().parents[1]


def test_public_schemas_are_strict_and_valid() -> None:
    contracts = [
        (timeline_semantics_json_schema(), SEMANTICS_SCHEMA_ID),
        (engine_readback_json_schema(), READBACK_SCHEMA_ID),
        (parity_report_json_schema(), REPORT_SCHEMA_ID),
    ]
    for schema, schema_id in contracts:
        assert schema["$schema"] == JSON_SCHEMA_DIALECT
        assert schema["$id"] == schema_id
        assert schema["additionalProperties"] is False
        Draft202012Validator.check_schema(schema)


def test_committed_artifacts_match_models(cir_project: Project) -> None:
    assert (PARITY_ROOT / "schemas" / "timeline-semantics-v0.1.schema.json").read_text(
        encoding="utf-8"
    ) == render_timeline_semantics_json_schema()
    assert (PARITY_ROOT / "schemas" / "engine-readback-v0.1.schema.json").read_text(
        encoding="utf-8"
    ) == render_engine_readback_json_schema()
    assert (PARITY_ROOT / "schemas" / "parity-report-v0.1.schema.json").read_text(
        encoding="utf-8"
    ) == render_parity_report_json_schema()
    expected = compile_semantics(cir_project)
    example = PARITY_ROOT / "examples" / "office-dialogue.semantics.json"
    assert example.read_text(encoding="utf-8") == render_timeline_semantics(expected)


def test_schema_writer_creates_parent_directories(tmp_path: Path) -> None:
    content = render_timeline_semantics_json_schema()
    output = write_json_schema(tmp_path / "contracts" / "semantics.json", content)

    assert output.is_absolute()
    assert output.read_text(encoding="utf-8") == content


def test_cli_writes_expected_and_returns_nonzero_for_mismatch(
    cir_project: Project, tmp_path: Path
) -> None:
    cir_path = tmp_path / "scene.cir.json"
    cir_path.write_text(
        json.dumps(cir_project.model_dump(mode="json")), encoding="utf-8"
    )
    expected_path = tmp_path / "expected.json"
    assert main(["expected", str(cir_path), "--output", str(expected_path)]) == 0
    semantics = compile_semantics(cir_project)
    assert expected_path.read_text(encoding="utf-8") == render_timeline_semantics(
        semantics
    )

    readback = EngineTimelineReadback(
        engine=EngineName.UNITY,
        engine_version="6000.0",
        adapter_version="0.1.0",
        timeline_asset="Assets/Timeline.playable",
        semantics=semantics,
    )
    readback.semantics.scenes[0].duration_frames -= 4
    readback_path = tmp_path / "unity.json"
    readback_path.write_text(render_engine_readback(readback), encoding="utf-8")
    report_path = tmp_path / "report.json"
    assert (
        main(
            [
                "verify",
                str(cir_path),
                "--readback",
                str(readback_path),
                "--tolerance-frames",
                "1",
                "--require-both-engines",
                "--output",
                str(report_path),
            ]
        )
        == 1
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["equivalent"] is False
    assert "missing_engine_readback" in {item["code"] for item in report["issues"]}


def test_cli_rejects_non_object_cir(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("[]", encoding="utf-8")
    try:
        main(["expected", str(bad)])
    except ValueError as exc:
        assert str(exc) == "CIR JSON must be an object."
    else:
        raise AssertionError("non-object CIR should fail")

    try:
        main(["verify", str(bad), "--readback", str(bad)])
    except ValueError as exc:
        assert str(exc) == "CIR JSON must be an object."
    else:
        raise AssertionError("non-object verification CIR should fail")


def test_cli_can_print_expected_semantics(
    cir_project: Project, tmp_path: Path, capsys
) -> None:
    cir_path = tmp_path / "scene.cir.json"
    cir_path.write_text(
        json.dumps(cir_project.model_dump(mode="json")), encoding="utf-8"
    )

    assert main(["expected", str(cir_path)]) == 0
    assert capsys.readouterr().out == render_timeline_semantics(
        compile_semantics(cir_project)
    )


def test_module_entry_point_executes_cli(
    cir_project: Project, tmp_path: Path, capsys
) -> None:
    cir_path = tmp_path / "scene.cir.json"
    cir_path.write_text(
        json.dumps(cir_project.model_dump(mode="json")), encoding="utf-8"
    )
    original_argv = sys.argv
    sys.argv = ["cutsceneai_parity", "expected", str(cir_path)]
    try:
        try:
            runpy.run_module("cutsceneai_parity", run_name="__main__")
        except SystemExit as exc:
            assert exc.code == 0
        else:
            raise AssertionError("module entry point should exit")
    finally:
        sys.argv = original_argv
    assert capsys.readouterr().out == render_timeline_semantics(
        compile_semantics(cir_project)
    )
