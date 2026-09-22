import math

import pytest

from cutsceneai_performance import (
    HUMANML_POSITION_CONVERSION_METHOD,
    HUMANML_SOURCE_FPS,
    HumanMLXYZMotion,
    humanml_xyz_to_canonical,
)


RAW_OFFSETS = (
    (0.0, 0.0, 0.0),
    (1.0, 0.0, 0.0),
    (-1.0, 0.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, -1.0, 0.0),
    (0.0, -1.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, -1.0, 0.0),
    (0.0, -1.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, 0.0, 1.0),
    (0.0, 0.0, 1.0),
    (0.0, 1.0, 0.0),
    (1.0, 0.0, 0.0),
    (-1.0, 0.0, 0.0),
    (0.0, 0.0, 1.0),
    (0.0, -1.0, 0.0),
    (0.0, -1.0, 0.0),
    (0.0, -1.0, 0.0),
    (0.0, -1.0, 0.0),
    (0.0, -1.0, 0.0),
    (0.0, -1.0, 0.0),
)

PARENTS = (-1, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9, 9, 12, 13, 14, 16, 17, 18, 19)


def _rest_positions() -> list[list[float]]:
    positions: list[list[float]] = []
    for index, offset in enumerate(RAW_OFFSETS):
        parent = PARENTS[index]
        if parent < 0:
            positions.append([0.0, 0.0, 0.0])
        else:
            source = positions[parent]
            positions.append(
                [
                    source[0] + offset[0],
                    source[1] + offset[1],
                    source[2] + offset[2],
                ]
            )
    return positions


def _yaw(frame: list[list[float]], radians: float) -> list[list[float]]:
    cosine = math.cos(radians)
    sine = math.sin(radians)
    return [
        [
            cosine * x + sine * z,
            y,
            -sine * x + cosine * z,
        ]
        for x, y, z in frame
    ]


def test_humanml_rest_pose_becomes_identity_local_rotations() -> None:
    rest = _rest_positions()
    artifact = humanml_xyz_to_canonical(
        HumanMLXYZMotion(frame_count=2, positions=[rest, rest])
    )

    assert HUMANML_SOURCE_FPS == 20
    assert HUMANML_POSITION_CONVERSION_METHOD.endswith("v0.2")
    assert artifact.frame_count == 2
    assert artifact.samples[0].root_translation.model_dump() == {
        "x": 0.0,
        "y": 0.0,
        "z": 0.0,
    }
    for rotation in artifact.samples[0].joint_rotations:
        assert rotation.x == pytest.approx(0.0, abs=1e-7)
        assert rotation.y == pytest.approx(0.0, abs=1e-7)
        assert rotation.z == pytest.approx(0.0, abs=1e-7)
        assert rotation.w == pytest.approx(1.0, abs=1e-7)


def test_humanml_whole_body_yaw_is_carried_by_pelvis_not_counter_rotated_limbs() -> (
    None
):
    rest = _rest_positions()
    turned = _yaw(rest, math.pi / 2.0)
    artifact = humanml_xyz_to_canonical(
        HumanMLXYZMotion(frame_count=2, positions=[rest, turned])
    )

    pelvis = artifact.samples[1].joint_rotations[0]
    assert abs(pelvis.y) == pytest.approx(math.sqrt(0.5), abs=1e-6)
    assert abs(pelvis.w) == pytest.approx(math.sqrt(0.5), abs=1e-6)
    for rotation in artifact.samples[1].joint_rotations[1:]:
        assert rotation.x == pytest.approx(0.0, abs=1e-6)
        assert rotation.y == pytest.approx(0.0, abs=1e-6)
        assert rotation.z == pytest.approx(0.0, abs=1e-6)
        assert abs(rotation.w) == pytest.approx(1.0, abs=1e-6)


def test_humanml_root_translation_is_rebased_and_z_reflected() -> None:
    rest = _rest_positions()
    moved = [[x + 1.5, y + 0.25, z + 2.0] for x, y, z in rest]
    artifact = humanml_xyz_to_canonical(
        HumanMLXYZMotion(frame_count=2, positions=[rest, moved])
    )

    assert artifact.samples[1].root_translation.model_dump() == {
        "x": 1.5,
        "y": 0.25,
        "z": -2.0,
    }


def test_humanml_leg_swing_produces_non_identity_hip_rotation() -> None:
    rest = _rest_positions()
    moved = [list(position) for position in rest]
    moved[4] = [rest[4][0], rest[4][1], rest[4][2] + 0.5]
    moved[7] = [rest[7][0], rest[7][1], rest[7][2] + 0.5]
    moved[10] = [rest[10][0], rest[10][1], rest[10][2] + 0.5]

    artifact = humanml_xyz_to_canonical(
        HumanMLXYZMotion(frame_count=2, positions=[rest, moved])
    )
    left_hip = artifact.samples[1].joint_rotations[1]

    assert abs(left_hip.x) > 0.01 or abs(left_hip.z) > 0.01


def test_humanml_rejects_nonfinite_and_wrong_joint_count() -> None:
    rest = _rest_positions()
    bad_count = rest[:-1]
    with pytest.raises(ValueError, match="exactly 22"):
        HumanMLXYZMotion(frame_count=1, positions=[bad_count])

    nonfinite = [list(position) for position in rest]
    nonfinite[0][0] = float("nan")
    with pytest.raises(ValueError, match=r"(?:not finite|finite number)"):
        HumanMLXYZMotion(frame_count=1, positions=[nonfinite])
