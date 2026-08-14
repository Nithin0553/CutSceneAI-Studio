import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .experiment_models import (
    GeneratedPerformanceAttemptEvidence,
    GeneratedPerformanceExperimentPlan,
    GeneratedPerformanceExperimentReport,
)
from .models import EngineTimelineReadback, ParityReport, TimelineSemantics


JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
SEMANTICS_SCHEMA_ID = "https://schemas.cutsceneai.dev/parity/v0.1/semantics.schema.json"
READBACK_SCHEMA_ID = "https://schemas.cutsceneai.dev/parity/v0.1/readback.schema.json"
REPORT_SCHEMA_ID = "https://schemas.cutsceneai.dev/parity/v0.1/report.schema.json"
EXPERIMENT_PLAN_SCHEMA_ID = "https://schemas.cutsceneai.dev/parity/v0.1/generated-performance-experiment-plan.schema.json"
ATTEMPT_EVIDENCE_SCHEMA_ID = "https://schemas.cutsceneai.dev/parity/v0.1/generated-performance-attempt.schema.json"
EXPERIMENT_REPORT_SCHEMA_ID = "https://schemas.cutsceneai.dev/parity/v0.1/generated-performance-experiment-report.schema.json"


def _schema(model: type[BaseModel], schema_id: str) -> dict[str, Any]:
    generated = model.model_json_schema(mode="validation")
    return {"$schema": JSON_SCHEMA_DIALECT, "$id": schema_id, **generated}


def timeline_semantics_json_schema() -> dict[str, Any]:
    return _schema(TimelineSemantics, SEMANTICS_SCHEMA_ID)


def engine_readback_json_schema() -> dict[str, Any]:
    return _schema(EngineTimelineReadback, READBACK_SCHEMA_ID)


def parity_report_json_schema() -> dict[str, Any]:
    return _schema(ParityReport, REPORT_SCHEMA_ID)


def generated_performance_experiment_plan_json_schema() -> dict[str, Any]:
    return _schema(GeneratedPerformanceExperimentPlan, EXPERIMENT_PLAN_SCHEMA_ID)


def generated_performance_attempt_evidence_json_schema() -> dict[str, Any]:
    return _schema(GeneratedPerformanceAttemptEvidence, ATTEMPT_EVIDENCE_SCHEMA_ID)


def generated_performance_experiment_report_json_schema() -> dict[str, Any]:
    return _schema(GeneratedPerformanceExperimentReport, EXPERIMENT_REPORT_SCHEMA_ID)


def _render(schema: dict[str, Any]) -> str:
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def render_timeline_semantics_json_schema() -> str:
    return _render(timeline_semantics_json_schema())


def render_engine_readback_json_schema() -> str:
    return _render(engine_readback_json_schema())


def render_parity_report_json_schema() -> str:
    return _render(parity_report_json_schema())


def render_generated_performance_experiment_plan_json_schema() -> str:
    return _render(generated_performance_experiment_plan_json_schema())


def render_generated_performance_attempt_evidence_json_schema() -> str:
    return _render(generated_performance_attempt_evidence_json_schema())


def render_generated_performance_experiment_report_json_schema() -> str:
    return _render(generated_performance_experiment_report_json_schema())


def write_json_schema(path: str | Path, content: str) -> Path:
    output_path = Path(path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return output_path
