from __future__ import annotations

import math

import pytest
from cutsceneai_performance import (
    CANONICAL_PARENT_LOCAL_RETARGETING_METHOD,
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


def test_non_root_parent_local_delta_pre_multiplies_target_bind_rotation() -> None:
    parent_component = axis_angle(0.0, 0.0, 1.0, 90.0)
    reference_local = axis_angle(1.0, 0.0, 0.0, 35.0)
    reference_component = multiply_quaternions(parent_component, reference_local)
    canonical_delta = axis_angle(0.0, 1.0, 0.0, 40.0)

    animated_local = retarget_parent_local_rotation(
        canonical_delta=canonical_delta,
        target_reference_local=reference_local,
        target_reference_component=reference_component,
    )

    expected = multiply_quaternions(canonical_delta, reference_local)
    assert_same_rotation(animated_local, expected)


def test_root_rotation_uses_target_parent_bind_basis() -> None:
    parent_component = axis_angle(0.0, 0.0, 1.0, 90.0)
    reference_local = axis_angle(1.0, 0.0, 0.0, 35.0)
    reference_component = multiply_quaternions(parent_component, reference_local)
    canonical_delta = axis_angle(0.0, 1.0, 0.0, 40.0)

    animated_local = retarget_parent_local_rotation(
        canonical_delta=canonical_delta,
        target_reference_local=reference_local,
        target_reference_component=reference_component,
        is_root_joint=True,
    )

    actual_component = multiply_quaternions(parent_component, animated_local)
    expected_component = multiply_quaternions(
        canonical_delta,
        reference_component,
    )
    assert_same_rotation(actual_component, expected_component)

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
    assert CANONICAL_PARENT_LOCAL_RETARGETING_METHOD.endswith("-v2")
