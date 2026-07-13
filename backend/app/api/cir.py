from typing import Any

from fastapi import APIRouter, Body
from pydantic import ValidationError

from app.api.cir_errors import domain_failure, structural_failure
from app.models.cir import CIRValidationFailure, CIRValidationSuccess, CIRValidationSummary
from cutsceneai_cir import CIRValidationError, validate_project


router = APIRouter(prefix="/api/v1/cir", tags=["cir"])


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
        return structural_failure(exc)
    except CIRValidationError as exc:
        return domain_failure(exc)

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
