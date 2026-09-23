from __future__ import annotations

import math

from ._geometry import Quaternion
from ._resampling import stable_float

PARENT_COMPONENT_BIND_RETARGETING_METHOD = "parent-component-bind-conjugation-v1"
CANONICAL_PARENT_LOCAL_RETARGETING_METHOD = (
    "canonical-parent-local-with-root-basis-v2"
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
    is_root_joint: bool = False,
) -> Quaternion:
    """Apply canonical humanoid motion to a target bind pose.

    Non-root CutSceneAI joint rotations are parent-local rotations whose reference
    pose is identity, so they pre-multiply the target bone local bind rotation
    directly. The root/pelvis rotation is actor-space rather than parent-local;
    only that joint requires conjugation through the target root parent bind basis.
    """

    if not is_root_joint:
        return multiply_quaternions(canonical_delta, target_reference_local)

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
