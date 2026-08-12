from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from cutsceneai_cir import Project, validate_project
from cutsceneai_parity import compile_semantics
from cutsceneai_performance import (
    BodyGenerationRequest,
    GenerationModelConfig,
    PerformanceCompilerConfig,
    PerformanceGenerationPlan,
    compile_generation_plan,
    render_generation_plan,
)
from cutsceneai_preview import compile_project as compile_preview
from pydantic import ValidationError

CIR_PATH = Path(__file__).parents[2] / "cir" / "examples" / "office-dialogue.cir.json"
CIR_FINGERPRINT = "39ff99659eb9ef2ccd9dc7422ef50a0305fb81d992858e4ee8e5838abe0f9dfc"


def config(*, seed: int = 20260812) -> PerformanceCompilerConfig:
    return PerformanceCompilerConfig(
        experiment_seed=seed,
        body=GenerationModelConfig(
            provider="research",
            model="body-model",
            model_revision="body-checkpoint",
            prompt_version="body-v1",
        ),
        facial=GenerationModelConfig(
            provider="research",
            model="face-model",
            model_revision="face-checkpoint",
            prompt_version="face-v1",
        ),
        camera=GenerationModelConfig(
            provider="research",
            model="camera-model",
            model_revision="camera-checkpoint",
            prompt_version="camera-v1",
        ),
    )


def office_project() -> Project:
    return validate_project(json.loads(CIR_PATH.read_text(encoding="utf-8")))


def test_compiler_creates_all_office_dialogue_generation_requests() -> None:
    plan = compile_generation_plan(office_project(), config=config())

    assert plan.cir_fingerprint_sha256 == CIR_FINGERPRINT
    assert plan.fps == 24
    assert plan.duration_frames == 432
    assert len(plan.body_requests) == 4
    assert len(plan.facial_requests) == 4
    assert len(plan.camera_requests) == 4
    assert [(item.start_frame, item.end_frame) for item in plan.body_requests] == [
        (0, 96),
        (96, 336),
        (96, 336),
        (336, 432),
    ]
    assert [(item.start_frame, item.end_frame) for item in plan.camera_requests] == [
        (0, 96),
        (96, 144),
        (144, 336),
        (336, 432),
    ]
    assert plan.facial_requests[1].source_dialogue_cue_id == (
        "dialogue:scene-meeting:beat-confrontation:mina:01"
    )
    assert plan.facial_requests[1].dialogue_start_frame == 120
    assert plan.facial_requests[2].dialogue_start_frame == 216


def test_compiler_is_repeatable_for_same_seed_and_configuration() -> None:
    first = compile_generation_plan(office_project(), config=config())
    second = compile_generation_plan(office_project(), config=config())

    assert render_generation_plan(first) == render_generation_plan(second)
    assert [request.seed for request in first.body_requests] == [
        request.seed for request in second.body_requests
    ]


def test_compiler_changes_only_seeds_when_experiment_seed_changes() -> None:
    first = compile_generation_plan(office_project(), config=config(seed=1))
    second = compile_generation_plan(office_project(), config=config(seed=2))

    assert first.cir_fingerprint_sha256 == second.cir_fingerprint_sha256
    assert first.body_requests[0].prompt == second.body_requests[0].prompt
    assert first.body_requests[0].prompt_sha256 == second.body_requests[0].prompt_sha256
    assert first.body_requests[0].seed != second.body_requests[0].seed


def test_compiler_preserves_model_and_prompt_provenance() -> None:
    plan = compile_generation_plan(office_project(), config=config())

    body = plan.body_requests[0]
    assert body.model == "body-model"
    assert body.model_revision == "body-checkpoint"
    assert body.prompt_version == "body-v1"
    assert len(body.prompt_sha256) == 64
    assert len(body.configuration_sha256) == 64
    assert "pre-authored" not in body.prompt.lower()
    assert "Generate novel full-body motion" in body.prompt


def test_compiler_rejects_multiple_scenes() -> None:
    project = office_project()
    project.scenes.append(project.scenes[0].model_copy(update={"id": "second-scene"}))

    with pytest.raises(ValueError, match="exactly one scene"):
        compile_generation_plan(project, config=config())


def test_compiler_rejects_divergent_preview_performance_cues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = compile_preview(office_project())
    manifest.scenes[0].performance_cues.pop()
    monkeypatch.setattr(
        "cutsceneai_performance.compiler.compile_preview", lambda project: manifest
    )

    with pytest.raises(RuntimeError, match="performance cues diverged"):
        compile_generation_plan(office_project(), config=config())


def test_compiler_rejects_missing_dialogue_semantics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    semantics = compile_semantics(office_project())
    semantics.scenes[0].dialogue_cues.clear()
    monkeypatch.setattr(
        "cutsceneai_performance.compiler.compile_semantics", lambda project: semantics
    )

    with pytest.raises(RuntimeError, match="omitted a CIR dialogue cue"):
        compile_generation_plan(office_project(), config=config())


def test_request_rejects_inverted_frame_window() -> None:
    plan = compile_generation_plan(office_project(), config=config())
    payload = plan.body_requests[0].model_dump(mode="json")
    payload.update(start_frame=10, end_frame=10)

    with pytest.raises(ValidationError, match="end_frame"):
        BodyGenerationRequest.model_validate(payload)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda payload: payload["body_requests"][0].update(end_frame=433),
            "duration_frames",
        ),
        (
            lambda payload: payload["camera_requests"][0].update(
                semantic_id=payload["body_requests"][0]["semantic_id"]
            ),
            "semantic IDs",
        ),
    ],
)
def test_generation_plan_rejects_invalid_global_invariants(
    mutation: Callable[[dict[str, Any]], None],
    message: str,
) -> None:
    payload = compile_generation_plan(office_project(), config=config()).model_dump(
        mode="json"
    )
    mutation(payload)

    with pytest.raises(ValidationError, match=message):
        PerformanceGenerationPlan.model_validate(payload)
