from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .artifact_io import sha256_bytes, write_json, write_npy
from .smpl_canonicalize import CanonicalSMPLMotion, canonicalize_smpl_motion
from .smpl_source import MotionRights, load_smpl_npz


def _artifact_ref(path: Path) -> dict[str, Any]:
    return {
        "relative_path": path.name,
        "format": "npy",
        "sha256": sha256_bytes(path.read_bytes()),
        "byte_length": path.stat().st_size,
    }


def write_canonical_smpl_record(
    output_dir: str | Path,
    *,
    motion: CanonicalSMPLMotion,
    source_dataset: str,
    source_file_sha256: str,
    source_family_id: str | None,
    rights: MotionRights,
    usage_pool: str,
) -> dict[str, Any]:
    rights.validate(usage_pool=usage_pool)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    artifacts: dict[str, dict[str, Any]] = {}
    for name, array in (
        ("root_position_m", motion.root_position_m),
        ("root_rotation_6d_columns", motion.root_rotation_6d_columns),
        ("joint_rotations_6d_columns", motion.joint_rotations_6d_columns),
    ):
        path = output / f"{name}.npy"
        write_npy(path, array)
        artifacts[name] = _artifact_ref(path)

    record: dict[str, Any] = {
        "record_version": "0.1.0",
        "record_kind": "canonical_smpl_motion",
        "canonical_contract_version": "0.1.0",
        "source": {
            "dataset": source_dataset,
            "record_id": motion.source_record_id,
            "file_sha256": source_file_sha256,
            "family_id": source_family_id or f"sha256:{source_file_sha256}",
            "source_fps": motion.source_fps,
            "source_forward_axis": motion.source_forward_axis,
        },
        "canonicalization": {
            "target_fps": motion.target_fps,
            "target_skeleton": "cutsceneai-humanoid-v1",
            "rotation_representation": "rotation_6d_columns",
            "root_orientation_explicit": True,
            "pelvis_local_policy": "identity_root_articulation",
            "translation_origin_policy": motion.translation_origin_policy,
            "resampling": "endpoint-preserving-linear-slerp-v0.1",
        },
        "rights": {
            **rights.as_dict(),
            "usage_pool": usage_pool,
        },
        "quality": {
            "human_review_status": "not_reviewed",
            "training_clip_status": "canonicalized_not_yet_mined",
        },
        "frame_count": motion.frame_count,
        "artifacts": artifacts,
    }
    write_json(output / "record.json", record)
    return record


def ingest_smpl_npz(
    source_path: str | Path,
    output_dir: str | Path,
    *,
    source_dataset: str,
    rights: MotionRights,
    source_family_id: str | None = None,
    usage_pool: str = "research",
    fps_override: float | None = None,
    source_forward_axis: str = "+z",
    translation_origin_policy: str = "first_frame_zero",
) -> dict[str, Any]:
    source_file = Path(source_path)
    source_sha = sha256_bytes(source_file.read_bytes())
    source = load_smpl_npz(
        source_file,
        fps_override=fps_override,
        source_forward_axis=source_forward_axis,
    )
    motion = canonicalize_smpl_motion(
        source,
        target_fps=30,
        translation_origin_policy=translation_origin_policy,
    )
    return write_canonical_smpl_record(
        output_dir,
        motion=motion,
        source_dataset=source_dataset,
        source_file_sha256=source_sha,
        source_family_id=source_family_id,
        rights=rights,
        usage_pool=usage_pool,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Canonicalize a rights-reviewed SMPL/SMPL-X NPZ for CutSceneAI training."
    )
    parser.add_argument("source_npz")
    parser.add_argument("output_dir")
    parser.add_argument("--source-dataset", required=True)
    parser.add_argument("--source-family-id")
    parser.add_argument("--fps", type=float)
    parser.add_argument(
        "--source-forward-axis",
        choices=["+z", "-z"],
        default="+z",
    )
    parser.add_argument(
        "--usage-pool",
        choices=["research", "production_candidate"],
        default="research",
    )
    parser.add_argument("--rights-status", required=True)
    parser.add_argument("--training-use-status", required=True)
    parser.add_argument("--model-distribution-status", required=True)
    parser.add_argument("--redistribution-status", default="not_reviewed")
    parser.add_argument("--review-status", default="not_reviewed")
    parser.add_argument("--license-name")
    parser.add_argument("--license-reference")
    args = parser.parse_args()

    record = ingest_smpl_npz(
        args.source_npz,
        args.output_dir,
        source_dataset=args.source_dataset,
        source_family_id=args.source_family_id,
        rights=MotionRights(
            rights_status=args.rights_status,
            training_use_status=args.training_use_status,
            model_distribution_status=args.model_distribution_status,
            redistribution_status=args.redistribution_status,
            review_status=args.review_status,
            license_name=args.license_name,
            license_reference=args.license_reference,
        ),
        usage_pool=args.usage_pool,
        fps_override=args.fps,
        source_forward_axis=args.source_forward_axis,
    )
    print(
        json.dumps(
            {
                "record_kind": record["record_kind"],
                "frame_count": record["frame_count"],
                "usage_pool": record["rights"]["usage_pool"],
                "root_orientation_explicit": record["canonicalization"][
                    "root_orientation_explicit"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
