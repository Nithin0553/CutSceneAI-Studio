from __future__ import annotations

import math

import numpy as np

from .geometry import JOINT_INDEX, JOINT_NAMES, forward_from_yaw, rotation_6d, smoothstep01, yaw_6d, yaw_pitch_6d


def build_turn_reference(
    *,
    initial_yaw: float,
    bearing: float,
    turn_frames: int,
    hold_frames: int,
    support_foot: str,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray], dict[str, int]]:
    frame_count = turn_frames + hold_frames

    root_position = np.zeros((frame_count, 3), dtype=np.float32)
    root_rotation = np.zeros((frame_count, 6), dtype=np.float32)
    joint_rotations = np.zeros((frame_count, len(JOINT_NAMES), 6), dtype=np.float32)

    left_contact = np.ones(frame_count, dtype=np.uint8)
    right_contact = np.ones(frame_count, dtype=np.uint8)
    contact_available = np.ones(frame_count, dtype=np.uint8)
    contact_confidence = np.ones(frame_count, dtype=np.float32)

    gaze_active = np.zeros(frame_count, dtype=np.uint8)
    gaze_active_available = np.ones(frame_count, dtype=np.uint8)
    head_direction = np.zeros((frame_count, 3), dtype=np.float32)
    head_direction_available = np.ones(frame_count, dtype=np.uint8)

    gaze_start = max(1, int(round(turn_frames * 0.10)))
    head_complete = max(gaze_start + 1, int(round(turn_frames * 0.55)))
    root_start = max(1, int(round(turn_frames * 0.25)))
    moving_foot_start = max(root_start, int(round(turn_frames * 0.28)))
    moving_foot_end = max(moving_foot_start + 1, int(round(turn_frames * 0.72)))

    identity = rotation_6d(np.eye(3))
    desired_yaw = initial_yaw + bearing

    for frame in range(frame_count):
        turn_t = min(frame, turn_frames - 1) / max(turn_frames - 1, 1)

        head_progress = smoothstep01(frame / max(head_complete - 1, 1))
        torso_progress = smoothstep01((turn_t - 0.10) / 0.68)
        root_progress = smoothstep01((turn_t - 0.25) / 0.75)

        root_yaw = initial_yaw + bearing * root_progress
        torso_world_yaw = initial_yaw + bearing * torso_progress
        head_world_yaw = initial_yaw + bearing * head_progress

        root_rotation[frame] = yaw_6d(root_yaw)
        joint_rotations[frame, :, :] = identity

        torso_delta = torso_world_yaw - root_yaw
        head_delta = head_world_yaw - torso_world_yaw

        joint_rotations[frame, JOINT_INDEX["spine1"]] = yaw_pitch_6d(
            yaw=torso_delta * 0.20
        )
        joint_rotations[frame, JOINT_INDEX["spine2"]] = yaw_pitch_6d(
            yaw=torso_delta * 0.30
        )
        joint_rotations[frame, JOINT_INDEX["spine3"]] = yaw_pitch_6d(
            yaw=torso_delta * 0.50
        )
        joint_rotations[frame, JOINT_INDEX["neck"]] = yaw_pitch_6d(
            yaw=head_delta * 0.35
        )
        joint_rotations[frame, JOINT_INDEX["head"]] = yaw_pitch_6d(
            yaw=head_delta * 0.65
        )

        pivot = math.sin(math.pi * min(1.0, root_progress))
        knee_bend = 0.18 * pivot
        ankle_counter = -0.08 * pivot

        moving_knee = "right_knee" if support_foot == "left" else "left_knee"
        moving_ankle = "right_ankle" if support_foot == "left" else "left_ankle"
        joint_rotations[frame, JOINT_INDEX[moving_knee]] = yaw_pitch_6d(
            pitch=knee_bend
        )
        joint_rotations[frame, JOINT_INDEX[moving_ankle]] = yaw_pitch_6d(
            pitch=ankle_counter
        )

        shoulder_counter = -0.08 * torso_delta
        joint_rotations[frame, JOINT_INDEX["left_shoulder"]] = yaw_pitch_6d(
            yaw=shoulder_counter
        )
        joint_rotations[frame, JOINT_INDEX["right_shoulder"]] = yaw_pitch_6d(
            yaw=shoulder_counter
        )

        if moving_foot_start <= frame < moving_foot_end:
            if support_foot == "left":
                right_contact[frame] = 0
            else:
                left_contact[frame] = 0

        if frame >= gaze_start:
            gaze_active[frame] = 1

        head_direction[frame] = forward_from_yaw(head_world_yaw)

    final_forward = forward_from_yaw(desired_yaw)
    if not np.allclose(
        final_forward,
        forward_from_yaw(initial_yaw + bearing),
        atol=1e-6,
    ):
        raise RuntimeError("Final facing construction is inconsistent.")

    body = {
        "root_position_m": root_position,
        "root_rotation_6d_columns": root_rotation,
        "joint_rotations_6d_columns": joint_rotations,
    }
    contact_gaze = {
        "left_foot_contact": left_contact,
        "right_foot_contact": right_contact,
        "left_contact_available": contact_available,
        "right_contact_available": contact_available.copy(),
        "left_contact_confidence": contact_confidence,
        "right_contact_confidence": contact_confidence.copy(),
        "gaze_active": gaze_active,
        "gaze_active_available": gaze_active_available,
        "head_direction_world": head_direction,
        "head_direction_available": head_direction_available,
    }
    timing = {
        "frame_count": frame_count,
        "gaze_start": gaze_start,
        "head_complete": head_complete,
        "root_start": root_start,
        "moving_foot_start": moving_foot_start,
        "moving_foot_end": moving_foot_end,
        "turn_end": turn_frames,
    }
    return body, contact_gaze, timing
