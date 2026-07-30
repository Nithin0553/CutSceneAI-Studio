from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from typing import ClassVar

from cutsceneai_assets import AssetIndex, AssetKind
from cutsceneai_unreal import render_unreal_asset_index_script


class _AssetClassPath:
    def __init__(self, asset_name: str) -> None:
        self.asset_name = asset_name


class _AssetData:
    def __init__(
        self,
        package_name: str,
        asset_name: str,
        class_name: str,
        *,
        redirector: bool = False,
        is_asset: bool = True,
    ) -> None:
        self.package_name = package_name
        self.asset_name = asset_name
        self.asset_class_path = _AssetClassPath(class_name)
        self._redirector = redirector
        self._is_asset = is_asset

    def is_redirector(self) -> bool:
        return self._redirector

    def is_u_asset(self) -> bool:
        return self._is_asset


def test_indexer_is_syntax_valid_read_only_and_explicit_about_curation() -> None:
    script = render_unreal_asset_index_script()

    compile(script, "cutsceneai-unreal-index.py", "exec")
    assert "AssetRegistryHelpers.get_asset_registry()" in script
    assert 'get_assets_by_path("/Game", True, True)' in script
    assert '"kind": "environment_prop"' in script
    assert "Curate aliases, location_terms, priority" in script
    assert "save_asset" not in script
    assert "delete_asset" not in script
    assert "rename_asset" not in script


def test_indexer_writes_a_deterministic_static_mesh_inventory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    asset_data = [
        _AssetData("/Game/Props/SM_Table", "SM_Table", "StaticMesh"),
        _AssetData("/Game/Characters/SKM_Mina", "SKM_Mina", "SkeletalMesh"),
        _AssetData(
            "/Game/Props/SM_Old",
            "SM_Old",
            "StaticMesh",
            redirector=True,
        ),
        _AssetData(
            "/Game/Maps/L_Office",
            "L_Office",
            "World",
            is_asset=False,
        ),
        _AssetData("/Game/Sets/SM_Office", "SM_Office", "StaticMesh"),
    ]

    class Registry:
        calls: ClassVar[list[tuple[str, bool, bool]]] = []

        @classmethod
        def get_assets_by_path(
            cls,
            path: str,
            recursive: bool,
            include_only_on_disk_assets: bool,
        ):
            cls.calls.append((path, recursive, include_only_on_disk_assets))
            return list(reversed(asset_data))

    class AssetRegistryHelpers:
        @staticmethod
        def get_asset_registry():
            return Registry()

    class Paths:
        @staticmethod
        def get_project_file_path() -> str:
            return str(tmp_path / "CutSceneAIStudio.uproject")

        @staticmethod
        def project_saved_dir() -> str:
            return str(tmp_path / "Saved")

        @staticmethod
        def convert_relative_path_to_full(path: str) -> str:
            return path

    logs: list[str] = []
    warnings: list[str] = []
    unreal = ModuleType("unreal")
    unreal.AssetRegistryHelpers = AssetRegistryHelpers
    unreal.Paths = Paths
    unreal.log = logs.append
    unreal.log_warning = warnings.append
    monkeypatch.setitem(sys.modules, "unreal", unreal)

    namespace = {"__name__": "cutsceneai_generated_indexer"}
    exec(  # noqa: S102 - execute the generated indexer under a fake Unreal API.
        render_unreal_asset_index_script(),
        namespace,
    )
    output_path = namespace["build_asset_index"]()

    assert output_path == (
        tmp_path / "Saved" / "CutSceneAI" / "unreal-project.asset-index.json"
    )
    index = AssetIndex.model_validate_json(output_path.read_text(encoding="utf-8"))
    assert Registry.calls == [("/Game", True, True)]
    assert [asset.asset_uri for asset in index.assets] == [
        "/Game/Props/SM_Table.SM_Table",
        "/Game/Sets/SM_Office.SM_Office",
    ]
    assert all(asset.kind is AssetKind.ENVIRONMENT_PROP for asset in index.assets)
    assert index.name == "CutSceneAIStudio Static Mesh Assets"
    assert "indexed 2 Static Mesh assets" in logs[0]
    assert "default to environment_prop" in warnings[0]
