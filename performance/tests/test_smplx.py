import math

import pytest

from cutsceneai_performance import (
    CANONICAL_HUMANOID_JOINTS,
    SMPLXAxisAngleMotion,
    smplx_axis_angle_to_canonical,
)


def _zeros() -> list[float]:
    return [0.0] * 63


def test_smplx_joint_order_matches_canonical_profile() -> None:
    assert len(CANONICAL_HUMANOID_JOINTS) == 22
    assert CANONICAL_HUMANOID_JOINTS[:4] == (
        "pelvis",
        "left_hip",
        "right_hip",
        "spine1",
    )


def test_smplx_identity_motion_converts_to_reference_offsets() -> None:
    motion = SMPLXAxisAngleMotion(
        fps=30,
        source_forward_axis="-z",
        global_orient=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
        body_pose=[_zeros(), _zeros()],
        transl=[[10.0, 2.0, 5.0], [11.0, 2.5, 3.0]],
    )

    artifact = smplx_axis_angle_to_canonical(motion)

    assert artifact.fps == 30
    assert artifact.frame_count == 2
    assert artifact.samples[0].root_translation.model_dump() == {
        "x": 0.0,
        "y": 0.0,
        "z": 0.0,
    }
    assert artifact.samples[1].root_translation.model_dump() == {
        "x": 1.0,
        "y": 0.5,
        "z": -2.0,
    }
    assert all(item.w == 1.0 for item in artifact.samples[0].joint_rotations)


def test_plus_z_source_rotates_translation_into_cutsceneai_forward() -> None:
    motion = SMPLXAxisAngleMotion(
        fps=24,
        source_forward_axis="+z",
        global_orient=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
        body_pose=[_zeros(), _zeros()],
        transl=[[0.0, 0.0, 0.0], [1.0, 0.0, 2.0]],
    )

    artifact = smplx_axis_angle_to_canonical(motion)

    assert artifact.samples[1].root_translation.model_dump() == {
        "x": -1.0,
        "y": 0.0,
        "z": -2.0,
    }


def test_axis_angle_becomes_unit_quaternion() -> None:
    pose = _zeros()
    pose[0:3] = [math.pi / 2.0, 0.0, 0.0]
    motion = SMPLXAxisAngleMotion(
        fps=24,
        source_forward_axis="-z",
        global_orient=[[0.0, 0.0, 0.0]],
        body_pose=[pose],
        transl=[[0.0, 0.0, 0.0]],
    )

    artifact = smplx_axis_angle_to_canonical(motion)
    hip = artifact.samples[0].joint_rotations[1]

    assert hip.x == pytest.approx(math.sqrt(0.5))
    assert hip.y == pytest.approx(0.0)
    assert hip.z == pytest.approx(0.0)
    assert hip.w == pytest.approx(math.sqrt(0.5))


def test_smplx_shape_validation_rejects_wrong_body_width() -> None:
    with pytest.raises(ValueError, match="63 values"):
        SMPLXAxisAngleMotion(
            fps=24,
            global_orient=[[0.0, 0.0, 0.0]],
            body_pose=[[0.0] * 60],
            transl=[[0.0, 0.0, 0.0]],
        )
