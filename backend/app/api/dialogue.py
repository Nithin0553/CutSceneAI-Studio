from functools import lru_cache
from typing import Any

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError

from app.api.cir_errors import domain_failure, structural_failure
from app.models.cir import CIRValidationFailure
from app.models.dialogue import DialogueFailure, DialogueSynthesizeRequest
from app.services.openai_speech import OpenAISpeechBackend
from cutsceneai_cir import CIRValidationError, validate_project, validate_project_model
from cutsceneai_dialogue import (
    DialogueConfigurationError,
    DialogueEngine,
    DialogueInputError,
    DialogueOutputError,
    DialogueProviderError,
    DialogueRenderPlan,
    plan_project,
    render_dialogue_bundle,
)


router = APIRouter(prefix="/api/v1/dialogue", tags=["dialogue"])


@lru_cache
def get_dialogue_engine() -> DialogueEngine:
    return DialogueEngine(OpenAISpeechBackend())


def _failure(
    status: int,
    code: str,
    message: str,
    retryable: bool = False,
    request_id: str | None = None,
) -> JSONResponse:
    body = DialogueFailure(
        code=code,
        message=message,
        retryable=retryable,
        request_id=request_id,
    )
    return JSONResponse(status_code=status, content=body.model_dump(mode="json"))


@router.post(
    "/plan",
    response_model=DialogueRenderPlan,
    responses={422: {"model": CIRValidationFailure}},
)
def plan_dialogue(payload: Any = Body(...)) -> DialogueRenderPlan | JSONResponse:
    """Return stable dialogue cues and frame positions without calling a provider."""

    try:
        project = validate_project(payload)
    except ValidationError as exc:
        return structural_failure(exc)
    except CIRValidationError as exc:
        return domain_failure(exc)
    return plan_project(project)


@router.post(
    "/synthesize",
    responses={
        200: {"content": {"application/zip": {}}},
        422: {"model": DialogueFailure},
        502: {"model": DialogueFailure},
        503: {"model": DialogueFailure},
    },
)
async def synthesize_dialogue(
    request: DialogueSynthesizeRequest,
    engine: DialogueEngine = Depends(get_dialogue_engine),
) -> Response:
    """Generate a portable WAV dialogue bundle with provenance and exact timing."""

    try:
        validate_project_model(request.project)
        bundle = await engine.synthesize_project(
            request.project,
            default_voice=request.default_voice,
            voices=request.voices,
            replace_existing=request.replace_existing,
        )
    except CIRValidationError as exc:
        return _failure(422, "invalid_cir", str(exc))
    except DialogueInputError as exc:
        return _failure(422, "invalid_dialogue_request", str(exc))
    except DialogueConfigurationError as exc:
        return _failure(503, "speech_not_configured", str(exc))
    except DialogueProviderError as exc:
        return _failure(502, "provider_error", str(exc), exc.retryable, exc.request_id)
    except DialogueOutputError as exc:
        return _failure(502, "invalid_provider_output", str(exc))

    content = render_dialogue_bundle(bundle)
    return Response(
        content=content,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{request.project.id}.dialogue-v0.1.zip"'
            ),
            "X-CutSceneAI-Dialogue-Version": "0.1.0",
            "X-CutSceneAI-Dialogue-Clips": str(len(bundle.manifest.clips)),
            "X-CutSceneAI-AI-Voice-Disclosure": "required",
        },
    )
