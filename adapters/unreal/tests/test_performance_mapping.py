from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest
from cutsceneai_cir import (
    CameraAngle,
    CameraFraming,
    CameraMovement,
    ProjectSettings,
    ShotPurpose,
)
from cutsceneai_performance import render_performance_bundle
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from cutsceneai_unreal import (
    UNREAL_PERFORMANCE_MAPPING_SCHEMA_ID,
    UNREAL_UE5_MANNEQUIN_BONES,
    UnrealActorBinding,
    UnrealActorKind,
    UnrealCameraBinding,
    UnrealExportPlan,
    UnrealMeshType,
    UnrealPerformanceMapping,
    UnrealSceneSequence,
    UnrealTransform,
    UnrealVector,
    compile_performance_bundle,
    render_unreal_performance_mapping,
    unreal_performance_mapping_json_schema,
)
from cutsceneai_test_support.generated_performance import (
    GeneratedPerformanceFixture,
    make_generated_performance_fixture,
)


def _export_plan(fixture: GeneratedPerformanceFixture) -> UnrealExportPlan:
    scene = fixture.semantics.scenes[0]
    cut = scene.camera_cuts[0]
    return UnrealExportPlan(
        project_id=fixture.bundle.package.project_id,
        project_name="Fixture Project",
        source_settings=ProjectSettings(fps=fixture.bundle.package.fps),
        sequences=[
            UnrealSceneSequence(
                source_scene_id=scene.source_scene_id,
                title="Fixture Scene",
                location="Test Stage",
                asset_name="LS_FixtureScene",
                package_path="/Game/CutSceneAI/Sequences",
                duration_frames=scene.duration_frames,
                set_pieces=[],
                actors=[
                    UnrealActorBinding(
                        binding_id="actor:mina",
                        source_entity_id="mina",
                        display_name="Mina",
                        kind=UnrealActorKind.CHARACTER,
                        mesh_type=UnrealMeshType.SKELETAL_MESH,
                        actor_class_path="/Script/Engine.SkeletalMeshActor",
                        placeholder=False,
                        transform=UnrealTransform(),
                    )
                ],
                performance_cues=[],
                animation_sections=[],
                audio_sections=[],
                cameras=[
                    UnrealCameraBinding(
                        binding_id="camera:fixture-shot",
                        source_shot_id=cut.source_shot_id,
                        source_beat_ids=cut.source_beat_ids,
                        display_name="Fixture Camera",
                        start_frame=cut.start_frame,
                        end_frame=cut.end_frame,
                        purpose=ShotPurpose.DIALOGUE,
                        description="Deterministic fixture camera",
                        framing=CameraFraming.MEDIUM,
                        angle=CameraAngle.EYE_LEVEL,
                        movement=CameraMovement.STATIC,
                        lens_mm=cut.lens_mm,
                        subject_binding_ids=cut.subject_binding_ids,
                        target_binding_ids=cut.target_binding_ids,
                        transform=UnrealTransform(),
                        look_at_location_cm=UnrealVector(),
                        inferred_transform=False,
                    )
                ],
            )
        ],
        warnings=[],
    )


@pytest.fixture
def generated_fixture() -> GeneratedPerformanceFixture:
    return make_generated_performance_fixture()


@pytest.fixture
def mapping(generated_fixture: GeneratedPerformanceFixture) -> UnrealPerformanceMapping:
    return compile_performance_bundle(
        generated_fixture.bundle,
        export_plan=_export_plan(generated_fixture),
        semantics=generated_fixture.semantics,
    )


def test_compile_maps_exact_bundle_into_unreal_native_contract(
    generated_fixture: GeneratedPerformanceFixture,
    mapping: UnrealPerformanceMapping,
) -> None:
    package = generated_fixture.bundle.package

    assert mapping.target_engine_version == "5.8.0"
    assert (
        mapping.source_bundle_sha256
        == hashlib.sha256(
            render_performance_bundle(generated_fixture.bundle)
        ).hexdigest()
    )
    assert mapping.cir_fingerprint_sha256 == package.cir_fingerprint_sha256
    body = mapping.body_tracks[0]
    assert body.source_artifact == package.body_tracks[0].artifact
    assert body.provenance == package.body_tracks[0].provenance
    assert tuple(item.target_bone_name for item in body.joint_bindings) == (
        UNREAL_UE5_MANNEQUIN_BONES
    )
    assert [item.timeline_frame for item in body.keyframes] == [0, 1, 2, 3]
    assert body.keyframes[-1].root_location_cm == UnrealVector(x=0.0, y=100.0, z=0.0)
    face = mapping.facial_tracks[0]
    assert face.curve_bindings[0].target_curve_name == "browDownLeft"
    assert face.curve_bindings[-1].target_curve_name == "tongueOut"
    camera = mapping.camera_tracks[0]
    assert camera.keyframes[0].location_cm == UnrealVector(x=-200.0, y=0.0, z=100.0)
    assert camera.keyframes[-1].location_cm == UnrealVector(x=-300.0, y=100.0, z=200.0)
    assert mapping.audio_tracks[0].target_sound_path.endswith(
        "/Audio/SW_DialogueFixtureMina"
    )


def test_mapping_serialization_and_schema_are_deterministic(
    mapping: UnrealPerformanceMapping,
) -> None:
    rendered = render_unreal_performance_mapping(mapping)
    schema = unreal_performance_mapping_json_schema()

    assert rendered == render_unreal_performance_mapping(mapping)
    assert json.loads(rendered) == mapping.model_dump(mode="json")
    assert schema["$id"] == UNREAL_PERFORMANCE_MAPPING_SCHEMA_ID
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(json.loads(rendered))


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("project", "identity or frame rate"),
        ("fps", "identity or frame rate"),
        ("sequences", "identity or frame rate"),
        ("scene", "scene does not match"),
        ("duration", "scene does not match"),
        ("actor", "actor bindings"),
        ("camera", "camera bindings"),
    ],
)
def test_compile_rejects_export_plan_drift(
    generated_fixture: GeneratedPerformanceFixture,
    mutation: str,
    message: str,
) -> None:
    plan = _export_plan(generated_fixture).model_copy(deep=True)
    if mutation == "project":
        plan.project_id = "other-project"
    elif mutation == "fps":
        plan.source_settings.fps = 25
    elif mutation == "sequences":
        plan.sequences.clear()
    elif mutation == "scene":
        plan.sequences[0].source_scene_id = "other-scene"
    elif mutation == "duration":
        plan.sequences[0].duration_frames = 5
    elif mutation == "actor":
        plan.sequences[0].actors[0].source_entity_id = "other-actor"
    elif mutation == "camera":
        plan.sequences[0].cameras[0].start_frame = 1

    with pytest.raises(ValueError, match=message):
        compile_performance_bundle(
            generated_fixture.bundle,
            export_plan=plan,
            semantics=generated_fixture.semantics,
        )


@pytest.mark.parametrize("target_path", ["Game/Generated", "/Game", "/Game/Bad-Path"])
def test_compile_rejects_non_normalized_unreal_target_paths(
    generated_fixture: GeneratedPerformanceFixture,
    target_path: str,
) -> None:
    with pytest.raises(ValueError, match="normalized Unreal"):
        compile_performance_bundle(
            generated_fixture.bundle,
            export_plan=_export_plan(generated_fixture),
            semantics=generated_fixture.semantics,
            target_path=target_path,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("track_range", "end_frame must be greater"),
        ("body_bindings", "joint_bindings must exactly map"),
        ("body_frames", "body keyframes must cover"),
        ("body_rotations", "one rotation per joint"),
        ("face_bindings", "curve_bindings must exactly map"),
        ("face_frames", "facial keyframes must cover"),
        ("face_weights", "one weight per curve"),
        ("camera_frames", "camera keyframes must cover"),
        ("audio_range", "end_frame must be greater"),
    ],
)
def test_mapping_models_reject_realization_drift(
    mapping: UnrealPerformanceMapping,
    mutation: str,
    message: str,
) -> None:
    payload: dict[str, Any] = mapping.model_dump(mode="json")
    if mutation == "track_range":
        payload["body_tracks"][0]["start_frame"] = 2
        payload["body_tracks"][0]["end_frame"] = 1
    elif mutation == "body_bindings":
        payload["body_tracks"][0]["joint_bindings"][0]["target_bone_name"] = "root"
    elif mutation == "body_frames":
        payload["body_tracks"][0]["keyframes"][0]["timeline_frame"] = 1
    elif mutation == "body_rotations":
        payload["body_tracks"][0]["keyframes"][0]["joint_rotations"].pop()
    elif mutation == "face_bindings":
        payload["facial_tracks"][0]["curve_bindings"][0]["target_curve_name"] = (
            "browDownRight"
        )
    elif mutation == "face_frames":
        payload["facial_tracks"][0]["keyframes"][0]["timeline_frame"] = 1
    elif mutation == "face_weights":
        payload["facial_tracks"][0]["keyframes"][0]["weights"].pop()
    elif mutation == "camera_frames":
        payload["camera_tracks"][0]["keyframes"][0]["timeline_frame"] = 1
    elif mutation == "audio_range":
        payload["audio_tracks"][0]["start_frame"] = 3
        payload["audio_tracks"][0]["end_frame"] = 2

    with pytest.raises(ValidationError, match=message):
        UnrealPerformanceMapping.model_validate(payload)
