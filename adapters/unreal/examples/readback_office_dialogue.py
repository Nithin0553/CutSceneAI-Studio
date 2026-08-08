"""Generated CutSceneAI Unreal semantic readback exporter.

Run this file inside Unreal Editor after importing and saving the generated Level Sequences.
It reopens the saved assets, inspects native tracks and CutSceneAI markers, then writes one
engine-neutral readback JSON file for the cross-engine parity verifier.
"""

import json
from pathlib import Path

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
        json.dumps(readback, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    unreal.log(f"CutSceneAI Unreal readback: {output_path}")
    return output_path


if __name__ == "__main__":
    export_readback()
