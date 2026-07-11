from __future__ import annotations

from typing import Any

from .models import Project


def validate_project(payload: dict[str, Any]) -> Project:
    """Validate a CIR project payload and return a typed project model."""
    return Project.model_validate(payload)
