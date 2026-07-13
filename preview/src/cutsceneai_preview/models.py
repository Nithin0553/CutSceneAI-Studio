from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from cutsceneai_cir import (
    CameraAngle,
    CameraFraming,
    CameraMovement,
    ProjectSettings,
    ShotPurpose,
    Transform,
)


class PreviewModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EntityKind(str, Enum):
    CHARACTER = "character"
    ENVIRONMENT = "environment"


class PlaceholderShape(str, Enum):
    CAPSULE = "capsule"
    BOX = "box"


class PreviewEntity(PreviewModel):
    id: str
    name: str
    kind: EntityKind
    asset_uri: str | None = None
    placeholder_shape: PlaceholderShape
    placeholder_color: str = Field(pattern=r"^#[0-9A-F]{6}$")
    initial_transform: Transform


class PerformanceCue(PreviewModel):
    beat_id: str
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)
    character_id: str
    motion_prompt: str
    motion_style: str | None = None
    emotion: str
    emotion_intensity: float = Field(ge=0, le=1)
    lip_sync: bool
    dialogue: str | None = None
    dialogue_start_frame: int | None = Field(default=None, ge=0)
    look_at_id: str | None = None


class CameraCut(PreviewModel):
    shot_id: str
    beat_ids: list[str]
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)
    purpose: ShotPurpose
    description: str
    subject_ids: list[str]
    framing: CameraFraming
    angle: CameraAngle
    movement: CameraMovement
    lens_mm: float = Field(ge=8, le=300)
    target_ids: list[str]
    composition: str | None = None
    transform: Transform | None = None


class PreviewScene(PreviewModel):
    id: str
    title: str
    location: str
    duration_frames: int = Field(gt=0)
    performance_cues: list[PerformanceCue]
    camera_cuts: list[CameraCut]


class PreviewWarning(PreviewModel):
    code: str
    entity_id: str
    message: str


class PreviewManifest(PreviewModel):
    preview_version: Literal["0.1.0"] = "0.1.0"
    cir_schema_version: Literal["0.1.0"] = "0.1.0"
    project_id: str
    project_name: str
    settings: ProjectSettings
    entities: list[PreviewEntity]
    scenes: list[PreviewScene]
    warnings: list[PreviewWarning]
