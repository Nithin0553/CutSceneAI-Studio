from __future__ import annotations

import math

import pytest
from cutsceneai_performance import (
    PARENT_COMPONENT_BIND_RETARGETING_METHOD,
    Quaternion,
    invert_quaternion,
    multiply_quaternions,
    retarget_parent_local_rotation,
)


def axis_angle(x: float, y: float, z: float, degrees: float) -> Quaternion:
    radians = math.radians(degrees) / 2.0
    scale = math.sin(radians)
    return Quaternion(x=x * scale, y=y * scale, z=z * scale, w=math.cos(radians))


def assert_same_rotation(first: Quaternion, second: Quaternion) -> None:
    dot = abs(
        first.x * second.x
        + first.y * second.y
        + first.z * second.z
        + first.w * second.w
    )
    assert dot == pytest.approx(1.0, abs=1e-8)


def test_parent_component_bind_retargeting_preserves_component_space_delta() -> None:
    parent_component = axis_angle(0.0, 0.0, 1.0, 90.0)
    reference_local = axis_angle(1.0, 0.0, 0.0, 35.0)
    reference_component = multiply_quaternions(parent_component, reference_local)
    canonical_delta = axis_angle(0.0, 1.0, 0.0, 40.0)

    animated_local = retarget_parent_local_rotation(
        canonical_delta=canonical_delta,
        target_reference_local=reference_local,
        target_reference_component=reference_component,
    )

    actual_component = multiply_quaternions(parent_component, animated_local)
    expected_component = multiply_quaternions(
        canonical_delta,
        reference_component,
    )
    assert_same_rotation(actual_component, expected_component)


def test_parent_local_delta_is_not_post_multiplied_on_target_bind_rotation() -> None:
    parent_component = axis_angle(0.0, 0.0, 1.0, 90.0)
    reference_local = axis_angle(1.0, 0.0, 0.0, 35.0)
    reference_component = multiply_quaternions(parent_component, reference_local)
    canonical_delta = axis_angle(0.0, 1.0, 0.0, 40.0)

    corrected = retarget_parent_local_rotation(
        canonical_delta=canonical_delta,
        target_reference_local=reference_local,
        target_reference_component=reference_component,
    )
    previous_implementation = multiply_quaternions(
        reference_local,
        canonical_delta,
    )

    dot = abs(
        corrected.x * previous_implementation.x
        + corrected.y * previous_implementation.y
        + corrected.z * previous_implementation.z
        + corrected.w * previous_implementation.w
    )
    assert dot < 0.99

def test_identity_delta_returns_exact_target_reference_rotation() -> None:
    reference_local = axis_angle(0.0, 0.0, 1.0, 62.0)
    reference_component = multiply_quaternions(
        axis_angle(0.0, 1.0, 0.0, -27.0),
        reference_local,
    )

    result = retarget_parent_local_rotation(
        canonical_delta=Quaternion(x=0.0, y=0.0, z=0.0, w=1.0),
        target_reference_local=reference_local,
        target_reference_component=reference_component,
    )

    assert_same_rotation(result, reference_local)
    assert invert_quaternion(Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)).w == 1.0
    assert PARENT_COMPONENT_BIND_RETARGETING_METHOD.endswith("-v1")
