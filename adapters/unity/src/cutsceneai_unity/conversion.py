from __future__ import annotations

from typing import Protocol

from cutsceneai_cir import Transform

from .models import UnityQuaternion, UnityTransform, UnityVector


class _Vector3Like(Protocol):
    x: float
    y: float
    z: float


class _QuaternionLike(Protocol):
    x: float
    y: float
    z: float
    w: float


def convert_position(position: _Vector3Like) -> UnityVector:
    """Convert CIR right-handed Y-up coordinates into Unity left-handed Y-up coordinates."""

    return UnityVector(x=position.x, y=position.y, z=-position.z)


def convert_quaternion(rotation: _QuaternionLike) -> UnityQuaternion:
    """Reflect a CIR quaternion across Z for Unity's left-handed coordinates."""

    return UnityQuaternion(
        x=-rotation.x,
        y=-rotation.y,
        z=rotation.z,
        w=rotation.w,
    )


def convert_scale(scale: _Vector3Like) -> UnityVector:
    return UnityVector(x=scale.x, y=scale.y, z=scale.z)


def convert_transform(transform: Transform) -> UnityTransform:
    return UnityTransform(
        position_m=convert_position(transform.position),
        rotation=convert_quaternion(transform.rotation),
        scale=convert_scale(transform.scale),
    )
