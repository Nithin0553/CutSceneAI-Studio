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
    monkeypatch.setattr(studio_module, "_COMMANDS_DIR", state / "bridge-commands")
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


def _client_with_service(service: StudioService) -> TestClient:
    app.dependency_overrides[get_studio_service] = lambda: service
    return TestClient(app)


def _project_payload() -> dict[str, object]:
    return _project().model_dump(mode="json")


def _required_bindings(record: dict[str, object]) -> list[dict[str, str]]:
    manifest = record["manifest"]
    assert isinstance(manifest, dict)
    assets = manifest["assets"]
    assert isinstance(assets, list)

    typed_assets = [item for item in assets if isinstance(item, dict)]
    mina = next(item for item in typed_assets if str(item["display_name"]).endswith("Mina"))
    arjun = next(item for item in typed_assets if str(item["display_name"]).endswith("Arjun"))
    return [
        {
            "cir_id": "mina",
            "project_object_id": str(mina["object_id"]),
        },
        {
            "cir_id": "arjun",
            "project_object_id": str(arjun["object_id"]),
        },
    ]


def test_api_exposes_capabilities_and_project_scan(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)
    client = _client_with_service(service)

    try:
        capabilities = client.get("/api/v1/studio/capabilities")
        connected = client.post(
            "/api/v1/studio/projects/connect",
            json={
                "engine": "unity",
                "project_path": str(_unity_project(tmp_path)),
                "display_name": "Demo Unity",
            },
        )
        project_id = connected.json()["project_id"]
        scanned = client.post(f"/api/v1/studio/projects/{project_id}/scan")
    finally:
        app.dependency_overrides.clear()

    assert capabilities.status_code == 200
    ids = {item["id"] for item in capabilities.json()["capabilities"]}
    assert {"project-connection", "engine-runner", "natural-language-editing"} <= ids
    assert connected.status_code == 200
    assert connected.json()["display_name"] == "Demo Unity"
    assert scanned.status_code == 200
    assert scanned.json()["manifest"]["discovery_mode"] == "filesystem_preflight"


def test_api_accepts_verified_engine_bridge_manifest(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)
    root = _unity_project(tmp_path)
    client = _client_with_service(service)

    try:
        connected = client.post(
            "/api/v1/studio/projects/connect",
            json={"engine": "unity", "project_path": str(root)},
        ).json()
        project_id = connected["project_id"]
        bridged = client.post(
            f"/api/v1/studio/projects/{project_id}/bridge-manifest",
            json={
                "engine_version": "6000.3.8f1",
                "adapter_version": "0.1.0",
                "current_scene": "Assets/Scenes/Main.unity",
                "fps": 24,
                "capabilities": ["humanoid", "timeline", "readback"],
                "assets": [
                    {
                        "object_id": "unity-global:mina",
                        "kind": "scene_actor",
                        "display_name": "Mina",
                        "engine_ref": "GlobalObjectId:minA",
                        "relative_path": "Assets/Scenes/Main.unity",
                        "verified": True,
                        "metadata": {"humanoid": True},
                    }
                ],
                "warnings": [],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert bridged.status_code == 200
    body = bridged.json()
    assert body["manifest"]["bridge_connected"] is True
    assert body["manifest"]["discovery_mode"] == "engine_bridge"
    assert body["manifest"]["fps"] == 24
    assert body["manifest"]["assets"][0]["verified"] is True


def test_api_runs_unity_binding_plan_realization_and_importer(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)
    client = _client_with_service(service)
    project = _project_payload()

    try:
        connected_response = client.post(
            "/api/v1/studio/projects/connect",
            json={"engine": "unity", "project_path": str(_unity_project(tmp_path))},
        )
        assert connected_response.status_code == 200
        connected = connected_response.json()
        project_id = connected["project_id"]
        bindings = _required_bindings(connected)

        options = client.post(
            "/api/v1/studio/bindings/options",
            json={"project_id": project_id, "project": project},
        )
        validated = client.post(
            "/api/v1/studio/bindings/validate",
            json={
                "project_id": project_id,
                "project": project,
                "bindings": bindings,
            },
        )
        performance = client.post(
            "/api/v1/studio/performance/plan",
            json={"project": project, "experiment_seed": 20260812},
        )
        realization = client.post(
            "/api/v1/studio/realization/plan",
            json={
                "project_id": project_id,
                "project": project,
                "bindings": bindings,
            },
        )
        importer = client.post(
            "/api/v1/studio/realization/importer",
            json={
                "project_id": project_id,
                "project": project,
                "bindings": bindings,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert options.status_code == 200
    assert len(options.json()["roles"]) >= 4
    assert validated.status_code == 200
    assert validated.json()["valid"] is True
    assert performance.status_code == 200
    assert performance.json()["fps"] == 24
    assert realization.status_code == 200
    assert realization.json()["ready"] is True
    assert realization.json()["engine"] == "unity"
    assert importer.status_code == 200
    assert importer.headers["content-type"].startswith("text/x-csharp")
    assert "CutSceneAI" in importer.text


def test_api_runs_unreal_binding_realization_and_importer(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)
    client = _client_with_service(service)
    project = _project_payload()

    try:
        connected_response = client.post(
            "/api/v1/studio/projects/connect",
            json={"engine": "unreal", "project_path": str(_unreal_project(tmp_path))},
        )
        assert connected_response.status_code == 200
        connected = connected_response.json()
        project_id = connected["project_id"]
        bindings = _required_bindings(connected)

        realization = client.post(
            "/api/v1/studio/realization/plan",
            json={
                "project_id": project_id,
                "project": project,
                "bindings": bindings,
            },
        )
        importer = client.post(
            "/api/v1/studio/realization/importer",
            json={
                "project_id": project_id,
                "project": project,
                "bindings": bindings,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert realization.status_code == 200
    assert realization.json()["ready"] is True
    assert realization.json()["engine"] == "unreal"
    assert importer.status_code == 200
    assert importer.headers["content-type"].startswith("text/x-python")
    assert "unreal" in importer.text.lower()


def test_realization_blocks_missing_and_incompatible_required_bindings(
    tmp_path: Path, monkeypatch
) -> None:
    service = _service(tmp_path, monkeypatch)
    root = _unity_project(tmp_path)
    (root / "Assets" / "Characters" / "NotAPrefab.fbx").write_bytes(b"fixture")
    record = service.connect_project(
        StudioProjectConnectRequest(
            engine=StudioEngine.UNITY,
            project_path=str(root),
        )
    )
    project = _project()

    missing = service.compile_realization(record.project_id, project, [])
    assert missing.ready is False
    assert "mina" in missing.blocking_issues[0]

    model = next(
        item for item in record.manifest.assets if item.engine_ref.endswith("/NotAPrefab.fbx")
    )
    arjun = next(
        item for item in record.manifest.assets if item.engine_ref.endswith("/Arjun.prefab")
    )
    incompatible = service.compile_realization(
        record.project_id,
        project,
        [
            StudioBindingSelection(cir_id="mina", project_object_id=model.object_id),
            StudioBindingSelection(cir_id="arjun", project_object_id=arjun.object_id),
        ],
    )
    assert incompatible.ready is False
    assert "Unity prefab" in incompatible.blocking_issues[0]


def test_binding_validation_rejects_unknown_project_object(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)
    record = service.connect_project(
        StudioProjectConnectRequest(
            engine=StudioEngine.UNITY,
            project_path=str(_unity_project(tmp_path)),
        )
    )

    try:
        service.validate_bindings(
            record.project_id,
            _project(),
            [
                StudioBindingSelection(
                    cir_id="mina",
                    project_object_id="does-not-exist",
                )
            ],
        )
    except ValueError as exc:
        assert "unknown project objects" in str(exc)
    else:
        raise AssertionError("Expected an unknown binding object to be rejected.")


def test_service_reports_unknown_and_invalid_projects(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)

    try:
        service.get_project("missing")
    except ValueError as exc:
        assert "Unknown Studio project" in str(exc)
    else:
        raise AssertionError("Expected unknown Studio project failure.")

    missing_path = tmp_path / "missing"
    try:
        service.connect_project(
            StudioProjectConnectRequest(
                engine=StudioEngine.UNITY,
                project_path=str(missing_path),
            )
        )
    except ValueError as exc:
        assert "does not exist" in str(exc)
    else:
        raise AssertionError("Expected missing project path failure.")

    invalid_unity = tmp_path / "InvalidUnity"
    invalid_unity.mkdir()
    try:
        service.connect_project(
            StudioProjectConnectRequest(
                engine=StudioEngine.UNITY,
                project_path=str(invalid_unity),
            )
        )
    except ValueError as exc:
        assert "not a Unity project" in str(exc)
    else:
        raise AssertionError("Expected invalid Unity project failure.")

    invalid_unreal = tmp_path / "InvalidUnreal"
    invalid_unreal.mkdir()
    try:
        service.connect_project(
            StudioProjectConnectRequest(
                engine=StudioEngine.UNREAL,
                project_path=str(invalid_unreal),
            )
        )
    except ValueError as exc:
        assert "exactly one .uproject" in str(exc)
    else:
        raise AssertionError("Expected invalid Unreal project failure.")


def test_corrupt_local_project_registry_fails_closed(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)
    studio_module._PROJECTS_FILE.write_text("{not-json", encoding="utf-8")

    assert service.list_projects() == []


def test_api_maps_unknown_project_errors_to_422(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)
    client = _client_with_service(service)
    project = _project_payload()

    try:
        scanned = client.post("/api/v1/studio/projects/missing/scan")
        options = client.post(
            "/api/v1/studio/bindings/options",
            json={"project_id": "missing", "project": project},
        )
        importer = client.post(
            "/api/v1/studio/realization/importer",
            json={
                "project_id": "missing",
                "project": project,
                "bindings": [],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert scanned.status_code == 422
    assert options.status_code == 422
    assert importer.status_code == 422



def test_unity_bridge_install_heartbeat_and_command_round_trip(
    tmp_path: Path, monkeypatch
) -> None:
    service = _service(tmp_path, monkeypatch)
    record = service.connect_project(
        StudioProjectConnectRequest(
            engine=StudioEngine.UNITY,
            project_path=str(_unity_project(tmp_path)),
        )
    )

    installed = service.install_bridge(record.project_id)
    project_root = Path(record.project_path)
    assert installed.engine is StudioEngine.UNITY
    assert (
        project_root / "Assets/Editor/CutSceneAI/CutSceneAIStudioBridge.cs"
    ).exists()
    config_path = project_root / "Assets/CutSceneAI/Bridge/cutsceneai-bridge.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config["project_id"] == record.project_id

    heartbeat = service.bridge_heartbeat(
        record.project_id,
        studio_module.StudioBridgeHeartbeatRequest(
            agent_id="test-unity-agent",
            engine_version="6000.3.8f1",
            adapter_version="0.1.0",
            current_scene="Assets/Scenes/Main.unity",
            fps=24,
            capabilities=["bridge:v0.1", "humanoid-scan"],
            assets=[
                {
                    "object_id": "global:mina",
                    "kind": "scene_actor",
                    "display_name": "Mina",
                    "engine_ref": "global:mina",
                    "relative_path": "Assets/Scenes/Main.unity",
                    "verified": True,
                    "metadata": {"humanoid": True, "humanoid_bone_count": 53},
                }
            ],
            warnings=[],
        ),
    )
    assert heartbeat.manifest.bridge_connected is True
    assert heartbeat.manifest.bridge_agent_id == "test-unity-agent"
    assert heartbeat.manifest.assets[0].verified is True

    queued = service.enqueue_bridge_command(
        record.project_id,
        studio_module.StudioBridgeCommandRequest(command="readback"),
    )
    polled = service.poll_bridge_command(record.project_id, "test-unity-agent")
    assert polled.command is not None
    assert polled.command.command_id == queued.command_id
    assert polled.command.status.value == "leased"

    completed = service.complete_bridge_command(
        record.project_id,
        queued.command_id,
        studio_module.StudioBridgeCommandResultRequest(
            agent_id="test-unity-agent",
            succeeded=True,
            result={"current_scene": "Assets/Scenes/Main.unity"},
        ),
    )
    assert completed.status.value == "succeeded"
    assert service.list_bridge_commands(record.project_id)[0].result["current_scene"].endswith(
        "Main.unity"
    )


def test_unreal_bridge_installs_as_project_plugin(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)
    record = service.connect_project(
        StudioProjectConnectRequest(
            engine=StudioEngine.UNREAL,
            project_path=str(_unreal_project(tmp_path)),
        )
    )

    installed = service.install_bridge(record.project_id)
    root = Path(record.project_path) / "Plugins" / "CutSceneAIStudioBridge"
    assert installed.engine is StudioEngine.UNREAL
    assert (root / "CutSceneAIStudioBridge.uplugin").exists()
    assert (root / "Content/Python/init_unreal.py").exists()
    assert (root / "Content/Python/cutsceneai_studio_bridge.py").exists()
    config = json.loads(
        (root / "Content/Python/cutsceneai-bridge.json").read_text(encoding="utf-8")
    )
    assert config["project_id"] == record.project_id


def test_bridge_command_rejects_wrong_agent_completion(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)
    record = service.connect_project(
        StudioProjectConnectRequest(
            engine=StudioEngine.UNITY,
            project_path=str(_unity_project(tmp_path)),
        )
    )
    queued = service.enqueue_bridge_command(
        record.project_id,
        studio_module.StudioBridgeCommandRequest(command="save"),
    )
    service.poll_bridge_command(record.project_id, "agent-a")

    try:
        service.complete_bridge_command(
            record.project_id,
            queued.command_id,
            studio_module.StudioBridgeCommandResultRequest(
                agent_id="agent-b",
                succeeded=True,
            ),
        )
    except ValueError as exc:
        assert "different engine agent" in str(exc)
    else:
        raise AssertionError("Expected bridge lease ownership to be enforced.")
