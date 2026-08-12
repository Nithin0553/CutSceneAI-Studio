from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import pytest
from cutsceneai_performance import (
    ARKIT_52_CURVES,
    FACIAL_RESAMPLING_METHOD,
    FacialCurveArtifact,
    FacialCurveSample,
    facial_curve_artifact_sha256,
    render_facial_curves,
    resample_facial_curves,
)
from pydantic import ValidationError


def weights(value: float) -> list[float]:
    return [value for _ in ARKIT_52_CURVES]


def facial_artifact() -> FacialCurveArtifact:
    return FacialCurveArtifact(
        fps=60,
        frame_count=2,
        samples=[
            FacialCurveSample(frame_index=0, weights=weights(0.0)),
            FacialCurveSample(frame_index=1, weights=weights(1.0)),
        ],
    )


def test_facial_artifact_declares_complete_arkit_profile() -> None:
    facial = facial_artifact()

    assert len(ARKIT_52_CURVES) == 52
    assert tuple(facial.curve_names) == ARKIT_52_CURVES
    assert facial.curve_names[8:10] == ["eye_blink_left", "eye_blink_right"]
    assert facial.curve_names[24] == "jaw_open"
    assert facial.curve_names[-1] == "tongue_out"


def test_facial_render_and_file_hash_are_deterministic() -> None:
    facial = facial_artifact()

    assert render_facial_curves(facial) == render_facial_curves(facial)
    assert facial_curve_artifact_sha256(facial) == facial_curve_artifact_sha256(facial)
    assert len(facial_curve_artifact_sha256(facial)) == 64


def test_facial_resampler_fits_exact_frame_window() -> None:
    source = facial_artifact()

    result = resample_facial_curves(source, target_fps=24, target_frame_count=3)

    assert result.fps == 24
    assert result.frame_count == 3
    assert result.samples[0].weights == source.samples[0].weights
    assert result.samples[1].weights == weights(0.5)
    assert result.samples[-1].weights == source.samples[-1].weights
    assert result.resampling is not None
    assert result.resampling.method == FACIAL_RESAMPLING_METHOD
    assert result.resampling.source_fps == 60
    assert result.resampling.source_frame_count == 2
    assert render_facial_curves(result) == render_facial_curves(
        resample_facial_curves(source, target_fps=24, target_frame_count=3)
    )


def test_facial_resampler_handles_single_source_or_target_frame() -> None:
    source = facial_artifact()
    one_frame = FacialCurveArtifact(
        fps=60,
        frame_count=1,
        samples=[source.samples[0]],
    )

    repeated = resample_facial_curves(
        one_frame,
        target_fps=24,
        target_frame_count=3,
    )
    reduced = resample_facial_curves(source, target_fps=24, target_frame_count=1)

    assert [sample.weights[0] for sample in repeated.samples] == [0.0, 0.0, 0.0]
    assert reduced.samples == [source.samples[0]]


def test_facial_resampler_returns_independent_copy_when_shape_is_current() -> None:
    source = facial_artifact()

    result = resample_facial_curves(source, target_fps=60, target_frame_count=2)

    assert result == source
    assert result is not source
    assert result.samples[0] is not source.samples[0]


def test_facial_resampler_rejects_invalid_target() -> None:
    with pytest.raises(ValueError, match="target_fps"):
        resample_facial_curves(
            facial_artifact(),
            target_fps=0,
            target_frame_count=2,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda payload: payload["curve_names"].reverse(), "curve_names"),
        (lambda payload: payload.update(frame_count=3), "frame_count"),
        (
            lambda payload: payload["samples"][1].update(frame_index=0),
            "contiguous",
        ),
        (
            lambda payload: payload["samples"][0]["weights"].pop(),
            "at least 52 items",
        ),
        (
            lambda payload: payload["samples"][0]["weights"].__setitem__(0, -0.1),
            "greater than or equal to 0",
        ),
        (
            lambda payload: payload["samples"][0]["weights"].__setitem__(0, 1.1),
            "less than or equal to 1",
        ),
        (
            lambda payload: payload["samples"][0]["weights"].__setitem__(0, math.inf),
            "finite number",
        ),
    ],
)
def test_facial_artifact_rejects_malformed_curves(
    mutation: Callable[[dict[str, Any]], None],
    message: str,
) -> None:
    payload = facial_artifact().model_dump(mode="json")
    mutation(payload)

    with pytest.raises(ValidationError, match=message):
        FacialCurveArtifact.model_validate(payload)
