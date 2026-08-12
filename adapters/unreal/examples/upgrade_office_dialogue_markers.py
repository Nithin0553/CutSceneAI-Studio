"""Generated CutSceneAI Unreal legacy-marker upgrade.

Run this file inside Unreal Editor only when the parity readback reports that an
existing generated Level Sequence has no timeline semantic marker. The script
validates the legacy sequence before adding canonical CutSceneAI markers. It does
not recreate bindings, tracks, sections, cameras, animation, or audio.
"""

import json

import unreal


PLAN = json.loads('{"adapter_version":"0.6.0","audio_imports":[],"cir_schema_version":"0.1.0","coordinate_system":{"distance_unit":"centimeter","forward_axis":"x","handedness":"left","position_mapping":"X=-Z*100; Y=X*100; Z=Y*100","up_axis":"z"},"preview_version":"0.1.0","project_id":"office-dialogue","project_name":"Office Dialogue","sequences":[{"actors":[{"actor_class_path":"/Script/Engine.StaticMeshActor","asset_path":null,"binding_id":"actor:mina","display_name":"ACT_Mina","kind":"character","mesh_type":"static_mesh","placeholder":true,"placeholder_visual":{"mesh_asset_path":"/Engine/BasicShapes/Cylinder.Cylinder","transform":{"location_cm":{"x":-100.0,"y":-150.0,"z":90.0},"rotation":{"w":1.0,"x":0.0,"y":0.0,"z":0.0},"scale":{"x":0.45,"y":0.45,"z":1.8}}},"source_entity_id":"mina","transform":{"location_cm":{"x":-100.0,"y":-150.0,"z":0.0},"rotation":{"w":1.0,"x":0.0,"y":0.0,"z":0.0},"scale":{"x":1.0,"y":1.0,"z":1.0}}},{"actor_class_path":"/Script/Engine.StaticMeshActor","asset_path":null,"binding_id":"actor:arjun","display_name":"ACT_Arjun","kind":"character","mesh_type":"static_mesh","placeholder":true,"placeholder_visual":{"mesh_asset_path":"/Engine/BasicShapes/Cylinder.Cylinder","transform":{"location_cm":{"x":-50.0,"y":100.0,"z":90.0},"rotation":{"w":1.0,"x":0.0,"y":0.0,"z":0.0},"scale":{"x":0.45,"y":0.45,"z":1.8}}},"source_entity_id":"arjun","transform":{"location_cm":{"x":-50.0,"y":100.0,"z":0.0},"rotation":{"w":1.0,"x":0.0,"y":0.0,"z":0.0},"scale":{"x":1.0,"y":1.0,"z":1.0}}},{"actor_class_path":"/Script/Engine.StaticMeshActor","asset_path":null,"binding_id":"actor:contract","display_name":"ACT_Contract","kind":"environment","mesh_type":"static_mesh","placeholder":true,"placeholder_visual":{"mesh_asset_path":"/Engine/BasicShapes/Cube.Cube","transform":{"location_cm":{"x":0.0,"y":0.0,"z":80.5},"rotation":{"w":1.0,"x":0.0,"y":0.0,"z":0.0},"scale":{"x":0.3,"y":0.21,"z":0.01}}},"source_entity_id":"contract","transform":{"location_cm":{"x":0.0,"y":0.0,"z":80.0},"rotation":{"w":1.0,"x":0.0,"y":0.0,"z":0.0},"scale":{"x":1.0,"y":1.0,"z":1.0}}},{"actor_class_path":"/Script/Engine.StaticMeshActor","asset_path":null,"binding_id":"actor:conference-table","display_name":"ACT_ConferenceTable","kind":"environment","mesh_type":"static_mesh","placeholder":true,"placeholder_visual":{"mesh_asset_path":"/Engine/BasicShapes/Cube.Cube","transform":{"location_cm":{"x":0.0,"y":0.0,"z":37.5},"rotation":{"w":1.0,"x":0.0,"y":0.0,"z":0.0},"scale":{"x":2.4,"y":1.2,"z":0.75}}},"source_entity_id":"conference-table","transform":{"location_cm":{"x":0.0,"y":0.0,"z":0.0},"rotation":{"w":1.0,"x":0.0,"y":0.0,"z":0.0},"scale":{"x":1.0,"y":1.0,"z":1.0}}}],"animation_sections":[],"asset_name":"LS_SceneMeeting","audio_sections":[],"cameras":[{"angle":"eye_level","binding_id":"camera:shot-establishing","composition":"Slow push-in while preserving room geography.","description":"Wide view revealing the office, Mina, Arjun, and the table.","display_name":"CAM_ShotEstablishing","end_frame":96,"framing":"wide","inferred_transform":true,"lens_mm":28.0,"look_at_location_cm":{"x":-75.0,"y":-25.0,"z":160.0},"movement":"dolly","purpose":"establishing","source_beat_ids":["beat-arrival"],"source_shot_id":"shot-establishing","start_frame":0,"subject_binding_ids":["actor:mina","actor:arjun","actor:conference-table"],"target_binding_ids":["actor:mina","actor:arjun"],"transform":{"location_cm":{"x":-675.0,"y":-25.0,"z":160.0},"rotation":{"w":1.0,"x":0.0,"y":0.0,"z":0.0},"scale":{"x":1.0,"y":1.0,"z":1.0}}},{"angle":"high","binding_id":"camera:shot-contract-detail","composition":"Keep the empty signature line in the upper-right intersection.","description":"Insert shot revealing the unsigned signature line.","display_name":"CAM_ShotContractDetail","end_frame":144,"framing":"insert","inferred_transform":true,"lens_mm":70.0,"look_at_location_cm":{"x":0.0,"y":0.0,"z":80.0},"movement":"static","purpose":"environment_detail","source_beat_ids":["beat-confrontation"],"source_shot_id":"shot-contract-detail","start_frame":96,"subject_binding_ids":["actor:contract"],"target_binding_ids":["actor:contract"],"transform":{"location_cm":{"x":-120.0,"y":0.0,"z":240.0},"rotation":{"w":0.8944271909999159,"x":0.0,"y":0.4472135954999579,"z":0.0},"scale":{"x":1.0,"y":1.0,"z":1.0}}},{"angle":"eye_level","binding_id":"camera:shot-dialogue","composition":"Prioritize Mina while retaining Arjun in the foreground.","description":"Over-the-shoulder coverage of the confrontation.","display_name":"CAM_ShotDialogue","end_frame":336,"framing":"over_the_shoulder","inferred_transform":true,"lens_mm":50.0,"look_at_location_cm":{"x":-100.0,"y":-150.0,"z":160.0},"movement":"static","purpose":"dialogue","source_beat_ids":["beat-confrontation"],"source_shot_id":"shot-dialogue","start_frame":144,"subject_binding_ids":["actor:mina","actor:arjun"],"target_binding_ids":["actor:mina","actor:arjun"],"transform":{"location_cm":{"x":0.9901951359278485,"y":201.9803902718557,"z":160.0},"rotation":{"w":0.6017506144815422,"x":0.0,"y":0.0,"z":-0.7986840413900145},"scale":{"x":1.0,"y":1.0,"z":1.0}}},{"angle":"eye_level","binding_id":"camera:shot-reaction","composition":"Hold steady and preserve negative space toward Mina.","description":"Close-up of Arjun absorbing Mina\'s response.","display_name":"CAM_ShotReaction","end_frame":432,"framing":"close_up","inferred_transform":true,"lens_mm":85.0,"look_at_location_cm":{"x":-50.0,"y":100.0,"z":160.0},"movement":"static","purpose":"reaction","source_beat_ids":["beat-reaction"],"source_shot_id":"shot-reaction","start_frame":336,"subject_binding_ids":["actor:arjun"],"target_binding_ids":["actor:arjun"],"transform":{"location_cm":{"x":-230.0,"y":100.0,"z":160.0},"rotation":{"w":1.0,"x":0.0,"y":0.0,"z":0.0},"scale":{"x":1.0,"y":1.0,"z":1.0}}}],"duration_frames":432,"location":"Corporate conference room","package_path":"/Game/CutSceneAI/Sequences","performance_cues":[{"actor_binding_id":"actor:mina","dialogue":null,"dialogue_audio_uri":null,"dialogue_language":null,"dialogue_start_frame":null,"emotion":"frustrated","emotion_intensity":0.65,"end_frame":96,"facial_asset_uri":null,"lip_sync":false,"look_at_binding_id":"actor:contract","motion_asset_uri":null,"motion_prompt":"Walk briskly into the room, stop at the table, and look down at the contract.","motion_style":"restrained tension","source_beat_id":"beat-arrival","start_frame":0},{"actor_binding_id":"actor:mina","dialogue":"You said this would be signed yesterday.","dialogue_audio_uri":null,"dialogue_language":"en","dialogue_start_frame":120,"emotion":"angry","emotion_intensity":0.75,"end_frame":336,"facial_asset_uri":null,"lip_sync":true,"look_at_binding_id":"actor:arjun","motion_asset_uri":null,"motion_prompt":"Point toward the contract, then fold both arms while maintaining eye contact.","motion_style":"authoritative","source_beat_id":"beat-confrontation","start_frame":96},{"actor_binding_id":"actor:arjun","dialogue":"Legal changed the final clause. I was waiting for approval.","dialogue_audio_uri":null,"dialogue_language":"en","dialogue_start_frame":216,"emotion":"worried","emotion_intensity":0.7,"end_frame":336,"facial_asset_uri":null,"lip_sync":true,"look_at_binding_id":"actor:mina","motion_asset_uri":null,"motion_prompt":"Shift weight backward, glance at the contract, and raise one hand defensively.","motion_style":"uneasy","source_beat_id":"beat-confrontation","start_frame":96},{"actor_binding_id":"actor:arjun","dialogue":null,"dialogue_audio_uri":null,"dialogue_language":null,"dialogue_start_frame":null,"emotion":"anxious","emotion_intensity":0.8,"end_frame":432,"facial_asset_uri":null,"lip_sync":false,"look_at_binding_id":"actor:mina","motion_asset_uri":null,"motion_prompt":"Lower the raised hand slowly and become still.","motion_style":"defeated","source_beat_id":"beat-reaction","start_frame":336}],"set_pieces":[{"binding_id":"set:floor","display_name":"SET_Floor","mesh_asset_path":"/Engine/BasicShapes/Cube.Cube","transform":{"location_cm":{"x":-100.0,"y":0.0,"z":-3.0},"rotation":{"w":1.0,"x":0.0,"y":0.0,"z":0.0},"scale":{"x":14.0,"y":9.0,"z":0.1}}},{"binding_id":"set:back-wall","display_name":"SET_BackWall","mesh_asset_path":"/Engine/BasicShapes/Cube.Cube","transform":{"location_cm":{"x":600.0,"y":0.0,"z":150.0},"rotation":{"w":1.0,"x":0.0,"y":0.0,"z":0.0},"scale":{"x":0.1,"y":9.0,"z":3.0}}},{"binding_id":"set:left-wall","display_name":"SET_LeftWall","mesh_asset_path":"/Engine/BasicShapes/Cube.Cube","transform":{"location_cm":{"x":-100.0,"y":-450.0,"z":150.0},"rotation":{"w":1.0,"x":0.0,"y":0.0,"z":0.0},"scale":{"x":14.0,"y":0.1,"z":3.0}}},{"binding_id":"set:right-wall","display_name":"SET_RightWall","mesh_asset_path":"/Engine/BasicShapes/Cube.Cube","transform":{"location_cm":{"x":-100.0,"y":450.0,"z":150.0},"rotation":{"w":1.0,"x":0.0,"y":0.0,"z":0.0},"scale":{"x":14.0,"y":0.1,"z":3.0}}}],"source_scene_id":"scene-meeting","title":"The Meeting"}],"source_settings":{"distance_unit":"meter","forward_axis":"-z","fps":24,"handedness":"right","time_unit":"second","up_axis":"y"},"target_engine":"Unreal Engine","target_engine_version":"5.8.0","warnings":[{"code":"placeholder_character","message":"Character \'mina\' imports as a visible cylinder proxy; set Character.asset_uri to an Unreal /Game Skeletal Mesh path to bind a production asset.","source_id":"mina"},{"code":"placeholder_character","message":"Character \'arjun\' imports as a visible cylinder proxy; set Character.asset_uri to an Unreal /Game Skeletal Mesh path to bind a production asset.","source_id":"arjun"},{"code":"placeholder_environment","message":"Environment object \'contract\' imports as a StaticMeshActor placeholder.","source_id":"contract"},{"code":"placeholder_environment","message":"Environment object \'conference-table\' imports as a StaticMeshActor placeholder.","source_id":"conference-table"},{"code":"performance_metadata_only","message":"4 of 4 performance cues have no compatible Unreal animation section; their motion intent plus facial and look-at data remain editable Sequencer markers.","source_id":"scene-meeting"},{"code":"dialogue_metadata_only","message":"2 of 2 dialogue cues have no compatible Unreal audio section; their text, language, and timing remain editable Sequencer markers.","source_id":"scene-meeting"},{"code":"inferred_camera_transform","message":"Camera \'shot-establishing\' had no CIR transform; the adapter generated a deterministic blocking pose.","source_id":"shot-establishing"},{"code":"camera_movement_metadata_only","message":"Camera movement \'dolly\' is retained as metadata; v0.6 imports a blocking pose for manual keyframing.","source_id":"shot-establishing"},{"code":"inferred_camera_transform","message":"Camera \'shot-contract-detail\' had no CIR transform; the adapter generated a deterministic blocking pose.","source_id":"shot-contract-detail"},{"code":"inferred_camera_transform","message":"Camera \'shot-dialogue\' had no CIR transform; the adapter generated a deterministic blocking pose.","source_id":"shot-dialogue"},{"code":"inferred_camera_transform","message":"Camera \'shot-reaction\' had no CIR transform; the adapter generated a deterministic blocking pose.","source_id":"shot-reaction"}]}')
EXPECTED = json.loads('{"cir_fingerprint_sha256":"39ff99659eb9ef2ccd9dc7422ef50a0305fb81d992858e4ee8e5838abe0f9dfc","cir_schema_version":"0.1.0","fps":24,"project_id":"office-dialogue","scenes":[{"camera_cuts":[{"angle":"eye_level","cut_id":"camera:scene-meeting:shot-establishing","end_frame":96,"framing":"wide","lens_mm":28.0,"movement":"dolly","purpose":"establishing","source_beat_ids":["beat-arrival"],"source_shot_id":"shot-establishing","start_frame":0,"subject_binding_ids":["actor:mina","actor:arjun","actor:conference-table"],"target_binding_ids":["actor:mina","actor:arjun"]},{"angle":"high","cut_id":"camera:scene-meeting:shot-contract-detail","end_frame":144,"framing":"insert","lens_mm":70.0,"movement":"static","purpose":"environment_detail","source_beat_ids":["beat-confrontation"],"source_shot_id":"shot-contract-detail","start_frame":96,"subject_binding_ids":["actor:contract"],"target_binding_ids":["actor:contract"]},{"angle":"eye_level","cut_id":"camera:scene-meeting:shot-dialogue","end_frame":336,"framing":"over_the_shoulder","lens_mm":50.0,"movement":"static","purpose":"dialogue","source_beat_ids":["beat-confrontation"],"source_shot_id":"shot-dialogue","start_frame":144,"subject_binding_ids":["actor:mina","actor:arjun"],"target_binding_ids":["actor:mina","actor:arjun"]},{"angle":"eye_level","cut_id":"camera:scene-meeting:shot-reaction","end_frame":432,"framing":"close_up","lens_mm":85.0,"movement":"static","purpose":"reaction","source_beat_ids":["beat-reaction"],"source_shot_id":"shot-reaction","start_frame":336,"subject_binding_ids":["actor:arjun"],"target_binding_ids":["actor:arjun"]}],"dialogue_cues":[{"actor_binding_id":"actor:mina","cue_id":"dialogue:scene-meeting:beat-confrontation:mina:01","language":"en","source_beat_id":"beat-confrontation","start_frame":120,"text_sha256":"9bde07b9889fa5b5582c62f215e4dd782a17b554af4ec8aadb781dafe4b0b8c1","window_end_frame":336},{"actor_binding_id":"actor:arjun","cue_id":"dialogue:scene-meeting:beat-confrontation:arjun:02","language":"en","source_beat_id":"beat-confrontation","start_frame":216,"text_sha256":"e53cb4393bd3cd379af29a4d7dcd42d0cdd94e36c8a29c0ffb58832b83f274c8","window_end_frame":336}],"duration_frames":432,"entities":[{"binding_id":"actor:mina","kind":"character","source_entity_id":"mina"},{"binding_id":"actor:arjun","kind":"character","source_entity_id":"arjun"},{"binding_id":"actor:contract","kind":"environment","source_entity_id":"contract"},{"binding_id":"actor:conference-table","kind":"environment","source_entity_id":"conference-table"}],"performance_cues":[{"actor_binding_id":"actor:mina","cue_id":"performance:scene-meeting:beat-arrival:mina:01","end_frame":96,"look_at_binding_id":"actor:contract","motion_intent_sha256":"0403232601b547be46335e7d2d125aedf7878c0ef2f5855c211eb6733dde4692","source_beat_id":"beat-arrival","start_frame":0},{"actor_binding_id":"actor:mina","cue_id":"performance:scene-meeting:beat-confrontation:mina:01","end_frame":336,"look_at_binding_id":"actor:arjun","motion_intent_sha256":"840a97877138cf8d4110d2a33da33fbfc09add2b2ec1c396c539c7d3321d124d","source_beat_id":"beat-confrontation","start_frame":96},{"actor_binding_id":"actor:arjun","cue_id":"performance:scene-meeting:beat-confrontation:arjun:02","end_frame":336,"look_at_binding_id":"actor:mina","motion_intent_sha256":"55d092b9487d9290f06eed9a6a03c15b14611b25925abfb79ca11b72b6d4636e","source_beat_id":"beat-confrontation","start_frame":96},{"actor_binding_id":"actor:arjun","cue_id":"performance:scene-meeting:beat-reaction:arjun:01","end_frame":432,"look_at_binding_id":"actor:mina","motion_intent_sha256":"0c407d3726147f465bf9d65e2a05db1c742da16d7874a589a232fb2784a7fff8","source_beat_id":"beat-reaction","start_frame":336}],"source_scene_id":"scene-meeting"}],"semantics_version":"0.1.0"}')


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
