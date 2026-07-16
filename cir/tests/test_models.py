import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from cutsceneai_cir import Project, ShotPurpose, validate_project


EXAMPLE_PATH = Path(__file__).parents[1] / "examples" / "office-dialogue.cir.json"


def load_example() -> dict[str, object]:
    return json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))


def test_office_dialogue_builds_a_typed_project() -> None:
    project = validate_project(load_example())

    assert isinstance(project, Project)
    assert project.schema_version == "0.1.0"
    assert project.settings.fps == 24
    assert project.characters[0].id == "mina"
    assert project.environment[0].id == "contract"
    assert project.scenes[0].beats[1].performances[0].dialogue is not None
    assert project.scenes[0].shots[0].purpose is ShotPurpose.ESTABLISHING
    assert project.scenes[0].shots[1].purpose is ShotPurpose.ENVIRONMENT_DETAIL


def test_models_forbid_unknown_fields() -> None:
    payload = load_example()
    payload["unexpected"] = True

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        validate_project(payload)


def test_character_accepts_engine_neutral_asset_uri() -> None:
    payload = load_example()
    payload["characters"][0]["asset_uri"] = (
        "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple.SKM_Manny_Simple"
    )

    project = validate_project(payload)

    assert project.characters[0].asset_uri == (
        "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple.SKM_Manny_Simple"
    )


def test_models_reject_invalid_ranges() -> None:
    payload = load_example()
    payload["scenes"][0]["shots"][0]["duration_seconds"] = 0
    payload["scenes"][0]["beats"][0]["performances"][0]["facial"]["intensity"] = 1.5

    with pytest.raises(ValidationError) as exc_info:
        validate_project(payload)

    errors = exc_info.value.errors()
    assert {error["type"] for error in errors} >= {"greater_than", "less_than_equal"}


def test_project_generates_a_strict_json_schema() -> None:
    schema = Project.model_json_schema()

    assert schema["additionalProperties"] is False
    assert "Scene" in schema["$defs"]
    assert "Shot" in schema["$defs"]
