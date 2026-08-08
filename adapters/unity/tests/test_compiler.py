from pydantic import ValidationError

from cutsceneai_cir import Project
from cutsceneai_parity import compile_semantics
from cutsceneai_unity import (
    UnityAnimationAsset,
    UnityAnimationSection,
    UnityAssetMap,
    UnityAudioAsset,
    UnityAudioSection,
    UnityCameraCut,
    UnityEntityAsset,
    UnityVector,
    compile_project,
)


def _complete_map(project: Project) -> UnityAssetMap:
    scene = compile_semantics(project).scenes[0]
    return UnityAssetMap(
        project_id=project.id,
        entities=[
            UnityEntityAsset(
                source_entity_id="mina", prefab_path="Assets/Characters/Mina.prefab"
            )
        ],
        animations=[
            UnityAnimationAsset(
                cue_id=cue.cue_id,
                asset_path="Assets/Animations/Idle.anim",
            )
            for cue in scene.performance_cues
        ],
        audio=[
            UnityAudioAsset(
                cue_id=scene.dialogue_cues[0].cue_id,
                asset_path="Assets/Audio/Mina.wav",
                end_frame=178,
            ),
            UnityAudioAsset(
                cue_id=scene.dialogue_cues[1].cue_id,
                asset_path="Assets/Audio/Arjun.wav",
                end_frame=302,
            ),
        ],
    )


def test_compile_golden_cir_into_editable_unity_timeline_plan(
    cir_project: Project,
) -> None:
    plan = compile_project(cir_project)

    assert plan.adapter_version == "0.1.0"
    assert plan.target_engine == "Unity"
    assert plan.target_engine_version == "6000.0"
    assert plan.timeline_package_version == "1.8.12"
    assert plan.fps == 24
    assert plan.semantics == compile_semantics(cir_project)
    sequence = plan.sequences[0]
    assert sequence.timeline_asset_path == (
        "Assets/CutSceneAI/Timelines/TL_SceneMeeting.playable"
    )
    assert sequence.scene_asset_path == "Assets/CutSceneAI/Scenes/SC_SceneMeeting.unity"
    assert sequence.duration_frames == 432
    assert len(sequence.actors) == 4
    assert all(actor.placeholder for actor in sequence.actors)
    assert len(sequence.animation_sections) == 4
    assert all(section.placeholder for section in sequence.animation_sections)
    assert sequence.audio_sections == []
    assert [(camera.start_frame, camera.end_frame) for camera in sequence.cameras] == [
        (0, 96),
        (96, 144),
        (144, 336),
        (336, 432),
    ]
    assert len(plan.warnings) == 10


def test_asset_map_binds_prefabs_animation_and_measured_audio(
    cir_project: Project,
) -> None:
    plan = compile_project(cir_project, asset_map=_complete_map(cir_project))
    sequence = plan.sequences[0]

    mina = next(actor for actor in sequence.actors if actor.source_entity_id == "mina")
    assert mina.prefab_path == "Assets/Characters/Mina.prefab"
    assert mina.placeholder is False
    assert all(not section.placeholder for section in sequence.animation_sections)
    assert [section.end_frame for section in sequence.audio_sections] == [178, 302]
    assert {warning.code for warning in plan.warnings} == {"placeholder_entity"}
    assert len(plan.warnings) == 3


def test_explicit_camera_transform_and_custom_paths_are_preserved(
    cir_project: Project,
) -> None:
    cir_project.scenes[0].shots[0].camera.transform = cir_project.characters[
        0
    ].initial_transform.model_copy(deep=True)
    plan = compile_project(
        cir_project,
        timeline_path="Assets/Research/Timelines",
        scene_path="Assets/Research/Scenes",
    )

    camera = plan.sequences[0].cameras[0]
    assert camera.position_m.x == -1.5
    assert camera.position_m.z == -1.0
    assert plan.sequences[0].timeline_asset_path.startswith(
        "Assets/Research/Timelines/"
    )


def test_invalid_paths_mismatched_project_and_unknown_mapping_fail(
    cir_project: Project,
) -> None:
    for kwargs, expected in [
        ({"timeline_path": "../Outside"}, "timeline_path must be"),
        ({"scene_path": "Assets"}, "scene_path must be"),
        (
            {"asset_map": UnityAssetMap(project_id="another-project")},
            "does not match CIR project",
        ),
        (
            {
                "asset_map": UnityAssetMap(
                    project_id=cir_project.id,
                    entities=[
                        UnityEntityAsset(
                            source_entity_id="unknown",
                            prefab_path="Assets/Unknown.prefab",
                        )
                    ],
                )
            },
            "unknown entity key",
        ),
    ]:
        try:
            compile_project(cir_project, **kwargs)
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError("invalid Unity compilation input should fail")


def test_invalid_audio_timing_and_duplicate_map_keys_fail(cir_project: Project) -> None:
    dialogue = compile_semantics(cir_project).scenes[0].dialogue_cues[0]
    for end_frame, expected in [
        (dialogue.start_frame, "must end after"),
        (400, "beyond"),
    ]:
        mapping = UnityAssetMap(
            project_id=cir_project.id,
            audio=[
                UnityAudioAsset(
                    cue_id=dialogue.cue_id,
                    asset_path="Assets/Audio/Mina.wav",
                    end_frame=end_frame,
                )
            ],
        )
        try:
            compile_project(cir_project, asset_map=mapping)
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError("invalid audio range should fail")

    try:
        UnityAssetMap(
            project_id=cir_project.id,
            animations=[
                UnityAnimationAsset(cue_id="same", asset_path="Assets/A.anim"),
                UnityAnimationAsset(cue_id="same", asset_path="Assets/B.anim"),
            ],
        )
    except ValidationError as exc:
        assert "duplicate animations keys" in str(exc)
    else:
        raise AssertionError("duplicate mapping should fail")


def test_timeline_sections_reject_invalid_ranges_and_placeholder_state() -> None:
    invalid_factories = [
        lambda: UnityAnimationSection(
            cue_id="performance:test",
            actor_binding_id="actor:test",
            start_frame=10,
            end_frame=10,
            placeholder=True,
        ),
        lambda: UnityAnimationSection(
            cue_id="performance:test",
            actor_binding_id="actor:test",
            start_frame=0,
            end_frame=10,
            asset_path="Assets/Test.anim",
            placeholder=True,
        ),
        lambda: UnityAudioSection(
            cue_id="dialogue:test",
            actor_binding_id="actor:test",
            start_frame=10,
            end_frame=10,
            asset_path="Assets/Test.wav",
        ),
        lambda: UnityCameraCut(
            cut_id="camera:test",
            source_shot_id="shot-test",
            display_name="CSA_CAM_Test",
            start_frame=10,
            end_frame=10,
            lens_mm=50,
            position_m=UnityVector(),
            look_at_m=UnityVector(),
        ),
    ]

    for factory in invalid_factories:
        try:
            factory()
        except ValidationError:
            pass
        else:
            raise AssertionError("invalid Unity section should fail validation")


def test_unity_compilation_is_deterministic(cir_project: Project) -> None:
    first = compile_project(cir_project, asset_map=_complete_map(cir_project))
    second = compile_project(
        cir_project.model_copy(deep=True), asset_map=_complete_map(cir_project)
    )
    assert first == second
