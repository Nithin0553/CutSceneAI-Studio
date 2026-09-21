import math

from fastapi.testclient import TestClient
import pytest

from cutsceneai_performance import BodyMotionArtifact
from providers.hymotion import service
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


def _provider_request(**updates) -> service.BodyRequest:
    payload = {
        "semantic_id": "body:scene:beat:guard",
        "start_frame": 0,
        "end_frame": 96,
        "prompt": (
            "Generate novel full-body motion. Action: walk forward, stop and turn toward a door "
            "Style: natural. Emotion: cautious at 0.50 intensity. "
            "Duration: 96 frames at 24 fps. Preserve balanced foot contact."
        ),
        "prompt_sha256": "a" * 64,
        "configuration_sha256": "b" * 64,
        "seed": 42,
        "provider": service.HY_MOTION_PROVIDER_ID,
        "model": service.HY_MOTION_MODEL_NAME,
        "model_revision": service.HY_MOTION_LITE_CHECKPOINT_SHA256,
        "prompt_version": "body-v0.1",
        "actor_binding_id": "actor:guard",
        "source_performance_cue_id": "performance:scene:beat:guard",
        "skeleton_profile": "cutsceneai-humanoid-v1",
        "look_at_binding_id": None,
    }
    payload.update(updates)
    return service.BodyRequest.model_validate(payload)


def test_hymotion_request_identity_is_checkpoint_locked() -> None:
    service._validate_request_identity(_provider_request())

    with pytest.raises(RuntimeError, match="does not match the loaded HY-Motion checkpoint"):
        service._validate_request_identity(_provider_request(model_revision="floating-latest"))


def test_hymotion_motion_prompt_isolates_body_action() -> None:
    prompt = service._motion_prompt(_provider_request().prompt)

    assert prompt == "walk forward, stop and turn toward a door"
    assert "Generate novel" not in prompt
    assert "Emotion:" not in prompt
    assert "Duration:" not in prompt


def test_hymotion_health_exposes_immutable_provenance(monkeypatch) -> None:
    monkeypatch.setattr(service, "_runtime", None)

    response = TestClient(service.app).get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "cold"
    assert body["provider"] == service.HY_MOTION_PROVIDER_ID
    assert body["model"] == service.HY_MOTION_MODEL_NAME
    assert body["model_revision"] == service.HY_MOTION_LITE_CHECKPOINT_SHA256
    assert body["checkpoint_sha256"] == service.HY_MOTION_LITE_CHECKPOINT_SHA256
    assert body["hub_revision"] == service.HY_MOTION_HUB_REVISION
    assert body["code_revision"] == service.HY_MOTION_CODE_REVISION


def test_hymotion_generate_rejects_wrong_protocol_without_gpu_load(monkeypatch) -> None:
    monkeypatch.setattr(
        service,
        "_load_runtime",
        lambda: (_ for _ in ()).throw(AssertionError("GPU runtime must not load")),
    )

    response = TestClient(service.app).post(
        "/generate",
        json={
            "protocol_version": "cutsceneai.provider.v9",
            "kind": "body_motion",
            "request": _provider_request().model_dump(mode="json"),
        },
    )

    assert response.status_code == 422
    assert "protocol" in response.json()["detail"].lower()
