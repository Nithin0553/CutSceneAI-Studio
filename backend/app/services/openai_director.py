import os
from typing import Any

import openai
from cutsceneai_cir import Project
from openai import AsyncOpenAI

from app.services.director import DirectorBackendResult, DirectorConfigurationError
from app.services.director import DirectorOutputError, DirectorProviderError

DEFAULT_MODEL = "gpt-5.6-terra"
SYSTEM_PROMPT = """You are the Director Agent for CutSceneAI Studio.
Convert the user's scene idea into exactly one complete CIR 0.1 Project.
Use stable lowercase IDs and SI units. Every scene needs non-overlapping beats and shots,
an establishing shot, and an environment-detail shot for each focused object. Declare every
referenced character and environment object. Plan camera, body motion, facial performance,
dialogue, blocking, and narrative intent. Timelines must fit their scene duration.
Return only the structured Project requested by the response schema.
"""

EDIT_SYSTEM_PROMPT = """You are the Director Editor for CutSceneAI Studio.
Apply the user's requested cinematic edit to the supplied CIR 0.1 Project while preserving all
unaffected intent, IDs, timing, entities, and structure whenever possible. Keep the project valid:
beats and shots must fit the scene duration, references must resolve, and every scene must retain
the required establishing/environment coverage. Make the smallest coherent revision that satisfies
the instruction. Return exactly one complete structured Project, never a patch or explanation.
"""


class OpenAIDirectorBackend:
    def __init__(self, client: Any | None = None, model: str | None = None) -> None:
        self.model = model or os.getenv("CUTSCENEAI_DIRECTOR_MODEL") or DEFAULT_MODEL
        try:
            self._client = client or AsyncOpenAI()
        except openai.OpenAIError as exc:
            raise DirectorConfigurationError(
                "OpenAI is not configured. Set OPENAI_API_KEY in the server environment."
            ) from exc

    async def generate(self, prompt: str) -> DirectorBackendResult:
        try:
            response = await self._client.responses.parse(
                model=self.model,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                text_format=Project,
            )
        except openai.APIConnectionError as exc:
            raise DirectorProviderError("OpenAI connection failed.", retryable=True) from exc
        except openai.RateLimitError as exc:
            raise DirectorProviderError(
                "OpenAI rate limit reached.", retryable=True, request_id=exc.request_id
            ) from exc
        except openai.APIStatusError as exc:
            raise DirectorProviderError(
                "OpenAI request failed.",
                retryable=exc.status_code >= 500,
                request_id=exc.request_id,
            ) from exc

        project = response.output_parsed
        if project is None:
            raise DirectorOutputError("OpenAI returned no structured CIR project.")
        return DirectorBackendResult(
            project=project,
            provider="openai",
            model=self.model,
            request_id=getattr(response, "_request_id", None),
        )

    async def edit(self, project: Project, instruction: str) -> DirectorBackendResult:
        try:
            response = await self._client.responses.parse(
                model=self.model,
                input=[
                    {"role": "system", "content": EDIT_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            "CURRENT CIR:\n"
                            + project.model_dump_json(indent=2)
                            + "\n\nEDIT INSTRUCTION:\n"
                            + instruction
                        ),
                    },
                ],
                text_format=Project,
            )
        except openai.APIConnectionError as exc:
            raise DirectorProviderError("OpenAI connection failed.", retryable=True) from exc
        except openai.RateLimitError as exc:
            raise DirectorProviderError(
                "OpenAI rate limit reached.", retryable=True, request_id=exc.request_id
            ) from exc
        except openai.APIStatusError as exc:
            raise DirectorProviderError(
                "OpenAI request failed.",
                retryable=exc.status_code >= 500,
                request_id=exc.request_id,
            ) from exc

        revised = response.output_parsed
        if revised is None:
            raise DirectorOutputError("OpenAI returned no structured edited CIR project.")
        return DirectorBackendResult(
            project=revised,
            provider="openai",
            model=self.model,
            request_id=getattr(response, "_request_id", None),
        )
