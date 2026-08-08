import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .models import UnityAssetMap, UnityExportPlan


JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
UNITY_PLAN_SCHEMA_ID = (
    "https://schemas.cutsceneai.dev/unity/v0.1/timeline-plan.schema.json"
)
UNITY_ASSET_MAP_SCHEMA_ID = (
    "https://schemas.cutsceneai.dev/unity/v0.1/asset-map.schema.json"
)


def _schema(model: type[BaseModel], schema_id: str) -> dict[str, Any]:
    generated = model.model_json_schema(mode="validation")
    return {"$schema": JSON_SCHEMA_DIALECT, "$id": schema_id, **generated}


def unity_plan_json_schema() -> dict[str, Any]:
    return _schema(UnityExportPlan, UNITY_PLAN_SCHEMA_ID)


def unity_asset_map_json_schema() -> dict[str, Any]:
    return _schema(UnityAssetMap, UNITY_ASSET_MAP_SCHEMA_ID)


def _render(schema: dict[str, Any]) -> str:
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def render_unity_plan_json_schema() -> str:
    return _render(unity_plan_json_schema())


def render_unity_asset_map_json_schema() -> str:
    return _render(unity_asset_map_json_schema())


def write_json_schema(path: str | Path, content: str) -> Path:
    output_path = Path(path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return output_path
