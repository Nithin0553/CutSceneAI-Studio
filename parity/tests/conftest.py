import json
from pathlib import Path

import pytest

from cutsceneai_cir import Project, validate_project
from cutsceneai_parity import (
    EngineName,
    EngineTimelineReadback,
    ReadbackEvidence,
    compile_semantics,
)


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def cir_project() -> Project:
    payload = json.loads(
        (ROOT / "cir" / "examples" / "office-dialogue.cir.json").read_text(
            encoding="utf-8"
        )
    )
    return validate_project(payload)


@pytest.fixture
def readbacks(cir_project: Project) -> list[EngineTimelineReadback]:
    semantics = compile_semantics(cir_project)
    return [
        EngineTimelineReadback(
            engine=EngineName.UNREAL,
            engine_version="5.8.0",
            adapter_version="0.6.0",
            timeline_asset="/Game/CutSceneAI/Sequences/LS_SceneMeeting",
            semantics=semantics.model_copy(deep=True),
            evidence=ReadbackEvidence(),
        ),
        EngineTimelineReadback(
            engine=EngineName.UNITY,
            engine_version="6000.0",
            adapter_version="0.1.0",
            timeline_asset="Assets/CutSceneAI/Timelines/TL_SceneMeeting.playable",
            semantics=semantics.model_copy(deep=True),
            evidence=ReadbackEvidence(),
        ),
    ]
