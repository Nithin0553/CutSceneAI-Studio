from __future__ import annotations

from decimal import Decimal

from cutsceneai_cir import Project
from cutsceneai_dialogue import plan_project, seconds_to_frame


def test_plan_project_emits_stable_office_dialogue_cues(project: Project) -> None:
    plan = plan_project(project)

    assert plan.dialogue_version == "0.1.0"
    assert plan.project_id == "office-dialogue"
    assert plan.fps == 24
    assert plan.warnings == []
    assert [cue.cue_id for cue in plan.cues] == [
        "dialogue-scene-meeting-beat-confrontation-mina-1",
        "dialogue-scene-meeting-beat-confrontation-arjun-2",
    ]
    assert [cue.start_seconds for cue in plan.cues] == [5.0, 9.0]
    assert [cue.start_frame for cue in plan.cues] == [120, 216]
    assert plan.cues[0].output_filename.endswith("mina-1.wav")
    assert plan.cues[1].beat_end_seconds == 14.0


def test_plan_reports_existing_audio_and_out_of_range_start(project: Project) -> None:
    dialogue = project.scenes[0].beats[1].performances[0].dialogue
    assert dialogue is not None
    dialogue.audio_uri = "/Game/Audio/Mina.Mina"
    dialogue.start_offset_seconds = 10.0

    plan = plan_project(project)

    assert [warning.code for warning in plan.warnings] == [
        "dialogue_start_out_of_range",
        "existing_audio_uri",
    ]
    assert all(warning.cue_id == plan.cues[0].cue_id for warning in plan.warnings)


def test_seconds_to_frame_uses_half_up_rounding() -> None:
    assert seconds_to_frame(0.5, 1) == 1
    assert seconds_to_frame(Decimal("0.49"), 1) == 0
    assert seconds_to_frame(5, 24) == 120


def test_plan_supports_every_valid_identifier_separator(project: Project) -> None:
    project.scenes[0].id = "scene_meeting"
    cue = plan_project(project).cues[0]
    assert "scene_meeting" in cue.cue_id
    assert cue.output_filename.endswith(".wav")
