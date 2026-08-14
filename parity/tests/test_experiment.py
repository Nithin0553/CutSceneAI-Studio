import hashlib
import json
from pathlib import Path

from pydantic import ValidationError
import pytest

from cutsceneai_cir import Project
from cutsceneai_parity import (
    EngineName,
    EngineRunEvidence,
    EngineTimelineReadback,
    EvidenceOrigin,
    ExperimentMode,
    ExperimentScene,
    GeneratedArtifactDigests,
    GeneratedPerformanceAttemptEvidence,
    GeneratedPerformanceExperimentPlan,
    ModalityRealizationEvidence,
    PerformanceModality,
    ReadbackEvidence,
    RealizedSection,
    RepeatabilityCase,
    compile_semantics,
    render_generated_performance_attempt_evidence,
    render_generated_performance_experiment_plan,
    verify_generated_performance_experiment,
    verify_readbacks,
)
from cutsceneai_parity.cli import main


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _strict_report(project: Project):
    semantics = compile_semantics(project)
    scene = semantics.scenes[0]
    evidence = ReadbackEvidence(
        animation_sections=[
            RealizedSection(
                semantic_id=cue.cue_id,
                actor_binding_id=cue.actor_binding_id,
                start_frame=cue.start_frame,
                end_frame=cue.end_frame,
                asset_ref=f"body:{cue.cue_id}",
            )
            for cue in scene.performance_cues
        ],
        facial_sections=[
            RealizedSection(
                semantic_id=cue.cue_id,
                actor_binding_id=cue.actor_binding_id,
                start_frame=cue.start_frame,
                end_frame=cue.end_frame,
                asset_ref=f"face:{cue.cue_id}",
            )
            for cue in scene.performance_cues
        ],
        camera_sections=[
            RealizedSection(
                semantic_id=cut.cut_id,
                start_frame=cut.start_frame,
                end_frame=cut.end_frame,
                asset_ref=f"camera:{cut.cut_id}",
            )
            for cut in scene.camera_cuts
        ],
        audio_sections=[
            RealizedSection(
                semantic_id=cue.cue_id,
                actor_binding_id=cue.actor_binding_id,
                start_frame=cue.start_frame,
                end_frame=cue.start_frame + 24,
                asset_ref=f"audio:{cue.cue_id}",
            )
            for cue in scene.dialogue_cues
        ],
    )
    readbacks = [
        EngineTimelineReadback(
            engine=EngineName.UNREAL,
            engine_version="5.8.0",
            adapter_version="0.6.0",
            timeline_asset="/Game/CutSceneAI/Sequences/LS_SceneMeeting",
            semantics=semantics.model_copy(deep=True),
            evidence=evidence.model_copy(deep=True),
        ),
        EngineTimelineReadback(
            engine=EngineName.UNITY,
            engine_version="6000.0",
            adapter_version="0.1.0",
            timeline_asset="Assets/CutSceneAI/Timelines/TL_SceneMeeting.playable",
            semantics=semantics.model_copy(deep=True),
            evidence=evidence.model_copy(deep=True),
        ),
    ]
    return verify_readbacks(
        project,
        readbacks,
        tolerance_frames=1,
        require_animation=True,
        require_facial=True,
        require_camera=True,
        require_audio=True,
        required_engines=(EngineName.UNREAL, EngineName.UNITY),
    )


def _scene(project: Project) -> ExperimentScene:
    semantics = compile_semantics(project)
    scene = semantics.scenes[0]
    return ExperimentScene(
        scene_id=scene.source_scene_id,
        project_id=semantics.project_id,
        cir_fingerprint_sha256=semantics.cir_fingerprint_sha256,
        expected_frame_count=scene.duration_frames,
        expected_body_sections=len(scene.performance_cues),
        expected_facial_sections=len(scene.performance_cues),
        expected_camera_sections=len(scene.camera_cuts),
        expected_audio_sections=len(scene.dialogue_cues),
    )


def _plan(project: Project) -> GeneratedPerformanceExperimentPlan:
    scene = _scene(project)
    return GeneratedPerformanceExperimentPlan(
        experiment_id="generated-performance-harness-v0.1",
        mode=ExperimentMode.HARNESS,
        scenes=[scene],
        seeds=[17],
        repeatability_cases=[RepeatabilityCase(scene_id=scene.scene_id, seed=17)],
    )


def _artifacts() -> GeneratedArtifactDigests:
    return GeneratedArtifactDigests(
        source_bundle_sha256=_sha("bundle"),
        generation_plan_sha256=_sha("plan"),
        performance_package_sha256=_sha("package"),
        body_motion_sha256s=sorted(_sha(f"body:{index}") for index in range(4)),
        facial_curves_sha256s=sorted(_sha(f"face:{index}") for index in range(4)),
        camera_curves_sha256s=sorted(_sha(f"camera:{index}") for index in range(4)),
        audio_sha256s=sorted(_sha(f"audio:{index}") for index in range(2)),
    )


def _modality_evidence(
    engine: EngineName,
    modality: PerformanceModality,
    expected_count: int,
    hashes: list[str],
) -> ModalityRealizationEvidence:
    return ModalityRealizationEvidence(
        modality=modality,
        expected_section_count=expected_count,
        realized_section_count=expected_count,
        placeholder_section_count=0,
        source_artifact_sha256s=hashes,
        target_asset_refs=sorted(
            f"{engine.value}:{modality.value}:{index}"
            for index in range(expected_count)
        ),
    )


def _engine_evidence(
    engine: EngineName,
    scene: ExperimentScene,
    artifacts: GeneratedArtifactDigests,
) -> EngineRunEvidence:
    counts = {
        PerformanceModality.BODY: scene.expected_body_sections,
        PerformanceModality.FACIAL: scene.expected_facial_sections,
        PerformanceModality.CAMERA: scene.expected_camera_sections,
        PerformanceModality.AUDIO: scene.expected_audio_sections,
    }
    hashes = {
        PerformanceModality.BODY: artifacts.body_motion_sha256s,
        PerformanceModality.FACIAL: artifacts.facial_curves_sha256s,
        PerformanceModality.CAMERA: artifacts.camera_curves_sha256s,
        PerformanceModality.AUDIO: artifacts.audio_sha256s,
    }
    return EngineRunEvidence(
        engine=engine,
        engine_version="5.8.0" if engine is EngineName.UNREAL else "6000.0",
        source_bundle_sha256=artifacts.source_bundle_sha256,
        mapping_sha256=_sha(f"mapping:{engine.value}"),
        editor_log_sha256=_sha(f"log:{engine.value}"),
        readback_sha256=_sha(f"readback:{engine.value}"),
        timeline_fingerprint_sha256=_sha(f"timeline:{engine.value}"),
        render_manifest_sha256=_sha(f"render:{engine.value}"),
        rendered_frame_count=scene.expected_frame_count,
        import_completed=True,
        saved=True,
        restarted=True,
        readback_completed=True,
        render_completed=True,
        modalities=[
            _modality_evidence(engine, modality, counts[modality], hashes[modality])
            for modality in PerformanceModality
        ],
    )


def _attempt(
    project: Project,
    repeat_index: int,
) -> GeneratedPerformanceAttemptEvidence:
    scene = _scene(project)
    artifacts = _artifacts()
    return GeneratedPerformanceAttemptEvidence(
        evidence_origin=EvidenceOrigin.SYNTHETIC,
        scene_id=scene.scene_id,
        project_id=scene.project_id,
        cir_fingerprint_sha256=scene.cir_fingerprint_sha256,
        seed=17,
        repeat_index=repeat_index,
        clean_run=True,
        manual_repair_count=0,
        generation_completed=True,
        artifacts=artifacts,
        engines=[
            _engine_evidence(EngineName.UNREAL, scene, artifacts),
            _engine_evidence(EngineName.UNITY, scene, artifacts),
        ],
        parity_report=_strict_report(project),
    )


def test_complete_harness_evidence_passes_but_is_not_publishable(
    cir_project: Project,
) -> None:
    report = verify_generated_performance_experiment(
        _plan(cir_project), [_attempt(cir_project, index) for index in range(1, 4)]
    )

    assert report.evidence_complete is True
    assert report.gate_passed is True
    assert report.publishable is False
    assert report.issue_count == 0
    assert report.reliability.model_dump() == {
        "planned_count": 1,
        "observed_count": 1,
        "passed_count": 1,
        "rate": 1.0,
        "minimum_rate": 1.0,
        "target_met": True,
    }
    assert report.repeatability.passed_count == 1
    assert report.portability.passed_count == 3
    assert report.native_realization.passed_count == 3


def test_experiment_cli_writes_deterministic_report(
    cir_project: Project, tmp_path: Path
) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        render_generated_performance_experiment_plan(_plan(cir_project)),
        encoding="utf-8",
    )
    command = ["experiment-verify", str(plan_path)]
    for repeat_index in range(1, 4):
        path = tmp_path / f"attempt-{repeat_index}.json"
        path.write_text(
            render_generated_performance_attempt_evidence(
                _attempt(cir_project, repeat_index)
            ),
            encoding="utf-8",
        )
        command.extend(["--attempt", str(path)])
    output = tmp_path / "report.json"
    command.extend(["--output", str(output)])

    assert main(command) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["gate_passed"] is True
    assert payload["publishable"] is False


def test_missing_duplicate_and_unexpected_attempts_fail_evidence_completeness(
    cir_project: Project,
) -> None:
    first = _attempt(cir_project, 1)
    unexpected = first.model_copy(
        update={"scene_id": "scene:unexpected", "repeat_index": 2}, deep=True
    )
    report = verify_generated_performance_experiment(
        _plan(cir_project), [first, first.model_copy(deep=True), unexpected]
    )

    assert report.evidence_complete is False
    assert report.gate_passed is False
    assert {item.code for item in report.issues} >= {
        "duplicate_attempt",
        "unexpected_attempt",
        "missing_attempt",
    }


def test_failed_generation_is_counted_without_erasing_the_denominator(
    cir_project: Project,
) -> None:
    scene = _scene(cir_project)
    failed = GeneratedPerformanceAttemptEvidence(
        evidence_origin=EvidenceOrigin.SYNTHETIC,
        scene_id=scene.scene_id,
        project_id=scene.project_id,
        cir_fingerprint_sha256=scene.cir_fingerprint_sha256,
        seed=17,
        repeat_index=1,
        clean_run=True,
        manual_repair_count=0,
        generation_completed=False,
        failure_code="provider_timeout",
    )
    report = verify_generated_performance_experiment(
        _plan(cir_project),
        [failed, _attempt(cir_project, 2), _attempt(cir_project, 3)],
    )

    assert report.evidence_complete is True
    assert report.gate_passed is False
    assert report.reliability.planned_count == 1
    assert report.reliability.passed_count == 0
    assert report.native_realization.passed_count == 2
    assert report.portability.passed_count == 2
    assert report.repeatability.passed_count == 0
    assert {item.code for item in report.issues} >= {
        "generation_failed",
        "native_realization_failed",
        "portability_failed",
        "repeatability_failed",
    }


def test_native_portability_and_repeatability_fail_independently(
    cir_project: Project,
) -> None:
    attempts = [_attempt(cir_project, index) for index in range(1, 4)]
    attempts[0].engines[0].rendered_frame_count -= 1
    attempts[1].parity_report.requirements.camera = False  # type: ignore[union-attr]
    attempts[2].engines[0].timeline_fingerprint_sha256 = _sha("changed")

    report = verify_generated_performance_experiment(_plan(cir_project), attempts)

    assert report.native_realization.passed_count == 2
    assert report.portability.passed_count == 2
    assert report.repeatability.passed_count == 0
    assert report.reliability.passed_count == 0
    assert report.gate_passed is False


@pytest.mark.parametrize(
    "violation",
    [
        "missing_engine",
        "wrong_bundle",
        "missing_digest",
        "lifecycle",
        "editor_errors",
        "missing_modality",
        "modality_mismatch",
        "missing_parity_report",
        "missing_parity_summary",
        "parity_summary_mismatch",
    ],
)
def test_native_evidence_rejects_incomplete_retained_proof(
    cir_project: Project, violation: str
) -> None:
    attempts = [_attempt(cir_project, index) for index in range(1, 4)]
    attempt = attempts[0]
    if violation == "missing_engine":
        attempt.engines.pop()
    elif violation == "wrong_bundle":
        attempt.engines[0].source_bundle_sha256 = _sha("wrong-bundle")
    elif violation == "missing_digest":
        attempt.engines[0].editor_log_sha256 = None
    elif violation == "lifecycle":
        attempt.engines[0].restarted = False
    elif violation == "editor_errors":
        attempt.engines[0].errors.append("editor import failed")
    elif violation == "missing_modality":
        attempt.engines[0].modalities.pop()
    elif violation == "modality_mismatch":
        attempt.engines[0].modalities[0].realized_section_count -= 1
    elif violation == "missing_parity_report":
        attempt.parity_report = None
    elif violation == "missing_parity_summary":
        assert attempt.parity_report is not None
        attempt.parity_report.readbacks.pop()
    else:
        assert attempt.parity_report is not None
        attempt.parity_report.readbacks[0].animation_section_count -= 1

    report = verify_generated_performance_experiment(_plan(cir_project), attempts)

    assert report.gate_passed is False
    if violation in {
        "missing_parity_report",
        "missing_parity_summary",
        "parity_summary_mismatch",
    }:
        assert report.native_realization.passed_count == 3
        assert report.portability.passed_count == 2
    else:
        assert report.native_realization.passed_count == 2


def test_repeatability_compares_package_digests_and_clean_runs(
    cir_project: Project,
) -> None:
    attempts = [_attempt(cir_project, index) for index in range(1, 4)]
    assert attempts[2].artifacts is not None
    attempts[2].artifacts.generation_plan_sha256 = _sha("different-plan")

    digest_report = verify_generated_performance_experiment(
        _plan(cir_project), attempts
    )

    assert digest_report.native_realization.passed_count == 3
    assert digest_report.portability.passed_count == 3
    assert digest_report.repeatability.passed_count == 0

    attempts = [_attempt(cir_project, index) for index in range(1, 4)]
    attempts[1].clean_run = False
    attempts[1].manual_repair_count = 1
    repair_report = verify_generated_performance_experiment(
        _plan(cir_project), attempts
    )

    assert repair_report.repeatability.passed_count == 0
    assert "manual_or_unclean_run" in {item.code for item in repair_report.issues}


def test_scene_identity_and_synthetic_paper_evidence_are_rejected(
    cir_project: Project,
) -> None:
    base_scene = _scene(cir_project)
    scenes = [
        base_scene.model_copy(update={"scene_id": f"scene:{index}"}, deep=True)
        for index in range(10)
    ]
    plan = GeneratedPerformanceExperimentPlan(
        experiment_id="paper-v0.1",
        mode=ExperimentMode.PAPER,
        scenes=scenes,
        seeds=[1, 2, 3, 4, 5],
        repeatability_cases=[RepeatabilityCase(scene_id="scene:0", seed=1)],
    )
    attempt = _attempt(cir_project, 1).model_copy(
        update={"scene_id": "scene:0", "seed": 1, "project_id": "wrong"},
        deep=True,
    )

    report = verify_generated_performance_experiment(plan, [attempt])

    assert report.publishable is False
    assert report.evidence_complete is False
    assert {item.code for item in report.issues} >= {
        "scene_identity_mismatch",
        "synthetic_paper_evidence",
        "missing_attempt",
    }


def test_experiment_model_invariants_are_strict(cir_project: Project) -> None:
    scene = _scene(cir_project)
    case = RepeatabilityCase(scene_id=scene.scene_id, seed=17)
    base = {
        "experiment_id": "invalid",
        "mode": ExperimentMode.HARNESS,
        "scenes": [scene],
        "seeds": [17],
        "repeatability_cases": [case],
    }
    invalid_plans = [
        {**base, "scenes": [scene, scene.model_copy(deep=True)]},
        {**base, "seeds": [17, 17]},
        {**base, "seeds": [-1]},
        {**base, "target_engines": [EngineName.UNREAL, EngineName.UNREAL]},
        {**base, "repeatability_cases": [case, case.model_copy(deep=True)]},
        {
            **base,
            "repeatability_cases": [
                RepeatabilityCase(scene_id="scene:missing", seed=17)
            ],
        },
        {**base, "mode": ExperimentMode.PAPER},
    ]
    for payload in invalid_plans:
        with pytest.raises(ValidationError):
            GeneratedPerformanceExperimentPlan.model_validate(payload)

    artifacts = _artifacts()
    with pytest.raises(ValidationError, match="sorted and unique"):
        GeneratedArtifactDigests.model_validate(
            {
                **artifacts.model_dump(),
                "body_motion_sha256s": [artifacts.body_motion_sha256s[0]] * 2,
            }
        )
    with pytest.raises(ValidationError, match="placeholder_section_count"):
        ModalityRealizationEvidence(
            modality=PerformanceModality.BODY,
            expected_section_count=1,
            realized_section_count=0,
            placeholder_section_count=1,
        )
    with pytest.raises(ValidationError, match="source_artifact_sha256s"):
        unsorted_hashes = sorted([_sha("z"), _sha("a")], reverse=True)
        ModalityRealizationEvidence(
            modality=PerformanceModality.BODY,
            expected_section_count=2,
            realized_section_count=2,
            placeholder_section_count=0,
            source_artifact_sha256s=unsorted_hashes,
        )
    with pytest.raises(ValidationError, match="target_asset_refs"):
        ModalityRealizationEvidence(
            modality=PerformanceModality.BODY,
            expected_section_count=1,
            realized_section_count=1,
            placeholder_section_count=0,
            target_asset_refs=["z", "a"],
        )


def test_attempt_and_engine_invariants_are_strict(cir_project: Project) -> None:
    scene = _scene(cir_project)
    artifacts = _artifacts()
    engine = _engine_evidence(EngineName.UNREAL, scene, artifacts)
    duplicate_modality = engine.modalities[0].model_copy(deep=True)
    with pytest.raises(ValidationError, match="modalities"):
        EngineRunEvidence.model_validate(
            {
                **engine.model_dump(),
                "modalities": [*engine.modalities, duplicate_modality],
            }
        )

    base = {
        "evidence_origin": EvidenceOrigin.SYNTHETIC,
        "scene_id": scene.scene_id,
        "project_id": scene.project_id,
        "cir_fingerprint_sha256": scene.cir_fingerprint_sha256,
        "seed": 17,
        "repeat_index": 1,
        "clean_run": True,
        "manual_repair_count": 0,
        "generation_completed": True,
        "artifacts": artifacts,
    }
    invalid_attempts = [
        {**base, "manual_repair_count": 1},
        {**base, "artifacts": None},
        {**base, "generation_completed": False, "artifacts": None},
        {**base, "engines": [engine, engine.model_copy(deep=True)]},
    ]
    for payload in invalid_attempts:
        with pytest.raises(ValidationError):
            GeneratedPerformanceAttemptEvidence.model_validate(payload)
