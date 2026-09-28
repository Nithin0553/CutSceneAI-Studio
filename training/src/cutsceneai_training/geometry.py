from __future__ import annotations

import math

import numpy as np


FPS = 30
JOINT_NAMES = (
    "pelvis",
    "left_hip",
    "right_hip",
    "spine1",
    "left_knee",
    "right_knee",
    "spine2",
    "left_ankle",
    "right_ankle",
    "spine3",
    "left_foot",
    "right_foot",
    "neck",
    "left_collar",
    "right_collar",
    "head",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
)
JOINT_INDEX = {name: index for index, name in enumerate(JOINT_NAMES)}


def rotation_x(angle: float) -> np.ndarray:
    c = math.cos(angle)
    s = math.sin(angle)
    return np.array(
        [[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]],
        dtype=np.float64,
    )


def rotation_y(angle: float) -> np.ndarray:
    c = math.cos(angle)
    s = math.sin(angle)
    return np.array(
        [[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]],
        dtype=np.float64,
    )


def rotation_6d(matrix: np.ndarray) -> np.ndarray:
    return np.array(
        [
            matrix[0, 0],
            matrix[1, 0],
            matrix[2, 0],
            matrix[0, 1],
            matrix[1, 1],
            matrix[2, 1],
        ],
        dtype=np.float32,
    )


def yaw_6d(angle: float) -> np.ndarray:
    return rotation_6d(rotation_y(angle))


def yaw_pitch_6d(*, yaw: float = 0.0, pitch: float = 0.0) -> np.ndarray:
    return rotation_6d(rotation_y(yaw) @ rotation_x(pitch))


def forward_from_yaw(angle: float) -> np.ndarray:
    return (
        rotation_y(angle) @ np.array([0.0, 0.0, -1.0], dtype=np.float64)
    ).astype(np.float32)


def smoothstep01(value: float) -> float:
    t = min(1.0, max(0.0, value))
    return t * t * (3.0 - 2.0 * t)
