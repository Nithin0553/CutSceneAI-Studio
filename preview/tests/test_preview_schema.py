import json
from pathlib import Path

from jsonschema import Draft202012Validator

from cutsceneai_preview import (
    JSON_SCHEMA_DIALECT,
    PREVIEW_SCHEMA_ID,
    PreviewManifest,
    preview_json_schema,
    render_preview_json_schema,
)


PREVIEW_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = PREVIEW_ROOT / "schemas" / "preview-v0.1.schema.json"
EXAMPLE = PREVIEW_ROOT / "examples" / "office-dialogue.preview.json"


def test_preview_schema_is_a_strict_public_contract() -> None:
    schema = preview_json_schema()
    assert schema["$schema"] == JSON_SCHEMA_DIALECT
    assert schema["$id"] == PREVIEW_SCHEMA_ID
    assert schema["additionalProperties"] is False


def test_committed_preview_artifacts_match_models() -> None:
    assert SCHEMA.read_text(encoding="utf-8") == render_preview_json_schema()
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(preview_json_schema())
    Draft202012Validator(preview_json_schema()).validate(payload)
    assert PreviewManifest.model_validate(payload).project_id == "office-dialogue"
