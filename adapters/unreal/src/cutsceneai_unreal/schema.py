import json
from pathlib import Path
from typing import Any

from .models import UnrealExportPlan
from .performance_models import UnrealPerformanceMapping


JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
UNREAL_PLAN_SCHEMA_ID = (
    "https://schemas.cutsceneai.dev/adapters/unreal/v0.6/sequencer-plan.schema.json"
)
UNREAL_PERFORMANCE_MAPPING_SCHEMA_ID = (
    "https://schemas.cutsceneai.dev/adapters/unreal/generated-performance/"
    "v0.1/mapping.schema.json"
)


def unreal_plan_json_schema() -> dict[str, Any]:
    generated = UnrealExportPlan.model_json_schema(mode="validation")
    return {"$schema": JSON_SCHEMA_DIALECT, "$id": UNREAL_PLAN_SCHEMA_ID, **generated}


def unreal_performance_mapping_json_schema() -> dict[str, Any]:
    generated = UnrealPerformanceMapping.model_json_schema(mode="validation")
    return {
        "$schema": JSON_SCHEMA_DIALECT,
        "$id": UNREAL_PERFORMANCE_MAPPING_SCHEMA_ID,
        **generated,
    }


def render_unreal_plan_json_schema() -> str:
    return json.dumps(unreal_plan_json_schema(), indent=2, sort_keys=True) + "\n"


def render_unreal_performance_mapping_json_schema() -> str:
    return (
        json.dumps(unreal_performance_mapping_json_schema(), indent=2, sort_keys=True)
        + "\n"
    )


def write_unreal_plan_json_schema(path: str | Path) -> Path:
    output_path = Path(path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_unreal_plan_json_schema(), encoding="utf-8")
    return output_path


def write_unreal_performance_mapping_json_schema(path: str | Path) -> Path:
    output_path = Path(path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_unreal_performance_mapping_json_schema(), encoding="utf-8"
    )
    return output_path
