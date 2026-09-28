from __future__ import annotations


def build_guard_turn_choreography(
    *,
    frame_count: int,
    gaze_start: int,
    head_complete: int,
    root_start: int,
    turn_end: int,
) -> dict[str, object]:
    return {
        "contract_version": "0.1.0",
        "duration_frames": frame_count,
        "events": [
            {
                "event_id": "notice-target",
                "frame": 0,
                "event_type": "target_notice",
                "subject_entity_id": "guard",
                "target_entity_id": "door",
            }
        ],
        "phases": [
            {
                "phase_id": "acquire-door",
                "actor_entity_id": "guard",
                "phase_type": "gaze_transition",
                "start_frame": gaze_start,
                "end_frame": head_complete,
                "priority": 80,
                "channels": ["head", "gaze"],
                "target_entity_id": "door",
                "coordination_group_id": "turn-to-door",
            },
            {
                "phase_id": "turn-to-door",
                "actor_entity_id": "guard",
                "phase_type": "orientation_change",
                "start_frame": root_start,
                "end_frame": turn_end,
                "priority": 90,
                "channels": ["root", "lower_body", "torso", "head"],
                "target_entity_id": "door",
                "coordination_group_id": "turn-to-door",
            },
            {
                "phase_id": "hold-door",
                "actor_entity_id": "guard",
                "phase_type": "hold",
                "start_frame": turn_end,
                "end_frame": frame_count,
                "priority": 60,
                "channels": ["root", "lower_body", "head", "gaze"],
                "target_entity_id": "door",
                "coordination_group_id": "turn-to-door",
            },
        ],
        "constraints": [
            {
                "constraint_id": "face-door",
                "constraint_type": "body_facing",
                "actor_entity_id": "guard",
                "start_frame": max(0, turn_end - 1),
                "end_frame": frame_count,
                "strength": "hard",
                "weight": 1.0,
                "target_entity_id": "door",
                "tolerance_degrees": 5.0,
            },
            {
                "constraint_id": "look-door",
                "constraint_type": "gaze_target",
                "actor_entity_id": "guard",
                "start_frame": head_complete,
                "end_frame": frame_count,
                "strength": "hard",
                "weight": 1.0,
                "target_entity_id": "door",
                "target_point_kind": "look",
                "tolerance_degrees": 3.0,
            },
            {
                "constraint_id": "support-during-turn",
                "constraint_type": "support_contact",
                "actor_entity_id": "guard",
                "start_frame": root_start,
                "end_frame": turn_end,
                "strength": "hard",
                "weight": 1.0,
                "contact_requirement": "at_least_one_foot",
            },
        ],
        "coordination_groups": [
            {
                "coordination_group_id": "turn-to-door",
                "member_phase_ids": [
                    "acquire-door",
                    "turn-to-door",
                    "hold-door",
                ],
            }
        ],
    }
