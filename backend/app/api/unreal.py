from typing import Any

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError

from app.api.cir_errors import domain_failure, failure_response, structural_failure
from app.models.cir import CIRValidationFailure, CIRValidationProblem
from cutsceneai_cir import CIRValidationError, Project, validate_project
from cutsceneai_unreal import (
    UnrealExportPlan,
    compile_project,
    render_unreal_import_script,
)


router = APIRouter(prefix="/api/v1/adapters/unreal", tags=["unreal-adapter"])


def _validate(payload: Any) -> Project | JSONResponse:
    try:
        return validate_project(payload)
    except ValidationError as exc:
        return structural_failure(exc)
    except CIRValidationError as exc:
        return domain_failure(exc)


def _compile(payload: Any) -> UnrealExportPlan | JSONResponse:
    project = _validate(payload)
    if isinstance(project, JSONResponse):
        return project
    try:
        return compile_project(project)
    except ValueError as exc:
        return failure_response(
            [
                CIRValidationProblem(
                    code="unreal.adapter_conversion_failed",
                    path="$",
                    message=str(exc),
                )
            ]
        )


@router.post(
    "/export",
    response_model=UnrealExportPlan,
    responses={422: {"model": CIRValidationFailure}},
)
def export_unreal_plan(payload: Any = Body(...)) -> UnrealExportPlan | JSONResponse:
    """Compile CIR into a deterministic Unreal Sequencer import plan."""

    return _compile(payload)


@router.post(
    "/importer.py",
    response_model=None,
    responses={
        200: {"content": {"text/x-python": {}}},
        422: {"model": CIRValidationFailure},
    },
)
def export_unreal_importer(payload: Any = Body(...)) -> Response | JSONResponse:
    """Render a self-contained Unreal Editor Python importer from CIR."""

    plan = _compile(payload)
    if isinstance(plan, JSONResponse):
        return plan
    return Response(
        content=render_unreal_import_script(plan),
        media_type="text/x-python",
        headers={"Content-Disposition": 'attachment; filename="cutsceneai-unreal-import.py"'},
    )
