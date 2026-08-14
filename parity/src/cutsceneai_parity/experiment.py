from __future__ import annotations

from collections.abc import Sequence

from .experiment_models import (
    EngineRunEvidence,
    EvidenceOrigin,
    ExperimentIssue,
    ExperimentMetricSummary,
    ExperimentMode,
    ExperimentScene,
    GeneratedArtifactDigests,
    GeneratedPerformanceAttemptEvidence,
    GeneratedPerformanceExperimentPlan,
    GeneratedPerformanceExperimentReport,
    PerformanceModality,
)
from .models import EngineName, IssueSeverity


AttemptKey = tuple[str, int, int]


def _issue(
    issues: list[ExperimentIssue],
    *,
    code: str,
    message: str,
    severity: IssueSeverity = IssueSeverity.ERROR,
    key: AttemptKey | None = None,
) -> None:
    issues.append(
        ExperimentIssue(
            severity=severity,
            code=code,
            message=message,
            scene_id=None if key is None else key[0],
            seed=None if key is None else key[1],
            repeat_index=None if key is None else key[2],
        )
    )


def _attempt_key(attempt: GeneratedPerformanceAttemptEvidence) -> AttemptKey:
    return attempt.scene_id, attempt.seed, attempt.repeat_index


def _expected_attempt_keys(
    plan: GeneratedPerformanceExperimentPlan,
) -> set[AttemptKey]:
    keys = {(scene.scene_id, seed, 1) for scene in plan.scenes for seed in plan.seeds}
    for case in plan.repeatability_cases:
        keys.update(
            (case.scene_id, case.seed, repeat_index)
            for repeat_index in range(2, plan.repeat_runs + 1)
        )
    return keys


def _expected_counts(scene: ExperimentScene) -> dict[PerformanceModality, int]:
    return {
        PerformanceModality.BODY: scene.expected_body_sections,
        PerformanceModality.FACIAL: scene.expected_facial_sections,
        PerformanceModality.CAMERA: scene.expected_camera_sections,
        PerformanceModality.AUDIO: scene.expected_audio_sections,
    }


def _artifact_hashes(
    artifacts: GeneratedArtifactDigests,
) -> dict[PerformanceModality, list[str]]:
    return {
        PerformanceModality.BODY: artifacts.body_motion_sha256s,
        PerformanceModality.FACIAL: artifacts.facial_curves_sha256s,
        PerformanceModality.CAMERA: artifacts.camera_curves_sha256s,
        PerformanceModality.AUDIO: artifacts.audio_sha256s,
    }


def _engine_index(
    attempt: GeneratedPerformanceAttemptEvidence,
) -> dict[EngineName, EngineRunEvidence]:
    return {item.engine: item for item in attempt.engines}


def _native_realization_complete(
    attempt: GeneratedPerformanceAttemptEvidence,
    scene: ExperimentScene,
    target_engines: set[EngineName],
) -> bool:
    if not attempt.generation_completed or attempt.artifacts is None:
        return False
    engines = _engine_index(attempt)
    if set(engines) != target_engines:
        return False
    expected_counts = _expected_counts(scene)
    artifact_hashes = _artifact_hashes(attempt.artifacts)
    for evidence in engines.values():
        if evidence.source_bundle_sha256 != attempt.artifacts.source_bundle_sha256:
            return False
        if any(
            value is None
            for value in (
                evidence.mapping_sha256,
                evidence.editor_log_sha256,
                evidence.readback_sha256,
                evidence.timeline_fingerprint_sha256,
                evidence.render_manifest_sha256,
            )
        ):
            return False
        if not all(
            (
                evidence.import_completed,
                evidence.saved,
                evidence.restarted,
                evidence.readback_completed,
                evidence.render_completed,
            )
        ):
            return False
        if evidence.rendered_frame_count != scene.expected_frame_count:
            return False
        if evidence.errors or evidence.missing_realization_warnings:
            return False
        modalities = {item.modality: item for item in evidence.modalities}
        if set(modalities) != set(PerformanceModality):
            return False
        for modality, expected_count in expected_counts.items():
            realization = modalities[modality]
            if (
                realization.expected_section_count != expected_count
                or realization.realized_section_count != expected_count
                or realization.placeholder_section_count != 0
                or realization.source_artifact_sha256s != artifact_hashes[modality]
                or len(realization.target_asset_refs) != expected_count
            ):
                return False
    return True


def _portability_complete(
    attempt: GeneratedPerformanceAttemptEvidence,
    scene: ExperimentScene,
    plan: GeneratedPerformanceExperimentPlan,
) -> bool:
    if not attempt.generation_completed or attempt.artifacts is None:
        return False
    engines = _engine_index(attempt)
    target_engines = set(plan.target_engines)
    if set(engines) != target_engines:
        return False
    if any(
        evidence.source_bundle_sha256 != attempt.artifacts.source_bundle_sha256
        or evidence.mapping_sha256 is None
        for evidence in engines.values()
    ):
        return False
    report = attempt.parity_report
    if report is None:
        return False
    requirements = report.requirements
    if (
        report.project_id != scene.project_id
        or report.cir_fingerprint_sha256 != scene.cir_fingerprint_sha256
        or report.tolerance_frames != plan.tolerance_frames
        or not report.equivalent
        or report.error_count != 0
        or report.warning_count != 0
        or not all(
            (
                requirements.animation,
                requirements.facial,
                requirements.camera,
                requirements.audio,
            )
        )
        or len(requirements.engines) != len(target_engines)
        or set(requirements.engines) != target_engines
    ):
        return False
    summaries = {item.engine: item for item in report.readbacks}
    if set(summaries) != target_engines:
        return False
    for engine, summary in summaries.items():
        engine_evidence = engines[engine]
        if (
            summary.engine_version != engine_evidence.engine_version
            or summary.animation_section_count != scene.expected_body_sections
            or summary.facial_section_count != scene.expected_facial_sections
            or summary.camera_section_count != scene.expected_camera_sections
            or summary.audio_section_count != scene.expected_audio_sections
        ):
            return False
    return True


def _reliable_first_pass(
    attempt: GeneratedPerformanceAttemptEvidence,
    scene: ExperimentScene,
    plan: GeneratedPerformanceExperimentPlan,
) -> bool:
    return (
        attempt.repeat_index == 1
        and attempt.clean_run
        and attempt.manual_repair_count == 0
        and attempt.failure_code is None
        and _native_realization_complete(attempt, scene, set(plan.target_engines))
        and _portability_complete(attempt, scene, plan)
    )


def _repeatability_complete(
    attempts: Sequence[GeneratedPerformanceAttemptEvidence],
    target_engines: set[EngineName],
) -> bool:
    if len(attempts) != 3 or any(attempt.artifacts is None for attempt in attempts):
        return False
    first = attempts[0]
    if any(
        not attempt.clean_run
        or attempt.manual_repair_count != 0
        or attempt.failure_code is not None
        for attempt in attempts
    ):
        return False
    first_artifacts = first.artifacts
    if any(attempt.artifacts != first_artifacts for attempt in attempts[1:]):
        return False
    first_engines = _engine_index(first)
    if set(first_engines) != target_engines:
        return False
    for attempt in attempts[1:]:
        engines = _engine_index(attempt)
        if set(engines) != target_engines:
            return False
        for engine in target_engines:
            if (
                engines[engine].mapping_sha256 != first_engines[engine].mapping_sha256
                or engines[engine].timeline_fingerprint_sha256
                != first_engines[engine].timeline_fingerprint_sha256
            ):
                return False
    return True


def _metric(
    *,
    planned: int,
    observed: int,
    passed: int,
    minimum_rate: float,
) -> ExperimentMetricSummary:
    rate = 0.0 if planned == 0 else passed / planned
    return ExperimentMetricSummary(
        planned_count=planned,
        observed_count=observed,
        passed_count=passed,
        rate=rate,
        minimum_rate=minimum_rate,
        target_met=observed == planned and rate >= minimum_rate,
    )


def verify_generated_performance_experiment(
    plan: GeneratedPerformanceExperimentPlan,
    attempts: Sequence[GeneratedPerformanceAttemptEvidence],
) -> GeneratedPerformanceExperimentReport:
    """Aggregate deterministic generated-performance acceptance evidence."""

    issues: list[ExperimentIssue] = []
    expected_keys = _expected_attempt_keys(plan)
    scene_by_id = {scene.scene_id: scene for scene in plan.scenes}
    attempt_by_key: dict[AttemptKey, GeneratedPerformanceAttemptEvidence] = {}
    evidence_complete = True

    for attempt in attempts:
        key = _attempt_key(attempt)
        if key in attempt_by_key:
            evidence_complete = False
            _issue(
                issues,
                code="duplicate_attempt",
                message="More than one evidence record uses this attempt key.",
                key=key,
            )
            continue
        attempt_by_key[key] = attempt
        if key not in expected_keys:
            evidence_complete = False
            _issue(
                issues,
                code="unexpected_attempt",
                message="Evidence record is not part of the experiment plan.",
                key=key,
            )
            continue
        scene = scene_by_id[attempt.scene_id]
        if (
            attempt.project_id != scene.project_id
            or attempt.cir_fingerprint_sha256 != scene.cir_fingerprint_sha256
        ):
            evidence_complete = False
            _issue(
                issues,
                code="scene_identity_mismatch",
                message="Attempt project or canonical CIR fingerprint differs from the plan.",
                key=key,
            )
        if plan.mode is ExperimentMode.PAPER and (
            attempt.evidence_origin is not EvidenceOrigin.REAL
        ):
            evidence_complete = False
            _issue(
                issues,
                code="synthetic_paper_evidence",
                message="Paper-mode evidence must come from real inference and editors.",
                key=key,
            )

    for key in sorted(expected_keys - attempt_by_key.keys()):
        evidence_complete = False
        _issue(
            issues,
            code="missing_attempt",
            message="The experiment plan has no evidence record for this attempt.",
            key=key,
        )

    expected_attempts = {
        key: attempt_by_key[key] for key in expected_keys & attempt_by_key.keys()
    }
    target_engines = set(plan.target_engines)
    native_results: dict[AttemptKey, bool] = {}
    portability_results: dict[AttemptKey, bool] = {}
    for key, attempt in expected_attempts.items():
        scene = scene_by_id[key[0]]
        native_results[key] = _native_realization_complete(
            attempt, scene, target_engines
        )
        portability_results[key] = _portability_complete(attempt, scene, plan)
        if not attempt.generation_completed:
            _issue(
                issues,
                severity=IssueSeverity.WARNING,
                code="generation_failed",
                message=f"Generation failed with code '{attempt.failure_code}'.",
                key=key,
            )
        if attempt.manual_repair_count or not attempt.clean_run:
            _issue(
                issues,
                severity=IssueSeverity.WARNING,
                code="manual_or_unclean_run",
                message="Attempt was not a clean, zero-repair run.",
                key=key,
            )
        if not native_results[key]:
            _issue(
                issues,
                severity=IssueSeverity.WARNING,
                code="native_realization_failed",
                message="Native import, restart, readback, modality, or render evidence failed.",
                key=key,
            )
        if not portability_results[key]:
            _issue(
                issues,
                severity=IssueSeverity.WARNING,
                code="portability_failed",
                message="Both engines did not prove strict parity from one unchanged bundle.",
                key=key,
            )

    first_pass_keys = {
        (scene.scene_id, seed, 1) for scene in plan.scenes for seed in plan.seeds
    }
    first_pass_observed = first_pass_keys & expected_attempts.keys()
    reliable_count = sum(
        _reliable_first_pass(expected_attempts[key], scene_by_id[key[0]], plan)
        for key in first_pass_observed
    )
    reliability = _metric(
        planned=len(first_pass_keys),
        observed=len(first_pass_observed),
        passed=reliable_count,
        minimum_rate=plan.minimum_first_pass_success_rate,
    )

    repeatability_passed = 0
    repeatability_observed = 0
    for case in plan.repeatability_cases:
        keys = [
            (case.scene_id, case.seed, repeat_index)
            for repeat_index in range(1, plan.repeat_runs + 1)
        ]
        if all(key in expected_attempts for key in keys):
            repeatability_observed += 1
            case_attempts = [expected_attempts[key] for key in keys]
            if all(
                native_results[key] and portability_results[key] for key in keys
            ) and _repeatability_complete(case_attempts, target_engines):
                repeatability_passed += 1
            else:
                _issue(
                    issues,
                    severity=IssueSeverity.WARNING,
                    code="repeatability_failed",
                    message=(
                        "Three clean same-seed runs did not preserve artifact, mapping, "
                        "and timeline fingerprints."
                    ),
                    key=keys[0],
                )
    repeatability = _metric(
        planned=len(plan.repeatability_cases),
        observed=repeatability_observed,
        passed=repeatability_passed,
        minimum_rate=plan.minimum_repeatability_rate,
    )
    portability = _metric(
        planned=len(expected_keys),
        observed=len(expected_attempts),
        passed=sum(portability_results.values()),
        minimum_rate=plan.minimum_portability_rate,
    )
    native_realization = _metric(
        planned=len(expected_keys),
        observed=len(expected_attempts),
        passed=sum(native_results.values()),
        minimum_rate=plan.minimum_native_realization_rate,
    )
    gate_passed = evidence_complete and all(
        metric.target_met
        for metric in (
            reliability,
            repeatability,
            portability,
            native_realization,
        )
    )
    publishable = plan.mode is ExperimentMode.PAPER and gate_passed
    return GeneratedPerformanceExperimentReport(
        experiment_id=plan.experiment_id,
        mode=plan.mode,
        evidence_complete=evidence_complete,
        gate_passed=gate_passed,
        publishable=publishable,
        reliability=reliability,
        repeatability=repeatability,
        portability=portability,
        native_realization=native_realization,
        issue_count=len(issues),
        issues=issues,
    )
