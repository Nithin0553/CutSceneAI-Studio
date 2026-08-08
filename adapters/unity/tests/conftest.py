import json
from pathlib import Path

import pytest

from cutsceneai_cir import Project, validate_project


ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def cir_project() -> Project:
    payload = json.loads(
        (ROOT / "cir" / "examples" / "office-dialogue.cir.json").read_text(
            encoding="utf-8"
        )
    )
    return validate_project(payload)
