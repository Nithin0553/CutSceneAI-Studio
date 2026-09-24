from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from cutsceneai_performance import (
    PerformanceBundle,
    load_performance_bundle,
    render_performance_bundle,
)
from pydantic import BaseModel

from .models import UnityExportPlan
from .native_models import UnityNativeRealizationTarget
from .performance import compile_performance_bundle
from .performance_models import UnityPerformanceMapping
from .serialization import (
    render_unity_performance_mapping,
    render_unity_plan,
)

UNITY_NATIVE_EDITOR_SCRIPT_FILENAME = "CutSceneAIGeneratedPerformance.cs"
UNITY_NATIVE_RUNNER_FILENAME = "run-unity-native.ps1"
_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


@dataclass(frozen=True)
class UnityNativePerformancePackage:
    bundle: PerformanceBundle
    plan: UnityExportPlan
    mapping: UnityPerformanceMapping
    target: UnityNativeRealizationTarget


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _mapping_target_root(mapping: UnityPerformanceMapping) -> str:
    marker = "/Body/"
    path = mapping.body_tracks[0].target_animation_path
    if marker not in path:
        raise ValueError(
            "Unity body target path does not contain the required Body folder."
        )
    return path.split(marker, 1)[0]


def compile_unity_native_performance_package(
    bundle: PerformanceBundle,
    *,
    plan: UnityExportPlan,
    mapping: UnityPerformanceMapping,
    target: UnityNativeRealizationTarget,
) -> UnityNativePerformancePackage:
    """Validate one unchanged bundle and its explicit Unity native target."""

    rendered_bundle = render_performance_bundle(bundle)
    verified_bundle = load_performance_bundle(rendered_bundle)
    expected_mapping = compile_performance_bundle(
        verified_bundle,
        export_plan=plan,
        target_path=_mapping_target_root(mapping),
    )
    omitted_facial = set(target.omitted_facial_actor_binding_ids)
    available_facial = {
        item.actor_binding_id for item in expected_mapping.facial_tracks
    }
    unknown_omissions = sorted(omitted_facial - available_facial)
    if unknown_omissions:
        raise ValueError(
            "Unity native target omits facial tracks that are not present in the bundle: "
            + ", ".join(unknown_omissions)
        )
    if omitted_facial:
        expected_mapping = expected_mapping.model_copy(
            update={
                "facial_tracks": [
                    item
                    for item in expected_mapping.facial_tracks
                    if item.actor_binding_id not in omitted_facial
                ]
            },
            deep=True,
        )
    if mapping != expected_mapping:
        raise ValueError(
            "Unity performance mapping is not the deterministic mapping of the bundle."
        )
    rendered_mapping = render_unity_performance_mapping(mapping).encode("utf-8")
    if target.source_mapping_sha256 != _sha256(rendered_mapping):
        raise ValueError("Unity native target does not match the mapping SHA-256.")
    if target.project_id != mapping.project_id or plan.project_id != mapping.project_id:
        raise ValueError(
            "Unity native target, plan, and mapping use different projects."
        )
    sequence = plan.sequences[0]
    if (
        target.timeline_asset_path != sequence.timeline_asset_path
        or target.scene_asset_path != sequence.scene_asset_path
        or mapping.source_scene_id != sequence.source_scene_id
    ):
        raise ValueError("Unity native target paths or scene do not match the plan.")

    scene_binding_ids = {item.source_entity_id for item in target.scene_bindings}
    plan_source_entity_ids = {
        item.source_entity_id for item in sequence.actors
    }
    unknown_scene_bindings = sorted(scene_binding_ids - plan_source_entity_ids)
    if unknown_scene_bindings:
        raise ValueError(
            "Unity native target scene bindings reference unknown plan entities: "
            + ", ".join(unknown_scene_bindings)
        )

    actor_targets = {item.actor_binding_id: item for item in target.actors}
    expected_actor_ids = {item.actor_binding_id for item in mapping.body_tracks} | {
        item.actor_binding_id for item in mapping.facial_tracks
    }
    if set(actor_targets) != expected_actor_ids:
        raise ValueError(
            "Unity native target actors do not exactly match generated body and face tracks."
        )
    plan_actors = {item.binding_id: item for item in sequence.actors}
    if set(actor_targets) - set(plan_actors):
        raise ValueError("Unity native target references an unknown plan actor.")
    facial_actor_ids = {item.actor_binding_id for item in mapping.facial_tracks}
    for binding_id, native_target in actor_targets.items():
        actor = plan_actors[binding_id]
        if actor.placeholder or actor.prefab_path != native_target.prefab_path:
            raise ValueError(
                "Unity native target requires the same non-placeholder prefab as the plan."
            )
        if binding_id in facial_actor_ids and not native_target.facial_renderer_path:
            raise ValueError(
                "Unity native target requires facial_renderer_path for actors with facial tracks."
            )

    return UnityNativePerformancePackage(
        bundle=verified_bundle,
        plan=plan.model_copy(deep=True),
        mapping=mapping.model_copy(deep=True),
        target=target.model_copy(deep=True),
    )


def _encoded_json(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    data = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.b64encode(data).decode("ascii")


_UNITY_NATIVE_TEMPLATE = r"""// Generated by CutSceneAI Unity Adapter v0.1.0 for validated Unity 6 LTS editor lines.
// Copy only through the generated runner. The importer refuses every asset conflict.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using UnityEditor;
using UnityEditor.PackageManager;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Animations;
using UnityEngine.Playables;
using UnityEngine.SceneManagement;
using UnityEngine.Timeline;

public static class CutSceneAIGeneratedPerformance
{
    private const string PlanBase64 = "__PLAN_BASE64__";
    private const string MappingBase64 = "__MAPPING_BASE64__";
    private const string TargetBase64 = "__TARGET_BASE64__";
    private const string BodyPrefix = "CSA|BODY|";
    private const string BodyActorPrefix = "CSA|BODY-ACTOR|";
    private const string MotionRootPrefix = "CSA|MOTIONROOT|";
    private const string FacePrefix = "CSA|FACIAL|";
    private const string CameraMotionPrefix = "CSA|CAMERA-MOTION|";
    private const string CameraPrefix = "CSA|CAMERA|";
    private const string AudioPrefix = "CSA|AUDIO|";
    private const string ActorPrefix = "CSA|ACTOR|";

    [Serializable] private sealed class VectorValue { public float x; public float y; public float z; }
    [Serializable] private sealed class QuaternionValue { public float x; public float y; public float z; public float w; }
    [Serializable] private sealed class Artifact { public string sha256; }
    [Serializable] private sealed class JointBinding {
        public string source_joint_name; public string target_human_bone; public int parent_index;
    }
    [Serializable] private sealed class BodyKeyframe { public int timeline_frame; public VectorValue root_position_m; public QuaternionValue[] joint_rotations; public VectorValue[] joint_positions_m; }
    [Serializable] private sealed class BodyTrack {
        public string semantic_id; public string actor_binding_id; public string source_performance_cue_id; public int start_frame;
        public int end_frame; public string target_animation_path; public Artifact source_artifact;
        public JointBinding[] joint_bindings; public BodyKeyframe[] keyframes;
    }
    [Serializable] private sealed class CurveBinding { public string target_blendshape_name; }
    [Serializable] private sealed class FaceKeyframe { public int timeline_frame; public float[] weights; }
    [Serializable] private sealed class FaceTrack {
        public string semantic_id; public string actor_binding_id; public int start_frame;
        public int end_frame; public string target_animation_path; public Artifact source_artifact;
        public CurveBinding[] curve_bindings; public FaceKeyframe[] keyframes;
    }
    [Serializable] private sealed class CameraKeyframe { public int timeline_frame; public VectorValue position_m; public QuaternionValue rotation; public float focal_length_mm; }
    [Serializable] private sealed class CameraTrack {
        public string semantic_id; public string camera_binding_id; public string source_camera_cut_id;
        public int start_frame; public int end_frame; public string target_animation_path;
        public float sensor_width_mm; public float sensor_height_mm; public Artifact source_artifact;
        public CameraKeyframe[] keyframes;
    }
    [Serializable] private sealed class AudioTrack {
        public string dialogue_cue_id; public string actor_binding_id; public int start_frame;
        public int end_frame; public string target_audio_path; public Artifact source_artifact;
    }
    [Serializable] private sealed class Mapping {
        public string project_id; public string source_scene_id; public string source_bundle_sha256;
        public int fps; public int duration_frames; public BodyTrack[] body_tracks;
        public FaceTrack[] facial_tracks; public CameraTrack[] camera_tracks; public AudioTrack[] audio_tracks;
    }
    [Serializable] private sealed class ActorTarget {
        public string actor_binding_id; public string prefab_path; public string animator_path;
        public string facial_renderer_path;
    }
    [Serializable] private sealed class SceneBinding {
        public string source_entity_id; public string source_object_id; public string hierarchy_path;
    }
    [Serializable] private sealed class RenderTarget { public int width; public int height; public string output_directory; }
    [Serializable] private sealed class Target {
        public string project_id; public string source_mapping_sha256; public string timeline_asset_path;
        public string scene_asset_path; public string source_scene_asset_path;
        public SceneBinding[] scene_bindings; public ActorTarget[] actors; public RenderTarget render;
    }
    [Serializable] private sealed class Plan {
        public string adapter_version; public string project_id; public int fps;
        public TimelineSemantics semantics; public ScenePlan[] sequences;
    }
    [Serializable] private sealed class ScenePlan { public string source_scene_id; public int duration_frames; public ActorPlan[] actors; }
    [Serializable] private sealed class ActorPlan {
        public string binding_id; public string source_entity_id; public string display_name; public string kind;
        public string prefab_path; public bool placeholder; public string placeholder_primitive;
        public TransformValue transform;
    }
    [Serializable] private sealed class TransformValue {
        public VectorValue position_m; public QuaternionValue rotation; public VectorValue scale;
    }
    [Serializable] private sealed class TimelineSemantics {
        public string semantics_version; public string cir_schema_version;
        public string cir_fingerprint_sha256; public string project_id; public int fps;
        public SemanticScene[] scenes;
    }
    [Serializable] private sealed class SemanticScene {
        public string source_scene_id; public int duration_frames; public SemanticEntity[] entities;
        public SemanticPerformance[] performance_cues; public SemanticDialogue[] dialogue_cues;
        public SemanticCamera[] camera_cuts;
    }
    [Serializable] private sealed class SemanticEntity { public string binding_id; public string source_entity_id; public string kind; }
    [Serializable] private sealed class SemanticPerformance {
        public string cue_id; public string source_beat_id; public string actor_binding_id;
        public int start_frame; public int end_frame; public string motion_intent_sha256;
        public string look_at_binding_id;
    }
    [Serializable] private sealed class SemanticDialogue {
        public string cue_id; public string source_beat_id; public string actor_binding_id;
        public int start_frame; public int window_end_frame; public string text_sha256; public string language;
    }
    [Serializable] private sealed class SemanticCamera {
        public string cut_id; public string source_shot_id; public string[] source_beat_ids;
        public int start_frame; public int end_frame; public string purpose; public string framing;
        public string angle; public string movement; public float lens_mm;
        public string[] subject_binding_ids; public string[] target_binding_ids;
    }
    [Serializable] private sealed class RealizedSection {
        public string semantic_id; public string actor_binding_id; public string asset_ref;
        public int start_frame; public int end_frame; public bool placeholder;
    }
    [Serializable] private sealed class ReadbackEvidence {
        public RealizedSection[] animation_sections; public RealizedSection[] facial_sections;
        public RealizedSection[] camera_sections; public RealizedSection[] audio_sections;
    }
    [Serializable] private sealed class EngineReadback {
        public string readback_version; public string engine; public string engine_version;
        public string adapter_version; public string timeline_asset; public TimelineSemantics semantics;
        public ReadbackEvidence evidence; public string[] warnings;
    }
    [Serializable] private sealed class BodyRealizationSample {
        public int frame; public string phase_semantic_id; public string actor_binding_id;
        public string target_binding_id; public VectorValue motion_root_position;
        public QuaternionValue motion_root_rotation; public VectorValue actor_forward;
        public VectorValue hips_position; public VectorValue left_knee_position;
        public VectorValue right_knee_position; public VectorValue left_foot_position;
        public VectorValue right_foot_position; public bool left_ground_found;
        public bool right_ground_found; public float left_ground_clearance_m;
        public float right_ground_clearance_m; public float left_knee_angle_deg;
        public float right_knee_angle_deg; public float source_left_knee_rotation_deg;
        public float source_right_knee_rotation_deg;
        public float realized_left_knee_local_delta_deg;
        public float realized_right_knee_local_delta_deg;
        public float animation_stream_probe_left_knee_delta_deg;
        public float animation_stream_probe_right_knee_delta_deg;
        public VectorValue realized_left_ankle_direction_from_knee;
        public VectorValue realized_right_ankle_direction_from_knee;
        public float target_facing_error_deg;
        public float max_leg_muscle_abs; public string max_leg_muscle_name;
    }
    [Serializable] private sealed class BodyRealizationDiagnostic {
        public string diagnostic_version; public string engine; public string engine_version;
        public string source_bundle_sha256; public BodyRealizationSample[] samples;
    }
    [Serializable] private sealed class LegGeometrySolverSample {
        public int frame;
        public string phase_semantic_id;
        public string actor_binding_id;
        public string limb_name;
        public VectorValue source_root;
        public VectorValue source_mid;
        public VectorValue source_end;
        public VectorValue solved_root;
        public VectorValue solved_mid;
        public VectorValue solved_end;
        public VectorValue bend_direction;
        public float target_upper_length_m;
        public float target_lower_length_m;
        public float solved_upper_length_error_m;
        public float solved_lower_length_error_m;
        public float source_extension_ratio;
        public bool source_bend_direction_defined;
        public bool reach_was_clamped;
        public bool solved;
    }
    [Serializable] private sealed class LegGeometrySolverDiagnostic {
        public string diagnostic_version;
        public string engine;
        public string engine_version;
        public string source_bundle_sha256;
        public float max_upper_length_error_m;
        public float max_lower_length_error_m;
        public int unresolved_sample_count;
        public LegGeometrySolverSample[] samples;
    }
    [Serializable] private sealed class LegRotationFkSample {
        public int frame;
        public string phase_semantic_id;
        public string actor_binding_id;
        public string limb_name;
        public QuaternionValue upper_local_rotation;
        public QuaternionValue lower_local_rotation;
        public VectorValue solved_root;
        public VectorValue solved_mid;
        public VectorValue solved_end;
        public VectorValue fk_root;
        public VectorValue fk_mid;
        public VectorValue fk_end;
        public float fk_mid_error_m;
        public float fk_end_error_m;
        public bool solved;
    }
    [Serializable] private sealed class LegRotationFkDiagnostic {
        public string diagnostic_version;
        public string engine;
        public string engine_version;
        public string source_bundle_sha256;
        public float max_fk_mid_error_m;
        public float max_fk_end_error_m;
        public int unresolved_sample_count;
        public LegRotationFkSample[] samples;
    }
    private sealed class TwoBoneGeometrySolution {
        public Vector3 root;
        public Vector3 mid;
        public Vector3 end;
        public Vector3 bend_direction;
        public float source_extension_ratio;
        public bool source_bend_direction_defined;
        public bool reach_was_clamped;
        public bool solved;
    }
    private struct KneeStreamProbeJob : IAnimationJob {
        public TransformStreamHandle left_knee;
        public TransformStreamHandle right_knee;
        public Quaternion left_rotation;
        public Quaternion right_rotation;

        private void WriteKnees(AnimationStream stream)
        {
            if (left_knee.IsValid(stream))
                left_knee.SetLocalRotation(stream, left_rotation);
            if (right_knee.IsValid(stream))
                right_knee.SetLocalRotation(stream, right_rotation);
        }

        public void ProcessRootMotion(AnimationStream stream)
        {
            WriteKnees(stream);
        }

        public void ProcessAnimation(AnimationStream stream)
        {
            WriteKnees(stream);
        }
    }
    [Serializable] private sealed class RenderedFrame { public int frame; public string relative_path; public string sha256; }
    [Serializable] private sealed class RenderManifest {
        public string manifest_version; public string engine; public string source_bundle_sha256;
        public int expected_frame_count; public int rendered_frame_count; public RenderedFrame[] frames;
    }
    [Serializable] private sealed class Lifecycle {
        public string lifecycle_version; public int import_process_id; public int readback_process_id;
        public bool import_completed; public bool saved; public bool restarted;
        public bool readback_completed; public bool render_completed; public string retargeting_method;
        public string retarget_profile; public string[] errors;
    }
    [Serializable] private sealed class RetargetTransform {
        public VectorValue translation; public QuaternionValue rotation; public VectorValue scale;
    }
    [Serializable] private sealed class RetargetJoint {
        public string source_joint_name; public string target_human_bone; public int parent_index;
        public bool mapped;
        public RetargetTransform reference_local; public RetargetTransform reference_component;
        public QuaternionValue target_parent_component_rotation;
        public VectorValue canonical_reference_direction;
        public VectorValue target_reference_direction_parent_local;
        public QuaternionValue canonical_to_target_parent_basis;
    }
    [Serializable] private sealed class RetargetLimb {
        public string limb_name;
        public string root_human_bone;
        public string mid_human_bone;
        public string end_human_bone;
        public float upper_length_m;
        public float lower_length_m;
        public VectorValue rest_bend_direction_component;
        public bool rest_bend_direction_defined;
    }
    [Serializable] private sealed class RetargetActor {
        public string actor_binding_id;
        public string prefab_path;
        public RetargetJoint[] joints;
        public RetargetLimb[] limbs;
    }
    [Serializable] private sealed class RetargetProfile {
        public string profile_version; public string retargeting_method; public string canonical_reference_frame;
        public string engine; public string engine_version; public string source_mapping_sha256;
        public RetargetActor[] actors;
    }

    private static Plan LoadPlan() => Load<Plan>(PlanBase64, "plan");
    private static Mapping LoadMapping() => Load<Mapping>(MappingBase64, "mapping");
    private static Target LoadTarget() => Load<Target>(TargetBase64, "target");
    private static T Load<T>(string encoded, string description) where T : class
    {
        string json = Encoding.UTF8.GetString(Convert.FromBase64String(encoded));
        T value = JsonUtility.FromJson<T>(json);
        if (value == null) throw new InvalidOperationException("Invalid CutSceneAI " + description + ".");
        return value;
    }
    private static string ProjectRoot => Directory.GetParent(Application.dataPath).FullName;
    private static string EvidenceRoot(Target target)
    {
        string renderPath = Path.Combine(
            ProjectRoot,
            target.render.output_directory.Replace('/', Path.DirectorySeparatorChar));
        string parent = Path.GetDirectoryName(renderPath);
        if (string.IsNullOrEmpty(parent))
            throw new InvalidOperationException("Native render output requires a parent evidence directory.");
        return parent;
    }
    private static int ProcessId => System.Diagnostics.Process.GetCurrentProcess().Id;
    private static string AbsoluteAssetPath(string path) => Path.Combine(ProjectRoot, path.Replace('/', Path.DirectorySeparatorChar));
    private static int Frame(double seconds, int fps) => (int)Math.Round(seconds * fps, MidpointRounding.AwayFromZero);
    private static Vector3 Vector(VectorValue value) => new Vector3(value.x, value.y, value.z);
    private static Quaternion QuaternionValueOf(QuaternionValue value) => new Quaternion(value.x, value.y, value.z, value.w);

    private static Quaternion GroundHeading(Quaternion rotation)
    {
        // Canonical -Z forward becomes Unity +Z after handedness conversion.
        Vector3 forward = rotation * Vector3.forward;
        forward.y = 0.0f;
        if (forward.sqrMagnitude <= 1e-10f)
            return Quaternion.identity;
        return Quaternion.LookRotation(forward.normalized, Vector3.up);
    }

    private static Quaternion RemoveGroundHeading(Quaternion rotation)
        => Quaternion.Inverse(GroundHeading(rotation)) * rotation;
    private static VectorValue VectorData(Vector3 value) => new VectorValue { x = value.x, y = value.y, z = value.z };
    private static QuaternionValue QuaternionData(Quaternion value) => new QuaternionValue { x = value.x, y = value.y, z = value.z, w = value.w };

    private static Quaternion ReferenceComponentRotation(Animator animator, Transform bone)
        => Quaternion.Inverse(animator.avatarRoot.rotation) * bone.rotation;

    private static Quaternion ParentComponentRotation(Quaternion referenceLocal, Quaternion referenceComponent)
        => referenceComponent * Quaternion.Inverse(referenceLocal);

    private static int CanonicalPrimaryChildIndex(int jointIndex)
    {
        switch (jointIndex)
        {
            case 1: return 4;
            case 2: return 5;
            case 3: return 6;
            case 4: return 7;
            case 5: return 8;
            case 6: return 9;
            case 7: return 10;
            case 8: return 11;
            case 9: return 12;
            case 12: return 15;
            case 13: return 16;
            case 14: return 17;
            case 16: return 18;
            case 17: return 19;
            case 18: return 20;
            case 19: return 21;
            default: return -1;
        }
    }

    private static Vector3 CanonicalReferenceDirectionUnity(int jointIndex)
    {
        // cutsceneai-humanoid-v1 reference directions after the canonical
        // right-handed -> Unity left-handed Z reflection performed by the
        // Unity mapping compiler.
        switch (jointIndex)
        {
            case 1:
            case 2:
            case 4:
            case 5:
            case 13:
            case 14:
            case 16:
            case 17:
            case 18:
            case 19:
                return Vector3.down;
            case 3:
            case 6:
            case 9:
                return Vector3.up;
            case 7:
            case 8:
            case 12:
                return Vector3.forward;
            default:
                return Vector3.zero;
        }
    }

    private static Vector3 TargetReferenceDirectionParentLocal(
        Animator animator,
        Transform joint,
        Transform child,
        Quaternion referenceLocal,
        Quaternion referenceComponent)
    {
        if (joint == null || child == null)
            return Vector3.zero;
        Vector3 componentDirection =
            Quaternion.Inverse(animator.avatarRoot.rotation)
            * (child.position - joint.position);
        if (componentDirection.sqrMagnitude <= 1e-10f)
            return Vector3.zero;
        Quaternion parentComponent = ParentComponentRotation(
            referenceLocal,
            referenceComponent);
        return (
            Quaternion.Inverse(parentComponent)
            * componentDirection.normalized
        ).normalized;
    }

    private static Quaternion CanonicalToTargetParentBasis(
        Vector3 canonicalReferenceDirection,
        Vector3 targetReferenceDirectionParentLocal,
        Quaternion referenceLocal,
        Quaternion referenceComponent)
    {
        if (
            canonicalReferenceDirection.sqrMagnitude > 1e-10f
            && targetReferenceDirectionParentLocal.sqrMagnitude > 1e-10f)
        {
            return Quaternion.FromToRotation(
                canonicalReferenceDirection.normalized,
                targetReferenceDirectionParentLocal.normalized);
        }

        // Root and terminal joints do not have one canonical primary child.
        // Preserve the previous component-frame mapping as a deterministic
        // fallback for those joints.
        Quaternion parentComponent = ParentComponentRotation(
            referenceLocal,
            referenceComponent);
        return Quaternion.Inverse(parentComponent);
    }

    private static Quaternion RetargetRotation(
        Quaternion referenceLocal,
        Quaternion canonicalToTargetParentBasis,
        Quaternion canonicalDelta)
    {
        Quaternion targetDelta =
            canonicalToTargetParentBasis
            * canonicalDelta
            * Quaternion.Inverse(canonicalToTargetParentBasis);
        return targetDelta * referenceLocal;
    }

    private static RetargetTransform RetargetTransformData(Transform bone)
        => new RetargetTransform {
            translation = VectorData(bone.localPosition),
            rotation = QuaternionData(bone.localRotation),
            scale = VectorData(bone.localScale),
        };

    private static void ApplyActorTransform(GameObject instance, ActorPlan actor)
    {
        instance.transform.SetPositionAndRotation(
            Vector(actor.transform.position_m), QuaternionValueOf(actor.transform.rotation));
        instance.transform.localScale = Vector(actor.transform.scale);
    }

    private static string Sha256(byte[] data)
    {
        using (SHA256 sha = SHA256.Create())
            return string.Concat(sha.ComputeHash(data).Select(value => value.ToString("x2")));
    }
    private static string Sha256File(string path) => Sha256(File.ReadAllBytes(path));
    private static void EnsureFolder(string assetPath)
    {
        string directory = Path.GetDirectoryName(assetPath).Replace('\\', '/');
        string[] parts = directory.Split('/');
        string current = parts[0];
        for (int index = 1; index < parts.Length; index++)
        {
            string next = current + "/" + parts[index];
            if (!AssetDatabase.IsValidFolder(next)) AssetDatabase.CreateFolder(current, parts[index]);
            current = next;
        }
    }
    private static Transform Find(Transform root, string relativePath)
    {
        if (string.IsNullOrEmpty(relativePath)) return root;
        Transform value = root.Find(relativePath);
        if (value == null) throw new InvalidOperationException("Missing target object path: " + relativePath);
        return value;
    }
    private static ActorTarget ActorTargetFor(Target target, string bindingId)
    {
        ActorTarget value = target.actors.SingleOrDefault(item => item.actor_binding_id == bindingId);
        if (value == null) throw new InvalidOperationException("Missing native actor target: " + bindingId);
        return value;
    }
    private static SceneBinding SceneBindingFor(Target target, string sourceEntityId)
        => (target.scene_bindings ?? Array.Empty<SceneBinding>())
            .SingleOrDefault(item => item.source_entity_id == sourceEntityId);

    private static GameObject SceneObjectAtPath(Scene scene, SceneBinding binding)
    {
        string[] parts = binding.hierarchy_path.Split('/');
        GameObject current = scene.GetRootGameObjects()
            .SingleOrDefault(item => item.name == parts[0]);
        if (current == null)
            throw new InvalidOperationException(
                "Bound source scene object root is missing: " + binding.hierarchy_path);
        Transform transform = current.transform;
        for (int index = 1; index < parts.Length; index++)
        {
            Transform child = transform.Cast<Transform>()
                .SingleOrDefault(item => item.name == parts[index]);
            if (child == null)
                throw new InvalidOperationException(
                    "Bound source scene object is missing: " + binding.hierarchy_path);
            transform = child;
        }
        return transform.gameObject;
    }

    private static Scene CreateRealizationScene(Target target)
    {
        if (string.IsNullOrEmpty(target.source_scene_asset_path))
            return EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

        EnsureFolder(target.scene_asset_path);
        if (!AssetDatabase.CopyAsset(target.source_scene_asset_path, target.scene_asset_path))
            throw new InvalidOperationException(
                "Failed to copy authored source scene into generated realization scene: "
                + target.source_scene_asset_path);
        AssetDatabase.Refresh();
        return EditorSceneManager.OpenScene(target.scene_asset_path, OpenSceneMode.Single);
    }
    private static GameObject LoadPrefab(ActorTarget target)
    {
        GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(target.prefab_path);
        if (prefab == null) throw new InvalidOperationException("Missing target prefab: " + target.prefab_path);
        return prefab;
    }
    private static Animator AnimatorComponentFor(GameObject root, ActorTarget target)
    {
        Animator animator = Find(root.transform, target.animator_path).GetComponent<Animator>();
        if (animator == null)
            throw new InvalidOperationException(
                "Target is missing the required Animator component: "
                + target.actor_binding_id);
        return animator;
    }

    private static Animator AnimatorFor(GameObject root, ActorTarget target)
    {
        Animator animator = AnimatorComponentFor(root, target);
        if (animator.avatar == null || !animator.avatar.isValid || !animator.avatar.isHuman)
            throw new InvalidOperationException("Target requires one valid Humanoid Animator: " + target.actor_binding_id);
        return animator;
    }
    private static bool IsRequiredHumanoidBone(HumanBodyBones bone)
    {
        string enumName = bone.ToString();
        for (int index = 0; index < HumanTrait.BoneCount; index++)
        {
            string traitName = HumanTrait.BoneName[index].Replace(" ", "");
            if (string.Equals(traitName, enumName, StringComparison.Ordinal))
                return HumanTrait.RequiredBone(index);
        }
        throw new InvalidOperationException("Unable to resolve Humanoid bone requirement: " + enumName);
    }

    private static SkinnedMeshRenderer FaceFor(GameObject root, ActorTarget target)
    {
        SkinnedMeshRenderer renderer = Find(root.transform, target.facial_renderer_path).GetComponent<SkinnedMeshRenderer>();
        if (renderer == null || renderer.sharedMesh == null)
            throw new InvalidOperationException("Target facial renderer is missing: " + target.actor_binding_id);
        return renderer;
    }

    private static bool SupportedUnityVersion(string version)
        => version.StartsWith("6000.0", StringComparison.Ordinal)
            || version.StartsWith("6000.3", StringComparison.Ordinal);

    private static string MotionRootAnimationPath(BodyTrack track)
        => track.target_animation_path.EndsWith(".anim", StringComparison.Ordinal)
            ? track.target_animation_path.Substring(
                0,
                track.target_animation_path.Length - ".anim".Length
            ) + ".root.anim"
            : track.target_animation_path + ".root.anim";

    private static string GenericAvatarPath(BodyTrack track)
    {
        int slash = track.target_animation_path.LastIndexOf('/');
        string directory =
            slash >= 0
                ? track.target_animation_path.Substring(0, slash)
                : "Assets/CutSceneAI/Studio";
        string actorHash = Sha256(
            Encoding.UTF8.GetBytes(track.actor_binding_id)).Substring(0, 12);
        return directory + "/AV_Generic_" + actorHash + ".asset";
    }

    private static string[] GeneratedAssetPaths(Mapping mapping, Target target)
        => mapping.body_tracks.Select(item => item.target_animation_path)
            .Concat(mapping.body_tracks.Select(MotionRootAnimationPath))
            .Concat(mapping.body_tracks.Select(GenericAvatarPath))
            .Concat(mapping.facial_tracks.Select(item => item.target_animation_path))
            .Concat(mapping.camera_tracks.Select(item => item.target_animation_path))
            .Concat(new[] { target.timeline_asset_path, target.scene_asset_path })
            .Distinct()
            .ToArray();

    private static bool IsManagedGeneratedAssetPath(string path)
        => !string.IsNullOrEmpty(path)
            && path.StartsWith(
                "Assets/CutSceneAI/Studio/Run_",
                StringComparison.Ordinal)
            && !path.Contains("..");

    private static void CleanupGeneratedAssets(IEnumerable<string> paths)
    {
        foreach (string path in paths.Reverse())
        {
            string absolutePath = AbsoluteAssetPath(path);
            if (AssetDatabase.LoadMainAssetAtPath(path) == null && !File.Exists(absolutePath))
                continue;

            if (!AssetDatabase.DeleteAsset(path))
            {
                if (File.Exists(absolutePath)) File.Delete(absolutePath);
                string metaPath = absolutePath + ".meta";
                if (File.Exists(metaPath)) File.Delete(metaPath);
            }
        }
        AssetDatabase.Refresh();
    }

    private static void Preflight(Plan plan, Mapping mapping, Target target)
    {
        if (!SupportedUnityVersion(Application.unityVersion))
            throw new InvalidOperationException(
                "Validated Unity 6 editor lines are 6000.0.x and 6000.3.x; got "
                + Application.unityVersion + ".");
        UnityEditor.PackageManager.PackageInfo timelinePackage =
            UnityEditor.PackageManager.PackageInfo.FindForAssembly(typeof(TimelineAsset).Assembly);
        if (timelinePackage == null || timelinePackage.version != "1.8.12")
            throw new InvalidOperationException("com.unity.timeline 1.8.12 is required.");
        if (plan.project_id != mapping.project_id || target.project_id != mapping.project_id || plan.fps != mapping.fps)
            throw new InvalidOperationException("Plan, mapping, and native target identity diverged.");
        string[] generatedAssets = GeneratedAssetPaths(mapping, target);
        if (generatedAssets.Distinct().Count() != generatedAssets.Length)
            throw new InvalidOperationException("Native target contains duplicate generated asset paths.");
        foreach (string path in generatedAssets)
        {
            bool exists =
                AssetDatabase.LoadMainAssetAtPath(path) != null
                || File.Exists(AbsoluteAssetPath(path));
            if (exists && !IsManagedGeneratedAssetPath(path))
                throw new InvalidOperationException(
                    "Refusing to replace existing generated asset outside the managed CutSceneAI run namespace: "
                    + path);
        }

        if (!string.IsNullOrEmpty(target.source_scene_asset_path))
        {
            SceneAsset sourceScene = AssetDatabase.LoadAssetAtPath<SceneAsset>(
                target.source_scene_asset_path);
            if (sourceScene == null)
                throw new InvalidOperationException(
                    "Authored source scene is missing: " + target.source_scene_asset_path);
            string[] entityIds = (target.scene_bindings ?? Array.Empty<SceneBinding>())
                .Select(item => item.source_entity_id).ToArray();
            if (entityIds.Distinct().Count() != entityIds.Length)
                throw new InvalidOperationException(
                    "Native target contains duplicate source scene entity bindings.");
        }

        foreach (ActorTarget actorTarget in target.actors)
        {
            GameObject prefab = LoadPrefab(actorTarget);
            Animator animator = AnimatorFor(prefab, actorTarget);
            foreach (BodyTrack body in mapping.body_tracks.Where(item => item.actor_binding_id == actorTarget.actor_binding_id))
                foreach (JointBinding binding in body.joint_bindings)
                {
                    HumanBodyBones bone = (HumanBodyBones)Enum.Parse(typeof(HumanBodyBones), binding.target_human_bone);
                    if (animator.GetBoneTransform(bone) == null && IsRequiredHumanoidBone(bone))
                        throw new InvalidOperationException("Required Humanoid bone is not mapped: " + binding.target_human_bone);
                }

            FaceTrack[] actorFaceTracks = mapping.facial_tracks
                .Where(item => item.actor_binding_id == actorTarget.actor_binding_id).ToArray();
            if (actorFaceTracks.Length == 0)
                continue;

            SkinnedMeshRenderer face = FaceFor(prefab, actorTarget);
            if (!face.transform.IsChildOf(animator.transform))
                throw new InvalidOperationException("Target facial renderer must be below the Humanoid Animator: " + actorTarget.actor_binding_id);
            string[] actualShapes = Enumerable.Range(0, face.sharedMesh.blendShapeCount)
                .Select(index => face.sharedMesh.GetBlendShapeName(index)).ToArray();
            string[] requiredShapes = actorFaceTracks.SelectMany(item => item.curve_bindings)
                .Select(item => item.target_blendshape_name).Distinct().OrderBy(item => item).ToArray();
            string[] missing = requiredShapes.Except(actualShapes).ToArray();
            if (missing.Length != 0) throw new InvalidOperationException(
                "Target is missing required facial blendshapes for "
                + actorTarget.actor_binding_id + ": " + string.Join(", ", missing));
        }
        foreach (AudioTrack audio in mapping.audio_tracks)
        {
            string path = AbsoluteAssetPath(audio.target_audio_path);
            if (!File.Exists(path) || Sha256File(path) != audio.source_artifact.sha256)
                throw new InvalidOperationException("Bundled WAV is missing or changed: " + audio.target_audio_path);
            if (AssetDatabase.LoadAssetAtPath<AudioClip>(audio.target_audio_path) == null)
                throw new InvalidOperationException("Bundled WAV did not import as AudioClip: " + audio.target_audio_path);
        }
    }

    private static AnimationCurve Curve(IEnumerable<Keyframe> keys) => new AnimationCurve(keys.ToArray());
    private static void SetCurve(AnimationClip clip, string path, Type type, string property, IEnumerable<Keyframe> keys)
        => AnimationUtility.SetEditorCurve(clip, EditorCurveBinding.FloatCurve(path, type, property), Curve(keys));
    private static IEnumerable<Keyframe> Keys(int startFrame, int fps, IEnumerable<Tuple<int, float>> values)
        => values.Select(item => new Keyframe((float)(item.Item1 - startFrame) / fps, item.Item2));

    private static bool BodyTrackHasSourceMotion(BodyTrack track)
    {
        if (track.keyframes.Length < 2) return false;
        BodyKeyframe first = track.keyframes[0];
        foreach (BodyKeyframe frame in track.keyframes.Skip(1))
        {
            // Actor translation is realized by the explicit motion-root track.
            // This validator only asks whether the in-place Humanoid body pose
            // is expected to change.
            for (int jointIndex = 0; jointIndex < frame.joint_rotations.Length; jointIndex++)
            {
                Quaternion a = QuaternionValueOf(first.joint_rotations[jointIndex]);
                Quaternion b = QuaternionValueOf(frame.joint_rotations[jointIndex]);
                if (Quaternion.Angle(a, b) > 0.001f) return true;
            }
        }
        return false;
    }

    private static void ValidateClipBindingPaths(
        AnimationClip clip,
        GameObject prefab,
        ActorTarget target)
    {
        GameObject instance = UnityEngine.Object.Instantiate(prefab);
        instance.hideFlags = HideFlags.HideAndDontSave;
        try
        {
            Animator animator = AnimatorFor(instance, target);
            foreach (EditorCurveBinding binding in AnimationUtility.GetCurveBindings(clip))
            {
                Transform transform = string.IsNullOrEmpty(binding.path)
                    ? animator.transform
                    : animator.transform.Find(binding.path);
                if (transform == null)
                    throw new InvalidOperationException(
                        "Generated animation curve path does not resolve from Animator '"
                        + animator.name + "': " + binding.path + " / " + binding.propertyName);
                if (binding.type == typeof(SkinnedMeshRenderer)
                    && transform.GetComponent<SkinnedMeshRenderer>() == null)
                    throw new InvalidOperationException(
                        "Generated facial curve path does not resolve to a SkinnedMeshRenderer: "
                        + binding.path);
            }
        }
        finally
        {
            UnityEngine.Object.DestroyImmediate(instance);
        }
    }

    private static HumanPose SnapshotHumanPose(HumanPoseHandler handler)
    {
        HumanPose pose = new HumanPose { muscles = new float[HumanTrait.MuscleCount] };
        handler.GetHumanPose(ref pose);
        pose.muscles = (float[])pose.muscles.Clone();
        return pose;
    }

    private static void SampleHumanoidClip(
        GameObject root,
        AnimationClip clip,
        float time)
    {
        AnimationMode.BeginSampling();
        try
        {
            AnimationMode.SampleAnimationClip(root, clip, time);
        }
        finally
        {
            AnimationMode.EndSampling();
        }
    }

    private static void ValidateBodyClipSampling(
        AnimationClip clip,
        BodyTrack track,
        GameObject prefab,
        ActorTarget target,
        int fps)
    {
        if (!BodyTrackHasSourceMotion(track)) return;

        GameObject instance = UnityEngine.Object.Instantiate(prefab);
        instance.hideFlags = HideFlags.HideAndDontSave;
        bool startedAnimationMode = false;
        Avatar genericAvatar = null;
        try
        {
            Animator animator = AnimatorFor(instance, target);
            animator.enabled = false;
            Transform[] bones = track.joint_bindings
                .Select(binding => animator.GetBoneTransform(
                    (HumanBodyBones)Enum.Parse(
                        typeof(HumanBodyBones),
                        binding.target_human_bone)))
                .Where(transform => transform != null)
                .ToArray();

            // Use the Humanoid Avatar only to discover semantic target bones.
            // Playback uses a real Generic Avatar so Unity evaluates the authored
            // Transform curves as hierarchy animation. Root motion remains external
            // on CutSceneAI's dedicated motion-root track.
            genericAvatar = AvatarBuilder.BuildGenericAvatar(
                animator.gameObject,
                string.Empty);
            if (
                genericAvatar == null
                || !genericAvatar.isValid
                || genericAvatar.isHuman)
                throw new InvalidOperationException(
                    "Failed to build a valid Generic Avatar for direct-bone playback.");
            genericAvatar.name = "CutSceneAI_Validation_GenericAvatar";
            animator.avatar = genericAvatar;
            animator.runtimeAnimatorController = null;
            animator.applyRootMotion = false;
            animator.Rebind();
            animator.Update(0.0f);

            if (!AnimationMode.InAnimationMode())
            {
                AnimationMode.StartAnimationMode();
                startedAnimationMode = true;
            }

            float[] times = new[] {
                0.0f,
                Mathf.Max(0.0f, clip.length / 3.0f),
                Mathf.Max(0.0f, clip.length * 2.0f / 3.0f),
                Mathf.Max(0.0f, clip.length),
            };

            SampleHumanoidClip(animator.gameObject, clip, times[0]);
            Quaternion[] referenceRotations = bones
                .Select(transform => transform.localRotation)
                .ToArray();
            float maxBoneRotationDelta = 0.0f;

            foreach (float time in times.Skip(1))
            {
                SampleHumanoidClip(animator.gameObject, clip, time);
                for (int boneIndex = 0; boneIndex < bones.Length; boneIndex++)
                    maxBoneRotationDelta = Mathf.Max(
                        maxBoneRotationDelta,
                        Quaternion.Angle(
                            referenceRotations[boneIndex],
                            bones[boneIndex].localRotation));
            }

            if (maxBoneRotationDelta <= 0.001f)
                throw new InvalidOperationException(
                    "Generated body clip contains source motion but direct target-bone "
                    + "sampling produced no pose change. Refusing to save a structurally "
                    + "valid but non-playing AnimationClip.");
        }
        finally
        {
            if (startedAnimationMode && AnimationMode.InAnimationMode())
                AnimationMode.StopAnimationMode();
            UnityEngine.Object.DestroyImmediate(instance);
            if (genericAvatar != null)
                UnityEngine.Object.DestroyImmediate(genericAvatar);
        }
    }

    private static AnimationClip CreateBodyClip(
        BodyTrack track,
        GameObject prefab,
        ActorTarget target,
        int fps)
    {
        GameObject instance = UnityEngine.Object.Instantiate(prefab);
        instance.hideFlags = HideFlags.HideAndDontSave;
        try
        {
            Animator animator = AnimatorFor(instance, target);
            animator.enabled = false;

            int jointCount = track.joint_bindings.Length;
            Transform[] transforms = new Transform[jointCount];
            Quaternion[] referenceRotations = new Quaternion[jointCount];
            Quaternion[] referenceComponents = new Quaternion[jointCount];
            Quaternion[] canonicalToTargetParentBases = Enumerable
                .Range(0, jointCount)
                .Select(_ => Quaternion.identity)
                .ToArray();
            List<Tuple<int, float>>[] qx = Enumerable.Range(0, jointCount)
                .Select(_ => new List<Tuple<int, float>>()).ToArray();
            List<Tuple<int, float>>[] qy = Enumerable.Range(0, jointCount)
                .Select(_ => new List<Tuple<int, float>>()).ToArray();
            List<Tuple<int, float>>[] qz = Enumerable.Range(0, jointCount)
                .Select(_ => new List<Tuple<int, float>>()).ToArray();
            List<Tuple<int, float>>[] qw = Enumerable.Range(0, jointCount)
                .Select(_ => new List<Tuple<int, float>>()).ToArray();

            for (int jointIndex = 0; jointIndex < jointCount; jointIndex++)
            {
                HumanBodyBones bone = (HumanBodyBones)Enum.Parse(
                    typeof(HumanBodyBones),
                    track.joint_bindings[jointIndex].target_human_bone);
                Transform transform = animator.GetBoneTransform(bone);
                if (transform == null)
                {
                    if (IsRequiredHumanoidBone(bone))
                        throw new InvalidOperationException(
                            "Required Humanoid bone is not mapped: "
                            + track.joint_bindings[jointIndex].target_human_bone);
                    continue;
                }

                transforms[jointIndex] = transform;
                referenceRotations[jointIndex] = transform.localRotation;
                referenceComponents[jointIndex] =
                    ReferenceComponentRotation(animator, transform);
            }

            for (int jointIndex = 0; jointIndex < jointCount; jointIndex++)
            {
                if (transforms[jointIndex] == null) continue;
                int childIndex = CanonicalPrimaryChildIndex(jointIndex);
                Transform child =
                    childIndex >= 0
                    && childIndex < jointCount
                    ? transforms[childIndex]
                    : null;
                Vector3 canonicalReference =
                    CanonicalReferenceDirectionUnity(jointIndex);
                Vector3 targetReference =
                    TargetReferenceDirectionParentLocal(
                        animator,
                        transforms[jointIndex],
                        child,
                        referenceRotations[jointIndex],
                        referenceComponents[jointIndex]);
                canonicalToTargetParentBases[jointIndex] =
                    CanonicalToTargetParentBasis(
                        canonicalReference,
                        targetReference,
                        referenceRotations[jointIndex],
                        referenceComponents[jointIndex]);
            }

            foreach (BodyKeyframe frame in track.keyframes)
            {
                for (int jointIndex = 0; jointIndex < jointCount; jointIndex++)
                {
                    if (transforms[jointIndex] == null) continue;

                    Quaternion canonicalRotation =
                        QuaternionValueOf(frame.joint_rotations[jointIndex]);
                    if (jointIndex == 0)
                        canonicalRotation = RemoveGroundHeading(canonicalRotation);
                    Quaternion targetRotation = RetargetRotation(
                        referenceRotations[jointIndex],
                        canonicalToTargetParentBases[jointIndex],
                        canonicalRotation);

                    qx[jointIndex].Add(Tuple.Create(
                        frame.timeline_frame,
                        targetRotation.x));
                    qy[jointIndex].Add(Tuple.Create(
                        frame.timeline_frame,
                        targetRotation.y));
                    qz[jointIndex].Add(Tuple.Create(
                        frame.timeline_frame,
                        targetRotation.z));
                    qw[jointIndex].Add(Tuple.Create(
                        frame.timeline_frame,
                        targetRotation.w));
                }
            }

            AnimationClip clip = new AnimationClip {
                name = Path.GetFileNameWithoutExtension(track.target_animation_path),
                frameRate = fps,
            };
            for (int jointIndex = 0; jointIndex < jointCount; jointIndex++)
            {
                Transform transform = transforms[jointIndex];
                if (transform == null) continue;
                string path = AnimationUtility.CalculateTransformPath(
                    transform,
                    animator.transform);
                SetCurve(
                    clip, path, typeof(Transform), "m_LocalRotation.x",
                    Keys(track.start_frame, fps, qx[jointIndex]));
                SetCurve(
                    clip, path, typeof(Transform), "m_LocalRotation.y",
                    Keys(track.start_frame, fps, qy[jointIndex]));
                SetCurve(
                    clip, path, typeof(Transform), "m_LocalRotation.z",
                    Keys(track.start_frame, fps, qz[jointIndex]));
                SetCurve(
                    clip, path, typeof(Transform), "m_LocalRotation.w",
                    Keys(track.start_frame, fps, qw[jointIndex]));
            }

            clip.EnsureQuaternionContinuity();
            ValidateClipBindingPaths(clip, prefab, target);
            ValidateBodyClipSampling(clip, track, prefab, target, fps);
            EnsureFolder(track.target_animation_path);
            AssetDatabase.CreateAsset(clip, track.target_animation_path);
            return clip;
        }
        finally
        {
            UnityEngine.Object.DestroyImmediate(instance);
        }
    }

    private static RetargetLimb CaptureRetargetLimb(
        Animator animator,
        string limbName,
        HumanBodyBones rootBone,
        HumanBodyBones midBone,
        HumanBodyBones endBone)
    {
        Transform root = animator.GetBoneTransform(rootBone);
        Transform mid = animator.GetBoneTransform(midBone);
        Transform end = animator.GetBoneTransform(endBone);
        if (root == null || mid == null || end == null)
            throw new InvalidOperationException(
                "Required target limb is not fully mapped: " + limbName);

        Vector3 rootComponent = animator.avatarRoot.InverseTransformPoint(root.position);
        Vector3 midComponent = animator.avatarRoot.InverseTransformPoint(mid.position);
        Vector3 endComponent = animator.avatarRoot.InverseTransformPoint(end.position);
        float upperLength = Vector3.Distance(rootComponent, midComponent);
        float lowerLength = Vector3.Distance(midComponent, endComponent);
        if (upperLength <= 1e-6f || lowerLength <= 1e-6f)
            throw new InvalidOperationException(
                "Target limb contains a zero-length segment: " + limbName);

        Vector3 rootToEnd = endComponent - rootComponent;
        Vector3 rootToMid = midComponent - rootComponent;
        Vector3 bend = Vector3.zero;
        bool bendDefined = false;
        if (rootToEnd.sqrMagnitude > 1e-12f)
        {
            Vector3 axis = rootToEnd.normalized;
            bend = rootToMid - axis * Vector3.Dot(rootToMid, axis);
            if (bend.sqrMagnitude > 1e-10f)
            {
                bend.Normalize();
                bendDefined = true;
            }
            else
            {
                bend = Vector3.zero;
            }
        }

        return new RetargetLimb {
            limb_name = limbName,
            root_human_bone = rootBone.ToString(),
            mid_human_bone = midBone.ToString(),
            end_human_bone = endBone.ToString(),
            upper_length_m = upperLength,
            lower_length_m = lowerLength,
            rest_bend_direction_component = VectorData(bend),
            rest_bend_direction_defined = bendDefined,
        };
    }

    private static bool TryAnatomicalBodyBasis(
        Vector3 pelvis,
        Vector3 leftHip,
        Vector3 rightHip,
        Vector3 spine,
        out Quaternion basis)
    {
        basis = Quaternion.identity;
        Vector3 xAxis = leftHip - rightHip;
        Vector3 upSeed = spine - pelvis;
        if (xAxis.sqrMagnitude <= 1e-12f || upSeed.sqrMagnitude <= 1e-12f)
            return false;
        xAxis.Normalize();
        Vector3 up = upSeed - xAxis * Vector3.Dot(upSeed, xAxis);
        if (up.sqrMagnitude <= 1e-12f)
            return false;
        up.Normalize();
        Vector3 forward = Vector3.Cross(xAxis, up);
        if (forward.sqrMagnitude <= 1e-12f)
            return false;
        forward.Normalize();
        up = Vector3.Cross(forward, xAxis).normalized;
        basis = Quaternion.LookRotation(forward, up);
        return true;
    }

    private static Vector3 ComponentPosition(Animator animator, Transform transform)
        => animator.avatarRoot.InverseTransformPoint(transform.position);

    private static Quaternion AlignReferenceBoneToDirection(
        Quaternion baseComponentRotation,
        Vector3 referenceChildOffsetLocal,
        Vector3 desiredDirectionComponent)
    {
        Vector3 baseDirection =
            baseComponentRotation * referenceChildOffsetLocal;
        if (
            baseDirection.sqrMagnitude <= 1e-12f
            || desiredDirectionComponent.sqrMagnitude <= 1e-12f)
            throw new InvalidOperationException(
                "Cannot align a zero-length target bone direction.");
        Quaternion swing = Quaternion.FromToRotation(
            baseDirection.normalized,
            desiredDirectionComponent.normalized);
        return swing * baseComponentRotation;
    }

    private static bool TrySourceBendDirection(
        Vector3 root,
        Vector3 mid,
        Vector3 end,
        out Vector3 bendDirection)
    {
        bendDirection = Vector3.zero;
        Vector3 rootToEnd = end - root;
        if (rootToEnd.sqrMagnitude <= 1e-12f)
            return false;
        Vector3 axis = rootToEnd.normalized;
        Vector3 rootToMid = mid - root;
        Vector3 bend = rootToMid - axis * Vector3.Dot(rootToMid, axis);
        if (bend.sqrMagnitude <= 1e-10f)
            return false;
        bendDirection = bend.normalized;
        return true;
    }

    private static TwoBoneGeometrySolution SolveTwoBoneGeometry(
        Vector3 sourceRoot,
        Vector3 sourceMid,
        Vector3 sourceEnd,
        Vector3 targetRoot,
        float targetUpperLength,
        float targetLowerLength,
        Vector3 fallbackBendDirection,
        bool hasFallback)
    {
        TwoBoneGeometrySolution result = new TwoBoneGeometrySolution {
            root = targetRoot,
            mid = targetRoot,
            end = targetRoot,
            bend_direction = Vector3.zero,
            source_extension_ratio = 0.0f,
            source_bend_direction_defined = false,
            reach_was_clamped = false,
            solved = false,
        };

        float sourceUpper = Vector3.Distance(sourceRoot, sourceMid);
        float sourceLower = Vector3.Distance(sourceMid, sourceEnd);
        Vector3 sourceDisplacement = sourceEnd - sourceRoot;
        float sourceReach = sourceDisplacement.magnitude;
        if (
            sourceUpper <= 1e-9f
            || sourceLower <= 1e-9f
            || sourceReach <= 1e-9f
            || targetUpperLength <= 1e-9f
            || targetLowerLength <= 1e-9f)
            return result;

        Vector3 direction = sourceDisplacement / sourceReach;
        float sourceTotal = sourceUpper + sourceLower;
        float extensionRatio = Mathf.Clamp01(sourceReach / sourceTotal);
        float targetTotal = targetUpperLength + targetLowerLength;
        float requestedReach = extensionRatio * targetTotal;
        float minimumReach = Mathf.Abs(targetUpperLength - targetLowerLength);
        float epsilon = Mathf.Max(targetTotal * 1e-7f, 1e-8f);
        float lowerBound = Mathf.Min(minimumReach + epsilon, targetTotal - epsilon);
        float upperBound = targetTotal - epsilon;
        float targetReach = Mathf.Clamp(requestedReach, lowerBound, upperBound);
        Vector3 targetEnd = targetRoot + direction * targetReach;

        bool sourceBendDefined = TrySourceBendDirection(
            sourceRoot,
            sourceMid,
            sourceEnd,
            out Vector3 bendDirection);
        if (!sourceBendDefined)
        {
            if (!hasFallback)
            {
                result.end = targetEnd;
                result.source_extension_ratio = extensionRatio;
                result.reach_was_clamped =
                    Mathf.Abs(targetReach - requestedReach) > epsilon;
                return result;
            }
            Vector3 rejected =
                fallbackBendDirection
                - direction * Vector3.Dot(fallbackBendDirection, direction);
            if (rejected.sqrMagnitude <= 1e-10f)
            {
                result.end = targetEnd;
                result.source_extension_ratio = extensionRatio;
                result.reach_was_clamped =
                    Mathf.Abs(targetReach - requestedReach) > epsilon;
                return result;
            }
            bendDirection = rejected.normalized;
        }

        float along = (
            targetUpperLength * targetUpperLength
            - targetLowerLength * targetLowerLength
            + targetReach * targetReach
        ) / (2.0f * targetReach);
        float heightSquared = Mathf.Max(
            0.0f,
            targetUpperLength * targetUpperLength - along * along);
        float height = Mathf.Sqrt(heightSquared);
        Vector3 targetMid =
            targetRoot + direction * along + bendDirection * height;

        result.mid = targetMid;
        result.end = targetEnd;
        result.bend_direction = bendDirection;
        result.source_extension_ratio = extensionRatio;
        result.source_bend_direction_defined = sourceBendDefined;
        result.reach_was_clamped =
            Mathf.Abs(targetReach - requestedReach) > epsilon;
        result.solved = true;
        return result;
    }

    private static bool FirstSourceBendDirection(
        Mapping mapping,
        string actorBindingId,
        string rootJoint,
        string midJoint,
        string endJoint,
        out Vector3 bendDirection)
    {
        bendDirection = Vector3.zero;
        foreach (BodyTrack track in mapping.body_tracks
            .Where(item => item.actor_binding_id == actorBindingId)
            .OrderBy(item => item.start_frame)
            .ThenBy(item => item.semantic_id))
        {
            int rootIndex = JointIndex(track, rootJoint);
            int midIndex = JointIndex(track, midJoint);
            int endIndex = JointIndex(track, endJoint);
            if (rootIndex < 0 || midIndex < 0 || endIndex < 0)
                continue;
            foreach (BodyKeyframe frame in track.keyframes)
            {
                if (
                    frame.joint_positions_m == null
                    || rootIndex >= frame.joint_positions_m.Length
                    || midIndex >= frame.joint_positions_m.Length
                    || endIndex >= frame.joint_positions_m.Length)
                    continue;
                if (TrySourceBendDirection(
                    Vector(frame.joint_positions_m[rootIndex]),
                    Vector(frame.joint_positions_m[midIndex]),
                    Vector(frame.joint_positions_m[endIndex]),
                    out bendDirection))
                    return true;
            }
        }
        return false;
    }

    private static LegGeometrySolverDiagnostic CaptureLegGeometrySolverDiagnostic(
        Mapping mapping,
        Target target)
    {
        List<LegGeometrySolverSample> samples =
            new List<LegGeometrySolverSample>();
        float maxUpperError = 0.0f;
        float maxLowerError = 0.0f;
        int unresolved = 0;

        foreach (IGrouping<string, BodyTrack> actorGroup in mapping.body_tracks
            .GroupBy(item => item.actor_binding_id))
        {
            ActorTarget actorTarget = ActorTargetFor(target, actorGroup.Key);
            GameObject prefab = LoadPrefab(actorTarget);
            Animator animator = AnimatorFor(prefab, actorTarget);
            RetargetLimb left = CaptureRetargetLimb(
                animator,
                "left_leg",
                HumanBodyBones.LeftUpperLeg,
                HumanBodyBones.LeftLowerLeg,
                HumanBodyBones.LeftFoot);
            RetargetLimb right = CaptureRetargetLimb(
                animator,
                "right_leg",
                HumanBodyBones.RightUpperLeg,
                HumanBodyBones.RightLowerLeg,
                HumanBodyBones.RightFoot);

            Dictionary<string, Vector3> carriedBend =
                new Dictionary<string, Vector3>(StringComparer.Ordinal);
            Dictionary<string, bool> carriedBendDefined =
                new Dictionary<string, bool>(StringComparer.Ordinal);
            foreach (string limbName in new[] { "left_leg", "right_leg" })
            {
                bool leftSide = limbName == "left_leg";
                bool defined = FirstSourceBendDirection(
                    mapping,
                    actorGroup.Key,
                    leftSide ? "left_hip" : "right_hip",
                    leftSide ? "left_knee" : "right_knee",
                    leftSide ? "left_ankle" : "right_ankle",
                    out Vector3 firstBend);
                carriedBend[limbName] = firstBend;
                carriedBendDefined[limbName] = defined;
            }

            foreach (BodyTrack track in actorGroup
                .OrderBy(item => item.start_frame)
                .ThenBy(item => item.semantic_id))
            {
                foreach (var limbSpec in new[] {
                    new {
                        name = "left_leg",
                        root = "left_hip",
                        mid = "left_knee",
                        end = "left_ankle",
                        geometry = left,
                    },
                    new {
                        name = "right_leg",
                        root = "right_hip",
                        mid = "right_knee",
                        end = "right_ankle",
                        geometry = right,
                    },
                })
                {
                    int rootIndex = JointIndex(track, limbSpec.root);
                    int midIndex = JointIndex(track, limbSpec.mid);
                    int endIndex = JointIndex(track, limbSpec.end);
                    foreach (BodyKeyframe frame in track.keyframes)
                    {
                        LegGeometrySolverSample sample =
                            new LegGeometrySolverSample {
                                frame = frame.timeline_frame,
                                phase_semantic_id = track.semantic_id,
                                actor_binding_id = track.actor_binding_id,
                                limb_name = limbSpec.name,
                                target_upper_length_m =
                                    limbSpec.geometry.upper_length_m,
                                target_lower_length_m =
                                    limbSpec.geometry.lower_length_m,
                                solved = false,
                            };
                        if (
                            frame.joint_positions_m == null
                            || rootIndex < 0
                            || midIndex < 0
                            || endIndex < 0
                            || rootIndex >= frame.joint_positions_m.Length
                            || midIndex >= frame.joint_positions_m.Length
                            || endIndex >= frame.joint_positions_m.Length)
                        {
                            unresolved++;
                            samples.Add(sample);
                            continue;
                        }

                        Vector3 sourceRoot =
                            Vector(frame.joint_positions_m[rootIndex]);
                        Vector3 sourceMid =
                            Vector(frame.joint_positions_m[midIndex]);
                        Vector3 sourceEnd =
                            Vector(frame.joint_positions_m[endIndex]);
                        bool currentBendDefined = TrySourceBendDirection(
                            sourceRoot,
                            sourceMid,
                            sourceEnd,
                            out Vector3 currentBend);
                        if (currentBendDefined)
                        {
                            carriedBend[limbSpec.name] = currentBend;
                            carriedBendDefined[limbSpec.name] = true;
                        }

                        TwoBoneGeometrySolution solution = SolveTwoBoneGeometry(
                            sourceRoot,
                            sourceMid,
                            sourceEnd,
                            sourceRoot,
                            limbSpec.geometry.upper_length_m,
                            limbSpec.geometry.lower_length_m,
                            carriedBend[limbSpec.name],
                            carriedBendDefined[limbSpec.name]);
                        sample.source_root = VectorData(sourceRoot);
                        sample.source_mid = VectorData(sourceMid);
                        sample.source_end = VectorData(sourceEnd);
                        sample.solved_root = VectorData(solution.root);
                        sample.solved_mid = VectorData(solution.mid);
                        sample.solved_end = VectorData(solution.end);
                        sample.bend_direction =
                            VectorData(solution.bend_direction);
                        sample.source_extension_ratio =
                            solution.source_extension_ratio;
                        sample.source_bend_direction_defined =
                            solution.source_bend_direction_defined;
                        sample.reach_was_clamped =
                            solution.reach_was_clamped;
                        sample.solved = solution.solved;
                        if (!solution.solved)
                        {
                            unresolved++;
                            samples.Add(sample);
                            continue;
                        }

                        sample.solved_upper_length_error_m = Mathf.Abs(
                            Vector3.Distance(solution.root, solution.mid)
                            - limbSpec.geometry.upper_length_m);
                        sample.solved_lower_length_error_m = Mathf.Abs(
                            Vector3.Distance(solution.mid, solution.end)
                            - limbSpec.geometry.lower_length_m);
                        maxUpperError = Mathf.Max(
                            maxUpperError,
                            sample.solved_upper_length_error_m);
                        maxLowerError = Mathf.Max(
                            maxLowerError,
                            sample.solved_lower_length_error_m);
                        samples.Add(sample);
                    }
                }
            }
        }

        return new LegGeometrySolverDiagnostic {
            diagnostic_version = "0.1.0",
            engine = "Unity",
            engine_version = Application.unityVersion,
            source_bundle_sha256 = mapping.source_bundle_sha256,
            max_upper_length_error_m = maxUpperError,
            max_lower_length_error_m = maxLowerError,
            unresolved_sample_count = unresolved,
            samples = samples
                .OrderBy(item => item.frame)
                .ThenBy(item => item.limb_name)
                .ToArray(),
        };
    }

    private static void CaptureRetargetProfile(Mapping mapping, Target target)
    {
        RetargetActor[] actors = mapping.body_tracks
            .GroupBy(item => item.actor_binding_id)
            .Select(group => group
                .OrderBy(item => item.start_frame)
                .ThenBy(item => item.semantic_id)
                .First())
            .Select(track => {
            ActorTarget actorTarget = ActorTargetFor(target, track.actor_binding_id);
            GameObject prefab = LoadPrefab(actorTarget);
            Animator animator = AnimatorFor(prefab, actorTarget);
            Transform[] mappedTransforms = track.joint_bindings
                .Select(binding => animator.GetBoneTransform(
                    (HumanBodyBones)Enum.Parse(
                        typeof(HumanBodyBones),
                        binding.target_human_bone)))
                .ToArray();
            RetargetJoint[] joints = track.joint_bindings.Select((binding, jointIndex) => {
                HumanBodyBones bone = (HumanBodyBones)Enum.Parse(typeof(HumanBodyBones), binding.target_human_bone);
                Transform transform = mappedTransforms[jointIndex];
                if (transform == null)
                {
                    if (IsRequiredHumanoidBone(bone))
                        throw new InvalidOperationException("Required Humanoid bone is not mapped: " + binding.target_human_bone);
                    return new RetargetJoint {
                        source_joint_name = binding.source_joint_name,
                        target_human_bone = binding.target_human_bone,
                        parent_index = binding.parent_index,
                        mapped = false,
                        reference_local = new RetargetTransform {
                            translation = VectorData(Vector3.zero),
                            rotation = QuaternionData(Quaternion.identity),
                            scale = VectorData(Vector3.one),
                        },
                        reference_component = new RetargetTransform {
                            translation = VectorData(Vector3.zero),
                            rotation = QuaternionData(Quaternion.identity),
                            scale = VectorData(Vector3.one),
                        },
                        target_parent_component_rotation = QuaternionData(Quaternion.identity),
                        canonical_reference_direction = VectorData(
                            CanonicalReferenceDirectionUnity(jointIndex)),
                        target_reference_direction_parent_local = VectorData(Vector3.zero),
                        canonical_to_target_parent_basis = QuaternionData(Quaternion.identity),
                    };
                }
                Quaternion local = transform.localRotation;
                Quaternion component = ReferenceComponentRotation(animator, transform);
                int childIndex = CanonicalPrimaryChildIndex(jointIndex);
                Transform child =
                    childIndex >= 0
                    && childIndex < mappedTransforms.Length
                    ? mappedTransforms[childIndex]
                    : null;
                Vector3 canonicalReference =
                    CanonicalReferenceDirectionUnity(jointIndex);
                Vector3 targetReference =
                    TargetReferenceDirectionParentLocal(
                        animator,
                        transform,
                        child,
                        local,
                        component);
                Quaternion basis = CanonicalToTargetParentBasis(
                    canonicalReference,
                    targetReference,
                    local,
                    component);
                return new RetargetJoint {
                    source_joint_name = binding.source_joint_name,
                    target_human_bone = binding.target_human_bone,
                    parent_index = binding.parent_index,
                    mapped = true,
                    reference_local = RetargetTransformData(transform),
                    reference_component = new RetargetTransform {
                        translation = VectorData(animator.avatarRoot.InverseTransformPoint(transform.position)),
                        rotation = QuaternionData(component),
                        scale = VectorData(transform.lossyScale),
                    },
                    target_parent_component_rotation = QuaternionData(ParentComponentRotation(local, component)),
                    canonical_reference_direction = VectorData(canonicalReference),
                    target_reference_direction_parent_local = VectorData(targetReference),
                    canonical_to_target_parent_basis = QuaternionData(basis),
                };
            }).ToArray();
            RetargetLimb[] limbs = new[] {
                CaptureRetargetLimb(
                    animator,
                    "left_leg",
                    HumanBodyBones.LeftUpperLeg,
                    HumanBodyBones.LeftLowerLeg,
                    HumanBodyBones.LeftFoot),
                CaptureRetargetLimb(
                    animator,
                    "right_leg",
                    HumanBodyBones.RightUpperLeg,
                    HumanBodyBones.RightLowerLeg,
                    HumanBodyBones.RightFoot),
                CaptureRetargetLimb(
                    animator,
                    "left_arm",
                    HumanBodyBones.LeftUpperArm,
                    HumanBodyBones.LeftLowerArm,
                    HumanBodyBones.LeftHand),
                CaptureRetargetLimb(
                    animator,
                    "right_arm",
                    HumanBodyBones.RightUpperArm,
                    HumanBodyBones.RightLowerArm,
                    HumanBodyBones.RightHand),
            };
            return new RetargetActor {
                actor_binding_id = track.actor_binding_id,
                prefab_path = actorTarget.prefab_path,
                joints = joints,
                limbs = limbs,
            };
        }).ToArray();
        RetargetProfile profile = new RetargetProfile {
            profile_version = "0.2.0",
            retargeting_method = "geometry-profile-v0.2+rest-direction-parent-basis-v1",
            canonical_reference_frame = "cutsceneai-humanoid-v1-unity-reflected-rest-directions",
            engine = "Unity",
            engine_version = Application.unityVersion,
            source_mapping_sha256 = target.source_mapping_sha256,
            actors = actors,
        };
        string evidenceRoot = EvidenceRoot(target);
        Directory.CreateDirectory(evidenceRoot);
        File.WriteAllText(Path.Combine(evidenceRoot, "retarget-profile.json"), JsonUtility.ToJson(profile, true), new UTF8Encoding(false));
    }

    private static float KneeAngle(Transform hip, Transform knee, Transform ankle)
    {
        if (hip == null || knee == null || ankle == null)
            return -1.0f;
        return Vector3.Angle(hip.position - knee.position, ankle.position - knee.position);
    }

    private static bool GroundClearance(
        Vector3 point,
        Transform excludedRoot,
        out float clearance)
    {
        RaycastHit[] hits = Physics.RaycastAll(
            point + Vector3.up * 1.0f,
            Vector3.down,
            5.0f,
            Physics.DefaultRaycastLayers,
            QueryTriggerInteraction.Ignore);
        foreach (RaycastHit hit in hits.OrderBy(item => item.distance))
        {
            if (hit.collider == null)
                continue;
            Transform hitTransform = hit.collider.transform;
            if (hitTransform == excludedRoot || hitTransform.IsChildOf(excludedRoot))
                continue;
            clearance = point.y - hit.point.y;
            return true;
        }
        clearance = 0.0f;
        return false;
    }

    private static float GroundFacingError(Vector3 forward, Vector3 towardTarget)
    {
        forward.y = 0.0f;
        towardTarget.y = 0.0f;
        if (forward.sqrMagnitude <= 1e-10f || towardTarget.sqrMagnitude <= 1e-10f)
            return -1.0f;
        return Vector3.Angle(forward.normalized, towardTarget.normalized);
    }

    private static float MaxLegMuscleAbs(HumanPose pose, out string muscleName)
    {
        float maximum = 0.0f;
        muscleName = "";
        for (int index = 0; index < pose.muscles.Length; index++)
        {
            string name = HumanTrait.MuscleName[index];
            if (name.IndexOf("Leg", StringComparison.OrdinalIgnoreCase) < 0
                && name.IndexOf("Foot", StringComparison.OrdinalIgnoreCase) < 0
                && name.IndexOf("Toes", StringComparison.OrdinalIgnoreCase) < 0)
                continue;
            float magnitude = Mathf.Abs(pose.muscles[index]);
            if (magnitude > maximum)
            {
                maximum = magnitude;
                muscleName = name;
            }
        }
        return maximum;
    }

    private static int JointIndex(BodyTrack track, string sourceJointName)
    {
        for (int index = 0; index < track.joint_bindings.Length; index++)
            if (string.Equals(
                track.joint_bindings[index].source_joint_name,
                sourceJointName,
                StringComparison.Ordinal))
                return index;
        return -1;
    }

    private static float SourceJointRotationDegrees(
        BodyTrack track,
        int timelineFrame,
        string sourceJointName)
    {
        int jointIndex = JointIndex(track, sourceJointName);
        if (jointIndex < 0)
            return -1.0f;
        BodyKeyframe keyframe = track.keyframes
            .FirstOrDefault(item => item.timeline_frame == timelineFrame);
        if (keyframe == null || jointIndex >= keyframe.joint_rotations.Length)
            return -1.0f;
        return Quaternion.Angle(
            Quaternion.identity,
            QuaternionValueOf(keyframe.joint_rotations[jointIndex]));
    }

    private static Dictionary<string, Transform> ResolveBodyTransforms(
        GameObject actor,
        ActorTarget actorTarget,
        BodyTrack track)
    {
        GameObject prefab = LoadPrefab(actorTarget);
        Animator prefabAnimator = AnimatorFor(prefab, actorTarget);
        Animator actorAnimator = AnimatorComponentFor(actor, actorTarget);
        Dictionary<string, Transform> resolved =
            new Dictionary<string, Transform>(StringComparer.Ordinal);

        for (int jointIndex = 0; jointIndex < track.joint_bindings.Length; jointIndex++)
        {
            JointBinding binding = track.joint_bindings[jointIndex];
            HumanBodyBones bone = (HumanBodyBones)Enum.Parse(
                typeof(HumanBodyBones),
                binding.target_human_bone);
            Transform prefabBone = prefabAnimator.GetBoneTransform(bone);
            if (prefabBone == null)
            {
                if (IsRequiredHumanoidBone(bone))
                    throw new InvalidOperationException(
                        "Required Humanoid bone is not mapped: "
                        + binding.target_human_bone);
                continue;
            }

            string path = AnimationUtility.CalculateTransformPath(
                prefabBone,
                prefabAnimator.transform);
            Transform actorBone = string.IsNullOrEmpty(path)
                ? actorAnimator.transform
                : actorAnimator.transform.Find(path);
            if (actorBone == null)
                throw new InvalidOperationException(
                    "Realized target bone path is missing: "
                    + binding.source_joint_name + " -> " + path);
            resolved[binding.source_joint_name] = actorBone;
        }
        return resolved;
    }

    private static void ProbeAnimationStreamKnees(
        GameObject prefab,
        ActorTarget target,
        out float leftDelta,
        out float rightDelta)
    {
        leftDelta = -1.0f;
        rightDelta = -1.0f;
        GameObject instance = UnityEngine.Object.Instantiate(prefab);
        instance.hideFlags = HideFlags.HideAndDontSave;
        Avatar genericAvatar = null;
        PlayableGraph graph = default(PlayableGraph);
        try
        {
            Animator animator = AnimatorFor(instance, target);
            Transform leftKnee = animator.GetBoneTransform(HumanBodyBones.LeftLowerLeg);
            Transform rightKnee = animator.GetBoneTransform(HumanBodyBones.RightLowerLeg);
            if (leftKnee == null || rightKnee == null)
                throw new InvalidOperationException(
                    "AnimationStream knee probe requires mapped lower-leg bones.");

            genericAvatar = AvatarBuilder.BuildGenericAvatar(
                animator.gameObject,
                string.Empty);
            if (
                genericAvatar == null
                || !genericAvatar.isValid
                || genericAvatar.isHuman)
                throw new InvalidOperationException(
                    "AnimationStream knee probe failed to build a valid Generic Avatar.");

            animator.avatar = genericAvatar;
            animator.runtimeAnimatorController = null;
            animator.applyRootMotion = false;
            animator.cullingMode = AnimatorCullingMode.AlwaysAnimate;
            animator.Rebind();
            animator.Update(0.0f);

            Quaternion leftReference = leftKnee.localRotation;
            Quaternion rightReference = rightKnee.localRotation;
            Quaternion leftTarget =
                leftReference * Quaternion.AngleAxis(25.0f, Vector3.right);
            Quaternion rightTarget =
                rightReference * Quaternion.AngleAxis(25.0f, Vector3.right);

            KneeStreamProbeJob job = new KneeStreamProbeJob {
                left_knee = animator.BindStreamTransform(leftKnee),
                right_knee = animator.BindStreamTransform(rightKnee),
                left_rotation = leftTarget,
                right_rotation = rightTarget,
            };

            graph = PlayableGraph.Create("CutSceneAI-KneeStreamProbe");
            graph.SetTimeUpdateMode(DirectorUpdateMode.Manual);
            AnimationScriptPlayable playable =
                AnimationScriptPlayable.Create(graph, job, 0);
            AnimationPlayableOutput output =
                AnimationPlayableOutput.Create(
                    graph,
                    "CutSceneAI-KneeStreamProbeOutput",
                    animator);
            output.SetSourcePlayable(playable);
            graph.Play();
            graph.Evaluate(1.0f / 60.0f);
            graph.Evaluate(1.0f / 60.0f);

            leftDelta = Quaternion.Angle(leftReference, leftKnee.localRotation);
            rightDelta = Quaternion.Angle(rightReference, rightKnee.localRotation);
        }
        finally
        {
            if (graph.IsValid())
                graph.Destroy();
            UnityEngine.Object.DestroyImmediate(instance);
            if (genericAvatar != null)
                UnityEngine.Object.DestroyImmediate(genericAvatar);
        }
    }

    private static CutSceneAIBodyStreamDriver ConfigureBodyStreamDriver(
        GameObject actor,
        ActorTarget actorTarget,
        BodyTrack[] tracks,
        PlayableDirector director,
        int fps)
    {
        if (tracks == null || tracks.Length == 0)
            throw new InvalidOperationException(
                "Body stream driver requires at least one body track.");

        BodyTrack template = tracks
            .OrderBy(item => item.start_frame)
            .ThenBy(item => item.semantic_id)
            .First();
        for (int trackIndex = 0; trackIndex < tracks.Length; trackIndex++)
        {
            BodyTrack candidate = tracks[trackIndex];
            if (candidate.joint_bindings.Length != template.joint_bindings.Length)
                throw new InvalidOperationException(
                    "Body tracks for one actor use different joint maps.");
            for (int jointIndex = 0; jointIndex < template.joint_bindings.Length; jointIndex++)
            {
                JointBinding expected = template.joint_bindings[jointIndex];
                JointBinding actual = candidate.joint_bindings[jointIndex];
                if (
                    actual.source_joint_name != expected.source_joint_name
                    || actual.target_human_bone != expected.target_human_bone
                    || actual.parent_index != expected.parent_index)
                    throw new InvalidOperationException(
                        "Body tracks for one actor use incompatible joint bindings.");
            }
        }

        GameObject prefab = LoadPrefab(actorTarget);
        Animator prefabAnimator = AnimatorFor(prefab, actorTarget);
        Animator actorAnimator = AnimatorComponentFor(actor, actorTarget);
        int jointCount = template.joint_bindings.Length;
        Transform[] prefabTransforms = new Transform[jointCount];
        Quaternion[] referenceRotations = new Quaternion[jointCount];
        Quaternion[] referenceComponents = new Quaternion[jointCount];
        Quaternion[] canonicalToTargetParentBases = Enumerable
            .Range(0, jointCount)
            .Select(_ => Quaternion.identity)
            .ToArray();

        List<int> mappedJointIndices = new List<int>();
        List<Transform> actorJoints = new List<Transform>();
        for (int jointIndex = 0; jointIndex < jointCount; jointIndex++)
        {
            JointBinding binding = template.joint_bindings[jointIndex];
            HumanBodyBones bone = (HumanBodyBones)Enum.Parse(
                typeof(HumanBodyBones),
                binding.target_human_bone);
            Transform prefabBone = prefabAnimator.GetBoneTransform(bone);
            if (prefabBone == null)
            {
                if (IsRequiredHumanoidBone(bone))
                    throw new InvalidOperationException(
                        "Required Humanoid bone is not mapped: "
                        + binding.target_human_bone);
                continue;
            }

            string path = AnimationUtility.CalculateTransformPath(
                prefabBone,
                prefabAnimator.transform);
            Transform actorBone = string.IsNullOrEmpty(path)
                ? actorAnimator.transform
                : actorAnimator.transform.Find(path);
            if (actorBone == null)
                throw new InvalidOperationException(
                    "Realized target bone path is missing: "
                    + binding.source_joint_name + " -> " + path);

            prefabTransforms[jointIndex] = prefabBone;
            referenceRotations[jointIndex] = prefabBone.localRotation;
            referenceComponents[jointIndex] =
                ReferenceComponentRotation(prefabAnimator, prefabBone);
            mappedJointIndices.Add(jointIndex);
            actorJoints.Add(actorBone);
        }

        for (int jointIndex = 0; jointIndex < jointCount; jointIndex++)
        {
            if (prefabTransforms[jointIndex] == null)
                continue;
            int childIndex = CanonicalPrimaryChildIndex(jointIndex);
            Transform child =
                childIndex >= 0
                && childIndex < jointCount
                ? prefabTransforms[childIndex]
                : null;
            canonicalToTargetParentBases[jointIndex] =
                CanonicalToTargetParentBasis(
                    CanonicalReferenceDirectionUnity(jointIndex),
                    TargetReferenceDirectionParentLocal(
                        prefabAnimator,
                        prefabTransforms[jointIndex],
                        child,
                        referenceRotations[jointIndex],
                        referenceComponents[jointIndex]),
                    referenceRotations[jointIndex],
                    referenceComponents[jointIndex]);
        }

        Dictionary<int, CutSceneAIBodyStreamDriver.PoseFrame> frameByTimelineFrame =
            new Dictionary<int, CutSceneAIBodyStreamDriver.PoseFrame>();
        foreach (BodyTrack track in tracks
            .OrderBy(item => item.start_frame)
            .ThenBy(item => item.semantic_id))
        {
            foreach (BodyKeyframe frame in track.keyframes)
            {
                Quaternion[] rotations = new Quaternion[mappedJointIndices.Count];
                for (int mappedIndex = 0; mappedIndex < mappedJointIndices.Count; mappedIndex++)
                {
                    int jointIndex = mappedJointIndices[mappedIndex];
                    Quaternion canonicalRotation =
                        QuaternionValueOf(frame.joint_rotations[jointIndex]);
                    if (jointIndex == 0)
                        canonicalRotation = RemoveGroundHeading(canonicalRotation);
                    rotations[mappedIndex] = RetargetRotation(
                        referenceRotations[jointIndex],
                        canonicalToTargetParentBases[jointIndex],
                        canonicalRotation);
                }
                frameByTimelineFrame[frame.timeline_frame] =
                    new CutSceneAIBodyStreamDriver.PoseFrame {
                        timeline_frame = frame.timeline_frame,
                        local_rotations = rotations,
                    };
            }
        }

        CutSceneAIBodyStreamDriver driver =
            actor.GetComponent<CutSceneAIBodyStreamDriver>();
        if (driver == null)
            driver = actor.AddComponent<CutSceneAIBodyStreamDriver>();
        driver.animator = actorAnimator;
        driver.director = director;
        driver.fps = fps;
        driver.joints = actorJoints.ToArray();
        driver.frames = frameByTimelineFrame
            .OrderBy(item => item.Key)
            .Select(item => item.Value)
            .ToArray();
        driver.RebuildGraph();
        return driver;
    }

    private static void EvaluateBodyStreamDrivers(
        PlayableDirector director,
        double time)
    {
        foreach (CutSceneAIBodyStreamDriver driver in
            UnityEngine.Object.FindObjectsByType<CutSceneAIBodyStreamDriver>(
                FindObjectsSortMode.None))
        {
            if (driver.director == director)
                driver.EvaluateAtTime(time);
        }
    }

    private static Dictionary<string, Quaternion> ReferenceBodyLocalRotations(
        ActorTarget actorTarget,
        BodyTrack track)
    {
        GameObject prefab = LoadPrefab(actorTarget);
        Animator animator = AnimatorFor(prefab, actorTarget);
        Dictionary<string, Quaternion> values =
            new Dictionary<string, Quaternion>(StringComparer.Ordinal);
        foreach (JointBinding binding in track.joint_bindings)
        {
            HumanBodyBones bone = (HumanBodyBones)Enum.Parse(
                typeof(HumanBodyBones),
                binding.target_human_bone);
            Transform transform = animator.GetBoneTransform(bone);
            if (transform != null)
                values[binding.source_joint_name] = transform.localRotation;
        }
        return values;
    }

    private static BodyRealizationDiagnostic CaptureBodyRealizationDiagnostic(
        Plan plan,
        Mapping mapping,
        Target target,
        PlayableDirector director,
        Dictionary<string, GameObject> actors,
        Dictionary<string, GameObject> motionRoots)
    {
        List<BodyRealizationSample> samples = new List<BodyRealizationSample>();
        Dictionary<string, Dictionary<string, Transform>> actorBones =
            new Dictionary<string, Dictionary<string, Transform>>();
        Dictionary<string, Dictionary<string, Quaternion>> actorReferenceRotations =
            new Dictionary<string, Dictionary<string, Quaternion>>();
        Dictionary<string, float> actorStreamProbeLeft =
            new Dictionary<string, float>();
        Dictionary<string, float> actorStreamProbeRight =
            new Dictionary<string, float>();
        foreach (BodyTrack actorTrack in mapping.body_tracks
            .GroupBy(item => item.actor_binding_id)
            .Select(group => group.First()))
        {
            if (!actors.TryGetValue(actorTrack.actor_binding_id, out GameObject actor))
                continue;
            ActorTarget actorTarget = ActorTargetFor(
                target,
                actorTrack.actor_binding_id);
            actorBones[actorTrack.actor_binding_id] = ResolveBodyTransforms(
                actor,
                actorTarget,
                actorTrack);
            actorReferenceRotations[actorTrack.actor_binding_id] =
                ReferenceBodyLocalRotations(actorTarget, actorTrack);
            ProbeAnimationStreamKnees(
                LoadPrefab(actorTarget),
                actorTarget,
                out float streamProbeLeft,
                out float streamProbeRight);
            actorStreamProbeLeft[actorTrack.actor_binding_id] = streamProbeLeft;
            actorStreamProbeRight[actorTrack.actor_binding_id] = streamProbeRight;
        }

        director.RebuildGraph();
        for (int frame = 0; frame < mapping.duration_frames; frame++)
        {
            BodyTrack active = mapping.body_tracks
                .Where(item => item.start_frame <= frame && frame < item.end_frame)
                .OrderBy(item => item.start_frame)
                .FirstOrDefault();
            if (active == null)
                continue;
            if (!actors.TryGetValue(active.actor_binding_id, out GameObject actor))
                continue;
            if (!motionRoots.TryGetValue(active.actor_binding_id, out GameObject motionRoot))
                continue;

            director.time = (double)frame / mapping.fps;
            director.Evaluate();
            EvaluateBodyStreamDrivers(director, director.time);
            Physics.SyncTransforms();

            ActorTarget actorTarget = ActorTargetFor(target, active.actor_binding_id);
            Animator animator = AnimatorComponentFor(actor, actorTarget);
            Dictionary<string, Transform> bones = actorBones[active.actor_binding_id];
            Transform hips = bones["pelvis"];
            Transform leftUpperLeg = bones["left_hip"];
            Transform rightUpperLeg = bones["right_hip"];
            Transform leftLowerLeg = bones["left_knee"];
            Transform rightLowerLeg = bones["right_knee"];
            Transform leftFoot = bones["left_ankle"];
            Transform rightFoot = bones["right_ankle"];

            bool leftGroundFound = GroundClearance(
                leftFoot.position,
                motionRoot.transform,
                out float leftClearance);
            bool rightGroundFound = GroundClearance(
                rightFoot.position,
                motionRoot.transform,
                out float rightClearance);

            SemanticPerformance cue = plan.semantics.scenes.Single().performance_cues
                .SingleOrDefault(item => item.cue_id == active.source_performance_cue_id);
            string targetBindingId = cue == null ? null : cue.look_at_binding_id;
            float facingError = -1.0f;
            if (!string.IsNullOrEmpty(targetBindingId)
                && actors.TryGetValue(targetBindingId, out GameObject targetActor))
            {
                facingError = GroundFacingError(
                    motionRoot.transform.forward,
                    targetActor.transform.position - motionRoot.transform.position);
            }

            float maxLegMuscle = -1.0f;
            string maxLegMuscleName = "not-applicable-direct-bone";
            if (animator.avatar != null
                && animator.avatar.isValid
                && animator.avatar.isHuman)
            {
                HumanPose pose;
                using (HumanPoseHandler handler = new HumanPoseHandler(
                    animator.avatar,
                    animator.avatarRoot))
                {
                    pose = SnapshotHumanPose(handler);
                }
                maxLegMuscle = MaxLegMuscleAbs(
                    pose,
                    out maxLegMuscleName);
            }
            float sourceLeftKneeRotation = SourceJointRotationDegrees(
                active,
                frame,
                "left_knee");
            float sourceRightKneeRotation = SourceJointRotationDegrees(
                active,
                frame,
                "right_knee");
            Dictionary<string, Quaternion> referenceRotations =
                actorReferenceRotations[active.actor_binding_id];
            float realizedLeftKneeLocalDelta = Quaternion.Angle(
                referenceRotations["left_knee"],
                leftLowerLeg.localRotation);
            float realizedRightKneeLocalDelta = Quaternion.Angle(
                referenceRotations["right_knee"],
                rightLowerLeg.localRotation);
            Vector3 leftAnkleDirection =
                (leftFoot.position - leftLowerLeg.position).normalized;
            Vector3 rightAnkleDirection =
                (rightFoot.position - rightLowerLeg.position).normalized;

            samples.Add(new BodyRealizationSample {
                frame = frame,
                phase_semantic_id = active.semantic_id,
                actor_binding_id = active.actor_binding_id,
                target_binding_id = targetBindingId,
                motion_root_position = VectorData(motionRoot.transform.position),
                motion_root_rotation = QuaternionData(motionRoot.transform.rotation),
                actor_forward = VectorData(motionRoot.transform.forward),
                hips_position = VectorData(hips.position),
                left_knee_position = VectorData(leftLowerLeg.position),
                right_knee_position = VectorData(rightLowerLeg.position),
                left_foot_position = VectorData(leftFoot.position),
                right_foot_position = VectorData(rightFoot.position),
                left_ground_found = leftGroundFound,
                right_ground_found = rightGroundFound,
                left_ground_clearance_m = leftClearance,
                right_ground_clearance_m = rightClearance,
                left_knee_angle_deg = KneeAngle(leftUpperLeg, leftLowerLeg, leftFoot),
                right_knee_angle_deg = KneeAngle(rightUpperLeg, rightLowerLeg, rightFoot),
                source_left_knee_rotation_deg = sourceLeftKneeRotation,
                source_right_knee_rotation_deg = sourceRightKneeRotation,
                realized_left_knee_local_delta_deg = realizedLeftKneeLocalDelta,
                realized_right_knee_local_delta_deg = realizedRightKneeLocalDelta,
                animation_stream_probe_left_knee_delta_deg =
                    actorStreamProbeLeft[active.actor_binding_id],
                animation_stream_probe_right_knee_delta_deg =
                    actorStreamProbeRight[active.actor_binding_id],
                realized_left_ankle_direction_from_knee =
                    VectorData(leftAnkleDirection),
                realized_right_ankle_direction_from_knee =
                    VectorData(rightAnkleDirection),
                target_facing_error_deg = facingError,
                max_leg_muscle_abs = maxLegMuscle,
                max_leg_muscle_name = maxLegMuscleName,
            });
        }
        director.time = 0.0;
        director.Evaluate();
        EvaluateBodyStreamDrivers(director, director.time);
        Physics.SyncTransforms();
        return new BodyRealizationDiagnostic {
            diagnostic_version = "0.1.0",
            engine = "Unity",
            engine_version = Application.unityVersion,
            source_bundle_sha256 = mapping.source_bundle_sha256,
            samples = samples.ToArray(),
        };
    }

    private static AnimationClip CreateFaceClip(FaceTrack track, GameObject prefab, ActorTarget target, int fps)
    {
        Animator animator = AnimatorFor(prefab, target);
        SkinnedMeshRenderer face = FaceFor(prefab, target);
        string path = AnimationUtility.CalculateTransformPath(face.transform, animator.transform);
        AnimationClip clip = new AnimationClip { name = Path.GetFileNameWithoutExtension(track.target_animation_path), frameRate = fps };
        for (int curveIndex = 0; curveIndex < track.curve_bindings.Length; curveIndex++)
        {
            string property = "blendShape." + track.curve_bindings[curveIndex].target_blendshape_name;
            SetCurve(clip, path, typeof(SkinnedMeshRenderer), property,
                Keys(track.start_frame, fps, track.keyframes.Select(frame => Tuple.Create(frame.timeline_frame, frame.weights[curveIndex] * 100.0f))));
        }
        ValidateClipBindingPaths(clip, prefab, target);
        EnsureFolder(track.target_animation_path);
        AssetDatabase.CreateAsset(clip, track.target_animation_path);
        return clip;
    }

    private static AnimationClip CreateCameraClip(CameraTrack track, int fps)
    {
        AnimationClip clip = new AnimationClip { name = Path.GetFileNameWithoutExtension(track.target_animation_path), frameRate = fps };
        SetCurve(clip, "", typeof(Transform), "m_LocalPosition.x", Keys(track.start_frame, fps, track.keyframes.Select(frame => Tuple.Create(frame.timeline_frame, frame.position_m.x))));
        SetCurve(clip, "", typeof(Transform), "m_LocalPosition.y", Keys(track.start_frame, fps, track.keyframes.Select(frame => Tuple.Create(frame.timeline_frame, frame.position_m.y))));
        SetCurve(clip, "", typeof(Transform), "m_LocalPosition.z", Keys(track.start_frame, fps, track.keyframes.Select(frame => Tuple.Create(frame.timeline_frame, frame.position_m.z))));
        SetCurve(clip, "", typeof(Transform), "m_LocalRotation.x", Keys(track.start_frame, fps, track.keyframes.Select(frame => Tuple.Create(frame.timeline_frame, frame.rotation.x))));
        SetCurve(clip, "", typeof(Transform), "m_LocalRotation.y", Keys(track.start_frame, fps, track.keyframes.Select(frame => Tuple.Create(frame.timeline_frame, frame.rotation.y))));
        SetCurve(clip, "", typeof(Transform), "m_LocalRotation.z", Keys(track.start_frame, fps, track.keyframes.Select(frame => Tuple.Create(frame.timeline_frame, frame.rotation.z))));
        SetCurve(clip, "", typeof(Transform), "m_LocalRotation.w", Keys(track.start_frame, fps, track.keyframes.Select(frame => Tuple.Create(frame.timeline_frame, frame.rotation.w))));
        SetCurve(clip, "", typeof(Camera), "m_FocalLength", Keys(track.start_frame, fps, track.keyframes.Select(frame => Tuple.Create(frame.timeline_frame, frame.focal_length_mm))));
        clip.EnsureQuaternionContinuity();
        EnsureFolder(track.target_animation_path);
        AssetDatabase.CreateAsset(clip, track.target_animation_path);
        return clip;
    }

    private static AnimationClip CreateMotionRootClip(
        BodyTrack track,
        int fps,
        Transform motionRoot)
    {
        Vector3 baseWorldPosition = motionRoot.position;
        Quaternion baseWorldRotation = motionRoot.rotation;
        Transform parent = motionRoot.parent;

        AnimationClip clip = new AnimationClip {
            name = Path.GetFileNameWithoutExtension(MotionRootAnimationPath(track)),
            frameRate = fps,
        };
        List<Tuple<int, float>> rootX = new List<Tuple<int, float>>();
        List<Tuple<int, float>> rootY = new List<Tuple<int, float>>();
        List<Tuple<int, float>> rootZ = new List<Tuple<int, float>>();
        foreach (BodyKeyframe frame in track.keyframes)
        {
            Vector3 actorLocalOffset = new Vector3(
                frame.root_position_m.x,
                0.0f,
                frame.root_position_m.z);
            Vector3 worldPosition =
                baseWorldPosition + baseWorldRotation * actorLocalOffset;
            Vector3 localPosition =
                parent == null
                    ? worldPosition
                    : parent.InverseTransformPoint(worldPosition);
            rootX.Add(Tuple.Create(frame.timeline_frame, localPosition.x));
            rootY.Add(Tuple.Create(frame.timeline_frame, localPosition.y));
            rootZ.Add(Tuple.Create(frame.timeline_frame, localPosition.z));
        }
        SetCurve(
            clip, "", typeof(Transform), "m_LocalPosition.x",
            Keys(track.start_frame, fps, rootX));
        SetCurve(
            clip, "", typeof(Transform), "m_LocalPosition.y",
            Keys(track.start_frame, fps, rootY));
        SetCurve(
            clip, "", typeof(Transform), "m_LocalPosition.z",
            Keys(track.start_frame, fps, rootZ));

        List<Tuple<int, float>> headingQx = new List<Tuple<int, float>>();
        List<Tuple<int, float>> headingQy = new List<Tuple<int, float>>();
        List<Tuple<int, float>> headingQz = new List<Tuple<int, float>>();
        List<Tuple<int, float>> headingQw = new List<Tuple<int, float>>();
        foreach (BodyKeyframe frame in track.keyframes)
        {
            Quaternion actorLocalHeading = GroundHeading(
                QuaternionValueOf(frame.joint_rotations[0]));
            Quaternion worldRotation =
                baseWorldRotation * actorLocalHeading;
            Quaternion localRotation =
                parent == null
                    ? worldRotation
                    : Quaternion.Inverse(parent.rotation) * worldRotation;
            headingQx.Add(Tuple.Create(frame.timeline_frame, localRotation.x));
            headingQy.Add(Tuple.Create(frame.timeline_frame, localRotation.y));
            headingQz.Add(Tuple.Create(frame.timeline_frame, localRotation.z));
            headingQw.Add(Tuple.Create(frame.timeline_frame, localRotation.w));
        }
        SetCurve(
            clip, "", typeof(Transform), "m_LocalRotation.x",
            Keys(track.start_frame, fps, headingQx));
        SetCurve(
            clip, "", typeof(Transform), "m_LocalRotation.y",
            Keys(track.start_frame, fps, headingQy));
        SetCurve(
            clip, "", typeof(Transform), "m_LocalRotation.z",
            Keys(track.start_frame, fps, headingQz));
        SetCurve(
            clip, "", typeof(Transform), "m_LocalRotation.w",
            Keys(track.start_frame, fps, headingQw));
        clip.EnsureQuaternionContinuity();

        string path = MotionRootAnimationPath(track);
        EnsureFolder(path);
        AssetDatabase.CreateAsset(clip, path);
        return clip;
    }

    private static TimelineClip AddAnimationClip(AnimationTrack track, string name, AnimationClip animation, int start, int end, int fps)
    {
        TimelineClip clip = track.CreateClip<AnimationPlayableAsset>();
        ((AnimationPlayableAsset)clip.asset).clip = animation;
        clip.start = (double)start / fps;
        clip.duration = (double)(end - start) / fps;
        clip.displayName = name;
        return clip;
    }

    private static void ImportCore(Plan plan, Mapping mapping, Target target)
    {
        CaptureRetargetProfile(mapping, target);
        LegGeometrySolverDiagnostic legGeometry =
            CaptureLegGeometrySolverDiagnostic(mapping, target);
        string preflightEvidenceRoot = EvidenceRoot(target);
        Directory.CreateDirectory(preflightEvidenceRoot);
        File.WriteAllText(
            Path.Combine(
                preflightEvidenceRoot,
                "leg-geometry-solver-diagnostic.json"),
            JsonUtility.ToJson(legGeometry, true),
            new UTF8Encoding(false));
        Scene scene = CreateRealizationScene(target);
        GameObject root = new GameObject("CutSceneAI_" + mapping.source_scene_id);
        SceneManager.MoveGameObjectToScene(root, scene);
        PlayableDirector director = root.AddComponent<PlayableDirector>();
        TimelineAsset timeline = ScriptableObject.CreateInstance<TimelineAsset>();
        timeline.name = Path.GetFileNameWithoutExtension(target.timeline_asset_path);
        timeline.editorSettings.frameRate = mapping.fps;
        timeline.durationMode = TimelineAsset.DurationMode.FixedLength;
        timeline.fixedDuration = (double)mapping.duration_frames / mapping.fps;
        EnsureFolder(target.timeline_asset_path);
        AssetDatabase.CreateAsset(timeline, target.timeline_asset_path);
        director.playableAsset = timeline;

        Dictionary<string, GameObject> actors = new Dictionary<string, GameObject>();
        Dictionary<string, GameObject> motionRoots = new Dictionary<string, GameObject>();
        Dictionary<string, AnimationTrack> animationRoots = new Dictionary<string, AnimationTrack>();
        Dictionary<string, AnimationTrack> motionRootTracks = new Dictionary<string, AnimationTrack>();
        foreach (ActorTarget actorTarget in target.actors)
        {
            ActorPlan actorPlan = plan.sequences.Single().actors.Single(
                item => item.binding_id == actorTarget.actor_binding_id);
            SceneBinding sceneBinding = SceneBindingFor(target, actorPlan.source_entity_id);
            if (sceneBinding == null
                && string.IsNullOrEmpty(actorPlan.prefab_path)
                && !string.IsNullOrEmpty(target.source_scene_asset_path)
                && !string.Equals(actorPlan.kind, "character", StringComparison.OrdinalIgnoreCase))
                continue;

            GameObject instance;
            if (sceneBinding != null)
            {
                instance = SceneObjectAtPath(scene, sceneBinding);
            }
            else
            {
                instance = (GameObject)PrefabUtility.InstantiatePrefab(
                    LoadPrefab(actorTarget), scene);
                instance.name = ActorPrefix + actorTarget.actor_binding_id;
            }
            ApplyActorTransform(instance, actorPlan);

            Transform originalParent = instance.transform.parent;
            Vector3 originalLocalPosition = instance.transform.localPosition;
            Quaternion originalLocalRotation = instance.transform.localRotation;
            Vector3 originalLocalScale = instance.transform.localScale;

            GameObject motionRoot = new GameObject(
                MotionRootPrefix + actorTarget.actor_binding_id);
            SceneManager.MoveGameObjectToScene(motionRoot, scene);
            motionRoot.transform.SetParent(originalParent, false);
            motionRoot.transform.localPosition = originalLocalPosition;
            motionRoot.transform.localRotation = originalLocalRotation;
            motionRoot.transform.localScale = Vector3.one;

            instance.transform.SetParent(motionRoot.transform, false);
            instance.transform.localPosition = Vector3.zero;
            instance.transform.localRotation = Quaternion.identity;
            instance.transform.localScale = originalLocalScale;

            Animator motionRootAnimator = motionRoot.AddComponent<Animator>();
            AnimationTrack motionTrack = timeline.CreateTrack<AnimationTrack>(
                null,
                MotionRootPrefix + actorTarget.actor_binding_id);
            motionTrack.trackOffset = TrackOffset.ApplySceneOffsets;
            director.SetGenericBinding(motionTrack, motionRootAnimator);

            AnimationTrack rootTrack = timeline.CreateTrack<AnimationTrack>(
                null,
                BodyActorPrefix + actorTarget.actor_binding_id);
            rootTrack.trackOffset = TrackOffset.ApplySceneOffsets;
            Animator actorAnimator = AnimatorFor(instance, actorTarget);
            BodyTrack actorBodyTrack = mapping.body_tracks
                .FirstOrDefault(item =>
                    item.actor_binding_id == actorTarget.actor_binding_id);
            if (actorBodyTrack != null)
            {
                Avatar genericAvatar = AvatarBuilder.BuildGenericAvatar(
                    actorAnimator.gameObject,
                    string.Empty);
                if (
                    genericAvatar == null
                    || !genericAvatar.isValid
                    || genericAvatar.isHuman)
                    throw new InvalidOperationException(
                        "Failed to build a valid Generic Avatar for actor: "
                        + actorTarget.actor_binding_id);
                genericAvatar.name =
                    "CutSceneAI_Generic_" + actorTarget.actor_binding_id;
                string genericAvatarPath = GenericAvatarPath(actorBodyTrack);
                EnsureFolder(genericAvatarPath);
                AssetDatabase.CreateAsset(genericAvatar, genericAvatarPath);
                actorAnimator.avatar = genericAvatar;
                actorAnimator.runtimeAnimatorController = null;
                actorAnimator.applyRootMotion = false;
                actorAnimator.Rebind();
                actorAnimator.Update(0.0f);
            }
            // Body clips remain on Timeline as semantic/readback evidence only.
            // Runtime skeletal realization is owned exclusively by
            // CutSceneAIBodyStreamDriver through Unity's AnimationStream.
            actors.Add(actorTarget.actor_binding_id, instance);
            motionRoots.Add(actorTarget.actor_binding_id, motionRoot);
            motionRootTracks.Add(actorTarget.actor_binding_id, motionTrack);
            animationRoots.Add(actorTarget.actor_binding_id, rootTrack);
        }
        foreach (ActorPlan actorPlan in plan.sequences.Single().actors)
        {
            if (actors.ContainsKey(actorPlan.binding_id)) continue;

            SceneBinding sceneBinding = SceneBindingFor(target, actorPlan.source_entity_id);
            GameObject instance;
            if (sceneBinding != null)
            {
                instance = SceneObjectAtPath(scene, sceneBinding);
            }
            else if (!string.IsNullOrEmpty(actorPlan.prefab_path))
            {
                GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(actorPlan.prefab_path);
                if (prefab == null)
                    throw new InvalidOperationException("Missing Unity prefab for semantic entity: " + actorPlan.prefab_path);
                instance = (GameObject)PrefabUtility.InstantiatePrefab(prefab, scene);
            }
            else
            {
                PrimitiveType primitive = string.Equals(
                    actorPlan.placeholder_primitive,
                    "capsule",
                    StringComparison.OrdinalIgnoreCase
                ) ? PrimitiveType.Capsule : PrimitiveType.Cube;
                instance = GameObject.CreatePrimitive(primitive);
                SceneManager.MoveGameObjectToScene(instance, scene);
            }

            if (sceneBinding == null)
                instance.name = ActorPrefix + actorPlan.binding_id;
            ApplyActorTransform(instance, actorPlan);
            actors.Add(actorPlan.binding_id, instance);
        }
        foreach (IGrouping<string, BodyTrack> actorTracks in mapping.body_tracks
            .GroupBy(item => item.actor_binding_id))
        {
            string actorBindingId = actorTracks.Key;
            ConfigureBodyStreamDriver(
                actors[actorBindingId],
                ActorTargetFor(target, actorBindingId),
                actorTracks.ToArray(),
                director,
                mapping.fps);
        }

        foreach (BodyTrack body in mapping.body_tracks)
        {
            ActorTarget actorTarget = ActorTargetFor(target, body.actor_binding_id);
            AnimationClip motionRootAnimation = CreateMotionRootClip(
                body,
                mapping.fps,
                motionRoots[body.actor_binding_id].transform);
            AnimationTrack motionTrack = motionRootTracks[body.actor_binding_id];
            TimelineClip motionRootClip = AddAnimationClip(
                motionTrack,
                MotionRootPrefix + body.actor_binding_id + "|" + body.semantic_id,
                motionRootAnimation,
                body.start_frame,
                body.end_frame,
                mapping.fps);
            ((AnimationPlayableAsset)motionRootClip.asset).removeStartOffset = false;

            AnimationClip animation = CreateBodyClip(
                body,
                LoadPrefab(actorTarget),
                actorTarget,
                mapping.fps);
            AnimationTrack track = animationRoots[body.actor_binding_id];
            TimelineClip bodyClip = AddAnimationClip(
                track,
                BodyPrefix + body.actor_binding_id + "|" + body.semantic_id,
                animation,
                body.start_frame,
                body.end_frame,
                mapping.fps);
            AnimationPlayableAsset bodyPlayable =
                (AnimationPlayableAsset)bodyClip.asset;
            bodyPlayable.removeStartOffset = true;
            // Diagnostic baseline: Unity Timeline foot IK can override the authored
            // Humanoid leg pose when root/pelvis constraints do not yet agree with
            // the generated foot contacts. Preserve the retargeted clip pose first;
            // explicit CutSceneAI foot locking/IK belongs in the canonical motion
            // processing layer and will be added after retarget fidelity is proven.
            bodyPlayable.applyFootIK = false;
        }
        foreach (FaceTrack face in mapping.facial_tracks)
        {
            ActorTarget actorTarget = ActorTargetFor(target, face.actor_binding_id);
            AnimationClip animation = CreateFaceClip(face, LoadPrefab(actorTarget), actorTarget, mapping.fps);
            AnimationTrack track = timeline.CreateTrack<AnimationTrack>(animationRoots[face.actor_binding_id], FacePrefix + face.actor_binding_id + "|" + face.semantic_id);
            director.SetGenericBinding(track, AnimatorComponentFor(actors[face.actor_binding_id], actorTarget));
            AddAnimationClip(track, track.name, animation, face.start_frame, face.end_frame, mapping.fps);
        }
        foreach (AudioTrack audio in mapping.audio_tracks)
        {
            GameObject audioActor = actors[audio.actor_binding_id];
            AudioSource source = audioActor.GetComponent<AudioSource>();
            if (source == null)
                source = audioActor.AddComponent<AudioSource>();
            source.playOnAwake = false;
            UnityEngine.Timeline.AudioTrack track = timeline.CreateTrack<UnityEngine.Timeline.AudioTrack>(null, AudioPrefix + audio.actor_binding_id + "|" + audio.dialogue_cue_id);
            TimelineClip clip = track.CreateClip<AudioPlayableAsset>();
            AudioPlayableAsset playable = (AudioPlayableAsset)clip.asset;
            playable.clip = AssetDatabase.LoadAssetAtPath<AudioClip>(audio.target_audio_path); playable.loop = false;
            clip.start = (double)audio.start_frame / mapping.fps; clip.duration = (double)(audio.end_frame - audio.start_frame) / mapping.fps;
            director.SetGenericBinding(track, source);
        }
        foreach (CameraTrack cameraTrack in mapping.camera_tracks)
        {
            GameObject cameraObject = new GameObject(CameraPrefix + cameraTrack.semantic_id);
            Camera camera = cameraObject.AddComponent<Camera>(); camera.usePhysicalProperties = true;
            camera.sensorSize = new Vector2(cameraTrack.sensor_width_mm, cameraTrack.sensor_height_mm);
            Animator animator = cameraObject.AddComponent<Animator>();
            AnimationClip animation = CreateCameraClip(cameraTrack, mapping.fps);
            AnimationTrack cameraMotion = timeline.CreateTrack<AnimationTrack>(null, CameraMotionPrefix + cameraTrack.semantic_id);
            TimelineClip motion = AddAnimationClip(cameraMotion, cameraMotion.name, animation, cameraTrack.start_frame, cameraTrack.end_frame, mapping.fps);
            director.SetGenericBinding(motion.parentTrack, animator);
            ActivationTrack activation = timeline.CreateTrack<ActivationTrack>(null, CameraPrefix + cameraTrack.semantic_id);
            activation.postPlaybackState = ActivationTrack.PostPlaybackState.Inactive;
            TimelineClip activeClip = activation.CreateDefaultClip();
            activeClip.start = (double)cameraTrack.start_frame / mapping.fps;
            activeClip.duration = (double)(cameraTrack.end_frame - cameraTrack.start_frame) / mapping.fps;
            director.SetGenericBinding(activation, cameraObject);
            cameraObject.SetActive(false);
        }
        EditorUtility.SetDirty(timeline); AssetDatabase.SaveAssets();
        EnsureFolder(target.scene_asset_path); EditorSceneManager.SaveScene(scene, target.scene_asset_path);
        string evidenceRoot = EvidenceRoot(target);
        Directory.CreateDirectory(evidenceRoot);
        BodyRealizationDiagnostic bodyDiagnostic = CaptureBodyRealizationDiagnostic(
            plan,
            mapping,
            target,
            director,
            actors,
            motionRoots);
        File.WriteAllText(
            Path.Combine(evidenceRoot, "body-realization-diagnostic.json"),
            JsonUtility.ToJson(bodyDiagnostic, true),
            new UTF8Encoding(false));
        Lifecycle receipt = new Lifecycle { lifecycle_version = "0.1.0", import_process_id = ProcessId,
            import_completed = true, saved = true, restarted = false, readback_completed = false,
            render_completed = false, retargeting_method = "rest-direction-parent-basis-v1+animation-stream-body-v1+generic-avatar+actor-motion-root-v3-authored-transform",
            retarget_profile = "retarget-profile.json", errors = Array.Empty<string>() };
        File.WriteAllText(Path.Combine(evidenceRoot, "lifecycle.json"), JsonUtility.ToJson(receipt, true), new UTF8Encoding(false));
        Debug.Log("CutSceneAI native Unity import saved successfully.");
    }

    public static void Import()
    {
        Plan plan = LoadPlan(); Mapping mapping = LoadMapping(); Target target = LoadTarget();
        Preflight(plan, mapping, target);
        string[] generatedAssets = GeneratedAssetPaths(mapping, target);
        CleanupGeneratedAssets(generatedAssets);
        try
        {
            ImportCore(plan, mapping, target);
        }
        catch
        {
            CleanupGeneratedAssets(generatedAssets);
            throw;
        }
    }

    private static RealizedSection Section(string semanticId, string actorId, string assetRef, TimelineClip clip, int fps)
        => new RealizedSection { semantic_id = semanticId, actor_binding_id = actorId, asset_ref = assetRef,
            start_frame = Frame(clip.start, fps), end_frame = Frame(clip.end, fps), placeholder = string.IsNullOrEmpty(assetRef) };
    private static string[] Parts(string name, string prefix)
    {
        if (!name.StartsWith(prefix, StringComparison.Ordinal)) return null;
        string[] parts = name.Substring(prefix.Length).Split('|');
        return parts.Length == 2 ? parts : null;
    }
    private static IEnumerable<TrackAsset> Descendants(TrackAsset track)
    {
        yield return track;
        foreach (TrackAsset child in track.GetChildTracks())
            foreach (TrackAsset descendant in Descendants(child)) yield return descendant;
    }
    private static IEnumerable<TrackAsset> AllTracks(TimelineAsset timeline)
        => timeline.GetRootTracks().SelectMany(Descendants);

    private static EngineReadback Readback(Plan plan, Mapping mapping, Target target, TimelineAsset timeline)
    {
        List<RealizedSection> body = new List<RealizedSection>(); List<RealizedSection> face = new List<RealizedSection>();
        List<RealizedSection> cameras = new List<RealizedSection>(); List<RealizedSection> audio = new List<RealizedSection>();
        foreach (TrackAsset track in AllTracks(timeline))
        {
            string[] parts = Parts(track.name, BodyPrefix);
            if (parts != null && track is AnimationTrack)
                foreach (TimelineClip clip in track.GetClips())
                    body.Add(Section(
                        parts[1],
                        parts[0],
                        AssetDatabase.GetAssetPath(((AnimationPlayableAsset)clip.asset).clip),
                        clip,
                        mapping.fps));
            else if (track.name.StartsWith(BodyActorPrefix, StringComparison.Ordinal)
                && track is AnimationTrack)
                foreach (TimelineClip clip in track.GetClips())
                {
                    string[] clipParts = Parts(clip.displayName, BodyPrefix);
                    if (clipParts != null)
                        body.Add(Section(
                            clipParts[1],
                            clipParts[0],
                            AssetDatabase.GetAssetPath(
                                ((AnimationPlayableAsset)clip.asset).clip),
                            clip,
                            mapping.fps));
                }
            parts = Parts(track.name, FacePrefix);
            if (parts != null && track is AnimationTrack)
                foreach (TimelineClip clip in track.GetClips()) face.Add(Section(parts[1], parts[0], AssetDatabase.GetAssetPath(((AnimationPlayableAsset)clip.asset).clip), clip, mapping.fps));
            parts = Parts(track.name, AudioPrefix);
            if (parts != null && track is UnityEngine.Timeline.AudioTrack)
                foreach (TimelineClip clip in track.GetClips()) audio.Add(Section(parts[1], parts[0], AssetDatabase.GetAssetPath(((AudioPlayableAsset)clip.asset).clip), clip, mapping.fps));
            if (track.name.StartsWith(CameraPrefix, StringComparison.Ordinal) && track is ActivationTrack)
            {
                string semanticId = track.name.Substring(CameraPrefix.Length);
                CameraTrack camera = mapping.camera_tracks.Single(item => item.semantic_id == semanticId);
                foreach (TimelineClip clip in track.GetClips()) cameras.Add(Section(semanticId, null, camera.target_animation_path, clip, mapping.fps));
            }
        }
        if (body.Count != mapping.body_tracks.Length || face.Count != mapping.facial_tracks.Length || cameras.Count != mapping.camera_tracks.Length || audio.Count != mapping.audio_tracks.Length)
            throw new InvalidOperationException("Saved Timeline does not contain every generated modality section.");
        return new EngineReadback { readback_version = "0.1.0", engine = "unity", engine_version = Application.unityVersion,
            adapter_version = plan.adapter_version, timeline_asset = target.timeline_asset_path, semantics = plan.semantics,
            evidence = new ReadbackEvidence { animation_sections = body.OrderBy(item => item.semantic_id).ToArray(), facial_sections = face.OrderBy(item => item.semantic_id).ToArray(),
                camera_sections = cameras.OrderBy(item => item.semantic_id).ToArray(), audio_sections = audio.OrderBy(item => item.semantic_id).ToArray() },
            warnings = Array.Empty<string>() };
    }

    private static RenderManifest Render(Mapping mapping, Target target, PlayableDirector director)
    {
        string output = Path.Combine(ProjectRoot, target.render.output_directory.Replace('/', Path.DirectorySeparatorChar));
        if (Directory.Exists(output) && Directory.EnumerateFileSystemEntries(output).Any())
            throw new InvalidOperationException("Refusing to replace existing render output: " + output);
        Directory.CreateDirectory(output);
        List<RenderedFrame> frames = new List<RenderedFrame>();
        RenderTexture texture = new RenderTexture(target.render.width, target.render.height, 24, RenderTextureFormat.ARGB32);
        Texture2D pixels = new Texture2D(target.render.width, target.render.height, TextureFormat.RGB24, false);
        try
        {
            for (int frame = 0; frame < mapping.duration_frames; frame++)
            {
                director.time = (double)frame / mapping.fps;
                director.Evaluate();
                EvaluateBodyStreamDrivers(director, director.time);
                Camera[] active = UnityEngine.Object.FindObjectsByType<Camera>(FindObjectsSortMode.None)
                    .Where(item => item.gameObject.activeInHierarchy
                        && item.enabled
                        && item.gameObject.name.StartsWith(CameraPrefix, StringComparison.Ordinal))
                    .ToArray();
                if (active.Length != 1) throw new InvalidOperationException("Expected exactly one active generated camera at frame " + frame + ".");
                Camera camera = active[0]; camera.targetTexture = texture; RenderTexture.active = texture; camera.Render();
                pixels.ReadPixels(new Rect(0, 0, target.render.width, target.render.height), 0, 0); pixels.Apply();
                byte[] png = pixels.EncodeToPNG(); string name = frame.ToString("D6") + ".png";
                File.WriteAllBytes(Path.Combine(output, name), png);
                frames.Add(new RenderedFrame { frame = frame, relative_path = name, sha256 = Sha256(png) });
                camera.targetTexture = null;
            }
        }
        finally { RenderTexture.active = null; UnityEngine.Object.DestroyImmediate(pixels); texture.Release(); UnityEngine.Object.DestroyImmediate(texture); }
        return new RenderManifest { manifest_version = "0.1.0", engine = "unity", source_bundle_sha256 = mapping.source_bundle_sha256,
            expected_frame_count = mapping.duration_frames, rendered_frame_count = frames.Count, frames = frames.ToArray() };
    }

    public static void ReadbackAndRender()
    {
        Plan plan = LoadPlan(); Mapping mapping = LoadMapping(); Target target = LoadTarget();
        string evidenceRoot = EvidenceRoot(target);
        string lifecyclePath = Path.Combine(evidenceRoot, "lifecycle.json");
        if (!File.Exists(lifecyclePath)) throw new InvalidOperationException("Native import receipt is missing.");
        Lifecycle lifecycle = JsonUtility.FromJson<Lifecycle>(File.ReadAllText(lifecyclePath));
        if (!lifecycle.import_completed || !lifecycle.saved || lifecycle.import_process_id == ProcessId)
            throw new InvalidOperationException("Readback must run after a separate saved editor process.");
        EditorSceneManager.OpenScene(target.scene_asset_path, OpenSceneMode.Single);
        TimelineAsset timeline = AssetDatabase.LoadAssetAtPath<TimelineAsset>(target.timeline_asset_path);
        if (timeline == null) throw new InvalidOperationException("Saved Timeline is missing after restart.");
        PlayableDirector director = UnityEngine.Object.FindObjectsByType<PlayableDirector>(FindObjectsSortMode.None).Single(item => item.playableAsset == timeline);
        EngineReadback readback = Readback(plan, mapping, target, timeline);
        Directory.CreateDirectory(evidenceRoot);
        File.WriteAllText(Path.Combine(evidenceRoot, "readback.json"), JsonUtility.ToJson(readback, true), new UTF8Encoding(false));
        RenderManifest manifest = Render(mapping, target, director);
        File.WriteAllText(Path.Combine(evidenceRoot, "render-manifest.json"), JsonUtility.ToJson(manifest, true), new UTF8Encoding(false));
        lifecycle.readback_process_id = ProcessId; lifecycle.restarted = true; lifecycle.readback_completed = true;
        lifecycle.render_completed = manifest.rendered_frame_count == manifest.expected_frame_count;
        File.WriteAllText(lifecyclePath, JsonUtility.ToJson(lifecycle, true), new UTF8Encoding(false));
        Debug.Log("CutSceneAI native Unity restart/readback/render completed successfully.");
    }
}
"""


_UNITY_BODY_STREAM_RUNTIME_TEMPLATE = r"""// Generated by CutSceneAI Unity Adapter runtime support v0.1.0.
using System;
using Unity.Collections;
using UnityEngine;
using UnityEngine.Animations;
using UnityEngine.Playables;

[ExecuteAlways]
public sealed class CutSceneAIBodyStreamDriver : MonoBehaviour
{
    [Serializable]
    public sealed class PoseFrame
    {
        public int timeline_frame;
        public Quaternion[] local_rotations;
    }

    public Animator animator;
    public PlayableDirector director;
    public int fps = 30;
    public Transform[] joints = Array.Empty<Transform>();
    public PoseFrame[] frames = Array.Empty<PoseFrame>();

    private PlayableGraph graph;
    private AnimationScriptPlayable playable;
    private NativeArray<TransformStreamHandle> handles;
    private NativeArray<Quaternion> rotations;
    private BodyStreamJob job;
    private bool initialized;

    private struct BodyStreamJob : IAnimationJob
    {
        public NativeArray<TransformStreamHandle> handles;
        public NativeArray<Quaternion> rotations;

        private void Apply(AnimationStream stream)
        {
            for (int index = 0; index < handles.Length; index++)
            {
                TransformStreamHandle handle = handles[index];
                if (handle.IsValid(stream))
                    handle.SetLocalRotation(stream, rotations[index]);
            }
        }

        public void ProcessRootMotion(AnimationStream stream)
        {
            Apply(stream);
        }

        public void ProcessAnimation(AnimationStream stream)
        {
            Apply(stream);
        }
    }

    public void RebuildGraph()
    {
        ReleaseGraph();
        if (
            animator == null
            || joints == null
            || joints.Length == 0
            || frames == null
            || frames.Length == 0)
            return;

        animator.cullingMode = AnimatorCullingMode.AlwaysAnimate;
        animator.applyRootMotion = false;
        animator.runtimeAnimatorController = null;
        animator.Rebind();
        animator.Update(0.0f);

        handles = new NativeArray<TransformStreamHandle>(
            joints.Length,
            Allocator.Persistent);
        rotations = new NativeArray<Quaternion>(
            joints.Length,
            Allocator.Persistent);
        for (int index = 0; index < joints.Length; index++)
        {
            if (joints[index] == null)
                throw new InvalidOperationException(
                    "CutSceneAI body stream driver contains an unmapped target joint.");
            handles[index] = animator.BindStreamTransform(joints[index]);
            rotations[index] = joints[index].localRotation;
        }

        job = new BodyStreamJob {
            handles = handles,
            rotations = rotations,
        };
        graph = PlayableGraph.Create(
            "CutSceneAI-BodyStream-" + gameObject.name);
        graph.SetTimeUpdateMode(DirectorUpdateMode.Manual);
        playable = AnimationScriptPlayable.Create(graph, job, 0);
        AnimationPlayableOutput output = AnimationPlayableOutput.Create(
            graph,
            "CutSceneAI-BodyStreamOutput",
            animator);
        output.SetSourcePlayable(playable);
        graph.Play();
        initialized = true;
    }

    public void EvaluateAtTime(double timeSeconds)
    {
        if (!initialized || !graph.IsValid())
            RebuildGraph();
        if (!initialized || frames == null || frames.Length == 0)
            return;

        float framePosition = (float)(timeSeconds * Math.Max(1, fps));
        int upper = 0;
        while (
            upper < frames.Length
            && frames[upper].timeline_frame < framePosition)
            upper++;

        int lower;
        float blend;
        if (upper <= 0)
        {
            lower = 0;
            upper = 0;
            blend = 0.0f;
        }
        else if (upper >= frames.Length)
        {
            lower = frames.Length - 1;
            upper = lower;
            blend = 0.0f;
        }
        else
        {
            lower = upper - 1;
            float span =
                frames[upper].timeline_frame - frames[lower].timeline_frame;
            blend = span <= 0.0f
                ? 0.0f
                : Mathf.Clamp01(
                    (framePosition - frames[lower].timeline_frame) / span);
        }

        Quaternion[] left = frames[lower].local_rotations;
        Quaternion[] right = frames[upper].local_rotations;
        if (
            left == null
            || right == null
            || left.Length != joints.Length
            || right.Length != joints.Length)
            throw new InvalidOperationException(
                "CutSceneAI body stream pose does not match its mapped joint count.");

        for (int jointIndex = 0; jointIndex < joints.Length; jointIndex++)
            rotations[jointIndex] = Quaternion.Slerp(
                left[jointIndex],
                right[jointIndex],
                blend);

        playable.SetJobData(job);
        graph.Evaluate(1.0f / Math.Max(1, fps));
    }

    private void Update()
    {
        if (director != null)
            EvaluateAtTime(director.time);
    }

    private void OnDisable()
    {
        ReleaseGraph();
    }

    private void OnDestroy()
    {
        ReleaseGraph();
    }

    private void ReleaseGraph()
    {
        initialized = false;
        if (graph.IsValid())
            graph.Destroy();
        if (handles.IsCreated)
            handles.Dispose();
        if (rotations.IsCreated)
            rotations.Dispose();
    }
}
"""


def render_unity_body_stream_runtime_script() -> str:
    """Render the reusable runtime body-stream driver used by Unity realizations."""

    return _UNITY_BODY_STREAM_RUNTIME_TEMPLATE


def render_unity_native_performance_script(
    package: UnityNativePerformancePackage,
) -> str:
    """Render the deterministic Unity editor realization/readback/render script."""

    return (
        _UNITY_NATIVE_TEMPLATE.replace("__PLAN_BASE64__", _encoded_json(package.plan))
        .replace("__MAPPING_BASE64__", _encoded_json(package.mapping))
        .replace("__TARGET_BASE64__", _encoded_json(package.target))
    )


_UNITY_RUNNER_TEMPLATE = r"""[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$UnityEditor,
    [Parameter(Mandatory = $true)][string]$ProjectPath,
    [string]$Python = "python"
)
$ErrorActionPreference = "Stop"
$packageRoot = Split-Path -Parent $PSScriptRoot
$projectRoot = (Resolve-Path $ProjectPath).Path
$bundlePath = Join-Path $packageRoot "performance.bundle.zip"
$actualBundleHash = (Get-FileHash -Algorithm SHA256 $bundlePath).Hash.ToLowerInvariant()
if ($actualBundleHash -ne "__BUNDLE_SHA256__") { throw "Performance bundle checksum mismatch." }

function Copy-CutSceneAIFile([string]$Source, [string]$Destination) {
    if (Test-Path $Destination) { throw "Refusing to replace existing project file: $Destination" }
    $directory = Split-Path -Parent $Destination
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Destination
}

$runtimeSource = Join-Path $PSScriptRoot "CutSceneAIBodyStreamDriver.cs"
$runtimeTarget = Join-Path $projectRoot "Assets\CutSceneAI\Runtime\CutSceneAIBodyStreamDriver.cs"
Copy-CutSceneAIFile $runtimeSource $runtimeTarget
$editorSource = Join-Path $PSScriptRoot "CutSceneAIGeneratedPerformance.cs"
$editorTarget = Join-Path $projectRoot "Assets\Editor\CutSceneAIGeneratedPerformance.cs"
Copy-CutSceneAIFile $editorSource $editorTarget
$audioTargets = ConvertFrom-Json @'
__AUDIO_TARGETS_JSON__
'@
foreach ($audio in $audioTargets) {
    $source = Join-Path $packageRoot $audio.source
    $destination = Join-Path $projectRoot $audio.destination
    Copy-CutSceneAIFile $source $destination
    $hash = (Get-FileHash -Algorithm SHA256 $destination).Hash.ToLowerInvariant()
    if ($hash -ne $audio.sha256) { throw "Copied WAV checksum mismatch: $destination" }
}

$evidenceRoot = Join-Path $projectRoot "__EVIDENCE_ROOT_RELATIVE__"
New-Item -ItemType Directory -Force -Path $evidenceRoot | Out-Null
$importLog = Join-Path $evidenceRoot "import.log"
& $UnityEditor -batchmode -quit -projectPath $projectRoot -logFile $importLog -executeMethod CutSceneAIGeneratedPerformance.Import
if ($LASTEXITCODE -ne 0) { throw "Unity native import failed with exit code $LASTEXITCODE. See $importLog" }
$readbackLog = Join-Path $evidenceRoot "readback-render.log"
& $UnityEditor -batchmode -quit -projectPath $projectRoot -logFile $readbackLog -executeMethod CutSceneAIGeneratedPerformance.ReadbackAndRender
if ($LASTEXITCODE -ne 0) { throw "Unity restart/readback/render failed with exit code $LASTEXITCODE. See $readbackLog" }
$combinedLog = Join-Path $evidenceRoot "editor.log"
Get-Content -Raw -Path $importLog, $readbackLog | Set-Content -NoNewline -Encoding UTF8 $combinedLog
& $Python (Join-Path $PSScriptRoot "collect-native-evidence.py") --engine unity --mapping (Join-Path $packageRoot "mapping.json") --lifecycle (Join-Path $evidenceRoot "lifecycle.json") --readback (Join-Path $evidenceRoot "readback.json") --render-manifest (Join-Path $evidenceRoot "render-manifest.json") --retarget-profile (Join-Path $evidenceRoot "retarget-profile.json") --editor-log $combinedLog --output (Join-Path $evidenceRoot "engine-run.evidence.json")
if ($LASTEXITCODE -ne 0) { throw "Native evidence collection failed with exit code $LASTEXITCODE." }
Write-Host "CutSceneAI Unity native gate completed: $evidenceRoot"
"""


def _windows_relative(path: str) -> str:
    return path.replace("/", "\\")


def render_unity_native_runner_script(
    package: UnityNativePerformancePackage,
) -> str:
    audio_targets = []
    for track in package.mapping.audio_tracks:
        source = f"Payload/{track.target_audio_path}"
        audio_targets.append(
            {
                "source": _windows_relative(source),
                "destination": _windows_relative(track.target_audio_path),
                "sha256": track.source_artifact.sha256,
            }
        )
    bundle_data = render_performance_bundle(package.bundle)
    evidence_root = PurePosixPath(
        package.target.render.output_directory
    ).parent.as_posix()
    return (
        _UNITY_RUNNER_TEMPLATE.replace("__BUNDLE_SHA256__", _sha256(bundle_data))
        .replace("__EVIDENCE_ROOT_RELATIVE__", _windows_relative(evidence_root))
        .replace(
            "__AUDIO_TARGETS_JSON__",
            json.dumps(audio_targets, indent=2, sort_keys=True),
        )
    )


def _write_entry(archive: ZipFile, path: str, data: bytes) -> None:
    entry = ZipInfo(path, date_time=_ZIP_TIMESTAMP)
    entry.compress_type = ZIP_DEFLATED
    entry.external_attr = 0o644 << 16
    archive.writestr(entry, data)


def render_unity_native_performance_package(
    package: UnityNativePerformancePackage,
    *,
    evidence_collector_script: str,
) -> bytes:
    """Render a deterministic portable Unity native-realization harness archive."""

    output = BytesIO()
    with ZipFile(output, "w") as archive:
        _write_entry(
            archive,
            "Scripts/CutSceneAIGeneratedPerformance.cs",
            render_unity_native_performance_script(package).encode("utf-8"),
        )
        _write_entry(
            archive,
            "Scripts/CutSceneAIBodyStreamDriver.cs",
            render_unity_body_stream_runtime_script().encode("utf-8"),
        )
        _write_entry(
            archive,
            "Scripts/run-unity-native.ps1",
            render_unity_native_runner_script(package).encode("utf-8"),
        )
        _write_entry(
            archive,
            "Scripts/collect-native-evidence.py",
            evidence_collector_script.encode("utf-8"),
        )
        _write_entry(
            archive,
            "mapping.json",
            render_unity_performance_mapping(package.mapping).encode("utf-8"),
        )
        _write_entry(
            archive,
            "plan.json",
            render_unity_plan(package.plan).encode("utf-8"),
        )
        _write_entry(
            archive,
            "target.json",
            (
                json.dumps(
                    package.target.model_dump(mode="json"), indent=2, sort_keys=True
                )
                + "\n"
            ).encode("utf-8"),
        )
        _write_entry(
            archive,
            "performance.bundle.zip",
            render_performance_bundle(package.bundle),
        )
        audio_by_path = {
            track.artifact.relative_path: track
            for track in package.bundle.package.audio_tracks
        }
        for mapped in package.mapping.audio_tracks:
            source_track = audio_by_path[mapped.source_artifact.relative_path]
            data = package.bundle.artifact_files[source_track.artifact.relative_path]
            if _sha256(data) != mapped.source_artifact.sha256:
                raise ValueError(
                    "Unity native package WAV changed after bundle verification."
                )
            path = PurePosixPath("Payload") / mapped.target_audio_path
            _write_entry(archive, path.as_posix(), data)
    return output.getvalue()
