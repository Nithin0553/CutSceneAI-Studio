from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from .artifact_io import write_json
from .rotations import rotation_6d_to_matrix, yaw_from_rotation_6d


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rotation_6d_valid(values: np.ndarray, *, tolerance: float = 1e-4) -> bool:
    rotations = np.asarray(values, dtype=np.float64).reshape(-1, 6)
    first = rotations[:, :3]
    second = rotations[:, 3:]
    first_norm = np.linalg.norm(first, axis=1)
    second_norm = np.linalg.norm(second, axis=1)
    orthogonality = np.sum(first * second, axis=1)
    return bool(
        np.all(np.abs(first_norm - 1.0) <= tolerance)
        and np.all(np.abs(second_norm - 1.0) <= tolerance)
        and np.all(np.abs(orthogonality) <= tolerance)
    )


def _facing_error_deg(
    root_position: np.ndarray,
    root_rotation_6d: np.ndarray,
    target_position: np.ndarray,
) -> float:
    matrix = rotation_6d_to_matrix(root_rotation_6d)
    actual = matrix @ np.array([0.0, 0.0, -1.0], dtype=np.float64)
    actual[1] = 0.0
    desired = np.asarray(target_position, dtype=np.float64) - np.asarray(
        root_position,
        dtype=np.float64,
    )
    desired[1] = 0.0
    actual_length = float(np.linalg.norm(actual))
    desired_length = float(np.linalg.norm(desired))
    if actual_length < 1e-12 or desired_length < 1e-12:
        raise ValueError("Cannot evaluate facing with a zero horizontal direction.")
    actual /= actual_length
    desired /= desired_length
    dot = float(np.clip(np.dot(actual, desired), -1.0, 1.0))
    return math.degrees(math.acos(dot))


def _continuity_metrics(
    root_position: np.ndarray, root_rotation: np.ndarray
) -> dict[str, float]:
    fps = 30.0
    velocity = np.diff(root_position, axis=0) * fps
    acceleration = np.diff(velocity, axis=0) * fps
    jerk = np.diff(acceleration, axis=0) * fps

    yaws = np.unwrap(
        np.array(
            [yaw_from_rotation_6d(value) for value in root_rotation],
            dtype=np.float64,
        )
    )
    angular_speed = np.degrees(np.diff(yaws)) * fps

    def max_norm(values: np.ndarray) -> float:
        if values.shape[0] == 0:
            return 0.0
        return float(np.max(np.linalg.norm(values, axis=1)))

    return {
        "max_root_speed_mps": max_norm(velocity),
        "max_root_acceleration_mps2": max_norm(acceleration),
        "max_root_jerk_mps3": max_norm(jerk),
        "max_root_angular_speed_deg_s": (
            float(np.max(np.abs(angular_speed))) if angular_speed.size else 0.0
        ),
    }


def evaluate_turn_sample(sample_dir: str | Path) -> dict[str, Any]:
    path = Path(sample_dir)
    example = json.loads((path / "example.json").read_text())
    frame_count = int(example["identity"]["sequence_frame_count"])

    artifact_results: dict[str, Any] = {}
    arrays: dict[str, np.ndarray] = {}
    artifact_ok = True
    for name, reference in example["artifacts"].items():
        artifact_path = path / reference["relative_path"]
        exists = artifact_path.is_file()
        hash_ok = exists and _sha256(artifact_path) == reference["sha256"]
        size_ok = exists and artifact_path.stat().st_size == reference["byte_length"]
        artifact_results[name] = {
            "exists": exists,
            "hash_ok": hash_ok,
            "size_ok": size_ok,
        }
        artifact_ok = artifact_ok and exists and hash_ok and size_ok
        if exists:
            arrays[name] = np.load(artifact_path, allow_pickle=False)

    required = {
        "root_position_m",
        "root_rotation_6d_columns",
        "joint_rotations_6d_columns",
    }
    required_present = required.issubset(arrays)

    shape_ok = False
    finite_ok = False
    rotations_ok = False
    facing_ok = False
    facing_metrics: dict[str, float | int] = {}
    continuity: dict[str, float] = {}

    if required_present:
        root_position = arrays["root_position_m"]
        root_rotation = arrays["root_rotation_6d_columns"]
        joint_rotation = arrays["joint_rotations_6d_columns"]
        shape_ok = (
            root_position.shape == (frame_count, 3)
            and root_rotation.shape == (frame_count, 6)
            and joint_rotation.shape == (frame_count, 22, 6)
        )
        finite_ok = bool(
            np.isfinite(root_position).all()
            and np.isfinite(root_rotation).all()
            and np.isfinite(joint_rotation).all()
        )
        rotations_ok = _rotation_6d_valid(root_rotation) and _rotation_6d_valid(
            joint_rotation
        )

        if shape_ok and finite_ok and rotations_ok:
            continuity = _continuity_metrics(root_position, root_rotation)

            scene_entities = {
                entity["entity_id"]: entity
                for entity in example["conditioning"]["scene_conditioning"]["entities"]
            }
            constraints = example["conditioning"]["choreography"]["constraints"]
            facing_constraints = [
                item for item in constraints if item["constraint_type"] == "body_facing"
            ]
            errors: list[float] = []
            tolerances: list[float] = []
            for constraint in facing_constraints:
                target = scene_entities[constraint["target_entity_id"]]
                target_position = np.asarray(
                    target["transform"]["position_m"],
                    dtype=np.float64,
                )
                tolerance = float(constraint.get("tolerance_degrees", 5.0))
                start = int(constraint["start_frame"])
                end = int(constraint["end_frame"])
                for frame in range(start, end):
                    errors.append(
                        _facing_error_deg(
                            root_position[frame],
                            root_rotation[frame],
                            target_position,
                        )
                    )
                    tolerances.append(tolerance)

            if errors:
                error_array = np.asarray(errors, dtype=np.float64)
                tolerance_array = np.asarray(tolerances, dtype=np.float64)
                facing_ok = bool(np.all(error_array <= tolerance_array + 1e-6))
                facing_metrics = {
                    "evaluated_frame_count": int(error_array.size),
                    "mean_facing_error_deg": float(np.mean(error_array)),
                    "max_facing_error_deg": float(np.max(error_array)),
                    "final_facing_error_deg": float(error_array[-1]),
                }
            else:
                facing_ok = False

    rights = example["metadata"]["rights"]
    usage_pool = str(rights.get("usage_pool", "research"))
    rights_ok = not (
        usage_pool == "production_candidate"
        and rights.get("rights_status") in {"research_only", "restricted", "unknown"}
    )

    human_review_status = str(
        example["metadata"]["quality"].get("human_review_status", "not_reviewed")
    )
    human_review_pass = human_review_status in {"approved", "passed"}

    automated_pass = bool(
        artifact_ok
        and required_present
        and shape_ok
        and finite_ok
        and rotations_ok
        and facing_ok
        and rights_ok
    )
    return {
        "sample_id": example["identity"]["sample_id"],
        "family_id": example["identity"]["family_id"],
        "split": example["identity"]["split"],
        "artifact_checks": artifact_results,
        "required_artifacts_present": required_present,
        "shape_ok": shape_ok,
        "finite_ok": finite_ok,
        "rotations_ok": rotations_ok,
        "facing_ok": facing_ok,
        "facing_metrics": facing_metrics,
        "continuity_metrics": continuity,
        "rights_ok": rights_ok,
        "usage_pool": usage_pool,
        "human_review_status": human_review_status,
        "human_review_pass": human_review_pass,
        "automated_qa_pass": automated_pass,
        "training_ready": automated_pass and human_review_pass,
    }


def evaluate_turn_dataset(dataset_root: str | Path) -> dict[str, Any]:
    root = Path(dataset_root)
    sample_dirs = sorted({path.parent for path in root.rglob("example.json")})
    sample_results = [evaluate_turn_sample(path) for path in sample_dirs]

    splits_by_family: dict[str, set[str]] = {}
    for result in sample_results:
        splits_by_family.setdefault(result["family_id"], set()).add(result["split"])
    leaking_families = sorted(
        family_id for family_id, splits in splits_by_family.items() if len(splits) > 1
    )

    report = {
        "qa_version": "turn-dataset-qa-v0.1",
        "sample_count": len(sample_results),
        "automated_qa_pass_count": sum(
            bool(result["automated_qa_pass"]) for result in sample_results
        ),
        "human_review_pass_count": sum(
            bool(result["human_review_pass"]) for result in sample_results
        ),
        "training_ready_count": sum(
            bool(result["training_ready"]) for result in sample_results
        ),
        "family_split_leakage": leaking_families,
        "family_split_ok": not leaking_families,
        "automated_dataset_pass": (
            bool(sample_results)
            and not leaking_families
            and all(bool(result["automated_qa_pass"]) for result in sample_results)
        ),
        "samples": sample_results,
    }
    write_json(root / "qa-report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run CutSceneAI automated QA over scene-conditioned turn candidates."
    )
    parser.add_argument("dataset_root")
    args = parser.parse_args()

    report = evaluate_turn_dataset(args.dataset_root)
    print(
        json.dumps(
            {
                "sample_count": report["sample_count"],
                "automated_qa_pass_count": report["automated_qa_pass_count"],
                "human_review_pass_count": report["human_review_pass_count"],
                "training_ready_count": report["training_ready_count"],
                "family_split_ok": report["family_split_ok"],
                "automated_dataset_pass": report["automated_dataset_pass"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
