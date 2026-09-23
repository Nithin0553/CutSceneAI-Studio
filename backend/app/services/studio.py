from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cutsceneai_cir import Project, Quaternion, Transform, Vector3
from cutsceneai_performance import compile_generation_plan
from cutsceneai_unity import (
    UnityAssetMap,
    UnityEntityAsset,
    compile_project as compile_unity_project,
)
from cutsceneai_unreal import compile_project as compile_unreal_project

from app.services.performance_providers import performance_compiler_config

from app.models.studio import (
    StudioAsset,
    StudioBindingCandidate,
    StudioBindingManifest,
    StudioBindingOptionsResponse,
    StudioBindingRole,
    StudioBindingSelection,
    StudioBridgeCommand,
    StudioBridgeCommandRequest,
    StudioBridgeCommandResultRequest,
    StudioBridgeCommandStatus,
    StudioBridgeHeartbeatRequest,
    StudioBridgeInstallResponse,
    StudioBridgeManifestRequest,
    StudioBridgePollResponse,
    StudioCapability,
    StudioCapabilityResponse,
    StudioEngine,
    StudioProjectConnectRequest,
    StudioProjectManifest,
    StudioProjectRecord,
    StudioRealizationResponse,
    StudioCIRRevision,
    StudioRevisionCreateRequest,
)


_REPO_ROOT = Path(__file__).resolve().parents[3]
_STATE_DIR = _REPO_ROOT / ".cutsceneai-studio" / "state"
_PROJECTS_FILE = _STATE_DIR / "projects.json"
_COMMANDS_DIR = _STATE_DIR / "bridge-commands"
_REVISIONS_DIR = _STATE_DIR / "cir-revisions"
_MAX_DISCOVERED_ASSETS = 5000
_BRIDGE_LEASE_TIMEOUT_SECONDS = 120
_BRIDGE_SAME_AGENT_REDELIVERY_SECONDS = 3


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _words(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower().replace("_", " "))
        if len(token) > 1
    }


def _character_capability_rank(candidate: StudioAsset) -> int:
    metadata = candidate.metadata
    if (
        candidate.verified
        and candidate.engine_ref.startswith("Assets/")
        and candidate.engine_ref.endswith(".prefab")
        and metadata.get("humanoid") is True
    ):
        return 5
    if (
        candidate.verified
        and candidate.kind == "character_asset"
        and candidate.engine_ref.startswith("/Game/")
        and metadata.get("asset_type") == "skeletal_mesh"
    ):
        return 5
    if candidate.engine_ref.startswith("Assets/") and candidate.engine_ref.endswith(".prefab"):
        return 3
    if candidate.kind == "character_asset" and candidate.engine_ref.startswith("/Game/"):
        return 3
    if candidate.kind == "model":
        return 2
    return 1


def _candidate_score(label: str, description: str | None, candidate: StudioAsset) -> float:
    label_words = _words(label)
    description_words = _words(description or "")
    display_words = _words(candidate.display_name)
    candidate_words = _words(
        f"{candidate.display_name} {candidate.relative_path} "
        + " ".join(str(value) for value in candidate.metadata.values())
    )
    if not label_words and not description_words:
        return 0.0

    label_overlap = len(label_words & display_words) / max(1, len(label_words))
    display_precision = len(label_words & display_words) / max(1, len(display_words))
    description_overlap = len(description_words & candidate_words) / max(
        1, len(description_words)
    )
    normalized_label = re.sub(r"[^a-z0-9]+", "", label.lower())
    normalized_display = re.sub(r"[^a-z0-9]+", "", candidate.display_name.lower())
    exact_name_bonus = 0.2 if normalized_label == normalized_display else 0.0

    score = (
        (0.55 * label_overlap)
        + (0.20 * display_precision)
        + (0.15 * description_overlap)
        + exact_name_bonus
    )
    return min(1.0, round(score, 4))


class StudioService:
    def __init__(self) -> None:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)

    def capabilities(self) -> StudioCapabilityResponse:
        return StudioCapabilityResponse(
            capabilities=[
                StudioCapability(
                    id="project-connection",
                    label="Project connection",
                    status="implemented",
                    description=(
                        "Local Unity/Unreal project registration and targeted filesystem preflight."
                    ),
                ),
                StudioCapability(
                    id="engine-native-discovery",
                    label="Engine-native capability discovery",
                    status="implemented-beta",
                    description=(
                        "Local Unity and Unreal editor agents now publish verified project objects, "
                        "rig/camera metadata, scene state and heartbeat liveness. Native editor "
                        "acceptance runs are still required before this gate is frozen."
                    ),
                    blocking=True,
                ),
                StudioCapability(
                    id="director-cir",
                    label="Natural language to CIR",
                    status="implemented",
                    description=(
                        "Director API, CIR validation and deterministic storyboard preview."
                    ),
                ),
                StudioCapability(
                    id="binding",
                    label="Role and asset binding",
                    status="implemented-baseline",
                    description=(
                        "Manual binding and deterministic suggestions are available from "
                        "discovered "
                        "project objects; verified rig compatibility depends on the engine bridge."
                    ),
                ),
                StudioCapability(
                    id="performance-plan",
                    label="Generated performance planning",
                    status="implemented",
                    description=(
                        "CIR compiles into deterministic body, facial and camera generation "
                        "requests."
                    ),
                ),
                StudioCapability(
                    id="performance-inference",
                    label="General performance inference orchestration",
                    status="provider-ready",
                    description=(
                        "The Studio now executes a strict external canonical body provider, "
                        "deterministic facial/camera baselines, optional OpenAI WAV speech, and "
                        "assembles hash-verified Generated Performance Packages. A production body "
                        "provider must still be configured and benchmarked."
                    ),
                    blocking=True,
                ),
                StudioCapability(
                    id="engine-realization",
                    label="Bound engine realization plan",
                    status="implemented",
                    description=(
                        "Validated CIR plus project bindings compiles to the existing Unity or "
                        "Unreal "
                        "adapter plan and importer."
                    ),
                ),
                StudioCapability(
                    id="engine-runner",
                    label="Bidirectional engine runner",
                    status="implemented-beta",
                    description=(
                        "A localhost-only Unity/Unreal bridge now installs into registered projects, "
                        "heartbeats verified state, leases allowlisted commands, stages managed "
                        "importers, executes realization, and returns editor readback. Native smoke "
                        "acceptance is still required."
                    ),
                    blocking=True,
                ),
                StudioCapability(
                    id="natural-language-editing",
                    label="Natural-language incremental editing",
                    status="implemented-baseline",
                    description=(
                        "Natural-language CIR revision, validation, in-session undo and safe "
                        "downstream invalidation are implemented. Persistent revision history and "
                        "dependency-local regeneration remain."
                    ),
                    blocking=True,
                ),
                StudioCapability(
                    id="evaluation",
                    label="Paper-grade benchmark evaluation",
                    status="partial",
                    description=(
                        "Parity/evidence infrastructure exists, but the V3 multi-scene benchmark, "
                        "repeated runs and reliability/repeatability statistics remain to be run."
                    ),
                    blocking=True,
                ),
            ]
        )

    def list_projects(self) -> list[StudioProjectRecord]:
        return [self._with_bridge_liveness(item) for item in self._load_projects().values()]

    def get_project(self, project_id: str) -> StudioProjectRecord:
        records = self._load_projects()
        try:
            return self._with_bridge_liveness(records[project_id])
        except KeyError as exc:
            raise ValueError(f"Unknown Studio project '{project_id}'.") from exc

    @staticmethod
    def _with_bridge_liveness(record: StudioProjectRecord) -> StudioProjectRecord:
        last_seen = record.manifest.bridge_last_seen_utc
        live = False
        if last_seen is not None:
            try:
                age = datetime.now(UTC) - datetime.fromisoformat(last_seen)
                live = 0 <= age.total_seconds() <= 30
            except ValueError:
                live = False
        if record.manifest.bridge_connected == live:
            return record
        return record.model_copy(
            update={"manifest": record.manifest.model_copy(update={"bridge_connected": live})}
        )

    def connect_project(self, request: StudioProjectConnectRequest) -> StudioProjectRecord:
        project_path = Path(request.project_path).expanduser().resolve()
        if not project_path.exists() or not project_path.is_dir():
            raise ValueError(f"Project path does not exist: {project_path}")

        if request.engine is StudioEngine.UNITY:
            self._validate_unity_project(project_path)
        else:
            self._validate_unreal_project(project_path)

        display_name = request.display_name or project_path.name
        project_id = _stable_id(
            "studio-project",
            f"{request.engine.value}:{str(project_path).lower()}",
        )
        manifest = self._filesystem_manifest(
            project_id=project_id,
            engine=request.engine,
            display_name=display_name,
            project_path=project_path,
        )
        record = StudioProjectRecord(
            project_id=project_id,
            engine=request.engine,
            display_name=display_name,
            project_path=str(project_path),
            engine_executable=request.engine_executable,
            connected_at_utc=_utc_now(),
            manifest=manifest,
        )
        records = self._load_projects()
        records[project_id] = record
        self._save_projects(records)
        return record

    def scan_project(self, project_id: str) -> StudioProjectRecord:
        record = self.get_project(project_id)
        path = Path(record.project_path)
        manifest = self._filesystem_manifest(
            project_id=record.project_id,
            engine=record.engine,
            display_name=record.display_name,
            project_path=path,
        )
        updated = record.model_copy(update={"manifest": manifest})
        records = self._load_projects()
        records[project_id] = updated
        self._save_projects(records)
        return updated

    def update_bridge_manifest(
        self, project_id: str, request: StudioBridgeManifestRequest
    ) -> StudioProjectRecord:
        record = self.get_project(project_id)
        manifest = record.manifest.model_copy(
            update={
                "engine_version": request.engine_version or record.manifest.engine_version,
                "adapter_version": request.adapter_version,
                "current_scene": request.current_scene,
                "fps": request.fps,
                "discovery_mode": "engine_bridge",
                "bridge_connected": True,
                "capabilities": request.capabilities,
                "assets": request.assets,
                "scene_snapshot": request.scene_snapshot,
                "warnings": request.warnings,
            }
        )
        updated = record.model_copy(update={"manifest": manifest})
        records = self._load_projects()
        records[project_id] = updated
        self._save_projects(records)
        return updated

    def install_bridge(self, project_id: str) -> StudioBridgeInstallResponse:
        record = self.get_project(project_id)
        project_root = Path(record.project_path)
        source_root = _REPO_ROOT / "engine-bridge"
        installed: list[str] = []

        config = {
            "bridge_version": "0.2.0",
            "project_id": project_id,
            "backend_url": "http://127.0.0.1:8000",
            "poll_interval_seconds": 2.0,
        }

        if record.engine is StudioEngine.UNITY:
            source = source_root / "unity" / "CutSceneAIStudioBridge.cs"
            benchmark_source = source_root / "unity" / "CutSceneAIHallwayBenchmarkSetup.cs"
            if not source.exists():
                raise ValueError("Unity bridge source is missing from the CutSceneAI repository.")
            if not benchmark_source.exists():
                raise ValueError(
                    "Unity hallway benchmark setup source is missing from the CutSceneAI repository."
                )
            script_target = (
                project_root / "Assets" / "Editor" / "CutSceneAI" / "CutSceneAIStudioBridge.cs"
            )
            benchmark_target = (
                project_root
                / "Assets"
                / "Editor"
                / "CutSceneAI"
                / "CutSceneAIHallwayBenchmarkSetup.cs"
            )
            config_target = (
                project_root / "Assets" / "CutSceneAI" / "Bridge" / "cutsceneai-bridge.json"
            )
            self._write_managed_bridge_file(source.read_text(encoding="utf-8"), script_target)
            self._write_managed_bridge_file(
                benchmark_source.read_text(encoding="utf-8"),
                benchmark_target,
            )
            self._write_managed_bridge_file(
                json.dumps(config, indent=2, sort_keys=True) + "\n",
                config_target,
            )
            installed.extend(
                [
                    script_target.relative_to(project_root).as_posix(),
                    benchmark_target.relative_to(project_root).as_posix(),
                    config_target.relative_to(project_root).as_posix(),
                ]
            )
            message = (
                "Unity bridge installed. Unity will compile it automatically when the project is "
                "open; otherwise open the project once to start the local bridge."
            )
        else:
            source = source_root / "unreal" / "cutsceneai_studio_bridge.py"
            plugin_source = source_root / "unreal" / "CutSceneAIStudioBridge.uplugin"
            if not source.exists() or not plugin_source.exists():
                raise ValueError("Unreal bridge source is missing from the CutSceneAI repository.")
            plugin_root = project_root / "Plugins" / "CutSceneAIStudioBridge"
            script_target = plugin_root / "Content" / "Python" / "cutsceneai_studio_bridge.py"
            init_target = plugin_root / "Content" / "Python" / "init_unreal.py"
            plugin_target = plugin_root / "CutSceneAIStudioBridge.uplugin"
            config_target = plugin_root / "Content" / "Python" / "cutsceneai-bridge.json"
            self._write_managed_bridge_file(source.read_text(encoding="utf-8"), script_target)
            self._write_managed_bridge_file(
                "import cutsceneai_studio_bridge\ncutsceneai_studio_bridge.start_bridge()\n",
                init_target,
            )
            self._write_managed_bridge_file(
                plugin_source.read_text(encoding="utf-8"),
                plugin_target,
            )
            self._write_managed_bridge_file(
                json.dumps(config, indent=2, sort_keys=True) + "\n",
                config_target,
            )
            installed.extend(
                [
                    script_target.relative_to(project_root).as_posix(),
                    init_target.relative_to(project_root).as_posix(),
                    plugin_target.relative_to(project_root).as_posix(),
                    config_target.relative_to(project_root).as_posix(),
                ]
            )
            message = (
                "Unreal bridge plugin installed. Restart/open the project so Unreal discovers the "
                "project plugin and its Python startup script."
            )

        return StudioBridgeInstallResponse(
            project_id=project_id,
            engine=record.engine,
            installed_files=installed,
            restart_required=True,
            message=message,
        )

    def stage_realization_importer(self, project_id: str, content: str) -> str:
        record = self.get_project(project_id)
        project_root = Path(record.project_path)
        if record.engine is StudioEngine.UNITY:
            relative = Path("Assets/Editor/CutSceneAI/Generated/CutSceneAISemanticMarker.cs")
            expected_marker = "// Generated by CutSceneAI Unity Adapter"
        else:
            relative = Path("Saved/CutSceneAI/Generated/cutsceneai-unreal-import.py")
            expected_marker = '"""Generated by CutSceneAI Unreal Adapter'

        target = project_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            existing = target.read_text(encoding="utf-8", errors="ignore")
            if existing and not existing.startswith(expected_marker):
                raise ValueError(f"Refusing to replace unmanaged realization importer: {target}")
        target.write_text(content, encoding="utf-8", newline="\n")
        return relative.as_posix()

    @staticmethod
    def _is_generated_realization_scene(scene_ref: str | None) -> bool:
        if not scene_ref:
            return False
        normalized = scene_ref.replace("\\", "/")
        return normalized.startswith("Assets/CutSceneAI/Studio/Run_")

    def bridge_heartbeat(
        self,
        project_id: str,
        request: StudioBridgeHeartbeatRequest,
    ) -> StudioProjectRecord:
        record = self.get_project(project_id)
        merged_assets = {
            item.object_id: item
            for item in record.manifest.assets
            if item.metadata.get("source") == "filesystem"
        }
        for item in request.assets:
            merged_assets[item.object_id] = item

        scene_snapshot = request.scene_snapshot
        if (
            self._is_generated_realization_scene(request.current_scene)
            and record.manifest.scene_snapshot is not None
        ):
            scene_snapshot = record.manifest.scene_snapshot

        manifest = record.manifest.model_copy(
            update={
                "engine_version": request.engine_version or record.manifest.engine_version,
                "adapter_version": request.adapter_version or record.manifest.adapter_version,
                "current_scene": request.current_scene,
                "fps": request.fps,
                "discovery_mode": "engine_bridge",
                "bridge_connected": True,
                "bridge_agent_id": request.agent_id,
                "bridge_last_seen_utc": _utc_now(),
                "capabilities": request.capabilities,
                "assets": list(merged_assets.values()),
                "scene_snapshot": scene_snapshot,
                "warnings": request.warnings,
            }
        )
        updated = record.model_copy(update={"manifest": manifest})
        records = self._load_projects()
        records[project_id] = updated
        self._save_projects(records)
        return updated

    def enqueue_bridge_command(
        self,
        project_id: str,
        request: StudioBridgeCommandRequest,
    ) -> StudioBridgeCommand:
        record = self.get_project(project_id)
        if not record.manifest.bridge_connected:
            raise ValueError(
                "The engine bridge is not live. Keep the target editor open and wait for a fresh "
                "heartbeat before sending commands."
            )
        command = StudioBridgeCommand(
            command_id=_stable_id(
                "bridge-command",
                f"{project_id}:{request.command.value}:{_utc_now()}",
            ),
            project_id=project_id,
            engine=record.engine,
            command=request.command,
            payload=request.payload,
            status=StudioBridgeCommandStatus.PENDING,
            created_at_utc=_utc_now(),
        )
        commands = self._load_bridge_commands(project_id)
        commands.append(command)
        self._save_bridge_commands(project_id, commands[-200:])
        return command

    def list_bridge_commands(self, project_id: str) -> list[StudioBridgeCommand]:
        self.get_project(project_id)
        return self._load_bridge_commands(project_id)

    def get_bridge_command(
        self,
        project_id: str,
        command_id: str,
    ) -> StudioBridgeCommand:
        self.get_project(project_id)
        for command in self._load_bridge_commands(project_id):
            if command.command_id == command_id:
                return command
        raise ValueError(f"Unknown bridge command '{command_id}'.")

    def poll_bridge_command(
        self,
        project_id: str,
        agent_id: str,
    ) -> StudioBridgePollResponse:
        self.get_project(project_id)
        commands = self._load_bridge_commands(project_id)
        now = datetime.now(UTC)
        changed = False

        for index, command in enumerate(commands):
            if (
                command.status is StudioBridgeCommandStatus.LEASED
                and command.leased_at_utc is not None
            ):
                leased_at = datetime.fromisoformat(command.leased_at_utc)
                lease_age = (now - leased_at).total_seconds()
                if lease_age > _BRIDGE_LEASE_TIMEOUT_SECONDS:
                    commands[index] = command.model_copy(
                        update={
                            "status": StudioBridgeCommandStatus.PENDING,
                            "leased_at_utc": None,
                            "leased_to_agent_id": None,
                        }
                    )
                    changed = True
                    continue
                if command.leased_to_agent_id == agent_id:
                    if changed:
                        self._save_bridge_commands(project_id, commands)
                    if lease_age >= _BRIDGE_SAME_AGENT_REDELIVERY_SECONDS:
                        return StudioBridgePollResponse(command=command)
                    return StudioBridgePollResponse(command=None)

        for index, command in enumerate(commands):
            if command.status is not StudioBridgeCommandStatus.PENDING:
                continue
            leased = command.model_copy(
                update={
                    "status": StudioBridgeCommandStatus.LEASED,
                    "leased_at_utc": _utc_now(),
                    "leased_to_agent_id": agent_id,
                }
            )
            commands[index] = leased
            self._save_bridge_commands(project_id, commands)
            return StudioBridgePollResponse(command=leased)

        if changed:
            self._save_bridge_commands(project_id, commands)
        return StudioBridgePollResponse(command=None)

    def complete_bridge_command(
        self,
        project_id: str,
        command_id: str,
        request: StudioBridgeCommandResultRequest,
    ) -> StudioBridgeCommand:
        self.get_project(project_id)
        commands = self._load_bridge_commands(project_id)
        for index, command in enumerate(commands):
            if command.command_id != command_id:
                continue
            if command.status not in {
                StudioBridgeCommandStatus.LEASED,
                StudioBridgeCommandStatus.SUCCEEDED,
                StudioBridgeCommandStatus.FAILED,
            }:
                raise ValueError("Bridge command is not currently leased.")
            if command.leased_to_agent_id != request.agent_id:
                raise ValueError("Bridge command lease belongs to a different engine agent.")
            if command.status in {
                StudioBridgeCommandStatus.SUCCEEDED,
                StudioBridgeCommandStatus.FAILED,
            }:
                expected = (
                    StudioBridgeCommandStatus.SUCCEEDED
                    if request.succeeded
                    else StudioBridgeCommandStatus.FAILED
                )
                if command.status is not expected:
                    raise ValueError("Bridge command already completed with a conflicting outcome.")
                return command
            completed = command.model_copy(
                update={
                    "status": (
                        StudioBridgeCommandStatus.SUCCEEDED
                        if request.succeeded
                        else StudioBridgeCommandStatus.FAILED
                    ),
                    "completed_at_utc": _utc_now(),
                    "result": request.result,
                    "error": request.error,
                }
            )
            commands[index] = completed
            self._save_bridge_commands(project_id, commands)
            return completed
        raise ValueError(f"Unknown bridge command '{command_id}'.")

    @staticmethod
    def _write_managed_bridge_file(content: str, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            existing = target.read_text(encoding="utf-8", errors="ignore")
            if existing == content:
                return

            managed_bridge_source = (
                "CutSceneAI Studio Bridge" in existing
                or "cutsceneai_studio_bridge" in str(target)
            )
            managed_bridge_config = False
            if target.name == "cutsceneai-bridge.json":
                try:
                    existing_config = json.loads(existing)
                    replacement_config = json.loads(content)
                except json.JSONDecodeError:
                    existing_config = None
                    replacement_config = None
                if isinstance(existing_config, dict) and isinstance(replacement_config, dict):
                    required = {
                        "bridge_version",
                        "project_id",
                        "backend_url",
                        "poll_interval_seconds",
                    }
                    managed_bridge_config = (
                        required.issubset(existing_config)
                        and required.issubset(replacement_config)
                        and existing_config["project_id"] == replacement_config["project_id"]
                        and existing_config["backend_url"] == replacement_config["backend_url"]
                    )

            if not managed_bridge_source and not managed_bridge_config:
                raise ValueError(f"Refusing to replace unmanaged bridge file: {target}")
        target.write_text(content, encoding="utf-8", newline="\n")

    @staticmethod
    def _bridge_commands_file(project_id: str) -> Path:
        return _COMMANDS_DIR / f"{project_id}.json"

    def _load_bridge_commands(self, project_id: str) -> list[StudioBridgeCommand]:
        path = self._bridge_commands_file(project_id)
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return [StudioBridgeCommand.model_validate(item) for item in payload]

    def _save_bridge_commands(
        self,
        project_id: str,
        commands: list[StudioBridgeCommand],
    ) -> None:
        _COMMANDS_DIR.mkdir(parents=True, exist_ok=True)
        path = self._bridge_commands_file(project_id)
        temp = path.with_suffix(".tmp")
        temp.write_text(
            json.dumps(
                [item.model_dump(mode="json") for item in commands],
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        temp.replace(path)

    def create_revision(
        self,
        request: StudioRevisionCreateRequest,
    ) -> StudioCIRRevision:
        self.get_project(request.project_id)
        project_payload = request.project.model_dump(mode="json")
        project_bytes = json.dumps(
            project_payload,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        project_sha256 = hashlib.sha256(project_bytes).hexdigest()

        existing = self.list_revisions(request.project_id)
        by_id = {item.revision_id: item for item in existing}
        parent = None
        if request.parent_revision_id is not None:
            try:
                parent = by_id[request.parent_revision_id]
            except KeyError as exc:
                raise ValueError(
                    f"Unknown parent revision '{request.parent_revision_id}'."
                ) from exc
            if parent.cir_project_id != request.project.id:
                raise ValueError("CIR revision parent belongs to a different CIR project identity.")
        elif request.source.value not in {"generation", "import"}:
            raise ValueError(
                "Edited or restored CIR revisions require an explicit parent revision."
            )

        if request.source.value == "edit" and not request.instruction:
            raise ValueError("Edited CIR revisions require the edit instruction.")

        created = _utc_now()
        revision_id = _stable_id(
            "cir-revision",
            (
                f"{request.project_id}:{request.project.id}:{project_sha256}:"
                f"{request.parent_revision_id or 'root'}:{created}"
            ),
        )
        revision = StudioCIRRevision(
            revision_id=revision_id,
            project_id=request.project_id,
            cir_project_id=request.project.id,
            source=request.source,
            parent_revision_id=request.parent_revision_id,
            instruction=request.instruction,
            created_at_utc=created,
            project_sha256=project_sha256,
            project=request.project.model_copy(deep=True),
        )
        revisions = [*existing, revision]
        self._save_revisions(request.project_id, revisions[-500:])
        return revision

    def list_revisions(self, project_id: str) -> list[StudioCIRRevision]:
        self.get_project(project_id)
        path = self._revisions_file(project_id)
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        revisions = [StudioCIRRevision.model_validate(item) for item in payload]
        revisions.sort(key=lambda item: item.created_at_utc)
        return revisions

    def get_revision(
        self,
        project_id: str,
        revision_id: str,
    ) -> StudioCIRRevision:
        for revision in self.list_revisions(project_id):
            if revision.revision_id == revision_id:
                return revision
        raise ValueError(f"Unknown CIR revision '{revision_id}'.")

    @staticmethod
    def _revisions_file(project_id: str) -> Path:
        return _REVISIONS_DIR / f"{project_id}.json"

    def _save_revisions(
        self,
        project_id: str,
        revisions: list[StudioCIRRevision],
    ) -> None:
        _REVISIONS_DIR.mkdir(parents=True, exist_ok=True)
        path = self._revisions_file(project_id)
        temp = path.with_suffix(".tmp")
        temp.write_text(
            json.dumps(
                [item.model_dump(mode="json") for item in revisions],
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        temp.replace(path)

    def binding_options(self, project_id: str, project: Project) -> StudioBindingOptionsResponse:
        record = self.get_project(project_id)
        assets = self.binding_assets(record)
        roles: list[StudioBindingRole] = []

        for character in project.characters:
            candidates = self._rank_candidates(
                label=character.name,
                description=" ".join(
                    value for value in (character.role, character.description) if value
                ),
                assets=assets,
                character=True,
            )
            roles.append(
                StudioBindingRole(
                    cir_id=character.id,
                    label=character.name,
                    kind="character",
                    description=character.description or character.role,
                    required=True,
                    candidates=candidates,
                )
            )

        for environment_object in project.environment:
            candidates = self._rank_candidates(
                label=environment_object.name,
                description=environment_object.description,
                assets=assets,
                character=False,
            )
            roles.append(
                StudioBindingRole(
                    cir_id=environment_object.id,
                    label=environment_object.name,
                    kind="environment",
                    description=environment_object.description,
                    required=False,
                    candidates=candidates,
                )
            )

        return StudioBindingOptionsResponse(
            project_id=project_id,
            engine=record.engine,
            roles=roles,
        )

    def validate_bindings(
        self,
        project_id: str,
        project: Project,
        bindings: list[StudioBindingSelection],
    ) -> StudioBindingManifest:
        record = self.get_project(project_id)
        known_object_ids = {asset.object_id for asset in record.manifest.assets}
        if record.manifest.scene_snapshot is not None:
            known_object_ids.update(
                item.object_id for item in record.manifest.scene_snapshot.objects
            )
        selection_by_id = {item.cir_id: item for item in bindings}
        unknown_objects = [
            item.project_object_id
            for item in bindings
            if item.project_object_id not in known_object_ids
        ]
        if unknown_objects:
            raise ValueError(
                "Binding references unknown project objects: " + ", ".join(unknown_objects)
            )

        required_ids = {item.id for item in project.characters}
        optional_ids = {item.id for item in project.environment}
        unresolved_required = sorted(required_ids - selection_by_id.keys())
        unresolved_optional = sorted(optional_ids - selection_by_id.keys())
        return StudioBindingManifest(
            project_id=project_id,
            engine=record.engine,
            cir_project_id=project.id,
            bindings=bindings,
            unresolved_required_ids=unresolved_required,
            unresolved_optional_ids=unresolved_optional,
            valid=not unresolved_required,
        )

    def performance_plan(
        self,
        project: Project,
        experiment_seed: int,
        *,
        project_id: str | None = None,
        bindings: list[StudioBindingSelection] | None = None,
    ) -> dict[str, Any]:
        conditioned = project
        if project_id is not None:
            conditioned = self.scene_conditioned_project(
                project_id,
                project,
                bindings or [],
            )
        plan = compile_generation_plan(
            conditioned,
            config=performance_compiler_config(experiment_seed),
        )
        return plan.model_dump(mode="json")

    def scene_conditioned_project(
        self,
        project_id: str,
        project: Project,
        bindings: list[StudioBindingSelection],
    ) -> Project:
        record = self.get_project(project_id)
        snapshot = record.manifest.scene_snapshot
        if snapshot is None:
            raise ValueError(
                "Scene-conditioned planning requires a live engine scene snapshot."
            )

        self.validate_bindings(project_id, project, bindings)
        scene_by_id = {item.object_id: item for item in snapshot.objects}
        result = project.model_copy(deep=True)
        entity_by_id = {
            **{item.id: item for item in result.characters},
            **{item.id: item for item in result.environment},
        }

        for binding in bindings:
            scene_object = scene_by_id.get(binding.project_object_id)
            entity = entity_by_id.get(binding.cir_id)
            if scene_object is None or entity is None:
                continue

            position = scene_object.transform.position_m
            rotation = scene_object.transform.rotation
            scale = scene_object.transform.scale
            entity.initial_transform = Transform(
                position=Vector3(x=position.x, y=position.y, z=position.z),
                rotation=Quaternion(
                    x=rotation.x,
                    y=rotation.y,
                    z=rotation.z,
                    w=rotation.w,
                ),
                scale=Vector3(x=scale.x, y=scale.y, z=scale.z),
            )

            prefab_path = scene_object.prefab_asset_path
            if prefab_path:
                entity.asset_uri = prefab_path

        return result

    @staticmethod
    def _scene_snapshot_assets(record: StudioProjectRecord) -> list[StudioAsset]:
        snapshot = record.manifest.scene_snapshot
        if snapshot is None:
            return []

        verified_by_ref = {
            item.engine_ref: item
            for item in record.manifest.assets
            if item.verified
        }
        object_by_id = {item.object_id: item for item in snapshot.objects}

        def has_character_ancestor(item) -> bool:
            parent_id = item.parent_object_id
            seen: set[str] = set()
            while parent_id:
                if parent_id in seen:
                    break
                seen.add(parent_id)
                parent = object_by_id.get(parent_id)
                if parent is None:
                    break
                if parent.kind == "character":
                    return True
                parent_id = parent.parent_object_id
            return False

        result: list[StudioAsset] = []
        for item in snapshot.objects:
            # Keep the complete hierarchy in the snapshot, but do not expose rig bones,
            # nested Animator objects, or other character internals as semantic bindings.
            if has_character_ancestor(item):
                continue

            prefab_path = item.prefab_asset_path or ""
            verified_prefab = verified_by_ref.get(prefab_path)
            metadata: dict[str, Any] = {
                "source": "scene_snapshot",
                "scene_ref": snapshot.scene_ref,
                "hierarchy_path": item.hierarchy_path,
                "scene_kind": item.kind,
                "prefab_asset_path": item.prefab_asset_path,
                "canonical_world_position_meters": item.transform.position_m.model_dump(
                    mode="json"
                ),
                "canonical_world_rotation": item.transform.rotation.model_dump(mode="json"),
                "canonical_world_scale": item.transform.scale.model_dump(mode="json"),
                "components": item.components,
            }
            if item.bounds is not None:
                metadata["canonical_world_bounds"] = item.bounds.model_dump(mode="json")
            if verified_prefab is not None:
                metadata.update(verified_prefab.metadata)

            result.append(
                StudioAsset(
                    object_id=item.object_id,
                    kind=(
                        "scene_character"
                        if item.kind == "character"
                        else "scene_object"
                    ),
                    display_name=item.display_name,
                    engine_ref=prefab_path or item.object_id,
                    relative_path=item.hierarchy_path,
                    verified=True,
                    metadata=metadata,
                )
            )
        return result

    def binding_assets(self, record: StudioProjectRecord) -> list[StudioAsset]:
        return [*record.manifest.assets, *self._scene_snapshot_assets(record)]

    def compile_realization(
        self,
        project_id: str,
        project: Project,
        bindings: list[StudioBindingSelection],
    ) -> StudioRealizationResponse:
        record = self.get_project(project_id)
        binding_manifest = self.validate_bindings(project_id, project, bindings)
        conditioned_project = (
            self.scene_conditioned_project(project_id, project, bindings)
            if record.manifest.scene_snapshot is not None
            else project
        )
        if not binding_manifest.valid:
            return StudioRealizationResponse(
                project_id=project_id,
                engine=record.engine,
                ready=False,
                blocking_issues=[
                    "Required character roles are not fully bound: "
                    + ", ".join(binding_manifest.unresolved_required_ids)
                ],
            )

        asset_by_id = {item.object_id: item for item in self.binding_assets(record)}
        selection_by_cir = {item.cir_id: item for item in bindings}
        required_character_ids = {item.id for item in project.characters}
        warnings: list[str] = []
        blocking_issues: list[str] = []

        if not record.manifest.bridge_connected:
            warnings.append(
                "Engine bridge is not connected. The realization plan can be prepared, "
                "but native cutscene generation requires the Studio bridge to be installed, "
                "the engine project open, and a live heartbeat."
            )

        environment_by_id = {item.id: item for item in project.environment}
        for cir_id in binding_manifest.unresolved_optional_ids:
            environment = environment_by_id[cir_id]
            warnings.append(
                f"Environment object '{environment.name}' is not bound to an engine asset; "
                "CutSceneAI will use its CIR transform and a placeholder visual when needed."
            )

        for cir_id in required_character_ids:
            selection = selection_by_cir[cir_id]
            asset = asset_by_id[selection.project_object_id]
            if record.engine is StudioEngine.UNITY:
                compatible = asset.engine_ref.startswith("Assets/") and asset.engine_ref.endswith(
                    ".prefab"
                )
                requirement = "a Unity prefab path under Assets/"
            else:
                compatible = asset.engine_ref.startswith("/Game/")
                requirement = "an Unreal /Game asset reference"
            if not compatible:
                blocking_issues.append(
                    f"Required character binding '{cir_id}' must resolve to {requirement}; "
                    f"got '{asset.engine_ref}'."
                )
                continue

            if record.manifest.bridge_connected:
                verified_matches = [
                    item
                    for item in record.manifest.assets
                    if item.verified and item.engine_ref == asset.engine_ref
                ]
                if not verified_matches:
                    warnings.append(
                        f"Character binding '{cir_id}' has not yet been verified by the live "
                        "engine bridge. Refresh discovery before native generation."
                    )
                elif record.engine is StudioEngine.UNITY:
                    verified = sorted(verified_matches, key=lambda item: item.object_id)[0]
                    if not bool(verified.metadata.get("humanoid")):
                        blocking_issues.append(
                            f"Unity character binding '{cir_id}' must use a prefab with a "
                            "verified valid Humanoid rig."
                        )
                else:
                    verified = sorted(verified_matches, key=lambda item: item.object_id)[0]
                    if verified.kind != "character_asset":
                        blocking_issues.append(
                            f"Unreal character binding '{cir_id}' must resolve to a verified "
                            "SkeletalMesh character asset."
                        )

        if blocking_issues:
            return StudioRealizationResponse(
                project_id=project_id,
                engine=record.engine,
                ready=False,
                warnings=warnings,
                blocking_issues=blocking_issues,
            )

        if record.engine is StudioEngine.UNITY:
            entity_assets: list[UnityEntityAsset] = []
            for cir_id, selection in selection_by_cir.items():
                asset = asset_by_id[selection.project_object_id]
                if not asset.engine_ref.startswith("Assets/") or not asset.engine_ref.endswith(
                    ".prefab"
                ):
                    warnings.append(
                        f"Binding '{cir_id}' is not a Unity prefab and cannot be passed to the "
                        "current Unity adapter asset map."
                    )
                    continue
                entity_assets.append(
                    UnityEntityAsset(
                        source_entity_id=cir_id,
                        prefab_path=asset.engine_ref,
                    )
                )
            asset_map = UnityAssetMap(project_id=project.id, entities=entity_assets)
            unity_plan = compile_unity_project(conditioned_project, asset_map=asset_map)
            plan_json = unity_plan.model_dump(mode="json")
            adapter_warnings = [warning.message for warning in unity_plan.warnings]
        else:
            bound_project = conditioned_project.model_copy(deep=True)
            character_by_id = {item.id: item for item in bound_project.characters}
            environment_by_id = {item.id: item for item in bound_project.environment}
            for cir_id, selection in selection_by_cir.items():
                asset = asset_by_id[selection.project_object_id]
                if not asset.engine_ref.startswith("/Game/"):
                    warnings.append(
                        f"Binding '{cir_id}' has no Unreal /Game asset reference and cannot be "
                        "passed to the current Unreal adapter."
                    )
                    continue
                if cir_id in character_by_id:
                    character_by_id[cir_id].asset_uri = asset.engine_ref
                elif cir_id in environment_by_id:
                    environment_by_id[cir_id].asset_uri = asset.engine_ref
            unreal_plan = compile_unreal_project(bound_project)
            plan_json = unreal_plan.model_dump(mode="json")
            adapter_warnings = [warning.message for warning in unreal_plan.warnings]

        return StudioRealizationResponse(
            project_id=project_id,
            engine=record.engine,
            ready=True,
            plan=plan_json,
            warnings=[*warnings, *adapter_warnings],
        )

    def bound_project(
        self,
        project_id: str,
        project: Project,
        bindings: list[StudioBindingSelection],
    ) -> Project:
        record = self.get_project(project_id)
        if record.engine is not StudioEngine.UNREAL:
            return project
        asset_by_id = {item.object_id: item for item in self.binding_assets(record)}
        result = (
            self.scene_conditioned_project(project_id, project, bindings)
            if record.manifest.scene_snapshot is not None
            else project.model_copy(deep=True)
        )
        characters = {item.id: item for item in result.characters}
        environment = {item.id: item for item in result.environment}
        for binding in bindings:
            asset = asset_by_id.get(binding.project_object_id)
            if asset is None or not asset.engine_ref.startswith("/Game/"):
                continue
            if binding.cir_id in characters:
                characters[binding.cir_id].asset_uri = asset.engine_ref
            elif binding.cir_id in environment:
                environment[binding.cir_id].asset_uri = asset.engine_ref
        return result

    def _rank_candidates(
        self,
        *,
        label: str,
        description: str | None,
        assets: list[StudioAsset],
        character: bool,
    ) -> list[StudioBindingCandidate]:
        if character:
            allowed = {
                "prefab",
                "model",
                "character_asset",
                "scene_actor",
                "scene_character",
            }
        else:
            allowed = {
                "prefab",
                "model",
                "asset",
                "prop",
                "scene_actor",
                "scene_object",
            }
        candidates = [item for item in assets if item.kind in allowed]
        if not character:
            candidates = [
                item
                for item in candidates
                if item.metadata.get("scene_kind") not in {"camera", "light"}
            ]
        ranked = sorted(
            candidates,
            key=lambda item: (
                _candidate_score(label, description, item),
                int(item.metadata.get("source") == "scene_snapshot"),
                _character_capability_rank(item) if character else int(item.verified),
                item.verified,
                item.display_name.lower(),
            ),
            reverse=True,
        )
        return [
            StudioBindingCandidate(
                project_object_id=item.object_id,
                display_name=item.display_name,
                engine_ref=item.engine_ref,
                kind=item.kind,
                score=_candidate_score(label, description, item),
                verified=item.verified,
                metadata=item.metadata,
            )
            for item in ranked[:50]
        ]

    def _filesystem_manifest(
        self,
        *,
        project_id: str,
        engine: StudioEngine,
        display_name: str,
        project_path: Path,
    ) -> StudioProjectManifest:
        if engine is StudioEngine.UNITY:
            return self._scan_unity(project_id, display_name, project_path)
        return self._scan_unreal(project_id, display_name, project_path)

    def _scan_unity(
        self, project_id: str, display_name: str, project_path: Path
    ) -> StudioProjectManifest:
        self._validate_unity_project(project_path)
        version_file = project_path / "ProjectSettings" / "ProjectVersion.txt"
        version = None
        if version_file.exists():
            match = re.search(
                r"m_EditorVersion:\s*([^\r\n]+)",
                version_file.read_text(encoding="utf-8", errors="ignore"),
            )
            version = match.group(1).strip() if match else None

        timeline_version = None
        package_manifest = project_path / "Packages" / "manifest.json"
        if package_manifest.exists():
            try:
                package_data = json.loads(package_manifest.read_text(encoding="utf-8"))
                timeline_version = package_data.get("dependencies", {}).get("com.unity.timeline")
            except (OSError, json.JSONDecodeError):
                pass

        assets: list[StudioAsset] = []
        asset_root = project_path / "Assets"
        extension_kind = {
            ".prefab": "prefab",
            ".fbx": "model",
            ".obj": "model",
            ".anim": "animation",
            ".playable": "timeline",
            ".unity": "scene",
            ".wav": "audio",
        }
        for path in asset_root.rglob("*"):
            if len(assets) >= _MAX_DISCOVERED_ASSETS:
                break
            if not path.is_file() or path.suffix.lower() not in extension_kind:
                continue
            relative = path.relative_to(project_path).as_posix()
            kind = extension_kind[path.suffix.lower()]
            assets.append(
                StudioAsset(
                    object_id=_stable_id("unity-object", relative.lower()),
                    kind=kind,
                    display_name=path.stem,
                    engine_ref=relative,
                    relative_path=relative,
                    verified=False,
                    metadata={"source": "filesystem"},
                )
            )

        warnings = [
            (
                "Filesystem preflight cannot verify Humanoid Avatar mappings, scene actor IDs, "
                "blendshapes or component paths. Connect the Unity engine bridge for verified "
                "capability discovery."
            )
        ]
        if len(assets) >= _MAX_DISCOVERED_ASSETS:
            warnings.append("Asset discovery reached the safety limit of 5000 entries.")

        capabilities = [
            "cir_export",
            "timeline_importer",
            "filesystem_asset_discovery",
        ]
        if timeline_version:
            capabilities.append(f"timeline:{timeline_version}")

        return StudioProjectManifest(
            project_id=project_id,
            engine=StudioEngine.UNITY,
            display_name=display_name,
            project_path=str(project_path),
            engine_version=version,
            adapter_version="0.1.0",
            discovery_mode="filesystem_preflight",
            bridge_connected=False,
            capabilities=capabilities,
            assets=assets,
            warnings=warnings,
        )

    def _scan_unreal(
        self, project_id: str, display_name: str, project_path: Path
    ) -> StudioProjectManifest:
        uproject = self._validate_unreal_project(project_path)
        engine_version = None
        try:
            data = json.loads(uproject.read_text(encoding="utf-8-sig"))
            engine_version = str(data.get("EngineAssociation") or "") or None
        except (OSError, json.JSONDecodeError):
            data = {}

        assets: list[StudioAsset] = []
        content_root = project_path / "Content"
        if content_root.exists():
            for path in content_root.rglob("*"):
                if len(assets) >= _MAX_DISCOVERED_ASSETS:
                    break
                if not path.is_file() or path.suffix.lower() not in {".uasset", ".umap", ".wav"}:
                    continue
                relative_content = path.relative_to(content_root).as_posix()
                relative_project = path.relative_to(project_path).as_posix()
                if path.suffix.lower() == ".umap":
                    kind = "scene"
                    engine_ref = "/Game/" + relative_content[: -len(path.suffix)]
                elif path.suffix.lower() == ".wav":
                    kind = "audio"
                    engine_ref = relative_project
                else:
                    searchable = relative_content.lower()
                    kind = (
                        "character_asset"
                        if any(
                            token in searchable
                            for token in ("character", "characters", "mannequin", "skeletal")
                        )
                        else "asset"
                    )
                    object_path = "/Game/" + relative_content[: -len(path.suffix)]
                    engine_ref = f"{object_path}.{path.stem}"
                assets.append(
                    StudioAsset(
                        object_id=_stable_id("unreal-object", relative_project.lower()),
                        kind=kind,
                        display_name=path.stem,
                        engine_ref=engine_ref,
                        relative_path=relative_project,
                        verified=False,
                        metadata={"source": "filesystem"},
                    )
                )

        warnings = [
            (
                "Filesystem preflight cannot inspect loaded-level actor GUIDs, SkeletalMesh "
                "skeleton "
                "compatibility, morph targets or camera instances. Connect the Unreal engine "
                "bridge "
                "for verified capability discovery."
            )
        ]
        if len(assets) >= _MAX_DISCOVERED_ASSETS:
            warnings.append("Asset discovery reached the safety limit of 5000 entries.")

        plugins = [
            item.get("Name")
            for item in data.get("Plugins", [])
            if isinstance(item, dict) and item.get("Enabled") and item.get("Name")
        ]
        capabilities = [
            "cir_export",
            "sequencer_importer",
            "filesystem_asset_discovery",
            *[f"plugin:{item}" for item in plugins],
        ]

        return StudioProjectManifest(
            project_id=project_id,
            engine=StudioEngine.UNREAL,
            display_name=display_name,
            project_path=str(project_path),
            engine_version=engine_version,
            adapter_version="0.6.0",
            discovery_mode="filesystem_preflight",
            bridge_connected=False,
            capabilities=capabilities,
            assets=assets,
            warnings=warnings,
        )

    @staticmethod
    def _validate_unity_project(project_path: Path) -> None:
        required = [
            project_path / "Assets",
            project_path / "ProjectSettings",
            project_path / "Packages",
        ]
        if not all(path.exists() for path in required):
            raise ValueError(
                f"Path is not a Unity project (Assets/ProjectSettings/Packages required): "
                f"{project_path}"
            )

    @staticmethod
    def _validate_unreal_project(project_path: Path) -> Path:
        projects = sorted(project_path.glob("*.uproject"))
        if len(projects) != 1:
            raise ValueError("Unreal project path must contain exactly one .uproject file.")
        return projects[0]

    def _load_projects(self) -> dict[str, StudioProjectRecord]:
        if not _PROJECTS_FILE.exists():
            return {}
        try:
            payload = json.loads(_PROJECTS_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return {item["project_id"]: StudioProjectRecord.model_validate(item) for item in payload}

    @staticmethod
    def _save_projects(records: dict[str, StudioProjectRecord]) -> None:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        temp = _PROJECTS_FILE.with_suffix(".tmp")
        payload = [
            item.model_dump(mode="json")
            for item in sorted(records.values(), key=lambda value: value.project_id)
        ]
        temp.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temp.replace(_PROJECTS_FILE)
