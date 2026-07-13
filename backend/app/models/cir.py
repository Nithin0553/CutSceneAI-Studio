from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CIRValidationSummary(APIModel):
    scene_count: int = Field(ge=0)
    beat_count: int = Field(ge=0)
    shot_count: int = Field(ge=0)


class CIRValidationSuccess(APIModel):
    valid: Literal[True] = True
    schema_version: str
    project_id: str
    summary: CIRValidationSummary


class CIRValidationProblem(APIModel):
    code: str
    path: str
    message: str


class CIRValidationFailure(APIModel):
    valid: Literal[False] = False
    errors: list[CIRValidationProblem]
