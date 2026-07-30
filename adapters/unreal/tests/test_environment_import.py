import json
from io import BytesIO
from zipfile import ZipFile

import pytest
from cutsceneai_assets import AssetIndex, AssetResolutionPlan
from cutsceneai_cir import Project
from cutsceneai_unreal import (
    UnrealEnvironmentImportPackage,
    compile_environment_package,
    render_unreal_environment_import_package,
)


def test_environment_package_is_deterministic_and_self_contained(
    cir_project: Project,
    asset_index: AssetIndex,
) -> None:
    package = compile_environment_package(cir_project, asset_index)

    first = render_unreal_environment_import_package(package)
    second = render_unreal_environment_import_package(package)

    assert first == second
    with ZipFile(BytesIO(first)) as archive:
        assert archive.namelist() == [
            "cutsceneai-unreal-import.py",
            "unreal.plan.json",
            "project.cir.json",
            "asset.index.json",
            "asset.resolution.json",
        ]
        script = archive.read("cutsceneai-unreal-import.py").decode("utf-8")
        compile(script, "cutsceneai-unreal-import.py", "exec")
        plan = json.loads(archive.read("unreal.plan.json"))
        resolution = AssetResolutionPlan.model_validate_json(
            archive.read("asset.resolution.json")
        )

    assert plan["adapter_version"] == "0.7.0"
    assert plan["asset_resolution"] == resolution.model_dump(mode="json")
    assert resolution.asset_index_id == asset_index.id
    assert all(
        item["resolution_status"] == "matched"
        for item in plan["sequences"][0]["actors"]
        if item["kind"] == "environment"
    )
    assert plan["sequences"][0]["set_pieces"][0]["placeholder"] is False


def test_environment_package_respects_custom_sequence_path(
    cir_project: Project,
    asset_index: AssetIndex,
) -> None:
    package = compile_environment_package(
        cir_project,
        asset_index,
        sequence_package_path="/Game/Sequences/Generated",
    )

    assert package.plan.sequences[0].package_path == "/Game/Sequences/Generated"


def test_environment_package_rejects_plan_resolution_mismatch(
    cir_project: Project,
    asset_index: AssetIndex,
) -> None:
    package = compile_environment_package(cir_project, asset_index)
    plan = package.plan.model_copy(deep=True)
    plan.asset_resolution = None
    tampered = UnrealEnvironmentImportPackage(
        project=package.project,
        asset_index=package.asset_index,
        asset_resolution=package.asset_resolution,
        plan=plan,
    )

    with pytest.raises(ValueError, match="does not contain"):
        render_unreal_environment_import_package(tampered)


def test_environment_package_rejects_other_plan_tampering(
    cir_project: Project,
    asset_index: AssetIndex,
) -> None:
    package = compile_environment_package(cir_project, asset_index)
    plan = package.plan.model_copy(deep=True)
    plan.project_name = "Tampered"
    tampered = UnrealEnvironmentImportPackage(
        project=package.project,
        asset_index=package.asset_index,
        asset_resolution=package.asset_resolution,
        plan=plan,
    )

    with pytest.raises(ValueError, match="does not match"):
        render_unreal_environment_import_package(tampered)
