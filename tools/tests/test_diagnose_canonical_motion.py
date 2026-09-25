from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

from tools.diagnose_canonical_motion import diagnose


def _positions(offset: float) -> list[dict[str, float]]:
    pts = []
    for index in range(22):
        pts.append(
            {
                "x": offset + (index % 2) * 0.1,
                "y": 1.0 + index * 0.01,
                "z": (index % 3) * 0.05,
            }
        )
    return pts


def test_diagnose_canonical_motion_reports_geometry_and_phase_metrics(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "performance.bundle.zip"
    package = {
        "fps": 20,
        "duration_frames": 4,
        "body_tracks": [
            {
                "semantic_id": "body:guard_walk",
                "actor_binding_id": "actor:guard",
                "start_frame": 0,
                "end_frame": 2,
                "artifact": {"relative_path": "body/walk.motion.json"},
            },
            {
                "semantic_id": "body:guard_stop",
                "actor_binding_id": "actor:guard",
                "start_frame": 2,
                "end_frame": 4,
                "artifact": {"relative_path": "body/stop.motion.json"},
            },
        ],
    }
    names = [
        "pelvis","left_hip","right_hip","spine1","left_knee","right_knee",
        "spine2","left_ankle","right_ankle","spine3","left_foot","right_foot",
        "neck","left_collar","right_collar","head","left_shoulder",
        "right_shoulder","left_elbow","right_elbow","left_wrist","right_wrist",
    ]
    parents = [-1,0,0,0,1,2,3,4,5,6,7,8,9,9,9,12,13,14,16,17,18,19]

    walk = {
        "joint_names": names,
        "parent_indices": parents,
        "samples": [
            {"frame_index": 0, "joint_positions": _positions(0.0)},
            {"frame_index": 1, "joint_positions": _positions(0.02)},
        ],
    }
    stop = {
        "joint_names": names,
        "parent_indices": parents,
        "samples": [
            {"frame_index": 0, "joint_positions": _positions(0.04)},
            {"frame_index": 1, "joint_positions": _positions(0.04)},
        ],
    }
    with ZipFile(bundle, "w") as archive:
        archive.writestr("performance.package.json", json.dumps(package))
        archive.writestr("body/walk.motion.json", json.dumps(walk))
        archive.writestr("body/stop.motion.json", json.dumps(stop))

    report = diagnose(bundle, "actor:guard")

    assert report["actor"] == "actor:guard"
    assert report["frame_count"] == 4
    assert report["summary"]["max_bone_relative_deviation"] < 1e-9
    assert len(report["phase_metrics"]) == 2
    stop_metric = next(
        item for item in report["phase_metrics"]
        if item["phase"] == "body:guard_stop"
    )
    assert stop_metric["expected_motion_class"] == "stationary"
    assert stop_metric["root_net_displacement_m"] == 0.0
    assert "left_foot" in report["foot_contact_heuristics"]
    assert report["notes"]
