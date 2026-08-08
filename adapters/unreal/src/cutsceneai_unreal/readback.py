from __future__ import annotations

import json

from cutsceneai_parity import TimelineSemantics

from .models import UnrealExportPlan


_READBACK_TEMPLATE = '''"""Generated CutSceneAI Unreal semantic readback exporter.

Run this file inside Unreal Editor after importing and saving the generated Level Sequences.
It reopens the saved assets, inspects native tracks and CutSceneAI markers, then writes one
engine-neutral readback JSON file for the cross-engine parity verifier.
"""

import json
from pathlib import Path

import unreal


PLAN = json.loads(__PLAN_JSON__)
EXPECTED = json.loads(__SEMANTICS_JSON__)


def _property(value, name):
    try:
        return value.get_editor_property(name)
    except Exception:
        return getattr(value, name)


def _frame_number(value):
    if isinstance(value, int):
        return value
    try:
        return int(_property(value, "value"))
    except Exception:
        return int(value)


def _section_range(section):
    return (
        _frame_number(section.get_start_frame()),
        _frame_number(section.get_end_frame()),
    )


def _display_name(value):
    try:
        return str(value.get_display_name())
    except Exception:
        return str(_property(value, "display_name"))


def _binding_key(value):
    try:
        return str(value.get_guid())
    except Exception:
        return str(value)


def _asset_ref(value):
    if value is None:
        return None
    try:
        return str(value.get_path_name())
    except Exception:
        return str(value)


def _display_rate_fps(sequence):
    rate = sequence.get_display_rate()
    numerator = int(_property(rate, "numerator"))
    denominator = int(_property(rate, "denominator"))
    if denominator <= 0 or numerator % denominator:
        raise RuntimeError(
            f"Level Sequence display rate must be a whole-number FPS, got "
            f"{numerator}/{denominator}."
        )
    return numerator // denominator


def _metadata(sequence, warnings):
    result = {}
    for marker in sequence.get_marked_frames_from_sequence(
        unreal.MovieSceneTimeUnit.DISPLAY_RATE
    ):
        label = str(_property(marker, "label"))
        if not label.startswith("CSA|"):
            continue
        try:
            payload = json.loads(str(_property(marker, "comment")))
            value = payload["cutsceneai"]
            kind = value["semantic_kind"]
            if not isinstance(value, dict) or not isinstance(kind, str):
                raise TypeError("semantic marker payload has invalid types")
            item = dict(value)
            item["marker_frame"] = _frame_number(_property(marker, "frame_number"))
            result.setdefault(kind, []).append(item)
        except Exception as exc:
            warnings.append(f"Malformed CutSceneAI marker '{label}': {exc}")
    return result


def _only(values, description):
    if len(values) != 1:
        raise RuntimeError(f"Expected one {description}, found {len(values)}.")
    return values[0]


def _load_sequence(scene):
    asset_path = f"{scene['package_path']}/{scene['asset_name']}"
    sequence = unreal.EditorAssetLibrary.load_asset(asset_path)
    if not isinstance(sequence, unreal.LevelSequence):
        raise RuntimeError(f"Saved Level Sequence could not be loaded: {asset_path}")
    return asset_path, sequence


def _bindings(sequence):
    by_display_name = {}
    by_binding_key = {}
    for binding in sequence.get_bindings():
        display_name = _display_name(binding)
        by_display_name[display_name] = binding
        by_binding_key[_binding_key(sequence.get_binding_id(binding))] = display_name
    return by_display_name, by_binding_key


def _semantic_entity(value):
    return {
        "binding_id": value["binding_id"],
        "source_entity_id": value["source_entity_id"],
        "kind": value["kind"],
    }


def _semantic_performance(value):
    return {
        "cue_id": value["cue_id"],
        "source_beat_id": value["source_beat_id"],
        "actor_binding_id": value["actor_binding_id"],
        "start_frame": value["marker_frame"],
        "end_frame": value["end_frame"],
        "motion_intent_sha256": value["motion_intent_sha256"],
        "look_at_binding_id": value.get("look_at_binding_id"),
    }


def _semantic_dialogue(value):
    return {
        "cue_id": value["cue_id"],
        "source_beat_id": value["source_beat_id"],
        "actor_binding_id": value["actor_binding_id"],
        "start_frame": value["marker_frame"],
        "window_end_frame": value["window_end_frame"],
        "text_sha256": value["text_sha256"],
        "language": value["language"],
    }


def _semantic_camera(value, start_frame, end_frame, *, cut_id=None):
    return {
        "cut_id": cut_id or value["cut_id"],
        "source_shot_id": value["source_shot_id"],
        "source_beat_ids": value["source_beat_ids"],
        "start_frame": start_frame,
        "end_frame": end_frame,
        "purpose": value["purpose"],
        "framing": value["framing"],
        "angle": value["angle"],
        "movement": value["movement"],
        "lens_mm": value["lens_mm"],
        "subject_binding_ids": value["subject_binding_ids"],
        "target_binding_ids": value["target_binding_ids"],
    }


def _camera_ranges(sequence, binding_name_by_key):
    result = []
    tracks = sequence.find_tracks_by_exact_type(
        unreal.MovieSceneCameraCutTrack
    )
    for track in tracks:
        for section in track.get_sections():
            binding_id = section.get_camera_binding_id()
            display_name = binding_name_by_key.get(_binding_key(binding_id))
            start_frame, end_frame = _section_range(section)
            result.append((display_name, start_frame, end_frame))
    return sorted(result, key=lambda item: (item[1], item[2], str(item[0])))


def _camera_lens_mm(binding):
    if binding is None:
        return None
    template = binding.get_object_template()
    if not isinstance(template, unreal.CineCameraActor):
        return None
    component = template.get_cine_camera_component()
    if component is None:
        return None
    return float(_property(component, "current_focal_length"))


def _skeletal_sections(binding):
    result = []
    for track in binding.find_tracks_by_exact_type(
        unreal.MovieSceneSkeletalAnimationTrack
    ):
        result.extend(track.get_sections())
    return sorted(result, key=lambda item: _section_range(item))


def _animation_evidence(scene, semantic_scene, bindings):
    evidence = []
    actor_by_binding = {item["binding_id"]: item for item in scene["actors"]}
    cues_by_actor = {}
    for cue in semantic_scene["performance_cues"]:
        cues_by_actor.setdefault(cue["actor_binding_id"], []).append(cue)

    handled_display_names = set()
    for actor_binding_id, actor in actor_by_binding.items():
        binding = bindings.get(actor["display_name"])
        if binding is None:
            continue
        handled_display_names.add(actor["display_name"])
        native = _skeletal_sections(binding)
        cues = sorted(
            cues_by_actor.get(actor_binding_id, []),
            key=lambda item: (item["start_frame"], item["cue_id"]),
        )
        for index, section in enumerate(native):
            start_frame, end_frame = _section_range(section)
            if index < len(cues):
                semantic_id = cues[index]["cue_id"]
            else:
                semantic_id = (
                    f"unmapped-animation:{scene['source_scene_id']}:"
                    f"{actor_binding_id}:{index + 1}"
                )
            params = _property(section, "params")
            animation = _property(params, "animation")
            evidence.append(
                {
                    "semantic_id": semantic_id,
                    "actor_binding_id": actor_binding_id,
                    "asset_ref": _asset_ref(animation),
                    "start_frame": start_frame,
                    "end_frame": end_frame,
                }
            )

    for display_name, binding in bindings.items():
        if display_name in handled_display_names:
            continue
        for index, section in enumerate(_skeletal_sections(binding), start=1):
            start_frame, end_frame = _section_range(section)
            params = _property(section, "params")
            animation = _property(params, "animation")
            evidence.append(
                {
                    "semantic_id": (
                        f"unmapped-animation:{scene['source_scene_id']}:"
                        f"binding:{display_name}:{index}"
                    ),
                    "actor_binding_id": None,
                    "asset_ref": _asset_ref(animation),
                    "start_frame": start_frame,
                    "end_frame": end_frame,
                }
            )
    return evidence


def _audio_evidence(sequence, scene, semantic_scene):
    evidence = []
    actor_by_binding = {item["binding_id"]: item for item in scene["actors"]}
    cues_by_track = {}
    for cue in semantic_scene["dialogue_cues"]:
        actor = actor_by_binding[cue["actor_binding_id"]]
        track_name = f"CutSceneAI Dialogue - {actor['display_name']}"
        cues_by_track.setdefault(track_name, []).append(cue)

    actual_tracks = sequence.find_tracks_by_exact_type(unreal.MovieSceneAudioTrack)
    for track in actual_tracks:
        track_name = _display_name(track)
        cues = sorted(
            cues_by_track.get(track_name, []),
            key=lambda item: (item["start_frame"], item["cue_id"]),
        )
        native = sorted(track.get_sections(), key=lambda item: _section_range(item))
        for index, section in enumerate(native):
            start_frame, end_frame = _section_range(section)
            if index < len(cues):
                cue = cues[index]
                semantic_id = cue["cue_id"]
                actor_binding_id = cue["actor_binding_id"]
            else:
                semantic_id = (
                    f"unmapped-audio:{scene['source_scene_id']}:{index + 1}"
                )
                actor_binding_id = None
            try:
                sound = section.get_sound()
            except Exception:
                sound = _property(section, "sound")
            evidence.append(
                {
                    "semantic_id": semantic_id,
                    "actor_binding_id": actor_binding_id,
                    "asset_ref": _asset_ref(sound),
                    "start_frame": start_frame,
                    "end_frame": end_frame,
                }
            )
    return evidence


def _read_scene(scene, expected_scene, warnings):
    asset_path, sequence = _load_sequence(scene)
    metadata = _metadata(sequence, warnings)
    timeline = _only(metadata.get("timeline", []), "timeline semantic marker")
    bindings, binding_name_by_key = _bindings(sequence)

    entities = [
        _semantic_entity(item)
        for item in metadata.get("entity", [])
        if item.get("display_name") in bindings
    ]
    performances = [
        _semantic_performance(item) for item in metadata.get("performance", [])
    ]
    dialogues = [
        _semantic_dialogue(item) for item in metadata.get("dialogue", [])
    ]

    camera_metadata = {
        item.get("display_name"): item for item in metadata.get("camera", [])
    }
    cameras = []
    for index, (display_name, start_frame, end_frame) in enumerate(
        _camera_ranges(sequence, binding_name_by_key), start=1
    ):
        value = camera_metadata.get(display_name)
        if value is not None:
            value = dict(value)
            lens_mm = _camera_lens_mm(bindings.get(display_name))
            if lens_mm is not None:
                value["lens_mm"] = lens_mm
            cameras.append(_semantic_camera(value, start_frame, end_frame))
        elif expected_scene["camera_cuts"]:
            warnings.append(
                f"Unmapped native camera cut in {asset_path} at frame {start_frame}."
            )
            cameras.append(
                _semantic_camera(
                    expected_scene["camera_cuts"][0],
                    start_frame,
                    end_frame,
                    cut_id=f"unmapped-camera:{scene['source_scene_id']}:{index}",
                )
            )

    playback_start = int(sequence.get_playback_start())
    playback_end = int(sequence.get_playback_end())
    actual_scene = {
        "source_scene_id": timeline["source_scene_id"],
        "duration_frames": playback_end - playback_start,
        "entities": sorted(entities, key=lambda item: item["binding_id"]),
        "performance_cues": sorted(
            performances, key=lambda item: (item["start_frame"], item["cue_id"])
        ),
        "dialogue_cues": sorted(
            dialogues, key=lambda item: (item["start_frame"], item["cue_id"])
        ),
        "camera_cuts": sorted(
            cameras, key=lambda item: (item["start_frame"], item["cut_id"])
        ),
    }
    identity = {
        "semantics_version": timeline["semantics_version"],
        "cir_schema_version": timeline["cir_schema_version"],
        "cir_fingerprint_sha256": timeline["cir_fingerprint_sha256"],
        "project_id": timeline["project_id"],
        "fps": _display_rate_fps(sequence),
    }
    return (
        asset_path,
        identity,
        actual_scene,
        _animation_evidence(scene, expected_scene, bindings),
        _audio_evidence(sequence, scene, expected_scene),
    )


def export_readback():
    warnings = [
        f"{item['code']}: {item['message']}" for item in PLAN["warnings"]
    ]
    expected_by_scene = {
        item["source_scene_id"]: item for item in EXPECTED["scenes"]
    }
    identities = []
    scenes = []
    animations = []
    audio = []
    asset_paths = []

    for scene in PLAN["sequences"]:
        expected_scene = expected_by_scene[scene["source_scene_id"]]
        asset_path, identity, actual_scene, scene_animations, scene_audio = _read_scene(
            scene, expected_scene, warnings
        )
        asset_paths.append(asset_path)
        identities.append(identity)
        scenes.append(actual_scene)
        animations.extend(scene_animations)
        audio.extend(scene_audio)

    identity = _only(identities[:1], "timeline identity")
    for other in identities[1:]:
        if other != identity:
            raise RuntimeError(
                "Saved Unreal sequences do not share one semantic identity and display rate."
            )

    readback = {
        "readback_version": "0.1.0",
        "engine": "unreal",
        "engine_version": str(unreal.SystemLibrary.get_engine_version()),
        "adapter_version": PLAN["adapter_version"],
        "timeline_asset": ";".join(asset_paths),
        "semantics": {
            **identity,
            "scenes": sorted(scenes, key=lambda item: item["source_scene_id"]),
        },
        "evidence": {
            "animation_sections": sorted(
                animations, key=lambda item: item["semantic_id"]
            ),
            "audio_sections": sorted(audio, key=lambda item: item["semantic_id"]),
        },
        "warnings": warnings,
    }

    output_directory = Path(unreal.Paths.project_saved_dir()) / "CutSceneAI" / "Readbacks"
    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = output_directory / f"{PLAN['project_id']}.unreal.readback.json"
    output_path.write_text(
        json.dumps(readback, indent=2, sort_keys=True) + "\\n", encoding="utf-8"
    )
    unreal.log(f"CutSceneAI Unreal readback: {output_path}")
    return output_path


if __name__ == "__main__":
    export_readback()
'''


def render_unreal_readback_script(
    plan: UnrealExportPlan, semantics: TimelineSemantics
) -> str:
    """Render a standalone exporter that reads saved Unreal timeline assets."""

    if plan.project_id != semantics.project_id:
        raise ValueError(
            "Unreal plan and timeline semantics use different project IDs."
        )
    if plan.source_settings.fps != semantics.fps:
        raise ValueError(
            "Unreal plan and timeline semantics use different frame rates."
        )
    plan_scene_ids = {item.source_scene_id for item in plan.sequences}
    semantic_scene_ids = {item.source_scene_id for item in semantics.scenes}
    if plan_scene_ids != semantic_scene_ids:
        raise ValueError("Unreal plan and timeline semantics contain different scenes.")

    plan_json = json.dumps(
        plan.model_dump(mode="json"), separators=(",", ":"), sort_keys=True
    )
    semantics_json = json.dumps(
        semantics.model_dump(mode="json"), separators=(",", ":"), sort_keys=True
    )
    return _READBACK_TEMPLATE.replace("__PLAN_JSON__", repr(plan_json)).replace(
        "__SEMANTICS_JSON__", repr(semantics_json)
    )
