from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .artifact_io import canonical_json_bytes, sha256_bytes, write_json, write_npy
from .rotations import rotation_6d_to_matrix


_IDENTITY_6D = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]


@dataclass(frozen=True)
class TurnCandidateConfig:
    seed: int = 20260928
    min_target_distance_m: float = 2.0
    max_target_distance_m: float = 5.0

    def validate(self) -> None:
        if not 0.0 < self.min_target_distance_m <= self.max_target_distance_m:
            raise ValueError("target-distance range is invalid.")


def _stable_unit_interval(value: str) -> float:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    integer = int.from_bytes(digest[:8], "big")
    return integer / float((1 << 64) - 1)


def _split_for_family(family_id: str) -> str:
    bucket = int.from_bytes(
        hashlib.sha256(family_id.encode("utf-8")).digest()[:2],
        "big",
    ) % 10
    if bucket == 0:
        return "val"
    if bucket == 1:
        return "test"
    return "train"


def _write_array(path: Path, array: np.ndarray) -> dict[str, Any]:
    sha = write_npy(path, array)
    return {
        "relative_path": path.name,
        "format": "npy",
        "sha256": sha,
        "byte_length": path.stat().st_size,
    }


def _target_distance(config: TurnCandidateConfig, sample_id: str) -> float:
    alpha = _stable_unit_interval(f"{config.seed}:{sample_id}")
    return config.min_target_distance_m + alpha * (
        config.max_target_distance_m - config.min_target_distance_m
    )


def _final_forward(root_rotation_6d: np.ndarray) -> np.ndarray:
    matrix = rotation_6d_to_matrix(root_rotation_6d)
    forward = matrix @ np.array([0.0, 0.0, -1.0], dtype=np.float64)
    forward[1] = 0.0
    length = float(np.linalg.norm(forward))
    if length < 1e-12:
        raise ValueError("Final root orientation has no horizontal facing direction.")
    return forward / length


def _build_choreography(
    *,
    frame_count: int,
    active_start_frame: int,
    active_end_frame: int,
) -> dict[str, Any]:
    phases: list[dict[str, Any]] = [
        {
            "phase_id": "turn-to-target",
            "actor_entity_id": "performer",
            "phase_type": "orientation_change",
            "start_frame": active_start_frame,
            "end_frame": active_end_frame,
            "priority": 90,
            "channels": ["root", "lower_body", "torso", "head"],
            "target_entity_id": "target-marker",
            "coordination_group_id": "target-turn",
        }
    ]
    if active_end_frame < frame_count:
        phases.append(
            {
                "phase_id": "hold-target-facing",
                "actor_entity_id": "performer",
                "phase_type": "hold",
                "start_frame": active_end_frame,
                "end_frame": frame_count,
                "priority": 60,
                "channels": ["root", "lower_body", "torso", "head"],
                "target_entity_id": "target-marker",
                "coordination_group_id": "target-turn",
            }
        )

    return {
        "contract_version": "0.1.0",
        "duration_frames": frame_count,
        "events": [],
        "phases": phases,
        "constraints": [
            {
                "constraint_id": "face-target",
                "constraint_type": "body_facing",
                "actor_entity_id": "performer",
                "start_frame": max(0, active_end_frame - 1),
                "end_frame": frame_count,
                "strength": "hard",
                "weight": 1.0,
                "target_entity_id": "target-marker",
                "tolerance_degrees": 5.0,
            }
        ],
        "coordination_groups": [
            {
                "coordination_group_id": "target-turn",
                "member_phase_ids": [phase["phase_id"] for phase in phases],
            }
        ],
    }


def materialize_turn_candidates(
    record_dir: str | Path,
    output_dir: str | Path,
    *,
    config: TurnCandidateConfig | None = None,
) -> dict[str, Any]:
    config = config or TurnCandidateConfig()
    config.validate()

    source_dir = Path(record_dir)
    output = Path(output_dir)
    record = json.loads((source_dir / "record.json").read_text())
    candidates = json.loads((source_dir / "turn_candidates.json").read_text())

    root_position = np.load(
        source_dir / record["artifacts"]["root_position_m"]["relative_path"]
    )
    root_rotation = np.load(
        source_dir / record["artifacts"]["root_rotation_6d_columns"]["relative_path"]
    )
    joint_rotation = np.load(
        source_dir / record["artifacts"]["joint_rotations_6d_columns"]["relative_path"]
    )

    family_id = str(record["source"]["family_id"])
    split = _split_for_family(family_id)
    source_hash = str(record["source"]["file_sha256"])
    sample_records: list[dict[str, Any]] = []

    for index, candidate in enumerate(candidates["candidates"]):
        start = int(candidate["start_frame"])
        end = int(candidate["end_frame"])
        active_start = int(candidate["active_start_frame"]) - start
        active_end = int(candidate["active_end_frame"]) - start
        frame_count = end - start

        clipped_root = np.asarray(root_position[start:end], dtype=np.float32).copy()
        clipped_root -= clipped_root[0]
        clipped_root_rotation = np.asarray(
            root_rotation[start:end],
            dtype=np.float32,
        ).copy()
        clipped_joint_rotation = np.asarray(
            joint_rotation[start:end],
            dtype=np.float32,
        ).copy()

        sample_id = (
            f"human-turn-{source_hash[:12]}-{start:06d}-{end:06d}-{index:02d}"
        )
        sample_dir = output / split / sample_id

        final_forward = _final_forward(clipped_root_rotation[-1])
        distance = _target_distance(config, sample_id)
        target_position = clipped_root[-1].astype(np.float64) + final_forward * distance

        artifacts = {
            "root_position_m": _write_array(
                sample_dir / "root_position_m.npy",
                clipped_root,
            ),
            "root_rotation_6d_columns": _write_array(
                sample_dir / "root_rotation_6d_columns.npy",
                clipped_root_rotation,
            ),
            "joint_rotations_6d_columns": _write_array(
                sample_dir / "joint_rotations_6d_columns.npy",
                clipped_joint_rotation,
            ),
        }

        scene = {
            "contract_version": "0.1.0",
            "scene_id": sample_id,
            "entities": [
                {
                    "entity_id": "performer",
                    "semantic_type": "character",
                    "role": "performer",
                    "active": True,
                    "dynamic": True,
                    "transform": {
                        "position_m": clipped_root[0].tolist(),
                        "rotation_6d_columns": clipped_root_rotation[0].tolist(),
                        "scale": [1.0, 1.0, 1.0],
                    },
                },
                {
                    "entity_id": "target-marker",
                    "semantic_type": "directional_target",
                    "role": "target",
                    "active": True,
                    "dynamic": False,
                    "transform": {
                        "position_m": target_position.astype(float).tolist(),
                        "rotation_6d_columns": _IDENTITY_6D,
                        "scale": [1.0, 1.0, 1.0],
                    },
                    "target_points": [
                        {
                            "point_id": "facing-target",
                            "kind": "look",
                            "position_m": target_position.astype(float).tolist(),
                        }
                    ],
                },
            ],
            "relationships": [
                {
                    "source_entity_id": "performer",
                    "target_entity_id": "target-marker",
                    "relation": "orientation_target",
                }
            ],
            "support_surfaces": [],
        }

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
                    "prompt": "Turn naturally to face the target.",
                    "scene_intent": "target-conditioned body turn",
                },
                "scene_conditioning": scene,
                "choreography": _build_choreography(
                    frame_count=frame_count,
                    active_start_frame=active_start,
                    active_end_frame=active_end,
                ),
                "previous_body_state": {
                    "root_position_m": clipped_root[0].tolist(),
                    "root_rotation_6d_columns": clipped_root_rotation[0].tolist(),
                    "joint_rotations_6d_columns": clipped_joint_rotation[0].tolist(),
                },
            },
            "targets": {
                "body": {"available": True},
                "contact_gaze": {"available": False},
                "camera": {"available": False},
            },
            "metadata": {
                "provenance": {
                    "source_kind": "mined_human_motion",
                    "source_dataset": record["source"]["dataset"],
                    "source_record_id": record["source"]["record_id"],
                    "source_file_sha256": source_hash,
                    "source_family_id": family_id,
                    "source_window": [start, end],
                    "mining_contract": "canonical-turn-mining-v0.1",
                },
                "rights": record["rights"],
                "target_proxy": {
                    "kind": "synthetic_directional_proxy",
                    "distance_m": distance,
                    "statement": (
                        "The marker is generated from observed final body facing and does not "
                        "assert that a real target existed in the source capture."
                    ),
                },
                "quality": {
                    "training_eligibility": "review_candidate",
                    "human_review_status": "not_reviewed",
                    "contact_supervision": "unavailable",
                    "gaze_supervision": "unavailable",
                },
                "mined_turn": candidate,
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
                        key: value["sha256"]
                        for key, value in sorted(artifacts.items())
                    },
                }
            )
        )
        sample_records.append(
            {
                "sample_id": sample_id,
                "family_id": family_id,
                "split": split,
                "fingerprint": fingerprint,
            }
        )

    manifest = {
        "dataset_id": "cutsceneai-mined-human-turn-candidates-v0.1",
        "dataset_version": "0.1.0",
        "status": "review_candidates",
        "source_record_id": record["source"]["record_id"],
        "source_family_id": family_id,
        "split": split,
        "sample_count": len(sample_records),
        "usage_pool": record["rights"]["usage_pool"],
        "samples": sample_records,
    }
    write_json(output / f"manifest-{source_hash[:12]}.json", manifest)
    return manifest


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Materialize mined human turns as scene-conditioned training candidates."
    )
    parser.add_argument("record_dir")
    parser.add_argument("output_dir")
    parser.add_argument("--min-target-distance-m", type=float, default=2.0)
    parser.add_argument("--max-target-distance-m", type=float, default=5.0)
    parser.add_argument("--seed", type=int, default=20260928)
    args = parser.parse_args()

    manifest = materialize_turn_candidates(
        args.record_dir,
        args.output_dir,
        config=TurnCandidateConfig(
            seed=args.seed,
            min_target_distance_m=args.min_target_distance_m,
            max_target_distance_m=args.max_target_distance_m,
        ),
    )
    print(
        json.dumps(
            {
                "sample_count": manifest["sample_count"],
                "split": manifest["split"],
                "source_family_id": manifest["source_family_id"],
                "status": manifest["status"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
