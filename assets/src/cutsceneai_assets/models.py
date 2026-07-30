from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from cutsceneai_cir import Project, Transform
from pydantic import BaseModel, ConfigDict, Field

Identifier = Annotated[
    str,
    Field(
        min_length=1,
        pattern=r"^[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*$",
        description="Stable lowercase identifier used by Asset Resolution references.",
    ),
]
NonEmptyString = Annotated[str, Field(min_length=1)]


class AssetModel(BaseModel):
    """Strict base configuration for Asset Index and resolution contracts."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class AssetKind(str, Enum):
    ENVIRONMENT_PROP = "environment_prop"
    ENVIRONMENT_SET = "environment_set"


class AssetRecord(AssetModel):
    id: Identifier
    name: NonEmptyString
    kind: AssetKind
    asset_uri: NonEmptyString
    description: str | None = None
    aliases: list[NonEmptyString] = Field(default_factory=list)
    keywords: list[NonEmptyString] = Field(default_factory=list)
    location_terms: list[NonEmptyString] = Field(default_factory=list)
    priority: int = Field(default=0, ge=0, le=100)
    default_transform: Transform = Field(default_factory=Transform)


class AssetIndex(AssetModel):
    schema_version: Literal["0.1.0"] = "0.1.0"
    id: Identifier
    name: NonEmptyString
    target_engine: NonEmptyString
    target_engine_version: NonEmptyString
    assets: list[AssetRecord] = Field(default_factory=list)


class ResolutionSourceKind(str, Enum):
    ENVIRONMENT_OBJECT = "environment_object"
    SCENE_SET = "scene_set"


class ResolutionStatus(str, Enum):
    EXPLICIT = "explicit"
    MATCHED = "matched"
    FALLBACK = "fallback"


class AssetResolution(AssetModel):
    source_kind: ResolutionSourceKind
    source_id: Identifier
    source_name: NonEmptyString
    expected_asset_kind: AssetKind
    status: ResolutionStatus
    asset_id: Identifier | None = None
    asset_name: str | None = None
    asset_uri: str | None = None
    score: int | None = Field(default=None, ge=1)
    priority: int | None = Field(default=None, ge=0, le=100)
    matched_terms: list[NonEmptyString] = Field(default_factory=list)
    asset_default_transform: Transform | None = None
    reason: NonEmptyString


class AssetResolutionWarning(AssetModel):
    code: NonEmptyString
    source_kind: ResolutionSourceKind
    source_id: Identifier
    message: NonEmptyString


class AssetResolutionPlan(AssetModel):
    resolution_version: Literal["0.1.0"] = "0.1.0"
    project_id: Identifier
    asset_index_id: Identifier
    asset_index_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    target_engine: NonEmptyString
    target_engine_version: NonEmptyString
    resolutions: list[AssetResolution]
    warnings: list[AssetResolutionWarning] = Field(default_factory=list)


class AssetResolutionRequest(AssetModel):
    project: Project
    asset_index: AssetIndex
