from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import pytest
from cutsceneai_performance import (
    CAMERA_RESAMPLING_METHOD,
    CameraCurveArtifact,
    CameraCurveSample,
    Quaternion,
    Vector3,
    camera_curve_artifact_sha256,
    render_camera_curves,
    resample_camera_curves,
)
from pydantic import ValidationError


def camera_artifact() -> CameraCurveArtifact:
    return CameraCurveArtifact(
        sensor_width_mm=24.0,
        sensor_height_mm=13.5,
        fps=30,
        frame_count=2,
        samples=[
            CameraCurveSample(
                frame_index=0,
                position=Vector3(x=0.0, y=1.0, z=2.0),
                rotation=Quaternion(x=0.0, y=0.0, z=0.0, w=1.0),
                focal_length_mm=28.0,
            ),
            CameraCurveSample(
                frame_index=1,
                position=Vector3(x=2.0, y=3.0, z=4.0),
                rotation=Quaternion(x=0.0, y=1.0, z=0.0, w=0.0),
                focal_length_mm=70.0,
            ),
        ],
    )


def test_camera_artifact_declares_portable_transform_and_filmback() -> None:
    camera = camera_artifact()

    assert camera.camera_profile == "cutsceneai-camera-v1"
    assert camera.projection == "perspective"
    assert camera.coordinate_space.forward_axis == "-z"
    assert camera.sensor_width_mm == 24.0
    assert camera.sensor_height_mm == 13.5


def test_camera_render_and_file_hash_are_deterministic() -> None:
    camera = camera_artifact()

    assert render_camera_curves(camera) == render_camera_curves(camera)
    assert camera_curve_artifact_sha256(camera) == camera_curve_artifact_sha256(camera)
    assert len(camera_curve_artifact_sha256(camera)) == 64


def test_camera_resampler_fits_transform_lens_and_exact_frame_window() -> None:
    source = camera_artifact()

    result = resample_camera_curves(source, target_fps=24, target_frame_count=3)

    assert result.fps == 24
    assert result.frame_count == 3
    assert result.sensor_width_mm == source.sensor_width_mm
    assert result.sensor_height_mm == source.sensor_height_mm
    assert result.samples[0].position == source.samples[0].position
    assert result.samples[-1].position == source.samples[-1].position
    assert result.samples[1].position == Vector3(x=1.0, y=2.0, z=3.0)
    assert result.samples[1].focal_length_mm == 49.0
    midpoint = result.samples[1].rotation
    assert midpoint.y == pytest.approx(math.sqrt(0.5), abs=1e-9)
    assert midpoint.w == pytest.approx(math.sqrt(0.5), abs=1e-9)
    assert result.resampling is not None
    assert result.resampling.method == CAMERA_RESAMPLING_METHOD
    assert result.resampling.source_fps == 30
    assert result.resampling.source_frame_count == 2
    assert render_camera_curves(result) == render_camera_curves(
        resample_camera_curves(source, target_fps=24, target_frame_count=3)
    )


def test_camera_resampler_handles_single_source_or_target_frame() -> None:
    source = camera_artifact()
    one_frame = CameraCurveArtifact(
        fps=30,
        frame_count=1,
        samples=[source.samples[0]],
    )

    repeated = resample_camera_curves(
        one_frame,
        target_fps=24,
        target_frame_count=3,
    )
    reduced = resample_camera_curves(source, target_fps=24, target_frame_count=1)

    assert [sample.position for sample in repeated.samples] == [
        source.samples[0].position,
        source.samples[0].position,
        source.samples[0].position,
    ]
    assert reduced.samples == [source.samples[0]]


def test_camera_resampler_returns_independent_copy_when_shape_is_current() -> None:
    source = camera_artifact()

    result = resample_camera_curves(source, target_fps=30, target_frame_count=2)

    assert result == source
    assert result is not source
    assert result.samples[0] is not source.samples[0]


def test_camera_resampler_rejects_invalid_target() -> None:
    with pytest.raises(ValueError, match="target_frame_count"):
        resample_camera_curves(
            camera_artifact(),
            target_fps=24,
            target_frame_count=0,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda payload: payload.update(frame_count=3), "frame_count"),
        (
            lambda payload: payload["samples"][1].update(frame_index=0),
            "contiguous",
        ),
        (
            lambda payload: payload["samples"][0].update(focal_length_mm=7.9),
            "greater than or equal to 8",
        ),
        (
            lambda payload: payload["samples"][0]["rotation"].update(w=0.5),
            "unit length",
        ),
        (
            lambda payload: payload["samples"][0]["position"].update(x=math.inf),
            "finite number",
        ),
        (
            lambda payload: payload.update(sensor_width_mm=0.0),
            "greater than 0",
        ),
    ],
)
def test_camera_artifact_rejects_malformed_curves(
    mutation: Callable[[dict[str, Any]], None],
    message: str,
) -> None:
    payload = camera_artifact().model_dump(mode="json")
    mutation(payload)

    with pytest.raises(ValidationError, match=message):
        CameraCurveArtifact.model_validate(payload)
