from typing import Any

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError

from app.api.cir_errors import domain_failure, failure_response, structural_failure
from app.models.cir import CIRValidationFailure, CIRValidationProblem
from app.models.dialogue import DialogueFailure
from cutsceneai_cir import CIRValidationError, Project, validate_project
from cutsceneai_dialogue import (
    MAX_DIALOGUE_BUNDLE_BYTES,
    DialogueInputError,
    DialogueOutputError,
    load_dialogue_bundle,
)
from cutsceneai_unreal import (
    UnrealExportPlan,
    compile_dialogue_bundle,
    compile_project,
    render_unreal_dialogue_import_package,
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


def _dialogue_bundle_failure(code: str, message: str, *, status_code: int = 422) -> JSONResponse:
    body = DialogueFailure(code=code, message=message)
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


@router.post(
    "/dialogue-bundle",
    response_model=None,
    responses={
        200: {"content": {"application/zip": {}}},
        413: {"model": DialogueFailure},
        422: {"model": DialogueFailure},
    },
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/zip": {"schema": {"type": "string", "format": "binary"}}},
        }
    },
)
async def export_unreal_dialogue_bundle(
    request: Request,
) -> Response | JSONResponse:
    """Verify a Dialogue v0.1 bundle and package its WAV files for Unreal 5.8."""

    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared_size = int(content_length)
        except ValueError:
            return _dialogue_bundle_failure(
                "invalid_dialogue_bundle",
                "Dialogue bundle Content-Length is invalid.",
            )
        if declared_size > MAX_DIALOGUE_BUNDLE_BYTES:
            return _dialogue_bundle_failure(
                "dialogue_bundle_too_large",
                f"Dialogue bundle exceeds the {MAX_DIALOGUE_BUNDLE_BYTES}-byte v0.1 limit.",
                status_code=413,
            )

    payload = bytearray()
    async for chunk in request.stream():
        if len(payload) + len(chunk) > MAX_DIALOGUE_BUNDLE_BYTES:
            return _dialogue_bundle_failure(
                "dialogue_bundle_too_large",
                f"Dialogue bundle exceeds the {MAX_DIALOGUE_BUNDLE_BYTES}-byte v0.1 limit.",
                status_code=413,
            )
        payload.extend(chunk)

    try:
        dialogue_bundle = load_dialogue_bundle(bytes(payload))
        package = compile_dialogue_bundle(dialogue_bundle)
        content = render_unreal_dialogue_import_package(package)
    except DialogueInputError as exc:
        return _dialogue_bundle_failure("invalid_dialogue_bundle", str(exc))
    except (DialogueOutputError, ValueError, RuntimeError) as exc:
        return _dialogue_bundle_failure("unreal.dialogue_import_failed", str(exc))

    return Response(
        content=content,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{dialogue_bundle.project.id}.unreal-v0.6.zip"'
            ),
            "X-CutSceneAI-Unreal-Adapter-Version": "0.6.0",
            "X-CutSceneAI-Unreal-Audio-Imports": str(len(package.plan.audio_imports)),
        },
    )
