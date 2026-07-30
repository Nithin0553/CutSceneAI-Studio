import json
from pathlib import Path

from cutsceneai_assets import (
    ASSET_INDEX_SCHEMA_ID,
    ASSET_RESOLUTION_SCHEMA_ID,
    AssetIndex,
    AssetResolutionPlan,
    asset_index_json_schema,
    asset_resolution_json_schema,
    render_asset_index_json_schema,
    render_asset_resolution_json_schema,
    resolve_project,
    write_asset_index_json_schema,
    write_asset_resolution_json_schema,
)
from cutsceneai_cir import validate_project
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "assets" / "examples" / "unreal-project.asset-index.json"
OFFICE = ROOT / "cir" / "examples" / "office-dialogue.cir.json"
INDEX_SCHEMA = ROOT / "assets" / "schemas" / "asset-index-v0.1.schema.json"
RESOLUTION_SCHEMA = ROOT / "assets" / "schemas" / "asset-resolution-v0.1.schema.json"
OFFICE_RESOLUTION = (
    ROOT / "assets" / "examples" / "office-dialogue.asset-resolution.json"
)


def test_asset_schemas_are_strict_public_contracts() -> None:
    index_schema = asset_index_json_schema()
    resolution_schema = asset_resolution_json_schema()

    assert index_schema["$id"] == ASSET_INDEX_SCHEMA_ID
    assert resolution_schema["$id"] == ASSET_RESOLUTION_SCHEMA_ID
    assert index_schema["additionalProperties"] is False
    assert resolution_schema["additionalProperties"] is False


def test_committed_asset_artifacts_match_models() -> None:
    assert INDEX_SCHEMA.read_text(encoding="utf-8") == render_asset_index_json_schema()
    assert (
        RESOLUTION_SCHEMA.read_text(encoding="utf-8")
        == render_asset_resolution_json_schema()
    )

    index_payload = json.loads(INDEX.read_text(encoding="utf-8"))
    resolution_payload = json.loads(OFFICE_RESOLUTION.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(asset_index_json_schema())
    Draft202012Validator.check_schema(asset_resolution_json_schema())
    Draft202012Validator(asset_index_json_schema()).validate(index_payload)
    Draft202012Validator(asset_resolution_json_schema()).validate(resolution_payload)
    assert AssetIndex.model_validate(index_payload).id == "cutsceneai-fixture-assets"
    assert (
        AssetResolutionPlan.model_validate(resolution_payload).project_id
        == "office-dialogue"
    )


def test_schema_writers_create_parent_directories(tmp_path: Path) -> None:
    index_output = write_asset_index_json_schema(
        tmp_path / "nested" / "asset-index.json"
    )
    resolution_output = write_asset_resolution_json_schema(
        tmp_path / "nested" / "asset-resolution.json"
    )

    assert index_output.read_text(encoding="utf-8") == render_asset_index_json_schema()
    assert (
        resolution_output.read_text(encoding="utf-8")
        == render_asset_resolution_json_schema()
    )


def test_office_resolution_example_matches_current_resolver() -> None:
    index = AssetIndex.model_validate(json.loads(INDEX.read_text(encoding="utf-8")))
    project = validate_project(json.loads(OFFICE.read_text(encoding="utf-8")))

    assert AssetResolutionPlan.model_validate(
        json.loads(OFFICE_RESOLUTION.read_text(encoding="utf-8"))
    ) == resolve_project(project, index)
