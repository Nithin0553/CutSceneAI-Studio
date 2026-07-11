from cutsceneai_cir.models import Character, Project, Scene, SceneBeat
from cutsceneai_cir.validation import validate_project


def test_validate_project_builds_a_typed_model() -> None:
    payload = {
        "name": "Office Dialogue",
        "description": "A tense scene between coworkers.",
        "characters": [{"name": "Mina", "role": "Manager"}],
        "scenes": [
            {
                "id": "scene-001",
                "title": "The meeting",
                "beats": [{"id": "beat-001", "description": "Mina enters the room."}],
            }
        ],
    }

    project = validate_project(payload)

    assert isinstance(project, Project)
    assert project.name == "Office Dialogue"
    assert isinstance(project.characters[0], Character)
    assert isinstance(project.scenes[0], Scene)
    assert isinstance(project.scenes[0].beats[0], SceneBeat)
    assert project.scenes[0].beats[0].description == "Mina enters the room."
