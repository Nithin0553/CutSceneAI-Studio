from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .artifact_io import canonical_json_bytes, sha256_bytes, write_json
from .sample_writer import write_guard_turn_sample


@dataclass(frozen=True)
class GuardTurnDatasetConfig:
    dataset_id: str = "cutsceneai-guard-turn-v0.1"
    seed: int = 20260928
    num_families: int = 12
    variants_per_family: int = 2
    min_abs_bearing_deg: float = 30.0
    max_abs_bearing_deg: float = 150.0
    min_target_distance_m: float = 2.0
    max_target_distance_m: float = 6.0
    min_turn_frames: int = 30
    max_turn_frames: int = 54
    hold_frames: int = 18

    def validate(self) -> None:
        if self.num_families < 3:
            raise ValueError("num_families must be at least 3.")
        if self.variants_per_family < 1:
            raise ValueError("variants_per_family must be positive.")
        if not 0.0 < self.min_abs_bearing_deg <= self.max_abs_bearing_deg < 180.0:
            raise ValueError("bearing range must be inside (0, 180) degrees.")
        if not 0.0 < self.min_target_distance_m <= self.max_target_distance_m:
            raise ValueError("target distance range is invalid.")
        if not 3 <= self.min_turn_frames <= self.max_turn_frames:
            raise ValueError("turn frame range is invalid.")
        if self.hold_frames < 1:
            raise ValueError("hold_frames must be positive.")


def _split_for_family(family_index: int) -> str:
    bucket = family_index % 10
    if bucket == 0:
        return "val"
    if bucket == 1:
        return "test"
    return "train"


def _family_parameters(
    config: GuardTurnDatasetConfig,
    family_index: int,
) -> dict[str, float | str]:
    rng = np.random.default_rng(config.seed + family_index * 1009)
    initial_yaw = float(rng.uniform(-math.pi, math.pi))
    magnitude_deg = float(
        rng.uniform(config.min_abs_bearing_deg, config.max_abs_bearing_deg)
    )
    sign = -1.0 if int(rng.integers(0, 2)) == 0 else 1.0
    bearing = math.radians(sign * magnitude_deg)
    target_distance = float(
        rng.uniform(config.min_target_distance_m, config.max_target_distance_m)
    )
    return {
        "initial_yaw": initial_yaw,
        "bearing": bearing,
        "target_distance_m": target_distance,
        "support_foot": "left" if sign > 0 else "right",
    }


def _variant_turn_frames(
    config: GuardTurnDatasetConfig,
    family_index: int,
    variant_index: int,
) -> int:
    rng = np.random.default_rng(
        config.seed + family_index * 1009 + variant_index * 9176 + 17
    )
    return int(rng.integers(config.min_turn_frames, config.max_turn_frames + 1))


def generate_guard_turn_dataset(
    output_dir: str | Path,
    *,
    config: GuardTurnDatasetConfig | None = None,
) -> dict[str, object]:
    config = config or GuardTurnDatasetConfig()
    config.validate()

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    sample_records: list[dict[str, str]] = []
    split_counts = {"train": 0, "val": 0, "test": 0}

    for family_index in range(config.num_families):
        split = _split_for_family(family_index)
        family = _family_parameters(config, family_index)

        for variant_index in range(config.variants_per_family):
            sample_id = f"guard-turn-{family_index:04d}-v{variant_index:02d}"
            family_id = f"guard-turn-family-{family_index:04d}"
            sample_dir = output / split / sample_id

            written_id, fingerprint = write_guard_turn_sample(
                dataset_id=config.dataset_id,
                dataset_seed=config.seed,
                family_index=family_index,
                variant_index=variant_index,
                split=split,
                initial_yaw=float(family["initial_yaw"]),
                bearing=float(family["bearing"]),
                target_distance_m=float(family["target_distance_m"]),
                support_foot=str(family["support_foot"]),
                turn_frames=_variant_turn_frames(
                    config,
                    family_index,
                    variant_index,
                ),
                hold_frames=config.hold_frames,
                sample_dir=sample_dir,
            )
            if written_id != sample_id:
                raise RuntimeError("Sample writer returned an unexpected sample id.")

            sample_records.append(
                {
                    "sample_id": sample_id,
                    "family_id": family_id,
                    "split": split,
                    "fingerprint": fingerprint,
                }
            )
            split_counts[split] += 1

    sorted_samples = sorted(sample_records, key=lambda item: item["sample_id"])
    dataset_fingerprint = sha256_bytes(
        canonical_json_bytes(
            {
                "dataset_id": config.dataset_id,
                "dataset_version": "0.1.0",
                "seed": config.seed,
                "samples": sorted_samples,
            }
        )
    )

    manifest: dict[str, object] = {
        "dataset_id": config.dataset_id,
        "dataset_version": "0.1.0",
        "schema_version": "0.1.0",
        "status": "contract_validation_only",
        "canonical_fps": 30,
        "dataset_fingerprint": dataset_fingerprint,
        "generator": {
            "name": "cutsceneai-guard-turn",
            "version": "0.1.0",
            "seed": config.seed,
        },
        "contract_versions": {
            "canonical_training": "0.1.0",
            "scene_conditioning": "0.1.0",
            "choreography_temporal": "0.1.0",
            "canonical_body_target": "0.1.0",
            "contact_gaze_target": "0.1.0",
            "training_dataset": "0.1.0",
            "evaluation_metrics": "0.1.0",
        },
        "sample_count": len(sorted_samples),
        "family_count": config.num_families,
        "split_counts": split_counts,
        "usage_pool": "research",
        "training_eligibility": "contract_validation_only",
        "samples": sorted_samples,
    }
    write_json(output / "manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the CutSceneAI guard-turn v0.1 contract dataset."
    )
    parser.add_argument("output_dir")
    parser.add_argument("--seed", type=int, default=GuardTurnDatasetConfig.seed)
    parser.add_argument(
        "--families",
        type=int,
        default=GuardTurnDatasetConfig.num_families,
    )
    parser.add_argument(
        "--variants-per-family",
        type=int,
        default=GuardTurnDatasetConfig.variants_per_family,
    )
    args = parser.parse_args()

    manifest = generate_guard_turn_dataset(
        args.output_dir,
        config=GuardTurnDatasetConfig(
            seed=args.seed,
            num_families=args.families,
            variants_per_family=args.variants_per_family,
        ),
    )
    print(
        json.dumps(
            {
                "dataset_id": manifest["dataset_id"],
                "sample_count": manifest["sample_count"],
                "split_counts": manifest["split_counts"],
                "dataset_fingerprint": manifest["dataset_fingerprint"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
