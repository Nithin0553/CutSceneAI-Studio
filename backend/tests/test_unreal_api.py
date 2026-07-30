import json
from io import BytesIO
from pathlib import Path
import wave
from zipfile import ZipFile

from fastapi.testclient import TestClient

from app.main import app
from cutsceneai_cir import validate_project
from cutsceneai_dialogue import (
    MAX_DIALOGUE_BUNDLE_BYTES,
    RecordedAudioInput,
    build_recorded_bundle,
    plan_project,
    render_dialogue_bundle,
)


EXAMPLE = Path(__file__).resolve().parents[2] / "cir" / "examples" / "office-dialogue.cir.json"
client = TestClient(app)


def payload() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def dialogue_bundle_payload() -> bytes:
    output = BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(8_000)
        wav_file.writeframes(b"\0" * 16_000)
    wav = output.getvalue()
    project = validate_project(payload())
    recordings = {
        cue.cue_id: RecordedAudioInput(data=wav, filename=f"{cue.character_id}.wav")
        for cue in plan_project(project).cues
    }
    return render_dialogue_bundle(build_recorded_bundle(project, recordings))


def test_export_unreal_plan_returns_golden_sequence_contract() -> None:
    response = client.post("/api/v1/adapters/unreal/export", json=payload())

    assert response.status_code == 200
    body = response.json()
    assert body["adapter_version"] == "0.6.0"
    assert body["target_engine_version"] == "5.8.0"
    assert body["sequences"][0]["asset_name"] == "LS_SceneMeeting"
    assert len(body["sequences"][0]["actors"]) == 4
    assert body["sequences"][0]["actors"][0]["mesh_type"] == "static_mesh"
    assert len(body["sequences"][0]["set_pieces"]) == 4
    assert body["sequences"][0]["animation_sections"] == []
    assert body["sequences"][0]["audio_sections"] == []
    assert len(body["sequences"][0]["cameras"]) == 4


def test_export_unreal_importer_returns_safe_python_script() -> None:
    response = client.post("/api/v1/adapters/unreal/importer.py", json=payload())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/x-python")
    assert response.headers["content-disposition"] == (
        'attachment; filename="cutsceneai-unreal-import.py"'
    )
    compile(response.text, "api_unreal_import.py", "exec")
    assert "unreal.MovieSceneCameraCutTrack" in response.text


def test_export_unreal_plan_preserves_character_skeletal_mesh_binding() -> None:
    value = payload()
    value["characters"][0]["asset_uri"] = (
        "/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple.SKM_Quinn_Simple"
    )

    response = client.post("/api/v1/adapters/unreal/export", json=value)

    assert response.status_code == 200
    mina = response.json()["sequences"][0]["actors"][0]
    assert mina["mesh_type"] == "skeletal_mesh"
    assert mina["actor_class_path"] == "/Script/Engine.SkeletalMeshActor"
    assert mina["placeholder"] is False


def test_export_unreal_plan_compiles_motion_asset_to_animation_section() -> None:
    value = payload()
    value["characters"][0]["asset_uri"] = (
        "/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple.SKM_Quinn_Simple"
    )
    value["scenes"][0]["beats"][0]["performances"][0]["motion"]["asset_uri"] = (
        "/Game/Characters/Mannequins/Animations/Quinn/MF_Idle.MF_Idle"
    )

    response = client.post("/api/v1/adapters/unreal/export", json=value)

    assert response.status_code == 200
    sections = response.json()["sequences"][0]["animation_sections"]
    assert sections == [
        {
            "source_beat_id": "beat-arrival",
            "actor_binding_id": "actor:mina",
            "asset_path": "/Game/Characters/Mannequins/Animations/Quinn/MF_Idle.MF_Idle",
            "start_frame": 0,
            "end_frame": 96,
        }
    ]


def test_export_unreal_plan_compiles_dialogue_audio_to_speaker_section() -> None:
    value = payload()
    value["scenes"][0]["beats"][1]["performances"][0]["dialogue"]["audio_uri"] = (
        "/Game/CutSceneAI/Audio/SW_Mina_Line01.SW_Mina_Line01"
    )

    response = client.post("/api/v1/adapters/unreal/export", json=value)

    assert response.status_code == 200
    sections = response.json()["sequences"][0]["audio_sections"]
    assert sections == [
        {
            "source_cue_id": None,
            "source_beat_id": "beat-confrontation",
            "actor_binding_id": "actor:mina",
            "asset_path": "/Game/CutSceneAI/Audio/SW_Mina_Line01.SW_Mina_Line01",
            "start_frame": 120,
            "end_frame": 336,
            "timing_source": "performance_range",
            "dialogue_text": "You said this would be signed yesterday.",
            "language": "en",
        }
    ]


def test_unreal_adapter_rejects_invalid_cir() -> None:
    value = payload()
    value["scenes"][0]["shots"][0]["purpose"] = "action"

    response = client.post("/api/v1/adapters/unreal/export", json=value)

    assert response.status_code == 422
    assert "missing_establishing_shot" in {problem["code"] for problem in response.json()["errors"]}


def test_unreal_adapter_reports_invalid_rotation_as_422() -> None:
    value = payload()
    value["characters"][0]["initial_transform"]["rotation"] = {
        "x": 0.0,
        "y": 0.0,
        "z": 0.0,
        "w": 0.0,
    }

    response = client.post("/api/v1/adapters/unreal/export", json=value)

    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "unreal.adapter_conversion_failed"


def test_unreal_importer_returns_validation_errors() -> None:
    response = client.post("/api/v1/adapters/unreal/importer.py", json={"bad": "payload"})

    assert response.status_code == 422
    assert response.json()["valid"] is False


def test_export_unreal_dialogue_bundle_returns_self_contained_import_package() -> None:
    response = client.post(
        "/api/v1/adapters/unreal/dialogue-bundle",
        content=dialogue_bundle_payload(),
        headers={"Content-Type": "application/zip"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/zip")
    assert response.headers["content-disposition"] == (
        'attachment; filename="office-dialogue.unreal-v0.6.zip"'
    )
    assert response.headers["x-cutsceneai-unreal-adapter-version"] == "0.6.0"
    assert response.headers["x-cutsceneai-unreal-audio-imports"] == "2"
    with ZipFile(BytesIO(response.content)) as archive:
        assert "cutsceneai-unreal-import.py" in archive.namelist()
        plan = json.loads(archive.read("unreal.plan.json"))
        assert len(plan["audio_imports"]) == 2
        assert [section["end_frame"] for section in plan["sequences"][0]["audio_sections"]] == [
            144,
            240,
        ]


def test_export_unreal_dialogue_bundle_returns_structured_validation_error() -> None:
    response = client.post(
        "/api/v1/adapters/unreal/dialogue-bundle",
        content=b"not a zip",
        headers={"Content-Type": "application/zip"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "code": "invalid_dialogue_bundle",
        "message": "Dialogue bundle is not a readable ZIP archive.",
        "retryable": False,
        "request_id": None,
    }


def test_export_unreal_dialogue_bundle_rejects_declared_oversized_upload() -> None:
    response = client.post(
        "/api/v1/adapters/unreal/dialogue-bundle",
        content=b"",
        headers={
            "Content-Type": "application/zip",
            "Content-Length": str(MAX_DIALOGUE_BUNDLE_BYTES + 1),
        },
    )

    assert response.status_code == 413
    assert response.json()["code"] == "dialogue_bundle_too_large"
