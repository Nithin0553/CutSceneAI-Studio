from pydantic import Field

from app.models.cir import APIModel
from cutsceneai_cir import Project


class DirectorGenerateRequest(APIModel):
    prompt: str = Field(min_length=20, max_length=8000)


class DirectorGenerateResponse(APIModel):
    project: Project
    provider: str
    model: str
    request_id: str | None = None


class DirectorFailure(APIModel):
    code: str
    message: str
    retryable: bool = False
    request_id: str | None = None
