from __future__ import annotations

from typing import Literal, Self

from cutsceneai_performance import (
    ARKIT_52_BLENDSHAPE_NAMES,
    ARKIT_52_CURVES,
    CANONICAL_HUMANOID_JOINTS,
    CANONICAL_HUMANOID_PARENTS,
    ArtifactReference,
    ModelProvenance,
)
from pydantic import Field, model_validator

from .models import UnityModel, UnityQuaternion, UnityVector


UNITY_HUMANOID_BONES = (
    "Hips",
    "LeftUpperLeg",
    "RightUpperLeg",
    "Spine",
    "LeftLowerLeg",
    "RightLowerLeg",
    "Chest",
    "LeftFoot",
    "RightFoot",
    "UpperChest",
    "LeftToes",
    "RightToes",
    "Neck",
    "LeftShoulder",
    "RightShoulder",
    "Head",
    "LeftUpperArm",
    "RightUpperArm",
    "LeftLowerArm",
    "RightLowerArm",
    "LeftHand",
    "RightHand",
)


class UnityJointBinding(UnityModel):
    source_joint_name: str
    target_human_bone: str = Field(pattern=r"^[A-Z][A-Za-z0-9]*$")
    parent_index: int = Field(ge=-1)


class UnityBodyKeyframe(UnityModel):
    timeline_frame: int = Field(ge=0)
    root_position_m: UnityVector
    joint_rotations: list[UnityQuaternion]


class UnityGeneratedTrack(UnityModel):
    semantic_id: str
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)
    source_artifact: ArtifactReference
    provenance: ModelProvenance

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if self.end_frame <= self.start_frame:
            raise ValueError("end_frame must be greater than start_frame")
        return self


class UnityGeneratedBodyTrack(UnityGeneratedTrack):
    actor_binding_id: str
    source_performance_cue_id: str
    source_skeleton_profile: Literal["cutsceneai-humanoid-v1"]
    target_rig_profile: Literal["unity-humanoid-v1"] = "unity-humanoid-v1"
    rotation_space: Literal["converted-canonical-parent-local"] = (
        "converted-canonical-parent-local"
    )
    target_animation_path: str = Field(pattern=r"^Assets/.+\.anim$")
    joint_bindings: list[UnityJointBinding]
    keyframes: list[UnityBodyKeyframe] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_body_mapping(self) -> Self:
        source_names = tuple(item.source_joint_name for item in self.joint_bindings)
        target_names = tuple(item.target_human_bone for item in self.joint_bindings)
        parent_indices = tuple(item.parent_index for item in self.joint_bindings)
        if (
            source_names != CANONICAL_HUMANOID_JOINTS
            or target_names != UNITY_HUMANOID_BONES
            or parent_indices != CANONICAL_HUMANOID_PARENTS
        ):
            raise ValueError(
                "joint_bindings must exactly map cutsceneai-humanoid-v1 to "
                "unity-humanoid-v1"
            )
        expected_frames = list(range(self.start_frame, self.end_frame))
        if [item.timeline_frame for item in self.keyframes] != expected_frames:
            raise ValueError("body keyframes must cover the exact track frame window")
        if any(
            len(item.joint_rotations) != len(self.joint_bindings)
            for item in self.keyframes
        ):
            raise ValueError(
                "body keyframes must contain one rotation per joint binding"
            )
        return self


class UnityFacialCurveBinding(UnityModel):
    source_curve_name: str
    target_blendshape_name: str = Field(pattern=r"^[a-z][A-Za-z0-9]*$")


class UnityFacialKeyframe(UnityModel):
    timeline_frame: int = Field(ge=0)
    weights: list[float]


class UnityGeneratedFacialTrack(UnityGeneratedTrack):
    actor_binding_id: str
    source_performance_cue_id: str
    source_dialogue_cue_id: str | None = None
    source_curve_profile: Literal["arkit-52"]
    target_curve_profile: Literal["arkit-52-blendshapes"] = "arkit-52-blendshapes"
    target_animation_path: str = Field(pattern=r"^Assets/.+\.anim$")
    curve_bindings: list[UnityFacialCurveBinding]
    keyframes: list[UnityFacialKeyframe] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_facial_mapping(self) -> Self:
        bindings = tuple(
            (item.source_curve_name, item.target_blendshape_name)
            for item in self.curve_bindings
        )
        if bindings != tuple(
            zip(ARKIT_52_CURVES, ARKIT_52_BLENDSHAPE_NAMES, strict=True)
        ):
            raise ValueError("curve_bindings must exactly map the ARKit-52 profile")
        expected_frames = list(range(self.start_frame, self.end_frame))
        if [item.timeline_frame for item in self.keyframes] != expected_frames:
            raise ValueError("facial keyframes must cover the exact track frame window")
        if any(
            len(item.weights) != len(self.curve_bindings) for item in self.keyframes
        ):
            raise ValueError(
                "facial keyframes must contain one weight per curve binding"
            )
        return self


class UnityCameraKeyframe(UnityModel):
    timeline_frame: int = Field(ge=0)
    position_m: UnityVector
    rotation: UnityQuaternion
    focal_length_mm: float = Field(ge=8, le=300)


class UnityGeneratedCameraTrack(UnityGeneratedTrack):
    camera_binding_id: str
    source_camera_cut_id: str
    sensor_width_mm: float = Field(gt=0, le=100)
    sensor_height_mm: float = Field(gt=0, le=100)
    keyframes: list[UnityCameraKeyframe] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_camera_mapping(self) -> Self:
        expected_frames = list(range(self.start_frame, self.end_frame))
        if [item.timeline_frame for item in self.keyframes] != expected_frames:
            raise ValueError("camera keyframes must cover the exact track frame window")
        return self


class UnityGeneratedAudioTrack(UnityModel):
    dialogue_cue_id: str
    actor_binding_id: str
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)
    source_artifact: ArtifactReference
    target_audio_path: str = Field(pattern=r"^Assets/.+\.wav$")

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if self.end_frame <= self.start_frame:
            raise ValueError("end_frame must be greater than start_frame")
        return self


class UnityPerformanceMapping(UnityModel):
    mapping_version: Literal["0.1.0"] = "0.1.0"
    target_engine: Literal["Unity"] = "Unity"
    target_engine_version: Literal["6000.0"] = "6000.0"
    timeline_package_version: Literal["1.8.12"] = "1.8.12"
    source_package_version: Literal["0.1.0"] = "0.1.0"
    source_bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    project_id: str
    cir_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_scene_id: str
    fps: int = Field(ge=1, le=240)
    duration_frames: int = Field(gt=0)
    body_tracks: list[UnityGeneratedBodyTrack] = Field(min_length=1)
    facial_tracks: list[UnityGeneratedFacialTrack] = Field(min_length=1)
    camera_tracks: list[UnityGeneratedCameraTrack] = Field(min_length=1)
    audio_tracks: list[UnityGeneratedAudioTrack] = Field(default_factory=list)
