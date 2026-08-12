from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest
from cutsceneai_performance import (
    GeneratedPerformancePackage,
    performance_package_fingerprint,
    render_performance_package,
)
from pydantic import ValidationError

SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64


def package_payload() -> dict[str, Any]:
    provenance = {
        "provider": "research",
        "model": "motion-model",
        "model_revision": "checkpoint-1",
        "prompt_sha256": SHA_A,
        "configuration_sha256": SHA_B,
        "seed": 42,
        "generated_at_inference": True,
        "retrieved_pre_authored_clip": False,
        "deterministic_algorithms": True,
    }
    return {
        "package_version": "0.1.0",
        "cir_schema_version": "0.1.0",
        "project_id": "office-dialogue",
        "cir_fingerprint_sha256": SHA_C,
        "fps": 24,
        "duration_frames": 432,
        "coordinate_space": {
            "distance_unit": "meter",
            "handedness": "right",
            "up_axis": "y",
            "forward_axis": "-z",
            "rotation_representation": "quaternion_xyzw",
        },
        "body_tracks": [
            {
                "semantic_id": "body:scene-meeting:mina:arrival",
                "actor_binding_id": "actor:mina",
                "source_performance_cue_id": (
                    "performance:scene-meeting:beat-arrival:mina:01"
                ),
                "start_frame": 0,
                "end_frame": 96,
                "skeleton_profile": "cutsceneai-humanoid-v1",
                "joint_count": 22,
                "sample_count": 96,
                "artifact": {
                    "kind": "body_motion",
                    "format": "cutsceneai.motion+json",
                    "relative_path": "body/mina-arrival.motion.json",
                    "sha256": SHA_A,
                    "byte_length": 1024,
                },
                "provenance": provenance,
            }
        ],
        "facial_tracks": [
            {
                "semantic_id": "face:scene-meeting:mina:confrontation",
                "actor_binding_id": "actor:mina",
                "source_performance_cue_id": (
                    "performance:scene-meeting:beat-confrontation:mina:01"
                ),
                "source_dialogue_cue_id": (
                    "dialogue:scene-meeting:beat-confrontation:mina:01"
                ),
                "start_frame": 120,
                "end_frame": 178,
                "curve_profile": "arkit-52",
                "curve_count": 52,
                "sample_count": 58,
                "artifact": {
                    "kind": "facial_curves",
                    "format": "cutsceneai.face+json",
                    "relative_path": "face/mina-confrontation.face.json",
                    "sha256": SHA_C,
                    "byte_length": 768,
                },
                "provenance": {**provenance, "model": "face-model"},
            }
        ],
        "camera_tracks": [
            {
                "semantic_id": "camera-motion:scene-meeting:shot-establishing",
                "camera_binding_id": "camera:shot-establishing",
                "source_camera_cut_id": "camera:scene-meeting:shot-establishing",
                "start_frame": 0,
                "end_frame": 96,
                "sample_count": 96,
                "artifact": {
                    "kind": "camera_curves",
                    "format": "cutsceneai.camera+json",
                    "relative_path": "camera/shot-establishing.camera.json",
                    "sha256": SHA_B,
                    "byte_length": 512,
                },
                "provenance": {**provenance, "model": "camera-model"},
            }
        ],
        "audio_tracks": [
            {
                "dialogue_cue_id": (
                    "dialogue:scene-meeting:beat-confrontation:mina:01"
                ),
                "actor_binding_id": "actor:mina",
                "start_frame": 120,
                "end_frame": 178,
                "artifact": {
                    "kind": "dialogue_audio",
                    "format": "audio/wav",
                    "relative_path": "audio/mina-confrontation.wav",
                    "sha256": "d" * 64,
                    "byte_length": 2048,
                },
            }
        ],
    }


def test_package_accepts_engine_neutral_generated_tracks() -> None:
    package = GeneratedPerformancePackage.model_validate(package_payload())

    assert package.project_id == "office-dialogue"
    assert package.body_tracks[0].provenance.retrieved_pre_authored_clip is False
    assert package.coordinate_space.handedness == "right"


def test_package_render_and_fingerprint_are_deterministic() -> None:
    package = GeneratedPerformancePackage.model_validate(package_payload())

    assert render_performance_package(package) == render_performance_package(package)
    assert performance_package_fingerprint(package) == performance_package_fingerprint(
        package
    )
    assert len(performance_package_fingerprint(package)) == 64
    assert json.loads(render_performance_package(package))["fps"] == 24


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda value: value["body_tracks"][0].update(start_frame=1, end_frame=1),
            "end_frame",
        ),
        (
            lambda value: value["body_tracks"][0]["artifact"].update(
                kind="camera_curves"
            ),
            "body_motion",
        ),
        (
            lambda value: value["body_tracks"][0]["artifact"].update(
                format="cutsceneai.camera+json"
            ),
            "cutsceneai.motion",
        ),
        (
            lambda value: value["facial_tracks"][0]["artifact"].update(
                kind="body_motion"
            ),
            "facial_curves",
        ),
        (
            lambda value: value["facial_tracks"][0]["artifact"].update(
                format="cutsceneai.motion+json"
            ),
            "cutsceneai.face",
        ),
        (
            lambda value: value["camera_tracks"][0]["artifact"].update(
                kind="body_motion"
            ),
            "camera_curves",
        ),
        (
            lambda value: value["camera_tracks"][0]["artifact"].update(
                format="cutsceneai.motion+json"
            ),
            "cutsceneai.camera",
        ),
        (
            lambda value: value["audio_tracks"][0].update(end_frame=120),
            "end_frame",
        ),
        (
            lambda value: value["audio_tracks"][0]["artifact"].update(
                kind="body_motion"
            ),
            "dialogue_audio",
        ),
        (
            lambda value: value["audio_tracks"][0]["artifact"].update(
                format="cutsceneai.motion+json"
            ),
            "audio/wav",
        ),
        (
            lambda value: value["camera_tracks"][0].update(end_frame=433),
            "duration_frames",
        ),
        (
            lambda value: value["camera_tracks"][0]["artifact"].update(
                relative_path="../escape.json"
            ),
            "relative_path",
        ),
        (
            lambda value: value["camera_tracks"][0].update(
                semantic_id=value["body_tracks"][0]["semantic_id"]
            ),
            "semantic IDs",
        ),
        (
            lambda value: value["camera_tracks"][0]["artifact"].update(
                relative_path=value["body_tracks"][0]["artifact"]["relative_path"]
            ),
            "relative paths",
        ),
    ],
)
def test_package_rejects_invalid_realization_contract(
    mutation: Callable[[dict[str, Any]], None], message: str
) -> None:
    payload = package_payload()
    mutation(payload)

    with pytest.raises(ValidationError, match=message):
        GeneratedPerformancePackage.model_validate(payload)
