import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .models import EngineTimelineReadback, ParityReport, TimelineSemantics


JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
SEMANTICS_SCHEMA_ID = "https://schemas.cutsceneai.dev/parity/v0.1/semantics.schema.json"
READBACK_SCHEMA_ID = "https://schemas.cutsceneai.dev/parity/v0.1/readback.schema.json"
REPORT_SCHEMA_ID = "https://schemas.cutsceneai.dev/parity/v0.1/report.schema.json"


def _schema(model: type[BaseModel], schema_id: str) -> dict[str, Any]:
    generated = model.model_json_schema(mode="validation")
    return {"$schema": JSON_SCHEMA_DIALECT, "$id": schema_id, **generated}


def timeline_semantics_json_schema() -> dict[str, Any]:
    return _schema(TimelineSemantics, SEMANTICS_SCHEMA_ID)


def engine_readback_json_schema() -> dict[str, Any]:
    return _schema(EngineTimelineReadback, READBACK_SCHEMA_ID)


def parity_report_json_schema() -> dict[str, Any]:
    return _schema(ParityReport, REPORT_SCHEMA_ID)


def _render(schema: dict[str, Any]) -> str:
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def render_timeline_semantics_json_schema() -> str:
    return _render(timeline_semantics_json_schema())


def render_engine_readback_json_schema() -> str:
    return _render(engine_readback_json_schema())


def render_parity_report_json_schema() -> str:
    return _render(parity_report_json_schema())


def write_json_schema(path: str | Path, content: str) -> Path:
    output_path = Path(path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return output_path
