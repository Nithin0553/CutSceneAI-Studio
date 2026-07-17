from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


Identifier = Annotated[
    str,
    Field(min_length=1, pattern=r"^[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*$"),
]
NonEmptyString = Annotated[str, Field(min_length=1)]
NonNegativeSeconds = Annotated[float, Field(ge=0)]
PositiveSeconds = Annotated[float, Field(gt=0)]
Sha256Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class DialogueModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DialogueSource(str, Enum):
    RECORDED = "recorded"
    TTS = "tts"


class DialogueWarning(DialogueModel):
    code: str
    cue_id: str
    message: str


class DialogueCue(DialogueModel):
    cue_id: Identifier
    scene_id: Identifier
    beat_id: Identifier
    character_id: Identifier
    performance_index: int = Field(ge=0)
    text: NonEmptyString
    language: NonEmptyString
    start_seconds: NonNegativeSeconds
    start_frame: int = Field(ge=0)
    beat_end_seconds: PositiveSeconds
    output_filename: str = Field(pattern=r"^[a-z][a-z0-9_-]*\.wav$")
    existing_audio_uri: str | None = None


class DialogueRenderPlan(DialogueModel):
    dialogue_version: Literal["0.1.0"] = "0.1.0"
    cir_schema_version: Literal["0.1.0"] = "0.1.0"
    project_id: Identifier
    fps: int = Field(ge=1, le=240)
    cues: list[DialogueCue]
    warnings: list[DialogueWarning]


class VoiceProfile(DialogueModel):
    voice: NonEmptyString
    instructions: str | None = Field(default=None, max_length=4096)
    speed: float = Field(default=1.0, ge=0.25, le=4.0)


class SpeechSynthesisRequest(DialogueModel):
    cue_id: Identifier
    text: NonEmptyString = Field(max_length=4096)
    language: NonEmptyString
    voice: NonEmptyString
    instructions: str | None = Field(default=None, max_length=4096)
    speed: float = Field(default=1.0, ge=0.25, le=4.0)
    response_format: Literal["wav"] = "wav"


class WavMetadata(DialogueModel):
    sha256: Sha256Digest
    byte_length: int = Field(gt=0)
    frame_count: int = Field(gt=0)
    sample_rate_hz: int = Field(gt=0)
    channels: int = Field(ge=1, le=2)
    sample_width_bytes: int = Field(ge=1, le=4)
    duration_seconds: PositiveSeconds
    format: Literal["wav"] = "wav"
    mime_type: Literal["audio/wav"] = "audio/wav"


class AudioProvenance(DialogueModel):
    source: DialogueSource
    ai_generated: bool
    provider: str | None = None
    model: str | None = None
    voice: str | None = None
    instructions: str | None = None
    speed: float | None = Field(default=None, ge=0.25, le=4.0)
    request_id: str | None = None
    original_filename: str | None = None

    @model_validator(mode="after")
    def validate_source_fields(self) -> Self:
        if self.source is DialogueSource.TTS:
            missing = [
                name
                for name, value in (
                    ("provider", self.provider),
                    ("model", self.model),
                    ("voice", self.voice),
                )
                if not value
            ]
            if missing:
                raise ValueError(f"TTS provenance requires {', '.join(missing)}.")
            if not self.ai_generated:
                raise ValueError("TTS provenance must be marked as AI-generated.")
        elif self.ai_generated:
            raise ValueError("Recorded audio cannot be marked as AI-generated.")
        return self


class DialogueClip(DialogueModel):
    cue_id: Identifier
    scene_id: Identifier
    beat_id: Identifier
    character_id: Identifier
    text: NonEmptyString
    language: NonEmptyString
    uri: NonEmptyString
    relative_path: str = Field(pattern=r"^audio/[a-z][a-z0-9_-]*\.wav$")
    start_seconds: NonNegativeSeconds
    end_seconds: PositiveSeconds
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)
    beat_end_seconds: PositiveSeconds
    fits_within_beat: bool
    wav: WavMetadata
    provenance: AudioProvenance


class DialogueManifest(DialogueModel):
    manifest_version: Literal["0.1.0"] = "0.1.0"
    cir_schema_version: Literal["0.1.0"] = "0.1.0"
    project_id: Identifier
    fps: int = Field(ge=1, le=240)
    ai_voice_disclosure_required: bool
    clips: list[DialogueClip]
    warnings: list[DialogueWarning]
