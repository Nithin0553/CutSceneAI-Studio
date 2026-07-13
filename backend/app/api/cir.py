from typing import Any

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.models.cir import (
    CIRValidationFailure,
    CIRValidationProblem,
    CIRValidationSuccess,
    CIRValidationSummary,
)
from cutsceneai_cir import CIRValidationError, validate_project


router = APIRouter(prefix="/api/v1/cir", tags=["cir"])


def _format_location(location: tuple[Any, ...]) -> str:
    path = ""
    for part in location:
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path += f".{part}" if path else str(part)
    return path or "$"


def _failure_response(problems: list[CIRValidationProblem]) -> JSONResponse:
    failure = CIRValidationFailure(errors=problems)
    return JSONResponse(status_code=422, content=failure.model_dump(mode="json"))


@router.post(
    "/validate",
    response_model=CIRValidationSuccess,
    responses={422: {"model": CIRValidationFailure}},
)
def validate_cir(payload: Any = Body(...)) -> Any:
    """Validate structural and cinematic CIR rules."""

    try:
        project = validate_project(payload)
    except ValidationError as exc:
        problems = [
            CIRValidationProblem(
                code=f"structural.{error['type']}",
                path=_format_location(error["loc"]),
                message=error["msg"],
            )
            for error in exc.errors(include_url=False, include_context=False, include_input=False)
        ]
        return _failure_response(problems)
    except CIRValidationError as exc:
        problems = [
            CIRValidationProblem(
                code=issue.code,
                path=issue.path,
                message=issue.message,
            )
            for issue in exc.issues
        ]
        return _failure_response(problems)

    summary = CIRValidationSummary(
        scene_count=len(project.scenes),
        beat_count=sum(len(scene.beats) for scene in project.scenes),
        shot_count=sum(len(scene.shots) for scene in project.scenes),
    )
    return CIRValidationSuccess(
        schema_version=project.schema_version,
        project_id=project.id,
        summary=summary,
    )
