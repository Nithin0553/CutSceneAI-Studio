from __future__ import annotations

from enum import Enum

from cutsceneai_cir import Project
from cutsceneai_dialogue import VoiceProfile
from cutsceneai_performance import EvaluationReport, RepairPlan
from pydantic import BaseModel, ConfigDict, Field

from app.models.studio import StudioBindingSelection


class PerformanceRuntimeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PerformanceProviderState(PerformanceRuntimeModel):
    modality: str
    configured: bool
    provider: str
    model: str
    description: str
    reachable: bool | None = None
    health_status: str | None = None
    health: dict[str, object] = Field(default_factory=dict)


class PerformanceReadinessResponse(PerformanceRuntimeModel):
    ready: bool
    providers: list[PerformanceProviderState]
    blocking_issues: list[str] = Field(default_factory=list)


class PerformanceGenerateRequest(PerformanceRuntimeModel):
    project: Project
    project_id: str | None = None
    bindings: list[StudioBindingSelection] = Field(default_factory=list)
    experiment_seed: int = 20260812
    default_voice: VoiceProfile = Field(default_factory=lambda: VoiceProfile(voice="marin"))
    voices: dict[str, VoiceProfile] = Field(default_factory=dict)


class PerformanceRunStatus(str, Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class PerformanceRunRecord(PerformanceRuntimeModel):
    run_version: str = "0.1.0"
    run_id: str
    project_id: str
    status: PerformanceRunStatus
    created_at_utc: str
    completed_at_utc: str | None = None
    experiment_seed: int
    run_directory: str
    generation_plan_sha256: str | None = None
    bundle_sha256: str | None = None
    bundle_byte_length: int | None = None
    body_request_count: int = 0
    facial_request_count: int = 0
    camera_request_count: int = 0
    audio_track_count: int = 0
    provider_summary: dict[str, str] = Field(default_factory=dict)
    derived_from_run_id: str | None = None
    derivation: str | None = None
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class PerformanceEvaluationResponse(PerformanceRuntimeModel):
    report: EvaluationReport
    repair_plan: RepairPlan


class PerformanceRepairResponse(PerformanceRuntimeModel):
    source_report: EvaluationReport
    source_repair_plan: RepairPlan
    derived_run: PerformanceRunRecord | None = None
    applied_action_ids: list[str] = Field(default_factory=list)
    deferred_action_ids: list[str] = Field(default_factory=list)
    post_report: EvaluationReport | None = None
    post_repair_plan: RepairPlan | None = None
