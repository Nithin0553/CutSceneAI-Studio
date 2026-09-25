from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

from tools.render_canonical_motion_preview import load_timeline, render_html


def test_canonical_motion_preview_reads_xyz_and_renders_html(tmp_path: Path) -> None:
    bundle = tmp_path / "performance.bundle.zip"
    package = {
        "fps": 24,
        "duration_frames": 2,
        "body_tracks": [
            {
                "semantic_id": "body:test",
                "actor_binding_id": "actor:test",
                "start_frame": 0,
                "end_frame": 2,
                "artifact": {"relative_path": "body/test.motion.json"},
            }
        ],
    }
    sample_positions = [
        {"x": float(i), "y": float(i % 3), "z": float(-i)}
        for i in range(22)
    ]
    motion = {
        "joint_names": [f"j{i}" for i in range(22)],
        "parent_indices": [-1] + list(range(21)),
        "samples": [
            {"frame_index": 0, "joint_positions": sample_positions},
            {"frame_index": 1, "joint_positions": sample_positions},
        ],
    }
    with ZipFile(bundle, "w") as archive:
        archive.writestr("performance.package.json", json.dumps(package))
        archive.writestr("body/test.motion.json", json.dumps(motion))

    data = load_timeline(bundle, None)

    assert data["actor"] == "actor:test"
    assert data["fps"] == 24
    assert len(data["frames"]) == 2
    rendered = render_html(data)
    assert "CutSceneAI Canonical Motion Preview" in rendered
    assert "Front (X/Y)" in rendered
    assert "Side (Z/Y)" in rendered
    assert "Top (X/Z)" in rendered
    assert "body:test" in rendered
