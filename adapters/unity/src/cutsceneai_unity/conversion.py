from __future__ import annotations

from cutsceneai_cir import Quaternion, Transform, Vector3

from .models import UnityQuaternion, UnityTransform, UnityVector


def convert_position(position: Vector3) -> UnityVector:
    """Convert CIR right-handed Y-up coordinates into Unity left-handed Y-up coordinates."""

    return UnityVector(x=position.x, y=position.y, z=-position.z)


def convert_quaternion(rotation: Quaternion) -> UnityQuaternion:
    """Reflect a CIR quaternion across Z for Unity's left-handed coordinates."""

    return UnityQuaternion(
        x=-rotation.x,
        y=-rotation.y,
        z=rotation.z,
        w=rotation.w,
    )


def convert_scale(scale: Vector3) -> UnityVector:
    return UnityVector(x=scale.x, y=scale.y, z=scale.z)


def convert_transform(transform: Transform) -> UnityTransform:
    return UnityTransform(
        position_m=convert_position(transform.position),
        rotation=convert_quaternion(transform.rotation),
        scale=convert_scale(transform.scale),
    )
