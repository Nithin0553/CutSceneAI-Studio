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


class UnityNativeSceneBinding(UnityModel):
    source_entity_id: str
    source_object_id: str
    hierarchy_path: str

    @model_validator(mode="after")
    def validate_scene_binding(self) -> Self:
        if not self.source_entity_id:
            raise ValueError("source_entity_id must not be empty")
        if not self.source_object_id:
            raise ValueError("source_object_id must not be empty")
        _validate_relative_object_path(
            self.hierarchy_path,
            field_name="hierarchy_path",
        )
        if not self.hierarchy_path:
            raise ValueError("hierarchy_path must not be empty")
        return self


class UnityNativeActorTarget(UnityModel):
    actor_binding_id: str
    prefab_path: str = Field(
        pattern=r"^Assets(?:/[A-Za-z0-9_. -]+)+\.prefab$"
    )
    animator_path: str = ""
    facial_renderer_path: str = ""

    @model_validator(mode="after")
    def validate_component_paths(self) -> Self:
        _validate_unity_asset_path(self.prefab_path, field_name="prefab_path")
        if not self.prefab_path.endswith(".prefab"):
            raise ValueError("prefab_path must reference a Unity .prefab asset")
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
    target_engine_version: str = Field(default="6000.3", pattern=r"^6000\.(?:0|3)$")
    timeline_package_version: Literal["1.8.12"] = "1.8.12"
    project_id: str
    source_mapping_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    timeline_asset_path: str = Field(pattern=r"^Assets(?:/[A-Za-z0-9_.-]+)+\.playable$")
    scene_asset_path: str = Field(pattern=r"^Assets(?:/[A-Za-z0-9_.-]+)+\.unity$")
    source_scene_asset_path: str | None = Field(
        default=None,
        pattern=r"^Assets(?:/[A-Za-z0-9_. -]+)+\.unity$",
    )
    scene_bindings: list[UnityNativeSceneBinding] = Field(default_factory=list)
    actors: list[UnityNativeActorTarget] = Field(min_length=1)
    omitted_facial_actor_binding_ids: list[str] = Field(default_factory=list)
    render: UnityNativeRenderSettings = Field(default_factory=UnityNativeRenderSettings)

    @model_validator(mode="after")
    def validate_unique_bindings(self) -> Self:
        _validate_unity_asset_path(
            self.timeline_asset_path, field_name="timeline_asset_path"
        )
        _validate_unity_asset_path(self.scene_asset_path, field_name="scene_asset_path")
        if self.source_scene_asset_path is not None:
            _validate_unity_asset_path(
                self.source_scene_asset_path,
                field_name="source_scene_asset_path",
            )
            if not self.source_scene_asset_path.endswith(".unity"):
                raise ValueError("source_scene_asset_path must reference a Unity .unity scene")
            if self.source_scene_asset_path == self.scene_asset_path:
                raise ValueError(
                    "source_scene_asset_path must differ from generated scene_asset_path"
                )

        if self.scene_bindings and self.source_scene_asset_path is None:
            raise ValueError(
                "scene_bindings require source_scene_asset_path"
            )

        scene_entity_ids = [item.source_entity_id for item in self.scene_bindings]
        if len(scene_entity_ids) != len(set(scene_entity_ids)):
            raise ValueError("scene_bindings must contain unique source_entity_id values")
        scene_object_ids = [item.source_object_id for item in self.scene_bindings]
        if len(scene_object_ids) != len(set(scene_object_ids)):
            raise ValueError("scene_bindings must contain unique source_object_id values")

        binding_ids = [item.actor_binding_id for item in self.actors]
        if len(binding_ids) != len(set(binding_ids)):
            raise ValueError("actors must contain unique actor_binding_id values")
        omissions = self.omitted_facial_actor_binding_ids
        if len(omissions) != len(set(omissions)):
            raise ValueError(
                "omitted_facial_actor_binding_ids must contain unique values"
            )
        unknown = sorted(set(omissions) - set(binding_ids))
        if unknown:
            raise ValueError(
                "omitted_facial_actor_binding_ids references unknown actors: "
                + ", ".join(unknown)
            )
        return self
