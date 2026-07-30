from copy import deepcopy

import pytest

from cutsceneai_cir import CIRValidationError, Project, Quaternion, Transform, Vector3
from cutsceneai_unreal import (
    SKELETAL_MESH_ACTOR_CLASS_PATH,
    UnrealMeshType,
    UnrealVector,
    compile_project,
    render_unreal_plan,
)


def test_compile_office_dialogue_creates_editable_sequence_contract(
    cir_project: Project,
) -> None:
    plan = compile_project(cir_project)
    sequence = plan.sequences[0]

    assert plan.adapter_version == "0.6.0"
    assert plan.target_engine_version == "5.8.0"
    assert sequence.asset_name == "LS_SceneMeeting"
    assert sequence.package_path == "/Game/CutSceneAI/Sequences"
    assert sequence.duration_frames == 432
    assert len(sequence.set_pieces) == 4
    assert len(sequence.actors) == 4
    assert len(sequence.performance_cues) == 4
    assert sequence.animation_sections == []
    assert sequence.audio_sections == []
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


def test_compile_builds_visible_asset_independent_proxy_assembly(
    cir_project: Project,
) -> None:
    sequence = compile_project(cir_project).sequences[0]
    actors = {actor.source_entity_id: actor for actor in sequence.actors}

    mina = actors["mina"]
    assert mina.actor_class_path == "/Script/Engine.StaticMeshActor"
    assert mina.mesh_type is UnrealMeshType.STATIC_MESH
    assert mina.placeholder_visual is not None
    assert mina.placeholder_visual.mesh_asset_path == (
        "/Engine/BasicShapes/Cylinder.Cylinder"
    )
    assert mina.placeholder_visual.transform.location_cm == UnrealVector(
        x=-100.0, y=-150.0, z=90.0
    )
    assert mina.placeholder_visual.transform.scale == UnrealVector(
        x=0.45, y=0.45, z=1.8
    )

    contract = actors["contract"]
    assert contract.placeholder_visual is not None
    assert contract.placeholder_visual.transform.location_cm == UnrealVector(
        x=0.0, y=0.0, z=80.5
    )
    assert contract.placeholder_visual.transform.scale == UnrealVector(
        x=0.3, y=0.21, z=0.01
    )

    table = actors["conference-table"]
    assert table.placeholder_visual is not None
    assert table.placeholder_visual.transform.location_cm.z == 37.5
    assert table.placeholder_visual.transform.scale == UnrealVector(
        x=2.4, y=1.2, z=0.75
    )

    assert [piece.display_name for piece in sequence.set_pieces] == [
        "SET_Floor",
        "SET_BackWall",
        "SET_LeftWall",
        "SET_RightWall",
    ]


def test_compile_non_interior_scene_uses_portable_floor_stage(
    cir_project: Project,
) -> None:
    cir_project.scenes[0].location = "Forest clearing"

    set_pieces = compile_project(cir_project).sequences[0].set_pieces

    assert [piece.display_name for piece in set_pieces] == ["SET_Floor"]


def test_compile_infers_deterministic_camera_blocking(cir_project: Project) -> None:
    cameras = compile_project(cir_project).sequences[0].cameras

    assert cameras[0].look_at_location_cm == UnrealVector(x=-75.0, y=-25.0, z=160.0)
    assert cameras[0].transform.location_cm == UnrealVector(x=-675.0, y=-25.0, z=160.0)
    assert cameras[0].transform.rotation.w == 1.0
    assert cameras[1].transform.location_cm == UnrealVector(x=-120.0, y=0.0, z=240.0)
    assert cameras[2].look_at_location_cm == UnrealVector(x=-100.0, y=-150.0, z=160.0)
    assert cameras[2].transform.location_cm.x == pytest.approx(0.990195, abs=1e-6)
    assert cameras[2].transform.location_cm.y == pytest.approx(201.98039, abs=1e-6)
    assert cameras[2].transform.location_cm.z == 160.0
    assert all(camera.inferred_transform for camera in cameras)


def test_over_the_shoulder_camera_keeps_foreground_near_frame_edge(
    cir_project: Project,
) -> None:
    sequence = compile_project(cir_project).sequences[0]
    camera = sequence.cameras[2]
    actor_points = {
        actor.source_entity_id: UnrealVector(
            x=actor.transform.location_cm.x,
            y=actor.transform.location_cm.y,
            z=actor.transform.location_cm.z + 160.0,
        )
        for actor in sequence.actors
        if actor.source_entity_id in {"mina", "arjun"}
    }

    origin = camera.transform.location_cm
    primary = actor_points["mina"]
    foreground = actor_points["arjun"]
    primary_direction = (primary.x - origin.x, primary.y - origin.y)
    foreground_direction = (foreground.x - origin.x, foreground.y - origin.y)
    cross = abs(
        primary_direction[0] * foreground_direction[1]
        - primary_direction[1] * foreground_direction[0]
    )
    dot = (
        primary_direction[0] * foreground_direction[0]
        + primary_direction[1] * foreground_direction[1]
    )

    assert camera.look_at_location_cm == primary
    assert 0.15 < cross / dot < 0.2


def test_over_the_shoulder_camera_handles_coincident_targets(
    cir_project: Project,
) -> None:
    cir_project.characters[1].initial_transform.position = cir_project.characters[
        0
    ].initial_transform.position

    camera = compile_project(cir_project).sequences[0].cameras[2]

    assert camera.transform.location_cm == UnrealVector(x=-350.0, y=-150.0, z=160.0)


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


def test_compile_creates_speaker_associated_dialogue_audio_sections(
    cir_project: Project,
) -> None:
    mina_audio = "/Game/CutSceneAI/Audio/SW_Mina_Line01.SW_Mina_Line01"
    arjun_audio = "/Game/CutSceneAI/Audio/SW_Arjun_Line01.SW_Arjun_Line01"
    mina_dialogue = cir_project.scenes[0].beats[1].performances[0].dialogue
    arjun_dialogue = cir_project.scenes[0].beats[1].performances[1].dialogue
    assert mina_dialogue is not None
    assert arjun_dialogue is not None
    mina_dialogue.audio_uri = mina_audio
    arjun_dialogue.audio_uri = arjun_audio

    plan = compile_project(cir_project)
    sections = plan.sequences[0].audio_sections

    assert [section.actor_binding_id for section in sections] == [
        "actor:mina",
        "actor:arjun",
    ]
    assert [(section.start_frame, section.end_frame) for section in sections] == [
        (120, 336),
        (216, 336),
    ]
    assert [section.asset_path for section in sections] == [mina_audio, arjun_audio]
    assert [section.dialogue_text for section in sections] == [
        "You said this would be signed yesterday.",
        "Legal changed the final clause. I was waiting for approval.",
    ]
    dialogue_warning = next(
        warning for warning in plan.warnings if warning.code == "dialogue_metadata_only"
    )
    assert "Explicit dialogue audio assets compile" in dialogue_warning.message


def test_compile_rejects_non_unreal_dialogue_audio_uri(
    cir_project: Project,
) -> None:
    dialogue = cir_project.scenes[0].beats[1].performances[0].dialogue
    assert dialogue is not None
    dialogue.audio_uri = "https://example.com/mina.wav"

    plan = compile_project(cir_project)

    assert plan.sequences[0].audio_sections == []
    assert any(
        warning.code == "unsupported_audio_uri"
        and warning.source_id == "beat-confrontation"
        for warning in plan.warnings
    )


def test_compile_skips_dialogue_audio_starting_at_performance_end(
    cir_project: Project,
) -> None:
    dialogue = cir_project.scenes[0].beats[1].performances[0].dialogue
    assert dialogue is not None
    dialogue.audio_uri = "/Game/CutSceneAI/Audio/SW_Mina_Line01.SW_Mina_Line01"
    dialogue.start_offset_seconds = 10.0

    plan = compile_project(cir_project)

    assert plan.sequences[0].audio_sections == []
    assert any(
        warning.code == "dialogue_audio_out_of_range"
        and warning.source_id == "beat-confrontation"
        for warning in plan.warnings
    )


def test_compile_creates_editable_animation_sections_for_skeletal_characters(
    cir_project: Project,
) -> None:
    quinn_mesh = "/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple.SKM_Quinn_Simple"
    manny_mesh = "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple.SKM_Manny_Simple"
    quinn_idle = "/Game/Characters/Mannequins/Animations/Quinn/MF_Idle.MF_Idle"
    manny_idle = "/Game/Characters/Mannequins/Animations/Manny/MM_Idle.MM_Idle"
    cir_project.characters[0].asset_uri = quinn_mesh
    cir_project.characters[1].asset_uri = manny_mesh
    for beat in cir_project.scenes[0].beats:
        for performance in beat.performances:
            performance.motion.asset_uri = (
                quinn_idle if performance.character_id == "mina" else manny_idle
            )

    plan = compile_project(cir_project)
    sections = plan.sequences[0].animation_sections

    assert [section.actor_binding_id for section in sections] == [
        "actor:mina",
        "actor:mina",
        "actor:arjun",
        "actor:arjun",
    ]
    assert [(section.start_frame, section.end_frame) for section in sections] == [
        (0, 96),
        (96, 336),
        (96, 336),
        (336, 432),
    ]
    assert [section.asset_path for section in sections] == [
        quinn_idle,
        quinn_idle,
        manny_idle,
        manny_idle,
    ]
    performance_warning = next(
        warning
        for warning in plan.warnings
        if warning.code == "performance_metadata_only"
    )
    assert "Explicit animation assets compile" in performance_warning.message


def test_compile_rejects_non_unreal_animation_uri(
    cir_project: Project,
) -> None:
    cir_project.characters[
        0
    ].asset_uri = "/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple.SKM_Quinn_Simple"
    cir_project.scenes[0].beats[0].performances[
        0
    ].motion.asset_uri = "https://example.com/mina.fbx"

    plan = compile_project(cir_project)

    assert plan.sequences[0].animation_sections == []
    assert any(
        warning.code == "unsupported_animation_uri"
        and warning.source_id == "beat-arrival"
        for warning in plan.warnings
    )


def test_compile_requires_skeletal_mesh_for_animation_section(
    cir_project: Project,
) -> None:
    cir_project.scenes[0].beats[0].performances[
        0
    ].motion.asset_uri = "/Game/Characters/Mannequins/Animations/Quinn/MF_Idle.MF_Idle"

    plan = compile_project(cir_project)

    assert plan.sequences[0].animation_sections == []
    assert any(
        warning.code == "animation_requires_skeletal_mesh"
        and warning.source_id == "beat-arrival"
        for warning in plan.warnings
    )


def test_compile_reports_v01_fallbacks_explicitly(cir_project: Project) -> None:
    codes = [warning.code for warning in compile_project(cir_project).warnings]

    assert codes.count("placeholder_character") == 2
    assert codes.count("placeholder_environment") == 2
    assert codes.count("inferred_camera_transform") == 4
    assert codes.count("camera_movement_metadata_only") == 1
    assert codes.count("performance_metadata_only") == 1
    assert codes.count("dialogue_metadata_only") == 1


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
    assert "dialogue_metadata_only" not in {warning.code for warning in plan.warnings}


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
    assert contract.placeholder_visual is None


def test_unreal_character_asset_path_creates_skeletal_mesh_binding(
    cir_project: Project,
) -> None:
    cir_project.characters[
        0
    ].asset_uri = "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple.SKM_Manny_Simple"

    plan = compile_project(cir_project)
    mina = next(
        actor for actor in plan.sequences[0].actors if actor.source_entity_id == "mina"
    )

    assert mina.asset_path == (
        "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple.SKM_Manny_Simple"
    )
    assert mina.actor_class_path == SKELETAL_MESH_ACTOR_CLASS_PATH
    assert mina.mesh_type is UnrealMeshType.SKELETAL_MESH
    assert mina.placeholder is False
    assert mina.placeholder_visual is None
    assert not any(
        warning.code == "placeholder_character" and warning.source_id == "mina"
        for warning in plan.warnings
    )


def test_non_unreal_character_asset_uri_falls_back_to_proxy(
    cir_project: Project,
) -> None:
    cir_project.characters[0].asset_uri = "https://example.com/mina.fbx"

    plan = compile_project(cir_project)
    mina = next(
        actor for actor in plan.sequences[0].actors if actor.source_entity_id == "mina"
    )

    assert mina.mesh_type is UnrealMeshType.STATIC_MESH
    assert mina.placeholder is True
    assert mina.placeholder_visual is not None
    assert any(
        warning.code == "unsupported_asset_uri" and warning.source_id == "mina"
        for warning in plan.warnings
    )


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
