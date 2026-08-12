from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[
    str,
    Field(min_length=1, pattern=r"^[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*$"),
]
NonEmptyString = Annotated[str, Field(min_length=1)]
SemanticId = Annotated[
    str,
    Field(
        min_length=1,
        pattern=r"^[a-z][a-z0-9_-]*(?::[a-z0-9][a-z0-9_-]*)+$",
    ),
]
Sha256Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
RelativeArtifactPath = Annotated[
    str,
    Field(
        min_length=1,
        pattern=r"^(?:body|face|camera|audio)/[a-z0-9][a-z0-9._-]*$",
    ),
]


class PerformanceModel(BaseModel):
    model_config = ConfigDict(
        allow_inf_nan=False,
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class ArtifactKind(str, Enum):
    BODY_MOTION = "body_motion"
    FACIAL_CURVES = "facial_curves"
    CAMERA_CURVES = "camera_curves"
    DIALOGUE_AUDIO = "dialogue_audio"


class ArtifactFormat(str, Enum):
    CUTSCENEAI_MOTION_JSON = "cutsceneai.motion+json"
    CUTSCENEAI_FACE_JSON = "cutsceneai.face+json"
    CUTSCENEAI_CAMERA_JSON = "cutsceneai.camera+json"
    WAV_PCM = "audio/wav"


class ArtifactReference(PerformanceModel):
    kind: ArtifactKind
    format: ArtifactFormat
    relative_path: RelativeArtifactPath
    sha256: Sha256Digest
    byte_length: int = Field(gt=0)


class ModelProvenance(PerformanceModel):
    provider: NonEmptyString
    model: NonEmptyString
    model_revision: NonEmptyString
    prompt_sha256: Sha256Digest
    configuration_sha256: Sha256Digest
    seed: int = Field(ge=0, le=2**32 - 1)
    generated_at_inference: Literal[True] = True
    retrieved_pre_authored_clip: Literal[False] = False
    deterministic_algorithms: bool


class CoordinateSpace(PerformanceModel):
    distance_unit: Literal["meter"] = "meter"
    handedness: Literal["right"] = "right"
    up_axis: Literal["y"] = "y"
    forward_axis: Literal["-z"] = "-z"
    rotation_representation: Literal["quaternion_xyzw"] = "quaternion_xyzw"


class GenerationModelConfig(PerformanceModel):
    provider: NonEmptyString
    model: NonEmptyString
    model_revision: NonEmptyString
    prompt_version: NonEmptyString
    deterministic_algorithms: bool = True


class PerformanceCompilerConfig(PerformanceModel):
    request_version: Literal["0.1.0"] = "0.1.0"
    experiment_seed: int = 20260812
    body: GenerationModelConfig
    facial: GenerationModelConfig
    camera: GenerationModelConfig
    skeleton_profile: Identifier = "cutsceneai-humanoid-v1"
    facial_curve_profile: Identifier = "arkit-52"


class GenerationRequest(PerformanceModel):
    semantic_id: SemanticId
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)
    prompt: NonEmptyString
    prompt_sha256: Sha256Digest
    configuration_sha256: Sha256Digest
    seed: int = Field(ge=0, le=2**32 - 1)
    provider: NonEmptyString
    model: NonEmptyString
    model_revision: NonEmptyString
    prompt_version: NonEmptyString

    @model_validator(mode="after")
    def validate_request_window(self) -> Self:
        if self.end_frame <= self.start_frame:
            raise ValueError("end_frame must be greater than start_frame.")
        return self


class BodyGenerationRequest(GenerationRequest):
    actor_binding_id: SemanticId
    source_performance_cue_id: SemanticId
    skeleton_profile: Identifier
    look_at_binding_id: SemanticId | None = None


class FacialGenerationRequest(GenerationRequest):
    actor_binding_id: SemanticId
    source_performance_cue_id: SemanticId
    source_dialogue_cue_id: SemanticId | None = None
    curve_profile: Identifier
    emotion: str
    emotion_intensity: float = Field(ge=0, le=1)
    lip_sync: bool
    dialogue_text: str | None = None
    dialogue_start_frame: int | None = Field(default=None, ge=0)


class CameraGenerationRequest(GenerationRequest):
    camera_binding_id: SemanticId
    source_camera_cut_id: SemanticId
    subject_binding_ids: list[SemanticId]
    target_binding_ids: list[SemanticId]
    lens_mm: float = Field(ge=8, le=300)


class PerformanceGenerationPlan(PerformanceModel):
    request_version: Literal["0.1.0"] = "0.1.0"
    cir_schema_version: Literal["0.1.0"] = "0.1.0"
    project_id: Identifier
    cir_fingerprint_sha256: Sha256Digest
    fps: int = Field(ge=1, le=240)
    duration_frames: int = Field(gt=0)
    experiment_seed: int
    body_requests: list[BodyGenerationRequest] = Field(min_length=1)
    facial_requests: list[FacialGenerationRequest] = Field(min_length=1)
    camera_requests: list[CameraGenerationRequest] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_plan_invariants(self) -> Self:
        requests: list[GenerationRequest] = [
            *self.body_requests,
            *self.facial_requests,
            *self.camera_requests,
        ]
        if any(request.end_frame > self.duration_frames for request in requests):
            raise ValueError("Generation request exceeds plan duration_frames.")
        semantic_ids = [request.semantic_id for request in requests]
        if len(semantic_ids) != len(set(semantic_ids)):
            raise ValueError("Generation request semantic IDs must be unique.")
        return self


class TimedGeneratedTrack(PerformanceModel):
    semantic_id: SemanticId
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)
    artifact: ArtifactReference
    provenance: ModelProvenance

    @model_validator(mode="after")
    def validate_frame_window(self) -> Self:
        if self.end_frame <= self.start_frame:
            raise ValueError("end_frame must be greater than start_frame.")
        return self


class BodyMotionTrack(TimedGeneratedTrack):
    actor_binding_id: SemanticId
    source_performance_cue_id: SemanticId
    skeleton_profile: Identifier
    joint_count: int = Field(gt=0)
    sample_count: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_artifact_kind(self) -> Self:
        if self.artifact.kind is not ArtifactKind.BODY_MOTION:
            raise ValueError("Body motion tracks require a body_motion artifact.")
        if self.artifact.format is not ArtifactFormat.CUTSCENEAI_MOTION_JSON:
            raise ValueError("Body motion tracks require cutsceneai.motion+json.")
        return self


class FacialAnimationTrack(TimedGeneratedTrack):
    actor_binding_id: SemanticId
    source_performance_cue_id: SemanticId
    source_dialogue_cue_id: SemanticId | None = None
    curve_profile: Identifier
    curve_count: int = Field(gt=0)
    sample_count: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_artifact_kind(self) -> Self:
        if self.artifact.kind is not ArtifactKind.FACIAL_CURVES:
            raise ValueError("Facial tracks require a facial_curves artifact.")
        if self.artifact.format is not ArtifactFormat.CUTSCENEAI_FACE_JSON:
            raise ValueError("Facial tracks require cutsceneai.face+json.")
        return self


class CameraAnimationTrack(TimedGeneratedTrack):
    camera_binding_id: SemanticId
    source_camera_cut_id: SemanticId
    sample_count: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_artifact_kind(self) -> Self:
        if self.artifact.kind is not ArtifactKind.CAMERA_CURVES:
            raise ValueError("Camera tracks require a camera_curves artifact.")
        if self.artifact.format is not ArtifactFormat.CUTSCENEAI_CAMERA_JSON:
            raise ValueError("Camera tracks require cutsceneai.camera+json.")
        return self


class DialogueAudioTrack(PerformanceModel):
    dialogue_cue_id: SemanticId
    actor_binding_id: SemanticId
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)
    artifact: ArtifactReference

    @model_validator(mode="after")
    def validate_track(self) -> Self:
        if self.end_frame <= self.start_frame:
            raise ValueError("end_frame must be greater than start_frame.")
        if self.artifact.kind is not ArtifactKind.DIALOGUE_AUDIO:
            raise ValueError("Dialogue tracks require a dialogue_audio artifact.")
        if self.artifact.format is not ArtifactFormat.WAV_PCM:
            raise ValueError("Dialogue tracks require audio/wav.")
        return self


class GeneratedPerformancePackage(PerformanceModel):
    package_version: Literal["0.1.0"] = "0.1.0"
    cir_schema_version: Literal["0.1.0"] = "0.1.0"
    project_id: Identifier
    cir_fingerprint_sha256: Sha256Digest
    fps: int = Field(ge=1, le=240)
    duration_frames: int = Field(gt=0)
    coordinate_space: CoordinateSpace = Field(default_factory=CoordinateSpace)
    body_tracks: list[BodyMotionTrack] = Field(min_length=1)
    facial_tracks: list[FacialAnimationTrack] = Field(default_factory=list)
    camera_tracks: list[CameraAnimationTrack] = Field(min_length=1)
    audio_tracks: list[DialogueAudioTrack] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_package_invariants(self) -> Self:
        tracks: list[TimedGeneratedTrack | DialogueAudioTrack] = [
            *self.body_tracks,
            *self.facial_tracks,
            *self.camera_tracks,
            *self.audio_tracks,
        ]
        outside_timeline = [
            track for track in tracks if track.end_frame > self.duration_frames
        ]
        if outside_timeline:
            raise ValueError("Track end_frame exceeds package duration_frames.")

        semantic_ids = [
            *(track.semantic_id for track in self.body_tracks),
            *(track.semantic_id for track in self.facial_tracks),
            *(track.semantic_id for track in self.camera_tracks),
            *(track.dialogue_cue_id for track in self.audio_tracks),
        ]
        if len(semantic_ids) != len(set(semantic_ids)):
            raise ValueError("Track semantic IDs must be unique within the package.")

        paths = [track.artifact.relative_path for track in tracks]
        if len(paths) != len(set(paths)):
            raise ValueError(
                "Artifact relative paths must be unique within the package."
            )
        return self
