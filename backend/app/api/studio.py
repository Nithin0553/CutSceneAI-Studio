from functools import lru_cache
from typing import Any

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
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.models.studio import (
    StudioBindingManifest,
    StudioBindingOptionsRequest,
    StudioBindingOptionsResponse,
    StudioBindingValidateRequest,
    StudioBridgeCommand,
    StudioBridgeCommandRequest,
    StudioBridgeCommandResultRequest,
    StudioBridgeCommandType,
    StudioBridgeHeartbeatRequest,
    StudioBridgeInstallResponse,
    StudioBridgeManifestRequest,
    StudioBridgePollResponse,
    StudioCapabilityResponse,
    StudioPerformancePlanRequest,
    StudioProjectConnectRequest,
    StudioProjectRecord,
    StudioRealizationRequest,
    StudioRealizationResponse,
    StudioCIRRevision,
    StudioRevisionCreateRequest,
)
from app.services.studio import StudioService


router = APIRouter(prefix="/api/v1/studio", tags=["studio"])


@lru_cache
def get_studio_service() -> StudioService:
    return StudioService()


def _bad_request(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=422, detail=str(exc))


@router.get("/capabilities", response_model=StudioCapabilityResponse)
def capabilities(
    service: StudioService = Depends(get_studio_service),
) -> StudioCapabilityResponse:
    return service.capabilities()


@router.get("/projects", response_model=list[StudioProjectRecord])
def list_projects(
    service: StudioService = Depends(get_studio_service),
) -> list[StudioProjectRecord]:
    return service.list_projects()


@router.post("/projects/connect", response_model=StudioProjectRecord)
def connect_project(
    request: StudioProjectConnectRequest,
    service: StudioService = Depends(get_studio_service),
) -> StudioProjectRecord:
    try:
        return service.connect_project(request)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post("/projects/{project_id}/scan", response_model=StudioProjectRecord)
def scan_project(
    project_id: str,
    service: StudioService = Depends(get_studio_service),
) -> StudioProjectRecord:
    try:
        return service.scan_project(project_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post("/projects/{project_id}/bridge-manifest", response_model=StudioProjectRecord)
def update_bridge_manifest(
    project_id: str,
    request: StudioBridgeManifestRequest,
    service: StudioService = Depends(get_studio_service),
) -> StudioProjectRecord:
    try:
        return service.update_bridge_manifest(project_id, request)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post(
    "/projects/{project_id}/bridge/install",
    response_model=StudioBridgeInstallResponse,
)
def install_bridge(
    project_id: str,
    service: StudioService = Depends(get_studio_service),
) -> StudioBridgeInstallResponse:
    try:
        return service.install_bridge(project_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post(
    "/projects/{project_id}/bridge/heartbeat",
    response_model=StudioProjectRecord,
)
def bridge_heartbeat(
    project_id: str,
    request: StudioBridgeHeartbeatRequest,
    service: StudioService = Depends(get_studio_service),
) -> StudioProjectRecord:
    try:
        return service.bridge_heartbeat(project_id, request)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post(
    "/projects/{project_id}/bridge/commands",
    response_model=StudioBridgeCommand,
)
def enqueue_bridge_command(
    project_id: str,
    request: StudioBridgeCommandRequest,
    service: StudioService = Depends(get_studio_service),
) -> StudioBridgeCommand:
    try:
        return service.enqueue_bridge_command(project_id, request)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.get(
    "/projects/{project_id}/bridge/commands",
    response_model=list[StudioBridgeCommand],
)
def list_bridge_commands(
    project_id: str,
    service: StudioService = Depends(get_studio_service),
) -> list[StudioBridgeCommand]:
    try:
        return service.list_bridge_commands(project_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.get(
    "/projects/{project_id}/bridge/commands/{command_id}",
    response_model=StudioBridgeCommand,
)
def get_bridge_command(
    project_id: str,
    command_id: str,
    service: StudioService = Depends(get_studio_service),
) -> StudioBridgeCommand:
    try:
        return service.get_bridge_command(project_id, command_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.get(
    "/projects/{project_id}/bridge/poll",
    response_model=StudioBridgePollResponse,
)
def poll_bridge_command(
    project_id: str,
    agent_id: str,
    service: StudioService = Depends(get_studio_service),
) -> StudioBridgePollResponse:
    try:
        return service.poll_bridge_command(project_id, agent_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post(
    "/projects/{project_id}/bridge/commands/{command_id}/complete",
    response_model=StudioBridgeCommand,
)
def complete_bridge_command(
    project_id: str,
    command_id: str,
    request: StudioBridgeCommandResultRequest,
    service: StudioService = Depends(get_studio_service),
) -> StudioBridgeCommand:
    try:
        return service.complete_bridge_command(project_id, command_id, request)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post("/revisions", response_model=StudioCIRRevision)
def create_revision(
    request: StudioRevisionCreateRequest,
    service: StudioService = Depends(get_studio_service),
) -> StudioCIRRevision:
    try:
        return service.create_revision(request)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.get(
    "/projects/{project_id}/revisions",
    response_model=list[StudioCIRRevision],
)
def list_revisions(
    project_id: str,
    service: StudioService = Depends(get_studio_service),
) -> list[StudioCIRRevision]:
    try:
        return service.list_revisions(project_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.get(
    "/projects/{project_id}/revisions/{revision_id}",
    response_model=StudioCIRRevision,
)
def get_revision(
    project_id: str,
    revision_id: str,
    service: StudioService = Depends(get_studio_service),
) -> StudioCIRRevision:
    try:
        return service.get_revision(project_id, revision_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post("/bindings/options", response_model=StudioBindingOptionsResponse)
def binding_options(
    request: StudioBindingOptionsRequest,
    service: StudioService = Depends(get_studio_service),
) -> StudioBindingOptionsResponse:
    try:
        return service.binding_options(request.project_id, request.project)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post("/bindings/validate", response_model=StudioBindingManifest)
def validate_bindings(
    request: StudioBindingValidateRequest,
    service: StudioService = Depends(get_studio_service),
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
    service: StudioService = Depends(get_studio_service),
) -> dict[str, Any]:
    try:
        return service.performance_plan(request.project, request.experiment_seed)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post("/realization/plan", response_model=StudioRealizationResponse)
def realization_plan(
    request: StudioRealizationRequest,
    service: StudioService = Depends(get_studio_service),
) -> StudioRealizationResponse:
    try:
        return service.compile_realization(
            request.project_id,
            request.project,
            request.bindings,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc


def _render_bound_importer(
    request: StudioRealizationRequest,
    service: StudioService,
) -> tuple[StudioProjectRecord, str, str, str]:
    record = service.get_project(request.project_id)
    realization = service.compile_realization(
        request.project_id,
        request.project,
        request.bindings,
    )
    if not realization.ready:
        raise ValueError(
            "Engine realization is not ready: " + "; ".join(realization.blocking_issues)
        )

    asset_by_id = {item.object_id: item for item in record.manifest.assets}
    selected = {item.cir_id: item for item in request.bindings}

    if record.engine.value == "unity":
        entities: list[UnityEntityAsset] = []
        for cir_id, binding in selected.items():
            asset = asset_by_id[binding.project_object_id]
            if asset.engine_ref.startswith("Assets/") and asset.engine_ref.endswith(".prefab"):
                entities.append(
                    UnityEntityAsset(
                        source_entity_id=cir_id,
                        prefab_path=asset.engine_ref,
                    )
                )
        unity_plan = compile_unity_project(
            request.project,
            asset_map=UnityAssetMap(
                project_id=request.project.id,
                entities=entities,
            ),
        )
        return (
            record,
            render_unity_editor_script(unity_plan),
            "text/x-csharp",
            "CutSceneAI-Unity-Importer.cs",
        )

    bound_project = service.bound_project(
        request.project_id,
        request.project,
        request.bindings,
    )
    unreal_plan = compile_unreal_project(bound_project)
    return (
        record,
        render_unreal_import_script(
            unreal_plan,
            compile_semantics(bound_project),
        ),
        "text/x-python",
        "cutsceneai-unreal-import.py",
    )


@router.post("/realization/importer", response_model=None)
def realization_importer(
    request: StudioRealizationRequest,
    service: StudioService = Depends(get_studio_service),
) -> Response:
    try:
        _, content, media_type, filename = _render_bound_importer(request, service)
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post("/realization/execute", response_model=StudioBridgeCommand)
def execute_realization(
    request: StudioRealizationRequest,
    service: StudioService = Depends(get_studio_service),
) -> StudioBridgeCommand:
    try:
        record, content, _, _ = _render_bound_importer(request, service)
        if not record.manifest.bridge_connected:
            raise ValueError(
                "The engine bridge is not live. Open the target project and wait for its heartbeat."
            )
        importer_path = service.stage_realization_importer(
            request.project_id,
            content,
        )
        return service.enqueue_bridge_command(
            request.project_id,
            StudioBridgeCommandRequest(
                command=StudioBridgeCommandType.RUN_IMPORTER,
                payload={
                    "importer_path": importer_path,
                    "entry_point": (
                        "CutSceneAIGeneratedTimeline.ImportGeneratedTimeline"
                        if record.engine.value == "unity"
                        else "import_plan"
                    ),
                },
            ),
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc
