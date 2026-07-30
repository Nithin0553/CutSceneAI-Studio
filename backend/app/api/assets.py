from typing import Any

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.api.cir_errors import format_location
from app.models.assets import AssetResolutionFailure, AssetResolutionProblem
from cutsceneai_assets import (
    AssetResolutionPlan,
    AssetResolutionRequest,
    AssetValidationError,
    resolve_project,
)
from cutsceneai_cir import CIRValidationError


router = APIRouter(prefix="/api/v1/assets", tags=["asset-resolution"])


def _failure(problems: list[AssetResolutionProblem]) -> JSONResponse:
    failure = AssetResolutionFailure(errors=problems)
    return JSONResponse(status_code=422, content=failure.model_dump(mode="json"))


def resolve_asset_request(
    payload: Any,
) -> tuple[AssetResolutionRequest, AssetResolutionPlan] | JSONResponse:
    try:
        request = AssetResolutionRequest.model_validate(payload)
        plan = resolve_project(request.project, request.asset_index)
    except ValidationError as exc:
        return _failure(
            [
                AssetResolutionProblem(
                    code=f"structural.{error['type']}",
                    path=format_location(error["loc"]),
                    message=error["msg"],
                )
                for error in exc.errors(
                    include_url=False,
                    include_context=False,
                    include_input=False,
                )
            ]
        )
    except CIRValidationError as exc:
        return _failure(
            [
                AssetResolutionProblem(
                    code=issue.code,
                    path=("project" if issue.path == "$" else f"project.{issue.path}"),
                    message=issue.message,
                )
                for issue in exc.issues
            ]
        )
    except AssetValidationError as exc:
        return _failure(
            [
                AssetResolutionProblem(
                    code=issue.code,
                    path=f"asset_index.{issue.path}",
                    message=issue.message,
                )
                for issue in exc.issues
            ]
        )
    return request, plan


@router.post(
    "/resolve",
    response_model=AssetResolutionPlan,
    responses={422: {"model": AssetResolutionFailure}},
)
def resolve_assets(payload: Any = Body(...)) -> AssetResolutionPlan | JSONResponse:
    """Resolve CIR environment intent against a project Asset Index."""

    result = resolve_asset_request(payload)
    if isinstance(result, JSONResponse):
        return result
    _, plan = result
    return plan
