from pydantic import ValidationError

from cutsceneai_cir import Project
from cutsceneai_parity import (
    SemanticDialogueCue,
    cir_fingerprint,
    compile_semantics,
)
from cutsceneai_parity.models import FrameRange


def test_compile_golden_cir_into_canonical_semantics(cir_project: Project) -> None:
    semantics = compile_semantics(cir_project)

    assert semantics.project_id == "office-dialogue"
    assert semantics.fps == 24
    assert semantics.cir_fingerprint_sha256 == cir_fingerprint(cir_project)
    assert len(semantics.cir_fingerprint_sha256) == 64
    assert len(semantics.scenes) == 1
    scene = semantics.scenes[0]
    assert scene.source_scene_id == "scene-meeting"
    assert scene.duration_frames == 432
    assert [item.binding_id for item in scene.entities] == [
        "actor:mina",
        "actor:arjun",
        "actor:contract",
        "actor:conference-table",
    ]
    assert [(cue.start_frame, cue.end_frame) for cue in scene.performance_cues] == [
        (0, 96),
        (96, 336),
        (96, 336),
        (336, 432),
    ]
    assert [cue.cue_id for cue in scene.performance_cues] == [
        "performance:scene-meeting:beat-arrival:mina:01",
        "performance:scene-meeting:beat-confrontation:mina:01",
        "performance:scene-meeting:beat-confrontation:arjun:02",
        "performance:scene-meeting:beat-reaction:arjun:01",
    ]
    assert [cue.start_frame for cue in scene.dialogue_cues] == [120, 216]
    assert [cut.start_frame for cut in scene.camera_cuts] == [0, 96, 144, 336]
    assert [cut.end_frame for cut in scene.camera_cuts] == [96, 144, 336, 432]


def test_compilation_and_fingerprint_are_deterministic(cir_project: Project) -> None:
    first = compile_semantics(cir_project)
    second = compile_semantics(cir_project.model_copy(deep=True))

    assert first == second
    cir_project.name = "Changed title"
    assert cir_fingerprint(cir_project) != first.cir_fingerprint_sha256


def test_semantic_ranges_must_be_nonempty() -> None:
    invalid_factories = [
        lambda: FrameRange(start_frame=10, end_frame=10),
        lambda: SemanticDialogueCue(
            cue_id="dialogue:test",
            source_beat_id="beat-test",
            actor_binding_id="actor:test",
            start_frame=10,
            window_end_frame=10,
            text_sha256="0" * 64,
            language="en",
        ),
    ]

    for factory in invalid_factories:
        try:
            factory()
        except ValidationError:
            pass
        else:
            raise AssertionError("empty semantic range should fail validation")
