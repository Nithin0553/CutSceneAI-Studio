import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)
EXAMPLE_PATH = Path(__file__).resolve().parents[2] / "cir" / "examples" / "office-dialogue.cir.json"


def load_example() -> dict:
    return json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))


def test_validate_cir_accepts_complete_project() -> None:
    response = client.post("/api/v1/cir/validate", json=load_example())

    assert response.status_code == 200
    assert response.json() == {
        "valid": True,
        "schema_version": "0.1.0",
        "project_id": "office-dialogue",
        "summary": {"scene_count": 1, "beat_count": 3, "shot_count": 4},
    }


def test_validate_cir_returns_structural_errors() -> None:
    payload = load_example()
    del payload["id"]

    response = client.post("/api/v1/cir/validate", json=payload)

    assert response.status_code == 422
    assert response.json()["valid"] is False
    assert {problem["code"] for problem in response.json()["errors"]} == {"structural.missing"}
    assert response.json()["errors"][0]["path"] == "id"


def test_validate_cir_returns_domain_errors() -> None:
    payload = load_example()
    payload["scenes"][0]["shots"][0]["purpose"] = "action"

    response = client.post("/api/v1/cir/validate", json=payload)

    assert response.status_code == 422
    assert response.json()["valid"] is False
    assert "missing_establishing_shot" in {problem["code"] for problem in response.json()["errors"]}


def test_validate_cir_rejects_non_object_body() -> None:
    response = client.post("/api/v1/cir/validate", json=[])

    assert response.status_code == 422
    assert response.json()["valid"] is False
    assert response.json()["errors"][0]["code"] == "structural.model_type"
    assert response.json()["errors"][0]["path"] == "$"
