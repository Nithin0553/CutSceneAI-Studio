from __future__ import annotations

from typing import Literal

TRANSFORM_RESAMPLING_METHOD: Literal["endpoint-preserving-linear-slerp-v1"] = (
    "endpoint-preserving-linear-slerp-v1"
)
LINEAR_RESAMPLING_METHOD: Literal["endpoint-preserving-linear-v1"] = (
    "endpoint-preserving-linear-v1"
)
ARTIFACT_FLOAT_PRECISION = 9


def validate_resampling_target(*, target_fps: int, target_frame_count: int) -> None:
    if not 1 <= target_fps <= 240:
        raise ValueError("target_fps must be between 1 and 240.")
    if target_frame_count < 1:
        raise ValueError("target_frame_count must be greater than zero.")


def resolve_sample_window(
    *,
    source_frame_count: int,
    target_index: int,
    target_frame_count: int,
) -> tuple[int, int, float]:
    if source_frame_count == 1 or target_frame_count == 1:
        source_position = 0.0
    else:
        source_position = (
            target_index * (source_frame_count - 1) / (target_frame_count - 1)
        )
    lower_index = int(source_position)
    upper_index = min(lower_index + 1, source_frame_count - 1)
    return lower_index, upper_index, source_position - lower_index


def interpolate_float(first: float, second: float, alpha: float) -> float:
    return stable_float(first + (second - first) * alpha)


def stable_float(value: float) -> float:
    rounded = round(value, ARTIFACT_FLOAT_PRECISION)
    return 0.0 if rounded == 0.0 else rounded
