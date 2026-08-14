from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from cutsceneai_parity import TimelineSemantics
from cutsceneai_performance import (
    PerformanceBundle,
    load_performance_bundle,
    render_performance_bundle,
)
from pydantic import BaseModel

from .models import UnrealExportPlan, UnrealMeshType
from .native_models import UnrealNativeRealizationTarget
from .performance import compile_performance_bundle
from .performance_models import UnrealPerformanceMapping
from .serialization import render_unreal_performance_mapping, render_unreal_plan

UNREAL_NATIVE_IMPORT_FILENAME = "cutsceneai-unreal-native-import.py"
UNREAL_NATIVE_READBACK_FILENAME = "cutsceneai-unreal-native-readback.py"
UNREAL_NATIVE_RENDER_FILENAME = "cutsceneai-unreal-native-render.py"
UNREAL_NATIVE_RUNNER_FILENAME = "run-unreal-native.ps1"
_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


@dataclass(frozen=True)
class UnrealNativePerformancePackage:
    bundle: PerformanceBundle
    plan: UnrealExportPlan
    mapping: UnrealPerformanceMapping
    target: UnrealNativeRealizationTarget
    semantics: TimelineSemantics


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _mapping_target_root(mapping: UnrealPerformanceMapping) -> str:
    marker = "/Body/"
    path = mapping.body_tracks[0].target_animation_path
    if marker not in path:
        raise ValueError(
            "Unreal body target path does not contain the required Body folder."
        )
    return path.split(marker, 1)[0]


def compile_unreal_native_performance_package(
    bundle: PerformanceBundle,
    *,
    plan: UnrealExportPlan,
    mapping: UnrealPerformanceMapping,
    target: UnrealNativeRealizationTarget,
    semantics: TimelineSemantics,
) -> UnrealNativePerformancePackage:
    """Validate one unchanged bundle and its explicit Unreal native target."""

    rendered_bundle = render_performance_bundle(bundle)
    verified_bundle = load_performance_bundle(rendered_bundle)
    expected_mapping = compile_performance_bundle(
        verified_bundle,
        export_plan=plan,
        semantics=semantics,
        target_path=_mapping_target_root(mapping),
    )
    if mapping != expected_mapping:
        raise ValueError(
            "Unreal performance mapping is not the deterministic mapping of the bundle."
        )
    rendered_mapping = render_unreal_performance_mapping(mapping).encode("utf-8")
    if target.source_mapping_sha256 != _sha256(rendered_mapping):
        raise ValueError("Unreal native target does not match the mapping SHA-256.")
    if (
        target.project_id != mapping.project_id
        or plan.project_id != mapping.project_id
        or semantics.project_id != mapping.project_id
    ):
        raise ValueError(
            "Unreal native target, plan, mapping, and semantics use different projects."
        )
    sequence = plan.sequences[0]
    if (
        target.sequence_package_path != sequence.package_path
        or target.sequence_asset_name != sequence.asset_name
        or mapping.source_scene_id != sequence.source_scene_id
        or semantics.scenes[0].source_scene_id != sequence.source_scene_id
    ):
        raise ValueError("Unreal native target paths or scene do not match the plan.")

    actor_targets = {item.actor_binding_id: item for item in target.actors}
    expected_actor_ids = {item.actor_binding_id for item in mapping.body_tracks} | {
        item.actor_binding_id for item in mapping.facial_tracks
    }
    if set(actor_targets) != expected_actor_ids:
        raise ValueError(
            "Unreal native target actors do not exactly match generated body and face tracks."
        )
    plan_actors = {item.binding_id: item for item in sequence.actors}
    if set(actor_targets) - set(plan_actors):
        raise ValueError("Unreal native target references an unknown plan actor.")
    for binding_id, native_target in actor_targets.items():
        actor = plan_actors[binding_id]
        if (
            actor.placeholder
            or actor.mesh_type is not UnrealMeshType.SKELETAL_MESH
            or actor.asset_path != native_target.skeletal_mesh_path
        ):
            raise ValueError(
                "Unreal native target requires the same non-placeholder skeletal mesh as the plan."
            )

    return UnrealNativePerformancePackage(
        bundle=verified_bundle,
        plan=plan.model_copy(deep=True),
        mapping=mapping.model_copy(deep=True),
        target=target.model_copy(deep=True),
        semantics=semantics.model_copy(deep=True),
    )


def _json(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


_UNREAL_IMPORT_TEMPLATE = r'''"""Generated CutSceneAI Unreal 5.8 native performance importer.

Run only through run-unreal-native.ps1. Every destination is preflighted before mutation.
"""
from hashlib import sha256
import json
import os
from pathlib import Path

import unreal

PLAN = json.loads(__PLAN_JSON__)
MAPPING = json.loads(__MAPPING_JSON__)
TARGET = json.loads(__TARGET_JSON__)
EXPECTED_BONES = tuple(item["target_bone_name"] for item in MAPPING["body_tracks"][0]["joint_bindings"])
EXPECTED_MORPHS = tuple(item["target_curve_name"] for item in MAPPING["facial_tracks"][0]["curve_bindings"])
BODY_PREFIX = "CSA|BODY|"
FACE_PREFIX = "CSA|FACIAL|"
CAMERA_PREFIX = "CSA|CAMERA|"
AUDIO_PREFIX = "CSA|AUDIO|"

def _root():
    if "__file__" not in globals():
        raise RuntimeError("Native importer must run from its extracted file.")
    return Path(__file__).resolve().parent.parent

def _saved_root():
    path = Path(unreal.Paths.project_saved_dir()) / "CutSceneAI" / "Native" / "Unreal"
    path.mkdir(parents=True, exist_ok=True)
    return path

def _asset_path(path):
    name = path.rsplit("/", 1)[-1]
    return path if "." in name else f"{path}.{name}"

def _load(path, expected, description):
    value = unreal.EditorAssetLibrary.load_asset(path)
    if not isinstance(value, expected):
        raise RuntimeError(f"{description} could not be loaded: {path}")
    return value

def _property(value, name):
    try:
        return value.get_editor_property(name)
    except Exception:
        return getattr(value, name)

def _component(value, name):
    return float(_property(value, name))

def _vector(data):
    return unreal.Vector(float(data["x"]), float(data["y"]), float(data["z"]))

def _quat(data):
    return unreal.Quat(float(data["x"]), float(data["y"]), float(data["z"]), float(data["w"]))

def _quat_multiply(first, second):
    ax, ay, az, aw = (_component(first, key) for key in ("x", "y", "z", "w"))
    bx, by, bz, bw = (_component(second, key) for key in ("x", "y", "z", "w"))
    return unreal.Quat(
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )

def _target(binding_id):
    return next(item for item in TARGET["actors"] if item["actor_binding_id"] == binding_id)

def _plan_actor(binding_id):
    return next(item for item in PLAN["sequences"][0]["actors"] if item["binding_id"] == binding_id)

def _source_audio(track):
    relative = Path("Audio") / track["source_artifact"]["relative_path"]
    source = (_root() / relative).resolve()
    source.relative_to(_root())
    if not source.is_file() or sha256(source.read_bytes()).hexdigest() != track["source_artifact"]["sha256"]:
        raise RuntimeError(f"Bundled WAV is missing or changed: {relative}")
    return source

def _sequence_path():
    return f"{TARGET['sequence_package_path']}/{TARGET['sequence_asset_name']}"

def _preflight():
    version = str(unreal.SystemLibrary.get_engine_version())
    if not version.startswith("5.8.0"):
        raise RuntimeError(f"Unreal Engine 5.8.0 is required, got {version}.")
    targets = [_sequence_path()]
    targets.extend(item["target_animation_path"] for item in MAPPING["body_tracks"])
    targets.extend(item["target_animation_path"] for item in MAPPING["facial_tracks"])
    targets.extend(item["target_sound_path"] for item in MAPPING["audio_tracks"])
    if len(targets) != len(set(targets)):
        raise RuntimeError("Native mapping contains duplicate Unreal asset targets.")
    conflicts = [path for path in targets if unreal.EditorAssetLibrary.does_asset_exist(path)]
    if conflicts:
        raise RuntimeError("Refusing to replace existing Unreal assets:\n" + "\n".join(f"- {item}" for item in conflicts))
    for actor in TARGET["actors"]:
        mesh = _load(actor["skeletal_mesh_path"], unreal.SkeletalMesh, "Target skeletal mesh")
        skeleton = _property(mesh, "skeleton")
        if not isinstance(skeleton, unreal.Skeleton):
            raise RuntimeError(f"Target mesh has no Skeleton: {actor['skeletal_mesh_path']}")
        reference = unreal.AnimPoseExtensions.get_reference_pose(skeleton)
        names = {str(item) for item in unreal.AnimPoseExtensions.get_bone_names(reference)}
        missing_bones = sorted(set(EXPECTED_BONES) - names)
        missing_morphs = sorted(set(EXPECTED_MORPHS) - set(mesh.get_all_morph_target_names()))
        if missing_bones:
            raise RuntimeError("Target is missing UE5 Mannequin bones: " + ", ".join(missing_bones))
        if missing_morphs:
            raise RuntimeError("Target is missing ARKit-52 morph targets: " + ", ".join(missing_morphs))
    for track in MAPPING["audio_tracks"]:
        _source_audio(track)

def _create_anim_sequence(path, mesh, frame_count):
    folder, name = path.rsplit("/", 1)
    factory = unreal.AnimSequenceFactory()
    factory.set_editor_property("target_skeleton", _property(mesh, "skeleton"))
    factory.set_editor_property("preview_skeletal_mesh", mesh)
    sequence = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, unreal.AnimSequence, factory)
    if not isinstance(sequence, unreal.AnimSequence):
        raise RuntimeError(f"Unable to create AnimSequence: {path}")
    controller = _property(sequence, "controller")
    controller.open_bracket("CutSceneAI generated performance", False)
    controller.set_frame_rate(unreal.FrameRate(MAPPING["fps"], 1), False)
    controller.set_number_of_frames(unreal.FrameNumber(frame_count), False)
    return sequence, controller

def _create_body(track):
    mesh = _load(_target(track["actor_binding_id"])["skeletal_mesh_path"], unreal.SkeletalMesh, "Target skeletal mesh")
    sequence, controller = _create_anim_sequence(track["target_animation_path"], mesh, track["end_frame"] - track["start_frame"])
    reference = unreal.AnimPoseExtensions.get_reference_pose(_property(mesh, "skeleton"))
    try:
        for index, binding in enumerate(track["joint_bindings"]):
            bone = unreal.Name(binding["target_bone_name"])
            reference_transform = unreal.AnimPoseExtensions.get_ref_bone_pose(reference, bone, unreal.AnimPoseSpaces.LOCAL)
            reference_location = _property(reference_transform, "translation")
            reference_rotation = _property(reference_transform, "rotation")
            reference_scale = _property(reference_transform, "scale3d")
            positions = []
            rotations = []
            scales = []
            for frame in track["keyframes"]:
                if index == 0:
                    offset = frame["root_location_cm"]
                    positions.append(unreal.Vector(_component(reference_location, "x") + offset["x"], _component(reference_location, "y") + offset["y"], _component(reference_location, "z") + offset["z"]))
                else:
                    positions.append(reference_location)
                rotations.append(_quat_multiply(reference_rotation, _quat(frame["joint_rotations"][index])))
                scales.append(reference_scale)
            if not controller.add_bone_curve(bone, False):
                raise RuntimeError(f"Unable to add generated bone track: {bone}")
            if not controller.set_bone_track_keys(bone, positions, rotations, scales, False):
                raise RuntimeError(f"Unable to set generated bone keys: {bone}")
    finally:
        controller.close_bracket(False)
    unreal.EditorAssetLibrary.save_loaded_asset(sequence, False)
    return sequence

def _create_face(track):
    mesh = _load(_target(track["actor_binding_id"])["skeletal_mesh_path"], unreal.SkeletalMesh, "Target skeletal mesh")
    sequence, controller = _create_anim_sequence(track["target_animation_path"], mesh, track["end_frame"] - track["start_frame"])
    controller.close_bracket(False)
    times = [(frame["timeline_frame"] - track["start_frame"]) / MAPPING["fps"] for frame in track["keyframes"]]
    for index, binding in enumerate(track["curve_bindings"]):
        name = unreal.Name(binding["target_curve_name"])
        unreal.AnimationLibrary.add_curve(sequence, name, unreal.RawCurveTrackTypes.RCT_FLOAT, False)
        unreal.AnimationLibrary.add_float_curve_keys(sequence, name, times, [frame["weights"][index] for frame in track["keyframes"]])
    unreal.EditorAssetLibrary.save_loaded_asset(sequence, False)
    return sequence

def _import_audio():
    if not MAPPING["audio_tracks"]:
        return
    tasks = []
    for track in MAPPING["audio_tracks"]:
        folder, name = track["target_sound_path"].rsplit("/", 1)
        task = unreal.AssetImportTask()
        task.set_editor_property("filename", str(_source_audio(track)))
        task.set_editor_property("destination_path", folder)
        task.set_editor_property("destination_name", name)
        task.set_editor_property("automated", True)
        task.set_editor_property("replace_existing", False)
        task.set_editor_property("save", True)
        tasks.append(task)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    for track in MAPPING["audio_tracks"]:
        _load(_asset_path(track["target_sound_path"]), unreal.SoundBase, "Imported SoundWave")

def _set_actor_transform(actor, data):
    actor.set_actor_location(_vector(data["location_cm"]), False, True)
    actor.set_actor_rotation(_quat(data["rotation"]).rotator(), True)
    actor.set_actor_scale3d(_vector(data["scale"]))

def _live_actor(sequence, binding, expected):
    unreal.LevelSequenceEditorBlueprintLibrary.force_update()
    binding_id = sequence.get_binding_id(binding)
    return next((item for item in unreal.LevelSequenceEditorBlueprintLibrary.get_bound_objects(binding_id) if isinstance(item, expected)), None)

def _actor_binding(sequence, subsystem, binding_id):
    target = _target(binding_id)
    planned = _plan_actor(binding_id)
    binding = subsystem.add_spawnable_from_class(sequence, unreal.SkeletalMeshActor)
    binding.set_display_name(planned["display_name"])
    template = binding.get_object_template()
    live = _live_actor(sequence, binding, unreal.SkeletalMeshActor)
    mesh = _load(target["skeletal_mesh_path"], unreal.SkeletalMesh, "Target skeletal mesh")
    for actor in (template, live):
        if actor is None:
            continue
        actor.set_actor_label(planned["display_name"])
        _set_actor_transform(actor, planned["transform"])
        component = _property(actor, "skeletal_mesh_component")
        component.set_skeletal_mesh_asset(mesh)
    if live is None:
        raise RuntimeError(f"Unable to resolve live skeletal spawnable: {binding_id}")
    subsystem.save_default_spawnable_state(binding)
    for track in binding.find_tracks_by_exact_type(unreal.MovieScene3DTransformTrack):
        binding.remove_track(track)
    return binding

def _add_animation(binding, track, prefix):
    native_track = binding.add_track(unreal.MovieSceneSkeletalAnimationTrack)
    native_track.set_display_name(prefix + track["semantic_id"])
    section = native_track.add_section()
    section.set_range(track["start_frame"], track["end_frame"])
    params = _property(section, "params")
    params.set_editor_property("animation", _load(_asset_path(track["target_animation_path"]), unreal.AnimSequenceBase, "Generated animation"))
    params.set_editor_property("force_custom_mode", True)
    section.set_editor_property("params", params)

def _add_audio(sequence, track):
    native = sequence.add_track(unreal.MovieSceneAudioTrack)
    native.set_display_name(AUDIO_PREFIX + track["actor_binding_id"] + "|" + track["dialogue_cue_id"])
    section = native.add_section()
    section.set_range(track["start_frame"], track["end_frame"])
    section.set_sound(_load(_asset_path(track["target_sound_path"]), unreal.SoundBase, "Generated audio"))
    section.set_looping(False)

def _key(channel, frame, value):
    channel.add_key(unreal.FrameNumber(int(frame)), float(value), 0.0, unreal.MovieSceneTimeUnit.DISPLAY_RATE, unreal.MovieSceneKeyInterpolation.LINEAR)

def _transform_channels(section):
    channels = {str(_property(item, "channel_name")): item for item in section.get_all_channels()}
    aliases = (
        ("Location.X", "Translation.X"), ("Location.Y", "Translation.Y"), ("Location.Z", "Translation.Z"),
        ("Rotation.X",), ("Rotation.Y",), ("Rotation.Z",),
        ("Scale.X",), ("Scale.Y",), ("Scale.Z",),
    )
    result = []
    for names in aliases:
        channel = next((channels[name] for name in names if name in channels), None)
        if channel is None:
            raise RuntimeError("Generated camera transform channel is missing: " + "/".join(names))
        result.append(channel)
    return result

def _add_camera(sequence, subsystem, track):
    binding = subsystem.add_spawnable_from_class(sequence, unreal.CineCameraActor)
    binding.set_display_name(CAMERA_PREFIX + track["semantic_id"])
    for old in binding.find_tracks_by_exact_type(unreal.MovieScene3DTransformTrack):
        binding.remove_track(old)
    live = _live_actor(sequence, binding, unreal.CineCameraActor)
    template = binding.get_object_template()
    if live is None or not isinstance(template, unreal.CineCameraActor):
        raise RuntimeError(f"Unable to resolve generated camera: {track['semantic_id']}")
    for actor in (template, live):
        component = actor.get_cine_camera_component()
        component.set_editor_property("filmback", unreal.CameraFilmbackSettings(sensor_width=track["sensor_width_mm"], sensor_height=track["sensor_height_mm"]))
    subsystem.save_default_spawnable_state(binding)
    transform_track = binding.add_track(unreal.MovieScene3DTransformTrack)
    transform_track.set_display_name(CAMERA_PREFIX + track["semantic_id"] + "|Transform")
    section = transform_track.add_section(); section.set_range(track["start_frame"], track["end_frame"])
    channels = _transform_channels(section)
    for frame in track["keyframes"]:
        rotation = _quat(frame["rotation"]).rotator()
        values = [frame["location_cm"]["x"], frame["location_cm"]["y"], frame["location_cm"]["z"], _component(rotation, "roll"), _component(rotation, "pitch"), _component(rotation, "yaw"), 1.0, 1.0, 1.0]
        for channel, value in zip(channels[:9], values):
            _key(channel, frame["timeline_frame"], value)
    component_binding = sequence.add_possessable(live.get_cine_camera_component())
    component_binding.set_parent(binding)
    component_binding.set_display_name(CAMERA_PREFIX + track["semantic_id"] + "|Component")
    focal_track = component_binding.add_track(unreal.MovieSceneFloatTrack)
    focal_track.set_display_name(CAMERA_PREFIX + track["semantic_id"] + "|FocalLength")
    focal_track.set_property_name_and_path("CurrentFocalLength", "CurrentFocalLength")
    focal_section = focal_track.add_section(); focal_section.set_range(track["start_frame"], track["end_frame"])
    focal_channels = focal_section.get_all_channels()
    if len(focal_channels) != 1:
        raise RuntimeError("Generated camera focal-length track does not expose one channel.")
    for frame in track["keyframes"]:
        _key(focal_channels[0], frame["timeline_frame"], frame["focal_length_mm"])
    return binding

def _create_sequence():
    sequence = unreal.AssetToolsHelpers.get_asset_tools().create_asset(TARGET["sequence_asset_name"], TARGET["sequence_package_path"], unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
    if not isinstance(sequence, unreal.LevelSequence):
        raise RuntimeError("Unable to create generated Level Sequence.")
    sequence.set_display_rate(unreal.FrameRate(MAPPING["fps"], 1)); sequence.set_playback_start(0); sequence.set_playback_end(MAPPING["duration_frames"])
    unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(sequence)
    subsystem = unreal.get_editor_subsystem(unreal.LevelSequenceEditorSubsystem)
    bindings = {actor["actor_binding_id"]: _actor_binding(sequence, subsystem, actor["actor_binding_id"]) for actor in TARGET["actors"]}
    for track in MAPPING["body_tracks"]: _add_animation(bindings[track["actor_binding_id"]], track, BODY_PREFIX)
    for track in MAPPING["facial_tracks"]: _add_animation(bindings[track["actor_binding_id"]], track, FACE_PREFIX)
    for track in MAPPING["audio_tracks"]: _add_audio(sequence, track)
    camera_bindings = {track["semantic_id"]: _add_camera(sequence, subsystem, track) for track in MAPPING["camera_tracks"]}
    cuts = sequence.add_track(unreal.MovieSceneCameraCutTrack)
    cuts.set_display_name("CSA|CAMERA-CUTS")
    for track in MAPPING["camera_tracks"]:
        section = cuts.add_section(); section.set_range(track["start_frame"], track["end_frame"])
        section.set_camera_binding_id(sequence.get_binding_id(camera_bindings[track["semantic_id"]]))
    unreal.EditorAssetLibrary.save_loaded_asset(sequence, False)
    return sequence

def _write_lifecycle():
    value = {"lifecycle_version": "0.1.0", "import_process_id": os.getpid(),
        "import_completed": True, "saved": True, "restarted": False, "readback_completed": False,
        "render_completed": False, "errors": []}
    (_saved_root() / "lifecycle.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def _record_failure(phase, error):
    path = _saved_root() / "lifecycle.json"
    if path.is_file():
        try: value = json.loads(path.read_text(encoding="utf-8"))
        except Exception: value = {}
    else: value = {}
    value.setdefault("lifecycle_version", "0.1.0")
    value.setdefault("import_process_id", os.getpid())
    value.setdefault("import_completed", False)
    value.setdefault("saved", False)
    value.setdefault("restarted", False)
    value.setdefault("readback_completed", False)
    value.setdefault("render_completed", False)
    value.setdefault("errors", []).append(f"{phase}: {type(error).__name__}: {error}")
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def import_native():
    _preflight()
    for track in MAPPING["body_tracks"]: _create_body(track)
    for track in MAPPING["facial_tracks"]: _create_face(track)
    _import_audio(); _create_sequence(); _write_lifecycle()
    unreal.log("CutSceneAI native Unreal import saved successfully.")

if __name__ == "__main__":
    try:
        import_native()
    except Exception as error:
        _record_failure("import", error)
        unreal.log_error(f"CutSceneAI native Unreal import failed: {error}")
        raise
    finally:
        unreal.SystemLibrary.quit_editor()
'''


_UNREAL_READBACK_TEMPLATE = r'''"""Generated CutSceneAI Unreal 5.8 native restart/readback exporter."""
import json
import os
from pathlib import Path
import unreal

PLAN = json.loads(__PLAN_JSON__)
MAPPING = json.loads(__MAPPING_JSON__)
TARGET = json.loads(__TARGET_JSON__)
SEMANTICS = json.loads(__SEMANTICS_JSON__)
BODY_PREFIX = "CSA|BODY|"; FACE_PREFIX = "CSA|FACIAL|"; CAMERA_PREFIX = "CSA|CAMERA|"; AUDIO_PREFIX = "CSA|AUDIO|"

def _saved_root():
    path = Path(unreal.Paths.project_saved_dir()) / "CutSceneAI" / "Native" / "Unreal"; path.mkdir(parents=True, exist_ok=True); return path
def _property(value, name):
    try: return value.get_editor_property(name)
    except Exception: return getattr(value, name)
def _display(value):
    try: return str(value.get_display_name())
    except Exception: return str(_property(value, "display_name"))
def _frame(value):
    if isinstance(value, int): return value
    try: return int(_property(value, "value"))
    except Exception: return int(value)
def _range(section): return _frame(section.get_start_frame()), _frame(section.get_end_frame())
def _asset(value):
    if value is None: return None
    try: return str(value.get_path_name())
    except Exception: return str(value)
def _sequence_path(): return f"{TARGET['sequence_package_path']}/{TARGET['sequence_asset_name']}"
def _section(semantic_id, actor_id, asset, section):
    start, end = _range(section)
    return {"semantic_id": semantic_id, "actor_binding_id": actor_id, "asset_ref": asset, "start_frame": start, "end_frame": end, "placeholder": asset is None}
def _record_failure(error):
    path = _saved_root() / "lifecycle.json"
    if path.is_file():
        try: value = json.loads(path.read_text(encoding="utf-8"))
        except Exception: value = {}
    else: value = {}
    value.setdefault("errors", []).append(f"readback: {type(error).__name__}: {error}")
    value["readback_process_id"] = os.getpid()
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def export_readback():
    lifecycle_path = _saved_root() / "lifecycle.json"
    if not lifecycle_path.is_file(): raise RuntimeError("Native import lifecycle receipt is missing.")
    lifecycle = json.loads(lifecycle_path.read_text(encoding="utf-8"))
    if not lifecycle["import_completed"] or not lifecycle["saved"] or lifecycle["restarted"] or lifecycle["import_process_id"] == os.getpid():
        raise RuntimeError("Native readback requires a fresh editor restart after import.")
    sequence = unreal.EditorAssetLibrary.load_asset(_sequence_path())
    if not isinstance(sequence, unreal.LevelSequence): raise RuntimeError("Saved native Level Sequence is missing after restart.")
    body = []; face = []; audio = []; cameras = []
    actor_by_name = {item["display_name"]: item["binding_id"] for item in PLAN["sequences"][0]["actors"]}
    for binding in sequence.get_bindings():
        actor_id = actor_by_name.get(_display(binding))
        for track in binding.find_tracks_by_exact_type(unreal.MovieSceneSkeletalAnimationTrack):
            name = _display(track)
            destination = body if name.startswith(BODY_PREFIX) else face if name.startswith(FACE_PREFIX) else None
            if destination is None: continue
            semantic_id = name.split("|", 2)[-1]
            for section in track.get_sections():
                animation = _property(_property(section, "params"), "animation")
                destination.append(_section(semantic_id, actor_id, _asset(animation), section))
    for track in sequence.find_tracks_by_exact_type(unreal.MovieSceneAudioTrack):
        name = _display(track)
        if not name.startswith(AUDIO_PREFIX): continue
        actor_id, semantic_id = name[len(AUDIO_PREFIX):].split("|", 1)
        for section in track.get_sections():
            try: sound = section.get_sound()
            except Exception: sound = _property(section, "sound")
            audio.append(_section(semantic_id, actor_id, _asset(sound), section))
    camera_ranges = {}
    for track in sequence.find_tracks_by_exact_type(unreal.MovieSceneCameraCutTrack):
        for section in track.get_sections():
            binding = sequence.resolve_binding_id(section.get_camera_binding_id())
            name = _display(binding)
            if name.startswith(CAMERA_PREFIX): camera_ranges[name[len(CAMERA_PREFIX):]] = section
    for mapped in MAPPING["camera_tracks"]:
        native = camera_ranges.get(mapped["semantic_id"])
        if native is not None: cameras.append(_section(mapped["semantic_id"], None, _sequence_path() + "#" + mapped["semantic_id"], native))
    counts = (len(body), len(face), len(cameras), len(audio))
    expected = (len(MAPPING["body_tracks"]), len(MAPPING["facial_tracks"]), len(MAPPING["camera_tracks"]), len(MAPPING["audio_tracks"]))
    if counts != expected: raise RuntimeError(f"Saved native modality counts diverged: {counts} != {expected}")
    readback = {"readback_version": "0.1.0", "engine": "unreal", "engine_version": str(unreal.SystemLibrary.get_engine_version()),
        "adapter_version": PLAN["adapter_version"], "timeline_asset": _sequence_path(), "semantics": SEMANTICS,
        "evidence": {"animation_sections": sorted(body, key=lambda item: item["semantic_id"]), "facial_sections": sorted(face, key=lambda item: item["semantic_id"]),
            "camera_sections": sorted(cameras, key=lambda item: item["semantic_id"]), "audio_sections": sorted(audio, key=lambda item: item["semantic_id"])}, "warnings": []}
    (_saved_root() / "readback.json").write_text(json.dumps(readback, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lifecycle["readback_process_id"] = os.getpid(); lifecycle["restarted"] = True; lifecycle["readback_completed"] = True
    lifecycle_path.write_text(json.dumps(lifecycle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    unreal.log("CutSceneAI native Unreal restart/readback completed successfully.")

if __name__ == "__main__":
    try:
        export_readback()
    except Exception as error:
        _record_failure(error)
        unreal.log_error(f"CutSceneAI native Unreal readback failed: {error}")
        raise
    finally:
        unreal.SystemLibrary.quit_editor()
'''


_UNREAL_RENDER_TEMPLATE = r'''"""Generated CutSceneAI Unreal 5.8 Movie Render Queue gate."""
from hashlib import sha256
import json
import os
from pathlib import Path
import unreal

MAPPING = json.loads(__MAPPING_JSON__)
TARGET = json.loads(__TARGET_JSON__)
STATE = {}

def _saved_root():
    path = Path(unreal.Paths.project_saved_dir()) / "CutSceneAI" / "Native" / "Unreal"; path.mkdir(parents=True, exist_ok=True); return path
def _output_root(): return Path(unreal.Paths.project_saved_dir()) / Path(TARGET["render"]["output_directory"])
def _sequence_path(): return f"{TARGET['sequence_package_path']}/{TARGET['sequence_asset_name']}"
def _asset_path(path):
    name = path.rsplit("/", 1)[-1]
    return path if "." in name else f"{path}.{name}"
def _record_failure(error):
    path = _saved_root() / "lifecycle.json"
    if path.is_file():
        try: lifecycle = json.loads(path.read_text(encoding="utf-8"))
        except Exception: lifecycle = {}
    else: lifecycle = {}
    lifecycle.setdefault("errors", []).append(f"render: {type(error).__name__}: {error}")
    lifecycle["render_process_id"] = os.getpid(); lifecycle["render_completed"] = False
    path.write_text(json.dumps(lifecycle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
def _finish(executor, success):
    try:
        output = _output_root()
        files = sorted(output.rglob("*.png"))
        frames = [{"frame": index, "relative_path": path.relative_to(output).as_posix(), "sha256": sha256(path.read_bytes()).hexdigest()} for index, path in enumerate(files)]
        manifest = {"manifest_version": "0.1.0", "engine": "unreal", "source_bundle_sha256": MAPPING["source_bundle_sha256"],
            "expected_frame_count": MAPPING["duration_frames"], "rendered_frame_count": len(frames), "frames": frames}
        (_saved_root() / "render-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        lifecycle_path = _saved_root() / "lifecycle.json"; lifecycle = json.loads(lifecycle_path.read_text(encoding="utf-8"))
        lifecycle["render_process_id"] = os.getpid()
        lifecycle["render_completed"] = bool(success) and len(frames) == MAPPING["duration_frames"]
        if not success: lifecycle.setdefault("errors", []).append("Movie Render Queue reported failure.")
        lifecycle_path.write_text(json.dumps(lifecycle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        unreal.log("CutSceneAI native Unreal render completed." if lifecycle["render_completed"] else "CutSceneAI native Unreal render failed.")
    except Exception as error:
        _record_failure(error)
        unreal.log_error(f"CutSceneAI native Unreal render callback failed: {error}")
    finally:
        unreal.SystemLibrary.quit_editor()

def render():
    lifecycle_path = _saved_root() / "lifecycle.json"
    lifecycle = json.loads(lifecycle_path.read_text(encoding="utf-8"))
    if not lifecycle["restarted"] or not lifecycle["readback_completed"]: raise RuntimeError("Render requires completed restart/readback evidence.")
    if lifecycle["import_process_id"] == os.getpid() or lifecycle["readback_process_id"] == os.getpid(): raise RuntimeError("Render requires a third editor process.")
    lifecycle["render_process_id"] = os.getpid(); lifecycle_path.write_text(json.dumps(lifecycle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output = _output_root()
    if output.exists() and any(output.iterdir()): raise RuntimeError(f"Refusing to replace existing render output: {output}")
    output.mkdir(parents=True, exist_ok=True)
    queue = unreal.MoviePipelineQueue(); job = queue.allocate_new_job(unreal.MoviePipelineExecutorJob)
    job.set_editor_property("job_name", "CutSceneAI Native " + MAPPING["source_scene_id"])
    job.set_editor_property("sequence", unreal.SoftObjectPath(path_string=_asset_path(_sequence_path())))
    job.set_editor_property("map", unreal.SoftObjectPath(path_string=_asset_path(TARGET["render"]["map_path"])))
    config = job.get_configuration()
    settings = config.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
    settings.set_editor_property("output_directory", unreal.DirectoryPath(path=str(output)))
    settings.set_editor_property("file_name_format", "frame_{frame_number}")
    settings.set_editor_property("output_resolution", unreal.IntPoint(x=TARGET["render"]["width"], y=TARGET["render"]["height"]))
    settings.set_editor_property("use_custom_playback_range", True); settings.set_editor_property("custom_start_frame", 0); settings.set_editor_property("custom_end_frame", MAPPING["duration_frames"])
    settings.set_editor_property("use_custom_frame_rate", True); settings.set_editor_property("output_frame_rate", unreal.FrameRate(MAPPING["fps"], 1))
    settings.set_editor_property("override_existing_output", False); settings.set_editor_property("flush_disk_writes_per_shot", True)
    config.find_or_add_setting_by_class(unreal.MoviePipelineDeferredPassBase)
    config.find_or_add_setting_by_class(unreal.MoviePipelineImageSequenceOutput_PNG)
    executor = unreal.MoviePipelinePIEExecutor(); executor.set_is_rendering_offscreen(True)
    executor.on_executor_finished_delegate.add_callable(_finish)
    subsystem = unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem)
    STATE.update(queue=queue, job=job, executor=executor, subsystem=subsystem)
    subsystem.render_queue_instance_with_executor_instance(queue, executor)

if __name__ == "__main__":
    try:
        render()
    except Exception as error:
        _record_failure(error)
        unreal.log_error(f"CutSceneAI native Unreal render setup failed: {error}")
        unreal.SystemLibrary.quit_editor()
        raise
'''


def render_unreal_native_import_script(
    package: UnrealNativePerformancePackage,
) -> str:
    return (
        _UNREAL_IMPORT_TEMPLATE.replace("__PLAN_JSON__", repr(_json(package.plan)))
        .replace("__MAPPING_JSON__", repr(_json(package.mapping)))
        .replace("__TARGET_JSON__", repr(_json(package.target)))
    )


def render_unreal_native_readback_script(
    package: UnrealNativePerformancePackage,
) -> str:
    return (
        _UNREAL_READBACK_TEMPLATE.replace("__PLAN_JSON__", repr(_json(package.plan)))
        .replace("__MAPPING_JSON__", repr(_json(package.mapping)))
        .replace("__TARGET_JSON__", repr(_json(package.target)))
        .replace("__SEMANTICS_JSON__", repr(_json(package.semantics)))
    )


def render_unreal_native_render_script(
    package: UnrealNativePerformancePackage,
) -> str:
    return _UNREAL_RENDER_TEMPLATE.replace(
        "__MAPPING_JSON__", repr(_json(package.mapping))
    ).replace("__TARGET_JSON__", repr(_json(package.target)))


_UNREAL_RUNNER_TEMPLATE = r"""[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$UnrealEditor,
    [Parameter(Mandatory = $true)][string]$UProject,
    [string]$Python = "python"
)
$ErrorActionPreference = "Stop"
$packageRoot = Split-Path -Parent $PSScriptRoot
$bundlePath = Join-Path $packageRoot "performance.bundle.zip"
$actualBundleHash = (Get-FileHash -Algorithm SHA256 $bundlePath).Hash.ToLowerInvariant()
if ($actualBundleHash -ne "__BUNDLE_SHA256__") { throw "Performance bundle checksum mismatch." }
$projectFile = (Resolve-Path $UProject).Path
$projectRoot = Split-Path -Parent $projectFile
$evidenceRoot = Join-Path $projectRoot "Saved\CutSceneAI\Native\Unreal"
New-Item -ItemType Directory -Force -Path $evidenceRoot | Out-Null

function Invoke-CutSceneAIUnreal([string]$Script, [string]$Log) {
    & $UnrealEditor $projectFile "-ExecutePythonScript=$Script" -unattended -nop4 -nosplash -stdout -FullStdOutLogOutput "-AbsLog=$Log"
    if ($LASTEXITCODE -ne 0) { throw "Unreal native phase failed with exit code $LASTEXITCODE. See $Log" }
}

$importLog = Join-Path $evidenceRoot "import.log"
$readbackLog = Join-Path $evidenceRoot "readback.log"
$renderLog = Join-Path $evidenceRoot "render.log"
Invoke-CutSceneAIUnreal (Join-Path $PSScriptRoot "cutsceneai-unreal-native-import.py") $importLog
Invoke-CutSceneAIUnreal (Join-Path $PSScriptRoot "cutsceneai-unreal-native-readback.py") $readbackLog
Invoke-CutSceneAIUnreal (Join-Path $PSScriptRoot "cutsceneai-unreal-native-render.py") $renderLog
$combinedLog = Join-Path $evidenceRoot "editor.log"
Get-Content -Raw -Path $importLog, $readbackLog, $renderLog | Set-Content -NoNewline -Encoding UTF8 $combinedLog
& $Python (Join-Path $PSScriptRoot "collect-native-evidence.py") --engine unreal --mapping (Join-Path $packageRoot "mapping.json") --lifecycle (Join-Path $evidenceRoot "lifecycle.json") --readback (Join-Path $evidenceRoot "readback.json") --render-manifest (Join-Path $evidenceRoot "render-manifest.json") --editor-log $combinedLog --output (Join-Path $evidenceRoot "engine-run.evidence.json")
if ($LASTEXITCODE -ne 0) { throw "Native evidence collection failed with exit code $LASTEXITCODE." }
Write-Host "CutSceneAI Unreal native gate completed: $evidenceRoot"
"""


def render_unreal_native_runner_script(
    package: UnrealNativePerformancePackage,
) -> str:
    return _UNREAL_RUNNER_TEMPLATE.replace(
        "__BUNDLE_SHA256__", _sha256(render_performance_bundle(package.bundle))
    )


def _write_entry(archive: ZipFile, path: str, data: bytes) -> None:
    entry = ZipInfo(path, date_time=_ZIP_TIMESTAMP)
    entry.compress_type = ZIP_DEFLATED
    entry.external_attr = 0o644 << 16
    archive.writestr(entry, data)


def render_unreal_native_performance_package(
    package: UnrealNativePerformancePackage,
    *,
    evidence_collector_script: str,
) -> bytes:
    """Render a deterministic portable Unreal native-realization harness archive."""

    output = BytesIO()
    with ZipFile(output, "w") as archive:
        scripts = {
            UNREAL_NATIVE_IMPORT_FILENAME: render_unreal_native_import_script(package),
            UNREAL_NATIVE_READBACK_FILENAME: render_unreal_native_readback_script(
                package
            ),
            UNREAL_NATIVE_RENDER_FILENAME: render_unreal_native_render_script(package),
            UNREAL_NATIVE_RUNNER_FILENAME: render_unreal_native_runner_script(package),
            "collect-native-evidence.py": evidence_collector_script,
        }
        for name, content in scripts.items():
            _write_entry(archive, f"Scripts/{name}", content.encode("utf-8"))
        _write_entry(
            archive,
            "mapping.json",
            render_unreal_performance_mapping(package.mapping).encode("utf-8"),
        )
        _write_entry(
            archive,
            "plan.json",
            render_unreal_plan(package.plan).encode("utf-8"),
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
            "semantics.json",
            (
                json.dumps(
                    package.semantics.model_dump(mode="json"), indent=2, sort_keys=True
                )
                + "\n"
            ).encode("utf-8"),
        )
        _write_entry(
            archive,
            "performance.bundle.zip",
            render_performance_bundle(package.bundle),
        )
        for track in package.bundle.package.audio_tracks:
            data = package.bundle.artifact_files[track.artifact.relative_path]
            if _sha256(data) != track.artifact.sha256:
                raise ValueError(
                    "Unreal native package WAV changed after bundle verification."
                )
            _write_entry(
                archive,
                (PurePosixPath("Audio") / track.artifact.relative_path).as_posix(),
                data,
            )
    return output.getvalue()
