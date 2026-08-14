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
    UNITY_FIXTURE_PREFAB,
    make_unity_native_export_plan,
)
from cutsceneai_unity import (
    UNITY_NATIVE_EDITOR_SCRIPT_FILENAME,
    UNITY_NATIVE_RUNNER_FILENAME,
    UNITY_NATIVE_TARGET_SCHEMA_ID,
    UnityNativeActorTarget,
    UnityNativeRealizationTarget,
    UnityNativeRenderSettings,
    compile_performance_bundle,
    compile_unity_native_performance_package,
    render_unity_native_performance_package,
    render_unity_native_performance_script,
    render_unity_native_runner_script,
    render_unity_native_target,
    render_unity_performance_mapping,
    render_unity_plan,
    unity_native_target_json_schema,
)
from cutsceneai_unity.native_cli import (
    compile_native_harness,
    main as native_cli_main,
)


def _components() -> tuple[
    GeneratedPerformanceFixture,
    Any,
    Any,
    UnityNativeRealizationTarget,
]:
    fixture = make_generated_performance_fixture()
    plan = make_unity_native_export_plan(fixture)
    mapping = compile_performance_bundle(fixture.bundle, export_plan=plan)
    target = UnityNativeRealizationTarget(
        project_id=mapping.project_id,
        source_mapping_sha256=hashlib.sha256(
            render_unity_performance_mapping(mapping).encode()
        ).hexdigest(),
        timeline_asset_path=plan.sequences[0].timeline_asset_path,
        scene_asset_path=plan.sequences[0].scene_asset_path,
        actors=[
            UnityNativeActorTarget(
                actor_binding_id="actor:mina",
                prefab_path=UNITY_FIXTURE_PREFAB,
                animator_path="",
                facial_renderer_path="Geometry/Face",
            )
        ],
    )
    return fixture, plan, mapping, target


def _package():
    fixture, plan, mapping, target = _components()
    return compile_unity_native_performance_package(
        fixture.bundle,
        plan=plan,
        mapping=mapping,
        target=target,
    )


def test_compiles_exact_bundle_and_renders_strict_unity_editor_harness() -> None:
    package = _package()
    script = render_unity_native_performance_script(package)
    runner = render_unity_native_runner_script(package)

    assert package.mapping.body_tracks[0].root_translation_space == (
        "target-reference-pose-offset"
    )
    assert package.mapping.body_tracks[0].rotation_space == (
        "target-reference-pose-relative-parent-local"
    )
    for token in (
        'Application.unityVersion.StartsWith("6000.0"',
        'timelinePackage.version != "1.8.12"',
        "animator.GetBoneTransform",
        "SetPositionAndRotation",
        "instance.transform.localScale",
        "reference * QuaternionValueOf",
        "frame.weights[curveIndex] * 100.0f",
        "timeline.CreateTrack<AnimationTrack>(animationRoots",
        "track.GetChildTracks()",
        "lifecycle.import_process_id == ProcessId",
        "camera.Render()",
        "Refusing to replace existing generated asset",
    ):
        assert token in script
    assert runner.count("& $UnityEditor") == 2
    assert "Get-Content -Raw -Path $importLog, $readbackLog" in runner
    assert "collect-native-evidence.py" in runner
    assert (
        hashlib.sha256(render_performance_bundle(package.bundle)).hexdigest() in runner
    )
    assert script == render_unity_native_performance_script(package)
    assert runner == render_unity_native_runner_script(package)


def test_native_target_schema_and_serialization_are_deterministic() -> None:
    _, _, _, target = _components()
    schema = unity_native_target_json_schema()
    rendered = render_unity_native_target(target)

    assert schema["$id"] == UNITY_NATIVE_TARGET_SCHEMA_ID
    assert schema["additionalProperties"] is False
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(json.loads(rendered))
    assert json.loads(rendered) == target.model_dump(mode="json")
    assert rendered == render_unity_native_target(target)


def test_native_harness_archive_is_deterministic_and_preserves_inputs() -> None:
    package = _package()
    collector = render_native_evidence_collector_script()
    rendered = render_unity_native_performance_package(
        package, evidence_collector_script=collector
    )

    assert rendered == render_unity_native_performance_package(
        package, evidence_collector_script=collector
    )
    with ZipFile(BytesIO(rendered)) as archive:
        names = archive.namelist()
        assert len(names) == len(set(names))
        assert {
            f"Scripts/{UNITY_NATIVE_EDITOR_SCRIPT_FILENAME}",
            f"Scripts/{UNITY_NATIVE_RUNNER_FILENAME}",
            "Scripts/collect-native-evidence.py",
            "mapping.json",
            "plan.json",
            "target.json",
            "performance.bundle.zip",
            "Payload/Assets/CutSceneAI/GeneratedPerformance/Audio/DialogueFixtureMina.wav",
        } == set(names)
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
    }
    paths["bundle"].write_bytes(render_performance_bundle(package.bundle))
    paths["plan"].write_text(render_unity_plan(package.plan), encoding="utf-8")
    paths["mapping"].write_text(
        render_unity_performance_mapping(package.mapping), encoding="utf-8"
    )
    paths["target"].write_text(
        render_unity_native_target(package.target), encoding="utf-8"
    )
    output = tmp_path / "result" / "unity-native.zip"

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
            output_path=output,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("mapping", "not the deterministic mapping"),
        ("mapping_sha", "mapping SHA-256"),
        ("project", "different projects"),
        ("timeline", "paths or scene"),
        ("actors", "do not exactly match"),
        ("prefab", "same non-placeholder prefab"),
        ("placeholder", "same non-placeholder prefab"),
    ],
)
def test_compile_rejects_native_target_or_plan_drift(
    mutation: str, message: str
) -> None:
    fixture, plan, mapping, target = _components()
    if mutation == "mapping":
        mapping = mapping.model_copy(deep=True)
        mapping.camera_tracks[0].sensor_width_mm = 40.0
    elif mutation == "mapping_sha":
        target = target.model_copy(update={"source_mapping_sha256": "f" * 64})
    elif mutation == "project":
        target = target.model_copy(update={"project_id": "other-project"})
    elif mutation == "timeline":
        target = target.model_copy(
            update={"timeline_asset_path": "Assets/CutSceneAI/Timelines/Other.playable"}
        )
    elif mutation == "actors":
        target = target.model_copy(update={"actors": []})
    elif mutation == "prefab":
        target = target.model_copy(deep=True)
        target.actors[0].prefab_path = "Assets/CutSceneAI/Characters/Other.prefab"
    elif mutation == "placeholder":
        plan = plan.model_copy(deep=True)
        plan.sequences[0].actors[0].placeholder = True

    with pytest.raises(ValueError, match=message):
        compile_unity_native_performance_package(
            fixture.bundle,
            plan=plan,
            mapping=mapping,
            target=target,
        )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {
                "actors": [
                    {
                        "actor_binding_id": "actor:mina",
                        "prefab_path": UNITY_FIXTURE_PREFAB,
                        "facial_renderer_path": "../Face",
                    }
                ]
            },
            "normalized relative object path",
        ),
        (
            {"render": {"output_directory": "../Frames"}},
            "normalized relative object path",
        ),
        (
            {"render": {"output_directory": "..\\Frames"}},
            "normalized relative object path",
        ),
        (
            {
                "timeline_asset_path": "Assets/../Escape.playable",
            },
            "normalized Unity Assets path",
        ),
        (
            {
                "actors": [
                    {
                        "actor_binding_id": "actor:mina",
                        "prefab_path": "Assets/../Mina.prefab",
                        "facial_renderer_path": "Face",
                    }
                ]
            },
            "normalized Unity Assets path",
        ),
        (
            {
                "actors": [
                    {
                        "actor_binding_id": "actor:mina",
                        "prefab_path": UNITY_FIXTURE_PREFAB,
                        "facial_renderer_path": "Face",
                    },
                    {
                        "actor_binding_id": "actor:mina",
                        "prefab_path": UNITY_FIXTURE_PREFAB,
                        "facial_renderer_path": "Face",
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
        UnityNativeRealizationTarget.model_validate(value)


def test_render_settings_enforce_png_and_safe_dimensions() -> None:
    with pytest.raises(ValidationError):
        UnityNativeRenderSettings(width=32)
    with pytest.raises(ValidationError):
        UnityNativeRenderSettings.model_validate({"image_format": "jpg"})
