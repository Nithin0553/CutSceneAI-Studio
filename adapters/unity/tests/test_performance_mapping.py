from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest
from cutsceneai_parity import EntityKind
from cutsceneai_performance import render_performance_bundle
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from cutsceneai_test_support.generated_performance import (
    GeneratedPerformanceFixture,
    make_generated_performance_fixture,
)
from cutsceneai_unity import (
    UNITY_HUMANOID_BONES,
    UNITY_PERFORMANCE_MAPPING_SCHEMA_ID,
    UnityActorBinding,
    UnityCameraCut,
    UnityExportPlan,
    UnityPerformanceMapping,
    UnityPrimitive,
    UnitySceneTimeline,
    UnityTransform,
    UnityVector,
    compile_performance_bundle,
    render_unity_performance_mapping,
    unity_performance_mapping_json_schema,
)


def _export_plan(fixture: GeneratedPerformanceFixture) -> UnityExportPlan:
    scene = fixture.semantics.scenes[0]
    cut = scene.camera_cuts[0]
    return UnityExportPlan(
        project_id=fixture.bundle.package.project_id,
        project_name="Fixture Project",
        fps=fixture.bundle.package.fps,
        semantics=fixture.semantics.model_copy(deep=True),
        sequences=[
            UnitySceneTimeline(
                source_scene_id=scene.source_scene_id,
                title="Fixture Scene",
                asset_name="FixtureScene",
                timeline_asset_path=(
                    "Assets/CutSceneAI/Timelines/FixtureScene.playable"
                ),
                scene_asset_path="Assets/CutSceneAI/Scenes/FixtureScene.unity",
                duration_frames=scene.duration_frames,
                actors=[
                    UnityActorBinding(
                        binding_id="actor:mina",
                        source_entity_id="mina",
                        display_name="Mina",
                        kind=EntityKind.CHARACTER,
                        prefab_path="Assets/CutSceneAI/Characters/Mina.prefab",
                        placeholder=False,
                        placeholder_primitive=UnityPrimitive.CAPSULE,
                        transform=UnityTransform(),
                    )
                ],
                animation_sections=[],
                audio_sections=[],
                cameras=[
                    UnityCameraCut(
                        cut_id=cut.cut_id,
                        source_shot_id=cut.source_shot_id,
                        display_name="Fixture Camera",
                        start_frame=cut.start_frame,
                        end_frame=cut.end_frame,
                        lens_mm=cut.lens_mm,
                        position_m=UnityVector(),
                        look_at_m=UnityVector(),
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
def mapping(generated_fixture: GeneratedPerformanceFixture) -> UnityPerformanceMapping:
    return compile_performance_bundle(
        generated_fixture.bundle,
        export_plan=_export_plan(generated_fixture),
    )


def test_compile_maps_exact_bundle_into_unity_native_contract(
    generated_fixture: GeneratedPerformanceFixture,
    mapping: UnityPerformanceMapping,
) -> None:
    package = generated_fixture.bundle.package

    assert mapping.target_engine_version == "6000.0"
    assert mapping.timeline_package_version == "1.8.12"
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
    assert body.root_translation_space == "target-reference-pose-offset"
    assert body.rotation_space == "target-reference-pose-relative-parent-local"
    assert tuple(item.target_human_bone for item in body.joint_bindings) == (
        UNITY_HUMANOID_BONES
    )
    assert [item.timeline_frame for item in body.keyframes] == [0, 1, 2, 3]
    assert body.keyframes[-1].root_position_m == UnityVector(x=1.0, y=0.0, z=0.0)
    face = mapping.facial_tracks[0]
    assert face.curve_bindings[0].target_blendshape_name == "browDownLeft"
    assert face.curve_bindings[-1].target_blendshape_name == "tongueOut"
    camera = mapping.camera_tracks[0]
    assert camera.target_animation_path.endswith(
        "/Camera/CA_CameraMotionFixtureShot.anim"
    )
    assert camera.keyframes[0].position_m == UnityVector(x=0.0, y=1.0, z=-2.0)
    assert camera.keyframes[-1].position_m == UnityVector(x=1.0, y=2.0, z=-3.0)
    assert mapping.audio_tracks[0].target_audio_path.endswith(
        "/Audio/DialogueFixtureMina.wav"
    )


def test_mapping_serialization_and_schema_are_deterministic(
    mapping: UnityPerformanceMapping,
) -> None:
    rendered = render_unity_performance_mapping(mapping)
    schema = unity_performance_mapping_json_schema()

    assert rendered == render_unity_performance_mapping(mapping)
    assert json.loads(rendered) == mapping.model_dump(mode="json")
    assert schema["$id"] == UNITY_PERFORMANCE_MAPPING_SCHEMA_ID
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
        ("camera", "camera cuts"),
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
        plan.fps = 25
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
        )


@pytest.mark.parametrize(
    "target_path",
    ["CutSceneAI/Generated", "Assets", "Assets/Bad Path", "Assets/../Escape"],
)
def test_compile_rejects_non_normalized_unity_target_paths(
    generated_fixture: GeneratedPerformanceFixture,
    target_path: str,
) -> None:
    with pytest.raises(ValueError, match="normalized Unity"):
        compile_performance_bundle(
            generated_fixture.bundle,
            export_plan=_export_plan(generated_fixture),
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
    mapping: UnityPerformanceMapping,
    mutation: str,
    message: str,
) -> None:
    payload: dict[str, Any] = mapping.model_dump(mode="json")
    if mutation == "track_range":
        payload["body_tracks"][0]["start_frame"] = 2
        payload["body_tracks"][0]["end_frame"] = 1
    elif mutation == "body_bindings":
        payload["body_tracks"][0]["joint_bindings"][0]["target_human_bone"] = "Root"
    elif mutation == "body_frames":
        payload["body_tracks"][0]["keyframes"][0]["timeline_frame"] = 1
    elif mutation == "body_rotations":
        payload["body_tracks"][0]["keyframes"][0]["joint_rotations"].pop()
    elif mutation == "face_bindings":
        payload["facial_tracks"][0]["curve_bindings"][0]["target_blendshape_name"] = (
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
        UnityPerformanceMapping.model_validate(payload)
