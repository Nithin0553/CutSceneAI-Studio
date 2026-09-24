from __future__ import annotations

import math

import pytest

from cutsceneai_performance import (
    BodyGenerationRequest,
    BodyMotionArtifact,
    BodyMotionSample,
    ModelProvenance,
    NormalizedArtifact,
    PerformanceGenerationPlan,
    Quaternion,
    Vector3,
    compose_body_sequence,
    diagnose_body_composition,
)
from cutsceneai_performance.motion import CANONICAL_HUMANOID_JOINTS


_HASH = "0" * 64


def _positions(root_x: float) -> list[Vector3]:
    values = [Vector3(x=0.0, y=0.0, z=0.0) for _ in CANONICAL_HUMANOID_JOINTS]
    values[0] = Vector3(x=root_x, y=0.0, z=0.0)
    values[1] = Vector3(x=root_x - 1.0, y=0.0, z=0.0)
    values[2] = Vector3(x=root_x + 1.0, y=0.0, z=0.0)
    values[3] = Vector3(x=root_x, y=1.0, z=0.0)
    return values


def _motion(
    roots: list[float],
    pelvis_rotations: list[Quaternion],
) -> BodyMotionArtifact:
    return BodyMotionArtifact(
        fps=24,
        frame_count=len(roots),
        samples=[
            BodyMotionSample(
                frame_index=index,
                root_translation=Vector3(x=root, y=0.0, z=0.0),
                joint_rotations=[
                    pelvis_rotations[index].model_copy(deep=True)
                    for _ in CANONICAL_HUMANOID_JOINTS
                ],
                joint_positions=_positions(root),
            )
            for index, root in enumerate(roots)
        ],
    )


def _request(semantic_id: str, start: int, end: int) -> BodyGenerationRequest:
    return BodyGenerationRequest(
        semantic_id=semantic_id,
        start_frame=start,
        end_frame=end,
        prompt="Action: move Style: natural.",
        prompt_sha256=_HASH,
        configuration_sha256=_HASH,
        seed=1,
        provider="fixture",
        model="fixture",
        model_revision="r1",
        prompt_version="body-v0.1",
        actor_binding_id="actor:guard",
        source_performance_cue_id="performance:scene:beat:guard:01",
        skeleton_profile="cutsceneai-humanoid-v1",
    )


def _normalized(
    request: BodyGenerationRequest,
    motion: BodyMotionArtifact,
) -> NormalizedArtifact[BodyMotionArtifact]:
    return NormalizedArtifact(
        request_semantic_id=request.semantic_id,
        artifact=motion,
        provenance=ModelProvenance(
            provider=request.provider,
            model=request.model,
            model_revision=request.model_revision,
            prompt_sha256=request.prompt_sha256,
            configuration_sha256=request.configuration_sha256,
            seed=request.seed,
            deterministic_algorithms=True,
        ),
    )


def test_diagnostic_exposes_rotation_only_composition_and_geometry_boundary_jump() -> None:
    identity = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
    opposite = Quaternion(x=0.0, y=1.0, z=0.0, w=0.0)
    first = _request("body:scene:beat:guard:01:walk", 0, 2)
    second = _request("body:scene:beat:guard:01:stop", 2, 4)

    first_motion = _motion([0.0, 1.0], [identity, identity])
    second_motion = _motion([0.0, 0.0], [opposite, opposite])
    raw = {
        first.semantic_id: _normalized(first, first_motion),
        second.semantic_id: _normalized(second, second_motion),
    }

    # Construct the historical failure explicitly: root/pelvis quaternion is rebased/blended
    # while XYZ is left in the provider-local phase frame.
    corrupted_second = second_motion.model_copy(deep=True)
    corrupted_second.samples[0].root_translation = Vector3(x=1.0, y=0.0, z=0.0)
    corrupted_second.samples[1].root_translation = Vector3(x=1.0, y=0.0, z=0.0)
    corrupted_second.samples[0].joint_rotations = [
        identity.model_copy(deep=True) for _ in CANONICAL_HUMANOID_JOINTS
    ]

    plan = PerformanceGenerationPlan.model_construct(
        project_id="diagnostic-fixture",
        cir_fingerprint_sha256=_HASH,
        fps=24,
        duration_frames=4,
        experiment_seed=1,
        body_requests=[first, second],
        facial_requests=[],
        camera_requests=[],
    )

    diagnostic = diagnose_body_composition(
        plan,
        raw,
        {
            first.semantic_id: first_motion,
            second.semantic_id: corrupted_second,
        },
    )

    assert diagnostic.rotation_only_composition_track_count == 1
    second_metric = next(
        item for item in diagnostic.track_metrics if item.semantic_id == second.semantic_id
    )
    assert second_metric.max_joint_position_edit_m == pytest.approx(0.0)
    assert second_metric.max_pelvis_rotation_edit_deg > 1.0
    assert second_metric.composed_max_root_geometry_error_m == pytest.approx(1.0)

    assert len(diagnostic.phase_boundaries) == 1
    boundary = diagnostic.phase_boundaries[0]
    assert boundary.root_position_gap_m == pytest.approx(0.0)
    assert boundary.geometry_pelvis_gap_m == pytest.approx(1.0)
    assert boundary.max_joint_position_gap_m == pytest.approx(1.0)


def test_fixed_compositor_keeps_xyz_and_root_consistent_across_phase_boundary() -> None:
    identity = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
    opposite = Quaternion(x=0.0, y=1.0, z=0.0, w=0.0)
    first = _request("body:scene:beat:guard:01:walk-fixed", 0, 2)
    second = _request("body:scene:beat:guard:01:stop-fixed", 2, 4)

    raw = {
        first.semantic_id: _normalized(first, _motion([0.0, 1.0], [identity, identity])),
        second.semantic_id: _normalized(second, _motion([0.0, 0.0], [opposite, opposite])),
    }
    composed = compose_body_sequence(
        [first, second],
        raw,
        blend_frames=2,
    )
    plan = PerformanceGenerationPlan.model_construct(
        project_id="diagnostic-fixture",
        cir_fingerprint_sha256=_HASH,
        fps=24,
        duration_frames=4,
        experiment_seed=1,
        body_requests=[first, second],
        facial_requests=[],
        camera_requests=[],
    )

    diagnostic = diagnose_body_composition(
        plan,
        raw,
        {key: value.artifact for key, value in composed.items()},
    )

    assert diagnostic.rotation_only_composition_track_count == 0
    assert diagnostic.max_composed_root_geometry_error_m == pytest.approx(0.0)
    boundary = diagnostic.phase_boundaries[0]
    assert boundary.root_position_gap_m > 0.0
    assert boundary.geometry_pelvis_gap_m == pytest.approx(boundary.root_position_gap_m)
    assert boundary.max_joint_position_gap_m is not None
    assert boundary.max_joint_position_gap_m >= boundary.geometry_pelvis_gap_m
    assert boundary.boundary_geometry_velocity_mps is not None
    assert boundary.boundary_geometry_velocity_mps > 0.0


def test_diagnostic_reports_geometry_orientation_consistency_for_unmodified_motion() -> None:
    identity = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
    request = _request("body:scene:beat:guard:01:hold", 0, 2)
    motion = _motion([0.0, 0.0], [identity, identity])
    raw = {request.semantic_id: _normalized(request, motion)}
    plan = PerformanceGenerationPlan.model_construct(
        project_id="diagnostic-fixture",
        cir_fingerprint_sha256=_HASH,
        fps=24,
        duration_frames=2,
        experiment_seed=1,
        body_requests=[request],
        facial_requests=[],
        camera_requests=[],
    )

    diagnostic = diagnose_body_composition(
        plan,
        raw,
        {request.semantic_id: motion},
    )
    metric = diagnostic.track_metrics[0]

    assert metric.raw_max_root_geometry_error_m == pytest.approx(0.0)
    assert metric.composed_max_root_geometry_error_m == pytest.approx(0.0)
    assert metric.raw_max_forward_error_deg == pytest.approx(0.0)
    assert metric.composed_max_forward_error_deg == pytest.approx(0.0)
    assert metric.raw_max_up_error_deg == pytest.approx(0.0)
    assert metric.composed_max_up_error_deg == pytest.approx(0.0)


def test_diagnostic_detects_hidden_zero_step_freeze_at_phase_boundary() -> None:
    identity = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
    first = _request("body:scene:beat:guard:01:walk-freeze", 0, 3)
    second = _request("body:scene:beat:guard:01:stop-freeze", 3, 6)

    first_motion = _motion([0.0, 0.5, 1.0], [identity, identity, identity])
    second_motion = _motion([1.0, 1.0, 1.0], [identity, identity, identity])
    raw = {
        first.semantic_id: _normalized(first, first_motion),
        second.semantic_id: _normalized(second, second_motion),
    }
    plan = PerformanceGenerationPlan.model_construct(
        project_id="diagnostic-fixture",
        cir_fingerprint_sha256=_HASH,
        fps=24,
        duration_frames=6,
        experiment_seed=1,
        body_requests=[first, second],
        facial_requests=[],
        camera_requests=[],
    )

    diagnostic = diagnose_body_composition(
        plan,
        raw,
        {
            first.semantic_id: first_motion,
            second.semantic_id: second_motion,
        },
    )
    boundary = diagnostic.phase_boundaries[0]

    assert boundary.geometry_pelvis_gap_m == pytest.approx(0.0)
    assert boundary.previous_geometry_velocity_mps == pytest.approx(12.0)
    assert boundary.boundary_geometry_velocity_mps == pytest.approx(0.0)
    assert boundary.current_geometry_velocity_mps == pytest.approx(0.0)
    assert boundary.previous_to_boundary_velocity_jump_mps == pytest.approx(12.0)
    assert boundary.boundary_to_current_velocity_jump_mps == pytest.approx(0.0)
    assert diagnostic.max_previous_to_boundary_velocity_jump_mps == pytest.approx(12.0)


def test_fixed_compositor_reduces_boundary_velocity_jump_without_freeze() -> None:
    identity = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
    first = _request("body:scene:beat:guard:01:fast-fixed", 0, 3)
    second = _request("body:scene:beat:guard:01:slow-fixed", 3, 6)

    raw = {
        first.semantic_id: _normalized(
            first,
            _motion([0.0, 0.5, 1.0], [identity, identity, identity]),
        ),
        second.semantic_id: _normalized(
            second,
            _motion([0.0, 0.1, 0.2], [identity, identity, identity]),
        ),
    }
    composed = compose_body_sequence(
        [first, second],
        raw,
        blend_frames=3,
    )
    plan = PerformanceGenerationPlan.model_construct(
        project_id="diagnostic-fixture",
        cir_fingerprint_sha256=_HASH,
        fps=24,
        duration_frames=6,
        experiment_seed=1,
        body_requests=[first, second],
        facial_requests=[],
        camera_requests=[],
    )

    diagnostic = diagnose_body_composition(
        plan,
        raw,
        {key: value.artifact for key, value in composed.items()},
    )
    boundary = diagnostic.phase_boundaries[0]

    assert boundary.previous_geometry_velocity_mps == pytest.approx(12.0)
    assert boundary.boundary_geometry_velocity_mps == pytest.approx(8.8)
    assert boundary.current_geometry_velocity_mps == pytest.approx(5.6)
    assert boundary.previous_to_boundary_velocity_jump_mps == pytest.approx(3.2)
    assert boundary.boundary_to_current_velocity_jump_mps == pytest.approx(3.2)
    assert boundary.boundary_geometry_velocity_mps > 0.0
