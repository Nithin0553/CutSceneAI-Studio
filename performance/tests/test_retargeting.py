from __future__ import annotations

import math

import pytest
from cutsceneai_performance import (
    PARENT_COMPONENT_BIND_RETARGETING_METHOD,
    Quaternion,
    Vector3,
    invert_quaternion,
    multiply_quaternions,
    retarget_parent_local_rotation,
    solve_two_bone_chain,
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


def distance(first: Vector3, second: Vector3) -> float:
    return math.sqrt(
        (first.x - second.x) ** 2
        + (first.y - second.y) ** 2
        + (first.z - second.z) ** 2
    )


def test_two_bone_solver_exactly_reconstructs_same_length_source_geometry() -> None:
    source_root = Vector3(x=0.0, y=0.0, z=0.0)
    source_mid = Vector3(x=0.35, y=-0.85, z=0.2)
    source_end = Vector3(x=0.15, y=-1.65, z=0.55)
    upper = distance(source_root, source_mid)
    lower = distance(source_mid, source_end)

    result = solve_two_bone_chain(
        source_root=source_root,
        source_mid=source_mid,
        source_end=source_end,
        target_root=source_root,
        target_upper_length=upper,
        target_lower_length=lower,
    )

    assert distance(result.mid, source_mid) == pytest.approx(0.0, abs=1e-8)
    assert distance(result.end, source_end) == pytest.approx(0.0, abs=1e-8)
    assert distance(result.root, result.mid) == pytest.approx(upper, abs=1e-8)
    assert distance(result.mid, result.end) == pytest.approx(lower, abs=1e-8)
    assert result.reach_was_clamped is False


def test_two_bone_solver_preserves_target_lengths_and_bend_side_for_new_proportions() -> None:
    source_root = Vector3(x=0.0, y=0.0, z=0.0)
    source_mid = Vector3(x=0.4, y=-0.8, z=0.25)
    source_end = Vector3(x=0.1, y=-1.55, z=0.6)
    target_root = Vector3(x=2.0, y=1.0, z=-3.0)

    result = solve_two_bone_chain(
        source_root=source_root,
        source_mid=source_mid,
        source_end=source_end,
        target_root=target_root,
        target_upper_length=1.15,
        target_lower_length=0.75,
    )

    assert distance(result.root, result.mid) == pytest.approx(1.15, abs=1e-8)
    assert distance(result.mid, result.end) == pytest.approx(0.75, abs=1e-8)

    source_direction = Vector3(
        x=source_end.x - source_root.x,
        y=source_end.y - source_root.y,
        z=source_end.z - source_root.z,
    )
    target_direction = Vector3(
        x=result.end.x - result.root.x,
        y=result.end.y - result.root.y,
        z=result.end.z - result.root.z,
    )
    cross = Vector3(
        x=source_direction.y * target_direction.z - source_direction.z * target_direction.y,
        y=source_direction.z * target_direction.x - source_direction.x * target_direction.z,
        z=source_direction.x * target_direction.y - source_direction.y * target_direction.x,
    )
    assert math.sqrt(cross.x * cross.x + cross.y * cross.y + cross.z * cross.z) == pytest.approx(
        0.0,
        abs=1e-8,
    )

    source_mid_offset = Vector3(
        x=source_mid.x - source_root.x,
        y=source_mid.y - source_root.y,
        z=source_mid.z - source_root.z,
    )
    target_mid_offset = Vector3(
        x=result.mid.x - result.root.x,
        y=result.mid.y - result.root.y,
        z=result.mid.z - result.root.z,
    )
    source_side = (
        source_mid_offset.x * result.bend_direction.x
        + source_mid_offset.y * result.bend_direction.y
        + source_mid_offset.z * result.bend_direction.z
    )
    target_side = (
        target_mid_offset.x * result.bend_direction.x
        + target_mid_offset.y * result.bend_direction.y
        + target_mid_offset.z * result.bend_direction.z
    )
    assert source_side > 0.0
    assert target_side > 0.0


def test_two_bone_solver_requires_explicit_fallback_for_collinear_source_chain() -> None:
    source_root = Vector3(x=0.0, y=0.0, z=0.0)
    source_mid = Vector3(x=0.0, y=-1.0, z=0.0)
    source_end = Vector3(x=0.0, y=-2.0, z=0.0)

    with pytest.raises(ValueError, match="fallback_bend_direction"):
        solve_two_bone_chain(
            source_root=source_root,
            source_mid=source_mid,
            source_end=source_end,
            target_root=source_root,
            target_upper_length=1.0,
            target_lower_length=1.0,
        )

    result = solve_two_bone_chain(
        source_root=source_root,
        source_mid=source_mid,
        source_end=source_end,
        target_root=source_root,
        target_upper_length=1.0,
        target_lower_length=1.0,
        fallback_bend_direction=Vector3(x=0.0, y=0.0, z=1.0),
    )
    assert distance(result.root, result.mid) == pytest.approx(1.0, abs=1e-7)
    assert distance(result.mid, result.end) == pytest.approx(1.0, abs=1e-7)
    assert result.bend_direction.z > 0.99
