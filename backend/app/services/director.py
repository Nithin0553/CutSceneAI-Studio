from dataclasses import dataclass, replace
from typing import Protocol

from cutsceneai_cir import CIRValidationError, GenerationMetadata, Project, validate_project_model

PROMPT_VERSION = "director-v0.1"
EDIT_PROMPT_VERSION = "director-edit-v0.1"


class DirectorError(RuntimeError):
    """Base error for Director generation."""


class DirectorConfigurationError(DirectorError):
    pass


class DirectorProviderError(DirectorError):
    def __init__(self, message: str, *, retryable: bool, request_id: str | None = None) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.request_id = request_id


class DirectorOutputError(DirectorError):
    pass


@dataclass(frozen=True, slots=True)
class DirectorBackendResult:
    project: Project
    provider: str
    model: str
    request_id: str | None = None


class DirectorBackend(Protocol):
    async def generate(self, prompt: str) -> DirectorBackendResult: ...

    async def edit(self, project: Project, instruction: str) -> DirectorBackendResult: ...


class DirectorService:
    def __init__(self, backend: DirectorBackend) -> None:
        self._backend = backend

    async def generate(self, prompt: str) -> DirectorBackendResult:
        result = await self._backend.generate(prompt)
        project = result.project.model_copy(
            update={
                "generation": GenerationMetadata(
                    generator=f"{result.provider}-director",
                    model=result.model,
                    prompt_version=PROMPT_VERSION,
                )
            }
        )
        try:
            validate_project_model(project)
        except CIRValidationError as exc:
            raise DirectorOutputError(f"Generated CIR failed domain validation: {exc}") from exc
        return replace(result, project=project)

    async def edit(self, project: Project, instruction: str) -> DirectorBackendResult:
        result = await self._backend.edit(project, instruction)
        revised = result.project.model_copy(
            update={
                "generation": GenerationMetadata(
                    generator=f"{result.provider}-director",
                    model=result.model,
                    prompt_version=EDIT_PROMPT_VERSION,
                )
            }
        )
        try:
            validate_project_model(revised)
        except CIRValidationError as exc:
            raise DirectorOutputError(f"Edited CIR failed domain validation: {exc}") from exc
        return replace(result, project=revised)
