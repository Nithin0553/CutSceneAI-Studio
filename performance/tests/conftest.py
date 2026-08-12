from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import TypeVar
import wave

import pytest
from cutsceneai_performance import (
    ARKIT_52_CURVES,
    CANONICAL_HUMANOID_JOINTS,
    BodyGenerationRequest,
    BodyMotionArtifact,
    BodyMotionSample,
    CameraCurveArtifact,
    CameraCurveSample,
    CameraGenerationRequest,
    DialogueAudioArtifact,
    FacialCurveArtifact,
    FacialCurveSample,
    FacialGenerationRequest,
    PerformanceGenerationPlan,
    ProviderArtifact,
    Quaternion,
    Vector3,
)
from cutsceneai_performance.models import GenerationRequest

SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
ArtifactT = TypeVar("ArtifactT")


@dataclass(frozen=True, slots=True)
class PerformanceFixture:
    plan: PerformanceGenerationPlan
    body_outputs: tuple[ProviderArtifact[BodyMotionArtifact], ...]
    facial_outputs: tuple[ProviderArtifact[FacialCurveArtifact], ...]
    camera_outputs: tuple[ProviderArtifact[CameraCurveArtifact], ...]
    audio_outputs: tuple[DialogueAudioArtifact, ...]


def _request_fields(semantic_id: str) -> dict[str, object]:
    return {
        "semantic_id": semantic_id,
        "start_frame": 0,
        "end_frame": 4,
        "prompt": f"Generate {semantic_id}",
        "prompt_sha256": SHA_A,
        "configuration_sha256": SHA_B,
        "seed": 42,
        "provider": "fixture-provider",
        "model": "fixture-model",
        "model_revision": "fixture-revision",
        "prompt_version": "fixture-v1",
    }


def _plan() -> PerformanceGenerationPlan:
    return PerformanceGenerationPlan(
        project_id="fixture-project",
        cir_fingerprint_sha256=SHA_C,
        fps=24,
        duration_frames=4,
        experiment_seed=42,
        body_requests=[
            BodyGenerationRequest(
                **_request_fields("body:fixture:mina"),
                actor_binding_id="actor:mina",
                source_performance_cue_id="performance:fixture:mina",
                skeleton_profile="cutsceneai-humanoid-v1",
            )
        ],
        facial_requests=[
            FacialGenerationRequest(
                **_request_fields("face:fixture:mina"),
                actor_binding_id="actor:mina",
                source_performance_cue_id="performance:fixture:mina",
                source_dialogue_cue_id="dialogue:fixture:mina",
                curve_profile="arkit-52",
                emotion="focused",
                emotion_intensity=0.5,
                lip_sync=True,
                dialogue_text="We need a deterministic fixture.",
                dialogue_start_frame=1,
            )
        ],
        camera_requests=[
            CameraGenerationRequest(
                **_request_fields("camera-motion:fixture:shot"),
                camera_binding_id="camera:fixture-shot",
                source_camera_cut_id="camera:fixture:shot",
                subject_binding_ids=["actor:mina"],
                target_binding_ids=[],
                lens_mm=50.0,
            )
        ],
    )


def _identity_rotations() -> list[Quaternion]:
    return [Quaternion(x=0.0, y=0.0, z=0.0, w=1.0) for _ in CANONICAL_HUMANOID_JOINTS]


def _body_artifact() -> BodyMotionArtifact:
    return BodyMotionArtifact(
        fps=12,
        frame_count=2,
        samples=[
            BodyMotionSample(
                frame_index=0,
                root_translation=Vector3(x=0.0, y=0.0, z=0.0),
                joint_rotations=_identity_rotations(),
            ),
            BodyMotionSample(
                frame_index=1,
                root_translation=Vector3(x=1.0, y=0.0, z=0.0),
                joint_rotations=_identity_rotations(),
            ),
        ],
    )


def _facial_artifact() -> FacialCurveArtifact:
    return FacialCurveArtifact(
        fps=12,
        frame_count=2,
        samples=[
            FacialCurveSample(
                frame_index=0,
                weights=[0.0 for _ in ARKIT_52_CURVES],
            ),
            FacialCurveSample(
                frame_index=1,
                weights=[1.0 for _ in ARKIT_52_CURVES],
            ),
        ],
    )


def _camera_artifact() -> CameraCurveArtifact:
    return CameraCurveArtifact(
        fps=12,
        frame_count=2,
        samples=[
            CameraCurveSample(
                frame_index=0,
                position=Vector3(x=0.0, y=1.0, z=2.0),
                rotation=Quaternion(x=0.0, y=0.0, z=0.0, w=1.0),
                focal_length_mm=35.0,
            ),
            CameraCurveSample(
                frame_index=1,
                position=Vector3(x=1.0, y=2.0, z=3.0),
                rotation=Quaternion(x=0.0, y=1.0, z=0.0, w=0.0),
                focal_length_mm=50.0,
            ),
        ],
    )


def provider_output(
    request: GenerationRequest,
    artifact: ArtifactT,
) -> ProviderArtifact[ArtifactT]:
    return ProviderArtifact(
        request_semantic_id=request.semantic_id,
        artifact=artifact,
        provider=request.provider,
        model=request.model,
        model_revision=request.model_revision,
        prompt_sha256=request.prompt_sha256,
        configuration_sha256=request.configuration_sha256,
        seed=request.seed,
        generated_at_inference=True,
        retrieved_pre_authored_clip=False,
        deterministic_algorithms=True,
    )


def wav_bytes(
    *,
    frame_count: int = 4000,
    sample_rate: int = 48000,
    channels: int = 1,
    sample_width: int = 2,
) -> bytes:
    output = BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(channels)
        audio.setsampwidth(sample_width)
        audio.setframerate(sample_rate)
        audio.writeframes(b"\x00" * frame_count * channels * sample_width)
    return output.getvalue()


def make_performance_fixture() -> PerformanceFixture:
    plan = _plan()
    body_request = plan.body_requests[0]
    facial_request = plan.facial_requests[0]
    camera_request = plan.camera_requests[0]
    return PerformanceFixture(
        plan=plan,
        body_outputs=(provider_output(body_request, _body_artifact()),),
        facial_outputs=(provider_output(facial_request, _facial_artifact()),),
        camera_outputs=(provider_output(camera_request, _camera_artifact()),),
        audio_outputs=(
            DialogueAudioArtifact(
                dialogue_cue_id="dialogue:fixture:mina",
                actor_binding_id="actor:mina",
                start_frame=1,
                end_frame=3,
                data=wav_bytes(),
            ),
        ),
    )


@pytest.fixture
def performance_fixture() -> PerformanceFixture:
    return make_performance_fixture()
