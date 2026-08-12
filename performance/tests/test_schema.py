from __future__ import annotations

import json
from pathlib import Path

from cutsceneai_performance import (
    JSON_SCHEMA_DIALECT,
    PERFORMANCE_PACKAGE_SCHEMA_ID,
    performance_package_json_schema,
    render_performance_package_json_schema,
    write_performance_package_json_schema,
)
from jsonschema import Draft202012Validator

SCHEMA_PATH = (
    Path(__file__).parents[1] / "schemas" / "performance-package-v0.1.schema.json"
)


def test_schema_declares_public_contract() -> None:
    schema = performance_package_json_schema()

    assert schema["$schema"] == JSON_SCHEMA_DIALECT
    assert schema["$id"] == PERFORMANCE_PACKAGE_SCHEMA_ID
    assert schema["additionalProperties"] is False
    Draft202012Validator.check_schema(schema)


def test_committed_schema_matches_models() -> None:
    committed = SCHEMA_PATH.read_text(encoding="utf-8")

    assert committed == render_performance_package_json_schema()
    assert json.loads(committed) == performance_package_json_schema()


def test_schema_writer_creates_parent_directories(tmp_path: Path) -> None:
    destination = tmp_path / "nested" / "performance-package.schema.json"

    written = write_performance_package_json_schema(destination)

    assert written == destination.resolve()
    assert destination.read_text(encoding="utf-8") == (
        render_performance_package_json_schema()
    )
