from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from zipfile import ZipFile

MANIFEST = "performance.package.json"

STATIONARY_HINTS = ("stop", "listen", "hold", "idle", "stand")
TURN_HINTS = ("turn", "pivot", "rotate")


def _v(a: list[float], b: list[float]) -> list[float]:
    return [a[0]-b[0], a[1]-b[1], a[2]-b[2]]


def _length(v: list[float]) -> float:
    return math.sqrt(v[0]*v[0] + v[1]*v[1] + v[2]*v[2])


def _distance(a: list[float], b: list[float]) -> float:
    return _length(_v(a, b))


def _horizontal_distance(a: list[float], b: list[float]) -> float:
    dx, dz = a[0]-b[0], a[2]-b[2]
    return math.sqrt(dx*dx + dz*dz)


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered)-1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return ordered[lo]
    t = pos-lo
    return ordered[lo]*(1-t) + ordered[hi]*t


def _heading(frame: list[list[float]], names: list[str]) -> float | None:
    try:
        pelvis = frame[names.index("pelvis")]
        left = frame[names.index("left_hip")]
        right = frame[names.index("right_hip")]
        spine = frame[names.index("spine1")]
    except ValueError:
        return None

    x = _v(left, right)
    up = _v(spine, pelvis)
    xl, ul = _length(x), _length(up)
    if xl < 1e-9 or ul < 1e-9:
        return None
    x = [c/xl for c in x]
    dot = sum(up[i]*x[i] for i in range(3))
    up = [up[i]-dot*x[i] for i in range(3)]
    ul = _length(up)
    if ul < 1e-9:
        return None
    up = [c/ul for c in up]
    # right-handed forward = x cross up
    f = [
        x[1]*up[2]-x[2]*up[1],
        x[2]*up[0]-x[0]*up[2],
        x[0]*up[1]-x[1]*up[0],
    ]
    fl = math.sqrt(f[0]*f[0] + f[2]*f[2])
    if fl < 1e-9:
        return None
    return math.atan2(f[0]/fl, f[2]/fl)


def _angle_delta_deg(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    d = (b-a+math.pi) % (2*math.pi) - math.pi
    return math.degrees(d)


def load_actor_timeline(bundle_path: Path, actor: str | None) -> dict[str, object]:
    with ZipFile(bundle_path) as archive:
        package = json.loads(archive.read(MANIFEST))
        tracks = list(package.get("body_tracks") or [])
        if not tracks:
            raise ValueError("Performance bundle contains no body tracks.")
        actors = sorted({str(t["actor_binding_id"]) for t in tracks})
        actor = actor or actors[0]
        selected = sorted(
            [t for t in tracks if t["actor_binding_id"] == actor],
            key=lambda t: (int(t["start_frame"]), str(t["semantic_id"])),
        )
        if not selected:
            raise ValueError(f"No body tracks for {actor!r}; available: {actors}")

        rows: list[dict[str, object]] = []
        names = parents = None
        for track in selected:
            motion = json.loads(
                archive.read(str(track["artifact"]["relative_path"]))
            )
            names = names or list(motion["joint_names"])
            parents = parents or [int(v) for v in motion["parent_indices"]]
            for sample in motion["samples"]:
                positions = sample.get("joint_positions")
                if positions is None:
                    raise ValueError(
                        f"Track {track['semantic_id']} has no canonical joint_positions."
                    )
                rows.append(
                    {
                        "timeline_frame": int(track["start_frame"]) + int(sample["frame_index"]),
                        "phase": str(track["semantic_id"]),
                        "positions": [
                            [float(p["x"]), float(p["y"]), float(p["z"])]
                            for p in positions
                        ],
                    }
                )

    rows.sort(key=lambda r: int(r["timeline_frame"]))
    if not rows:
        raise ValueError("No canonical XYZ frames found.")
    return {
        "actor": actor,
        "fps": int(package["fps"]),
        "joint_names": names,
        "parents": parents,
        "rows": rows,
    }


def diagnose(bundle_path: Path, actor: str | None = None) -> dict[str, object]:
    data = load_actor_timeline(bundle_path, actor)
    fps = int(data["fps"])
    names = list(data["joint_names"])
    parents = list(data["parents"])
    rows = list(data["rows"])
    frames = [r["positions"] for r in rows]

    bone_stats = []
    max_bone_rel_dev = 0.0
    for joint, parent in enumerate(parents):
        if parent < 0:
            continue
        values = [_distance(f[joint], f[parent]) for f in frames]
        median = statistics.median(values)
        max_dev = (
            max(abs(v-median) for v in values) / median
            if median > 1e-9
            else 0.0
        )
        max_bone_rel_dev = max(max_bone_rel_dev, max_dev)
        bone_stats.append(
            {
                "joint": names[joint],
                "parent": names[parent],
                "median_length_m": median,
                "max_relative_deviation": max_dev,
            }
        )

    pelvis = names.index("pelvis")
    root_speeds = [
        _distance(frames[i][pelvis], frames[i-1][pelvis]) * fps
        for i in range(1, len(frames))
    ]
    max_root_speed = max(root_speeds, default=0.0)

    phase_names = []
    for row in rows:
        phase = str(row["phase"])
        if not phase_names or phase_names[-1] != phase:
            phase_names.append(phase)

    phases = []
    for phase in phase_names:
        idx = [i for i, r in enumerate(rows) if r["phase"] == phase]
        first, last = idx[0], idx[-1]
        root_net = _distance(frames[last][pelvis], frames[first][pelvis])
        root_path = sum(
            _distance(frames[i][pelvis], frames[i-1][pelvis])
            for i in range(first+1, last+1)
        )
        heading_delta = _angle_delta_deg(
            _heading(frames[first], names),
            _heading(frames[last], names),
        )
        lower = phase.lower()
        expected = (
            "stationary"
            if any(token in lower for token in STATIONARY_HINTS)
            else "turn"
            if any(token in lower for token in TURN_HINTS)
            else "unspecified"
        )
        phases.append(
            {
                "phase": phase,
                "start_frame": int(rows[first]["timeline_frame"]),
                "end_frame": int(rows[last]["timeline_frame"]),
                "expected_motion_class": expected,
                "root_net_displacement_m": root_net,
                "root_path_length_m": root_path,
                "heading_change_deg": heading_delta,
            }
        )

    boundary_metrics = []
    max_boundary_speed_jump = 0.0
    for i in range(1, len(rows)-1):
        if rows[i-1]["phase"] == rows[i]["phase"]:
            continue
        before = _distance(frames[i-1][pelvis], frames[i-2][pelvis]) * fps if i >= 2 else 0.0
        after = _distance(frames[i+1][pelvis], frames[i][pelvis]) * fps
        jump = abs(after-before)
        max_boundary_speed_jump = max(max_boundary_speed_jump, jump)
        boundary_metrics.append(
            {
                "frame": int(rows[i]["timeline_frame"]),
                "from_phase": rows[i-1]["phase"],
                "to_phase": rows[i]["phase"],
                "previous_speed_mps": before,
                "next_speed_mps": after,
                "speed_jump_mps": jump,
            }
        )

    foot_metrics = {}
    for foot_name in ("left_foot", "right_foot"):
        if foot_name not in names:
            continue
        ji = names.index(foot_name)
        ys = [f[ji][1] for f in frames]
        floor = _percentile(ys, 0.05)
        slide_speeds = []
        contact_frames = 0
        for i in range(1, len(frames)):
            vertical_speed = abs(frames[i][ji][1]-frames[i-1][ji][1]) * fps
            near_ground = frames[i][ji][1] <= floor + 0.04
            if near_ground and vertical_speed <= 0.12:
                contact_frames += 1
                slide_speeds.append(
                    _horizontal_distance(frames[i][ji], frames[i-1][ji]) * fps
                )
        foot_metrics[foot_name] = {
            "estimated_floor_y_m": floor,
            "heuristic_contact_frames": contact_frames,
            "contact_horizontal_speed_p95_mps": _percentile(slide_speeds, 0.95),
            "contact_horizontal_speed_max_mps": max(slide_speeds, default=0.0),
        }

    issues = []
    if max_bone_rel_dev > 0.01:
        issues.append(
            {
                "severity": "error",
                "code": "bone_length_instability",
                "message": "Canonical skeleton bone lengths vary by more than 1%.",
            }
        )
    for phase in phases:
        if (
            phase["expected_motion_class"] == "stationary"
            and phase["root_net_displacement_m"] > 0.20
        ):
            issues.append(
                {
                    "severity": "warning",
                    "code": "stationary_phase_root_travel",
                    "phase": phase["phase"],
                    "message": "A stationary semantic phase travels more than 0.20 m.",
                }
            )
    if max_boundary_speed_jump > 0.75:
        issues.append(
            {
                "severity": "warning",
                "code": "large_phase_boundary_speed_jump",
                "message": "A phase transition changes pelvis speed by more than 0.75 m/s.",
            }
        )
    for foot_name, metric in foot_metrics.items():
        if (
            metric["heuristic_contact_frames"] >= 3
            and metric["contact_horizontal_speed_p95_mps"] > 0.25
        ):
            issues.append(
                {
                    "severity": "warning",
                    "code": "possible_foot_slide",
                    "foot": foot_name,
                    "message": "Near-ground low-vertical-speed frames show high horizontal foot speed.",
                }
            )

    return {
        "diagnostic_version": "0.1.0",
        "bundle": str(bundle_path),
        "actor": data["actor"],
        "fps": fps,
        "frame_count": len(frames),
        "summary": {
            "max_bone_relative_deviation": max_bone_rel_dev,
            "max_root_speed_mps": max_root_speed,
            "max_phase_boundary_speed_jump_mps": max_boundary_speed_jump,
            "issue_count": len(issues),
            "error_count": sum(i["severity"] == "error" for i in issues),
            "warning_count": sum(i["severity"] == "warning" for i in issues),
        },
        "issues": issues,
        "phase_metrics": phases,
        "boundary_metrics": boundary_metrics,
        "foot_contact_heuristics": foot_metrics,
        "bone_metrics": bone_stats,
        "notes": [
            "Foot contacts are inferred heuristically because the current CutSceneAI bundle preserves HumanML XYZ but not the original HumanML contact channels.",
            "This diagnostic evaluates canonical motion before engine retargeting.",
        ],
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run-id", required=True)
    p.add_argument("--actor")
    p.add_argument("--run-root", default=".cutsceneai-studio/runs/performance")
    p.add_argument("--output")
    a = p.parse_args()
    bundle = Path(a.run_root) / a.run_id / "performance.bundle.zip"
    if not bundle.is_file():
        raise SystemExit(f"Missing bundle: {bundle}")
    report = diagnose(bundle, a.actor)
    output = (
        Path(a.output)
        if a.output
        else bundle.parent / "canonical-motion-diagnostic.json"
    )
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    print(str(output.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
