from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .models import EngineName, IssueSeverity, ParityModel, ParityReport


SHA256_PATTERN = r"^[0-9a-f]{64}$"
Sha256 = Annotated[str, Field(pattern=SHA256_PATTERN)]


class ExperimentMode(str, Enum):
    HARNESS = "harness"
    PAPER = "paper"


class EvidenceOrigin(str, Enum):
    SYNTHETIC = "synthetic"
    REAL = "real"


class PerformanceModality(str, Enum):
    BODY = "body"
    FACIAL = "facial"
    CAMERA = "camera"
    AUDIO = "audio"


class ExperimentScene(ParityModel):
    scene_id: str
    project_id: str
    cir_fingerprint_sha256: Sha256
    expected_frame_count: int = Field(gt=0)
    expected_body_sections: int = Field(gt=0)
    expected_facial_sections: int = Field(gt=0)
    expected_camera_sections: int = Field(gt=0)
    expected_audio_sections: int = Field(gt=0)


class RepeatabilityCase(ParityModel):
    scene_id: str
    seed: int = Field(ge=0)


class GeneratedPerformanceExperimentPlan(ParityModel):
    plan_version: Literal["0.1.0"] = "0.1.0"
    experiment_id: str
    mode: ExperimentMode
    scenes: list[ExperimentScene] = Field(min_length=1)
    seeds: list[int] = Field(min_length=1)
    repeat_runs: Literal[3] = 3
    repeatability_cases: list[RepeatabilityCase] = Field(min_length=1)
    target_engines: list[EngineName] = Field(
        default_factory=lambda: [EngineName.UNREAL, EngineName.UNITY]
    )
    tolerance_frames: int = Field(default=1, ge=0)
    minimum_first_pass_success_rate: float = Field(default=1.0, ge=0, le=1)
    minimum_repeatability_rate: float = Field(default=1.0, ge=0, le=1)
    minimum_portability_rate: float = Field(default=1.0, ge=0, le=1)
    minimum_native_realization_rate: float = Field(default=1.0, ge=0, le=1)

    @model_validator(mode="after")
    def validate_plan(self) -> Self:
        scene_ids = [scene.scene_id for scene in self.scenes]
        if len(scene_ids) != len(set(scene_ids)):
            raise ValueError("scenes must have unique scene_id values")
        if len(self.seeds) != len(set(self.seeds)):
            raise ValueError("seeds must be unique")
        if any(seed < 0 for seed in self.seeds):
            raise ValueError("seeds must be non-negative")
        expected_engines = {EngineName.UNREAL, EngineName.UNITY}
        if (
            len(self.target_engines) != 2
            or set(self.target_engines) != expected_engines
        ):
            raise ValueError(
                "target_engines must contain Unreal and Unity exactly once"
            )
        case_keys = [(case.scene_id, case.seed) for case in self.repeatability_cases]
        if len(case_keys) != len(set(case_keys)):
            raise ValueError("repeatability_cases must be unique")
        scene_id_set = set(scene_ids)
        seed_set = set(self.seeds)
        if any(
            scene_id not in scene_id_set or seed not in seed_set
            for scene_id, seed in case_keys
        ):
            raise ValueError(
                "repeatability_cases must reference planned scenes and seeds"
            )
        if self.mode is ExperimentMode.PAPER:
            if len(self.scenes) != 10 or len(self.seeds) != 5:
                raise ValueError("paper mode requires exactly 10 scenes and 5 seeds")
        return self


class GeneratedArtifactDigests(ParityModel):
    source_bundle_sha256: Sha256
    generation_plan_sha256: Sha256
    performance_package_sha256: Sha256
    body_motion_sha256s: list[Sha256] = Field(min_length=1)
    facial_curves_sha256s: list[Sha256] = Field(min_length=1)
    camera_curves_sha256s: list[Sha256] = Field(min_length=1)
    audio_sha256s: list[Sha256] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_digests(self) -> Self:
        for field_name in (
            "body_motion_sha256s",
            "facial_curves_sha256s",
            "camera_curves_sha256s",
            "audio_sha256s",
        ):
            values = getattr(self, field_name)
            if values != sorted(set(values)):
                raise ValueError(f"{field_name} must be sorted and unique")
        return self


class ModalityRealizationEvidence(ParityModel):
    modality: PerformanceModality
    expected_section_count: int = Field(ge=0)
    realized_section_count: int = Field(ge=0)
    placeholder_section_count: int = Field(ge=0)
    source_artifact_sha256s: list[Sha256] = Field(default_factory=list)
    target_asset_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_realization(self) -> Self:
        if self.placeholder_section_count > self.realized_section_count:
            raise ValueError(
                "placeholder_section_count cannot exceed realized_section_count"
            )
        if self.source_artifact_sha256s != sorted(set(self.source_artifact_sha256s)):
            raise ValueError("source_artifact_sha256s must be sorted and unique")
        if self.target_asset_refs != sorted(set(self.target_asset_refs)):
            raise ValueError("target_asset_refs must be sorted and unique")
        return self


class EngineRunEvidence(ParityModel):
    engine: EngineName
    engine_version: str
    source_bundle_sha256: Sha256 | None = None
    mapping_sha256: Sha256 | None = None
    editor_log_sha256: Sha256 | None = None
    readback_sha256: Sha256 | None = None
    timeline_fingerprint_sha256: Sha256 | None = None
    render_manifest_sha256: Sha256 | None = None
    rendered_frame_count: int = Field(default=0, ge=0)
    import_completed: bool = False
    saved: bool = False
    restarted: bool = False
    readback_completed: bool = False
    render_completed: bool = False
    modalities: list[ModalityRealizationEvidence] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    missing_realization_warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_modalities(self) -> Self:
        names = [item.modality for item in self.modalities]
        if len(names) != len(set(names)):
            raise ValueError("modalities must contain each modality at most once")
        return self


class GeneratedPerformanceAttemptEvidence(ParityModel):
    evidence_version: Literal["0.1.0"] = "0.1.0"
    evidence_origin: EvidenceOrigin
    scene_id: str
    project_id: str
    cir_fingerprint_sha256: Sha256
    seed: int = Field(ge=0)
    repeat_index: int = Field(ge=1, le=3)
    clean_run: bool
    manual_repair_count: int = Field(ge=0)
    generation_completed: bool
    artifacts: GeneratedArtifactDigests | None = None
    engines: list[EngineRunEvidence] = Field(default_factory=list)
    parity_report: ParityReport | None = None
    failure_code: str | None = None

    @model_validator(mode="after")
    def validate_attempt(self) -> Self:
        if self.clean_run and self.manual_repair_count:
            raise ValueError("clean_run cannot include manual repairs")
        if self.generation_completed and self.artifacts is None:
            raise ValueError("completed generation requires artifact digests")
        if not self.generation_completed and self.failure_code is None:
            raise ValueError("failed generation requires failure_code")
        engines = [item.engine for item in self.engines]
        if len(engines) != len(set(engines)):
            raise ValueError("engines must contain each engine at most once")
        return self


class ExperimentMetricSummary(ParityModel):
    planned_count: int = Field(ge=0)
    observed_count: int = Field(ge=0)
    passed_count: int = Field(ge=0)
    rate: float = Field(ge=0, le=1)
    minimum_rate: float = Field(ge=0, le=1)
    target_met: bool


class ExperimentIssue(ParityModel):
    severity: IssueSeverity
    code: str
    message: str
    scene_id: str | None = None
    seed: int | None = None
    repeat_index: int | None = None


class GeneratedPerformanceExperimentReport(ParityModel):
    report_version: Literal["0.1.0"] = "0.1.0"
    experiment_id: str
    mode: ExperimentMode
    evidence_complete: bool
    gate_passed: bool
    publishable: bool
    reliability: ExperimentMetricSummary
    repeatability: ExperimentMetricSummary
    portability: ExperimentMetricSummary
    native_realization: ExperimentMetricSummary
    issue_count: int = Field(ge=0)
    issues: list[ExperimentIssue]
