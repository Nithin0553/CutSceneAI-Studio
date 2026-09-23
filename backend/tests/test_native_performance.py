import asyncio
import base64
import json
from pathlib import Path
import re
import sys

from cutsceneai_cir import Project
from cutsceneai_performance import ARKIT_52_BLENDSHAPE_NAMES

from app.models.performance_runtime import PerformanceGenerateRequest
from app.models.studio import (
    StudioBindingSelection,
    StudioBridgeHeartbeatRequest,
    StudioEngine,
    StudioProjectConnectRequest,
)
from app.services.native_performance import NativePerformanceRealizer
from app.services.performance_executor import StudioPerformanceExecutor
from app.services.studio import StudioService
import app.services.studio as studio_module


FIXTURE = Path(__file__).resolve().parents[2] / "cir" / "examples" / "office-dialogue.cir.json"


def _project_without_dialogue() -> Project:
    payload = Project.model_validate_json(FIXTURE.read_text(encoding="utf-8")).model_dump(
        mode="json"
    )
    for scene in payload["scenes"]:
        for beat in scene["beats"]:
            for performance in beat["performances"]:
                performance["dialogue"] = None
                performance["facial"]["lip_sync"] = False
    return Project.model_validate(payload)


def _service(tmp_path: Path, monkeypatch) -> StudioService:
    state = tmp_path / "state"
    monkeypatch.setattr(studio_module, "_STATE_DIR", state)
    monkeypatch.setattr(studio_module, "_PROJECTS_FILE", state / "projects.json")
    monkeypatch.setattr(studio_module, "_COMMANDS_DIR", state / "bridge-commands")
    return StudioService()


def _body_provider(path: Path) -> None:
    path.write_text(
        """
import json
import re
import sys

payload = json.loads(sys.stdin.read())
request = payload["request"]
frame_count = request["end_frame"] - request["start_frame"]
match = re.search(r"at (\\d+) fps", request["prompt"])
fps = int(match.group(1)) if match else 24
identity = {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}
samples = [
    {
        "frame_index": frame,
        "root_translation": {"x": 0.0, "y": 0.0, "z": -0.01 * frame},
        "joint_rotations": [identity for _ in range(22)],
    }
    for frame in range(frame_count)
]
response = {
    "request_semantic_id": request["semantic_id"],
    "provider": request["provider"],
    "model": request["model"],
    "model_revision": request["model_revision"],
    "prompt_sha256": request["prompt_sha256"],
    "configuration_sha256": request["configuration_sha256"],
    "seed": request["seed"],
    "generated_at_inference": True,
    "retrieved_pre_authored_clip": False,
    "deterministic_algorithms": True,
    "artifact": {
        "fps": fps,
        "frame_count": frame_count,
        "samples": samples,
    },
}
sys.stdout.write(json.dumps(response))
""".strip()
        + "\n",
        encoding="utf-8",
    )


def _configure_provider(tmp_path: Path, monkeypatch) -> None:
    script = tmp_path / "body_provider.py"
    _body_provider(script)
    monkeypatch.setenv(
        "CUTSCENEAI_BODY_PROVIDER_COMMAND",
        json.dumps([sys.executable, str(script)]),
    )
    monkeypatch.setenv("CUTSCENEAI_BODY_PROVIDER", "fixture-motion")
    monkeypatch.setenv("CUTSCENEAI_BODY_MODEL", "canonical-fixture")
    monkeypatch.setenv("CUTSCENEAI_BODY_MODEL_REVISION", "test-r1")


def _generate_run(tmp_path: Path, monkeypatch) -> tuple[StudioPerformanceExecutor, object]:
    _configure_provider(tmp_path, monkeypatch)
    executor = StudioPerformanceExecutor(run_root=tmp_path / "runs")
    record = asyncio.run(
        executor.generate(
            PerformanceGenerateRequest(
                project=_project_without_dialogue(),
                experiment_seed=20260812,
            )
        )
    )
    assert record.status.value == "succeeded"
    return executor, record


def _unity_project(tmp_path: Path) -> Path:
    root = tmp_path / "UnityProject"
    (root / "Assets" / "Characters").mkdir(parents=True)
    (root / "Assets" / "Scenes").mkdir(parents=True)
    (root / "ProjectSettings").mkdir()
    (root / "Packages").mkdir()
    for name in ("Mina", "Arjun"):
        (root / "Assets" / "Characters" / f"{name}.prefab").write_text(
            "%YAML",
            encoding="utf-8",
        )
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
    for name in ("Mina", "Arjun"):
        (root / "Content" / "Characters" / f"SKM_{name}.uasset").write_bytes(b"fixture")
    (root / "Content" / "Maps" / "Main.umap").write_bytes(b"fixture")
    (root / "CutSceneAIStudio.uproject").write_text(
        json.dumps({"EngineAssociation": "5.8"}),
        encoding="utf-8",
    )
    return root


def test_verified_performance_run_stages_native_unity_importer(
    tmp_path: Path,
    monkeypatch,
) -> None:
    executor, run = _generate_run(tmp_path, monkeypatch)
    studio = _service(tmp_path, monkeypatch)
    record = studio.connect_project(
        StudioProjectConnectRequest(
            engine=StudioEngine.UNITY,
            project_path=str(_unity_project(tmp_path)),
        )
    )

    assets = []
    selections = []
    for name in ("Mina", "Arjun"):
        source_id = name.lower()
        engine_ref = f"Assets/Characters/{name}.prefab"
        object_id = f"verified:{source_id}"
        assets.append(
            {
                "object_id": object_id,
                "kind": "prefab",
                "display_name": name,
                "engine_ref": engine_ref,
                "relative_path": engine_ref,
                "verified": True,
                "metadata": {
                    "source": "engine_bridge",
                    "humanoid": True,
                    "animator_path": "Armature",
                    "facial_renderer_path": "Geometry/Face",
                    "blendshape_names": list(ARKIT_52_BLENDSHAPE_NAMES),
                },
            }
        )
        selections.append(
            StudioBindingSelection(
                cir_id=source_id,
                project_object_id=object_id,
            )
        )

    contract_ref = "Assets/Props/Contract.prefab"
    contract_path = Path(record.project_path) / contract_ref
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_text("%YAML", encoding="utf-8")
    assets.append(
        {
            "object_id": "verified:contract",
            "kind": "prefab",
            "display_name": "Contract",
            "engine_ref": contract_ref,
            "relative_path": contract_ref,
            "verified": True,
            "metadata": {"source": "engine_bridge"},
        }
    )
    selections.append(
        StudioBindingSelection(
            cir_id="contract",
            project_object_id="verified:contract",
        )
    )

    studio.bridge_heartbeat(
        record.project_id,
        StudioBridgeHeartbeatRequest(
            agent_id="unity-agent",
            engine_version="6000.3.8f1",
            adapter_version="0.1.0",
            current_scene="Assets/Scenes/Main.unity",
            fps=24,
            capabilities=["bridge:v0.1", "humanoid-scan", "blendshape-scan"],
            assets=assets,
            warnings=[],
        ),
    )

    command = NativePerformanceRealizer(
        studio=studio,
        performance=executor,
    ).realize(
        run_id=run.run_id,
        project_id=record.project_id,
        project=_project_without_dialogue(),
        bindings=selections,
    )

    assert command.command.value == "run_importer"
    assert command.payload["performance_run_id"] == run.run_id
    importer = (
        Path(record.project_path)
        / "Assets/Editor/CutSceneAI/Generated/CutSceneAIGeneratedPerformance.cs"
    )
    assert importer.exists()
    source = importer.read_text(encoding="utf-8")
    assert "CutSceneAIGeneratedPerformance" in source
    assert 'version.StartsWith("6000.3"' in source
    assert "foreach (ActorPlan actorPlan in plan.sequences.Single().actors)" in source
    assert "GameObject.CreatePrimitive(primitive)" in source

    plan_match = re.search(r'private const string PlanBase64 = "([^"]+)";', source)
    assert plan_match is not None
    embedded_plan = json.loads(base64.b64decode(plan_match.group(1)).decode("utf-8"))
    plan_actors = {
        item["source_entity_id"]: item
        for item in embedded_plan["sequences"][0]["actors"]
    }
    assert plan_actors["contract"]["prefab_path"] == contract_ref
    assert plan_actors["contract"]["placeholder"] is False
    assert plan_actors["conference-table"]["prefab_path"] is None
    assert plan_actors["conference-table"]["placeholder"] is True
    assert plan_actors["conference-table"]["placeholder_primitive"] == "cube"


def test_unity_native_realization_uses_authored_scene_objects(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _configure_provider(tmp_path, monkeypatch)
    executor = StudioPerformanceExecutor(run_root=tmp_path / "runs")
    studio = _service(tmp_path, monkeypatch)
    record = studio.connect_project(
        StudioProjectConnectRequest(
            engine=StudioEngine.UNITY,
            project_path=str(_unity_project(tmp_path)),
        )
    )

    assets = []
    scene_objects = []
    selections = []
    for index, name in enumerate(("Mina", "Arjun")):
        source_id = name.lower()
        engine_ref = f"Assets/Characters/{name}.prefab"
        assets.append(
            {
                "object_id": f"verified:{source_id}",
                "kind": "prefab",
                "display_name": name,
                "engine_ref": engine_ref,
                "relative_path": engine_ref,
                "verified": True,
                "metadata": {
                    "source": "engine_bridge",
                    "humanoid": True,
                    "animator_path": "Armature",
                    "facial_renderer_path": "Geometry/Face",
                    "blendshape_names": list(ARKIT_52_BLENDSHAPE_NAMES),
                },
            }
        )
        scene_object_id = f"scene:{source_id}"
        scene_objects.append(
            {
                "object_id": scene_object_id,
                "display_name": name,
                "hierarchy_path": f"HallwayEnvironment/Characters/{name}",
                "parent_object_id": "scene:characters",
                "kind": "character",
                "active": True,
                "is_static": False,
                "tag": "Untagged",
                "layer": "Default",
                "prefab_asset_path": engine_ref,
                "transform": {
                    "position_m": {
                        "x": float(index * 2),
                        "y": 0.0,
                        "z": -5.0,
                    },
                    "rotation": {
                        "x": 0.0,
                        "y": 0.0,
                        "z": 0.0,
                        "w": 1.0,
                    },
                    "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
                },
                "bounds": None,
                "components": ["UnityEngine.Transform", "UnityEngine.Animator"],
            }
        )
        selections.append(
            StudioBindingSelection(
                cir_id=source_id,
                project_object_id=scene_object_id,
            )
        )

    studio.bridge_heartbeat(
        record.project_id,
        StudioBridgeHeartbeatRequest(
            agent_id="unity-scene-agent",
            engine_version="6000.3.8f1",
            adapter_version="0.2.0",
            current_scene="Assets/Scenes/Main.unity",
            fps=24,
            capabilities=["bridge:v0.1", "scene-context:v0.1", "humanoid-scan"],
            assets=assets,
            scene_snapshot={
                "snapshot_version": "0.1.0",
                "scene_ref": "Assets/Scenes/Main.unity",
                "coordinate_space": "cutsceneai-rh-yup-negative-z-forward",
                "distance_unit": "meter",
                "objects": scene_objects,
            },
            warnings=[],
        ),
    )

    source_project = _project_without_dialogue()
    conditioned_project = studio.scene_conditioned_project(
        record.project_id,
        source_project,
        selections,
    )
    run = asyncio.run(
        executor.generate(
            PerformanceGenerateRequest(
                project=conditioned_project,
                experiment_seed=20260812,
            )
        )
    )
    assert run.status.value == "succeeded"

    command = NativePerformanceRealizer(
        studio=studio,
        performance=executor,
    ).realize(
        run_id=run.run_id,
        project_id=record.project_id,
        project=source_project,
        bindings=selections,
    )

    importer = (
        Path(record.project_path)
        / "Assets/Editor/CutSceneAI/Generated/CutSceneAIGeneratedPerformance.cs"
    )
    source = importer.read_text(encoding="utf-8")
    target_match = re.search(r'private const string TargetBase64 = "([^"]+)";', source)
    assert target_match is not None
    embedded_target = json.loads(
        base64.b64decode(target_match.group(1)).decode("utf-8")
    )

    assert embedded_target["source_scene_asset_path"] == "Assets/Scenes/Main.unity"
    assert {
        item["source_entity_id"]: item["hierarchy_path"]
        for item in embedded_target["scene_bindings"]
    } == {
        "mina": "HallwayEnvironment/Characters/Mina",
        "arjun": "HallwayEnvironment/Characters/Arjun",
    }
    assert "AssetDatabase.CopyAsset" in source
    assert "SceneObjectAtPath" in source
    assert command.command.value == "run_importer"


def test_verified_performance_run_stages_native_unreal_importer(
    tmp_path: Path,
    monkeypatch,
) -> None:
    executor, run = _generate_run(tmp_path, monkeypatch)
    studio = _service(tmp_path, monkeypatch)
    record = studio.connect_project(
        StudioProjectConnectRequest(
            engine=StudioEngine.UNREAL,
            project_path=str(_unreal_project(tmp_path)),
        )
    )

    assets = []
    selections = []
    for name in ("Mina", "Arjun"):
        source_id = name.lower()
        mesh_ref = f"/Game/Characters/SKM_{name}.SKM_{name}"
        object_id = f"verified:{source_id}"
        assets.append(
            {
                "object_id": object_id,
                "kind": "character_asset",
                "display_name": f"SKM_{name}",
                "engine_ref": mesh_ref,
                "relative_path": mesh_ref,
                "verified": True,
                "metadata": {
                    "source": "engine_bridge",
                    "asset_type": "skeletal_mesh",
                    "skeleton": "/Game/Characters/SK_Mannequin_Skeleton",
                    "morph_target_names": list(ARKIT_52_BLENDSHAPE_NAMES),
                },
            }
        )
        selections.append(
            StudioBindingSelection(
                cir_id=source_id,
                project_object_id=object_id,
            )
        )

    studio.bridge_heartbeat(
        record.project_id,
        StudioBridgeHeartbeatRequest(
            agent_id="unreal-agent",
            engine_version="5.8.2-CL-56702186",
            adapter_version="0.1.0",
            current_scene="/Game/Maps/Main.Main",
            fps=24,
            capabilities=["bridge:v0.1", "skeletal-mesh-assets", "sequencer"],
            assets=assets,
            warnings=[],
        ),
    )

    command = NativePerformanceRealizer(
        studio=studio,
        performance=executor,
    ).realize(
        run_id=run.run_id,
        project_id=record.project_id,
        project=_project_without_dialogue(),
        bindings=selections,
    )

    assert command.command.value == "run_importer"
    importer = Path(record.project_path) / str(command.payload["importer_path"])
    assert importer.exists()
    source = importer.read_text(encoding="utf-8")
    assert "Generated by CutSceneAI Unreal Adapter" in source
    assert "Validated Unreal Engine line is 5.8.x" in source


def test_native_realization_declares_facial_degradation_for_body_only_targets(
    tmp_path: Path,
    monkeypatch,
) -> None:
    executor, run = _generate_run(tmp_path, monkeypatch)
    project = _project_without_dialogue()

    unity = _service(tmp_path / "unity-state", monkeypatch)
    unity_record = unity.connect_project(
        StudioProjectConnectRequest(
            engine=StudioEngine.UNITY,
            project_path=str(_unity_project(tmp_path / "unity-project")),
        )
    )
    unity_assets = []
    unity_bindings = []
    for name in ("Mina", "Arjun"):
        source_id = name.lower()
        engine_ref = f"Assets/Characters/{name}.prefab"
        object_id = f"unity-body-only:{source_id}"
        unity_assets.append(
            {
                "object_id": object_id,
                "kind": "prefab",
                "display_name": name,
                "engine_ref": engine_ref,
                "relative_path": engine_ref,
                "verified": True,
                "metadata": {
                    "source": "engine_bridge",
                    "humanoid": True,
                    "animator_path": "Armature",
                    "facial_renderer_path": "",
                    "blendshape_names": [],
                },
            }
        )
        unity_bindings.append(StudioBindingSelection(cir_id=source_id, project_object_id=object_id))
    unity.bridge_heartbeat(
        unity_record.project_id,
        StudioBridgeHeartbeatRequest(
            agent_id="unity-body-agent",
            engine_version="6000.3.8f1",
            adapter_version="0.1.0",
            current_scene="Assets/Scenes/Main.unity",
            fps=24,
            capabilities=["bridge:v0.1", "humanoid-scan"],
            assets=unity_assets,
            warnings=[],
        ),
    )
    unity_command = NativePerformanceRealizer(
        studio=unity,
        performance=executor,
    ).realize(
        run_id=run.run_id,
        project_id=unity_record.project_id,
        project=project,
        bindings=unity_bindings,
    )
    assert set(unity_command.payload["omitted_facial_actor_binding_ids"]) == {
        "actor:mina",
        "actor:arjun",
    }
    unity_source = (
        Path(unity_record.project_path)
        / "Assets/Editor/CutSceneAI/Generated/CutSceneAIGeneratedPerformance.cs"
    ).read_text(encoding="utf-8")
    match = re.search(r'private const string TargetBase64 = "([^"]+)";', unity_source)
    assert match is not None
    embedded_target = json.loads(base64.b64decode(match.group(1)).decode("utf-8"))
    assert set(embedded_target["omitted_facial_actor_binding_ids"]) == {
        "actor:mina",
        "actor:arjun",
    }

    unreal = _service(tmp_path / "unreal-state", monkeypatch)
    unreal_record = unreal.connect_project(
        StudioProjectConnectRequest(
            engine=StudioEngine.UNREAL,
            project_path=str(_unreal_project(tmp_path / "unreal-project")),
        )
    )
    unreal_assets = []
    unreal_bindings = []
    for name in ("Mina", "Arjun"):
        source_id = name.lower()
        engine_ref = f"/Game/Characters/SKM_{name}.SKM_{name}"
        object_id = f"unreal-body-only:{source_id}"
        unreal_assets.append(
            {
                "object_id": object_id,
                "kind": "character_asset",
                "display_name": f"SKM_{name}",
                "engine_ref": engine_ref,
                "relative_path": engine_ref,
                "verified": True,
                "metadata": {
                    "source": "engine_bridge",
                    "asset_type": "skeletal_mesh",
                    "skeleton": "/Game/Characters/SK_Mannequin_Skeleton",
                    "morph_target_names": [],
                },
            }
        )
        unreal_bindings.append(
            StudioBindingSelection(cir_id=source_id, project_object_id=object_id)
        )
    unreal.bridge_heartbeat(
        unreal_record.project_id,
        StudioBridgeHeartbeatRequest(
            agent_id="unreal-body-agent",
            engine_version="5.8.2-CL-56702186",
            adapter_version="0.1.0",
            current_scene="/Game/Maps/Main.Main",
            fps=24,
            capabilities=["bridge:v0.1", "skeletal-mesh-assets", "sequencer"],
            assets=unreal_assets,
            warnings=[],
        ),
    )
    unreal_command = NativePerformanceRealizer(
        studio=unreal,
        performance=executor,
    ).realize(
        run_id=run.run_id,
        project_id=unreal_record.project_id,
        project=project,
        bindings=unreal_bindings,
    )
    assert set(unreal_command.payload["omitted_facial_actor_binding_ids"]) == {
        "actor:mina",
        "actor:arjun",
    }
    unreal_source = (
        Path(unreal_record.project_path) / str(unreal_command.payload["importer_path"])
    ).read_text(encoding="utf-8")
    assert "EXPECTED_MORPHS" in unreal_source
    assert "else tuple()" in unreal_source
