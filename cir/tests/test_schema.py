import json
from pathlib import Path

from jsonschema import Draft202012Validator

from cutsceneai_cir import (
    JSON_SCHEMA_DIALECT,
    PROJECT_SCHEMA_ID,
    project_json_schema,
    render_project_json_schema,
    write_project_json_schema,
)


SCHEMA_PATH = Path(__file__).parents[1] / "schemas" / "cir-v0.1.schema.json"
EXAMPLE_PATH = Path(__file__).parents[1] / "examples" / "office-dialogue.cir.json"


def test_project_schema_declares_public_contract() -> None:
    schema = project_json_schema()

    assert schema["$schema"] == JSON_SCHEMA_DIALECT
    assert schema["$id"] == PROJECT_SCHEMA_ID
    assert schema["additionalProperties"] is False
    assert schema["properties"]["schema_version"]["const"] == "0.1.0"


def test_committed_schema_matches_models() -> None:
    committed = SCHEMA_PATH.read_text(encoding="utf-8")

    assert committed == render_project_json_schema()
    assert json.loads(committed) == project_json_schema()


def test_project_schema_accepts_golden_example() -> None:
    schema = project_json_schema()
    example = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(example)


def test_schema_writer_creates_parent_directories(tmp_path: Path) -> None:
    destination = tmp_path / "nested" / "project.schema.json"

    written = write_project_json_schema(destination)

    assert written == destination.resolve()
    assert destination.read_text(encoding="utf-8") == render_project_json_schema()
