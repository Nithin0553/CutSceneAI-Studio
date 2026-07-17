import json
from pathlib import Path
from typing import Any

from .models import DialogueManifest, DialogueRenderPlan


JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
DIALOGUE_PLAN_SCHEMA_ID = "https://schemas.cutsceneai.dev/dialogue/v0.1/render-plan.schema.json"
DIALOGUE_MANIFEST_SCHEMA_ID = "https://schemas.cutsceneai.dev/dialogue/v0.1/manifest.schema.json"


def _schema(
    model: type[DialogueRenderPlan] | type[DialogueManifest], schema_id: str
) -> dict[str, Any]:
    generated = model.model_json_schema(mode="validation")
    return {"$schema": JSON_SCHEMA_DIALECT, "$id": schema_id, **generated}


def dialogue_plan_json_schema() -> dict[str, Any]:
    return _schema(DialogueRenderPlan, DIALOGUE_PLAN_SCHEMA_ID)


def dialogue_manifest_json_schema() -> dict[str, Any]:
    return _schema(DialogueManifest, DIALOGUE_MANIFEST_SCHEMA_ID)


def render_dialogue_plan_json_schema() -> str:
    return json.dumps(dialogue_plan_json_schema(), indent=2, sort_keys=True) + "\n"


def render_dialogue_manifest_json_schema() -> str:
    return json.dumps(dialogue_manifest_json_schema(), indent=2, sort_keys=True) + "\n"


def write_dialogue_schemas(plan_path: str | Path, manifest_path: str | Path) -> tuple[Path, Path]:
    resolved_plan = Path(plan_path).resolve()
    resolved_manifest = Path(manifest_path).resolve()
    resolved_plan.parent.mkdir(parents=True, exist_ok=True)
    resolved_manifest.parent.mkdir(parents=True, exist_ok=True)
    resolved_plan.write_text(render_dialogue_plan_json_schema(), encoding="utf-8")
    resolved_manifest.write_text(render_dialogue_manifest_json_schema(), encoding="utf-8")
    return resolved_plan, resolved_manifest
