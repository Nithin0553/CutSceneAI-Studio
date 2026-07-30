from __future__ import annotations

import json
from dataclasses import dataclass
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from cutsceneai_assets import (
    AssetIndex,
    AssetResolutionPlan,
    render_asset_index,
    render_asset_resolution_plan,
    resolve_project,
    validate_resolution_plan,
)
from cutsceneai_cir import Project

from .compiler import DEFAULT_PACKAGE_PATH, compile_project
from .models import UnrealExportPlan
from .rendering import render_unreal_import_script
from .serialization import render_unreal_plan

_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


@dataclass(frozen=True)
class UnrealEnvironmentImportPackage:
    project: Project
    asset_index: AssetIndex
    asset_resolution: AssetResolutionPlan
    plan: UnrealExportPlan


def compile_environment_package(
    project: Project,
    asset_index: AssetIndex,
    *,
    asset_resolution: AssetResolutionPlan | None = None,
    sequence_package_path: str = DEFAULT_PACKAGE_PATH,
) -> UnrealEnvironmentImportPackage:
    """Resolve environment assets and compile a traceable Unreal 5.8 import package."""

    if asset_resolution is None:
        asset_resolution = resolve_project(project, asset_index)
    else:
        validate_resolution_plan(project, asset_index, asset_resolution)
    plan = compile_project(
        project,
        package_path=sequence_package_path,
        asset_index=asset_index,
        asset_resolution=asset_resolution,
    )
    return UnrealEnvironmentImportPackage(
        project=project,
        asset_index=asset_index,
        asset_resolution=asset_resolution,
        plan=plan,
    )


def _write_entry(archive: ZipFile, path: str, data: bytes) -> None:
    entry = ZipInfo(path, date_time=_ZIP_TIMESTAMP)
    entry.compress_type = ZIP_DEFLATED
    entry.external_attr = 0o644 << 16
    archive.writestr(entry, data)


def render_unreal_environment_import_package(
    package: UnrealEnvironmentImportPackage,
) -> bytes:
    """Render a deterministic ZIP with resolution evidence and an Unreal importer."""

    validate_resolution_plan(
        package.project,
        package.asset_index,
        package.asset_resolution,
    )
    if package.plan.asset_resolution != package.asset_resolution:
        raise ValueError(
            "Unreal plan does not contain the package Asset Resolution plan."
        )
    package_paths = {sequence.package_path for sequence in package.plan.sequences}
    if len(package_paths) != 1:
        raise ValueError(
            "Unreal environment package must use one sequence package path."
        )
    expected_plan = compile_project(
        package.project,
        package_path=next(iter(package_paths)),
        asset_index=package.asset_index,
        asset_resolution=package.asset_resolution,
    )
    if package.plan != expected_plan:
        raise ValueError(
            "Unreal plan does not match the package CIR, Asset Index, and resolution."
        )

    project_json = (
        json.dumps(
            package.project.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        _write_entry(
            archive,
            "cutsceneai-unreal-import.py",
            render_unreal_import_script(package.plan).encode("utf-8"),
        )
        _write_entry(
            archive,
            "unreal.plan.json",
            render_unreal_plan(package.plan).encode("utf-8"),
        )
        _write_entry(archive, "project.cir.json", project_json.encode("utf-8"))
        _write_entry(
            archive,
            "asset.index.json",
            render_asset_index(package.asset_index).encode("utf-8"),
        )
        _write_entry(
            archive,
            "asset.resolution.json",
            render_asset_resolution_plan(package.asset_resolution).encode("utf-8"),
        )
    return output.getvalue()
