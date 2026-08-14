import json
from pathlib import Path

from jsonschema import Draft202012Validator

from cutsceneai_cir import Project
from cutsceneai_unity import (
    JSON_SCHEMA_DIALECT,
    UNITY_ASSET_MAP_SCHEMA_ID,
    UNITY_NATIVE_TARGET_SCHEMA_ID,
    UNITY_PERFORMANCE_MAPPING_SCHEMA_ID,
    UNITY_PLAN_SCHEMA_ID,
    UnityAssetMap,
    UnityExportPlan,
    compile_project,
    render_unity_asset_map_json_schema,
    render_unity_native_target_json_schema,
    render_unity_plan,
    render_unity_plan_json_schema,
    render_unity_performance_mapping_json_schema,
    unity_asset_map_json_schema,
    unity_native_target_json_schema,
    unity_plan_json_schema,
    unity_performance_mapping_json_schema,
    write_json_schema,
)


UNITY_ROOT = Path(__file__).resolve().parents[1]


def test_unity_schemas_are_strict_public_contracts() -> None:
    for schema, schema_id in [
        (unity_plan_json_schema(), UNITY_PLAN_SCHEMA_ID),
        (unity_asset_map_json_schema(), UNITY_ASSET_MAP_SCHEMA_ID),
        (unity_native_target_json_schema(), UNITY_NATIVE_TARGET_SCHEMA_ID),
        (
            unity_performance_mapping_json_schema(),
            UNITY_PERFORMANCE_MAPPING_SCHEMA_ID,
        ),
    ]:
        assert schema["$schema"] == JSON_SCHEMA_DIALECT
        assert schema["$id"] == schema_id
        assert schema["additionalProperties"] is False
        Draft202012Validator.check_schema(schema)


def test_committed_schema_and_plan_artifacts_match(cir_project: Project) -> None:
    assert (UNITY_ROOT / "schemas" / "unity-timeline-plan-v0.1.schema.json").read_text(
        encoding="utf-8"
    ) == render_unity_plan_json_schema()
    assert (UNITY_ROOT / "schemas" / "unity-asset-map-v0.1.schema.json").read_text(
        encoding="utf-8"
    ) == render_unity_asset_map_json_schema()
    assert (
        UNITY_ROOT / "schemas" / "unity-performance-mapping-v0.1.schema.json"
    ).read_text(encoding="utf-8") == render_unity_performance_mapping_json_schema()
    assert (
        UNITY_ROOT / "schemas" / "unity-native-performance-target-v0.1.schema.json"
    ).read_text(encoding="utf-8") == render_unity_native_target_json_schema()
    plan = compile_project(cir_project)
    example = UNITY_ROOT / "examples" / "office-dialogue.unity.json"
    assert example.read_text(encoding="utf-8") == render_unity_plan(plan)
    assert (
        UnityExportPlan.model_validate(json.loads(example.read_text(encoding="utf-8")))
        == plan
    )
    asset_map_payload = json.loads(
        (UNITY_ROOT / "examples" / "office-dialogue.asset-map.example.json").read_text(
            encoding="utf-8"
        )
    )
    assert (
        UnityAssetMap.model_validate(asset_map_payload).project_id == "office-dialogue"
    )


def test_schema_writer_creates_parent_directories(tmp_path: Path) -> None:
    content = render_unity_plan_json_schema()
    output = write_json_schema(tmp_path / "contracts" / "unity.json", content)

    assert output.is_absolute()
    assert output.read_text(encoding="utf-8") == content
