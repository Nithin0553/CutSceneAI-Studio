from typing import Literal

from pydantic import BaseModel, ConfigDict


class AssetAPIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AssetResolutionProblem(AssetAPIModel):
    code: str
    path: str
    message: str


class AssetResolutionFailure(AssetAPIModel):
    valid: Literal[False] = False
    errors: list[AssetResolutionProblem]
