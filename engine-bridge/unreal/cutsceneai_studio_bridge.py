# CutSceneAI Studio Bridge v0.1.0
# Research-grade local editor bridge. Only an explicit command allowlist is executed.
from __future__ import annotations

import json
import os
import runpy
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import unreal

BRIDGE_VERSION = "0.1.0"
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "cutsceneai-bridge.json")
_state: dict[str, Any] = {
    "config": None,
    "agent_id": None,
    "last_heartbeat": 0.0,
    "last_poll": 0.0,
    "ticker_handle": None,
    "request_in_flight": False,
}


def _load_config() -> dict[str, Any]:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as handle:
        config = json.load(handle)
    if not config.get("project_id") or not config.get("backend_url"):
        raise RuntimeError("CutSceneAI bridge configuration is incomplete.")
    config["backend_url"] = str(config["backend_url"]).rstrip("/")
    return config


def _request(method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
    body = None
    headers: dict[str, str] = {}
    if payload is not None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=1.5) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw) if raw else None


def _current_world() -> Any:
    try:
        subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        return subsystem.get_editor_world()
    except Exception:
        return None


def _actors() -> list[Any]:
    try:
        subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        return list(subsystem.get_all_level_actors())
    except Exception:
        return []


def _actor_record(actor: Any) -> dict[str, Any]:
    class_name = actor.get_class().get_name()
    kind = "scene_actor"
    if "Camera" in class_name:
        kind = "camera"
    elif "SkeletalMesh" in class_name or "Character" in class_name:
        kind = "scene_actor"

    path_name = actor.get_path_name()
    metadata: dict[str, Any] = {
        "class_name": class_name,
        "asset_type": kind,
        "humanoid": "SkeletalMesh" in class_name or "Character" in class_name,
        "blendshape_count": 0,
    }

    try:
        components = actor.get_components_by_class(unreal.SkeletalMeshComponent)
        if components:
            mesh = components[0].get_editor_property("skeletal_mesh")
            if mesh is not None:
                metadata["skeletal_mesh"] = mesh.get_path_name()
                metadata["skeleton"] = (
                    mesh.get_editor_property("skeleton").get_path_name()
                    if mesh.get_editor_property("skeleton") is not None
                    else ""
                )
    except Exception:
        pass

    return {
        "object_id": path_name,
        "kind": kind,
        "display_name": actor.get_actor_label(),
        "engine_ref": path_name,
        "relative_path": path_name,
        "verified": True,
        "metadata": metadata,
    }


def _manifest() -> dict[str, Any]:
    world = _current_world()
    actors = _actors()
    world_path = world.get_path_name() if world is not None else ""
    records = [_actor_record(actor) for actor in actors[:500]]

    meshes: dict[str, dict[str, Any]] = {}
    for record in records:
        mesh_path = str(record.get("metadata", {}).get("skeletal_mesh") or "")
        if not mesh_path or mesh_path in meshes:
            continue
        meshes[mesh_path] = {
            "object_id": "skeletal-mesh:" + mesh_path,
            "kind": "character_asset",
            "display_name": mesh_path.rsplit("/", 1)[-1].split(".", 1)[0],
            "engine_ref": mesh_path,
            "relative_path": mesh_path,
            "verified": True,
            "metadata": {
                "source": "engine_bridge",
                "asset_type": "skeletal_mesh",
                "skeletal_mesh": mesh_path,
                "skeleton": record.get("metadata", {}).get("skeleton", ""),
            },
        }

    return {
        "agent_id": _state["agent_id"],
        "engine_version": unreal.SystemLibrary.get_engine_version(),
        "adapter_version": BRIDGE_VERSION,
        "current_scene": world_path,
        "fps": 24,
        "capabilities": [
            "bridge:v0.1",
            "verified-project-objects",
            "level-actors",
            "skeletal-mesh-assets",
            "sequencer",
            "editor-command-queue",
            "readback",
        ],
        "assets": records + list(meshes.values()),
        "warnings": [],
    }


def _heartbeat(force: bool = False) -> None:
    config = _state["config"]
    now = time.monotonic()
    if not force and now - float(_state["last_heartbeat"]) < 10.0:
        return
    url = (
        config["backend_url"]
        + "/api/v1/studio/projects/"
        + urllib.parse.quote(config["project_id"], safe="")
        + "/bridge/heartbeat"
    )
    _request("POST", url, _manifest())
    _state["last_heartbeat"] = now


def _readback(message: str) -> dict[str, Any]:
    actors = _actors()
    world = _current_world()
    selected: list[str] = []
    try:
        subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        selected = [actor.get_actor_label() for actor in subsystem.get_selected_level_actors()]
    except Exception:
        pass
    return {
        "current_scene": world.get_path_name() if world is not None else "",
        "is_playing": False,
        "scene_actor_count": len(actors),
        "playable_director_count": 0,
        "selected_object": ", ".join(selected),
        "message": message,
    }


def _focus_preview() -> dict[str, Any]:
    sequence_actors = [
        actor for actor in _actors() if "LevelSequenceActor" in actor.get_class().get_name()
    ]
    if not sequence_actors:
        raise RuntimeError("No LevelSequenceActor exists in the current level.")
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    subsystem.set_selected_level_actors([sequence_actors[0]])
    return _readback("Level Sequence actor selected in the editor.")


def _execute(command: dict[str, Any]) -> tuple[bool, dict[str, Any], str | None]:
    name = command["command"]
    try:
        if name == "refresh_manifest":
            _heartbeat(force=True)
            result = _readback("Manifest refreshed.")
        elif name == "focus_preview":
            result = _focus_preview()
        elif name == "save":
            unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
            result = _readback("Dirty Unreal packages saved.")
        elif name == "readback":
            result = _readback("Unreal editor readback captured.")
        elif name == "run_importer":
            payload = command.get("payload") or {}
            relative = str(payload.get("importer_path") or "")
            expected = "Saved/CutSceneAI/Generated/cutsceneai-unreal-import.py"
            if relative.replace("\\", "/") != expected:
                raise RuntimeError(
                    "Bridge refused an importer outside the managed CutSceneAI path."
                )
            project_root = os.path.realpath(unreal.Paths.project_dir())
            importer = os.path.realpath(os.path.join(project_root, relative))
            if os.path.commonpath([project_root, importer]) != project_root:
                raise RuntimeError("Managed importer escaped the Unreal project root.")
            if not os.path.isfile(importer):
                raise RuntimeError(f"Managed importer does not exist: {importer}")
            runpy.run_path(importer, run_name="__main__")
            result = _readback("CutSceneAI Unreal importer executed.")
        elif name in {"play_preview", "stop_preview"}:
            library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
            if library is None:
                raise RuntimeError("Sequencer scripting is unavailable.")
            action = "play" if name == "play_preview" else "pause"
            callback = getattr(library, action, None)
            if callback is None:
                raise RuntimeError(f"Sequencer does not expose {action}().")
            callback()
            result = _readback(f"Sequencer {action} requested.")
        else:
            raise RuntimeError(f"Unsupported bridge command: {name}")
        return True, result, None
    except Exception as exc:
        return False, _readback("Command failed."), str(exc)


def _poll() -> None:
    config = _state["config"]
    now = time.monotonic()
    interval = max(1.0, float(config.get("poll_interval_seconds", 2.0)))
    if now - float(_state["last_poll"]) < interval:
        return
    _state["last_poll"] = now

    base = (
        config["backend_url"]
        + "/api/v1/studio/projects/"
        + urllib.parse.quote(config["project_id"], safe="")
    )
    response = _request(
        "GET",
        base
        + "/bridge/poll?agent_id="
        + urllib.parse.quote(_state["agent_id"], safe=""),
    )
    command = (response or {}).get("command")
    if not command:
        return

    succeeded, result, error = _execute(command)
    _request(
        "POST",
        base
        + "/bridge/commands/"
        + urllib.parse.quote(command["command_id"], safe="")
        + "/complete",
        {
            "agent_id": _state["agent_id"],
            "succeeded": succeeded,
            "result": result,
            "error": error,
        },
    )


def _tick(delta_time: float) -> None:
    del delta_time
    try:
        _heartbeat()
        _poll()
    except (urllib.error.URLError, TimeoutError):
        return
    except Exception as exc:
        unreal.log_warning(f"CutSceneAI Studio Bridge: {exc}")


def start_bridge() -> None:
    if _state["ticker_handle"] is not None:
        return
    try:
        config = _load_config()
    except Exception as exc:
        unreal.log_error(f"CutSceneAI Studio Bridge configuration error: {exc}")
        return

    _state["config"] = config
    _state["agent_id"] = (
        socket.gethostname() + ":unreal:" + str(config["project_id"])
    )
    _state["ticker_handle"] = unreal.register_slate_post_tick_callback(_tick)
    unreal.log(
        "CutSceneAI Studio Bridge ready for project "
        + str(config["project_id"])
        + " at "
        + str(config["backend_url"])
    )


def stop_bridge() -> None:
    handle = _state.get("ticker_handle")
    if handle is not None:
        unreal.unregister_slate_post_tick_callback(handle)
    _state["ticker_handle"] = None
