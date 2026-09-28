from __future__ import annotations

import numpy as np

from .geometry import yaw_6d


def build_guard_turn_scene(
    *,
    family_id: str,
    initial_yaw: float,
    bearing: float,
    target_distance_m: float,
) -> dict[str, object]:
    actor_position = np.array([0.0, 0.0, 0.0], dtype=np.float32)
    target_direction = np.array(
        [
            -np.sin(initial_yaw + bearing),
            0.0,
            -np.cos(initial_yaw + bearing),
        ],
        dtype=np.float32,
    )
    door_position = actor_position + target_direction * target_distance_m
    door_center = door_position + np.array([0.0, 1.0, 0.0], dtype=np.float32)

    return {
        "contract_version": "0.1.0",
        "scene_id": family_id,
        "entities": [
            {
                "entity_id": "guard",
                "semantic_type": "character",
                "role": "performer",
                "active": True,
                "dynamic": True,
                "transform": {
                    "position_m": actor_position.tolist(),
                    "rotation_6d_columns": yaw_6d(initial_yaw).tolist(),
                    "scale": [1.0, 1.0, 1.0],
                },
            },
            {
                "entity_id": "door",
                "semantic_type": "door",
                "role": "target",
                "active": True,
                "dynamic": False,
                "transform": {
                    "position_m": door_position.tolist(),
                    "rotation_6d_columns": yaw_6d(0.0).tolist(),
                    "scale": [1.0, 1.0, 1.0],
                },
                "bounds": {
                    "center_m": door_center.tolist(),
                    "extents_m": [0.5, 1.0, 0.1],
                },
                "target_points": [
                    {
                        "point_id": "visual-center",
                        "kind": "look",
                        "position_m": door_center.tolist(),
                    }
                ],
                "affordances": ["look_target"],
            },
        ],
        "relationships": [
            {
                "source_entity_id": "guard",
                "target_entity_id": "door",
                "relation": "attention_target",
            }
        ],
        "support_surfaces": [
            {
                "surface_id": "floor-main",
                "kind": "ground",
                "point_m": [0.0, 0.0, 0.0],
                "normal": [0.0, 1.0, 0.0],
                "walkable": True,
            }
        ],
    }
