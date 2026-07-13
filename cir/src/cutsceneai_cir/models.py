from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


Identifier = Annotated[
    str,
    Field(
        min_length=1,
        pattern=r"^[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*$",
        description="Stable lowercase identifier used by CIR references.",
    ),
]
NonEmptyString = Annotated[str, Field(min_length=1)]
NonNegativeSeconds = Annotated[float, Field(ge=0)]
PositiveSeconds = Annotated[float, Field(gt=0)]
NormalizedValue = Annotated[float, Field(ge=0, le=1)]


class CIRModel(BaseModel):
    """Base configuration shared by every CIR model."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class Axis(str, Enum):
    POSITIVE_X = "x"
    POSITIVE_Y = "y"
    POSITIVE_Z = "z"
    NEGATIVE_X = "-x"
    NEGATIVE_Y = "-y"
    NEGATIVE_Z = "-z"


class Handedness(str, Enum):
    LEFT = "left"
    RIGHT = "right"


class ShotPurpose(str, Enum):
    ESTABLISHING = "establishing"
    ENVIRONMENT_DETAIL = "environment_detail"
    DIALOGUE = "dialogue"
    REACTION = "reaction"
    ACTION = "action"
    TRANSITION = "transition"


class CameraFraming(str, Enum):
    EXTREME_WIDE = "extreme_wide"
    WIDE = "wide"
    MEDIUM_WIDE = "medium_wide"
    MEDIUM = "medium"
    MEDIUM_CLOSE_UP = "medium_close_up"
    CLOSE_UP = "close_up"
    EXTREME_CLOSE_UP = "extreme_close_up"
    OVER_THE_SHOULDER = "over_the_shoulder"
    POINT_OF_VIEW = "point_of_view"
    INSERT = "insert"


class CameraAngle(str, Enum):
    EYE_LEVEL = "eye_level"
    LOW = "low"
    HIGH = "high"
    DUTCH = "dutch"
    OVERHEAD = "overhead"


class CameraMovement(str, Enum):
    STATIC = "static"
    PAN = "pan"
    TILT = "tilt"
    DOLLY = "dolly"
    TRUCK = "truck"
    CRANE = "crane"
    HANDHELD = "handheld"
    ORBIT = "orbit"


class Vector3(CIRModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


class Quaternion(CIRModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    w: float = 1.0


def _unit_scale() -> Vector3:
    return Vector3(x=1.0, y=1.0, z=1.0)


class Transform(CIRModel):
    position: Vector3 = Field(default_factory=Vector3)
    rotation: Quaternion = Field(default_factory=Quaternion)
    scale: Vector3 = Field(default_factory=_unit_scale)


class ProjectSettings(CIRModel):
    fps: int = Field(default=24, ge=1, le=240)
    distance_unit: Literal["meter"] = "meter"
    time_unit: Literal["second"] = "second"
    handedness: Handedness = Handedness.RIGHT
    up_axis: Axis = Axis.POSITIVE_Y
    forward_axis: Axis = Axis.NEGATIVE_Z


class GenerationMetadata(CIRModel):
    generator: NonEmptyString = "manual"
    model: str | None = None
    prompt_version: str | None = None
    seed: int | None = None


class Character(CIRModel):
    id: Identifier
    name: NonEmptyString
    role: str | None = None
    description: str | None = None
    rig_profile: str | None = None
    initial_transform: Transform = Field(default_factory=Transform)


class EnvironmentObject(CIRModel):
    id: Identifier
    name: NonEmptyString
    description: str | None = None
    asset_uri: str | None = None
    importance: NormalizedValue = 0.5
    initial_transform: Transform = Field(default_factory=Transform)


class DialoguePlan(CIRModel):
    text: NonEmptyString
    audio_uri: str | None = None
    language: NonEmptyString = "en"
    start_offset_seconds: NonNegativeSeconds = 0.0


class MotionPlan(CIRModel):
    prompt: NonEmptyString
    style: str | None = None
    asset_uri: str | None = None
    seed: int | None = None


class FacialPlan(CIRModel):
    emotion: NonEmptyString = "neutral"
    intensity: NormalizedValue = 0.5
    lip_sync: bool = True
    asset_uri: str | None = None


class PerformancePlan(CIRModel):
    character_id: Identifier
    motion: MotionPlan
    facial: FacialPlan = Field(default_factory=FacialPlan)
    dialogue: DialoguePlan | None = None
    look_at_id: Identifier | None = None


class SceneBeat(CIRModel):
    id: Identifier
    start_seconds: NonNegativeSeconds
    duration_seconds: PositiveSeconds
    description: NonEmptyString
    narrative_intent: str | None = None
    performances: list[PerformancePlan] = Field(default_factory=list)
    environment_focus_ids: list[Identifier] = Field(default_factory=list)


class CameraPlan(CIRModel):
    framing: CameraFraming
    angle: CameraAngle = CameraAngle.EYE_LEVEL
    movement: CameraMovement = CameraMovement.STATIC
    lens_mm: float = Field(default=50.0, ge=8.0, le=300.0)
    target_ids: list[Identifier] = Field(default_factory=list)
    composition: str | None = None
    transform: Transform | None = None


class Shot(CIRModel):
    id: Identifier
    beat_ids: list[Identifier] = Field(min_length=1)
    start_seconds: NonNegativeSeconds
    duration_seconds: PositiveSeconds
    purpose: ShotPurpose
    description: NonEmptyString
    subject_ids: list[Identifier] = Field(default_factory=list)
    camera: CameraPlan


class Scene(CIRModel):
    id: Identifier
    title: NonEmptyString
    location: NonEmptyString
    duration_seconds: PositiveSeconds
    beats: list[SceneBeat] = Field(min_length=1)
    shots: list[Shot] = Field(min_length=1)


class Project(CIRModel):
    schema_version: Literal["0.1.0"] = "0.1.0"
    id: Identifier
    name: NonEmptyString
    description: str | None = None
    settings: ProjectSettings = Field(default_factory=ProjectSettings)
    generation: GenerationMetadata = Field(default_factory=GenerationMetadata)
    characters: list[Character] = Field(default_factory=list)
    environment: list[EnvironmentObject] = Field(default_factory=list)
    scenes: list[Scene] = Field(min_length=1)
