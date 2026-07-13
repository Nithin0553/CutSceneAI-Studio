import json
from pathlib import Path
from typing import Any

from .models import PreviewManifest


JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
PREVIEW_SCHEMA_ID = "https://schemas.cutsceneai.dev/preview/v0.1/manifest.schema.json"


def preview_json_schema() -> dict[str, Any]:
    generated = PreviewManifest.model_json_schema(mode="validation")
    return {"$schema": JSON_SCHEMA_DIALECT, "$id": PREVIEW_SCHEMA_ID, **generated}


def render_preview_json_schema() -> str:
    return json.dumps(preview_json_schema(), indent=2, sort_keys=True) + "\n"


def write_preview_json_schema(path: str | Path) -> Path:
    output_path = Path(path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_preview_json_schema(), encoding="utf-8")
    return output_path
