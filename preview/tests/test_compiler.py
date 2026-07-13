import json
from decimal import Decimal
from pathlib import Path

import pytest

from cutsceneai_cir import CIRValidationError, Project, validate_project
from cutsceneai_preview import (
    compile_project,
    render_preview_manifest,
    seconds_to_frame,
)


EXAMPLE = (
    Path(__file__).resolve().parents[2]
    / "cir"
    / "examples"
    / "office-dialogue.cir.json"
)


def project() -> Project:
    return validate_project(json.loads(EXAMPLE.read_text(encoding="utf-8")))


def test_frame_conversion_uses_explicit_half_up_rounding() -> None:
    assert seconds_to_frame(0.5, 25) == 13
    assert seconds_to_frame(Decimal("0.02"), 25) == 1


def test_compile_office_dialogue_timeline() -> None:
    manifest = compile_project(project())

    assert manifest.project_id == "office-dialogue"
    assert manifest.settings.fps == 24
    assert [
        (cut.start_frame, cut.end_frame) for cut in manifest.scenes[0].camera_cuts
    ] == [
        (0, 96),
        (96, 144),
        (144, 336),
        (336, 432),
    ]
    assert manifest.scenes[0].duration_frames == 432
    assert len(manifest.scenes[0].performance_cues) == 4
    assert manifest.scenes[0].performance_cues[1].dialogue_start_frame == 120
    assert manifest.scenes[0].performance_cues[2].dialogue_start_frame == 216


def test_compile_assigns_stable_placeholders_and_warnings() -> None:
    first = compile_project(project())
    second = compile_project(project())

    assert render_preview_manifest(first) == render_preview_manifest(second)
    assert [entity.placeholder_shape.value for entity in first.entities] == [
        "capsule",
        "capsule",
        "box",
        "box",
    ]
    assert len(first.warnings) == 4


def test_compile_revalidates_typed_projects() -> None:
    value = project()
    value.scenes[0].shots = [
        shot for shot in value.scenes[0].shots if shot.purpose.value != "establishing"
    ]

    with pytest.raises(CIRValidationError, match="missing_establishing_shot"):
        compile_project(value)


def test_subframe_shots_receive_one_in_bounds_frame() -> None:
    value = project()
    value.scenes[0].shots[0].duration_seconds = 0.001

    cut = compile_project(value).scenes[0].camera_cuts[0]

    assert (cut.start_frame, cut.end_frame) == (0, 1)
