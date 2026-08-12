from __future__ import annotations

import json

from cutsceneai_parity import TimelineSemantics

from .models import UnrealExportPlan

_UPGRADE_TEMPLATE = '''"""Generated CutSceneAI Unreal legacy-marker upgrade.

Run this file inside Unreal Editor only when the parity readback reports that an
existing generated Level Sequence has no timeline semantic marker. The script
validates the legacy sequence before adding canonical CutSceneAI markers. It does
not recreate bindings, tracks, sections, cameras, animation, or audio.
"""

import json

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


def _section_range(section):
    return (
        _frame_number(section.get_start_frame()),
        _frame_number(section.get_end_frame()),
    )


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


def _markers(sequence):
    return list(
        sequence.get_marked_frames_from_sequence(
            unreal.MovieSceneTimeUnit.DISPLAY_RATE
        )
    )


def _marker_label(marker):
    return str(_property(marker, "label"))


def _marker_comment(marker):
    return str(_property(marker, "comment"))


def _marker_frame(marker):
    return _frame_number(_property(marker, "frame_number"))


def _semantic_comment(kind, value, authoring=None):
    metadata = dict(value)
    metadata["semantic_kind"] = kind
    payload = {"cutsceneai": metadata}
    if authoring is not None:
        payload["authoring"] = authoring
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def _marker_specs(scene, semantics):
    timeline = {
        "semantics_version": EXPECTED["semantics_version"],
        "cir_schema_version": EXPECTED["cir_schema_version"],
        "cir_fingerprint_sha256": EXPECTED["cir_fingerprint_sha256"],
        "project_id": EXPECTED["project_id"],
        "fps": EXPECTED["fps"],
        "source_scene_id": semantics["source_scene_id"],
        "duration_frames": semantics["duration_frames"],
    }
    result = [
        (
            0,
            f"CSA|TIMELINE|{semantics['source_scene_id']}",
            _semantic_comment("timeline", timeline),
        )
    ]

    actor_name_by_binding = {
        actor["binding_id"]: actor["display_name"] for actor in scene["actors"]
    }
    for entity in semantics["entities"]:
        value = dict(entity)
        value["display_name"] = actor_name_by_binding.get(entity["binding_id"])
        result.append(
            (
                0,
                f"CSA|ENTITY|{entity['binding_id']}",
                _semantic_comment("entity", value),
            )
        )

    performance_cues = semantics["performance_cues"]
    if len(performance_cues) != len(scene["performance_cues"]):
        raise RuntimeError("CIR semantics and Unreal performance plan diverged.")
    for cue, authoring in zip(performance_cues, scene["performance_cues"]):
        result.append(
            (
                cue["start_frame"],
                f"CSA|PERFORMANCE|{cue['cue_id']}",
                _semantic_comment("performance", cue, authoring),
            )
        )

    dialogue_authoring = [
        cue for cue in scene["performance_cues"] if cue["dialogue"] is not None
    ]
    if len(semantics["dialogue_cues"]) != len(dialogue_authoring):
        raise RuntimeError("CIR semantics and Unreal dialogue plan diverged.")
    for cue, authoring in zip(semantics["dialogue_cues"], dialogue_authoring):
        result.append(
            (
                cue["start_frame"],
                f"CSA|DIALOGUE|{cue['cue_id']}",
                _semantic_comment("dialogue", cue, authoring),
            )
        )

    if len(semantics["camera_cuts"]) != len(scene["cameras"]):
        raise RuntimeError("CIR semantics and Unreal camera plan diverged.")
    for cut, authoring in zip(semantics["camera_cuts"], scene["cameras"]):
        value = dict(cut)
        value["display_name"] = authoring["display_name"]
        result.append(
            (
                cut["start_frame"],
                f"CSA|CAMERA|{cut['cut_id']}",
                _semantic_comment("camera", value, authoring),
            )
        )
    return result


def _add_marker(sequence, frame, label, comment):
    marker = unreal.MovieSceneMarkedFrame(
        frame_number=unreal.FrameNumber(int(frame)), label=label
    )
    marker.set_editor_property("comment", comment)
    sequence.add_marked_frame_to_sequence(
        marker, unreal.MovieSceneTimeUnit.DISPLAY_RATE
    )


def _canonical_snapshot(sequence):
    result = {}
    for marker in _markers(sequence):
        label = _marker_label(marker)
        if not label.startswith("CSA|"):
            continue
        if label in result:
            raise RuntimeError(f"Duplicate canonical marker: {label}")
        try:
            payload = json.loads(_marker_comment(marker))
        except Exception as exc:
            raise RuntimeError(f"Malformed canonical marker: {label}") from exc
        result[label] = (_marker_frame(marker), payload)
    return result


def _assert_canonical_markers(sequence, specs):
    expected = {
        label: (int(frame), json.loads(comment)) for frame, label, comment in specs
    }
    actual = _canonical_snapshot(sequence)
    if actual != expected:
        missing = sorted(set(expected) - set(actual))
        unexpected = sorted(set(actual) - set(expected))
        changed = sorted(
            label
            for label in set(expected) & set(actual)
            if expected[label] != actual[label]
        )
        details = []
        if missing:
            details.append(f"missing={missing}")
        if unexpected:
            details.append(f"unexpected={unexpected}")
        if changed:
            details.append(f"changed={changed}")
        raise RuntimeError(
            "Canonical CutSceneAI markers do not match the compiled CIR: "
            + "; ".join(details)
        )


def _legacy_performance_comment(cue):
    return {
        "motion_prompt": cue["motion_prompt"],
        "motion_style": cue["motion_style"],
        "emotion": cue["emotion"],
        "emotion_intensity": cue["emotion_intensity"],
        "lip_sync": cue["lip_sync"],
        "look_at_binding_id": cue["look_at_binding_id"],
    }


def _require_legacy_marker(markers, label, frame, expected_comment, *, json_comment):
    matches = [marker for marker in markers if _marker_label(marker) == label]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one legacy marker '{label}', found {len(matches)}.")
    marker = matches[0]
    actual_frame = _marker_frame(marker)
    if actual_frame != int(frame):
        raise RuntimeError(
            f"Legacy marker '{label}' is at frame {actual_frame}; expected {frame}."
        )
    actual_comment = _marker_comment(marker)
    if json_comment:
        try:
            actual_comment = json.loads(actual_comment)
        except Exception as exc:
            raise RuntimeError(
                f"Legacy marker '{label}' has malformed JSON metadata."
            ) from exc
    if actual_comment != expected_comment:
        raise RuntimeError(f"Legacy marker '{label}' metadata does not match the CIR.")


def _binding_maps(sequence):
    by_display_name = {}
    display_name_by_key = {}
    for binding in sequence.get_bindings():
        display_name = _display_name(binding)
        by_display_name[display_name] = binding
        display_name_by_key[_binding_key(sequence.get_binding_id(binding))] = (
            display_name
        )
    return by_display_name, display_name_by_key


def _resolved_binding_display_name(sequence, binding_id, display_name_by_key):
    try:
        binding = sequence.resolve_binding_id(binding_id)
        try:
            is_valid = binding.is_valid()
        except Exception:
            is_valid = True
        if is_valid:
            return _display_name(binding)
    except Exception:
        pass
    return display_name_by_key.get(_binding_key(binding_id))


def _camera_ranges(sequence, display_name_by_key):
    result = []
    for track in sequence.find_tracks_by_exact_type(unreal.MovieSceneCameraCutTrack):
        for section in track.get_sections():
            binding_id = section.get_camera_binding_id()
            display_name = _resolved_binding_display_name(
                sequence, binding_id, display_name_by_key
            )
            start_frame, end_frame = _section_range(section)
            result.append((display_name, start_frame, end_frame))
    return sorted(result, key=lambda item: (item[1], item[2], str(item[0])))


def _validate_legacy_sequence(sequence, scene, semantics):
    fps = _display_rate_fps(sequence)
    if fps != EXPECTED["fps"]:
        raise RuntimeError(
            f"Legacy Level Sequence uses {fps} fps; expected {EXPECTED['fps']} fps."
        )
    playback_start = int(sequence.get_playback_start())
    playback_end = int(sequence.get_playback_end())
    if playback_start != 0 or playback_end != semantics["duration_frames"]:
        raise RuntimeError(
            "Legacy Level Sequence playback range does not match the CIR: "
            f"[{playback_start}, {playback_end}) versus "
            f"[0, {semantics['duration_frames']})."
        )

    by_display_name, display_name_by_key = _binding_maps(sequence)
    expected_bindings = {
        actor["display_name"] for actor in scene["actors"]
    } | {camera["display_name"] for camera in scene["cameras"]}
    missing_bindings = sorted(expected_bindings - set(by_display_name))
    if missing_bindings:
        raise RuntimeError(
            f"Legacy Level Sequence is missing expected bindings: {missing_bindings}"
        )

    actual_cameras = _camera_ranges(sequence, display_name_by_key)
    expected_cameras = sorted(
        (
            camera["display_name"],
            cut["start_frame"],
            cut["end_frame"],
        )
        for cut, camera in zip(semantics["camera_cuts"], scene["cameras"])
    )
    expected_cameras.sort(key=lambda item: (item[1], item[2], str(item[0])))
    if actual_cameras != expected_cameras:
        raise RuntimeError(
            "Legacy Level Sequence camera cuts do not match the compiled CIR: "
            f"actual={actual_cameras}, expected={expected_cameras}"
        )

    markers = _markers(sequence)
    for index, cue in enumerate(scene["performance_cues"], start=1):
        actor_id = cue["actor_binding_id"].split(":", 1)[-1]
        _require_legacy_marker(
            markers,
            f"PERF {index:02d} {actor_id} {cue['source_beat_id']}",
            cue["start_frame"],
            _legacy_performance_comment(cue),
            json_comment=True,
        )
        if cue["dialogue"] is not None and cue["dialogue_start_frame"] is not None:
            _require_legacy_marker(
                markers,
                f"DIALOGUE {index:02d} {actor_id}",
                cue["dialogue_start_frame"],
                cue["dialogue"],
                json_comment=False,
            )


def _load_scene(scene):
    asset_path = f"{scene['package_path']}/{scene['asset_name']}"
    sequence = unreal.EditorAssetLibrary.load_asset(asset_path)
    if not isinstance(sequence, unreal.LevelSequence):
        raise RuntimeError(f"Saved Level Sequence could not be loaded: {asset_path}")
    return asset_path, sequence


def upgrade_semantic_markers():
    expected_by_scene = {
        item["source_scene_id"]: item for item in EXPECTED["scenes"]
    }
    upgraded = []
    already_current = []

    for scene in PLAN["sequences"]:
        semantics = expected_by_scene[scene["source_scene_id"]]
        asset_path, sequence = _load_scene(scene)
        specs = _marker_specs(scene, semantics)
        canonical = _canonical_snapshot(sequence)
        if canonical:
            _assert_canonical_markers(sequence, specs)
            already_current.append(asset_path)
            continue

        _validate_legacy_sequence(sequence, scene, semantics)
        for frame, label, comment in specs:
            _add_marker(sequence, frame, label, comment)
        _assert_canonical_markers(sequence, specs)
        if not unreal.EditorAssetLibrary.save_loaded_asset(sequence, False):
            raise RuntimeError(f"Failed to save upgraded Level Sequence: {asset_path}")
        upgraded.append((asset_path, len(specs)))

    for asset_path, marker_count in upgraded:
        unreal.log(
            f"CutSceneAI Unreal semantic marker upgrade: {asset_path} "
            f"({marker_count} canonical markers added; native tracks unchanged)"
        )
    for asset_path in already_current:
        unreal.log(
            f"CutSceneAI Unreal semantic markers already current: {asset_path}"
        )
    return upgraded


upgrade_semantic_markers()
'''


def render_unreal_marker_upgrade_script(
    plan: UnrealExportPlan, semantics: TimelineSemantics
) -> str:
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
    return _UPGRADE_TEMPLATE.replace("__PLAN_JSON__", repr(plan_json)).replace(
        "__SEMANTICS_JSON__", repr(semantics_json)
    )
