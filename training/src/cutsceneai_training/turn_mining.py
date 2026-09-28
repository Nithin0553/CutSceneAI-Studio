from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .artifact_io import write_json
from .rotations import yaw_from_rotation_6d


@dataclass(frozen=True)
class TurnMiningConfig:
    fps: int = 30
    active_angular_speed_deg_s: float = 20.0
    min_heading_change_deg: float = 30.0
    max_heading_change_deg: float = 150.0
    min_duration_frames: int = 18
    max_duration_frames: int = 90
    max_gap_frames: int = 4
    context_frames: int = 6
    max_horizontal_displacement_m: float = 1.0
    min_direction_consistency: float = 0.70

    def validate(self) -> None:
        if self.fps != 30:
            raise ValueError("Turn mining v0.1 requires the canonical 30 fps timebase.")
        if self.active_angular_speed_deg_s <= 0.0:
            raise ValueError("active_angular_speed_deg_s must be positive.")
        if not 0.0 < self.min_heading_change_deg <= self.max_heading_change_deg < 180.0:
            raise ValueError("heading-change range must lie inside (0, 180) degrees.")
        if not 2 <= self.min_duration_frames <= self.max_duration_frames:
            raise ValueError("duration-frame range is invalid.")
        if self.max_gap_frames < 0 or self.context_frames < 0:
            raise ValueError("gap/context frame counts cannot be negative.")
        if self.max_horizontal_displacement_m < 0.0:
            raise ValueError("max_horizontal_displacement_m cannot be negative.")
        if not 0.0 <= self.min_direction_consistency <= 1.0:
            raise ValueError("min_direction_consistency must be inside [0, 1].")


@dataclass(frozen=True)
class TurnWindow:
    start_frame: int
    end_frame: int
    active_start_frame: int
    active_end_frame: int
    heading_change_deg: float
    horizontal_displacement_m: float
    direction_consistency: float

    @property
    def direction(self) -> str:
        return "left" if self.heading_change_deg > 0.0 else "right"

    @property
    def frame_count(self) -> int:
        return self.end_frame - self.start_frame

    def as_dict(self) -> dict[str, Any]:
        return {
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
            "active_start_frame": self.active_start_frame,
            "active_end_frame": self.active_end_frame,
            "frame_count": self.frame_count,
            "heading_change_deg": self.heading_change_deg,
            "horizontal_displacement_m": self.horizontal_displacement_m,
            "direction_consistency": self.direction_consistency,
            "direction": self.direction,
        }


def _unwrap_yaw(root_rotation_6d: np.ndarray) -> np.ndarray:
    rotations = np.asarray(root_rotation_6d, dtype=np.float64)
    if rotations.ndim != 2 or rotations.shape[1] != 6:
        raise ValueError("root rotations must have shape [T, 6].")
    if rotations.shape[0] < 2:
        return np.array(
            [yaw_from_rotation_6d(rotations[0])],
            dtype=np.float64,
        )
    raw = np.array(
        [yaw_from_rotation_6d(rotations[index]) for index in range(rotations.shape[0])],
        dtype=np.float64,
    )
    return np.unwrap(raw)


def _active_groups(
    active_indices: np.ndarray, max_gap_frames: int
) -> list[tuple[int, int]]:
    if active_indices.size == 0:
        return []
    groups: list[tuple[int, int]] = []
    first = int(active_indices[0])
    previous = first
    for value in active_indices[1:]:
        current = int(value)
        if current - previous > max_gap_frames + 1:
            groups.append((first, previous))
            first = current
        previous = current
    groups.append((first, previous))
    return groups


def mine_turn_windows(
    *,
    root_position_m: np.ndarray,
    root_rotation_6d_columns: np.ndarray,
    config: TurnMiningConfig | None = None,
) -> list[TurnWindow]:
    config = config or TurnMiningConfig()
    config.validate()

    root_position = np.asarray(root_position_m, dtype=np.float64)
    if root_position.ndim != 2 or root_position.shape[1] != 3:
        raise ValueError("root positions must have shape [T, 3].")
    if root_position.shape[0] != np.asarray(root_rotation_6d_columns).shape[0]:
        raise ValueError("root position and rotation frame counts must match.")
    if root_position.shape[0] < 2:
        return []
    if not np.isfinite(root_position).all():
        raise ValueError("root positions contain non-finite values.")

    yaw = _unwrap_yaw(root_rotation_6d_columns)
    delta = np.diff(yaw)
    angular_speed_deg_s = np.abs(np.degrees(delta)) * config.fps
    active = np.flatnonzero(angular_speed_deg_s >= config.active_angular_speed_deg_s)

    windows: list[TurnWindow] = []
    for first_delta, last_delta in _active_groups(active, config.max_gap_frames):
        active_start = first_delta
        active_end = last_delta + 2
        start = max(0, active_start - config.context_frames)
        end = min(root_position.shape[0], active_end + config.context_frames)
        frame_count = end - start
        if not config.min_duration_frames <= frame_count <= config.max_duration_frames:
            continue

        heading_change_deg = math.degrees(yaw[active_end - 1] - yaw[active_start])
        if not (
            config.min_heading_change_deg
            <= abs(heading_change_deg)
            <= config.max_heading_change_deg
        ):
            continue

        segment_delta = delta[active_start : active_end - 1]
        total_rotation = float(np.sum(np.abs(segment_delta)))
        if total_rotation <= 1e-12:
            continue
        consistency = abs(float(np.sum(segment_delta))) / total_rotation
        if consistency < config.min_direction_consistency:
            continue

        displacement = root_position[end - 1] - root_position[start]
        horizontal_displacement = float(np.linalg.norm(displacement[[0, 2]]))
        if horizontal_displacement > config.max_horizontal_displacement_m:
            continue

        windows.append(
            TurnWindow(
                start_frame=start,
                end_frame=end,
                active_start_frame=active_start,
                active_end_frame=active_end,
                heading_change_deg=heading_change_deg,
                horizontal_displacement_m=horizontal_displacement,
                direction_consistency=consistency,
            )
        )

    return windows


def mine_canonical_record(
    record_dir: str | Path,
    *,
    config: TurnMiningConfig | None = None,
) -> dict[str, Any]:
    path = Path(record_dir)
    record = json.loads((path / "record.json").read_text())
    artifacts = record["artifacts"]
    root_position = np.load(path / artifacts["root_position_m"]["relative_path"])
    root_rotation = np.load(
        path / artifacts["root_rotation_6d_columns"]["relative_path"]
    )

    windows = mine_turn_windows(
        root_position_m=root_position,
        root_rotation_6d_columns=root_rotation,
        config=config,
    )
    result = {
        "record_version": "0.1.0",
        "record_kind": "canonical_turn_candidates",
        "source_record": {
            "dataset": record["source"]["dataset"],
            "record_id": record["source"]["record_id"],
            "file_sha256": record["source"]["file_sha256"],
        },
        "source_rights": record["rights"],
        "candidate_count": len(windows),
        "candidates": [window.as_dict() for window in windows],
        "target_semantics": {
            "kind": "synthetic_directional_proxy",
            "statement": (
                "A future target may be placed along observed final facing. "
                "This does not claim the source performer attended to a real object."
            ),
        },
    }
    write_json(path / "turn_candidates.json", result)
    return result


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Mine target-turn windows from a canonical CutSceneAI motion record."
    )
    parser.add_argument("record_dir")
    parser.add_argument("--min-heading-deg", type=float, default=30.0)
    parser.add_argument("--max-heading-deg", type=float, default=150.0)
    parser.add_argument("--max-displacement-m", type=float, default=1.0)
    args = parser.parse_args()

    result = mine_canonical_record(
        args.record_dir,
        config=TurnMiningConfig(
            min_heading_change_deg=args.min_heading_deg,
            max_heading_change_deg=args.max_heading_deg,
            max_horizontal_displacement_m=args.max_displacement_m,
        ),
    )
    print(
        json.dumps(
            {
                "candidate_count": result["candidate_count"],
                "source_record": result["source_record"],
                "target_semantics": result["target_semantics"]["kind"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
