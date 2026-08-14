from cutsceneai_cir import Project
from cutsceneai_parity import (
    EngineName,
    EngineTimelineReadback,
    ReadbackEvidence,
    RealizedSection,
    verify_readbacks,
)


def _realize(readback: EngineTimelineReadback) -> None:
    scene = readback.semantics.scenes[0]
    readback.evidence = ReadbackEvidence(
        animation_sections=[
            RealizedSection(
                semantic_id=cue.cue_id,
                actor_binding_id=cue.actor_binding_id,
                start_frame=cue.start_frame,
                end_frame=cue.end_frame,
            )
            for cue in scene.performance_cues
        ],
        facial_sections=[
            RealizedSection(
                semantic_id=cue.cue_id,
                actor_binding_id=cue.actor_binding_id,
                start_frame=cue.start_frame,
                end_frame=cue.end_frame,
            )
            for cue in scene.performance_cues
        ],
        camera_sections=[
            RealizedSection(
                semantic_id=cut.cut_id,
                start_frame=cut.start_frame,
                end_frame=cut.end_frame,
            )
            for cut in scene.camera_cuts
        ],
        audio_sections=[
            RealizedSection(
                semantic_id=cue.cue_id,
                actor_binding_id=cue.actor_binding_id,
                start_frame=cue.start_frame,
                end_frame=cue.start_frame + 24,
            )
            for cue in scene.dialogue_cues
        ],
    )


def test_identical_readbacks_are_semantically_equivalent_with_coverage_warnings(
    cir_project: Project, readbacks: list[EngineTimelineReadback]
) -> None:
    report = verify_readbacks(cir_project, readbacks, tolerance_frames=0)

    assert report.equivalent is True
    assert report.error_count == 0
    assert report.warning_count == 28


def test_complete_realization_passes_strict_verification(
    cir_project: Project, readbacks: list[EngineTimelineReadback]
) -> None:
    for readback in readbacks:
        _realize(readback)

    report = verify_readbacks(
        cir_project,
        readbacks,
        tolerance_frames=0,
        require_animation=True,
        require_facial=True,
        require_camera=True,
        require_audio=True,
    )

    assert report.equivalent is True
    assert report.error_count == 0
    assert report.warning_count == 0
    assert [item.animation_section_count for item in report.readbacks] == [4, 4]
    assert [item.facial_section_count for item in report.readbacks] == [4, 4]
    assert [item.camera_section_count for item in report.readbacks] == [4, 4]
    assert [item.audio_section_count for item in report.readbacks] == [2, 2]
    assert report.requirements.facial is True
    assert report.requirements.camera is True


def test_engine_specific_asset_paths_do_not_define_semantic_equality(
    cir_project: Project, readbacks: list[EngineTimelineReadback]
) -> None:
    for readback in readbacks:
        _realize(readback)
    readbacks[0].evidence.animation_sections[0].asset_ref = "/Game/Mina/Idle"
    readbacks[1].evidence.animation_sections[0].asset_ref = "Assets/Mina/Idle.anim"
    readbacks[0].evidence.audio_sections[0].asset_ref = "/Game/Mina/Line01"
    readbacks[1].evidence.audio_sections[0].asset_ref = "Assets/Mina/Line01.wav"

    report = verify_readbacks(
        cir_project,
        readbacks,
        tolerance_frames=0,
        require_animation=True,
        require_facial=True,
        require_camera=True,
        require_audio=True,
    )

    assert report.equivalent is True
    assert report.issues == []


def test_frame_tolerance_and_semantic_changes_are_reported(
    cir_project: Project, readbacks: list[EngineTimelineReadback]
) -> None:
    unity = readbacks[1]
    unity.semantics.scenes[0].camera_cuts[0].start_frame = 1
    within_tolerance = verify_readbacks(cir_project, readbacks, tolerance_frames=1)
    assert within_tolerance.equivalent is True

    unity.semantics.scenes[0].camera_cuts[0].start_frame = 2
    unity.semantics.scenes[0].camera_cuts[1].purpose = "reaction"
    unity.semantics.scenes[0].camera_cuts[2].target_binding_ids = []
    report = verify_readbacks(cir_project, readbacks, tolerance_frames=1)

    assert report.equivalent is False
    assert {
        issue.code for issue in report.issues if issue.severity.value == "error"
    } == {
        "frame_mismatch",
        "semantic_value_mismatch",
    }


def test_audio_end_frames_are_compared_directly_between_engines(
    cir_project: Project, readbacks: list[EngineTimelineReadback]
) -> None:
    for readback in readbacks:
        _realize(readback)
    readbacks[1].evidence.audio_sections[0].end_frame += 2

    report = verify_readbacks(cir_project, readbacks, tolerance_frames=1)

    issue = next(
        item
        for item in report.issues
        if item.scope == "realization:unreal_to_unity"
        and item.field == "audio.end_frame"
    )
    assert issue.code == "frame_mismatch"
    assert issue.delta_frames == 2


def test_facial_and_camera_realization_mismatches_are_reported(
    cir_project: Project, readbacks: list[EngineTimelineReadback]
) -> None:
    for readback in readbacks:
        _realize(readback)
    readbacks[1].evidence.facial_sections[0].end_frame += 2
    readbacks[1].evidence.camera_sections[0].start_frame += 2

    report = verify_readbacks(cir_project, readbacks, tolerance_frames=1)

    mismatches = {
        item.field: item.delta_frames
        for item in report.issues
        if item.scope == "realization:unreal_to_unity" and item.code == "frame_mismatch"
    }
    assert mismatches["facial.end_frame"] == 2
    assert mismatches["camera.start_frame"] == 2


def test_missing_extra_duplicate_and_header_changes_fail(
    cir_project: Project, readbacks: list[EngineTimelineReadback]
) -> None:
    unity = readbacks[1]
    scene = unity.semantics.scenes[0]
    scene.entities.pop()
    scene.performance_cues.append(scene.performance_cues[0].model_copy(deep=True))
    scene.dialogue_cues.append(
        scene.dialogue_cues[0].model_copy(update={"cue_id": "dialogue:unexpected"})
    )
    unity.semantics.fps = 30

    report = verify_readbacks(cir_project, readbacks)

    assert report.equivalent is False
    assert {
        "missing_semantic_item",
        "duplicate_semantic_id",
        "unexpected_semantic_item",
        "semantic_value_mismatch",
    } <= {issue.code for issue in report.issues}


def test_realization_failures_and_duplicate_engine_are_detected(
    cir_project: Project, readbacks: list[EngineTimelineReadback]
) -> None:
    _realize(readbacks[0])
    readbacks[0].evidence.animation_sections[0].end_frame += 2
    readbacks[0].evidence.audio_sections[0].end_frame = 400
    readbacks[0].evidence.audio_sections.append(
        RealizedSection(
            semantic_id="dialogue:unexpected",
            start_frame=0,
            end_frame=1,
        )
    )
    readbacks[0].evidence.animation_sections.append(
        RealizedSection(
            semantic_id="performance:unexpected",
            start_frame=0,
            end_frame=1,
        )
    )
    readbacks[0].evidence.facial_sections.append(
        RealizedSection(
            semantic_id="facial:unexpected",
            start_frame=0,
            end_frame=1,
        )
    )
    readbacks[0].evidence.camera_sections.append(
        RealizedSection(
            semantic_id="camera:unexpected",
            start_frame=0,
            end_frame=1,
        )
    )
    readbacks[1].engine = readbacks[0].engine

    report = verify_readbacks(
        cir_project,
        readbacks,
        tolerance_frames=0,
        require_animation=True,
        require_facial=True,
        require_camera=True,
        require_audio=True,
    )

    assert report.equivalent is False
    codes = {issue.code for issue in report.issues}
    assert {
        "duplicate_engine_readback",
        "frame_mismatch",
        "audio_exceeds_dialogue_window",
        "unexpected_realized_audio",
        "unexpected_realized_animation",
        "unexpected_realized_facial",
        "unexpected_realized_camera",
        "missing_realized_animation",
        "missing_realized_audio",
        "missing_realized_facial",
        "missing_realized_camera",
    } <= codes


def test_placeholder_animation_does_not_satisfy_strict_realization(
    cir_project: Project, readbacks: list[EngineTimelineReadback]
) -> None:
    for readback in readbacks:
        _realize(readback)
    readbacks[1].evidence.animation_sections[0].placeholder = True

    report = verify_readbacks(
        cir_project,
        readbacks,
        require_animation=True,
        require_facial=True,
        require_camera=True,
        require_audio=True,
    )

    assert report.equivalent is False
    assert any(
        item.code == "missing_realized_animation"
        and item.semantic_id == readbacks[1].evidence.animation_sections[0].semantic_id
        for item in report.issues
    )


def test_placeholder_facial_and_camera_do_not_satisfy_strict_realization(
    cir_project: Project, readbacks: list[EngineTimelineReadback]
) -> None:
    for readback in readbacks:
        _realize(readback)
    readbacks[0].evidence.facial_sections[0].placeholder = True
    readbacks[0].evidence.camera_sections[0].placeholder = True

    report = verify_readbacks(
        cir_project,
        readbacks,
        require_facial=True,
        require_camera=True,
    )

    codes = {item.code for item in report.issues}
    assert "missing_realized_facial" in codes
    assert "missing_realized_camera" in codes


def test_invalid_verifier_arguments_are_rejected(cir_project: Project) -> None:
    try:
        verify_readbacks(cir_project, [], tolerance_frames=-1)
    except ValueError as exc:
        assert str(exc) == "tolerance_frames must be non-negative"
    else:
        raise AssertionError("negative tolerance should fail")

    try:
        verify_readbacks(cir_project, [])
    except ValueError as exc:
        assert str(exc) == "At least one engine readback is required."
    else:
        raise AssertionError("empty readbacks should fail")


def test_cross_engine_gate_requires_unreal_and_unity(
    cir_project: Project, readbacks: list[EngineTimelineReadback]
) -> None:
    report = verify_readbacks(
        cir_project,
        [readbacks[1]],
        required_engines=(EngineName.UNREAL, EngineName.UNITY),
    )

    assert report.equivalent is False
    issue = next(
        item for item in report.issues if item.code == "missing_engine_readback"
    )
    assert issue.semantic_id == "unreal"
