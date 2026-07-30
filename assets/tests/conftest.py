import json
from pathlib import Path

import pytest
from cutsceneai_assets import AssetIndex
from cutsceneai_cir import Project, validate_project

ROOT = Path(__file__).resolve().parents[2]
INDEX_EXAMPLE = ROOT / "assets" / "examples" / "unreal-project.asset-index.json"
OFFICE_EXAMPLE = ROOT / "cir" / "examples" / "office-dialogue.cir.json"
OUTDOOR_EXAMPLE = ROOT / "assets" / "examples" / "outdoor-action.cir.json"


@pytest.fixture
def asset_index() -> AssetIndex:
    return AssetIndex.model_validate(
        json.loads(INDEX_EXAMPLE.read_text(encoding="utf-8"))
    )


@pytest.fixture
def office_project() -> Project:
    return validate_project(json.loads(OFFICE_EXAMPLE.read_text(encoding="utf-8")))


@pytest.fixture
def outdoor_project() -> Project:
    return validate_project(json.loads(OUTDOOR_EXAMPLE.read_text(encoding="utf-8")))
