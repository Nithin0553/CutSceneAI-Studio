import math

import pytest

from cutsceneai_performance import BodyMotionArtifact
from providers.hymotion.canonical import (
    CANONICAL_JOINT_NAMES,
    CANONICAL_PARENT_INDICES,
    convert_hymotion_smplh_to_cutsceneai,
)


def _flat_pose(root_axis_angle: tuple[float, float, float]) -> list[float]:
    values = [0.0] * (52 * 3)
    values[0:3] = list(root_axis_angle)
    return values


def test_hymotion_converter_matches_canonical_joint_contract() -> None:
    artifact = convert_hymotion_smplh_to_cutsceneai(
        [
            _flat_pose((0.0, 0.0, 0.0)),
            _flat_pose((0.0, math.pi / 2.0, 0.0)),
        ],
        [
            [1.0, 2.0, 3.0],
            [2.0, 3.0, 4.0],
        ],
    )

    validated = BodyMotionArtifact.model_validate(artifact)
    assert tuple(validated.joint_names) == CANONICAL_JOINT_NAMES
    assert tuple(validated.parent_indices) == CANONICAL_PARENT_INDICES
    assert validated.fps == 30
    assert validated.frame_count == 2

    first = validated.samples[0]
    second = validated.samples[1]
    assert first.root_translation.x == pytest.approx(0.0)
    assert first.root_translation.y == pytest.approx(0.0)
    assert first.root_translation.z == pytest.approx(0.0)
    assert second.root_translation.x == pytest.approx(1.0)
    assert second.root_translation.y == pytest.approx(1.0)
    assert second.root_translation.z == pytest.approx(-1.0)

    pelvis = second.joint_rotations[0]
    assert pelvis.x == pytest.approx(0.0, abs=1e-7)
    assert pelvis.y == pytest.approx(-math.sqrt(0.5), abs=1e-7)
    assert pelvis.z == pytest.approx(0.0, abs=1e-7)
    assert pelvis.w == pytest.approx(math.sqrt(0.5), abs=1e-7)


def test_hymotion_converter_accepts_nested_first_22_smplh_joints() -> None:
    frame = [[0.0, 0.0, 0.0] for _ in range(52)]
    frame[16] = [math.pi / 4.0, 0.0, 0.0]

    artifact = BodyMotionArtifact.model_validate(
        convert_hymotion_smplh_to_cutsceneai(
            [frame],
            [[0.0, 0.0, 0.0]],
            source_fps=30,
        )
    )

    shoulder = artifact.samples[0].joint_rotations[16]
    assert shoulder.x < 0.0
    assert shoulder.w > 0.0
    assert len(artifact.samples[0].joint_rotations) == 22


def test_hymotion_converter_rebases_absolute_translation_to_reference_pose() -> None:
    pose = _flat_pose((0.0, 0.0, 0.0))
    artifact = BodyMotionArtifact.model_validate(
        convert_hymotion_smplh_to_cutsceneai(
            [pose, pose, pose],
            [
                [4.0, 0.9, -7.0],
                [4.5, 0.9, -7.25],
                [5.0, 1.0, -7.5],
            ],
        )
    )

    assert artifact.samples[0].root_translation.model_dump() == {
        "x": 0.0,
        "y": 0.0,
        "z": -0.0,
    }
    assert artifact.samples[1].root_translation.x == pytest.approx(0.5)
    assert artifact.samples[1].root_translation.y == pytest.approx(0.0)
    assert artifact.samples[1].root_translation.z == pytest.approx(0.25)
    assert artifact.samples[2].root_translation.x == pytest.approx(1.0)
    assert artifact.samples[2].root_translation.y == pytest.approx(0.1)
    assert artifact.samples[2].root_translation.z == pytest.approx(0.5)


@pytest.mark.parametrize(
    ("poses", "translations", "message"),
    [
        ([], [], "no pose frames"),
        ([_flat_pose((0.0, 0.0, 0.0))], [], "frame counts"),
        ([[0.0] * 12], [[0.0, 0.0, 0.0]], "at least 66"),
        (
            [_flat_pose((0.0, 0.0, 0.0))],
            [[0.0, 0.0]],
            "exactly three",
        ),
    ],
)
def test_hymotion_converter_rejects_malformed_provider_output(
    poses,
    translations,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        convert_hymotion_smplh_to_cutsceneai(poses, translations)
