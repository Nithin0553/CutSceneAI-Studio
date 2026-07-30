from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import AssetIndex, AssetResolutionPlan

JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
ASSET_INDEX_SCHEMA_ID = (
    "https://schemas.cutsceneai.dev/assets/v0.1/asset-index.schema.json"
)
ASSET_RESOLUTION_SCHEMA_ID = (
    "https://schemas.cutsceneai.dev/assets/v0.1/asset-resolution.schema.json"
)


def asset_index_json_schema() -> dict[str, Any]:
    generated = AssetIndex.model_json_schema(mode="validation")
    return {"$schema": JSON_SCHEMA_DIALECT, "$id": ASSET_INDEX_SCHEMA_ID, **generated}


def asset_resolution_json_schema() -> dict[str, Any]:
    generated = AssetResolutionPlan.model_json_schema(mode="validation")
    return {
        "$schema": JSON_SCHEMA_DIALECT,
        "$id": ASSET_RESOLUTION_SCHEMA_ID,
        **generated,
    }


def render_asset_index_json_schema() -> str:
    return json.dumps(asset_index_json_schema(), indent=2, sort_keys=True) + "\n"


def render_asset_resolution_json_schema() -> str:
    return json.dumps(asset_resolution_json_schema(), indent=2, sort_keys=True) + "\n"


def write_asset_index_json_schema(path: str | Path) -> Path:
    output = Path(path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_asset_index_json_schema(), encoding="utf-8")
    return output


def write_asset_resolution_json_schema(path: str | Path) -> Path:
    output = Path(path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_asset_resolution_json_schema(), encoding="utf-8")
    return output
