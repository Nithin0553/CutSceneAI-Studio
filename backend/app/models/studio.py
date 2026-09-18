from __future__ import annotations

from enum import Enum
from typing import Any

from cutsceneai_cir import Project
from pydantic import BaseModel, ConfigDict, Field


class StudioModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class StudioEngine(str, Enum):
    UNITY = "unity"
    UNREAL = "unreal"


class StudioCapability(StudioModel):
    id: str
    label: str
    status: str
    description: str
    blocking: bool = False


class StudioCapabilityResponse(StudioModel):
    workflow_version: str = "v3"
    capabilities: list[StudioCapability]


class StudioProjectConnectRequest(StudioModel):
    engine: StudioEngine
    project_path: str = Field(min_length=1)
    display_name: str | None = None
    engine_executable: str | None = None


class StudioAsset(StudioModel):
    object_id: str
    kind: str
    display_name: str
    engine_ref: str
    relative_path: str
    verified: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class StudioProjectManifest(StudioModel):
    manifest_version: str = "0.1.0"
    project_id: str
    engine: StudioEngine
    display_name: str
    project_path: str
    engine_version: str | None = None
    adapter_version: str | None = None
    current_scene: str | None = None
    fps: int | None = None
    discovery_mode: str
    bridge_connected: bool = False
    capabilities: list[str] = Field(default_factory=list)
    assets: list[StudioAsset] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StudioProjectRecord(StudioModel):
    project_id: str
    engine: StudioEngine
    display_name: str
    project_path: str
    engine_executable: str | None = None
    connected_at_utc: str
    manifest: StudioProjectManifest


class StudioBridgeManifestRequest(StudioModel):
    engine_version: str | None = None
    adapter_version: str | None = None
    current_scene: str | None = None
    fps: int | None = None
    capabilities: list[str] = Field(default_factory=list)
    assets: list[StudioAsset] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StudioBindingOptionsRequest(StudioModel):
    project_id: str
    project: Project


class StudioBindingCandidate(StudioModel):
    project_object_id: str
    display_name: str
    engine_ref: str
    kind: str
    score: float = Field(ge=0, le=1)
    verified: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


class StudioBindingRole(StudioModel):
    cir_id: str
    label: str
    kind: str
    description: str | None = None
    required: bool
    candidates: list[StudioBindingCandidate] = Field(default_factory=list)


class StudioBindingOptionsResponse(StudioModel):
    project_id: str
    engine: StudioEngine
    roles: list[StudioBindingRole]


class StudioBindingSelection(StudioModel):
    cir_id: str
    project_object_id: str


class StudioBindingValidateRequest(StudioModel):
    project_id: str
    project: Project
    bindings: list[StudioBindingSelection]


class StudioBindingManifest(StudioModel):
    binding_version: str = "0.1.0"
    project_id: str
    engine: StudioEngine
    cir_project_id: str
    bindings: list[StudioBindingSelection]
    unresolved_required_ids: list[str] = Field(default_factory=list)
    unresolved_optional_ids: list[str] = Field(default_factory=list)
    valid: bool


class StudioPerformancePlanRequest(StudioModel):
    project: Project
    experiment_seed: int = 20260812


class StudioRealizationRequest(StudioModel):
    project_id: str
    project: Project
    bindings: list[StudioBindingSelection]


class StudioRealizationResponse(StudioModel):
    project_id: str
    engine: StudioEngine
    ready: bool
    plan: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)
    blocking_issues: list[str] = Field(default_factory=list)
