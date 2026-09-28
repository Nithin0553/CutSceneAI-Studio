from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .artifact_io import write_json
from .smpl_ingestion import ingest_smpl_npz
from .smpl_source import MotionRights
from .turn_candidates import materialize_turn_candidates
from .turn_mining import mine_canonical_record
from .turn_qa import evaluate_turn_dataset


AMASS_LICENSE_REFERENCE = "https://amass.is.tue.mpg.de/license.html"


def amass_research_rights() -> MotionRights:
    return MotionRights(
        rights_status="research_only",
        training_use_status="allowed",
        model_distribution_status="unclear",
        redistribution_status="not_allowed",
        review_status="allowed",
        license_name=(
            "AMASS Dataset Copyright License for non-commercial scientific "
            "research purposes"
        ),
        license_reference=AMASS_LICENSE_REFERENCE,
        notes=(
            "CutSceneAI research-pool use only. Commercial model training is "
            "not permitted by the reviewed AMASS license."
        ),
    )


def discover_amass_motion_files(source_root: str | Path) -> list[Path]:
    root = Path(source_root)
    if not root.is_dir():
        raise ValueError(f"AMASS source root does not exist: {root}")
    return sorted(path for path in root.rglob("*_poses.npz") if path.is_file())


def source_family_id(source_root: Path, motion_path: Path) -> str:
    relative = motion_path.relative_to(source_root)
    parents = relative.parts[:-1]
    if not parents:
        return f"amass:{motion_path.stem}"
    return "amass:" + "/".join(parents)


def _record_output_dir(work_root: Path, source_root: Path, source_file: Path) -> Path:
    relative = source_file.relative_to(source_root)
    return work_root / "records" / relative.parent / relative.stem


def run_amass_turn_pilot(
    source_root: str | Path,
    work_dir: str | Path,
    *,
    limit: int = 10,
    license_confirmed: bool = False,
) -> dict[str, Any]:
    if not license_confirmed:
        raise ValueError(
            "AMASS license confirmation is required before running the research pilot."
        )
    if limit < 1:
        raise ValueError("limit must be positive.")

    source_root_path = Path(source_root)
    work_root = Path(work_dir)
    files = discover_amass_motion_files(source_root_path)[:limit]
    rights = amass_research_rights()

    source_records: list[dict[str, Any]] = []
    total_turn_candidates = 0
    total_materialized_samples = 0

    for source_file in files:
        record_dir = _record_output_dir(
            work_root,
            source_root_path,
            source_file,
        )
        relative = source_file.relative_to(source_root_path)
        family_id = source_family_id(source_root_path, source_file)

        record = ingest_smpl_npz(
            source_file,
            record_dir,
            source_dataset="AMASS",
            source_family_id=family_id,
            rights=rights,
            usage_pool="research",
            source_forward_axis="+z",
        )
        mined = mine_canonical_record(record_dir)
        materialized = materialize_turn_candidates(
            record_dir,
            work_root / "turn-candidates",
        )

        candidate_count = int(mined["candidate_count"])
        sample_count = int(materialized["sample_count"])
        total_turn_candidates += candidate_count
        total_materialized_samples += sample_count

        source_records.append(
            {
                "relative_source_path": relative.as_posix(),
                "source_family_id": family_id,
                "canonical_frame_count": record["frame_count"],
                "turn_candidate_count": candidate_count,
                "materialized_sample_count": sample_count,
                "split": materialized["split"],
            }
        )

    qa_report = evaluate_turn_dataset(work_root / "turn-candidates")

    manifest: dict[str, Any] = {
        "pilot_id": "cutsceneai-amass-turn-pilot-v0.1",
        "status": "research_only",
        "license_reference": AMASS_LICENSE_REFERENCE,
        "source_file_count": len(files),
        "turn_candidate_count": total_turn_candidates,
        "materialized_sample_count": total_materialized_samples,
        "usage_pool": "research",
        "training_eligibility": "review_candidates_only",
        "qa": {
            "sample_count": qa_report["sample_count"],
            "automated_qa_pass_count": qa_report["automated_qa_pass_count"],
            "human_review_pass_count": qa_report["human_review_pass_count"],
            "training_ready_count": qa_report["training_ready_count"],
            "family_split_ok": qa_report["family_split_ok"],
            "automated_dataset_pass": qa_report["automated_dataset_pass"],
        },
        "sources": source_records,
    }
    write_json(work_root / "amass-turn-pilot-manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a small research-only AMASS turn-data pilot."
    )
    parser.add_argument("source_root")
    parser.add_argument("work_dir")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument(
        "--confirm-amass-license",
        action="store_true",
        help=(
            "Confirm that you obtained AMASS yourself and accepted its current "
            "non-commercial research license."
        ),
    )
    args = parser.parse_args()

    manifest = run_amass_turn_pilot(
        args.source_root,
        args.work_dir,
        limit=args.limit,
        license_confirmed=args.confirm_amass_license,
    )
    print(
        json.dumps(
            {
                "pilot_id": manifest["pilot_id"],
                "source_file_count": manifest["source_file_count"],
                "turn_candidate_count": manifest["turn_candidate_count"],
                "materialized_sample_count": manifest["materialized_sample_count"],
                "usage_pool": manifest["usage_pool"],
                "automated_qa_pass_count": manifest["qa"]["automated_qa_pass_count"],
                "training_ready_count": manifest["qa"]["training_ready_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
