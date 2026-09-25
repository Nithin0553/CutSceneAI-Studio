from __future__ import annotations

import hashlib
import math
import statistics

from .bundle import PerformanceBundle, decode_performance_bundle, render_performance_bundle
from .evaluation import (
    EvaluationReport,
    EvaluationStage,
    IssueSeverity,
    PerformanceIssue,
    stable_issue_id,
)


_STATIONARY_HINTS = ("listen", "hold", "idle", "stand", "remain")
_STOP_HINTS = ("stop", "halt")
_TURN_HINTS = ("turn", "pivot", "rotate")


def _sub(a, b):
    return (a.x - b.x, a.y - b.y, a.z - b.z)


def _length(value: tuple[float, float, float]) -> float:
    return math.sqrt(sum(component * component for component in value))


def _distance(a, b) -> float:
    return _length(_sub(a, b))


def _horizontal_distance(a, b) -> float:
    dx = a.x - b.x
    dz = a.z - b.z
    return math.sqrt(dx * dx + dz * dz)


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    alpha = position - lower
    return ordered[lower] * (1.0 - alpha) + ordered[upper] * alpha


def _body_heading(sample, joint_index: dict[str, int]) -> float | None:
    pelvis = sample.joint_positions[joint_index["pelvis"]]
    left = sample.joint_positions[joint_index["left_hip"]]
    right = sample.joint_positions[joint_index["right_hip"]]
    spine = sample.joint_positions[joint_index["spine1"]]

    x_axis = _sub(left, right)
    up_seed = _sub(spine, pelvis)
    x_length = _length(x_axis)
    up_length = _length(up_seed)
    if x_length <= 1e-9 or up_length <= 1e-9:
        return None
    x_axis = tuple(component / x_length for component in x_axis)
    dot = sum(up_seed[index] * x_axis[index] for index in range(3))
    up = tuple(up_seed[index] - dot * x_axis[index] for index in range(3))
    up_length = _length(up)
    if up_length <= 1e-9:
        return None
    up = tuple(component / up_length for component in up)

    forward = (
        x_axis[1] * up[2] - x_axis[2] * up[1],
        x_axis[2] * up[0] - x_axis[0] * up[2],
        x_axis[0] * up[1] - x_axis[1] * up[0],
    )
    horizontal = math.sqrt(forward[0] * forward[0] + forward[2] * forward[2])
    if horizontal <= 1e-9:
        return None
    return math.atan2(forward[0] / horizontal, forward[2] / horizontal)


def _heading_delta_degrees(first: float | None, last: float | None) -> float:
    if first is None or last is None:
        return 0.0
    delta = (last - first + math.pi) % (2.0 * math.pi) - math.pi
    return math.degrees(delta)


def _issue(
    *,
    stage: EvaluationStage,
    domain: str,
    code: str,
    severity: IssueSeverity,
    message: str,
    semantic_id: str | None,
    actor_binding_id: str | None,
    component: str | None,
    start_frame: int | None,
    end_frame: int | None,
    metrics: dict[str, float],
) -> PerformanceIssue:
    return PerformanceIssue(
        issue_id=stable_issue_id(
            stage=stage,
            code=code,
            semantic_id=semantic_id,
            actor_binding_id=actor_binding_id,
            component=component,
            start_frame=start_frame,
            end_frame=end_frame,
        ),
        stage=stage,
        domain=domain,
        code=code,
        severity=severity,
        message=message,
        semantic_id=semantic_id,
        actor_binding_id=actor_binding_id,
        component=component,
        start_frame=start_frame,
        end_frame=end_frame,
        metrics=metrics,
    )


def evaluate_canonical_performance(
    bundle: PerformanceBundle,
    *,
    performance_run_id: str,
    iteration: int = 0,
) -> EvaluationReport:
    """Evaluate canonical body motion before target-rig or engine realization."""

    decoded = decode_performance_bundle(bundle)
    issues: list[PerformanceIssue] = []
    package = bundle.package

    tracks_by_actor: dict[str, list] = {}
    for track in package.body_tracks:
        tracks_by_actor.setdefault(track.actor_binding_id, []).append(track)

    for actor_binding_id, tracks in sorted(tracks_by_actor.items()):
        tracks.sort(key=lambda item: (item.start_frame, item.semantic_id))
        timeline: list[tuple[int, str, object]] = []

        for track in tracks:
            artifact = decoded.body_artifacts[track.semantic_id]
            if any(sample.joint_positions is None for sample in artifact.samples):
                issues.append(
                    _issue(
                        stage=EvaluationStage.CANONICAL,
                        domain="motion",
                        code="canonical_geometry_missing",
                        severity=IssueSeverity.ERROR,
                        message="Canonical body motion is missing joint geometry.",
                        semantic_id=track.semantic_id,
                        actor_binding_id=actor_binding_id,
                        component=None,
                        start_frame=track.start_frame,
                        end_frame=track.end_frame,
                        metrics={},
                    )
                )
                continue

            joint_index = {
                name: index for index, name in enumerate(artifact.joint_names)
            }

            max_relative_deviation = 0.0
            for joint_index_value, parent_index in enumerate(artifact.parent_indices):
                if parent_index < 0:
                    continue
                lengths = [
                    _distance(
                        sample.joint_positions[joint_index_value],
                        sample.joint_positions[parent_index],
                    )
                    for sample in artifact.samples
                ]
                median = statistics.median(lengths)
                if median <= 1e-9:
                    continue
                relative_deviation = max(
                    abs(length - median) / median for length in lengths
                )
                max_relative_deviation = max(
                    max_relative_deviation,
                    relative_deviation,
                )

            if max_relative_deviation > 0.01:
                issues.append(
                    _issue(
                        stage=EvaluationStage.CANONICAL,
                        domain="motion",
                        code="bone_length_instability",
                        severity=IssueSeverity.ERROR,
                        message=(
                            "Canonical skeleton segment lengths vary by more than 1% "
                            "inside one motion phase."
                        ),
                        semantic_id=track.semantic_id,
                        actor_binding_id=actor_binding_id,
                        component=None,
                        start_frame=track.start_frame,
                        end_frame=track.end_frame,
                        metrics={
                            "max_bone_relative_deviation": max_relative_deviation
                        },
                    )
                )

            first = artifact.samples[0]
            last = artifact.samples[-1]
            pelvis_index = joint_index["pelvis"]
            root_displacement = _distance(
                first.joint_positions[pelvis_index],
                last.joint_positions[pelvis_index],
            )
            phase_name = track.semantic_id.lower()
            if (
                any(token in phase_name for token in _STATIONARY_HINTS)
                and root_displacement > 0.20
            ):
                issues.append(
                    _issue(
                        stage=EvaluationStage.CANONICAL,
                        domain="semantic",
                        code="stationary_phase_root_travel",
                        severity=IssueSeverity.ERROR,
                        message=(
                            "A phase whose semantics imply remaining stationary moves "
                            "the canonical pelvis more than 0.20 m."
                        ),
                        semantic_id=track.semantic_id,
                        actor_binding_id=actor_binding_id,
                        component=None,
                        start_frame=track.start_frame,
                        end_frame=track.end_frame,
                        metrics={"root_displacement_m": root_displacement},
                    )
                )

            if any(token in phase_name for token in _STOP_HINTS):
                if len(artifact.samples) >= 2:
                    tail = artifact.samples[-min(4, len(artifact.samples)) :]
                    speeds = [
                        _distance(
                            tail[index].joint_positions[pelvis_index],
                            tail[index - 1].joint_positions[pelvis_index],
                        )
                        * artifact.fps
                        for index in range(1, len(tail))
                    ]
                    ending_speed = statistics.median(speeds) if speeds else 0.0
                else:
                    ending_speed = 0.0
                if ending_speed > 0.20:
                    issues.append(
                        _issue(
                            stage=EvaluationStage.CANONICAL,
                            domain="semantic",
                            code="stop_phase_not_settled",
                            severity=IssueSeverity.ERROR,
                            message=(
                                "A stop/halt phase still has substantial pelvis speed "
                                "at the end of the phase."
                            ),
                            semantic_id=track.semantic_id,
                            actor_binding_id=actor_binding_id,
                            component=None,
                            start_frame=max(track.start_frame, track.end_frame - 4),
                            end_frame=track.end_frame,
                            metrics={"ending_speed_mps": ending_speed},
                        )
                    )

            heading_change = abs(
                _heading_delta_degrees(
                    _body_heading(first, joint_index),
                    _body_heading(last, joint_index),
                )
            )
            if (
                any(token in phase_name for token in _TURN_HINTS)
                and heading_change < 10.0
            ):
                issues.append(
                    _issue(
                        stage=EvaluationStage.CANONICAL,
                        domain="semantic",
                        code="semantic_action_missing",
                        severity=IssueSeverity.ERROR,
                        message=(
                            "A turn/pivot phase changes canonical body heading by "
                            "less than 10 degrees."
                        ),
                        semantic_id=track.semantic_id,
                        actor_binding_id=actor_binding_id,
                        component=None,
                        start_frame=track.start_frame,
                        end_frame=track.end_frame,
                        metrics={"heading_change_deg": heading_change},
                    )
                )

            for sample in artifact.samples:
                timeline.append(
                    (
                        track.start_frame + sample.frame_index,
                        track.semantic_id,
                        sample,
                    )
                )

            for foot_name in ("left_foot", "right_foot"):
                foot_index = joint_index[foot_name]
                heights = [
                    sample.joint_positions[foot_index].y
                    for sample in artifact.samples
                ]
                floor = _percentile(heights, 0.05)
                slide_speeds: list[float] = []
                for sample_index in range(1, len(artifact.samples)):
                    previous = artifact.samples[sample_index - 1].joint_positions[
                        foot_index
                    ]
                    current = artifact.samples[sample_index].joint_positions[
                        foot_index
                    ]
                    vertical_speed = abs(current.y - previous.y) * artifact.fps
                    if current.y <= floor + 0.04 and vertical_speed <= 0.12:
                        slide_speeds.append(
                            _horizontal_distance(current, previous) * artifact.fps
                        )
                if (
                    len(slide_speeds) >= 3
                    and _percentile(slide_speeds, 0.95) > 0.25
                ):
                    issues.append(
                        _issue(
                            stage=EvaluationStage.CANONICAL,
                            domain="contact",
                            code="possible_foot_slide",
                            severity=IssueSeverity.WARNING,
                            message=(
                                "Heuristic near-ground frames show substantial "
                                "horizontal foot motion. Explicit HumanML contact "
                                "channels are not yet preserved."
                            ),
                            semantic_id=track.semantic_id,
                            actor_binding_id=actor_binding_id,
                            component=foot_name,
                            start_frame=track.start_frame,
                            end_frame=track.end_frame,
                            metrics={
                                "contact_speed_p95_mps": _percentile(
                                    slide_speeds, 0.95
                                )
                            },
                        )
                    )

        timeline.sort(key=lambda item: item[0])
        for index in range(2, len(timeline) - 1):
            previous_frame, previous_phase, previous = timeline[index - 1]
            current_frame, current_phase, current = timeline[index]
            next_frame, _, following = timeline[index + 1]
            if previous_phase == current_phase:
                continue
            if current_frame != previous_frame + 1 or next_frame != current_frame + 1:
                continue
            previous_speed = (
                _distance(
                    previous.joint_positions[0],
                    timeline[index - 2][2].joint_positions[0],
                )
                * package.fps
            )
            next_speed = (
                _distance(
                    following.joint_positions[0],
                    current.joint_positions[0],
                )
                * package.fps
            )
            speed_jump = abs(next_speed - previous_speed)
            if speed_jump > 0.75:
                issues.append(
                    _issue(
                        stage=EvaluationStage.CANONICAL,
                        domain="timing",
                        code="large_phase_boundary_speed_jump",
                        severity=IssueSeverity.ERROR,
                        message=(
                            "Canonical pelvis speed changes by more than 0.75 m/s "
                            "across a phase boundary."
                        ),
                        semantic_id=current_phase,
                        actor_binding_id=actor_binding_id,
                        component=None,
                        start_frame=current_frame,
                        end_frame=current_frame + 1,
                        metrics={"speed_jump_mps": speed_jump},
                    )
                )

    source_bundle_sha256 = hashlib.sha256(
        render_performance_bundle(bundle)
    ).hexdigest()
    blocking = any(issue.severity is IssueSeverity.ERROR for issue in issues)
    report_digest = hashlib.sha256(
        (
            source_bundle_sha256
            + ":"
            + str(iteration)
            + ":"
            + ",".join(sorted(issue.issue_id for issue in issues))
        ).encode("utf-8")
    ).hexdigest()[:16]

    return EvaluationReport(
        report_id=f"evaluation-{report_digest}",
        performance_run_id=performance_run_id,
        source_bundle_sha256=source_bundle_sha256,
        iteration=iteration,
        stages_evaluated=[EvaluationStage.CANONICAL],
        issues=issues,
        accepted=not blocking,
    )
