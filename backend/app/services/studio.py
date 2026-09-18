from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cutsceneai_cir import Project
from cutsceneai_performance import (
    GenerationModelConfig,
    PerformanceCompilerConfig,
    compile_generation_plan,
)
from cutsceneai_unity import (
    UnityAssetMap,
    UnityEntityAsset,
    compile_project as compile_unity_project,
)
from cutsceneai_unreal import compile_project as compile_unreal_project

from app.models.studio import (
    StudioAsset,
    StudioBindingCandidate,
    StudioBindingManifest,
    StudioBindingOptionsResponse,
    StudioBindingRole,
    StudioBindingSelection,
    StudioBridgeManifestRequest,
    StudioCapability,
    StudioCapabilityResponse,
    StudioEngine,
    StudioProjectConnectRequest,
    StudioProjectManifest,
    StudioProjectRecord,
    StudioRealizationResponse,
)


_REPO_ROOT = Path(__file__).resolve().parents[3]
_STATE_DIR = _REPO_ROOT / ".cutsceneai-studio" / "state"
_PROJECTS_FILE = _STATE_DIR / "projects.json"
_MAX_DISCOVERED_ASSETS = 5000


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


def _candidate_score(label: str, description: str | None, candidate: StudioAsset) -> float:
    role_words = _words(" ".join(item for item in (label, description) if item))
    candidate_words = _words(
        f"{candidate.display_name} {candidate.relative_path} "
        + " ".join(str(value) for value in candidate.metadata.values())
    )
    if not role_words:
        return 0.0
    overlap = len(role_words & candidate_words)
    base = overlap / len(role_words)
    exact_bonus = 0.25 if label.lower() in candidate.display_name.lower() else 0.0
    return min(1.0, round(base + exact_bonus, 4))


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
                    status="contract-ready",
                    description=(
                        "Bridge manifest ingestion is implemented; engine-side scanners still need "
                        "to publish verified actors, rigs, cameras, props and scene state."
                    ),
                    blocking=True,
                ),
                StudioCapability(
                    id="director-cir",
                    label="Natural language to CIR",
                    status="implemented",
                    description="Director API, CIR validation and deterministic storyboard preview.",
                ),
                StudioCapability(
                    id="binding",
                    label="Role and asset binding",
                    status="implemented-baseline",
                    description=(
                        "Manual binding and deterministic suggestions are available from discovered "
                        "project objects; verified rig compatibility depends on the engine bridge."
                    ),
                ),
                StudioCapability(
                    id="performance-plan",
                    label="Generated performance planning",
                    status="implemented",
                    description=(
                        "CIR compiles into deterministic body, facial and camera generation requests."
                    ),
                ),
                StudioCapability(
                    id="performance-inference",
                    label="General performance inference orchestration",
                    status="missing",
                    description=(
                        "The repository has provider contracts and one retained S02 motion result, "
                        "but the web backend does not yet execute arbitrary body/facial/camera model "
                        "providers and assemble a complete performance bundle."
                    ),
                    blocking=True,
                ),
                StudioCapability(
                    id="engine-realization",
                    label="Bound engine realization plan",
                    status="implemented",
                    description=(
                        "Validated CIR plus project bindings compiles to the existing Unity or Unreal "
                        "adapter plan and importer."
                    ),
                ),
                StudioCapability(
                    id="engine-runner",
                    label="Bidirectional engine runner",
                    status="missing",
                    description=(
                        "A persistent Unity/Unreal bridge that executes realization, focuses the "
                        "authoritative engine preview, streams status and returns readback evidence "
                        "is still required."
                    ),
                    blocking=True,
                ),
                StudioCapability(
                    id="natural-language-editing",
                    label="Natural-language incremental editing",
                    status="missing",
                    description=(
                        "CIR patch interpretation, revision history, dependency-local regeneration "
                        "and engine incremental update are not yet implemented end to end."
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
        return list(self._load_projects().values())

    def get_project(self, project_id: str) -> StudioProjectRecord:
        records = self._load_projects()
        try:
            return records[project_id]
        except KeyError as exc:
            raise ValueError(f"Unknown Studio project '{project_id}'.") from exc

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
                "warnings": request.warnings,
            }
        )
        updated = record.model_copy(update={"manifest": manifest})
        records = self._load_projects()
        records[project_id] = updated
        self._save_projects(records)
        return updated

    def binding_options(
        self, project_id: str, project: Project
    ) -> StudioBindingOptionsResponse:
        record = self.get_project(project_id)
        assets = record.manifest.assets
        roles: list[StudioBindingRole] = []

        for item in project.characters:
            candidates = self._rank_candidates(
                label=item.name,
                description=" ".join(value for value in (item.role, item.description) if value),
                assets=assets,
                character=True,
            )
            roles.append(
                StudioBindingRole(
                    cir_id=item.id,
                    label=item.name,
                    kind="character",
                    description=item.description or item.role,
                    required=True,
                    candidates=candidates,
                )
            )

        for item in project.environment:
            candidates = self._rank_candidates(
                label=item.name,
                description=item.description,
                assets=assets,
                character=False,
            )
            roles.append(
                StudioBindingRole(
                    cir_id=item.id,
                    label=item.name,
                    kind="environment",
                    description=item.description,
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
        asset_ids = {asset.object_id for asset in record.manifest.assets}
        selection_by_id = {item.cir_id: item for item in bindings}
        unknown_objects = [
            item.project_object_id
            for item in bindings
            if item.project_object_id not in asset_ids
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

    def performance_plan(self, project: Project, experiment_seed: int) -> dict[str, Any]:
        config = PerformanceCompilerConfig(
            experiment_seed=experiment_seed,
            body=GenerationModelConfig(
                provider=os.getenv("CUTSCENEAI_BODY_PROVIDER", "mdm-local"),
                model=os.getenv(
                    "CUTSCENEAI_BODY_MODEL",
                    "humanml-encoder-512-50steps",
                ),
                model_revision=os.getenv("CUTSCENEAI_BODY_MODEL_REVISION", "research-runtime"),
                prompt_version="body-v0.1",
                deterministic_algorithms=True,
            ),
            facial=GenerationModelConfig(
                provider=os.getenv("CUTSCENEAI_FACIAL_PROVIDER", "unconfigured-facial"),
                model=os.getenv("CUTSCENEAI_FACIAL_MODEL", "unconfigured"),
                model_revision=os.getenv("CUTSCENEAI_FACIAL_MODEL_REVISION", "unconfigured"),
                prompt_version="facial-v0.1",
                deterministic_algorithms=True,
            ),
            camera=GenerationModelConfig(
                provider=os.getenv("CUTSCENEAI_CAMERA_PROVIDER", "cutsceneai-camera"),
                model=os.getenv("CUTSCENEAI_CAMERA_MODEL", "procedural-v0.1"),
                model_revision=os.getenv("CUTSCENEAI_CAMERA_MODEL_REVISION", "0.1.0"),
                prompt_version="camera-v0.1",
                deterministic_algorithms=True,
            ),
        )
        plan = compile_generation_plan(project, config=config)
        return plan.model_dump(mode="json")

    def compile_realization(
        self,
        project_id: str,
        project: Project,
        bindings: list[StudioBindingSelection],
    ) -> StudioRealizationResponse:
        record = self.get_project(project_id)
        binding_manifest = self.validate_bindings(project_id, project, bindings)
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

        asset_by_id = {item.object_id: item for item in record.manifest.assets}
        selection_by_cir = {item.cir_id: item for item in bindings}
        warnings: list[str] = []

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
            plan = compile_unity_project(project, asset_map=asset_map)
        else:
            bound_project = project.model_copy(deep=True)
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
            plan = compile_unreal_project(bound_project)

        adapter_warnings = [
            warning.message
            for warning in getattr(plan, "warnings", [])
        ]
        return StudioRealizationResponse(
            project_id=project_id,
            engine=record.engine,
            ready=True,
            plan=plan.model_dump(mode="json"),
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
        asset_by_id = {item.object_id: item for item in record.manifest.assets}
        result = project.model_copy(deep=True)
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
            }
        else:
            allowed = {
                "prefab",
                "model",
                "asset",
                "prop",
                "scene_actor",
            }
        candidates = [item for item in assets if item.kind in allowed]
        ranked = sorted(
            candidates,
            key=lambda item: (
                _candidate_score(label, description, item),
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
                timeline_version = package_data.get("dependencies", {}).get(
                    "com.unity.timeline"
                )
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
        for path in sorted(asset_root.rglob("*")):
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
            for path in sorted(content_root.rglob("*")):
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
                "Filesystem preflight cannot inspect loaded-level actor GUIDs, SkeletalMesh skeleton "
                "compatibility, morph targets or camera instances. Connect the Unreal engine bridge "
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
            raise ValueError(
                "Unreal project path must contain exactly one .uproject file."
            )
        return projects[0]

    def _load_projects(self) -> dict[str, StudioProjectRecord]:
        if not _PROJECTS_FILE.exists():
            return {}
        try:
            payload = json.loads(_PROJECTS_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return {
            item["project_id"]: StudioProjectRecord.model_validate(item)
            for item in payload
        }

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
