from typing import Any

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError

from app.api.cir_errors import domain_failure, failure_response, structural_failure
from app.models.cir import CIRValidationFailure, CIRValidationProblem
from cutsceneai_cir import CIRValidationError, validate_project
from cutsceneai_unity import (
    UnityExportPlan,
    compile_project,
    render_unity_editor_script,
)


router = APIRouter(prefix="/api/v1/adapters/unity", tags=["unity-adapter"])


def _compile(payload: Any) -> UnityExportPlan | JSONResponse:
    try:
        project = validate_project(payload)
    except ValidationError as exc:
        return structural_failure(exc)
    except CIRValidationError as exc:
        return domain_failure(exc)

    try:
        return compile_project(project)
    except ValueError as exc:
        return failure_response(
            [
                CIRValidationProblem(
                    code="unity.adapter_conversion_failed",
                    path="$",
                    message=str(exc),
                )
            ]
        )


@router.post(
    "/export",
    response_model=UnityExportPlan,
    responses={422: {"model": CIRValidationFailure}},
)
def export_unity_plan(payload: Any = Body(...)) -> UnityExportPlan | JSONResponse:
    """Compile CIR into a deterministic Unity Timeline editor plan."""

    return _compile(payload)


@router.post(
    "/importer.cs",
    response_model=None,
    responses={
        200: {"content": {"text/x-csharp": {}}},
        422: {"model": CIRValidationFailure},
    },
)
def export_unity_importer(payload: Any = Body(...)) -> Response | JSONResponse:
    """Render one Unity Editor importer with restart-safe semantic readback."""

    plan = _compile(payload)
    if isinstance(plan, JSONResponse):
        return plan
    return Response(
        content=render_unity_editor_script(plan),
        media_type="text/x-csharp",
        headers={"Content-Disposition": 'attachment; filename="CutSceneAIGeneratedTimeline.cs"'},
    )
