from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from cutsceneai_performance.errors import PerformanceError

from app.models.performance_runtime import (
    PerformanceGenerateRequest,
    PerformanceReadinessResponse,
    PerformanceRunRecord,
)
from app.models.studio import StudioBridgeCommand, StudioRealizationRequest
from app.services.native_performance import NativePerformanceRealizer
from app.services.performance_executor import StudioPerformanceExecutor
from app.services.studio import StudioService
from app.services.performance_providers import PerformanceProviderConfigurationError


router = APIRouter(prefix="/api/v1/studio/performance", tags=["studio-performance"])


@lru_cache
def get_performance_executor() -> StudioPerformanceExecutor:
    return StudioPerformanceExecutor()


@lru_cache
def get_native_studio_service() -> StudioService:
    return StudioService()


def _bad_request(
    exc: ValueError | PerformanceError | PerformanceProviderConfigurationError,
) -> HTTPException:
    return HTTPException(status_code=422, detail=str(exc))


@router.get("/readiness", response_model=PerformanceReadinessResponse)
def performance_readiness(
    experiment_seed: int = Query(default=20260812),
    executor: StudioPerformanceExecutor = Depends(get_performance_executor),
) -> PerformanceReadinessResponse:
    try:
        return executor.readiness(experiment_seed)
    except PerformanceProviderConfigurationError as exc:
        raise _bad_request(exc) from exc


@router.post("/generate", response_model=PerformanceRunRecord)
async def generate_performance(
    request: PerformanceGenerateRequest,
    executor: StudioPerformanceExecutor = Depends(get_performance_executor),
    studio: StudioService = Depends(get_native_studio_service),
) -> PerformanceRunRecord:
    if request.project_id is None:
        return await executor.generate(request)

    conditioned_project = studio.scene_conditioned_project(
        request.project_id,
        request.project,
        request.bindings,
    )
    conditioned_request = request.model_copy(
        update={"project": conditioned_project},
        deep=True,
    )
    return await executor.generate(conditioned_request)


@router.get("/runs", response_model=list[PerformanceRunRecord])
def list_performance_runs(
    limit: int = Query(default=50, ge=1, le=200),
    executor: StudioPerformanceExecutor = Depends(get_performance_executor),
) -> list[PerformanceRunRecord]:
    try:
        return executor.list_runs(limit)
    except (ValueError, PerformanceError) as exc:
        raise _bad_request(exc) from exc


@router.get("/runs/{run_id}", response_model=PerformanceRunRecord)
def get_performance_run(
    run_id: str,
    executor: StudioPerformanceExecutor = Depends(get_performance_executor),
) -> PerformanceRunRecord:
    try:
        return executor.get_run(run_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.get("/runs/{run_id}/bundle", response_model=None)
def download_performance_bundle(
    run_id: str,
    executor: StudioPerformanceExecutor = Depends(get_performance_executor),
) -> Response:
    try:
        data = executor.bundle_bytes(run_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition": (f'attachment; filename="cutsceneai-performance-{run_id}.zip"')
        },
    )


@router.post(
    "/runs/{run_id}/realize",
    response_model=StudioBridgeCommand,
)
def realize_performance_run(
    run_id: str,
    request: StudioRealizationRequest,
    executor: StudioPerformanceExecutor = Depends(get_performance_executor),
    studio: StudioService = Depends(get_native_studio_service),
) -> StudioBridgeCommand:
    try:
        return NativePerformanceRealizer(
            studio=studio,
            performance=executor,
        ).realize(
            run_id=run_id,
            project_id=request.project_id,
            project=request.project,
            bindings=request.bindings,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc
