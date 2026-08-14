import json

from .experiment_models import (
    GeneratedPerformanceAttemptEvidence,
    GeneratedPerformanceExperimentPlan,
    GeneratedPerformanceExperimentReport,
)
from .models import EngineTimelineReadback, ParityReport, TimelineSemantics


def _render(
    value: (
        TimelineSemantics
        | EngineTimelineReadback
        | ParityReport
        | GeneratedPerformanceExperimentPlan
        | GeneratedPerformanceAttemptEvidence
        | GeneratedPerformanceExperimentReport
    ),
) -> str:
    return json.dumps(value.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"


def render_timeline_semantics(semantics: TimelineSemantics) -> str:
    return _render(semantics)


def render_engine_readback(readback: EngineTimelineReadback) -> str:
    return _render(readback)


def render_parity_report(report: ParityReport) -> str:
    return _render(report)


def render_generated_performance_experiment_plan(
    plan: GeneratedPerformanceExperimentPlan,
) -> str:
    return _render(plan)


def render_generated_performance_attempt_evidence(
    evidence: GeneratedPerformanceAttemptEvidence,
) -> str:
    return _render(evidence)


def render_generated_performance_experiment_report(
    report: GeneratedPerformanceExperimentReport,
) -> str:
    return _render(report)
