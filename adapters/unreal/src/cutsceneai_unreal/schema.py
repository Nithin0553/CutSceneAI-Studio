import json
from pathlib import Path
from typing import Any

from .models import UnrealExportPlan


JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
UNREAL_PLAN_SCHEMA_ID = (
    "https://schemas.cutsceneai.dev/adapters/unreal/v0.3/sequencer-plan.schema.json"
)


def unreal_plan_json_schema() -> dict[str, Any]:
    generated = UnrealExportPlan.model_json_schema(mode="validation")
    return {"$schema": JSON_SCHEMA_DIALECT, "$id": UNREAL_PLAN_SCHEMA_ID, **generated}


def render_unreal_plan_json_schema() -> str:
    return json.dumps(unreal_plan_json_schema(), indent=2, sort_keys=True) + "\n"


def write_unreal_plan_json_schema(path: str | Path) -> Path:
    output_path = Path(path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_unreal_plan_json_schema(), encoding="utf-8")
    return output_path
