import json
from pathlib import Path

import pytest

from cutsceneai_cir import Project, validate_project
from cutsceneai_unreal import UnrealExportPlan, compile_project


ROOT = Path(__file__).resolve().parents[3]
CIR_EXAMPLE = ROOT / "cir" / "examples" / "office-dialogue.cir.json"


@pytest.fixture
def cir_project() -> Project:
    return validate_project(json.loads(CIR_EXAMPLE.read_text(encoding="utf-8")))


@pytest.fixture
def unreal_plan(cir_project: Project) -> UnrealExportPlan:
    return compile_project(cir_project)
