from __future__ import annotations

import hashlib
from pathlib import Path
import re
from typing import Any

from cutsceneai_parity import compile_semantics
from cutsceneai_performance import ARKIT_52_BLENDSHAPE_NAMES, load_performance_bundle
from cutsceneai_unity import (
    UnityAssetMap,
    UnityEntityAsset,
    UnityNativeActorTarget,
    UnityNativeRealizationTarget,
    UnityNativeRenderSettings,
    UnityNativeSceneBinding,
    compile_performance_bundle as compile_unity_performance_bundle,
    compile_project as compile_unity_project,
    compile_unity_native_performance_package,
    render_unity_native_performance_script,
    render_unity_performance_mapping,
)
from cutsceneai_unreal import (
    SKELETAL_MESH_ACTOR_CLASS_PATH,
    UnrealMeshType,
    UnrealNativeActorTarget,
    UnrealNativeRealizationTarget,
    UnrealNativeRenderSettings,
    compile_performance_bundle as compile_unreal_performance_bundle,
    compile_project as compile_unreal_project,
    compile_unreal_native_performance_package,
    render_unreal_native_import_script,
    render_unreal_performance_mapping,
)

from app.models.studio import (
    StudioBindingSelection,
    StudioBridgeCommand,
    StudioBridgeCommandRequest,
    StudioBridgeCommandType,
    StudioEngine,
)
from app.services.performance_executor import StudioPerformanceExecutor
from app.services.studio import StudioService
from cutsceneai_cir import Project


_ARKIT_BLENDSHAPES = frozenset(ARKIT_52_BLENDSHAPE_NAMES)


def _run_token(run_id: str) -> str:
    token = re.sub(r"[^A-Fa-f0-9]", "", run_id)
    if len(token) != 32:
        raise ValueError("Performance run id is not a canonical UUID.")
    return "Run_" + token[:16]


def _mapping_sha(rendered: str) -> str:
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _verified_asset_for_engine_ref(record, engine_ref: str):
    verified = [
        item for item in record.manifest.assets if item.engine_ref == engine_ref and item.verified
    ]
    if not verified:
        raise ValueError(
            "Native realization requires engine-verified target metadata for "
            f"'{engine_ref}'. Install/open the bridge and refresh project discovery."
        )
    verified.sort(
        key=lambda item: (
            item.kind not in {"prefab", "character_asset"},
            item.object_id,
        )
    )
    return verified[0]


def _selected_assets(
    studio: StudioService,
    record,
    bindings: list[StudioBindingSelection],
) -> dict[str, Any]:
    by_id = {item.object_id: item for item in studio.binding_assets(record)}
    result: dict[str, Any] = {}
    for binding in bindings:
        try:
            selected = by_id[binding.project_object_id]
        except KeyError as exc:
            raise ValueError(
                f"Binding '{binding.cir_id}' references an unknown project object."
            ) from exc
        result[binding.cir_id] = selected
    return result


class NativePerformanceRealizer:
    def __init__(
        self,
        *,
        studio: StudioService,
        performance: StudioPerformanceExecutor,
    ) -> None:
        self.studio = studio
        self.performance = performance

    def realize(
        self,
        *,
        run_id: str,
        project_id: str,
        project: Project,
        bindings: list[StudioBindingSelection],
    ) -> StudioBridgeCommand:
        record = self.studio.get_project(project_id)
        if not record.manifest.bridge_connected:
            raise ValueError(
                "Native generated-performance realization requires a live engine bridge."
            )

        run = self.performance.get_run(run_id)
        if run.project_id != project.id:
            raise ValueError(
                f"Performance run project '{run.project_id}' does not match CIR '{project.id}'."
            )
        bundle = load_performance_bundle(self.performance.bundle_bytes(run_id))
        if bundle.package.project_id != project.id:
            raise ValueError("Verified performance bundle project does not match the CIR.")

        manifest = self.studio.validate_bindings(project_id, project, bindings)
        conditioned_project = (
            self.studio.scene_conditioned_project(project_id, project, bindings)
            if record.manifest.scene_snapshot is not None
            else project
        )
        if not manifest.valid:
            raise ValueError(
                "Required character roles are not fully bound: "
                + ", ".join(manifest.unresolved_required_ids)
            )

        token = _run_token(run_id)
        if record.engine is StudioEngine.UNITY:
            importer_path, entry_point, omissions = self._stage_unity(
                record=record,
                project=conditioned_project,
                bindings=bindings,
                bundle=bundle,
                token=token,
            )
        else:
            importer_path, entry_point, omissions = self._stage_unreal(
                record=record,
                project=conditioned_project,
                bindings=bindings,
                bundle=bundle,
                token=token,
            )

        return self.studio.enqueue_bridge_command(
            project_id,
            StudioBridgeCommandRequest(
                command=StudioBridgeCommandType.RUN_IMPORTER,
                payload={
                    "importer_path": importer_path,
                    "entry_point": entry_point,
                    "performance_run_id": run_id,
                    "bundle_sha256": run.bundle_sha256,
                    "realization_policy": ("strict-body-camera-audio_degrade-facial-by-capability"),
                    "omitted_facial_actor_binding_ids": omissions,
                },
            ),
        )

    def _stage_unity(
        self,
        *,
        record,
        project: Project,
        bindings: list[StudioBindingSelection],
        bundle,
        token: str,
    ) -> tuple[str, str, list[str]]:
        selected = _selected_assets(self.studio, record, bindings)
        entities: list[UnityEntityAsset] = []
        for character in project.characters:
            asset = selected.get(character.id)
            if asset is None:
                raise ValueError(f"Character '{character.id}' is not bound.")
            if not asset.engine_ref.startswith("Assets/") or not asset.engine_ref.endswith(
                ".prefab"
            ):
                raise ValueError(f"Unity character '{character.id}' must bind to a project prefab.")
            entities.append(
                UnityEntityAsset(
                    source_entity_id=character.id,
                    prefab_path=asset.engine_ref,
                )
            )

        for environment in project.environment:
            asset = selected.get(environment.id)
            if asset is None:
                continue
            if not asset.engine_ref.startswith("Assets/") or not asset.engine_ref.endswith(
                ".prefab"
            ):
                continue
            entities.append(
                UnityEntityAsset(
                    source_entity_id=environment.id,
                    prefab_path=asset.engine_ref,
                )
            )

        root = f"Assets/CutSceneAI/Studio/{token}"
        plan = compile_unity_project(
            project,
            asset_map=UnityAssetMap(project_id=project.id, entities=entities),
            timeline_path=f"{root}/Timelines",
            scene_path=f"{root}/Scenes",
        )
        full_mapping = compile_unity_performance_bundle(
            bundle,
            export_plan=plan,
            target_path=f"{root}/GeneratedPerformance",
        )

        requested_facial_actor_ids = {item.actor_binding_id for item in full_mapping.facial_tracks}
        omitted_facial_actor_ids: set[str] = set()
        actors: list[UnityNativeActorTarget] = []
        for plan_actor in plan.sequences[0].actors:
            if plan_actor.kind.value != "character":
                continue
            source_id = plan_actor.source_entity_id
            selected_asset = selected[source_id]
            verified = _verified_asset_for_engine_ref(record, selected_asset.engine_ref)
            if not bool(verified.metadata.get("humanoid")):
                raise ValueError(
                    f"Unity target '{verified.display_name}' is not a verified valid Humanoid."
                )
            facial_renderer = str(verified.metadata.get("facial_renderer_path") or "")
            if plan_actor.binding_id in requested_facial_actor_ids:
                names = set(verified.metadata.get("blendshape_names") or [])
                missing = sorted(_ARKIT_BLENDSHAPES - names)
                if not facial_renderer or missing:
                    omitted_facial_actor_ids.add(plan_actor.binding_id)
                    facial_renderer = ""
            actors.append(
                UnityNativeActorTarget(
                    actor_binding_id=plan_actor.binding_id,
                    prefab_path=selected_asset.engine_ref,
                    animator_path=str(verified.metadata.get("animator_path") or ""),
                    facial_renderer_path=facial_renderer,
                )
            )

        mapping = full_mapping.model_copy(
            update={
                "facial_tracks": [
                    item
                    for item in full_mapping.facial_tracks
                    if item.actor_binding_id not in omitted_facial_actor_ids
                ]
            },
            deep=True,
        )

        version = str(record.manifest.engine_version or "")
        line_match = re.match(r"^(6000\.(?:0|3))", version)
        if line_match is None:
            raise ValueError(
                f"Unity native realization is validated only for 6000.0.x/6000.3.x; got '{version}'."
            )

        snapshot = record.manifest.scene_snapshot
        snapshot_object_by_id = (
            {item.object_id: item for item in snapshot.objects}
            if snapshot is not None
            else {}
        )
        scene_bindings: list[UnityNativeSceneBinding] = []
        for binding in bindings:
            scene_object = snapshot_object_by_id.get(binding.project_object_id)
            if scene_object is None:
                continue
            scene_bindings.append(
                UnityNativeSceneBinding(
                    source_entity_id=binding.cir_id,
                    source_object_id=scene_object.object_id,
                    hierarchy_path=scene_object.hierarchy_path,
                )
            )
        source_scene_asset_path = (
            snapshot.scene_ref
            if snapshot is not None
            and snapshot.scene_ref.startswith("Assets/")
            and snapshot.scene_ref.endswith(".unity")
            else None
        )

        target = UnityNativeRealizationTarget(
            target_engine_version=line_match.group(1),
            project_id=project.id,
            source_mapping_sha256=_mapping_sha(render_unity_performance_mapping(mapping)),
            timeline_asset_path=plan.sequences[0].timeline_asset_path,
            scene_asset_path=plan.sequences[0].scene_asset_path,
            source_scene_asset_path=source_scene_asset_path,
            scene_bindings=scene_bindings,
            actors=actors,
            omitted_facial_actor_binding_ids=sorted(omitted_facial_actor_ids),
            render=UnityNativeRenderSettings(
                output_directory=f"CutSceneAIEvidence/Studio/{token}/Unity/Frames"
            ),
        )
        package = compile_unity_native_performance_package(
            bundle,
            plan=plan,
            mapping=mapping,
            target=target,
        )
        script = render_unity_native_performance_script(package)
        importer_relative = "Assets/Editor/CutSceneAI/Generated/CutSceneAIGeneratedPerformance.cs"
        self._write_managed_text(
            Path(record.project_path) / importer_relative,
            script,
            marker="// Generated by CutSceneAI Unity Adapter",
        )

        audio_by_relative = {
            track.artifact.relative_path: track for track in bundle.package.audio_tracks
        }
        for mapped in mapping.audio_tracks:
            source = audio_by_relative[mapped.source_artifact.relative_path]
            data = bundle.artifact_files[source.artifact.relative_path]
            self._write_new_binary(
                Path(record.project_path) / mapped.target_audio_path,
                data,
            )
        return (
            importer_relative,
            "CutSceneAIGeneratedPerformance.Import",
            sorted(omitted_facial_actor_ids),
        )

    def _stage_unreal(
        self,
        *,
        record,
        project: Project,
        bindings: list[StudioBindingSelection],
        bundle,
        token: str,
    ) -> tuple[str, str, list[str]]:
        selected = _selected_assets(record, bindings)
        package_path = f"/Game/CutSceneAI/Studio/{token}/Sequences"
        base_plan = compile_unreal_project(project, package_path=package_path)
        sequence = base_plan.sequences[0]

        updated_actors = []
        for actor in sequence.actors:
            if actor.kind.value != "character":
                updated_actors.append(actor)
                continue
            selected_asset = selected.get(actor.source_entity_id)
            if selected_asset is None:
                raise ValueError(f"Character '{actor.source_entity_id}' is not bound.")
            verified = _verified_asset_for_engine_ref(record, selected_asset.engine_ref)
            if verified.kind != "character_asset":
                raise ValueError(
                    f"Unreal character '{actor.source_entity_id}' must bind to a verified "
                    "SkeletalMesh asset."
                )
            updated_actors.append(
                actor.model_copy(
                    update={
                        "mesh_type": UnrealMeshType.SKELETAL_MESH,
                        "actor_class_path": SKELETAL_MESH_ACTOR_CLASS_PATH,
                        "asset_path": verified.engine_ref,
                        "placeholder": False,
                        "placeholder_visual": None,
                    }
                )
            )

        plan = base_plan.model_copy(
            update={"sequences": [sequence.model_copy(update={"actors": updated_actors})]}
        )
        semantics = compile_semantics(project)
        full_mapping = compile_unreal_performance_bundle(
            bundle,
            export_plan=plan,
            semantics=semantics,
            target_path=f"/Game/CutSceneAI/Studio/{token}/GeneratedPerformance",
        )

        requested_facial_actor_ids = {item.actor_binding_id for item in full_mapping.facial_tracks}
        omitted_facial_actor_ids: set[str] = set()
        native_actors: list[UnrealNativeActorTarget] = []
        plan_actor_by_binding = {actor.binding_id: actor for actor in plan.sequences[0].actors}
        body_actor_ids = {item.actor_binding_id for item in full_mapping.body_tracks}
        for actor_binding_id in sorted(body_actor_ids | requested_facial_actor_ids):
            actor = plan_actor_by_binding[actor_binding_id]
            assert actor.asset_path is not None
            verified = _verified_asset_for_engine_ref(record, actor.asset_path)
            morph_names = set(verified.metadata.get("morph_target_names") or [])
            needs_face = actor_binding_id in requested_facial_actor_ids
            if needs_face:
                missing = sorted(_ARKIT_BLENDSHAPES - morph_names)
                if missing:
                    omitted_facial_actor_ids.add(actor_binding_id)
                    needs_face = False
            native_actors.append(
                UnrealNativeActorTarget(
                    actor_binding_id=actor_binding_id,
                    skeletal_mesh_path=actor.asset_path,
                    require_arkit_52_morph_targets=needs_face,
                )
            )

        mapping = full_mapping.model_copy(
            update={
                "facial_tracks": [
                    item
                    for item in full_mapping.facial_tracks
                    if item.actor_binding_id not in omitted_facial_actor_ids
                ]
            },
            deep=True,
        )

        current_map = str(record.manifest.current_scene or "")
        if not current_map.startswith("/Game/"):
            raise ValueError(
                "Unreal bridge must report an active /Game map before native realization."
            )
        version_text = str(record.manifest.engine_version or "")
        version_match = re.search(r"\b(5\.8(?:\.\d+)?)", version_text)
        if version_match is None:
            raise ValueError(
                f"Unreal native realization is validated only for 5.8.x; got '{version_text}'."
            )

        target = UnrealNativeRealizationTarget(
            target_engine_version=version_match.group(1),
            project_id=project.id,
            source_mapping_sha256=_mapping_sha(render_unreal_performance_mapping(mapping)),
            sequence_package_path=plan.sequences[0].package_path,
            sequence_asset_name=plan.sequences[0].asset_name,
            actors=native_actors,
            omitted_facial_actor_binding_ids=sorted(omitted_facial_actor_ids),
            render=UnrealNativeRenderSettings(
                map_path=current_map,
                output_directory=f"CutSceneAI/Studio/{token}/Unreal/Frames",
            ),
        )
        package = compile_unreal_native_performance_package(
            bundle,
            plan=plan,
            mapping=mapping,
            target=target,
            semantics=semantics,
        )
        script = render_unreal_native_import_script(package)
        importer_relative = (
            f"Saved/CutSceneAI/NativeBridge/{token}/Scripts/cutsceneai-unreal-native-import.py"
        )
        importer = Path(record.project_path) / importer_relative
        self._write_managed_text(
            importer,
            script,
            marker='"""Generated by CutSceneAI Unreal Adapter',
        )

        root = importer.parent.parent
        for track in bundle.package.audio_tracks:
            data = bundle.artifact_files[track.artifact.relative_path]
            self._write_new_binary(
                root / "Audio" / track.artifact.relative_path,
                data,
            )
        return importer_relative, "import", sorted(omitted_facial_actor_ids)

    @staticmethod
    def _write_new_binary(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            existing = path.read_bytes()
            if existing == data:
                return
            raise ValueError(f"Refusing to replace existing generated payload: {path}")
        path.write_bytes(data)

    @staticmethod
    def _write_managed_text(path: Path, content: str, *, marker: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            existing = path.read_text(encoding="utf-8", errors="ignore")
            if existing == content:
                return
            if not existing.startswith(marker):
                raise ValueError(f"Refusing to replace unmanaged generated importer: {path}")
        path.write_text(content, encoding="utf-8", newline="\n")
