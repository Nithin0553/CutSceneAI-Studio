from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from .models import UnityModel


def _validate_relative_object_path(value: str, *, field_name: str) -> None:
    if "\\" in value or ":" in value or value.startswith("/") or value.endswith("/"):
        raise ValueError(f"{field_name} must be a normalized relative object path")
    parts = value.split("/") if value else []
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"{field_name} must be a normalized relative object path")


def _validate_unity_asset_path(value: str, *, field_name: str) -> None:
    if "\\" in value or ":" in value:
        raise ValueError(f"{field_name} must be a normalized Unity Assets path")
    parts = value.split("/")
    if parts[0] != "Assets" or any(part in {"", ".", ".."} for part in parts[1:]):
        raise ValueError(f"{field_name} must be a normalized Unity Assets path")


class UnityNativeActorTarget(UnityModel):
    actor_binding_id: str
    prefab_path: str = Field(pattern=r"^Assets(?:/[A-Za-z0-9_.-]+)+\.prefab$")
    animator_path: str = ""
    facial_renderer_path: str

    @model_validator(mode="after")
    def validate_component_paths(self) -> Self:
        _validate_unity_asset_path(self.prefab_path, field_name="prefab_path")
        if self.animator_path:
            _validate_relative_object_path(
                self.animator_path, field_name="animator_path"
            )
        _validate_relative_object_path(
            self.facial_renderer_path, field_name="facial_renderer_path"
        )
        return self


class UnityNativeRenderSettings(UnityModel):
    width: int = Field(default=1280, ge=64, le=7680)
    height: int = Field(default=720, ge=64, le=4320)
    output_directory: str = "CutSceneAIEvidence/Unity/Frames"
    image_format: Literal["png"] = "png"

    @model_validator(mode="after")
    def validate_output_directory(self) -> Self:
        _validate_relative_object_path(
            self.output_directory, field_name="output_directory"
        )
        return self


class UnityNativeRealizationTarget(UnityModel):
    target_version: Literal["0.1.0"] = "0.1.0"
    target_engine: Literal["Unity"] = "Unity"
    target_engine_version: Literal["6000.0"] = "6000.0"
    timeline_package_version: Literal["1.8.12"] = "1.8.12"
    project_id: str
    source_mapping_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    timeline_asset_path: str = Field(pattern=r"^Assets(?:/[A-Za-z0-9_.-]+)+\.playable$")
    scene_asset_path: str = Field(pattern=r"^Assets(?:/[A-Za-z0-9_.-]+)+\.unity$")
    actors: list[UnityNativeActorTarget] = Field(min_length=1)
    render: UnityNativeRenderSettings = Field(default_factory=UnityNativeRenderSettings)

    @model_validator(mode="after")
    def validate_unique_bindings(self) -> Self:
        _validate_unity_asset_path(
            self.timeline_asset_path, field_name="timeline_asset_path"
        )
        _validate_unity_asset_path(self.scene_asset_path, field_name="scene_asset_path")
        binding_ids = [item.actor_binding_id for item in self.actors]
        if len(binding_ids) != len(set(binding_ids)):
            raise ValueError("actors must contain unique actor_binding_id values")
        return self
