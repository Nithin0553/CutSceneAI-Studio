from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from .camera import CameraCurveArtifact, resample_camera_curves
from .errors import PerformanceOutputError
from .facial import FacialCurveArtifact, resample_facial_curves
from .models import (
    BodyGenerationRequest,
    CameraGenerationRequest,
    FacialGenerationRequest,
    GenerationRequest,
    ModelProvenance,
)
from .motion import BodyMotionArtifact, resample_body_motion

ArtifactT = TypeVar("ArtifactT")


@dataclass(frozen=True, slots=True)
class ProviderArtifact(Generic[ArtifactT]):
    """Canonical provider samples plus the exact request metadata used to create them."""

    request_semantic_id: str
    artifact: ArtifactT
    provider: str
    model: str
    model_revision: str
    prompt_sha256: str
    configuration_sha256: str
    seed: int
    generated_at_inference: bool
    retrieved_pre_authored_clip: bool
    deterministic_algorithms: bool


@dataclass(frozen=True, slots=True)
class NormalizedArtifact(Generic[ArtifactT]):
    """Provider output validated and fitted to its exact generation-request window."""

    request_semantic_id: str
    artifact: ArtifactT
    provenance: ModelProvenance


class BodyGenerationBackend(Protocol):
    async def generate_body(
        self, request: BodyGenerationRequest
    ) -> ProviderArtifact[BodyMotionArtifact]: ...


class FacialGenerationBackend(Protocol):
    async def generate_facial(
        self, request: FacialGenerationRequest
    ) -> ProviderArtifact[FacialCurveArtifact]: ...


class CameraGenerationBackend(Protocol):
    async def generate_camera(
        self, request: CameraGenerationRequest
    ) -> ProviderArtifact[CameraCurveArtifact]: ...


def _provenance(
    request: GenerationRequest,
    output: ProviderArtifact[ArtifactT],
) -> ModelProvenance:
    echoed_fields = {
        "request_semantic_id": (request.semantic_id, output.request_semantic_id),
        "provider": (request.provider, output.provider),
        "model": (request.model, output.model),
        "model_revision": (request.model_revision, output.model_revision),
        "prompt_sha256": (request.prompt_sha256, output.prompt_sha256),
        "configuration_sha256": (
            request.configuration_sha256,
            output.configuration_sha256,
        ),
        "seed": (request.seed, output.seed),
    }
    mismatches = [
        name for name, (expected, actual) in echoed_fields.items() if expected != actual
    ]
    if mismatches:
        raise PerformanceOutputError(
            f"Provider output for '{request.semantic_id}' does not match request fields: "
            + ", ".join(mismatches)
            + "."
        )
    if output.generated_at_inference is not True:
        raise PerformanceOutputError(
            f"Provider output for '{request.semantic_id}' was not generated at inference time."
        )
    if output.retrieved_pre_authored_clip is not False:
        raise PerformanceOutputError(
            f"Provider output for '{request.semantic_id}' retrieved a pre-authored clip."
        )
    if not isinstance(output.deterministic_algorithms, bool):
        raise PerformanceOutputError(
            f"Provider output for '{request.semantic_id}' returned invalid determinism metadata."
        )
    return ModelProvenance(
        provider=output.provider,
        model=output.model,
        model_revision=output.model_revision,
        prompt_sha256=output.prompt_sha256,
        configuration_sha256=output.configuration_sha256,
        seed=output.seed,
        deterministic_algorithms=output.deterministic_algorithms,
    )


def normalize_body_output(
    request: BodyGenerationRequest,
    output: ProviderArtifact[BodyMotionArtifact],
    *,
    target_fps: int,
) -> NormalizedArtifact[BodyMotionArtifact]:
    """Validate and fit canonical body provider output to its request window."""

    provenance = _provenance(request, output)
    if output.artifact.skeleton_profile != request.skeleton_profile:
        raise PerformanceOutputError(
            f"Body output for '{request.semantic_id}' uses skeleton profile "
            f"'{output.artifact.skeleton_profile}', expected '{request.skeleton_profile}'."
        )
    artifact = resample_body_motion(
        output.artifact,
        target_fps=target_fps,
        target_frame_count=request.end_frame - request.start_frame,
    )
    return NormalizedArtifact(
        request_semantic_id=request.semantic_id,
        artifact=artifact,
        provenance=provenance,
    )


def normalize_facial_output(
    request: FacialGenerationRequest,
    output: ProviderArtifact[FacialCurveArtifact],
    *,
    target_fps: int,
) -> NormalizedArtifact[FacialCurveArtifact]:
    """Validate and fit canonical facial provider output to its request window."""

    provenance = _provenance(request, output)
    if output.artifact.curve_profile != request.curve_profile:
        raise PerformanceOutputError(
            f"Facial output for '{request.semantic_id}' uses curve profile "
            f"'{output.artifact.curve_profile}', expected '{request.curve_profile}'."
        )
    artifact = resample_facial_curves(
        output.artifact,
        target_fps=target_fps,
        target_frame_count=request.end_frame - request.start_frame,
    )
    return NormalizedArtifact(
        request_semantic_id=request.semantic_id,
        artifact=artifact,
        provenance=provenance,
    )


def normalize_camera_output(
    request: CameraGenerationRequest,
    output: ProviderArtifact[CameraCurveArtifact],
    *,
    target_fps: int,
) -> NormalizedArtifact[CameraCurveArtifact]:
    """Validate and fit canonical camera provider output to its request window."""

    provenance = _provenance(request, output)
    artifact = resample_camera_curves(
        output.artifact,
        target_fps=target_fps,
        target_frame_count=request.end_frame - request.start_frame,
    )
    return NormalizedArtifact(
        request_semantic_id=request.semantic_id,
        artifact=artifact,
        provenance=provenance,
    )
