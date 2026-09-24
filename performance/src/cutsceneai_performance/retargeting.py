from __future__ import annotations

import math

from ._geometry import Quaternion, Vector3
from ._resampling import stable_float

PARENT_COMPONENT_BIND_RETARGETING_METHOD = "parent-component-bind-conjugation-v1"


class TwoBoneChainSolution:
    """Solved target geometry for one analytic two-bone chain."""

    def __init__(
        self,
        *,
        root: Vector3,
        mid: Vector3,
        end: Vector3,
        bend_direction: Vector3,
        source_extension_ratio: float,
        target_reach: float,
        reach_was_clamped: bool,
    ) -> None:
        self.root = root
        self.mid = mid
        self.end = end
        self.bend_direction = bend_direction
        self.source_extension_ratio = source_extension_ratio
        self.target_reach = target_reach
        self.reach_was_clamped = reach_was_clamped


def solve_two_bone_chain(
    *,
    source_root: Vector3,
    source_mid: Vector3,
    source_end: Vector3,
    target_root: Vector3,
    target_upper_length: float,
    target_lower_length: float,
    fallback_bend_direction: Vector3 | None = None,
) -> TwoBoneChainSolution:
    """Retarget one root/mid/end chain from source XYZ geometry.

    The source root-to-end direction and normalized extension define the target
    end-effector goal. The source mid joint supplies the bend-plane direction
    (the same role as an IK hint/pole vector). The target mid joint is then the
    analytic intersection of the two target-length spheres.

    A fallback bend direction is required only when the source chain is
    effectively collinear, where XYZ positions cannot determine a unique bend
    plane.
    """

    if not math.isfinite(target_upper_length) or target_upper_length <= 0.0:
        raise ValueError("target_upper_length must be finite and greater than zero.")
    if not math.isfinite(target_lower_length) or target_lower_length <= 0.0:
        raise ValueError("target_lower_length must be finite and greater than zero.")

    source_upper = _distance(source_root, source_mid)
    source_lower = _distance(source_mid, source_end)
    source_total = source_upper + source_lower
    if source_upper <= 1e-9 or source_lower <= 1e-9:
        raise ValueError("Source two-bone chain contains a zero-length segment.")

    source_displacement = _subtract_vector(source_end, source_root)
    source_reach = _length_vector(source_displacement)
    if source_reach <= 1e-9:
        raise ValueError("Source two-bone chain root and end positions coincide.")

    direction = _scale_vector(source_displacement, 1.0 / source_reach)
    source_extension_ratio = min(1.0, max(0.0, source_reach / source_total))

    target_total = target_upper_length + target_lower_length
    requested_reach = source_extension_ratio * target_total
    minimum_reach = abs(target_upper_length - target_lower_length)
    epsilon = max(target_total * 1e-7, 1e-8)
    lower_bound = min(minimum_reach + epsilon, target_total - epsilon)
    upper_bound = target_total - epsilon
    target_reach = min(upper_bound, max(lower_bound, requested_reach))
    reach_was_clamped = abs(target_reach - requested_reach) > epsilon

    target_end = _add_vector(
        target_root,
        _scale_vector(direction, target_reach),
    )

    source_root_to_mid = _subtract_vector(source_mid, source_root)
    axial = _dot_vector(source_root_to_mid, direction)
    source_bend = _subtract_vector(
        source_root_to_mid,
        _scale_vector(direction, axial),
    )
    if _length_vector(source_bend) <= 1e-8:
        if fallback_bend_direction is None:
            raise ValueError(
                "Source two-bone chain is collinear; fallback_bend_direction is required."
            )
        source_bend = _reject_vector(fallback_bend_direction, direction)
        if _length_vector(source_bend) <= 1e-8:
            raise ValueError(
                "fallback_bend_direction must not be parallel to the chain direction."
            )
    bend_direction = _normalize_vector(source_bend)

    along = (
        target_upper_length * target_upper_length
        - target_lower_length * target_lower_length
        + target_reach * target_reach
    ) / (2.0 * target_reach)
    height_squared = max(
        0.0,
        target_upper_length * target_upper_length - along * along,
    )
    height = math.sqrt(height_squared)
    target_mid = _add_vector(
        _add_vector(
            target_root,
            _scale_vector(direction, along),
        ),
        _scale_vector(bend_direction, height),
    )

    return TwoBoneChainSolution(
        root=_stable_vector(target_root),
        mid=_stable_vector(target_mid),
        end=_stable_vector(target_end),
        bend_direction=_stable_vector(bend_direction),
        source_extension_ratio=stable_float(source_extension_ratio),
        target_reach=stable_float(target_reach),
        reach_was_clamped=reach_was_clamped,
    )


def _stable_vector(value: Vector3) -> Vector3:
    return Vector3(
        x=stable_float(value.x),
        y=stable_float(value.y),
        z=stable_float(value.z),
    )


def _add_vector(first: Vector3, second: Vector3) -> Vector3:
    return Vector3(
        x=first.x + second.x,
        y=first.y + second.y,
        z=first.z + second.z,
    )


def _subtract_vector(first: Vector3, second: Vector3) -> Vector3:
    return Vector3(
        x=first.x - second.x,
        y=first.y - second.y,
        z=first.z - second.z,
    )


def _scale_vector(value: Vector3, scalar: float) -> Vector3:
    return Vector3(
        x=value.x * scalar,
        y=value.y * scalar,
        z=value.z * scalar,
    )


def _dot_vector(first: Vector3, second: Vector3) -> float:
    return math.fsum(
        (
            first.x * second.x,
            first.y * second.y,
            first.z * second.z,
        )
    )


def _length_vector(value: Vector3) -> float:
    return math.sqrt(_dot_vector(value, value))


def _distance(first: Vector3, second: Vector3) -> float:
    return _length_vector(_subtract_vector(first, second))


def _normalize_vector(value: Vector3) -> Vector3:
    length = _length_vector(value)
    if length <= 1e-12:
        raise ValueError("Cannot normalize a zero-length vector.")
    return _scale_vector(value, 1.0 / length)


def _reject_vector(value: Vector3, axis: Vector3) -> Vector3:
    axis_unit = _normalize_vector(axis)
    return _subtract_vector(
        value,
        _scale_vector(axis_unit, _dot_vector(value, axis_unit)),
    )


def multiply_quaternions(first: Quaternion, second: Quaternion) -> Quaternion:
    """Compose two Hamilton quaternions and return a normalized result."""

    ax, ay, az, aw = first.x, first.y, first.z, first.w
    bx, by, bz, bw = second.x, second.y, second.z, second.w
    return _normalized_quaternion(
        (
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz,
        )
    )


def invert_quaternion(value: Quaternion) -> Quaternion:
    """Invert a unit quaternion."""

    return Quaternion(x=-value.x, y=-value.y, z=-value.z, w=value.w)


def retarget_parent_local_rotation(
    *,
    canonical_delta: Quaternion,
    target_reference_local: Quaternion,
    target_reference_component: Quaternion,
) -> Quaternion:
    """Apply a canonical parent-space delta to a target bind pose.

    CutSceneAI canonical joint rotations use axis-aligned parent-space frames.
    Conjugating through the target parent component bind rotation expresses the
    same delta in the target parent bone basis before it is applied to the
    target local bind rotation.
    """

    target_parent_component = multiply_quaternions(
        target_reference_component,
        invert_quaternion(target_reference_local),
    )
    target_parent_delta = multiply_quaternions(
        multiply_quaternions(
            invert_quaternion(target_parent_component),
            canonical_delta,
        ),
        target_parent_component,
    )
    return multiply_quaternions(target_parent_delta, target_reference_local)

def _normalized_quaternion(
    values: tuple[float, float, float, float],
) -> Quaternion:
    length = math.sqrt(math.fsum(component * component for component in values))
    if length <= 1e-12:
        raise ValueError("Quaternion product has zero length.")
    normalized = tuple(component / length for component in values)
    if normalized[3] < 0.0:
        normalized = tuple(-component for component in normalized)
    return Quaternion(
        x=stable_float(normalized[0]),
        y=stable_float(normalized[1]),
        z=stable_float(normalized[2]),
        w=stable_float(normalized[3]),
    )
