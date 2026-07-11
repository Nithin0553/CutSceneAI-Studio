from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Character(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1)
    role: str | None = None


class SceneBeat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)


class Scene(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    title: str | None = None
    beats: list[SceneBeat] = Field(default_factory=list)


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1)
    description: str | None = None
    characters: list[Character] = Field(default_factory=list)
    scenes: list[Scene] = Field(default_factory=list)
