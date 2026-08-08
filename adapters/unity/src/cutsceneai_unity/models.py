from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cutsceneai_parity import EntityKind, TimelineSemantics


class UnityModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class UnityPrimitive(str, Enum):
    CAPSULE = "capsule"
    CUBE = "cube"


class UnityVector(UnityModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


class UnityQuaternion(UnityModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    w: float = 1.0


def _unit_scale() -> UnityVector:
    return UnityVector(x=1.0, y=1.0, z=1.0)


class UnityTransform(UnityModel):
    position_m: UnityVector = Field(default_factory=UnityVector)
    rotation: UnityQuaternion = Field(default_factory=UnityQuaternion)
    scale: UnityVector = Field(default_factory=_unit_scale)


class UnityCoordinateSystem(UnityModel):
    distance_unit: Literal["meter"] = "meter"
    handedness: Literal["left"] = "left"
    up_axis: Literal["y"] = "y"
    forward_axis: Literal["z"] = "z"
    position_mapping: Literal["X=X; Y=Y; Z=-Z"] = "X=X; Y=Y; Z=-Z"


class UnityEntityAsset(UnityModel):
    source_entity_id: str
    prefab_path: str = Field(pattern=r"^Assets/.+\.prefab$")


class UnityAnimationAsset(UnityModel):
    cue_id: str
    asset_path: str = Field(pattern=r"^Assets/.+")


class UnityAudioAsset(UnityModel):
    cue_id: str
    asset_path: str = Field(pattern=r"^Assets/.+")
    end_frame: int = Field(gt=0)


class UnityAssetMap(UnityModel):
    map_version: Literal["0.1.0"] = "0.1.0"
    project_id: str
    entities: list[UnityEntityAsset] = Field(default_factory=list)
    animations: list[UnityAnimationAsset] = Field(default_factory=list)
    audio: list[UnityAudioAsset] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_keys(self) -> UnityAssetMap:
        groups = (
            ("entities", [item.source_entity_id for item in self.entities]),
            ("animations", [item.cue_id for item in self.animations]),
            ("audio", [item.cue_id for item in self.audio]),
        )
        for group_name, keys in groups:
            if len(keys) != len(set(keys)):
                raise ValueError(
                    f"Unity asset map contains duplicate {group_name} keys"
                )
        return self


class UnityActorBinding(UnityModel):
    binding_id: str
    source_entity_id: str
    display_name: str
    kind: EntityKind
    prefab_path: str | None = None
    placeholder: bool
    placeholder_primitive: UnityPrimitive
    transform: UnityTransform


class UnityAnimationSection(UnityModel):
    cue_id: str
    actor_binding_id: str
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)
    asset_path: str | None = Field(default=None, pattern=r"^Assets/.+")
    placeholder: bool

    @model_validator(mode="after")
    def validate_range(self) -> UnityAnimationSection:
        if self.end_frame <= self.start_frame:
            raise ValueError("end_frame must be greater than start_frame")
        if self.placeholder is (self.asset_path is not None):
            raise ValueError(
                "placeholder must be true exactly when asset_path is absent"
            )
        return self


class UnityAudioSection(UnityModel):
    cue_id: str
    actor_binding_id: str
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)
    asset_path: str = Field(pattern=r"^Assets/.+")

    @model_validator(mode="after")
    def validate_range(self) -> UnityAudioSection:
        if self.end_frame <= self.start_frame:
            raise ValueError("end_frame must be greater than start_frame")
        return self


class UnityCameraCut(UnityModel):
    cut_id: str
    source_shot_id: str
    display_name: str
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)
    lens_mm: float = Field(ge=8, le=300)
    position_m: UnityVector
    look_at_m: UnityVector

    @model_validator(mode="after")
    def validate_range(self) -> UnityCameraCut:
        if self.end_frame <= self.start_frame:
            raise ValueError("end_frame must be greater than start_frame")
        return self


class UnitySceneTimeline(UnityModel):
    source_scene_id: str
    title: str
    asset_name: str
    timeline_asset_path: str = Field(pattern=r"^Assets/.+\.playable$")
    scene_asset_path: str = Field(pattern=r"^Assets/.+\.unity$")
    duration_frames: int = Field(gt=0)
    actors: list[UnityActorBinding]
    animation_sections: list[UnityAnimationSection]
    audio_sections: list[UnityAudioSection]
    cameras: list[UnityCameraCut]


class UnityExportWarning(UnityModel):
    code: str
    source_id: str | None = None
    message: str


class UnityExportPlan(UnityModel):
    adapter_version: Literal["0.1.0"] = "0.1.0"
    cir_schema_version: Literal["0.1.0"] = "0.1.0"
    target_engine: Literal["Unity"] = "Unity"
    target_engine_version: Literal["6000.0"] = "6000.0"
    timeline_package_version: Literal["1.8.12"] = "1.8.12"
    project_id: str
    project_name: str
    fps: int = Field(ge=1, le=240)
    coordinate_system: UnityCoordinateSystem = Field(
        default_factory=UnityCoordinateSystem
    )
    semantics: TimelineSemantics
    sequences: list[UnitySceneTimeline]
    warnings: list[UnityExportWarning]
