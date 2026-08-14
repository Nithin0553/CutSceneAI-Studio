from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest
from cutsceneai_parity import EngineName, PerformanceModality
from cutsceneai_performance import (
    collect_native_engine_run_evidence,
    render_native_evidence_collector_script,
)

from cutsceneai_test_support.generated_performance import (
    make_generated_performance_fixture,
)


def _data(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _payloads(engine: EngineName) -> dict[str, Any]:
    mapping = {
        "source_bundle_sha256": "e" * 64,
        "project_id": "fixture-project",
        "cir_fingerprint_sha256": "c" * 64,
        "source_scene_id": "fixture-scene",
        "fps": 24,
        "duration_frames": 4,
        "body_tracks": [{"source_artifact": {"sha256": "a" * 64}}],
        "facial_tracks": [{"source_artifact": {"sha256": "b" * 64}}],
        "camera_tracks": [{"source_artifact": {"sha256": "c" * 64}}],
        "audio_tracks": [{"source_artifact": {"sha256": "d" * 64}}],
    }
    readback = {
        "readback_version": "0.1.0",
        "engine": engine.value,
        "engine_version": "5.8.0" if engine is EngineName.UNREAL else "6000.0.42f1",
        "adapter_version": "0.1.0",
        "timeline_asset": "native-timeline",
        "semantics": make_generated_performance_fixture().semantics.model_dump(
            mode="json"
        ),
        "evidence": {
            "animation_sections": [
                {
                    "semantic_id": "body:fixture:mina",
                    "actor_binding_id": "actor:mina",
                    "asset_ref": "native-body",
                    "start_frame": 0,
                    "end_frame": 4,
                    "placeholder": False,
                }
            ],
            "facial_sections": [
                {
                    "semantic_id": "face:fixture:mina",
                    "actor_binding_id": "actor:mina",
                    "asset_ref": "native-face",
                    "start_frame": 0,
                    "end_frame": 4,
                    "placeholder": False,
                }
            ],
            "camera_sections": [
                {
                    "semantic_id": "camera-motion:fixture:shot",
                    "asset_ref": "native-camera",
                    "start_frame": 0,
                    "end_frame": 4,
                    "placeholder": False,
                }
            ],
            "audio_sections": [
                {
                    "semantic_id": "dialogue:fixture:mina",
                    "actor_binding_id": "actor:mina",
                    "asset_ref": "native-audio",
                    "start_frame": 1,
                    "end_frame": 3,
                    "placeholder": False,
                }
            ],
        },
        "warnings": [],
    }
    lifecycle = {
        "import_process_id": 101,
        "readback_process_id": 202,
        "import_completed": True,
        "saved": True,
        "restarted": True,
        "readback_completed": True,
        "render_completed": True,
        "errors": [],
    }
    if engine is EngineName.UNREAL:
        lifecycle["render_process_id"] = 303
    render = {
        "engine": engine.value,
        "source_bundle_sha256": mapping["source_bundle_sha256"],
        "expected_frame_count": 4,
        "rendered_frame_count": 4,
        "frames": [
            {
                "frame": frame,
                "relative_path": f"{frame:06}.png",
                "sha256": f"{frame + 1:x}" * 64,
            }
            for frame in range(4)
        ],
    }
    return {
        "mapping": mapping,
        "readback": readback,
        "lifecycle": lifecycle,
        "render": render,
        "log": b"native editor log\n",
    }


def _collect(payloads: dict[str, Any], engine: EngineName):
    return collect_native_engine_run_evidence(
        engine=engine,
        mapping_data=_data(payloads["mapping"]),
        lifecycle_data=_data(payloads["lifecycle"]),
        readback_data=_data(payloads["readback"]),
        render_manifest_data=_data(payloads["render"]),
        editor_log_data=payloads["log"],
    )


@pytest.mark.parametrize("engine", list(EngineName))
def test_collects_strict_hash_anchored_native_evidence(engine: EngineName) -> None:
    payloads = _payloads(engine)
    result = _collect(payloads, engine)

    assert result.engine is engine
    assert result.source_bundle_sha256 == "e" * 64
    assert (
        result.mapping_sha256 == hashlib.sha256(_data(payloads["mapping"])).hexdigest()
    )
    assert result.editor_log_sha256 == hashlib.sha256(payloads["log"]).hexdigest()
    assert result.rendered_frame_count == 4
    assert result.render_completed
    assert [item.modality for item in result.modalities] == list(PerformanceModality)
    assert result.modalities[0].source_artifact_sha256s == ["a" * 64]
    assert result.modalities[0].target_asset_refs == ["native-body"]


def test_incomplete_render_is_preserved_as_failed_evidence() -> None:
    payloads = _payloads(EngineName.UNITY)
    payloads["render"]["rendered_frame_count"] = 3
    payloads["render"]["frames"].pop()

    result = _collect(payloads, EngineName.UNITY)

    assert result.rendered_frame_count == 3
    assert not result.render_completed


@pytest.mark.parametrize(
    ("field", "value", "exception", "message"),
    [
        ("mapping", [], TypeError, "one JSON object"),
        ("lifecycle", [], TypeError, "one JSON object"),
        ("readback", [], TypeError, "one JSON object"),
        ("render", [], TypeError, "one JSON object"),
    ],
)
def test_rejects_non_object_json_documents(
    field: str,
    value: object,
    exception: type[Exception],
    message: str,
) -> None:
    payloads = _payloads(EngineName.UNITY)
    payloads[field] = value

    with pytest.raises(exception, match=message):
        _collect(payloads, EngineName.UNITY)


def test_rejects_malformed_json() -> None:
    payloads = _payloads(EngineName.UNITY)
    with pytest.raises(ValueError, match="not valid UTF-8 JSON"):
        collect_native_engine_run_evidence(
            engine=EngineName.UNITY,
            mapping_data=b"{",
            lifecycle_data=_data(payloads["lifecycle"]),
            readback_data=_data(payloads["readback"]),
            render_manifest_data=_data(payloads["render"]),
            editor_log_data=payloads["log"],
        )


@pytest.mark.parametrize(
    ("mutation", "exception", "message"),
    [
        ("readback_engine", ValueError, "readback engine"),
        ("render_engine", ValueError, "render manifest engine"),
        ("bundle", ValueError, "bundle SHA-256"),
        ("semantics", ValueError, "semantics do not match"),
        ("missing_pid", TypeError, "process IDs must be integers"),
        ("boolean_pid", TypeError, "process IDs must be integers"),
        ("duplicate_pid", ValueError, "separate editor processes"),
        ("mapping_array", TypeError, "must be an array"),
        ("artifact", ValueError, "missing or duplicate artifacts"),
        ("frame_count", ValueError, "frame accounting"),
        ("expected_frames", ValueError, "frame accounting"),
        ("errors", ValueError, "array of strings"),
        ("lifecycle_bool", TypeError, "must be a boolean"),
    ],
)
def test_rejects_invalid_native_evidence(
    mutation: str,
    exception: type[Exception],
    message: str,
) -> None:
    payloads = _payloads(EngineName.UNITY)
    if mutation == "readback_engine":
        payloads["readback"]["engine"] = "unreal"
    elif mutation == "render_engine":
        payloads["render"]["engine"] = "unreal"
    elif mutation == "bundle":
        payloads["render"]["source_bundle_sha256"] = "f" * 64
    elif mutation == "semantics":
        payloads["readback"]["semantics"]["project_id"] = "other-project"
    elif mutation == "missing_pid":
        payloads["lifecycle"].pop("readback_process_id")
    elif mutation == "boolean_pid":
        payloads["lifecycle"]["readback_process_id"] = True
    elif mutation == "duplicate_pid":
        payloads["lifecycle"]["readback_process_id"] = 101
    elif mutation == "mapping_array":
        payloads["mapping"]["body_tracks"] = {}
    elif mutation == "artifact":
        payloads["mapping"]["body_tracks"][0] = {}
    elif mutation == "frame_count":
        payloads["render"]["rendered_frame_count"] = 3
    elif mutation == "expected_frames":
        payloads["render"]["expected_frame_count"] = 5
    elif mutation == "errors":
        payloads["lifecycle"]["errors"] = [1]
    elif mutation == "lifecycle_bool":
        payloads["lifecycle"]["saved"] = "true"

    with pytest.raises(exception, match=message):
        _collect(payloads, EngineName.UNITY)


@pytest.mark.parametrize("engine", list(EngineName))
def test_generated_collector_is_self_contained_and_equivalent(
    tmp_path: Path, engine: EngineName
) -> None:
    payloads = _payloads(engine)
    inputs = {
        "mapping": _data(payloads["mapping"]),
        "lifecycle": _data(payloads["lifecycle"]),
        "readback": _data(payloads["readback"]),
        "render": _data(payloads["render"]),
        "log": payloads["log"],
    }
    paths = {}
    for name, data in inputs.items():
        path = tmp_path / f"{name}.json"
        path.write_bytes(data)
        paths[name] = path
    script = tmp_path / "collect-native-evidence.py"
    script.write_text(render_native_evidence_collector_script(), encoding="utf-8")
    compile(script.read_text(encoding="utf-8"), str(script), "exec")
    output = tmp_path / "evidence.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--engine",
            engine.value,
            "--mapping",
            str(paths["mapping"]),
            "--lifecycle",
            str(paths["lifecycle"]),
            "--readback",
            str(paths["readback"]),
            "--render-manifest",
            str(paths["render"]),
            "--editor-log",
            str(paths["log"]),
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    expected = _collect(payloads, engine)
    assert json.loads(output.read_text(encoding="utf-8")) == expected.model_dump(
        mode="json"
    )
