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
    UnityNativeSceneBinding,
    compile_performance_bundle,
    compile_unity_native_performance_package,
    render_unity_body_stream_runtime_script,
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
    runtime = render_unity_body_stream_runtime_script()
    runner = render_unity_native_runner_script(package)

    assert package.mapping.body_tracks[0].root_translation_space == (
        "actor-motion-root-local-offset"
    )
    assert package.mapping.body_tracks[0].rotation_space == (
        "target-reference-pose-relative-parent-local"
    )
    for token in (
        'version.StartsWith("6000.0"',
        'version.StartsWith("6000.3"',
        'timelinePackage.version != "1.8.12"',
        "animator.GetBoneTransform",
        "IsRequiredHumanoidBone",
        "HumanTrait.RequiredBone",
        "Required Humanoid bone is not mapped",
        "mapped = false",
        "mapped = true",
        "EvidenceRoot(Target target)",
        "ValidateClipBindingPaths",
        "ValidateBodyClipSampling",
        "BodyTrackHasSourceMotion",
        "animator.avatarRoot",
        "AnimationMode.BeginSampling",
        "AnimationMode.SampleAnimationClip",
        "ConfigureBodyStreamDriver",
        "CutSceneAIBodyStreamDriver.PoseFrame",
        "driver.RebuildGraph()",
        "EvaluateBodyStreamDrivers(director, director.time)",
        "director.SetGenericBinding(track, AnimatorComponentFor(actors[face.actor_binding_id]",
        "actorFaceTracks.Length == 0",
        "required facial blendshapes for",
        "SetPositionAndRotation",
        "instance.transform.localScale",
        "ReferenceComponentRotation(animator, transform)",
        "Quaternion.Inverse(animator.avatarRoot.rotation) * bone.rotation",
        "animator.avatarRoot.InverseTransformPoint(transform.position)",
        "CanonicalReferenceDirectionUnity",
        "TargetReferenceDirectionParentLocal",
        "Quaternion.FromToRotation",
        "canonicalToTargetParentBasis",
        "return targetDelta * referenceLocal",
        "AnimationUtility.CalculateTransformPath",
        'typeof(Transform), "m_LocalRotation.x"',
        'typeof(Transform), "m_LocalRotation.w"',
        "direct target-bone",
        "AnimatorComponentFor",
        "AvatarBuilder.BuildGenericAvatar",
        "GenericAvatarPath",
        "genericAvatar.isValid",
        "genericAvatar.isHuman",
        "AssetDatabase.CreateAsset(genericAvatar, genericAvatarPath)",
        "animator.runtimeAnimatorController = null",
        "animator.Rebind()",
        "animator.Update(0.0f)",
        "ResolveBodyTransforms",
        "not-applicable-direct-bone",
        "canonical_reference_direction",
        "target_reference_direction_parent_local",
        "canonical_to_target_parent_basis",
        "private sealed class RetargetLimb",
        "CaptureRetargetLimb",
        '"left_leg"',
        '"right_leg"',
        '"left_arm"',
        '"right_arm"',
        "upper_length_m",
        "lower_length_m",
        "rest_bend_direction_component",
        "rest_bend_direction_defined",
        'profile_version = "0.2.0"',
        'retargeting_method = "geometry-profile-v0.2+rest-direction-parent-basis-v1"',
        ".GroupBy(item => item.actor_binding_id)",
        "private static TwoBoneGeometrySolution SolveTwoBoneGeometry",
        "TrySourceBendDirection",
        "FirstSourceBendDirection",
        "CaptureLegGeometrySolverDiagnostic",
        "source_extension_ratio",
        "source_bend_direction_defined",
        "reach_was_clamped",
        '"leg-geometry-solver-diagnostic.json"',
        "max_upper_length_error_m",
        "max_lower_length_error_m",
        "unresolved_sample_count",
        "TryAnatomicalBodyBasis",
        "AlignReferenceBoneToDirection",
        "CaptureLegRotationFkDiagnostic",
        '"leg-rotation-fk-diagnostic.json"',
        "upper_local_rotation",
        "lower_local_rotation",
        "max_fk_mid_error_m",
        "max_fk_end_error_m",
        "mappedSlotByJointIndex",
        "geometryLegsAvailable",
        "sourceToTargetBody",
        "carriedLegBend",
        "upperDesiredLocal",
        "lowerDesiredLocal",
        "rotations[mappedSlotByJointIndex[limb.rootIndex]]",
        "rotations[mappedSlotByJointIndex[limb.midIndex]]",
        'retargeting_method = "geometry-legs-v1+legacy-upper-body-v1+animation-stream-body-v1+generic-avatar+actor-motion-root-v3-authored-transform"',
        '"retarget-profile.json"',
        "frame.weights[curveIndex] * 100.0f",
        "BodyActorPrefix + actorTarget.actor_binding_id",
        "MotionRootPrefix + actorTarget.actor_binding_id",
        "CreateMotionRootClip",
        "MotionRootAnimationPath",
        "GroundHeading",
        "RemoveGroundHeading",
        "baseWorldPosition + baseWorldRotation * actorLocalOffset",
        "parent.InverseTransformPoint(worldPosition)",
        "baseWorldRotation * actorLocalHeading",
        "Quaternion.Inverse(parent.rotation) * worldRotation",
        "Quaternion.LookRotation",
        "motionRoot.transform.localPosition = originalLocalPosition",
        "instance.transform.localPosition = Vector3.zero",
        "motionTrack.trackOffset = TrackOffset.ApplySceneOffsets",
        "rootTrack.trackOffset = TrackOffset.ApplySceneOffsets",
        "frame.root_position_m.x",
        "frame.root_position_m.z",
        "0.0f",
        "bodyPlayable.removeStartOffset = true",
        "bodyPlayable.applyFootIK = false",
        "CaptureBodyRealizationDiagnostic",
        "body-realization-diagnostic.json",
        "GroundClearance",
        "target_facing_error_deg",
        "max_leg_muscle_abs",
        "realized_left_knee_local_delta_deg",
        "realized_right_knee_local_delta_deg",
        "animation_stream_probe_left_knee_delta_deg",
        "animation_stream_probe_right_knee_delta_deg",
        "public VectorValue[] joint_positions_m",
        "animator.BindStreamTransform",
        "AnimatorCullingMode.AlwaysAnimate",
        "graph.Evaluate(1.0f / 60.0f)",
        "ProcessRootMotion(AnimationStream stream)",
        "WriteKnees(stream)",
        "AnimationScriptPlayable.Create",
        "SetLocalRotation(stream",
        "realized_left_ankle_direction_from_knee",
        "realized_right_ankle_direction_from_knee",
        "max_leg_muscle_name",
        "source_left_knee_rotation_deg",
        "source_right_knee_rotation_deg",
        "AnimationTrack track = animationRoots[body.actor_binding_id]",
        "removeStartOffset = false",
        "foreach (ActorPlan actorPlan in plan.sequences.Single().actors)",
        "GameObject.CreatePrimitive(primitive)",
        "SceneManager.MoveGameObjectToScene(instance, scene)",
        "track.GetChildTracks()",
        "lifecycle.import_process_id == ProcessId",
        "camera.Render()",
        "UnityEngine.Timeline.AudioTrack track = timeline.CreateTrack<UnityEngine.Timeline.AudioTrack>",
        "AudioSource source = audioActor.GetComponent<AudioSource>();",
        "if (source == null)",
        "source = audioActor.AddComponent<AudioSource>();",
        "track is UnityEngine.Timeline.AudioTrack",
        "GeneratedAssetPaths(mapping, target)",
        "IsManagedGeneratedAssetPath",
        'path.StartsWith(\n                "Assets/CutSceneAI/Studio/Run_"',
        "CleanupGeneratedAssets(generatedAssets)",
        "AssetDatabase.DeleteAsset(path)",
        "outside the managed CutSceneAI run namespace",
        "AssetDatabase.CopyAsset",
        "source_scene_asset_path",
        "SceneBindingFor",
        "SceneObjectAtPath",
    ):
        assert token in script
    assert "director.SetGenericBinding(rootTrack, actorAnimator)" not in script
    for token in (
        "[ExecuteAlways]",
        "public sealed class CutSceneAIBodyStreamDriver",
        "NativeArray<TransformStreamHandle>",
        "animator.BindStreamTransform",
        "AnimationScriptPlayable.Create",
        "handle.SetLocalRotation(stream, rotations[index])",
        "EvaluateAtTime(double timeSeconds)",
        "Quaternion.Slerp",
        "AnimatorCullingMode.AlwaysAnimate",
    ):
        assert token in runtime
    assert ".Where(item => item.transform != null).Select" not in script
    assert 'throw new InvalidOperationException("Humanoid bone is not mapped: "' not in script
    assert 'throw new InvalidOperationException("Generated clip sampling is missing Humanoid bone: "' not in script
    assert 'SetCurve(clip, path, typeof(Transform), "m_LocalRotation.x"' not in script
    assert "reference * QuaternionValueOf" not in script
    assert "Quaternion.Inverse(animator.transform.rotation) * bone.rotation" not in script
    assert "animator.transform.InverseTransformPoint(transform.position)" not in script
    assert "timeline.CreateTrack<AnimationTrack>(animationRoots[body.actor_binding_id]" not in script
    assert "+ Quaternion.Inverse(parentComponents[jointIndex])" not in script
    assert "GetComponent<AudioSource>() ??" not in script
    assert runner.count("& $UnityEditor") == 2
    assert '"Assets\\CutSceneAI\\Runtime\\CutSceneAIBodyStreamDriver.cs"' in runner
    assert 'Join-Path $projectRoot "CutSceneAIEvidence\\Unity"' in runner
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
            "Scripts/CutSceneAIBodyStreamDriver.cs",
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


def test_native_target_accepts_authored_source_scene_bindings() -> None:
    _, _, _, target = _components()
    target = target.model_copy(
        update={
            "source_scene_asset_path": (
                "Assets/CutSceneAI/Research/Scenes/SC_HallwaySource.unity"
            ),
            "scene_bindings": [
                UnityNativeSceneBinding(
                    source_entity_id="mina",
                    source_object_id="GlobalObjectId:mina",
                    hierarchy_path="HallwayEnvironment/Characters/Mina",
                )
            ],
        }
    )

    rendered = render_unity_native_target(target)
    payload = json.loads(rendered)

    assert payload["source_scene_asset_path"].endswith("SC_HallwaySource.unity")
    assert payload["scene_bindings"][0]["source_entity_id"] == "mina"
    assert payload["scene_bindings"][0]["hierarchy_path"] == (
        "HallwayEnvironment/Characters/Mina"
    )


def test_native_actor_target_accepts_valid_prefab_path_with_spaces() -> None:
    path = "Assets/Starter Assets/Runtime/SpaceRobotKyle/Prefabs/RobotKyle.prefab"
    target = UnityNativeActorTarget(
        actor_binding_id="actor:guard",
        prefab_path=path,
    )

    assert target.prefab_path == path


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
                        "prefab_path": "Assets/Characters/Mina.fbx",
                        "facial_renderer_path": "Face",
                    }
                ]
            },
            "must reference a Unity .prefab asset",
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
