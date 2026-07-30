import json
from json import JSONDecodeError
from typing import Annotated, Any

from fastapi import APIRouter, Body, File, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError

from app.api.assets import resolve_asset_request
from app.api.cir_errors import domain_failure, failure_response, structural_failure
from app.models.assets import AssetResolutionFailure, AssetResolutionProblem
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
    compile_environment_package,
    compile_project,
    render_unreal_asset_index_script,
    render_unreal_dialogue_import_package,
    render_unreal_environment_import_package,
    render_unreal_import_script,
)


router = APIRouter(prefix="/api/v1/adapters/unreal", tags=["unreal-adapter"])
MAX_ASSET_INDEX_BYTES = 20 * 1024 * 1024
_UPLOAD_CHUNK_BYTES = 1024 * 1024


class _UploadTooLarge(ValueError):
    pass


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


@router.get(
    "/asset-indexer.py",
    response_model=None,
    responses={200: {"content": {"text/x-python": {}}}},
)
def export_unreal_asset_indexer() -> Response:
    """Render a read-only Unreal 5.8 Static Mesh project indexer."""

    return Response(
        content=render_unreal_asset_index_script(),
        media_type="text/x-python",
        headers={
            "Content-Disposition": ('attachment; filename="cutsceneai-unreal-asset-index.py"')
        },
    )


def _asset_bundle_failure(
    code: str,
    message: str,
    *,
    path: str = "$",
    status_code: int = 422,
) -> JSONResponse:
    failure = AssetResolutionFailure(
        errors=[
            AssetResolutionProblem(
                code=code,
                path=path,
                message=message,
            )
        ]
    )
    return JSONResponse(
        status_code=status_code,
        content=failure.model_dump(mode="json"),
    )


@router.post(
    "/environment-bundle",
    response_model=None,
    responses={
        200: {"content": {"application/zip": {}}},
        422: {"model": AssetResolutionFailure},
    },
)
def export_unreal_environment_bundle(
    payload: Any = Body(...),
) -> Response | JSONResponse:
    """Resolve project assets and package an editable Unreal 5.8 scene importer."""

    result = resolve_asset_request(payload)
    if isinstance(result, JSONResponse):
        return result
    request, resolution = result
    try:
        package = compile_environment_package(
            request.project,
            request.asset_index,
            asset_resolution=resolution,
        )
        content = render_unreal_environment_import_package(package)
    except (ValueError, RuntimeError) as exc:
        return _asset_bundle_failure(
            "unreal.environment_import_failed",
            str(exc),
        )

    return Response(
        content=content,
        media_type="application/zip",
        headers={
            "Content-Disposition": (f'attachment; filename="{request.project.id}.unreal-v0.7.zip"'),
            "X-CutSceneAI-Unreal-Adapter-Version": "0.7.0",
            "X-CutSceneAI-Asset-Resolutions": str(len(package.asset_resolution.resolutions)),
            "X-CutSceneAI-Asset-Warnings": str(len(package.asset_resolution.warnings)),
        },
    )


async def _read_limited_upload(
    upload: UploadFile,
    *,
    limit: int,
    label: str,
) -> bytes:
    payload = bytearray()
    while chunk := await upload.read(_UPLOAD_CHUNK_BYTES):
        if len(payload) + len(chunk) > limit:
            raise _UploadTooLarge(f"{label} exceeds the {limit}-byte limit.")
        payload.extend(chunk)
    return bytes(payload)


@router.post(
    "/dialogue-environment-bundle",
    response_model=None,
    responses={
        200: {"content": {"application/zip": {}}},
        413: {"model": AssetResolutionFailure},
        422: {"model": AssetResolutionFailure},
    },
)
async def export_unreal_dialogue_environment_bundle(
    dialogue_bundle_file: Annotated[
        UploadFile,
        File(description="Verified Dialogue v0.1 ZIP bundle."),
    ],
    asset_index_file: Annotated[
        UploadFile,
        File(description="Reviewed Asset Index v0.1 JSON file."),
    ],
) -> Response | JSONResponse:
    """Compose exact Dialogue timing and reviewed environment assets in one package."""

    try:
        dialogue_payload = await _read_limited_upload(
            dialogue_bundle_file,
            limit=MAX_DIALOGUE_BUNDLE_BYTES,
            label="Dialogue bundle",
        )
        asset_index_payload = await _read_limited_upload(
            asset_index_file,
            limit=MAX_ASSET_INDEX_BYTES,
            label="Asset Index",
        )
    except _UploadTooLarge as exc:
        return _asset_bundle_failure(
            "unreal.dialogue_environment_bundle_too_large",
            str(exc),
            status_code=413,
        )

    try:
        dialogue_bundle = load_dialogue_bundle(dialogue_payload)
    except DialogueInputError as exc:
        return _asset_bundle_failure(
            "invalid_dialogue_bundle",
            str(exc),
            path="dialogue_bundle",
        )

    try:
        asset_index_data = json.loads(asset_index_payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, JSONDecodeError) as exc:
        return _asset_bundle_failure(
            "invalid_asset_index",
            f"Asset Index is not readable JSON: {exc}",
            path="asset_index",
        )

    result = resolve_asset_request(
        {
            "project": dialogue_bundle.project.model_dump(mode="json"),
            "asset_index": asset_index_data,
        }
    )
    if isinstance(result, JSONResponse):
        return result
    request, resolution = result

    try:
        package = compile_dialogue_bundle(
            dialogue_bundle,
            asset_index=request.asset_index,
            asset_resolution=resolution,
        )
        content = render_unreal_dialogue_import_package(package)
    except (DialogueInputError, DialogueOutputError, ValueError, RuntimeError) as exc:
        return _asset_bundle_failure(
            "unreal.dialogue_environment_import_failed",
            str(exc),
        )

    return Response(
        content=content,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{dialogue_bundle.project.id}.'
                'dialogue-environment.unreal-v0.7.zip"'
            ),
            "X-CutSceneAI-Unreal-Adapter-Version": "0.7.0",
            "X-CutSceneAI-Unreal-Audio-Imports": str(len(package.plan.audio_imports)),
            "X-CutSceneAI-Asset-Resolutions": str(len(resolution.resolutions)),
            "X-CutSceneAI-Asset-Warnings": str(len(resolution.warnings)),
        },
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
                f'attachment; filename="{dialogue_bundle.project.id}.unreal-v0.7.zip"'
            ),
            "X-CutSceneAI-Unreal-Adapter-Version": "0.7.0",
            "X-CutSceneAI-Unreal-Audio-Imports": str(len(package.plan.audio_imports)),
        },
    )
