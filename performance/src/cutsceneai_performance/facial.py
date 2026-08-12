from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ._resampling import (
    LINEAR_RESAMPLING_METHOD,
    interpolate_float,
    resolve_sample_window,
    validate_resampling_target,
)
from .models import Identifier, PerformanceModel

ARKIT_52_CURVES = (
    "brow_down_left",
    "brow_down_right",
    "brow_inner_up",
    "brow_outer_up_left",
    "brow_outer_up_right",
    "cheek_puff",
    "cheek_squint_left",
    "cheek_squint_right",
    "eye_blink_left",
    "eye_blink_right",
    "eye_look_down_left",
    "eye_look_down_right",
    "eye_look_in_left",
    "eye_look_in_right",
    "eye_look_out_left",
    "eye_look_out_right",
    "eye_look_up_left",
    "eye_look_up_right",
    "eye_squint_left",
    "eye_squint_right",
    "eye_wide_left",
    "eye_wide_right",
    "jaw_forward",
    "jaw_left",
    "jaw_open",
    "jaw_right",
    "mouth_close",
    "mouth_dimple_left",
    "mouth_dimple_right",
    "mouth_frown_left",
    "mouth_frown_right",
    "mouth_funnel",
    "mouth_left",
    "mouth_lower_down_left",
    "mouth_lower_down_right",
    "mouth_press_left",
    "mouth_press_right",
    "mouth_pucker",
    "mouth_right",
    "mouth_roll_lower",
    "mouth_roll_upper",
    "mouth_shrug_lower",
    "mouth_shrug_upper",
    "mouth_smile_left",
    "mouth_smile_right",
    "mouth_stretch_left",
    "mouth_stretch_right",
    "mouth_upper_up_left",
    "mouth_upper_up_right",
    "nose_sneer_left",
    "nose_sneer_right",
    "tongue_out",
)
FACIAL_RESAMPLING_METHOD: Literal["endpoint-preserving-linear-v1"] = (
    LINEAR_RESAMPLING_METHOD
)
BlendshapeWeight = Annotated[float, Field(ge=0.0, le=1.0)]


class FacialCurveSample(PerformanceModel):
    frame_index: int = Field(ge=0)
    weights: list[BlendshapeWeight] = Field(
        min_length=len(ARKIT_52_CURVES),
        max_length=len(ARKIT_52_CURVES),
    )


class FacialResamplingRecord(PerformanceModel):
    method: Literal["endpoint-preserving-linear-v1"] = FACIAL_RESAMPLING_METHOD
    source_fps: int = Field(ge=1, le=240)
    source_frame_count: int = Field(gt=0)


class FacialCurveArtifact(PerformanceModel):
    artifact_version: Literal["0.1.0"] = "0.1.0"
    curve_profile: Literal["arkit-52"] = "arkit-52"
    fps: int = Field(ge=1, le=240)
    frame_count: int = Field(gt=0)
    curve_names: list[Identifier] = Field(
        default_factory=lambda: list(ARKIT_52_CURVES),
        min_length=len(ARKIT_52_CURVES),
        max_length=len(ARKIT_52_CURVES),
        json_schema_extra={"const": list(ARKIT_52_CURVES)},
    )
    samples: list[FacialCurveSample] = Field(min_length=1)
    resampling: FacialResamplingRecord | None = None

    @model_validator(mode="after")
    def validate_facial_contract(self) -> Self:
        if tuple(self.curve_names) != ARKIT_52_CURVES:
            raise ValueError("curve_names must exactly match arkit-52 order.")
        if self.frame_count != len(self.samples):
            raise ValueError("frame_count must equal the number of facial samples.")
        expected_indices = list(range(self.frame_count))
        if [sample.frame_index for sample in self.samples] != expected_indices:
            raise ValueError(
                "Facial sample frame_index values must be contiguous from zero."
            )
        return self


def resample_facial_curves(
    facial: FacialCurveArtifact,
    *,
    target_fps: int,
    target_frame_count: int,
) -> FacialCurveArtifact:
    """Fit canonical facial weights to an exact frame window with linear interpolation."""

    validate_resampling_target(
        target_fps=target_fps,
        target_frame_count=target_frame_count,
    )
    if facial.fps == target_fps and facial.frame_count == target_frame_count:
        return facial.model_copy(deep=True)

    samples = [
        _sample_at(facial, target_index, target_frame_count)
        for target_index in range(target_frame_count)
    ]
    return FacialCurveArtifact(
        fps=target_fps,
        frame_count=target_frame_count,
        samples=samples,
        resampling=FacialResamplingRecord(
            source_fps=facial.fps,
            source_frame_count=facial.frame_count,
        ),
    )


def _sample_at(
    facial: FacialCurveArtifact,
    target_index: int,
    target_frame_count: int,
) -> FacialCurveSample:
    lower_index, upper_index, alpha = resolve_sample_window(
        source_frame_count=facial.frame_count,
        target_index=target_index,
        target_frame_count=target_frame_count,
    )
    lower = facial.samples[lower_index]
    upper = facial.samples[upper_index]
    return FacialCurveSample(
        frame_index=target_index,
        weights=[
            interpolate_float(first, second, alpha)
            for first, second in zip(lower.weights, upper.weights, strict=True)
        ],
    )
