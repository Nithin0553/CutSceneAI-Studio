from __future__ import annotations

from math import copysign, sqrt

from cutsceneai_cir import Quaternion, Transform, Vector3

from .models import UnrealQuaternion, UnrealTransform, UnrealVector


_EPSILON = 1e-12
_CLEAN_EPSILON = 1e-8


def _clean(value: float) -> float:
    return 0.0 if abs(value) <= _CLEAN_EPSILON else value


def convert_position(position: Vector3) -> UnrealVector:
    """Convert CIR right-handed, Y-up meters into Unreal left-handed, Z-up centimeters."""

    return UnrealVector(
        x=_clean(-position.z * 100.0),
        y=_clean(position.x * 100.0),
        z=_clean(position.y * 100.0),
    )


def convert_scale(scale: Vector3) -> UnrealVector:
    """Map scale components into Unreal's semantic forward/right/up axes."""

    return UnrealVector(x=scale.z, y=scale.x, z=scale.y)


def convert_quaternion(rotation: Quaternion) -> UnrealQuaternion:
    """Convert an orientation across the CIR-to-Unreal reflected basis."""

    norm = sqrt(
        rotation.x * rotation.x
        + rotation.y * rotation.y
        + rotation.z * rotation.z
        + rotation.w * rotation.w
    )
    if norm <= _EPSILON:
        raise ValueError("CIR rotation quaternion must have non-zero length.")

    x = rotation.x / norm
    y = rotation.y / norm
    z = rotation.z / norm
    w = rotation.w / norm

    # Quaternion vector components are axial vectors. For the reflected basis
    # B(x, y, z) = (-z, x, y), they transform as det(B) * B * v.
    converted = UnrealQuaternion(x=_clean(z), y=_clean(-x), z=_clean(-y), w=_clean(w))
    if converted.w < 0:
        return UnrealQuaternion(
            x=_clean(-converted.x),
            y=_clean(-converted.y),
            z=_clean(-converted.z),
            w=_clean(-converted.w),
        )
    return converted


def convert_transform(transform: Transform) -> UnrealTransform:
    return UnrealTransform(
        location_cm=convert_position(transform.position),
        rotation=convert_quaternion(transform.rotation),
        scale=convert_scale(transform.scale),
    )


def look_at_quaternion(origin: UnrealVector, target: UnrealVector) -> UnrealQuaternion:
    """Return an Unreal quaternion whose local +X axis points at target."""

    forward = _normalize(
        (
            target.x - origin.x,
            target.y - origin.y,
            target.z - origin.z,
        )
    )
    if forward is None:
        return UnrealQuaternion()

    right = _normalize(_cross((0.0, 0.0, 1.0), forward))
    if right is None:
        right = (0.0, 1.0, 0.0)
    up = _cross(forward, right)

    matrix = (
        (forward[0], right[0], up[0]),
        (forward[1], right[1], up[1]),
        (forward[2], right[2], up[2]),
    )
    return _quaternion_from_matrix(matrix)


def _cross(
    left: tuple[float, float, float], right: tuple[float, float, float]
) -> tuple[float, float, float]:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _normalize(
    vector: tuple[float, float, float],
) -> tuple[float, float, float] | None:
    length = sqrt(sum(component * component for component in vector))
    if length <= _EPSILON:
        return None
    return (
        vector[0] / length,
        vector[1] / length,
        vector[2] / length,
    )


def _quaternion_from_matrix(
    matrix: tuple[
        tuple[float, float, float],
        tuple[float, float, float],
        tuple[float, float, float],
    ],
) -> UnrealQuaternion:
    m00, m01, m02 = matrix[0]
    m10, m11, m12 = matrix[1]
    m20, m21, m22 = matrix[2]
    x = 0.5 * copysign(sqrt(max(0.0, 1.0 + m00 - m11 - m22)), m21 - m12)
    y = 0.5 * copysign(sqrt(max(0.0, 1.0 - m00 + m11 - m22)), m02 - m20)
    z = 0.5 * copysign(sqrt(max(0.0, 1.0 - m00 - m11 + m22)), m10 - m01)
    w = 0.5 * sqrt(max(0.0, 1.0 + m00 + m11 + m22))
    return UnrealQuaternion(x=_clean(x), y=_clean(y), z=_clean(z), w=_clean(w))
