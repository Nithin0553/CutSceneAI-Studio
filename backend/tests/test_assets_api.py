import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


ROOT = Path(__file__).resolve().parents[2]
CIR_EXAMPLE = ROOT / "cir" / "examples" / "office-dialogue.cir.json"
ASSET_INDEX_EXAMPLE = ROOT / "assets" / "examples" / "unreal-project.asset-index.json"
client = TestClient(app)


def request_payload() -> dict:
    return {
        "project": json.loads(CIR_EXAMPLE.read_text(encoding="utf-8")),
        "asset_index": json.loads(ASSET_INDEX_EXAMPLE.read_text(encoding="utf-8")),
    }


def test_resolve_assets_returns_traceable_deterministic_plan() -> None:
    value = request_payload()

    first = client.post("/api/v1/assets/resolve", json=value)
    second = client.post("/api/v1/assets/resolve", json=value)

    assert first.status_code == 200
    assert first.json() == second.json()
    body = first.json()
    assert body["resolution_version"] == "0.1.0"
    assert body["project_id"] == "office-dialogue"
    assert body["asset_index_id"] == "cutsceneai-fixture-assets"
    assert len(body["asset_index_sha256"]) == 64
    assert len(body["resolutions"]) == 3
    assert body["warnings"] == []
    by_source = {(item["source_kind"], item["source_id"]): item for item in body["resolutions"]}
    assert by_source[("environment_object", "contract")]["asset_id"] == ("office-contract")
    assert (
        by_source[("environment_object", "conference-table")]["asset_id"]
        == "office-conference-table"
    )
    assert by_source[("scene_set", "scene-meeting")]["asset_id"] == ("office-conference-room")
    assert all(item["status"] == "matched" for item in body["resolutions"])


def test_resolve_assets_reports_structural_contract_errors() -> None:
    value = request_payload()
    del value["asset_index"]["id"]

    response = client.post("/api/v1/assets/resolve", json=value)

    assert response.status_code == 422
    assert response.json()["valid"] is False
    assert response.json()["errors"][0]["path"] == "asset_index.id"
    assert response.json()["errors"][0]["code"].startswith("structural.")


def test_resolve_assets_reports_asset_index_domain_errors() -> None:
    value = request_payload()
    duplicate = dict(value["asset_index"]["assets"][0])
    value["asset_index"]["assets"].append(duplicate)

    response = client.post("/api/v1/assets/resolve", json=value)

    assert response.status_code == 422
    errors = response.json()["errors"]
    assert {item["code"] for item in errors} == {
        "duplicate_asset_id",
        "duplicate_asset_uri",
    }
    assert all(item["path"].startswith("asset_index.assets[7]") for item in errors)


def test_resolve_assets_reports_cir_domain_errors_under_project_path() -> None:
    value = request_payload()
    value["project"]["scenes"][0]["shots"][0]["purpose"] = "action"

    response = client.post("/api/v1/assets/resolve", json=value)

    assert response.status_code == 422
    problem = next(
        item for item in response.json()["errors"] if item["code"] == "missing_establishing_shot"
    )
    assert problem["path"].startswith("project.")
