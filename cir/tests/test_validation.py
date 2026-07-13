import json
from pathlib import Path

import pytest

from cutsceneai_cir import CIRValidationError, validate_project


EXAMPLE_PATH = Path(__file__).parents[1] / "examples" / "office-dialogue.cir.json"


def load_example() -> dict:
    return json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))


def error_codes(payload: dict) -> set[str]:
    with pytest.raises(CIRValidationError) as exc_info:
        validate_project(payload)
    return {issue.code for issue in exc_info.value.issues}


def test_complete_example_passes_domain_validation() -> None:
    project = validate_project(load_example())

    assert project.id == "office-dialogue"


def test_duplicate_ids_are_rejected() -> None:
    payload = load_example()
    payload["environment"][0]["id"] = "mina"

    assert "duplicate_id" in error_codes(payload)


def test_unknown_references_are_rejected() -> None:
    payload = load_example()
    payload["scenes"][0]["beats"][0]["performances"][0]["character_id"] = "ghost"
    payload["scenes"][0]["shots"][0]["camera"]["target_ids"] = ["missing-camera-target"]

    assert error_codes(payload) >= {
        "unknown_character_reference",
        "unknown_entity_reference",
    }


def test_timeline_overflow_and_overlap_are_rejected() -> None:
    payload = load_example()
    payload["scenes"][0]["shots"][0]["duration_seconds"] = 5.0
    payload["scenes"][0]["shots"][-1]["duration_seconds"] = 5.0

    assert error_codes(payload) >= {"shot_overlap", "shot_out_of_bounds"}


def test_scene_requires_an_establishing_shot() -> None:
    payload = load_example()
    payload["scenes"][0]["shots"][0]["purpose"] = "action"

    assert "missing_establishing_shot" in error_codes(payload)


def test_focused_environment_object_requires_detail_shot() -> None:
    payload = load_example()
    payload["scenes"][0]["shots"][1]["purpose"] = "action"

    assert "missing_environment_detail_shot" in error_codes(payload)


def test_coordinate_axes_must_not_be_collinear() -> None:
    payload = load_example()
    payload["settings"]["forward_axis"] = "-y"

    assert "coordinate_axes_collinear" in error_codes(payload)
