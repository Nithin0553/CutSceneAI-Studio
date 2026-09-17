from __future__ import annotations

import hashlib
import json
from typing import Any

from cutsceneai_parity import (
    EngineName,
    EngineRunEvidence,
    EngineTimelineReadback,
    ModalityRealizationEvidence,
    PerformanceModality,
)

from .retargeting import PARENT_COMPONENT_BIND_RETARGETING_METHOD


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(data: bytes, description: str) -> dict[str, Any]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{description} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise TypeError(f"{description} must contain one JSON object")
    return value


def _required_bool(value: dict[str, Any], name: str) -> bool:
    result = value.get(name)
    if not isinstance(result, bool):
        raise TypeError(f"lifecycle {name} must be a boolean")
    return result


def _validate_process_lifecycle(lifecycle: dict[str, Any], engine: EngineName) -> None:
    process_fields = ["import_process_id", "readback_process_id"]
    if engine is EngineName.UNREAL:
        process_fields.append("render_process_id")
    process_ids = [lifecycle.get(name) for name in process_fields]
    if any(
        not isinstance(value, int) or isinstance(value, bool) for value in process_ids
    ):
        raise TypeError("lifecycle process IDs must be integers")
    if len(process_ids) != len(set(process_ids)):
        raise ValueError(
            "native lifecycle phases must run in separate editor processes"
        )


def _validate_retarget_profile(
    *,
    engine: EngineName,
    engine_version: str,
    mapping: dict[str, Any],
    mapping_sha256: str,
    lifecycle: dict[str, Any],
    profile: dict[str, Any],
) -> None:
    expected_engine = "Unreal Engine" if engine is EngineName.UNREAL else "Unity"
    if (
        lifecycle.get("retargeting_method") != PARENT_COMPONENT_BIND_RETARGETING_METHOD
        or lifecycle.get("retarget_profile") != "retarget-profile.json"
    ):
        raise ValueError("lifecycle does not identify the required retarget profile")
    if (
        profile.get("profile_version") != "0.1.0"
        or profile.get("retargeting_method") != PARENT_COMPONENT_BIND_RETARGETING_METHOD
        or profile.get("canonical_reference_frame") != "axis-aligned-parent-frame-v1"
        or profile.get("engine") != expected_engine
        or profile.get("engine_version") != engine_version
        or profile.get("source_mapping_sha256") != mapping_sha256
    ):
        raise ValueError("retarget profile identity does not match the native run")

    tracks = mapping.get("body_tracks")
    actors = profile.get("actors")
    if not isinstance(tracks, list) or not isinstance(actors, list):
        raise TypeError(
            "retarget profile actors and mapping body_tracks must be arrays"
        )
    if len(actors) != len(tracks):
        raise ValueError("retarget profile does not cover every mapped body track")
    for track, actor in zip(tracks, actors, strict=True):
        if not isinstance(track, dict) or not isinstance(actor, dict):
            raise TypeError("retarget profile actors and body tracks must be objects")
        bindings = track.get("joint_bindings")
        joints = actor.get("joints")
        if (
            actor.get("actor_binding_id") != track.get("actor_binding_id")
            or not isinstance(bindings, list)
            or not isinstance(joints, list)
            or len(joints) != len(bindings)
        ):
            raise ValueError(
                "retarget profile joint coverage does not match the mapping"
            )
        for binding, joint in zip(bindings, joints, strict=True):
            if not isinstance(binding, dict) or not isinstance(joint, dict):
                raise TypeError("retarget profile joints and bindings must be objects")
            target_name = binding.get("target_bone_name") or binding.get(
                "target_human_bone"
            )
            profile_target_name = joint.get("target_bone_name") or joint.get(
                "target_human_bone"
            )
            if (
                joint.get("source_joint_name") != binding.get("source_joint_name")
                or profile_target_name != target_name
                or joint.get("parent_index") != binding.get("parent_index")
                or not isinstance(joint.get("reference_local"), dict)
                or not isinstance(joint.get("reference_component"), dict)
                or not isinstance(joint.get("target_parent_component_rotation"), dict)
            ):
                raise ValueError(
                    "retarget profile joint context does not match the mapping"
                )


def collect_native_engine_run_evidence(
    *,
    engine: EngineName,
    mapping_data: bytes,
    lifecycle_data: bytes,
    readback_data: bytes,
    render_manifest_data: bytes,
    retarget_profile_data: bytes,
    editor_log_data: bytes,
) -> EngineRunEvidence:
    """Collect strict, hash-anchored experiment evidence from one native engine run."""

    mapping = _json(mapping_data, "mapping")
    lifecycle = _json(lifecycle_data, "lifecycle")
    render_manifest = _json(render_manifest_data, "render manifest")
    retarget_profile = _json(retarget_profile_data, "retarget profile")
    readback_payload = _json(readback_data, "readback")
    readback = EngineTimelineReadback.model_validate(readback_payload)
    if readback.engine is not engine:
        raise ValueError("readback engine does not match the requested engine")
    if render_manifest.get("engine") != engine.value:
        raise ValueError("render manifest engine does not match the requested engine")
    source_bundle_sha256 = mapping.get("source_bundle_sha256")
    if (
        not isinstance(source_bundle_sha256, str)
        or render_manifest.get("source_bundle_sha256") != source_bundle_sha256
    ):
        raise ValueError("mapping and render manifest bundle SHA-256 values diverged")
    semantics = readback.semantics
    scenes = [
        scene
        for scene in semantics.scenes
        if scene.source_scene_id == mapping.get("source_scene_id")
    ]
    if (
        semantics.project_id != mapping.get("project_id")
        or semantics.cir_fingerprint_sha256 != mapping.get("cir_fingerprint_sha256")
        or semantics.fps != mapping.get("fps")
        or len(scenes) != 1
        or scenes[0].duration_frames != mapping.get("duration_frames")
    ):
        raise ValueError("readback semantics do not match the native mapping")
    _validate_process_lifecycle(lifecycle, engine)
    mapping_sha256 = _sha256(mapping_data)

    modality_fields = (
        (
            PerformanceModality.BODY,
            "body_tracks",
            "animation_sections",
        ),
        (
            PerformanceModality.FACIAL,
            "facial_tracks",
            "facial_sections",
        ),
        (
            PerformanceModality.CAMERA,
            "camera_tracks",
            "camera_sections",
        ),
        (
            PerformanceModality.AUDIO,
            "audio_tracks",
            "audio_sections",
        ),
    )
    modalities = []
    evidence = readback.evidence.model_dump(mode="json")
    for modality, mapping_field, evidence_field in modality_fields:
        mapped_tracks = mapping.get(mapping_field)
        if not isinstance(mapped_tracks, list):
            raise TypeError(f"mapping {mapping_field} must be an array")
        sections = evidence[evidence_field]
        hashes = sorted(
            {
                str(track["source_artifact"]["sha256"])
                for track in mapped_tracks
                if isinstance(track, dict)
                and isinstance(track.get("source_artifact"), dict)
            }
        )
        if len(hashes) != len(mapped_tracks):
            raise ValueError(
                f"mapping {mapping_field} has missing or duplicate artifacts"
            )
        target_refs = sorted(
            {
                str(section["asset_ref"])
                for section in sections
                if section.get("asset_ref")
            }
        )
        modalities.append(
            ModalityRealizationEvidence(
                modality=modality,
                expected_section_count=len(mapped_tracks),
                realized_section_count=len(sections),
                placeholder_section_count=sum(
                    bool(section["placeholder"]) for section in sections
                ),
                source_artifact_sha256s=hashes,
                target_asset_refs=target_refs,
            )
        )

    _validate_retarget_profile(
        engine=engine,
        engine_version=readback.engine_version,
        mapping=mapping,
        mapping_sha256=mapping_sha256,
        lifecycle=lifecycle,
        profile=retarget_profile,
    )

    frames = render_manifest.get("frames")
    rendered_frame_count = render_manifest.get("rendered_frame_count")
    expected_frame_count = render_manifest.get("expected_frame_count")
    if (
        not isinstance(frames, list)
        or not isinstance(rendered_frame_count, int)
        or not isinstance(expected_frame_count, int)
        or rendered_frame_count != len(frames)
        or expected_frame_count != mapping.get("duration_frames")
    ):
        raise ValueError("render manifest frame accounting is invalid")
    errors = lifecycle.get("errors", [])
    if not isinstance(errors, list) or not all(
        isinstance(item, str) for item in errors
    ):
        raise ValueError("lifecycle errors must be an array of strings")
    timeline_payload = {
        "semantics": readback_payload["semantics"],
        "evidence": readback_payload["evidence"],
    }
    timeline_data = json.dumps(
        timeline_payload, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return EngineRunEvidence(
        engine=engine,
        engine_version=readback.engine_version,
        source_bundle_sha256=source_bundle_sha256,
        mapping_sha256=mapping_sha256,
        editor_log_sha256=_sha256(editor_log_data),
        readback_sha256=_sha256(readback_data),
        timeline_fingerprint_sha256=_sha256(timeline_data),
        render_manifest_sha256=_sha256(render_manifest_data),
        retarget_profile_sha256=_sha256(retarget_profile_data),
        rendered_frame_count=rendered_frame_count,
        import_completed=_required_bool(lifecycle, "import_completed"),
        saved=_required_bool(lifecycle, "saved"),
        restarted=_required_bool(lifecycle, "restarted"),
        readback_completed=_required_bool(lifecycle, "readback_completed"),
        render_completed=(
            _required_bool(lifecycle, "render_completed")
            and rendered_frame_count == expected_frame_count
        ),
        modalities=modalities,
        errors=errors,
        missing_realization_warnings=list(readback.warnings),
    )


_COLLECTOR_SCRIPT = r"""#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path

MODALITIES = (
    ("body", "body_tracks", "animation_sections"),
    ("facial", "facial_tracks", "facial_sections"),
    ("camera", "camera_tracks", "camera_sections"),
    ("audio", "audio_tracks", "audio_sections"),
)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def load(path):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(str(path) + " must contain one JSON object")
    return value

def required_bool(value, name):
    result = value.get(name)
    if type(result) is not bool:
        raise SystemExit("Lifecycle " + name + " must be a boolean")
    return result

def main():
    parser = argparse.ArgumentParser(description="Collect CutSceneAI native engine evidence.")
    parser.add_argument("--engine", choices=("unreal", "unity"), required=True)
    parser.add_argument("--mapping", required=True)
    parser.add_argument("--lifecycle", required=True)
    parser.add_argument("--readback", required=True)
    parser.add_argument("--render-manifest", required=True)
    parser.add_argument("--retarget-profile", required=True)
    parser.add_argument("--editor-log", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    mapping_data = Path(args.mapping).read_bytes(); mapping = json.loads(mapping_data)
    lifecycle = load(args.lifecycle)
    readback_data = Path(args.readback).read_bytes(); readback = json.loads(readback_data)
    render_data = Path(args.render_manifest).read_bytes(); render = json.loads(render_data)
    profile_data = Path(args.retarget_profile).read_bytes(); profile = json.loads(profile_data)
    log_data = Path(args.editor_log).read_bytes()
    if readback["engine"] != args.engine or render["engine"] != args.engine:
        raise SystemExit("Engine identity mismatch in native evidence.")
    if render["source_bundle_sha256"] != mapping["source_bundle_sha256"]:
        raise SystemExit("Bundle SHA-256 mismatch in native evidence.")
    scenes = [item for item in readback["semantics"]["scenes"] if item["source_scene_id"] == mapping["source_scene_id"]]
    if (readback["semantics"]["project_id"] != mapping["project_id"]
            or readback["semantics"]["cir_fingerprint_sha256"] != mapping["cir_fingerprint_sha256"]
            or readback["semantics"]["fps"] != mapping["fps"]
            or len(scenes) != 1 or scenes[0]["duration_frames"] != mapping["duration_frames"]):
        raise SystemExit("Readback semantics do not match the native mapping.")
    process_fields = ["import_process_id", "readback_process_id"]
    if args.engine == "unreal": process_fields.append("render_process_id")
    process_ids = [lifecycle.get(name) for name in process_fields]
    if any(type(value) is not int for value in process_ids) or len(process_ids) != len(set(process_ids)):
        raise SystemExit("Native lifecycle phases must use distinct integer process IDs.")
    expected_profile_engine = "Unreal Engine" if args.engine == "unreal" else "Unity"
    mapping_sha256 = digest(mapping_data)
    if (lifecycle.get("retargeting_method") != "parent-component-bind-conjugation-v1"
            or lifecycle.get("retarget_profile") != "retarget-profile.json"
            or profile.get("profile_version") != "0.1.0"
            or profile.get("retargeting_method") != "parent-component-bind-conjugation-v1"
            or profile.get("canonical_reference_frame") != "axis-aligned-parent-frame-v1"
            or profile.get("engine") != expected_profile_engine
            or profile.get("engine_version") != readback["engine_version"]
            or profile.get("source_mapping_sha256") != mapping_sha256):
        raise SystemExit("Retarget profile identity does not match the native run.")
    tracks = mapping.get("body_tracks"); actors = profile.get("actors")
    if not isinstance(tracks, list) or not isinstance(actors, list) or len(actors) != len(tracks):
        raise SystemExit("Retarget profile does not cover every mapped body track.")
    for track, actor in zip(tracks, actors):
        bindings = track.get("joint_bindings"); joints = actor.get("joints")
        if (actor.get("actor_binding_id") != track.get("actor_binding_id")
                or not isinstance(bindings, list) or not isinstance(joints, list)
                or len(joints) != len(bindings)):
            raise SystemExit("Retarget profile joint coverage does not match the mapping.")
        for binding, joint in zip(bindings, joints):
            target_name = binding.get("target_bone_name") or binding.get("target_human_bone")
            profile_target = joint.get("target_bone_name") or joint.get("target_human_bone")
            if (joint.get("source_joint_name") != binding.get("source_joint_name")
                    or profile_target != target_name
                    or joint.get("parent_index") != binding.get("parent_index")
                    or not isinstance(joint.get("reference_local"), dict)
                    or not isinstance(joint.get("reference_component"), dict)
                    or not isinstance(joint.get("target_parent_component_rotation"), dict)):
                raise SystemExit("Retarget profile joint context does not match the mapping.")
    modalities = []
    for modality, mapping_field, evidence_field in MODALITIES:
        tracks = mapping[mapping_field]; sections = readback["evidence"][evidence_field]
        hashes = sorted({item["source_artifact"]["sha256"] for item in tracks})
        refs = sorted({item["asset_ref"] for item in sections if item.get("asset_ref")})
        if len(hashes) != len(tracks):
            raise SystemExit("Missing or duplicate source artifact hashes for " + modality)
        modalities.append({
            "modality": modality,
            "expected_section_count": len(tracks),
            "realized_section_count": len(sections),
            "placeholder_section_count": sum(bool(item.get("placeholder")) for item in sections),
            "source_artifact_sha256s": hashes,
            "target_asset_refs": refs,
        })
    timeline = json.dumps({"semantics": readback["semantics"], "evidence": readback["evidence"]}, separators=(",", ":"), sort_keys=True).encode("utf-8")
    rendered = render["rendered_frame_count"]; expected = render["expected_frame_count"]
    if (type(rendered) is not int or type(expected) is not int or not isinstance(render.get("frames"), list)
            or rendered != len(render["frames"]) or expected != mapping["duration_frames"]):
        raise SystemExit("Render manifest frame accounting is invalid.")
    errors = lifecycle.get("errors", [])
    if not isinstance(errors, list) or not all(isinstance(item, str) for item in errors):
        raise SystemExit("Lifecycle errors must be an array of strings.")
    result = {
        "engine": args.engine,
        "engine_version": readback["engine_version"],
        "source_bundle_sha256": mapping["source_bundle_sha256"],
        "mapping_sha256": mapping_sha256,
        "editor_log_sha256": digest(log_data),
        "readback_sha256": digest(readback_data),
        "timeline_fingerprint_sha256": digest(timeline),
        "render_manifest_sha256": digest(render_data),
        "retarget_profile_sha256": digest(profile_data),
        "rendered_frame_count": rendered,
        "import_completed": required_bool(lifecycle, "import_completed"),
        "saved": required_bool(lifecycle, "saved"),
        "restarted": required_bool(lifecycle, "restarted"),
        "readback_completed": required_bool(lifecycle, "readback_completed"),
        "render_completed": required_bool(lifecycle, "render_completed") and rendered == expected,
        "modalities": modalities,
        "errors": errors,
        "missing_realization_warnings": list(readback.get("warnings", [])),
    }
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
"""


def render_native_evidence_collector_script() -> str:
    return _COLLECTOR_SCRIPT
