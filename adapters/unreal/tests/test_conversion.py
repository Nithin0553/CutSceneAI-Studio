from math import isclose, sqrt

import pytest

from cutsceneai_cir import Quaternion, Transform, Vector3
from cutsceneai_unreal import (
    UnrealVector,
    convert_position,
    convert_quaternion,
    convert_scale,
    convert_transform,
    look_at_quaternion,
)


def test_position_maps_cir_semantic_axes_into_unreal_centimeters() -> None:
    converted = convert_position(Vector3(x=1.0, y=2.0, z=3.0))

    assert converted == UnrealVector(x=-300.0, y=100.0, z=200.0)


def test_scale_and_transform_follow_the_same_semantic_axes() -> None:
    assert convert_scale(Vector3(x=2.0, y=3.0, z=4.0)) == UnrealVector(
        x=4.0, y=2.0, z=3.0
    )
    transform = convert_transform(
        Transform(
            position=Vector3(x=1.0, y=2.0, z=3.0),
            scale=Vector3(x=2.0, y=3.0, z=4.0),
        )
    )
    assert transform.location_cm == UnrealVector(x=-300.0, y=100.0, z=200.0)
    assert transform.scale == UnrealVector(x=4.0, y=2.0, z=3.0)


def test_quaternion_conversion_normalizes_and_reflects_rotation_axis() -> None:
    converted = convert_quaternion(Quaternion(x=0.0, y=sqrt(2.0), z=0.0, w=sqrt(2.0)))

    assert isclose(converted.x, 0.0, abs_tol=1e-12)
    assert isclose(converted.y, 0.0, abs_tol=1e-12)
    assert isclose(converted.z, -sqrt(0.5), abs_tol=1e-12)
    assert isclose(converted.w, sqrt(0.5), abs_tol=1e-12)


def test_quaternion_conversion_canonicalizes_negative_identity() -> None:
    converted = convert_quaternion(Quaternion(w=-1.0))

    assert converted.model_dump() == {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}


def test_zero_length_quaternion_is_rejected() -> None:
    with pytest.raises(ValueError, match="non-zero length"):
        convert_quaternion(Quaternion(x=0.0, y=0.0, z=0.0, w=0.0))


def test_look_at_quaternion_is_identity_when_target_is_forward() -> None:
    rotation = look_at_quaternion(
        UnrealVector(x=-100.0, y=0.0, z=10.0),
        UnrealVector(x=0.0, y=0.0, z=10.0),
    )

    assert rotation.model_dump() == {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}


def test_look_at_handles_coincident_and_vertical_points() -> None:
    point = UnrealVector(x=1.0, y=2.0, z=3.0)
    assert look_at_quaternion(point, point).w == 1.0

    vertical = look_at_quaternion(point, UnrealVector(x=1.0, y=2.0, z=30.0))
    norm = sqrt(vertical.x**2 + vertical.y**2 + vertical.z**2 + vertical.w**2)
    assert isclose(norm, 1.0, abs_tol=1e-12)

    behind = look_at_quaternion(point, UnrealVector(x=-30.0, y=2.0, z=3.0))
    behind_norm = sqrt(behind.x**2 + behind.y**2 + behind.z**2 + behind.w**2)
    assert isclose(behind_norm, 1.0, abs_tol=1e-12)
