from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ._geometry import Quaternion, Vector3, interpolate_vector3, slerp_quaternion
from ._resampling import (
    TRANSFORM_RESAMPLING_METHOD,
    interpolate_float,
    resolve_sample_window,
    validate_resampling_target,
)
from .models import CoordinateSpace, PerformanceModel

CAMERA_RESAMPLING_METHOD: Literal["endpoint-preserving-linear-slerp-v1"] = (
    TRANSFORM_RESAMPLING_METHOD
)
FocalLengthMm = Annotated[float, Field(ge=8.0, le=300.0)]
SensorDimensionMm = Annotated[float, Field(gt=0.0, le=100.0)]


class CameraCurveSample(PerformanceModel):
    frame_index: int = Field(ge=0)
    position: Vector3
    rotation: Quaternion
    focal_length_mm: FocalLengthMm


class CameraResamplingRecord(PerformanceModel):
    method: Literal["endpoint-preserving-linear-slerp-v1"] = CAMERA_RESAMPLING_METHOD
    source_fps: int = Field(ge=1, le=240)
    source_frame_count: int = Field(gt=0)


class CameraCurveArtifact(PerformanceModel):
    artifact_version: Literal["0.1.0"] = "0.1.0"
    camera_profile: Literal["cutsceneai-camera-v1"] = "cutsceneai-camera-v1"
    projection: Literal["perspective"] = "perspective"
    coordinate_space: CoordinateSpace = Field(default_factory=CoordinateSpace)
    sensor_width_mm: SensorDimensionMm = 36.0
    sensor_height_mm: SensorDimensionMm = 20.25
    fps: int = Field(ge=1, le=240)
    frame_count: int = Field(gt=0)
    samples: list[CameraCurveSample] = Field(min_length=1)
    resampling: CameraResamplingRecord | None = None

    @model_validator(mode="after")
    def validate_camera_contract(self) -> Self:
        if self.frame_count != len(self.samples):
            raise ValueError("frame_count must equal the number of camera samples.")
        expected_indices = list(range(self.frame_count))
        if [sample.frame_index for sample in self.samples] != expected_indices:
            raise ValueError(
                "Camera sample frame_index values must be contiguous from zero."
            )
        return self


def resample_camera_curves(
    camera: CameraCurveArtifact,
    *,
    target_fps: int,
    target_frame_count: int,
) -> CameraCurveArtifact:
    """Fit camera transform and focal curves to an exact frame window."""

    validate_resampling_target(
        target_fps=target_fps,
        target_frame_count=target_frame_count,
    )
    if camera.fps == target_fps and camera.frame_count == target_frame_count:
        return camera.model_copy(deep=True)

    samples = [
        _sample_at(camera, target_index, target_frame_count)
        for target_index in range(target_frame_count)
    ]
    return CameraCurveArtifact(
        coordinate_space=camera.coordinate_space.model_copy(deep=True),
        sensor_width_mm=camera.sensor_width_mm,
        sensor_height_mm=camera.sensor_height_mm,
        fps=target_fps,
        frame_count=target_frame_count,
        samples=samples,
        resampling=CameraResamplingRecord(
            source_fps=camera.fps,
            source_frame_count=camera.frame_count,
        ),
    )


def _sample_at(
    camera: CameraCurveArtifact,
    target_index: int,
    target_frame_count: int,
) -> CameraCurveSample:
    lower_index, upper_index, alpha = resolve_sample_window(
        source_frame_count=camera.frame_count,
        target_index=target_index,
        target_frame_count=target_frame_count,
    )
    lower = camera.samples[lower_index]
    upper = camera.samples[upper_index]
    return CameraCurveSample(
        frame_index=target_index,
        position=interpolate_vector3(lower.position, upper.position, alpha),
        rotation=slerp_quaternion(lower.rotation, upper.rotation, alpha),
        focal_length_mm=interpolate_float(
            lower.focal_length_mm,
            upper.focal_length_mm,
            alpha,
        ),
    )
