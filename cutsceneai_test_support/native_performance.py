from __future__ import annotations

from cutsceneai_cir import (
    CameraAngle,
    CameraFraming,
    CameraMovement,
    ProjectSettings,
    ShotPurpose,
)
from cutsceneai_parity import EntityKind
from cutsceneai_unity import (
    UnityActorBinding,
    UnityCameraCut,
    UnityExportPlan,
    UnityPrimitive,
    UnitySceneTimeline,
    UnityTransform,
    UnityVector,
)
from cutsceneai_unreal import (
    UnrealActorBinding,
    UnrealActorKind,
    UnrealCameraBinding,
    UnrealExportPlan,
    UnrealMeshType,
    UnrealSceneSequence,
    UnrealTransform,
    UnrealVector,
)

from .generated_performance import GeneratedPerformanceFixture


UNITY_FIXTURE_PREFAB = "Assets/CutSceneAI/Characters/Mina.prefab"
UNREAL_FIXTURE_MESH = "/Game/CutSceneAI/Characters/SK_Mina.SK_Mina"


def make_unity_native_export_plan(
    fixture: GeneratedPerformanceFixture,
) -> UnityExportPlan:
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
                        prefab_path=UNITY_FIXTURE_PREFAB,
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


def make_unreal_native_export_plan(
    fixture: GeneratedPerformanceFixture,
) -> UnrealExportPlan:
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
                        asset_path=UNREAL_FIXTURE_MESH,
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
