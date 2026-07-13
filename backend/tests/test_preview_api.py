import json
from pathlib import Path
from xml.etree import ElementTree

from fastapi.testclient import TestClient

from app.main import app


EXAMPLE = Path(__file__).resolve().parents[2] / "cir" / "examples" / "office-dialogue.cir.json"
client = TestClient(app)


def payload() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_compile_preview_returns_portable_manifest() -> None:
    response = client.post("/api/v1/preview/compile", json=payload())

    assert response.status_code == 200
    body = response.json()
    assert body["preview_version"] == "0.1.0"
    assert body["project_id"] == "office-dialogue"
    assert body["scenes"][0]["duration_frames"] == 432
    assert len(body["scenes"][0]["camera_cuts"]) == 4


def test_storyboard_endpoint_returns_svg() -> None:
    response = client.post("/api/v1/preview/storyboard.svg", json=payload())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert ElementTree.fromstring(response.text).tag == "{http://www.w3.org/2000/svg}svg"


def test_preview_rejects_invalid_cir() -> None:
    value = payload()
    value["scenes"][0]["shots"][0]["purpose"] = "action"

    response = client.post("/api/v1/preview/compile", json=value)

    assert response.status_code == 422
    assert response.json()["valid"] is False
    assert "missing_establishing_shot" in {problem["code"] for problem in response.json()["errors"]}
