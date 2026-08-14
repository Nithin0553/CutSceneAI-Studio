from __future__ import annotations

import hashlib
from io import BytesIO
import json
from pathlib import Path, PurePosixPath
from typing import Any
from zipfile import ZipFile

import pytest
from cutsceneai_performance import (
    render_native_evidence_collector_script,
    render_performance_bundle,
)
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from cutsceneai_test_support.generated_performance import (
    GeneratedPerformanceFixture,
    make_generated_performance_fixture,
)
from cutsceneai_test_support.native_performance import (
    UNREAL_FIXTURE_MESH,
    make_unreal_native_export_plan,
)
from cutsceneai_unreal import (
    UNREAL_NATIVE_IMPORT_FILENAME,
    UNREAL_NATIVE_READBACK_FILENAME,
    UNREAL_NATIVE_RENDER_FILENAME,
    UNREAL_NATIVE_RUNNER_FILENAME,
    UNREAL_NATIVE_TARGET_SCHEMA_ID,
    UnrealNativeActorTarget,
    UnrealNativeRealizationTarget,
    UnrealNativeRenderSettings,
    compile_performance_bundle,
    compile_unreal_native_performance_package,
    render_unreal_native_import_script,
    render_unreal_native_performance_package,
    render_unreal_native_readback_script,
    render_unreal_native_render_script,
    render_unreal_native_runner_script,
    render_unreal_native_target,
    render_unreal_performance_mapping,
    render_unreal_plan,
    unreal_native_target_json_schema,
)
from cutsceneai_unreal.native_cli import (
    compile_native_harness,
    main as native_cli_main,
)


def _components() -> tuple[
    GeneratedPerformanceFixture,
    Any,
    Any,
    UnrealNativeRealizationTarget,
]:
    fixture = make_generated_performance_fixture()
    plan = make_unreal_native_export_plan(fixture)
    mapping = compile_performance_bundle(
        fixture.bundle,
        export_plan=plan,
        semantics=fixture.semantics,
    )
    target = UnrealNativeRealizationTarget(
        project_id=mapping.project_id,
        source_mapping_sha256=hashlib.sha256(
            render_unreal_performance_mapping(mapping).encode()
        ).hexdigest(),
        sequence_package_path=plan.sequences[0].package_path,
        sequence_asset_name=plan.sequences[0].asset_name,
        actors=[
            UnrealNativeActorTarget(
                actor_binding_id="actor:mina",
                skeletal_mesh_path=UNREAL_FIXTURE_MESH,
            )
        ],
        render=UnrealNativeRenderSettings(
            map_path="/Game/CutSceneAI/Maps/TestStage.TestStage"
        ),
    )
    return fixture, plan, mapping, target


def _package():
    fixture, plan, mapping, target = _components()
    return compile_unreal_native_performance_package(
        fixture.bundle,
        plan=plan,
        mapping=mapping,
        target=target,
        semantics=fixture.semantics,
    )


def test_compiles_exact_bundle_and_renders_three_phase_unreal_harness() -> None:
    package = _package()
    importer = render_unreal_native_import_script(package)
    readback = render_unreal_native_readback_script(package)
    renderer = render_unreal_native_render_script(package)
    runner = render_unreal_native_runner_script(package)

    for name, script in (
        (UNREAL_NATIVE_IMPORT_FILENAME, importer),
        (UNREAL_NATIVE_READBACK_FILENAME, readback),
        (UNREAL_NATIVE_RENDER_FILENAME, renderer),
    ):
        compile(script, name, "exec")
    assert package.mapping.body_tracks[0].root_translation_space == (
        "target-reference-pose-offset"
    )
    assert package.mapping.body_tracks[0].rotation_space == (
        "target-reference-pose-relative-parent-local"
    )
    for token in (
        'version.startswith("5.8.0")',
        "AnimPoseExtensions.get_reference_pose",
        "AnimPoseExtensions.get_ref_bone_pose",
        "_quat_multiply(reference_rotation",
        "mesh.get_all_morph_target_names()",
        "AnimationLibrary.add_float_curve_keys",
        "MovieSceneSkeletalAnimationTrack",
        "MovieSceneCameraCutTrack",
        "Refusing to replace existing Unreal assets",
    ):
        assert token in importer
    assert 'lifecycle["import_process_id"] == os.getpid()' in readback
    assert 'lifecycle["readback_process_id"] = os.getpid()' in readback
    for token in (
        "MoviePipelineQueue",
        "MoviePipelineOutputSetting",
        "MoviePipelineDeferredPassBase",
        "MoviePipelineImageSequenceOutput_PNG",
        "MoviePipelinePIEExecutor",
        "MoviePipelineQueueSubsystem",
        "SoftObjectPath(path_string=",
        "DirectoryPath(path=",
        "IntPoint(x=",
    ):
        assert token in renderer
    assert runner.count("Invoke-CutSceneAIUnreal (Join-Path") == 3
    assert "Get-Content -Raw -Path $importLog, $readbackLog, $renderLog" in runner
    assert (
        hashlib.sha256(render_performance_bundle(package.bundle)).hexdigest() in runner
    )


def test_native_target_schema_and_serialization_are_deterministic() -> None:
    _, _, _, target = _components()
    schema = unreal_native_target_json_schema()
    rendered = render_unreal_native_target(target)

    assert schema["$id"] == UNREAL_NATIVE_TARGET_SCHEMA_ID
    assert schema["additionalProperties"] is False
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(json.loads(rendered))
    assert json.loads(rendered) == target.model_dump(mode="json")
    assert rendered == render_unreal_native_target(target)


def test_native_harness_archive_is_deterministic_and_preserves_inputs() -> None:
    package = _package()
    collector = render_native_evidence_collector_script()
    rendered = render_unreal_native_performance_package(
        package, evidence_collector_script=collector
    )

    assert rendered == render_unreal_native_performance_package(
        package, evidence_collector_script=collector
    )
    with ZipFile(BytesIO(rendered)) as archive:
        names = archive.namelist()
        expected = {
            f"Scripts/{UNREAL_NATIVE_IMPORT_FILENAME}",
            f"Scripts/{UNREAL_NATIVE_READBACK_FILENAME}",
            f"Scripts/{UNREAL_NATIVE_RENDER_FILENAME}",
            f"Scripts/{UNREAL_NATIVE_RUNNER_FILENAME}",
            "Scripts/collect-native-evidence.py",
            "mapping.json",
            "plan.json",
            "target.json",
            "semantics.json",
            "performance.bundle.zip",
        }
        expected.update(
            f"Audio/{track.artifact.relative_path}"
            for track in package.bundle.package.audio_tracks
        )
        assert set(names) == expected
        assert len(names) == len(set(names))
        assert archive.read("performance.bundle.zip") == render_performance_bundle(
            package.bundle
        )
        assert archive.read("Scripts/collect-native-evidence.py").decode() == collector
        assert all(
            info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist()
        )
        for name in names:
            path = PurePosixPath(name)
            assert not path.is_absolute()
            assert ".." not in path.parts


def test_installed_cli_compiles_once_without_replacement(tmp_path: Path) -> None:
    package = _package()
    paths = {
        "bundle": tmp_path / "performance.bundle.zip",
        "plan": tmp_path / "plan.json",
        "mapping": tmp_path / "mapping.json",
        "target": tmp_path / "target.json",
        "semantics": tmp_path / "semantics.json",
    }
    paths["bundle"].write_bytes(render_performance_bundle(package.bundle))
    paths["plan"].write_text(render_unreal_plan(package.plan), encoding="utf-8")
    paths["mapping"].write_text(
        render_unreal_performance_mapping(package.mapping), encoding="utf-8"
    )
    paths["target"].write_text(
        render_unreal_native_target(package.target), encoding="utf-8"
    )
    paths["semantics"].write_text(
        json.dumps(package.semantics.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "result" / "unreal-native.zip"

    result = native_cli_main(
        [
            "--bundle",
            str(paths["bundle"]),
            "--plan",
            str(paths["plan"]),
            "--mapping",
            str(paths["mapping"]),
            "--target",
            str(paths["target"]),
            "--semantics",
            str(paths["semantics"]),
            "--output",
            str(output),
        ]
    )

    assert result == 0
    with ZipFile(output) as archive:
        assert archive.read("performance.bundle.zip") == paths["bundle"].read_bytes()
    with pytest.raises(FileExistsError, match="refusing to replace"):
        compile_native_harness(
            bundle_path=paths["bundle"],
            plan_path=paths["plan"],
            mapping_path=paths["mapping"],
            target_path=paths["target"],
            semantics_path=paths["semantics"],
            output_path=output,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("mapping", "not the deterministic mapping"),
        ("mapping_sha", "mapping SHA-256"),
        ("project", "different projects"),
        ("sequence", "paths or scene"),
        ("actors", "do not exactly match"),
        ("mesh", "same non-placeholder skeletal mesh"),
        ("placeholder", "same non-placeholder skeletal mesh"),
    ],
)
def test_compile_rejects_native_target_plan_or_semantic_drift(
    mutation: str, message: str
) -> None:
    fixture, plan, mapping, target = _components()
    semantics = fixture.semantics.model_copy(deep=True)
    if mutation == "mapping":
        mapping = mapping.model_copy(deep=True)
        mapping.camera_tracks[0].sensor_width_mm = 40.0
    elif mutation == "mapping_sha":
        target = target.model_copy(update={"source_mapping_sha256": "f" * 64})
    elif mutation == "project":
        target = target.model_copy(update={"project_id": "other-project"})
    elif mutation == "sequence":
        target = target.model_copy(update={"sequence_asset_name": "LS_Other"})
    elif mutation == "actors":
        target = target.model_copy(update={"actors": []})
    elif mutation == "mesh":
        target = target.model_copy(deep=True)
        target.actors[
            0
        ].skeletal_mesh_path = "/Game/CutSceneAI/Characters/SK_Other.SK_Other"
    elif mutation == "placeholder":
        plan = plan.model_copy(deep=True)
        plan.sequences[0].actors[0].placeholder = True
    with pytest.raises(ValueError, match=message):
        compile_unreal_native_performance_package(
            fixture.bundle,
            plan=plan,
            mapping=mapping,
            target=target,
            semantics=semantics,
        )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {"render": {"map_path": "/Game/Map", "output_directory": "../Frames"}},
            "normalized relative path",
        ),
        (
            {
                "render": {
                    "map_path": "/Game/Map",
                    "output_directory": "..\\Frames",
                }
            },
            "normalized relative path",
        ),
        (
            {
                "actors": [
                    {
                        "actor_binding_id": "actor:mina",
                        "skeletal_mesh_path": UNREAL_FIXTURE_MESH,
                    },
                    {
                        "actor_binding_id": "actor:mina",
                        "skeletal_mesh_path": UNREAL_FIXTURE_MESH,
                    },
                ]
            },
            "unique actor_binding_id",
        ),
    ],
)
def test_native_target_rejects_unsafe_paths_and_duplicate_bindings(
    payload: dict[str, Any], message: str
) -> None:
    _, _, _, target = _components()
    value = target.model_dump(mode="json")
    value.update(payload)

    with pytest.raises(ValidationError, match=message):
        UnrealNativeRealizationTarget.model_validate(value)


def test_render_settings_enforce_png_and_safe_dimensions() -> None:
    with pytest.raises(ValidationError):
        UnrealNativeRenderSettings(map_path="/Game/CutSceneAI/Maps/Test.Test", width=32)
    with pytest.raises(ValidationError):
        UnrealNativeRenderSettings.model_validate(
            {
                "map_path": "/Game/CutSceneAI/Maps/Test.Test",
                "image_format": "jpg",
            }
        )
