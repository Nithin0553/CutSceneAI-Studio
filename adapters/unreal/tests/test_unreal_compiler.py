from copy import deepcopy

import pytest

from cutsceneai_cir import CIRValidationError, Project, Quaternion, Transform, Vector3
from cutsceneai_unreal import UnrealVector, compile_project, render_unreal_plan


def test_compile_office_dialogue_creates_editable_sequence_contract(
    cir_project: Project,
) -> None:
    plan = compile_project(cir_project)
    sequence = plan.sequences[0]

    assert plan.target_engine_version == "5.6"
    assert sequence.asset_name == "LS_SceneMeeting"
    assert sequence.package_path == "/Game/CutSceneAI/Sequences"
    assert sequence.duration_frames == 432
    assert len(sequence.actors) == 4
    assert len(sequence.performance_cues) == 4
    assert len(sequence.cameras) == 4
    assert sequence.cameras[0].source_beat_ids == ["beat-arrival"]
    assert sequence.cameras[0].subject_binding_ids == [
        "actor:mina",
        "actor:arjun",
        "actor:conference-table",
    ]
    assert [(camera.start_frame, camera.end_frame) for camera in sequence.cameras] == [
        (0, 96),
        (96, 144),
        (144, 336),
        (336, 432),
    ]


def test_compile_converts_golden_actor_positions(cir_project: Project) -> None:
    actors = {
        actor.source_entity_id: actor
        for actor in compile_project(cir_project).sequences[0].actors
    }

    assert actors["mina"].transform.location_cm == UnrealVector(
        x=-100.0, y=-150.0, z=0.0
    )
    assert actors["arjun"].transform.location_cm == UnrealVector(
        x=-50.0, y=100.0, z=0.0
    )
    assert actors["contract"].transform.location_cm == UnrealVector(
        x=0.0, y=0.0, z=80.0
    )


def test_compile_infers_deterministic_camera_blocking(cir_project: Project) -> None:
    cameras = compile_project(cir_project).sequences[0].cameras

    assert cameras[0].look_at_location_cm == UnrealVector(x=-75.0, y=-25.0, z=160.0)
    assert cameras[0].transform.location_cm == UnrealVector(x=-675.0, y=-25.0, z=160.0)
    assert cameras[0].transform.rotation.w == 1.0
    assert cameras[1].transform.location_cm == UnrealVector(x=-120.0, y=0.0, z=240.0)
    assert cameras[2].transform.location_cm == UnrealVector(x=-325.0, y=55.0, z=160.0)
    assert all(camera.inferred_transform for camera in cameras)


def test_compile_preserves_performance_and_dialogue_metadata(
    cir_project: Project,
) -> None:
    cues = compile_project(cir_project).sequences[0].performance_cues
    source_dialogue = cir_project.scenes[0].beats[1].performances[0].dialogue

    assert source_dialogue is not None
    assert cues[1].actor_binding_id == "actor:mina"
    assert cues[1].dialogue == source_dialogue.text
    assert cues[1].dialogue_language == "en"
    assert cues[1].dialogue_start_frame == 120
    assert cues[2].look_at_binding_id == "actor:mina"
    assert cues[2].dialogue_start_frame == 216


def test_compile_reports_v01_fallbacks_explicitly(cir_project: Project) -> None:
    codes = [warning.code for warning in compile_project(cir_project).warnings]

    assert codes.count("placeholder_character") == 2
    assert codes.count("placeholder_environment") == 2
    assert codes.count("inferred_camera_transform") == 4
    assert codes.count("camera_movement_metadata_only") == 1
    assert codes.count("performance_metadata_only") == 1


def test_scene_without_performances_has_no_performance_warning(
    cir_project: Project,
) -> None:
    for beat in cir_project.scenes[0].beats:
        beat.performances = []

    plan = compile_project(cir_project)

    assert plan.sequences[0].performance_cues == []
    assert "performance_metadata_only" not in {
        warning.code for warning in plan.warnings
    }


def test_camera_without_targets_blocks_toward_world_origin(
    cir_project: Project,
) -> None:
    shot = cir_project.scenes[0].shots[-1]
    shot.camera.target_ids = []
    shot.subject_ids = []

    camera = compile_project(cir_project).sequences[0].cameras[-1]

    assert camera.look_at_location_cm == UnrealVector()
    assert camera.target_binding_ids == []


def test_compile_is_deterministic(cir_project: Project) -> None:
    first = render_unreal_plan(compile_project(cir_project))
    second = render_unreal_plan(compile_project(deepcopy(cir_project)))

    assert first == second


def test_compile_revalidates_typed_cir(cir_project: Project) -> None:
    cir_project.scenes[0].shots = [
        shot
        for shot in cir_project.scenes[0].shots
        if shot.purpose.value != "establishing"
    ]

    with pytest.raises(CIRValidationError, match="missing_establishing_shot"):
        compile_project(cir_project)


def test_explicit_camera_transform_is_converted_without_inference_warning(
    cir_project: Project,
) -> None:
    cir_project.scenes[0].shots[0].camera.transform = Transform(
        position=Vector3(x=1.0, y=2.0, z=3.0)
    )

    plan = compile_project(cir_project)
    camera = plan.sequences[0].cameras[0]

    assert camera.inferred_transform is False
    assert camera.transform.location_cm == UnrealVector(x=-300.0, y=100.0, z=200.0)
    assert not any(
        warning.code == "inferred_camera_transform"
        and warning.source_id == "shot-establishing"
        for warning in plan.warnings
    )


def test_unreal_environment_asset_paths_disable_placeholders(
    cir_project: Project,
) -> None:
    cir_project.environment[0].asset_uri = "/Game/Props/SM_Contract.SM_Contract"

    plan = compile_project(cir_project)
    contract = next(
        actor
        for actor in plan.sequences[0].actors
        if actor.source_entity_id == "contract"
    )

    assert contract.asset_path == "/Game/Props/SM_Contract.SM_Contract"
    assert contract.placeholder is False


def test_non_unreal_asset_uri_is_reported(cir_project: Project) -> None:
    cir_project.environment[0].asset_uri = "https://example.com/contract.fbx"

    plan = compile_project(cir_project)

    assert any(
        warning.code == "unsupported_asset_uri" and warning.source_id == "contract"
        for warning in plan.warnings
    )


def test_invalid_rotation_and_package_path_fail_early(cir_project: Project) -> None:
    cir_project.characters[0].initial_transform.rotation = Quaternion(
        x=0.0, y=0.0, z=0.0, w=0.0
    )
    with pytest.raises(ValueError, match="non-zero length"):
        compile_project(cir_project)

    cir_project.characters[0].initial_transform.rotation = Quaternion()
    with pytest.raises(ValueError, match="package path"):
        compile_project(cir_project, package_path="/Game/../Unsafe")
