from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from cutsceneai_cir import (
    CameraAngle,
    CameraFraming,
    CameraMovement,
    ProjectSettings,
    ShotPurpose,
)


class UnrealModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class UnrealActorKind(str, Enum):
    CHARACTER = "character"
    ENVIRONMENT = "environment"


class UnrealMeshType(str, Enum):
    STATIC_MESH = "static_mesh"
    SKELETAL_MESH = "skeletal_mesh"


class UnrealVector(UnrealModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


class UnrealQuaternion(UnrealModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    w: float = 1.0


def _unit_scale() -> UnrealVector:
    return UnrealVector(x=1.0, y=1.0, z=1.0)


class UnrealTransform(UnrealModel):
    location_cm: UnrealVector = Field(default_factory=UnrealVector)
    rotation: UnrealQuaternion = Field(default_factory=UnrealQuaternion)
    scale: UnrealVector = Field(default_factory=_unit_scale)


class UnrealPlaceholderVisual(UnrealModel):
    mesh_asset_path: str
    transform: UnrealTransform


class UnrealSetPiece(UnrealModel):
    binding_id: str
    display_name: str
    mesh_asset_path: str
    transform: UnrealTransform


class UnrealCoordinateSystem(UnrealModel):
    distance_unit: Literal["centimeter"] = "centimeter"
    handedness: Literal["left"] = "left"
    up_axis: Literal["z"] = "z"
    forward_axis: Literal["x"] = "x"
    position_mapping: Literal["X=-Z*100; Y=X*100; Z=Y*100"] = (
        "X=-Z*100; Y=X*100; Z=Y*100"
    )


class UnrealActorBinding(UnrealModel):
    binding_id: str
    source_entity_id: str
    display_name: str
    kind: UnrealActorKind
    mesh_type: UnrealMeshType
    actor_class_path: str
    asset_path: str | None = None
    placeholder: bool
    placeholder_visual: UnrealPlaceholderVisual | None = None
    transform: UnrealTransform


class UnrealPerformanceCue(UnrealModel):
    source_beat_id: str
    actor_binding_id: str
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)
    motion_prompt: str
    motion_style: str | None = None
    motion_asset_uri: str | None = None
    emotion: str
    emotion_intensity: float = Field(ge=0, le=1)
    facial_asset_uri: str | None = None
    lip_sync: bool
    dialogue: str | None = None
    dialogue_language: str | None = None
    dialogue_audio_uri: str | None = None
    dialogue_start_frame: int | None = Field(default=None, ge=0)
    look_at_binding_id: str | None = None


class UnrealAnimationSection(UnrealModel):
    source_beat_id: str
    actor_binding_id: str
    asset_path: str = Field(pattern=r"^/Game/")
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)


class UnrealAudioSection(UnrealModel):
    source_cue_id: str | None = None
    source_beat_id: str
    actor_binding_id: str
    asset_path: str = Field(pattern=r"^/Game/")
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)
    timing_source: Literal["performance_range", "dialogue_manifest"] = (
        "performance_range"
    )
    dialogue_text: str
    language: str


class UnrealAudioImport(UnrealModel):
    source_cue_id: str
    source_uri: str = Field(pattern=r"^cutsceneai://dialogue/")
    source_relative_path: str = Field(pattern=r"^audio/[a-z][a-z0-9_-]*\.wav$")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    destination_path: str = Field(pattern=r"^/Game/")
    asset_name: str = Field(pattern=r"^SW_[A-Za-z][A-Za-z0-9_]*$")
    asset_path: str = Field(pattern=r"^/Game/")


class UnrealCameraBinding(UnrealModel):
    binding_id: str
    source_shot_id: str
    source_beat_ids: list[str]
    display_name: str
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)
    purpose: ShotPurpose
    description: str
    framing: CameraFraming
    angle: CameraAngle
    movement: CameraMovement
    lens_mm: float = Field(ge=8, le=300)
    subject_binding_ids: list[str]
    target_binding_ids: list[str]
    composition: str | None = None
    transform: UnrealTransform
    look_at_location_cm: UnrealVector
    inferred_transform: bool


class UnrealSceneSequence(UnrealModel):
    source_scene_id: str
    title: str
    location: str
    asset_name: str
    package_path: str
    duration_frames: int = Field(gt=0)
    set_pieces: list[UnrealSetPiece]
    actors: list[UnrealActorBinding]
    performance_cues: list[UnrealPerformanceCue]
    animation_sections: list[UnrealAnimationSection]
    audio_sections: list[UnrealAudioSection]
    cameras: list[UnrealCameraBinding]


class UnrealExportWarning(UnrealModel):
    code: str
    source_id: str | None = None
    message: str


class UnrealExportPlan(UnrealModel):
    adapter_version: Literal["0.6.0"] = "0.6.0"
    cir_schema_version: Literal["0.1.0"] = "0.1.0"
    preview_version: Literal["0.1.0"] = "0.1.0"
    target_engine: Literal["Unreal Engine"] = "Unreal Engine"
    target_engine_version: Literal["5.8.0"] = "5.8.0"
    project_id: str
    project_name: str
    source_settings: ProjectSettings
    coordinate_system: UnrealCoordinateSystem = Field(
        default_factory=UnrealCoordinateSystem
    )
    audio_imports: list[UnrealAudioImport] = Field(default_factory=list)
    sequences: list[UnrealSceneSequence]
    warnings: list[UnrealExportWarning]
