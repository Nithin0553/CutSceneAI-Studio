from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import Project


JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
PROJECT_SCHEMA_ID = "https://schemas.cutsceneai.dev/cir/v0.1/project.schema.json"


def project_json_schema() -> dict[str, Any]:
    """Return the public JSON Schema contract for a CIR 0.1 project."""

    generated = Project.model_json_schema(mode="validation")
    return {
        "$schema": JSON_SCHEMA_DIALECT,
        "$id": PROJECT_SCHEMA_ID,
        **generated,
    }


def render_project_json_schema() -> str:
    """Render the CIR schema deterministically for source control and CI."""

    return json.dumps(project_json_schema(), indent=2, sort_keys=True) + "\n"


def write_project_json_schema(path: str | Path) -> Path:
    """Write the current CIR schema to *path* and return the resolved path."""

    output_path = Path(path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_project_json_schema(), encoding="utf-8")
    return output_path
