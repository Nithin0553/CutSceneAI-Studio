from functools import lru_cache

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.models.director import DirectorFailure, DirectorGenerateRequest, DirectorGenerateResponse
from app.services.director import DirectorConfigurationError, DirectorOutputError
from app.services.director import DirectorProviderError, DirectorService
from app.services.openai_director import OpenAIDirectorBackend

router = APIRouter(prefix="/api/v1/director", tags=["director"])


@lru_cache
def get_director_service() -> DirectorService:
    return DirectorService(OpenAIDirectorBackend())


def _failure(
    status: int, code: str, message: str, retryable: bool = False, request_id: str | None = None
) -> JSONResponse:
    body = DirectorFailure(code=code, message=message, retryable=retryable, request_id=request_id)
    return JSONResponse(status_code=status, content=body.model_dump(mode="json"))


@router.post("/generate", response_model=DirectorGenerateResponse)
async def generate_cir(
    request: DirectorGenerateRequest,
    service: DirectorService = Depends(get_director_service),
) -> DirectorGenerateResponse | JSONResponse:
    try:
        result = await service.generate(request.prompt)
    except DirectorConfigurationError as exc:
        return _failure(503, "director_not_configured", str(exc))
    except DirectorProviderError as exc:
        return _failure(502, "provider_error", str(exc), exc.retryable, exc.request_id)
    except DirectorOutputError as exc:
        return _failure(502, "invalid_provider_output", str(exc))
    return DirectorGenerateResponse(
        project=result.project,
        provider=result.provider,
        model=result.model,
        request_id=result.request_id,
    )
