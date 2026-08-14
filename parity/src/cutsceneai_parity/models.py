from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cutsceneai_cir import CameraAngle, CameraFraming, CameraMovement, ShotPurpose


class ParityModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EngineName(str, Enum):
    UNREAL = "unreal"
    UNITY = "unity"


class EntityKind(str, Enum):
    CHARACTER = "character"
    ENVIRONMENT = "environment"


class IssueSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


class FrameRange(ParityModel):
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_range(self) -> FrameRange:
        if self.end_frame <= self.start_frame:
            raise ValueError("end_frame must be greater than start_frame")
        return self


class SemanticEntity(ParityModel):
    binding_id: str
    source_entity_id: str
    kind: EntityKind


class SemanticPerformanceCue(FrameRange):
    cue_id: str
    source_beat_id: str
    actor_binding_id: str
    motion_intent_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    look_at_binding_id: str | None = None


class SemanticDialogueCue(ParityModel):
    cue_id: str
    source_beat_id: str
    actor_binding_id: str
    start_frame: int = Field(ge=0)
    window_end_frame: int = Field(gt=0)
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    language: str

    @model_validator(mode="after")
    def validate_window(self) -> SemanticDialogueCue:
        if self.window_end_frame <= self.start_frame:
            raise ValueError("window_end_frame must be greater than start_frame")
        return self


class SemanticCameraCut(FrameRange):
    cut_id: str
    source_shot_id: str
    source_beat_ids: list[str]
    purpose: ShotPurpose
    framing: CameraFraming
    angle: CameraAngle
    movement: CameraMovement
    lens_mm: float = Field(ge=8, le=300)
    subject_binding_ids: list[str]
    target_binding_ids: list[str]


class SemanticScene(ParityModel):
    source_scene_id: str
    duration_frames: int = Field(gt=0)
    entities: list[SemanticEntity]
    performance_cues: list[SemanticPerformanceCue]
    dialogue_cues: list[SemanticDialogueCue]
    camera_cuts: list[SemanticCameraCut]


class TimelineSemantics(ParityModel):
    semantics_version: Literal["0.1.0"] = "0.1.0"
    cir_schema_version: Literal["0.1.0"] = "0.1.0"
    cir_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    project_id: str
    fps: int = Field(ge=1, le=240)
    scenes: list[SemanticScene]


class RealizedSection(FrameRange):
    semantic_id: str
    actor_binding_id: str | None = None
    asset_ref: str | None = None
    placeholder: bool = False


class ReadbackEvidence(ParityModel):
    animation_sections: list[RealizedSection] = Field(default_factory=list)
    facial_sections: list[RealizedSection] = Field(default_factory=list)
    camera_sections: list[RealizedSection] = Field(default_factory=list)
    audio_sections: list[RealizedSection] = Field(default_factory=list)


class EngineTimelineReadback(ParityModel):
    readback_version: Literal["0.1.0"] = "0.1.0"
    engine: EngineName
    engine_version: str
    adapter_version: str
    timeline_asset: str
    semantics: TimelineSemantics
    evidence: ReadbackEvidence = Field(default_factory=ReadbackEvidence)
    warnings: list[str] = Field(default_factory=list)


class ParityIssue(ParityModel):
    severity: IssueSeverity
    scope: str
    code: str
    semantic_id: str | None = None
    field: str | None = None
    expected: str | None = None
    actual: str | None = None
    delta_frames: int | None = None
    message: str


class ReadbackSummary(ParityModel):
    engine: EngineName
    engine_version: str
    adapter_version: str
    timeline_asset: str
    animation_section_count: int = Field(ge=0)
    facial_section_count: int = Field(ge=0)
    camera_section_count: int = Field(ge=0)
    audio_section_count: int = Field(ge=0)


class RealizationRequirements(ParityModel):
    animation: bool = False
    facial: bool = False
    camera: bool = False
    audio: bool = False
    engines: list[EngineName] = Field(default_factory=list)


class ParityReport(ParityModel):
    report_version: Literal["0.1.0"] = "0.1.0"
    project_id: str
    cir_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tolerance_frames: int = Field(ge=0)
    requirements: RealizationRequirements = Field(
        default_factory=RealizationRequirements
    )
    equivalent: bool
    error_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    readbacks: list[ReadbackSummary]
    issues: list[ParityIssue]
