import json
from pathlib import Path

from jsonschema import Draft202012Validator

from cutsceneai_unreal import (
    JSON_SCHEMA_DIALECT,
    UNREAL_NATIVE_TARGET_SCHEMA_ID,
    UNREAL_PERFORMANCE_MAPPING_SCHEMA_ID,
    UNREAL_PLAN_SCHEMA_ID,
    UnrealExportPlan,
    UnrealTransform,
    render_unreal_native_target_json_schema,
    render_unreal_performance_mapping_json_schema,
    render_unreal_plan_json_schema,
    unreal_native_target_json_schema,
    unreal_performance_mapping_json_schema,
    unreal_plan_json_schema,
    write_unreal_native_target_json_schema,
    write_unreal_performance_mapping_json_schema,
    write_unreal_plan_json_schema,
)


UNREAL_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = UNREAL_ROOT / "schemas" / "unreal-sequencer-plan-v0.6.schema.json"
PERFORMANCE_SCHEMA = (
    UNREAL_ROOT / "schemas" / "unreal-performance-mapping-v0.1.schema.json"
)
NATIVE_TARGET_SCHEMA = (
    UNREAL_ROOT / "schemas" / "unreal-native-performance-target-v0.1.schema.json"
)
EXAMPLE = UNREAL_ROOT / "examples" / "office-dialogue.unreal.json"


def test_unreal_schema_is_a_strict_public_contract() -> None:
    for schema, schema_id in [
        (unreal_plan_json_schema(), UNREAL_PLAN_SCHEMA_ID),
        (unreal_native_target_json_schema(), UNREAL_NATIVE_TARGET_SCHEMA_ID),
        (
            unreal_performance_mapping_json_schema(),
            UNREAL_PERFORMANCE_MAPPING_SCHEMA_ID,
        ),
    ]:
        assert schema["$schema"] == JSON_SCHEMA_DIALECT
        assert schema["$id"] == schema_id
        assert schema["additionalProperties"] is False
        Draft202012Validator.check_schema(schema)


def test_committed_unreal_artifacts_match_models() -> None:
    assert SCHEMA.read_text(encoding="utf-8") == render_unreal_plan_json_schema()
    assert (
        PERFORMANCE_SCHEMA.read_text(encoding="utf-8")
        == render_unreal_performance_mapping_json_schema()
    )
    assert (
        NATIVE_TARGET_SCHEMA.read_text(encoding="utf-8")
        == render_unreal_native_target_json_schema()
    )
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    Draft202012Validator(unreal_plan_json_schema()).validate(payload)
    assert UnrealExportPlan.model_validate(payload).project_id == "office-dialogue"


def test_schema_writer_and_default_transform_are_usable(tmp_path: Path) -> None:
    output = write_unreal_plan_json_schema(tmp_path / "contracts" / "unreal.json")
    performance_output = write_unreal_performance_mapping_json_schema(
        tmp_path / "contracts" / "unreal-performance.json"
    )
    native_target_output = write_unreal_native_target_json_schema(
        tmp_path / "contracts" / "unreal-native-target.json"
    )

    assert output.read_text(encoding="utf-8") == render_unreal_plan_json_schema()
    assert (
        performance_output.read_text(encoding="utf-8")
        == render_unreal_performance_mapping_json_schema()
    )
    assert (
        native_target_output.read_text(encoding="utf-8")
        == render_unreal_native_target_json_schema()
    )
    assert UnrealTransform().scale.model_dump() == {"x": 1.0, "y": 1.0, "z": 1.0}
