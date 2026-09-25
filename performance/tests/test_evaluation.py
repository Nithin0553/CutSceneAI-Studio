from __future__ import annotations

import pytest
from pydantic import ValidationError

from cutsceneai_performance import (
    EvaluationReport,
    EvaluationStage,
    IssueSeverity,
    PerformanceIssue,
    RepairActionKind,
    plan_repairs,
    stable_issue_id,
)


def _issue(
    *,
    code: str,
    stage: EvaluationStage,
    severity: IssueSeverity = IssueSeverity.ERROR,
    semantic_id: str | None = "body:guard_walk",
    start_frame: int | None = 0,
    end_frame: int | None = 24,
) -> PerformanceIssue:
    return PerformanceIssue(
        issue_id=stable_issue_id(
            stage=stage,
            code=code,
            semantic_id=semantic_id,
            actor_binding_id="actor:guard",
            start_frame=start_frame,
            end_frame=end_frame,
        ),
        stage=stage,
        domain="motion" if stage is EvaluationStage.CANONICAL else "retargeting",
        code=code,
        severity=severity,
        message=f"fixture {code}",
        semantic_id=semantic_id,
        actor_binding_id="actor:guard",
        start_frame=start_frame,
        end_frame=end_frame,
    )


def _report(issues: list[PerformanceIssue]) -> EvaluationReport:
    return EvaluationReport(
        report_id="evaluation-fixture",
        performance_run_id="run-fixture",
        source_bundle_sha256="a" * 64,
        iteration=0,
        stages_evaluated=[EvaluationStage.CANONICAL, EvaluationStage.ENGINE],
        issues=issues,
        accepted=not any(
            issue.severity is IssueSeverity.ERROR for issue in issues
        ),
    )


def test_stable_issue_id_is_deterministic_and_scope_sensitive() -> None:
    first = stable_issue_id(
        stage=EvaluationStage.CANONICAL,
        code="possible_foot_slide",
        semantic_id="body:guard_walk",
        actor_binding_id="actor:guard",
        start_frame=10,
        end_frame=20,
    )
    second = stable_issue_id(
        stage=EvaluationStage.CANONICAL,
        code="possible_foot_slide",
        semantic_id="body:guard_walk",
        actor_binding_id="actor:guard",
        start_frame=10,
        end_frame=20,
    )
    changed = stable_issue_id(
        stage=EvaluationStage.CANONICAL,
        code="possible_foot_slide",
        semantic_id="body:guard_walk",
        actor_binding_id="actor:guard",
        start_frame=11,
        end_frame=20,
    )
    left = stable_issue_id(
        stage=EvaluationStage.CANONICAL,
        code="possible_foot_slide",
        semantic_id="body:guard_walk",
        actor_binding_id="actor:guard",
        component="left_foot",
        start_frame=10,
        end_frame=20,
    )
    right = stable_issue_id(
        stage=EvaluationStage.CANONICAL,
        code="possible_foot_slide",
        semantic_id="body:guard_walk",
        actor_binding_id="actor:guard",
        component="right_foot",
        start_frame=10,
        end_frame=20,
    )

    assert first == second
    assert first != changed
    assert left != right


def test_evaluation_report_accepts_warnings_but_rejects_error_acceptance() -> None:
    warning = _issue(
        code="possible_foot_slide",
        stage=EvaluationStage.CANONICAL,
        severity=IssueSeverity.WARNING,
    )
    report = _report([warning])
    assert report.accepted is True

    with pytest.raises(ValidationError, match="accepted must be true"):
        EvaluationReport(
            report_id="invalid",
            performance_run_id="run-fixture",
            source_bundle_sha256="b" * 64,
            iteration=0,
            stages_evaluated=[EvaluationStage.CANONICAL],
            issues=[_issue(
                code="bone_length_instability",
                stage=EvaluationStage.CANONICAL,
            )],
            accepted=True,
        )


def test_repair_planner_prefers_targeted_no_inference_repairs() -> None:
    report = _report(
        [
            _issue(
                code="possible_foot_slide",
                stage=EvaluationStage.CANONICAL,
            ),
            _issue(
                code="large_phase_boundary_speed_jump",
                stage=EvaluationStage.CANONICAL,
                semantic_id="body:guard_stop",
                start_frame=120,
                end_frame=124,
            ),
            _issue(
                code="retarget_deformation",
                stage=EvaluationStage.ENGINE,
            ),
        ]
    )

    plan = plan_repairs(report)
    kinds = {action.kind for action in plan.actions}

    assert RepairActionKind.STABILIZE_CONTACT in kinds
    assert RepairActionKind.SMOOTH_TRANSITION in kinds
    assert RepairActionKind.RETARGET_CHAIN in kinds
    assert plan.requires_fresh_inference is False
    assert plan.requires_engine is True
    retarget = next(
        action for action in plan.actions
        if action.kind is RepairActionKind.RETARGET_CHAIN
    )
    assert retarget.requires_engine is True
    assert retarget.engine_agnostic is False


def test_semantic_failure_is_the_only_fixture_that_requests_fresh_inference() -> None:
    report = _report(
        [
            _issue(
                code="semantic_action_missing",
                stage=EvaluationStage.SEMANTIC,
            )
        ]
    )

    plan = plan_repairs(report)

    assert len(plan.actions) == 1
    assert plan.actions[0].kind is RepairActionKind.REGENERATE_SEGMENT
    assert plan.actions[0].requires_fresh_inference is True
    assert plan.requires_fresh_inference is True


def test_unknown_error_falls_back_to_engine_edit_without_regeneration() -> None:
    report = _report(
        [
            _issue(
                code="unknown_visual_failure",
                stage=EvaluationStage.RENDER,
            )
        ]
    )

    plan = plan_repairs(report)

    assert len(plan.actions) == 1
    action = plan.actions[0]
    assert action.kind is RepairActionKind.ENGINE_ANIMATION_EDIT
    assert action.requires_engine is True
    assert action.engine_agnostic is False
    assert action.requires_fresh_inference is False
