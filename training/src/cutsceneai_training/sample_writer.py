from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifact_io import canonical_json_bytes, sha256_bytes, write_json, write_npy
from .choreography_builder import build_guard_turn_choreography
from .procedural_turn import build_turn_reference
from .scene_builder import build_guard_turn_scene


def _write_array(path: Path, array) -> dict[str, Any]:
    sha = write_npy(path, array)
    return {
        "relative_path": path.name,
        "format": "npy",
        "sha256": sha,
        "byte_length": path.stat().st_size,
    }


def write_guard_turn_sample(
    *,
    dataset_id: str,
    dataset_seed: int,
    family_index: int,
    variant_index: int,
    split: str,
    initial_yaw: float,
    bearing: float,
    target_distance_m: float,
    support_foot: str,
    turn_frames: int,
    hold_frames: int,
    sample_dir: Path,
) -> tuple[str, str]:
    sample_id = f"guard-turn-{family_index:04d}-v{variant_index:02d}"
    family_id = f"guard-turn-family-{family_index:04d}"

    body, contact_gaze, timing = build_turn_reference(
        initial_yaw=initial_yaw,
        bearing=bearing,
        turn_frames=turn_frames,
        hold_frames=hold_frames,
        support_foot=support_foot,
    )
    frame_count = int(timing["frame_count"])

    artifacts: dict[str, dict[str, Any]] = {}
    for name, array in {**body, **contact_gaze}.items():
        artifacts[name] = _write_array(sample_dir / f"{name}.npy", array)

    scene = build_guard_turn_scene(
        family_id=family_id,
        initial_yaw=initial_yaw,
        bearing=bearing,
        target_distance_m=target_distance_m,
    )
    choreography = build_guard_turn_choreography(
        frame_count=frame_count,
        gaze_start=int(timing["gaze_start"]),
        head_complete=int(timing["head_complete"]),
        root_start=int(timing["root_start"]),
        turn_end=int(timing["turn_end"]),
    )

    example = {
        "identity": {
            "schema_version": "0.1.0",
            "sample_id": sample_id,
            "family_id": family_id,
            "split": split,
            "fps": 30,
            "sequence_frame_count": frame_count,
        },
        "conditioning": {
            "narrative": {
                "prompt": "A guard turns cautiously toward a suspicious door.",
                "scene_intent": "target-conditioned cautious turn",
            },
            "scene_conditioning": scene,
            "choreography": choreography,
            "previous_body_state": {
                "root_position_m": body["root_position_m"][0].tolist(),
                "root_rotation_6d_columns": body["root_rotation_6d_columns"][
                    0
                ].tolist(),
                "joint_rotations_6d_columns": body["joint_rotations_6d_columns"][
                    0
                ].tolist(),
            },
        },
        "targets": {
            "body": {
                "available": True,
                "quality_class": "procedural_contract_reference",
            },
            "contact_gaze": {
                "available": True,
                "gaze_target_intervals": [
                    {
                        "start_frame": int(timing["gaze_start"]),
                        "end_frame": frame_count,
                        "target_entity_id": "door",
                        "target_point_id": "visual-center",
                    }
                ],
            },
            "camera": {"available": False},
        },
        "metadata": {
            "provenance": {
                "source_kind": "synthetic",
                "source_dataset_or_generator": dataset_id,
                "source_record_id": sample_id,
                "canonicalizer_version": "guard-turn-generator-v0.1",
                "generation_seed": dataset_seed,
                "human_review_status": "not_reviewed",
            },
            "rights": {
                "rights_status": "unknown",
                "training_use_status": "not_reviewed",
                "redistribution_status": "not_reviewed",
                "model_distribution_status": "not_reviewed",
                "review_status": "not_reviewed",
                "usage_pool": "research",
            },
            "quality": {
                "training_eligibility": "contract_validation_only",
                "body_quality": "procedural_reference",
            },
            "parameters": {
                "initial_yaw_rad": initial_yaw,
                "target_bearing_rad": bearing,
                "target_distance_m": target_distance_m,
                "turn_frames": turn_frames,
                "hold_frames": hold_frames,
                "support_foot": support_foot,
            },
        },
        "artifacts": artifacts,
    }

    example_sha = write_json(sample_dir / "example.json", example)
    fingerprint = sha256_bytes(
        canonical_json_bytes(
            {
                "sample_id": sample_id,
                "example_sha256": example_sha,
                "artifacts": {
                    key: value["sha256"] for key, value in sorted(artifacts.items())
                },
            }
        )
    )
    return sample_id, fingerprint
