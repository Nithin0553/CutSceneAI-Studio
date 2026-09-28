from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Literal

from .artifact_io import write_json


ReviewStatus = Literal["approved", "rejected"]


def review_turn_sample(
    sample_dir: str | Path,
    *,
    status: ReviewStatus,
    reviewer: str,
    note: str,
) -> dict[str, object]:
    path = Path(sample_dir)
    example_path = path / "example.json"
    if not example_path.is_file():
        raise ValueError(f"Sample example.json does not exist: {example_path}")
    if status not in {"approved", "rejected"}:
        raise ValueError("status must be 'approved' or 'rejected'.")
    reviewer_value = reviewer.strip()
    note_value = note.strip()
    if not reviewer_value:
        raise ValueError("reviewer must be non-empty.")
    if not note_value:
        raise ValueError("review note must be non-empty.")

    example = json.loads(example_path.read_text())
    quality = example.setdefault("metadata", {}).setdefault("quality", {})
    quality["human_review_status"] = status
    quality["human_review"] = {
        "reviewer": reviewer_value,
        "note": note_value,
        "review_contract": "turn-human-review-v0.1",
    }
    if status == "approved":
        quality["training_eligibility"] = "human_approved_candidate"
    else:
        quality["training_eligibility"] = "rejected"

    write_json(example_path, example)
    return {
        "sample_id": example["identity"]["sample_id"],
        "status": status,
        "reviewer": reviewer_value,
        "training_eligibility": quality["training_eligibility"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Record an explicit human review decision for one turn candidate."
    )
    parser.add_argument("sample_dir")
    parser.add_argument("--status", choices=["approved", "rejected"], required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--note", required=True)
    args = parser.parse_args()

    result = review_turn_sample(
        args.sample_dir,
        status=args.status,
        reviewer=args.reviewer,
        note=args.note,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
