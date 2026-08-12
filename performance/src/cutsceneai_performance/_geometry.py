from __future__ import annotations

import math
from typing import Self

from pydantic import model_validator

from ._resampling import interpolate_float, stable_float
from .models import PerformanceModel

QUATERNION_UNIT_TOLERANCE = 1e-5


class Vector3(PerformanceModel):
    x: float
    y: float
    z: float


class Quaternion(PerformanceModel):
    x: float
    y: float
    z: float
    w: float

    @model_validator(mode="after")
    def validate_unit_length(self) -> Self:
        length = math.sqrt(
            math.fsum(component * component for component in _quat(self))
        )
        if abs(length - 1.0) > QUATERNION_UNIT_TOLERANCE:
            raise ValueError("Quaternion must have unit length within 1e-5.")
        return self


def interpolate_vector3(first: Vector3, second: Vector3, alpha: float) -> Vector3:
    return Vector3(
        x=interpolate_float(first.x, second.x, alpha),
        y=interpolate_float(first.y, second.y, alpha),
        z=interpolate_float(first.z, second.z, alpha),
    )


def slerp_quaternion(first: Quaternion, second: Quaternion, alpha: float) -> Quaternion:
    first_values = _quat(first)
    second_values = _quat(second)
    dot = math.fsum(a * b for a, b in zip(first_values, second_values, strict=True))
    if dot < 0.0:
        second_values = (
            -second_values[0],
            -second_values[1],
            -second_values[2],
            -second_values[3],
        )
        dot = -dot
    dot = max(-1.0, min(1.0, dot))
    if dot > 0.9995:
        values = (
            first_values[0] + (second_values[0] - first_values[0]) * alpha,
            first_values[1] + (second_values[1] - first_values[1]) * alpha,
            first_values[2] + (second_values[2] - first_values[2]) * alpha,
            first_values[3] + (second_values[3] - first_values[3]) * alpha,
        )
    else:
        theta = math.acos(dot)
        sin_theta = math.sin(theta)
        first_weight = math.sin((1.0 - alpha) * theta) / sin_theta
        second_weight = math.sin(alpha * theta) / sin_theta
        values = (
            first_weight * first_values[0] + second_weight * second_values[0],
            first_weight * first_values[1] + second_weight * second_values[1],
            first_weight * first_values[2] + second_weight * second_values[2],
            first_weight * first_values[3] + second_weight * second_values[3],
        )
    normalized = _normalize_quaternion(values)
    return Quaternion(
        x=stable_float(normalized[0]),
        y=stable_float(normalized[1]),
        z=stable_float(normalized[2]),
        w=stable_float(normalized[3]),
    )


def _quat(value: Quaternion) -> tuple[float, float, float, float]:
    return (value.x, value.y, value.z, value.w)


def _normalize_quaternion(
    values: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    length = math.sqrt(math.fsum(component * component for component in values))
    return (
        values[0] / length,
        values[1] / length,
        values[2] / length,
        values[3] / length,
    )
