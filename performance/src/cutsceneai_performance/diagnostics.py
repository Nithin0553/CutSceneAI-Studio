from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
import math
from typing import Literal

from pydantic import Field

from ._geometry import Quaternion, Vector3
from .models import BodyGenerationRequest, PerformanceGenerationPlan, PerformanceModel
from .motion import BodyMotionArtifact
from .providers import NormalizedArtifact


_EPSILON = 1e-9
_CANONICAL_FORWARD = Vector3(x=0.0, y=0.0, z=-1.0)
_CANONICAL_UP = Vector3(x=0.0, y=1.0, z=0.0)


class BodyTrackCompositionMetric(PerformanceModel):
    semantic_id: str
    actor_binding_id: str
    frame_count: int = Field(gt=0)
    raw_max_root_geometry_error_m: float | None = None
    composed_max_root_geometry_error_m: float | None = None
    raw_max_forward_error_deg: float | None = None
    composed_max_forward_error_deg: float | None = None
    raw_max_up_error_deg: float | None = None
    composed_max_up_error_deg: float | None = None
    max_root_translation_edit_m: float = 0.0
    max_joint_position_edit_m: float | None = None
    max_pelvis_rotation_edit_deg: float = 0.0
    rotation_only_composition_detected: bool = False


class BodyPhaseBoundaryMetric(PerformanceModel):
    actor_binding_id: str
    previous_semantic_id: str
    current_semantic_id: str
    boundary_frame: int = Field(ge=0)
    root_position_gap_m: float
    geometry_pelvis_gap_m: float | None = None
    max_joint_position_gap_m: float | None = None
    root_velocity_jump_mps: float | None = None
    geometry_pelvis_velocity_jump_mps: float | None = None
    pelvis_rotation_gap_deg: float


class BodyCompositionDiagnostic(PerformanceModel):
    diagnostic_version: Literal["0.1.0"] = "0.1.0"
    fps: int = Field(gt=0)
    track_metrics: list[BodyTrackCompositionMetric]
    phase_boundaries: list[BodyPhaseBoundaryMetric]
    rotation_only_composition_track_count: int = 0
    max_composed_root_geometry_error_m: float | None = None
    max_composed_forward_error_deg: float | None = None
    max_boundary_geometry_pelvis_gap_m: float | None = None
    max_boundary_joint_position_gap_m: float | None = None
    max_boundary_geometry_velocity_jump_mps: float | None = None


def diagnose_body_composition(
    plan: PerformanceGenerationPlan,
    raw_normalized: Mapping[str, NormalizedArtifact[BodyMotionArtifact]],
    composed: Mapping[str, BodyMotionArtifact],
) -> BodyCompositionDiagnostic:
    requests = {item.semantic_id: item for item in plan.body_requests}
    missing_raw = sorted(set(requests) - set(raw_normalized))
    missing_composed = sorted(set(requests) - set(composed))
    if missing_raw or missing_composed:
        detail = []
        if missing_raw:
            detail.append("raw: " + ", ".join(missing_raw))
        if missing_composed:
            detail.append("composed: " + ", ".join(missing_composed))
        raise ValueError("Body composition diagnostic is missing tracks (" + "; ".join(detail) + ").")

    track_metrics = [
        _track_metric(
            requests[semantic_id],
            raw_normalized[semantic_id].artifact,
            composed[semantic_id],
        )
        for semantic_id in requests
    ]
    phase_boundaries = _boundary_metrics(plan, composed)

    root_geometry_values = [
        item.composed_max_root_geometry_error_m
        for item in track_metrics
        if item.composed_max_root_geometry_error_m is not None
    ]
    forward_values = [
        item.composed_max_forward_error_deg
        for item in track_metrics
        if item.composed_max_forward_error_deg is not None
    ]
    pelvis_gap_values = [
        item.geometry_pelvis_gap_m
        for item in phase_boundaries
        if item.geometry_pelvis_gap_m is not None
    ]
    joint_gap_values = [
        item.max_joint_position_gap_m
        for item in phase_boundaries
        if item.max_joint_position_gap_m is not None
    ]
    geometry_velocity_values = [
        item.geometry_pelvis_velocity_jump_mps
        for item in phase_boundaries
        if item.geometry_pelvis_velocity_jump_mps is not None
    ]

    return BodyCompositionDiagnostic(
        fps=plan.fps,
        track_metrics=track_metrics,
        phase_boundaries=phase_boundaries,
        rotation_only_composition_track_count=sum(
            item.rotation_only_composition_detected for item in track_metrics
        ),
        max_composed_root_geometry_error_m=max(root_geometry_values, default=None),
        max_composed_forward_error_deg=max(forward_values, default=None),
        max_boundary_geometry_pelvis_gap_m=max(pelvis_gap_values, default=None),
        max_boundary_joint_position_gap_m=max(joint_gap_values, default=None),
        max_boundary_geometry_velocity_jump_mps=max(
            geometry_velocity_values,
            default=None,
        ),
    )


def _track_metric(
    request: BodyGenerationRequest,
    raw: BodyMotionArtifact,
    composed: BodyMotionArtifact,
) -> BodyTrackCompositionMetric:
    if raw.frame_count != composed.frame_count:
        raise ValueError(
            f"Body track '{request.semantic_id}' raw/composed frame counts differ."
        )

    raw_root_errors: list[float] = []
    composed_root_errors: list[float] = []
    raw_forward_errors: list[float] = []
    composed_forward_errors: list[float] = []
    raw_up_errors: list[float] = []
    composed_up_errors: list[float] = []
    root_edits: list[float] = []
    joint_edits: list[float] = []
    pelvis_rotation_edits: list[float] = []

    for raw_sample, composed_sample in zip(raw.samples, composed.samples, strict=True):
        root_edits.append(
            _distance(raw_sample.root_translation, composed_sample.root_translation)
        )
        pelvis_rotation_edits.append(
            _quaternion_angle_deg(
                raw_sample.joint_rotations[0],
                composed_sample.joint_rotations[0],
            )
        )

        raw_geometry = raw_sample.joint_positions
        composed_geometry = composed_sample.joint_positions
        if raw_geometry is not None:
            raw_root_errors.append(
                _distance(raw_sample.root_translation, raw_geometry[0])
            )
            orientation = _geometry_orientation(raw_geometry)
            if orientation is not None:
                forward, up = orientation
                raw_forward_errors.append(
                    _vector_angle_deg(
                        _rotate(raw_sample.joint_rotations[0], _CANONICAL_FORWARD),
                        forward,
                    )
                )
                raw_up_errors.append(
                    _vector_angle_deg(
                        _rotate(raw_sample.joint_rotations[0], _CANONICAL_UP),
                        up,
                    )
                )

        if composed_geometry is not None:
            composed_root_errors.append(
                _distance(composed_sample.root_translation, composed_geometry[0])
            )
            orientation = _geometry_orientation(composed_geometry)
            if orientation is not None:
                forward, up = orientation
                composed_forward_errors.append(
                    _vector_angle_deg(
                        _rotate(
                            composed_sample.joint_rotations[0],
                            _CANONICAL_FORWARD,
                        ),
                        forward,
                    )
                )
                composed_up_errors.append(
                    _vector_angle_deg(
                        _rotate(composed_sample.joint_rotations[0], _CANONICAL_UP),
                        up,
                    )
                )

        if raw_geometry is not None and composed_geometry is not None:
            joint_edits.extend(
                _distance(first, second)
                for first, second in zip(raw_geometry, composed_geometry, strict=True)
            )

    max_joint_edit = max(joint_edits, default=None)
    max_pelvis_rotation_edit = max(pelvis_rotation_edits, default=0.0)
    return BodyTrackCompositionMetric(
        semantic_id=request.semantic_id,
        actor_binding_id=request.actor_binding_id,
        frame_count=raw.frame_count,
        raw_max_root_geometry_error_m=max(raw_root_errors, default=None),
        composed_max_root_geometry_error_m=max(composed_root_errors, default=None),
        raw_max_forward_error_deg=max(raw_forward_errors, default=None),
        composed_max_forward_error_deg=max(composed_forward_errors, default=None),
        raw_max_up_error_deg=max(raw_up_errors, default=None),
        composed_max_up_error_deg=max(composed_up_errors, default=None),
        max_root_translation_edit_m=max(root_edits, default=0.0),
        max_joint_position_edit_m=max_joint_edit,
        max_pelvis_rotation_edit_deg=max_pelvis_rotation_edit,
        rotation_only_composition_detected=(
            max_pelvis_rotation_edit > 1e-3
            and max_joint_edit is not None
            and max_joint_edit <= 1e-7
        ),
    )


def _boundary_metrics(
    plan: PerformanceGenerationPlan,
    composed: Mapping[str, BodyMotionArtifact],
) -> list[BodyPhaseBoundaryMetric]:
    by_actor: dict[str, list[BodyGenerationRequest]] = defaultdict(list)
    for request in plan.body_requests:
        by_actor[request.actor_binding_id].append(request)

    result: list[BodyPhaseBoundaryMetric] = []
    for actor_binding_id, requests in by_actor.items():
        requests.sort(key=lambda item: (item.start_frame, item.end_frame, item.semantic_id))
        for previous_request, current_request in zip(requests, requests[1:], strict=False):
            previous = composed[previous_request.semantic_id]
            current = composed[current_request.semantic_id]
            previous_end = previous.samples[-1]
            current_start = current.samples[0]
            geometry_pelvis_gap = None
            max_joint_gap = None
            if (
                previous_end.joint_positions is not None
                and current_start.joint_positions is not None
            ):
                geometry_pelvis_gap = _distance(
                    previous_end.joint_positions[0],
                    current_start.joint_positions[0],
                )
                max_joint_gap = max(
                    _distance(first, second)
                    for first, second in zip(
                        previous_end.joint_positions,
                        current_start.joint_positions,
                        strict=True,
                    )
                )

            root_velocity_jump = _velocity_jump(
                previous,
                current,
                fps=plan.fps,
                use_geometry=False,
            )
            geometry_velocity_jump = _velocity_jump(
                previous,
                current,
                fps=plan.fps,
                use_geometry=True,
            )
            result.append(
                BodyPhaseBoundaryMetric(
                    actor_binding_id=actor_binding_id,
                    previous_semantic_id=previous_request.semantic_id,
                    current_semantic_id=current_request.semantic_id,
                    boundary_frame=current_request.start_frame,
                    root_position_gap_m=_distance(
                        previous_end.root_translation,
                        current_start.root_translation,
                    ),
                    geometry_pelvis_gap_m=geometry_pelvis_gap,
                    max_joint_position_gap_m=max_joint_gap,
                    root_velocity_jump_mps=root_velocity_jump,
                    geometry_pelvis_velocity_jump_mps=geometry_velocity_jump,
                    pelvis_rotation_gap_deg=_quaternion_angle_deg(
                        previous_end.joint_rotations[0],
                        current_start.joint_rotations[0],
                    ),
                )
            )
    return result


def _velocity_jump(
    previous: BodyMotionArtifact,
    current: BodyMotionArtifact,
    *,
    fps: int,
    use_geometry: bool,
) -> float | None:
    if previous.frame_count < 2 or current.frame_count < 2:
        return None

    if use_geometry:
        if (
            previous.samples[-2].joint_positions is None
            or previous.samples[-1].joint_positions is None
            or current.samples[0].joint_positions is None
            or current.samples[1].joint_positions is None
        ):
            return None
        prev_a = previous.samples[-2].joint_positions[0]
        prev_b = previous.samples[-1].joint_positions[0]
        cur_a = current.samples[0].joint_positions[0]
        cur_b = current.samples[1].joint_positions[0]
    else:
        prev_a = previous.samples[-2].root_translation
        prev_b = previous.samples[-1].root_translation
        cur_a = current.samples[0].root_translation
        cur_b = current.samples[1].root_translation

    previous_velocity = _scale(_subtract(prev_b, prev_a), float(fps))
    current_velocity = _scale(_subtract(cur_b, cur_a), float(fps))
    return _distance(previous_velocity, current_velocity)


def _geometry_orientation(
    positions: list[Vector3],
) -> tuple[Vector3, Vector3] | None:
    if len(positions) < 4:
        return None
    pelvis = positions[0]
    left_hip = positions[1]
    right_hip = positions[2]
    spine = positions[3]
    x_axis = _subtract(left_hip, right_hip)
    up_seed = _subtract(spine, pelvis)
    x_axis = _normalize(x_axis)
    if x_axis is None:
        return None
    up = _subtract(up_seed, _scale(x_axis, _dot(up_seed, x_axis)))
    up = _normalize(up)
    if up is None:
        return None
    forward = _normalize(_cross(x_axis, up))
    if forward is None:
        return None
    up = _normalize(_cross(forward, x_axis))
    if up is None:
        return None
    return forward, up


def _quaternion_angle_deg(first: Quaternion, second: Quaternion) -> float:
    dot = abs(
        first.x * second.x
        + first.y * second.y
        + first.z * second.z
        + first.w * second.w
    )
    dot = max(-1.0, min(1.0, dot))
    return math.degrees(2.0 * math.acos(dot))


def _vector_angle_deg(first: Vector3, second: Vector3) -> float:
    a = _normalize(first)
    b = _normalize(second)
    if a is None or b is None:
        return 0.0
    dot = max(-1.0, min(1.0, _dot(a, b)))
    return math.degrees(math.acos(dot))


def _rotate(rotation: Quaternion, vector: Vector3) -> Vector3:
    ux, uy, uz = rotation.x, rotation.y, rotation.z
    vx, vy, vz = vector.x, vector.y, vector.z
    dot_uv = ux * vx + uy * vy + uz * vz
    dot_uu = ux * ux + uy * uy + uz * uz
    cross_x = uy * vz - uz * vy
    cross_y = uz * vx - ux * vz
    cross_z = ux * vy - uy * vx
    scale = rotation.w * rotation.w - dot_uu
    return Vector3(
        x=2.0 * dot_uv * ux + scale * vx + 2.0 * rotation.w * cross_x,
        y=2.0 * dot_uv * uy + scale * vy + 2.0 * rotation.w * cross_y,
        z=2.0 * dot_uv * uz + scale * vz + 2.0 * rotation.w * cross_z,
    )


def _distance(first: Vector3, second: Vector3) -> float:
    delta = _subtract(first, second)
    return math.sqrt(_dot(delta, delta))


def _subtract(first: Vector3, second: Vector3) -> Vector3:
    return Vector3(
        x=first.x - second.x,
        y=first.y - second.y,
        z=first.z - second.z,
    )


def _scale(value: Vector3, amount: float) -> Vector3:
    return Vector3(x=value.x * amount, y=value.y * amount, z=value.z * amount)


def _dot(first: Vector3, second: Vector3) -> float:
    return first.x * second.x + first.y * second.y + first.z * second.z


def _cross(first: Vector3, second: Vector3) -> Vector3:
    return Vector3(
        x=first.y * second.z - first.z * second.y,
        y=first.z * second.x - first.x * second.z,
        z=first.x * second.y - first.y * second.x,
    )


def _normalize(value: Vector3) -> Vector3 | None:
    length = math.sqrt(_dot(value, value))
    if length <= _EPSILON:
        return None
    return _scale(value, 1.0 / length)
