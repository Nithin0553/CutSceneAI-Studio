from __future__ import annotations

import os
from typing import Any

import openai
from cutsceneai_dialogue import (
    DialogueConfigurationError,
    DialogueProviderError,
    SpeechBackendResult,
    SpeechSynthesisRequest,
)
from openai import AsyncOpenAI


DEFAULT_MODEL = "gpt-4o-mini-tts"


class OpenAISpeechBackend:
    """OpenAI speech adapter that always requests WAV for deterministic timing."""

    def __init__(self, client: Any | None = None, model: str | None = None) -> None:
        self.model = model or os.getenv("CUTSCENEAI_TTS_MODEL") or DEFAULT_MODEL
        self._client = client

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            self._client = AsyncOpenAI()
        except openai.OpenAIError as exc:
            raise DialogueConfigurationError(
                "OpenAI speech is not configured. Set OPENAI_API_KEY in the server environment."
            ) from exc
        return self._client

    async def synthesize(self, request: SpeechSynthesisRequest) -> SpeechBackendResult:
        parameters: dict[str, object] = {
            "model": self.model,
            "voice": request.voice,
            "input": request.text,
            "response_format": "wav",
            "speed": request.speed,
        }
        if request.instructions is not None:
            parameters["instructions"] = request.instructions

        try:
            async with self._get_client().audio.speech.with_streaming_response.create(
                **parameters
            ) as response:
                data = await response.read()
                request_id = response.headers.get("x-request-id")
        except openai.APIConnectionError as exc:
            raise DialogueProviderError("OpenAI connection failed.", retryable=True) from exc
        except openai.RateLimitError as exc:
            raise DialogueProviderError(
                "OpenAI rate limit reached.", retryable=True, request_id=exc.request_id
            ) from exc
        except openai.APIStatusError as exc:
            raise DialogueProviderError(
                "OpenAI speech request failed.",
                retryable=exc.status_code >= 500,
                request_id=exc.request_id,
            ) from exc

        return SpeechBackendResult(
            data=data,
            provider="openai",
            model=self.model,
            voice=request.voice,
            request_id=request_id,
        )
