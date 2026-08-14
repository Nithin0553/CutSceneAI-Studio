from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from .models import UnrealModel


def _validate_relative_output_path(value: str) -> None:
    if "\\" in value or ":" in value or value.startswith("/") or value.endswith("/"):
        raise ValueError("output_directory must be a normalized relative path")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("output_directory must be a normalized relative path")


class UnrealNativeActorTarget(UnrealModel):
    actor_binding_id: str
    skeletal_mesh_path: str = Field(
        pattern=(
            r"^/Game(?:/[A-Za-z][A-Za-z0-9_]*)+"
            r"(?:\.[A-Za-z][A-Za-z0-9_]*)?$"
        )
    )
    require_ue5_mannequin_bones: Literal[True] = True
    require_arkit_52_morph_targets: Literal[True] = True


class UnrealNativeRenderSettings(UnrealModel):
    map_path: str = Field(
        pattern=(
            r"^/Game(?:/[A-Za-z][A-Za-z0-9_]*)+"
            r"(?:\.[A-Za-z][A-Za-z0-9_]*)?$"
        )
    )
    width: int = Field(default=1280, ge=64, le=7680)
    height: int = Field(default=720, ge=64, le=4320)
    output_directory: str = "CutSceneAI/Native/Unreal/Frames"
    image_format: Literal["png"] = "png"

    @model_validator(mode="after")
    def validate_output_directory(self) -> Self:
        _validate_relative_output_path(self.output_directory)
        return self


class UnrealNativeRealizationTarget(UnrealModel):
    target_version: Literal["0.1.0"] = "0.1.0"
    target_engine: Literal["Unreal Engine"] = "Unreal Engine"
    target_engine_version: Literal["5.8.0"] = "5.8.0"
    project_id: str
    source_mapping_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sequence_package_path: str = Field(pattern=r"^/Game(?:/[A-Za-z][A-Za-z0-9_]*)+$")
    sequence_asset_name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]*$")
    actors: list[UnrealNativeActorTarget] = Field(min_length=1)
    render: UnrealNativeRenderSettings

    @model_validator(mode="after")
    def validate_unique_bindings(self) -> Self:
        binding_ids = [item.actor_binding_id for item in self.actors]
        if len(binding_ids) != len(set(binding_ids)):
            raise ValueError("actors must contain unique actor_binding_id values")
        return self
