from typing import Any

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError

from app.api.cir_errors import domain_failure, structural_failure
from app.models.cir import CIRValidationFailure
from cutsceneai_cir import CIRValidationError, Project, validate_project
from cutsceneai_preview import PreviewManifest, compile_project, render_storyboard_svg


router = APIRouter(prefix="/api/v1/preview", tags=["preview"])


def _validate(payload: Any) -> Project | JSONResponse:
    try:
        return validate_project(payload)
    except ValidationError as exc:
        return structural_failure(exc)
    except CIRValidationError as exc:
        return domain_failure(exc)


@router.post(
    "/compile",
    response_model=PreviewManifest,
    responses={422: {"model": CIRValidationFailure}},
)
def compile_preview(payload: Any = Body(...)) -> PreviewManifest | JSONResponse:
    """Compile CIR into an engine-neutral preview manifest."""

    project = _validate(payload)
    if isinstance(project, JSONResponse):
        return project
    return compile_project(project)


@router.post(
    "/storyboard.svg",
    response_model=None,
    responses={
        200: {"content": {"image/svg+xml": {}}},
        422: {"model": CIRValidationFailure},
    },
)
def render_storyboard(payload: Any = Body(...)) -> Response | JSONResponse:
    """Render a deterministic storyboard timeline from CIR."""

    project = _validate(payload)
    if isinstance(project, JSONResponse):
        return project
    svg = render_storyboard_svg(compile_project(project))
    return Response(content=svg, media_type="image/svg+xml")
