from __future__ import annotations

import pytest
from cutsceneai_cir import Project

from dialogue.tests.helpers import FIXTURE


@pytest.fixture
def project() -> Project:
    return Project.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
