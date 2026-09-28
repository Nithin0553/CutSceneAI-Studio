from __future__ import annotations

import math

import numpy as np
import pytest

from cutsceneai_training.geometry import yaw_6d
from cutsceneai_training.turn_mining import TurnMiningConfig, mine_turn_windows


def _rotation_sequence(yaws: np.ndarray) -> np.ndarray:
    return np.stack([yaw_6d(float(value)) for value in yaws], axis=0)


def test_mines_single_stable_ninety_degree_turn() -> None:
    yaws = np.concatenate(
        [
            np.zeros(8),
            np.linspace(0.0, math.pi / 2.0, 31),
            np.full(8, math.pi / 2.0),
        ]
    )
    roots = np.zeros((yaws.shape[0], 3), dtype=np.float32)

    windows = mine_turn_windows(
        root_position_m=roots,
        root_rotation_6d_columns=_rotation_sequence(yaws),
        config=TurnMiningConfig(context_frames=4),
    )

    assert len(windows) == 1
    window = windows[0]
    assert window.heading_change_deg == pytest.approx(90.0, abs=0.2)
    assert window.horizontal_displacement_m == pytest.approx(0.0)
    assert window.direction_consistency == pytest.approx(1.0, abs=1e-5)


def test_rejects_turn_with_excessive_translation() -> None:
    yaws = np.concatenate(
        [
            np.zeros(8),
            np.linspace(0.0, math.pi / 2.0, 31),
            np.full(8, math.pi / 2.0),
        ]
    )
    roots = np.zeros((yaws.shape[0], 3), dtype=np.float32)
    roots[:, 0] = np.linspace(0.0, 2.0, yaws.shape[0])

    windows = mine_turn_windows(
        root_position_m=roots,
        root_rotation_6d_columns=_rotation_sequence(yaws),
        config=TurnMiningConfig(
            context_frames=4,
            max_horizontal_displacement_m=0.5,
        ),
    )

    assert windows == []


def test_rejects_small_heading_change() -> None:
    yaws = np.concatenate(
        [
            np.zeros(8),
            np.linspace(0.0, math.radians(12.0), 20),
            np.full(8, math.radians(12.0)),
        ]
    )
    roots = np.zeros((yaws.shape[0], 3), dtype=np.float32)

    windows = mine_turn_windows(
        root_position_m=roots,
        root_rotation_6d_columns=_rotation_sequence(yaws),
    )

    assert windows == []


def test_negative_heading_change_is_right_turn() -> None:
    yaws = np.concatenate(
        [
            np.zeros(8),
            np.linspace(0.0, -math.pi / 2.0, 31),
            np.full(8, -math.pi / 2.0),
        ]
    )
    roots = np.zeros((yaws.shape[0], 3), dtype=np.float32)

    windows = mine_turn_windows(
        root_position_m=roots,
        root_rotation_6d_columns=_rotation_sequence(yaws),
        config=TurnMiningConfig(context_frames=4),
    )

    assert len(windows) == 1
    assert windows[0].direction == "right"
    assert windows[0].heading_change_deg == pytest.approx(-90.0, abs=0.2)
