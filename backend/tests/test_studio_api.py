import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.studio import get_studio_service
from app.main import app
from app.models.studio import (
    StudioBindingSelection,
    StudioEngine,
    StudioProjectConnectRequest,
)
from app.services.studio import StudioService
import app.services.studio as studio_module
from cutsceneai_cir import Project


FIXTURE = Path(__file__).resolve().parents[2] / "cir" / "examples" / "office-dialogue.cir.json"


def _project() -> Project:
    return Project.model_validate_json(FIXTURE.read_text(encoding="utf-8"))


def _service(tmp_path: Path, monkeypatch) -> StudioService:
    state = tmp_path / "state"
    monkeypatch.setattr(studio_module, "_STATE_DIR", state)
    monkeypatch.setattr(studio_module, "_PROJECTS_FILE", state / "projects.json")
    return StudioService()


def _unity_project(tmp_path: Path) -> Path:
    root = tmp_path / "UnityProject"
    (root / "Assets" / "Characters").mkdir(parents=True)
    (root / "Assets" / "Scenes").mkdir(parents=True)
    (root / "ProjectSettings").mkdir()
    (root / "Packages").mkdir()
    (root / "Assets" / "Characters" / "Mina.prefab").write_text("%YAML", encoding="utf-8")
    (root / "Assets" / "Characters" / "Arjun.prefab").write_text("%YAML", encoding="utf-8")
    (root / "Assets" / "Scenes" / "Main.unity").write_text("%YAML", encoding="utf-8")
    (root / "ProjectSettings" / "ProjectVersion.txt").write_text(
        "m_EditorVersion: 6000.3.8f1\n",
        encoding="utf-8",
    )
    (root / "Packages" / "manifest.json").write_text(
        json.dumps({"dependencies": {"com.unity.timeline": "1.8.12"}}),
        encoding="utf-8",
    )
    return root


def _unreal_project(tmp_path: Path) -> Path:
    root = tmp_path / "UnrealProject"
    (root / "Content" / "Characters").mkdir(parents=True)
    (root / "Content" / "Maps").mkdir(parents=True)
    (root / "Content" / "Characters" / "SKM_Mina.uasset").write_bytes(b"fixture")
    (root / "Content" / "Characters" / "SKM_Arjun.uasset").write_bytes(b"fixture")
    (root / "Content" / "Maps" / "Main.umap").write_bytes(b"fixture")
    (root / "CutSceneAIStudio.uproject").write_text(
        json.dumps(
            {
                "EngineAssociation": "5.8",
                "Plugins": [
                    {"Name": "PythonScriptPlugin", "Enabled": True},
                    {"Name": "SequencerScripting", "Enabled": True},
                ],
            }
        ),
        encoding="utf-8",
    )
    return root


def test_capabilities_report_missing_v3_execution_gates(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)

    result = service.capabilities()
    by_id = {item.id: item for item in result.capabilities}

    assert by_id["project-connection"].status == "implemented"
    assert by_id["director-cir"].status == "implemented"
    assert by_id["performance-inference"].status == "missing"
    assert by_id["performance-inference"].blocking is True
    assert by_id["engine-runner"].status == "missing"
    assert by_id["natural-language-editing"].status == "missing"


def test_unity_connect_uses_scoped_filesystem_preflight(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)
    root = _unity_project(tmp_path)

    record = service.connect_project(
        StudioProjectConnectRequest(
            engine=StudioEngine.UNITY,
            project_path=str(root),
        )
    )

    assert record.engine is StudioEngine.UNITY
    assert record.manifest.engine_version == "6000.3.8f1"
    assert record.manifest.discovery_mode == "filesystem_preflight"
    assert record.manifest.bridge_connected is False
    refs = {item.engine_ref for item in record.manifest.assets}
    assert "Assets/Characters/Mina.prefab" in refs
    assert "Assets/Characters/Arjun.prefab" in refs
    assert any("engine bridge" in warning.lower() for warning in record.manifest.warnings)


def test_unreal_connect_discovers_project_assets_without_claiming_verification(
    tmp_path: Path, monkeypatch
) -> None:
    service = _service(tmp_path, monkeypatch)
    root = _unreal_project(tmp_path)

    record = service.connect_project(
        StudioProjectConnectRequest(
            engine=StudioEngine.UNREAL,
            project_path=str(root),
        )
    )

    assert record.manifest.engine_version == "5.8"
    mina = next(item for item in record.manifest.assets if item.display_name == "SKM_Mina")
    assert mina.engine_ref == "/Game/Characters/SKM_Mina.SKM_Mina"
    assert mina.kind == "character_asset"
    assert mina.verified is False
    assert "plugin:PythonScriptPlugin" in record.manifest.capabilities


def test_binding_options_and_validation_use_connected_project_objects(
    tmp_path: Path, monkeypatch
) -> None:
    service = _service(tmp_path, monkeypatch)
    record = service.connect_project(
        StudioProjectConnectRequest(
            engine=StudioEngine.UNITY,
            project_path=str(_unity_project(tmp_path)),
        )
    )
    project = _project()

    options = service.binding_options(record.project_id, project)
    roles = {item.cir_id: item for item in options.roles}

    assert {"mina", "arjun", "contract", "conference-table"} <= set(roles)
    assert roles["mina"].required is True
    assert roles["contract"].required is False
    assert roles["mina"].candidates

    mina = next(item for item in record.manifest.assets if item.engine_ref.endswith("/Mina.prefab"))
    arjun = next(
        item for item in record.manifest.assets if item.engine_ref.endswith("/Arjun.prefab")
    )
    manifest = service.validate_bindings(
        record.project_id,
        project,
        [
            StudioBindingSelection(cir_id="mina", project_object_id=mina.object_id),
            StudioBindingSelection(cir_id="arjun", project_object_id=arjun.object_id),
        ],
    )

    assert manifest.valid is True
    assert manifest.unresolved_required_ids == []
    assert set(manifest.unresolved_optional_ids) == {"conference-table", "contract"}


def test_performance_plan_compiles_deterministic_requests(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)

    result = service.performance_plan(_project(), 20260812)

    assert result["project_id"] == "office-dialogue"
    assert result["fps"] == 24
    assert result["duration_frames"] == 432
    assert len(result["body_requests"]) == 4
    assert len(result["facial_requests"]) == 4
    assert len(result["camera_requests"]) == 4


def test_studio_api_connects_and_lists_project(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)
    root = _unity_project(tmp_path)
    app.dependency_overrides[get_studio_service] = lambda: service

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/studio/projects/connect",
            json={"engine": "unity", "project_path": str(root)},
        )
        listed = client.get("/api/v1/studio/projects")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["engine"] == "unity"
