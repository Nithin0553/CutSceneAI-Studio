from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import TypeVar
import wave

from cutsceneai_cir import CameraAngle, CameraFraming, CameraMovement, ShotPurpose
from cutsceneai_parity import (
    EntityKind,
    SemanticCameraCut,
    SemanticDialogueCue,
    SemanticEntity,
    SemanticPerformanceCue,
    SemanticScene,
    TimelineSemantics,
)
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
    PerformanceBundle,
    PerformanceGenerationPlan,
    ProviderArtifact,
    Quaternion,
    Vector3,
    assemble_performance_bundle,
)
from cutsceneai_performance.models import GenerationRequest


SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
ArtifactT = TypeVar("ArtifactT")


@dataclass(frozen=True, slots=True)
class GeneratedPerformanceFixture:
    bundle: PerformanceBundle
    semantics: TimelineSemantics


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


def _provider_output(
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


def _wav_bytes() -> bytes:
    output = BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(48_000)
        audio.writeframes(b"\x00" * 8_000)
    return output.getvalue()


def _semantics() -> TimelineSemantics:
    return TimelineSemantics(
        cir_fingerprint_sha256=SHA_C,
        project_id="fixture-project",
        fps=24,
        scenes=[
            SemanticScene(
                source_scene_id="fixture-scene",
                duration_frames=4,
                entities=[
                    SemanticEntity(
                        binding_id="actor:mina",
                        source_entity_id="mina",
                        kind=EntityKind.CHARACTER,
                    )
                ],
                performance_cues=[
                    SemanticPerformanceCue(
                        cue_id="performance:fixture:mina",
                        source_beat_id="fixture-beat",
                        actor_binding_id="actor:mina",
                        start_frame=0,
                        end_frame=4,
                        motion_intent_sha256=SHA_A,
                    )
                ],
                dialogue_cues=[
                    SemanticDialogueCue(
                        cue_id="dialogue:fixture:mina",
                        source_beat_id="fixture-beat",
                        actor_binding_id="actor:mina",
                        start_frame=1,
                        window_end_frame=4,
                        text_sha256=SHA_B,
                        language="en-US",
                    )
                ],
                camera_cuts=[
                    SemanticCameraCut(
                        cut_id="camera:fixture:shot",
                        source_shot_id="fixture-shot",
                        source_beat_ids=["fixture-beat"],
                        start_frame=0,
                        end_frame=4,
                        purpose=ShotPurpose.DIALOGUE,
                        framing=CameraFraming.MEDIUM,
                        angle=CameraAngle.EYE_LEVEL,
                        movement=CameraMovement.STATIC,
                        lens_mm=50.0,
                        subject_binding_ids=["actor:mina"],
                        target_binding_ids=["actor:mina"],
                    )
                ],
            )
        ],
    )


def make_generated_performance_fixture() -> GeneratedPerformanceFixture:
    plan = _plan()
    body = BodyMotionArtifact(
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
    face = FacialCurveArtifact(
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
    camera = CameraCurveArtifact(
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
    bundle = assemble_performance_bundle(
        plan,
        body_outputs=(_provider_output(plan.body_requests[0], body),),
        facial_outputs=(_provider_output(plan.facial_requests[0], face),),
        camera_outputs=(_provider_output(plan.camera_requests[0], camera),),
        audio_outputs=(
            DialogueAudioArtifact(
                dialogue_cue_id="dialogue:fixture:mina",
                actor_binding_id="actor:mina",
                start_frame=1,
                end_frame=3,
                data=_wav_bytes(),
            ),
        ),
    )
    return GeneratedPerformanceFixture(bundle=bundle, semantics=_semantics())
