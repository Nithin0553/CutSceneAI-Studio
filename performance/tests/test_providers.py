from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest
from cutsceneai_performance import (
    ModelProvenance,
    PerformanceOutputError,
    normalize_body_output,
    normalize_camera_output,
    normalize_facial_output,
)
from pydantic import ValidationError


def test_provider_outputs_normalize_to_exact_request_windows(
    performance_fixture: Any,
) -> None:
    plan = performance_fixture.plan
    body = normalize_body_output(
        plan.body_requests[0],
        performance_fixture.body_outputs[0],
        target_fps=plan.fps,
    )
    facial = normalize_facial_output(
        plan.facial_requests[0],
        performance_fixture.facial_outputs[0],
        target_fps=plan.fps,
    )
    camera = normalize_camera_output(
        plan.camera_requests[0],
        performance_fixture.camera_outputs[0],
        target_fps=plan.fps,
    )

    assert body.artifact.fps == facial.artifact.fps == camera.artifact.fps == 24
    assert body.artifact.frame_count == 4
    assert facial.artifact.frame_count == 4
    assert camera.artifact.frame_count == 4
    assert body.provenance.generated_at_inference is True
    assert body.provenance.retrieved_pre_authored_clip is False
    assert body.provenance.prompt_sha256 == plan.body_requests[0].prompt_sha256
    assert body.request_semantic_id == plan.body_requests[0].semantic_id


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("request_semantic_id", "body:wrong:identity"),
        ("provider", "wrong-provider"),
        ("model", "wrong-model"),
        ("model_revision", "wrong-revision"),
        ("prompt_sha256", "d" * 64),
        ("configuration_sha256", "e" * 64),
        ("seed", 43),
    ],
)
def test_normalizer_rejects_provider_request_metadata_mismatch(
    performance_fixture: Any,
    field: str,
    value: Any,
) -> None:
    output = replace(performance_fixture.body_outputs[0], **{field: value})

    with pytest.raises(PerformanceOutputError, match=field):
        normalize_body_output(
            performance_fixture.plan.body_requests[0],
            output,
            target_fps=24,
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("generated_at_inference", False, "not generated at inference"),
        ("generated_at_inference", 1, "not generated at inference"),
        ("retrieved_pre_authored_clip", True, "pre-authored clip"),
        ("retrieved_pre_authored_clip", 0, "pre-authored clip"),
    ],
)
def test_normalizer_rejects_non_inference_or_retrieved_output(
    performance_fixture: Any,
    field: str,
    value: object,
    message: str,
) -> None:
    output = replace(performance_fixture.body_outputs[0], **{field: value})

    with pytest.raises(PerformanceOutputError, match=message):
        normalize_body_output(
            performance_fixture.plan.body_requests[0],
            output,
            target_fps=24,
        )


def test_normalizer_rejects_invalid_determinism_metadata(
    performance_fixture: Any,
) -> None:
    output = replace(
        performance_fixture.body_outputs[0],
        deterministic_algorithms="true",
    )

    with pytest.raises(PerformanceOutputError, match="determinism metadata"):
        normalize_body_output(
            performance_fixture.plan.body_requests[0],
            output,
            target_fps=24,
        )


def test_normalizers_reject_profile_mismatches(
    performance_fixture: Any,
) -> None:
    body_request = performance_fixture.plan.body_requests[0].model_copy(
        update={"skeleton_profile": "other-humanoid"}
    )
    facial_request = performance_fixture.plan.facial_requests[0].model_copy(
        update={"curve_profile": "other-face"}
    )

    with pytest.raises(PerformanceOutputError, match="skeleton profile"):
        normalize_body_output(
            body_request,
            performance_fixture.body_outputs[0],
            target_fps=24,
        )
    with pytest.raises(PerformanceOutputError, match="curve profile"):
        normalize_facial_output(
            facial_request,
            performance_fixture.facial_outputs[0],
            target_fps=24,
        )


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"provider": " "}, "at least 1 character"),
        ({"seed": -1}, "greater than or equal to 0"),
        ({"seed": 2**32}, "less than or equal"),
    ],
)
def test_provenance_rejects_incomplete_identity_or_invalid_seed(
    change: dict[str, Any],
    message: str,
) -> None:
    payload: dict[str, Any] = {
        "provider": "fixture-provider",
        "model": "fixture-model",
        "model_revision": "fixture-revision",
        "prompt_sha256": "a" * 64,
        "configuration_sha256": "b" * 64,
        "seed": 42,
        "generated_at_inference": True,
        "retrieved_pre_authored_clip": False,
        "deterministic_algorithms": True,
    }
    payload.update(change)

    with pytest.raises(ValidationError, match=message):
        ModelProvenance.model_validate(payload)
