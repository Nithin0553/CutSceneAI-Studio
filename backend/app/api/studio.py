from functools import lru_cache
from typing import Any

from cutsceneai_cir import Project
from cutsceneai_parity import compile_semantics
from cutsceneai_unity import (
    UnityAssetMap,
    UnityEntityAsset,
    compile_project as compile_unity_project,
    render_unity_editor_script,
)
from cutsceneai_unreal import (
    compile_project as compile_unreal_project,
    render_unreal_import_script,
)
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.models.studio import (
    StudioBindingManifest,
    StudioBindingOptionsRequest,
    StudioBindingOptionsResponse,
    StudioBindingValidateRequest,
    StudioBridgeManifestRequest,
    StudioCapabilityResponse,
    StudioPerformancePlanRequest,
    StudioProjectConnectRequest,
    StudioProjectRecord,
    StudioRealizationRequest,
    StudioRealizationResponse,
)
from app.services.studio import StudioService


router = APIRouter(prefix="/api/v1/studio", tags=["studio"])


@lru_cache
def get_studio_service() -> StudioService:
    return StudioService()


def _bad_request(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=422, detail=str(exc))


@router.get("/capabilities", response_model=StudioCapabilityResponse)
def capabilities(service: StudioService = get_studio_service()) -> StudioCapabilityResponse:
    return service.capabilities()


@router.get("/projects", response_model=list[StudioProjectRecord])
def list_projects(service: StudioService = get_studio_service()) -> list[StudioProjectRecord]:
    return service.list_projects()


@router.post("/projects/connect", response_model=StudioProjectRecord)
def connect_project(
    request: StudioProjectConnectRequest,
    service: StudioService = get_studio_service(),
) -> StudioProjectRecord:
    try:
        return service.connect_project(request)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post("/projects/{project_id}/scan", response_model=StudioProjectRecord)
def scan_project(
    project_id: str,
    service: StudioService = get_studio_service(),
) -> StudioProjectRecord:
    try:
        return service.scan_project(project_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post("/projects/{project_id}/bridge-manifest", response_model=StudioProjectRecord)
def update_bridge_manifest(
    project_id: str,
    request: StudioBridgeManifestRequest,
    service: StudioService = get_studio_service(),
) -> StudioProjectRecord:
    try:
        return service.update_bridge_manifest(project_id, request)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post("/bindings/options", response_model=StudioBindingOptionsResponse)
def binding_options(
    request: StudioBindingOptionsRequest,
    service: StudioService = get_studio_service(),
) -> StudioBindingOptionsResponse:
    try:
        return service.binding_options(request.project_id, request.project)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post("/bindings/validate", response_model=StudioBindingManifest)
def validate_bindings(
    request: StudioBindingValidateRequest,
    service: StudioService = get_studio_service(),
) -> StudioBindingManifest:
    try:
        return service.validate_bindings(
            request.project_id,
            request.project,
            request.bindings,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post("/performance/plan", response_model=dict[str, Any])
def performance_plan(
    request: StudioPerformancePlanRequest,
    service: StudioService = get_studio_service(),
) -> dict[str, Any]:
    try:
        return service.performance_plan(request.project, request.experiment_seed)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post("/realization/plan", response_model=StudioRealizationResponse)
def realization_plan(
    request: StudioRealizationRequest,
    service: StudioService = get_studio_service(),
) -> StudioRealizationResponse:
    try:
        return service.compile_realization(
            request.project_id,
            request.project,
            request.bindings,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post("/realization/importer", response_model=None)
def realization_importer(
    request: StudioRealizationRequest,
    service: StudioService = get_studio_service(),
) -> Response:
    try:
        record = service.get_project(request.project_id)
        binding_manifest = service.validate_bindings(
            request.project_id,
            request.project,
            request.bindings,
        )
        if not binding_manifest.valid:
            raise ValueError(
                "Required roles are not fully bound: "
                + ", ".join(binding_manifest.unresolved_required_ids)
            )

        asset_by_id = {item.object_id: item for item in record.manifest.assets}
        selected = {item.cir_id: item for item in request.bindings}

        if record.engine.value == "unity":
            entities: list[UnityEntityAsset] = []
            for cir_id, binding in selected.items():
                asset = asset_by_id[binding.project_object_id]
                if asset.engine_ref.startswith("Assets/") and asset.engine_ref.endswith(
                    ".prefab"
                ):
                    entities.append(
                        UnityEntityAsset(
                            source_entity_id=cir_id,
                            prefab_path=asset.engine_ref,
                        )
                    )
            plan = compile_unity_project(
                request.project,
                asset_map=UnityAssetMap(
                    project_id=request.project.id,
                    entities=entities,
                ),
            )
            return Response(
                content=render_unity_editor_script(plan),
                media_type="text/x-csharp",
                headers={
                    "Content-Disposition": 'attachment; filename="CutSceneAI-Unity-Importer.cs"'
                },
            )

        bound_project = service.bound_project(
            request.project_id,
            request.project,
            request.bindings,
        )
        plan = compile_unreal_project(bound_project)
        content = render_unreal_import_script(plan, compile_semantics(bound_project))
        return Response(
            content=content,
            media_type="text/x-python",
            headers={
                "Content-Disposition": 'attachment; filename="cutsceneai-unreal-import.py"'
            },
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc
