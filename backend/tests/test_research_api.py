from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_s02_research_result_is_scoped_and_hash_locked() -> None:
    response = client.get("/api/v1/research/s02")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "RESEARCH_PASS_WITH_KNOWN_LIMITATIONS"
    assert body["intent"] == "WALK_FORWARD_STOP_AND_LOOK_DOWN"
    assert body["canonical"] == {
        "sha256": "f708f7a0ca84f055d9c357a6c72bc30f726108400c8c9b799d728f8f58fca461",
        "frame_count": 96,
        "fps": 24,
        "joint_count": 22,
        "skeleton_profile": "cutsceneai-humanoid-v1",
    }
    assert body["ai_reinference_between_engines"] is False
    assert body["engines"]["unreal"]["status"] == "PASS_WITH_KNOWN_LIMITATION"
    assert body["engines"]["unity"]["status"] == "PASS_WITH_KNOWN_LIMITATION"
    assert body["engines"]["unity"]["native_animationclip_timeline_validated"] is False
    assert "does not empirically establish universal support" in body["non_claim"]
