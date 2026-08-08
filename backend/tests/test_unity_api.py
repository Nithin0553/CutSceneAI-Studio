import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


EXAMPLE = Path(__file__).resolve().parents[2] / "cir" / "examples" / "office-dialogue.cir.json"
client = TestClient(app)


def payload() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_export_unity_plan_returns_golden_timeline_contract() -> None:
    response = client.post("/api/v1/adapters/unity/export", json=payload())

    assert response.status_code == 200
    body = response.json()
    assert body["adapter_version"] == "0.1.0"
    assert body["target_engine_version"] == "6000.0"
    assert body["timeline_package_version"] == "1.8.12"
    assert body["semantics"]["cir_fingerprint_sha256"]
    assert body["sequences"][0]["duration_frames"] == 432
    assert len(body["sequences"][0]["animation_sections"]) == 4
    assert len(body["sequences"][0]["cameras"]) == 4


def test_export_unity_importer_returns_editor_script_with_readback() -> None:
    response = client.post("/api/v1/adapters/unity/importer.cs", json=payload())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/x-csharp")
    assert response.headers["content-disposition"] == (
        'attachment; filename="CutSceneAIGeneratedTimeline.cs"'
    )
    assert "CutSceneAI/Import Generated Timeline" in response.text
    assert "ExportReadbackInternal" in response.text
    assert "EngineReadback" in response.text


def test_export_unity_rejects_structurally_invalid_cir() -> None:
    value = payload()
    value["unexpected"] = True

    response = client.post("/api/v1/adapters/unity/export", json=value)

    assert response.status_code == 422
    assert response.json()["valid"] is False


def test_export_unity_rejects_domain_invalid_cir() -> None:
    value = payload()
    value["scenes"][0]["shots"][0]["purpose"] = "action"

    response = client.post("/api/v1/adapters/unity/export", json=value)

    assert response.status_code == 422
    assert response.json()["valid"] is False


def test_export_unity_reports_conversion_failure(monkeypatch) -> None:
    def fail(project):
        raise ValueError("synthetic Unity conversion failure")

    monkeypatch.setattr("app.api.unity.compile_project", fail)
    response = client.post("/api/v1/adapters/unity/export", json=payload())

    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "unity.adapter_conversion_failed"
