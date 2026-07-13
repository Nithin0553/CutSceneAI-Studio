import json
from pathlib import Path

import pytest

from cutsceneai_cir import validate_project
from cutsceneai_preview import PreviewManifest, compile_project


EXAMPLE = (
    Path(__file__).resolve().parents[2]
    / "cir"
    / "examples"
    / "office-dialogue.cir.json"
)


@pytest.fixture
def preview_manifest() -> PreviewManifest:
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    return compile_project(validate_project(payload))
