from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import GeneratedPerformancePackage, PerformanceGenerationPlan
from .motion import BodyMotionArtifact

JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
PERFORMANCE_PACKAGE_SCHEMA_ID = (
    "https://schemas.cutsceneai.dev/performance/v0.1/package.schema.json"
)
GENERATION_PLAN_SCHEMA_ID = (
    "https://schemas.cutsceneai.dev/performance/v0.1/generation-plan.schema.json"
)
BODY_MOTION_SCHEMA_ID = (
    "https://schemas.cutsceneai.dev/performance/v0.1/body-motion.schema.json"
)


def performance_package_json_schema() -> dict[str, Any]:
    generated = GeneratedPerformancePackage.model_json_schema(mode="validation")
    return {
        "$schema": JSON_SCHEMA_DIALECT,
        "$id": PERFORMANCE_PACKAGE_SCHEMA_ID,
        **generated,
    }


def generation_plan_json_schema() -> dict[str, Any]:
    generated = PerformanceGenerationPlan.model_json_schema(mode="validation")
    return {
        "$schema": JSON_SCHEMA_DIALECT,
        "$id": GENERATION_PLAN_SCHEMA_ID,
        **generated,
    }


def body_motion_json_schema() -> dict[str, Any]:
    generated = BodyMotionArtifact.model_json_schema(mode="validation")
    return {
        "$schema": JSON_SCHEMA_DIALECT,
        "$id": BODY_MOTION_SCHEMA_ID,
        **generated,
    }


def render_performance_package_json_schema() -> str:
    return (
        json.dumps(performance_package_json_schema(), indent=2, sort_keys=True) + "\n"
    )


def render_generation_plan_json_schema() -> str:
    return json.dumps(generation_plan_json_schema(), indent=2, sort_keys=True) + "\n"


def render_body_motion_json_schema() -> str:
    return json.dumps(body_motion_json_schema(), indent=2, sort_keys=True) + "\n"


def write_performance_package_json_schema(path: str | Path) -> Path:
    output_path = Path(path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_performance_package_json_schema(), encoding="utf-8")
    return output_path


def write_body_motion_json_schema(path: str | Path) -> Path:
    output_path = Path(path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_body_motion_json_schema(), encoding="utf-8")
    return output_path
