import asyncio
from io import BytesIO
import json
from pathlib import Path
import sys
import wave

from cutsceneai_cir import Project
from cutsceneai_dialogue import SpeechBackendResult
from cutsceneai_performance import (
    HumanMLXYZMotion,
    ProviderArtifact,
    humanml_xyz_to_canonical,
    load_performance_bundle,
)
from fastapi.testclient import TestClient
import pytest

from app.api.performance_runtime import get_native_studio_service, get_performance_executor
from app.main import app
from app.models.performance_runtime import PerformanceGenerateRequest, PerformanceRunStatus
from app.services.performance_executor import StudioPerformanceExecutor
from app.services.performance_providers import (
    ExternalCanonicalBodyBackend,
    PerformanceProviderExecutionError,
)
import app.services.performance_executor as performance_executor_module
import app.services.performance_providers as performance_providers_module


FIXTURE = Path(__file__).resolve().parents[2] / "cir" / "examples" / "office-dialogue.cir.json"


def _project() -> Project:
    return Project.model_validate_json(FIXTURE.read_text(encoding="utf-8"))


def _project_without_dialogue() -> Project:
    payload = _project().model_dump(mode="json")
    for scene in payload["scenes"]:
        for beat in scene["beats"]:
            for performance in beat["performances"]:
                performance["dialogue"] = None
                performance["facial"]["lip_sync"] = False
    return Project.model_validate(payload)


def _write_body_provider(path: Path) -> None:
    path.write_text(
        """
import json
import re
import sys

payload = json.loads(sys.stdin.read())
request = payload["request"]
frame_count = request["end_frame"] - request["start_frame"]
match = re.search(r"at (\\d+) fps", request["prompt"])
fps = int(match.group(1)) if match else 24
identity = {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}
samples = [
    {
        "frame_index": frame,
        "root_translation": {"x": 0.0, "y": 0.0, "z": -0.01 * frame},
        "joint_rotations": [identity for _ in range(22)],
    }
    for frame in range(frame_count)
]
response = {
    "request_semantic_id": request["semantic_id"],
    "provider": request["provider"],
    "model": request["model"],
    "model_revision": request["model_revision"],
    "prompt_sha256": request["prompt_sha256"],
    "configuration_sha256": request["configuration_sha256"],
    "seed": request["seed"],
    "generated_at_inference": True,
    "retrieved_pre_authored_clip": False,
    "deterministic_algorithms": True,
    "artifact": {
        "fps": fps,
        "frame_count": frame_count,
        "samples": samples,
    },
}
sys.stdout.write(json.dumps(response))
""".strip()
        + "\n",
        encoding="utf-8",
    )


def _write_humanml_body_provider(path: Path) -> None:
    path.write_text(
        """
import json
import re
import sys

payload = json.loads(sys.stdin.read())
request = payload["request"]
frame_count = request["end_frame"] - request["start_frame"]
match = re.search(r"at (\\d+) fps", request["prompt"])
fps = int(match.group(1)) if match else 20
names = [
    "pelvis","left_hip","right_hip","spine1","left_knee","right_knee",
    "spine2","left_ankle","right_ankle","spine3","left_foot","right_foot",
    "neck","left_collar","right_collar","head","left_shoulder","right_shoulder",
    "left_elbow","right_elbow","left_wrist","right_wrist",
]
parents = [-1,0,0,0,1,2,3,4,5,6,7,8,9,9,9,12,13,14,16,17,18,19]
offsets = [
    (0,0,0),(0.2,-0.1,0),(-0.2,-0.1,0),(0,0.2,0),(0,-0.4,0.1),
    (0,-0.4,0.1),(0,0.2,0),(0,-0.4,-0.1),(0,-0.4,-0.1),(0,0.2,0),
    (0,-0.05,0.2),(0,-0.05,0.2),(0,0.2,0),(0.15,0.05,0),
    (-0.15,0.05,0),(0,0.2,0),(0.25,0,0),(-0.25,0,0),
    (0.25,0,0),(-0.25,0,0),(0.25,0,0),(-0.25,0,0),
]
frames = []
for frame in range(frame_count):
    scale = 0.8 if frame % 2 == 0 else 1.25
    positions = []
    for index, parent in enumerate(parents):
        if parent < 0:
            positions.append([0.0, 1.0, -0.01 * frame])
        else:
            px, py, pz = positions[parent]
            ox, oy, oz = offsets[index]
            positions.append([px + ox * scale, py + oy * scale, pz + oz * scale])
    frames.append(positions)

response = {
    "request_semantic_id": request["semantic_id"],
    "provider": request["provider"],
    "model": request["model"],
    "model_revision": request["model_revision"],
    "prompt_sha256": request["prompt_sha256"],
    "configuration_sha256": request["configuration_sha256"],
    "seed": request["seed"],
    "generated_at_inference": True,
    "retrieved_pre_authored_clip": False,
    "deterministic_algorithms": True,
    "artifact_format": "humanml-xyz-v0.1",
    "artifact": {
        "fps": fps,
        "frame_count": frame_count,
        "joint_names": names,
        "positions": frames,
    },
}
sys.stdout.write(json.dumps(response))
""".strip()
        + "\n",
        encoding="utf-8",
    )


def _configure_humanml_body_provider(tmp_path: Path, monkeypatch) -> None:
    script = tmp_path / "humanml_body_provider.py"
    _write_humanml_body_provider(script)
    monkeypatch.setenv(
        "CUTSCENEAI_BODY_PROVIDER_COMMAND",
        json.dumps([sys.executable, str(script)]),
    )
    monkeypatch.setenv("CUTSCENEAI_BODY_PROVIDER", "fixture-humanml")
    monkeypatch.setenv("CUTSCENEAI_BODY_MODEL", "varying-skeleton")
    monkeypatch.setenv("CUTSCENEAI_BODY_MODEL_REVISION", "test-r1")
    monkeypatch.setenv("CUTSCENEAI_BODY_PROVIDER_TIMEOUT_SECONDS", "5")


def _configure_body_provider(tmp_path: Path, monkeypatch) -> None:
    script = tmp_path / "body_provider.py"
    _write_body_provider(script)
    monkeypatch.setenv(
        "CUTSCENEAI_BODY_PROVIDER_COMMAND",
        json.dumps([sys.executable, str(script)]),
    )
    monkeypatch.setenv("CUTSCENEAI_BODY_PROVIDER", "fixture-motion")
    monkeypatch.setenv("CUTSCENEAI_BODY_MODEL", "identity-canonical")
    monkeypatch.setenv("CUTSCENEAI_BODY_MODEL_REVISION", "test-r1")
    monkeypatch.setenv("CUTSCENEAI_BODY_PROVIDER_TIMEOUT_SECONDS", "5")


def _wav(duration_seconds: float = 0.08, sample_rate: int = 16000) -> bytes:
    frame_count = max(1, int(duration_seconds * sample_rate))
    output = BytesIO()
    with wave.open(output, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"\x00\x00" * frame_count)
    return output.getvalue()


class FakeSpeechBackend:
    async def synthesize(self, request):
        return SpeechBackendResult(
            data=_wav(),
            provider="fake-speech",
            model="fake-wav",
            voice=request.voice,
            request_id="speech-test",
        )


def _humanml_rest_positions() -> list[list[float]]:
    offsets = (
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
    parents = (-1, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9, 9, 12, 13, 14, 16, 17, 18, 19)
    positions: list[list[float]] = []
    for index, offset in enumerate(offsets):
        parent = parents[index]
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


def test_external_body_provider_accepts_humanml_xyz_output() -> None:
    request = performance_executor_module.compile_generation_plan(
        _project_without_dialogue(),
        config=performance_providers_module.performance_compiler_config(20260812),
    ).body_requests[0]
    rest = _humanml_rest_positions()
    moved = [[x, y, z + 1.0] for x, y, z in rest]
    response = {
        "request_semantic_id": request.semantic_id,
        "provider": request.provider,
        "model": request.model,
        "model_revision": request.model_revision,
        "prompt_sha256": request.prompt_sha256,
        "configuration_sha256": request.configuration_sha256,
        "seed": request.seed,
        "generated_at_inference": True,
        "retrieved_pre_authored_clip": False,
        "deterministic_algorithms": False,
        "artifact_format": "humanml-xyz-v0.1",
        "artifact": {
            "fps": 20,
            "frame_count": 2,
            "joint_names": [
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
            ],
            "positions": [rest, moved],
        },
    }

    output = ExternalCanonicalBodyBackend._parse_response(request, response)

    assert output.artifact.fps == 20
    assert output.artifact.frame_count == 2
    assert len(output.artifact.samples[0].joint_rotations) == 22
    assert output.artifact.samples[1].root_translation.z == pytest.approx(-1.0)


def test_external_body_provider_accepts_smplx_axis_angle_output() -> None:
    request = performance_executor_module.compile_generation_plan(
        _project_without_dialogue(),
        config=performance_providers_module.performance_compiler_config(20260812),
    ).body_requests[0]
    request = request.model_copy(
        update={
            "provider": "motionmaster-cvpr2026",
            "model": "mllm_single_3b",
            "model_revision": "fixture-revision",
        }
    )
    frame_count = 3
    response = {
        "request_semantic_id": request.semantic_id,
        "provider": request.provider,
        "model": request.model,
        "model_revision": request.model_revision,
        "prompt_sha256": request.prompt_sha256,
        "configuration_sha256": request.configuration_sha256,
        "seed": request.seed,
        "generated_at_inference": True,
        "retrieved_pre_authored_clip": False,
        "deterministic_algorithms": False,
        "artifact_format": "smplx-axis-angle-v0.1",
        "artifact": {
            "fps": 30,
            "source_forward_axis": "+z",
            "global_orient": [[0.0, 0.0, 0.0]] * frame_count,
            "body_pose": [[0.0] * 63 for _ in range(frame_count)],
            "transl": [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 2.0],
                [2.0, 0.0, 4.0],
            ],
        },
    }

    output = ExternalCanonicalBodyBackend._parse_response(request, response)

    assert output.request_semantic_id == request.semantic_id
    assert output.provider == "motionmaster-cvpr2026"
    assert output.deterministic_algorithms is False
    assert output.artifact.frame_count == frame_count
    assert len(output.artifact.samples[0].joint_rotations) == 22
    assert output.artifact.samples[1].root_translation.model_dump() == {
        "x": -1.0,
        "y": 0.0,
        "z": -2.0,
    }


def test_external_body_provider_rejects_unknown_artifact_format() -> None:
    request = performance_executor_module.compile_generation_plan(
        _project_without_dialogue(),
        config=performance_providers_module.performance_compiler_config(20260812),
    ).body_requests[0]
    response = {
        "request_semantic_id": request.semantic_id,
        "provider": request.provider,
        "model": request.model,
        "model_revision": request.model_revision,
        "prompt_sha256": request.prompt_sha256,
        "configuration_sha256": request.configuration_sha256,
        "seed": request.seed,
        "generated_at_inference": True,
        "retrieved_pre_authored_clip": False,
        "deterministic_algorithms": True,
        "artifact_format": "unknown-motion-format",
        "artifact": {},
    }

    with pytest.raises(PerformanceProviderExecutionError, match="unsupported artifact_format"):
        ExternalCanonicalBodyBackend._parse_response(request, response)


def test_readiness_requires_explicit_body_provider_identity(tmp_path: Path, monkeypatch) -> None:
    executor = StudioPerformanceExecutor(run_root=tmp_path / "runs")
    monkeypatch.delenv("CUTSCENEAI_BODY_PROVIDER_COMMAND", raising=False)
    monkeypatch.delenv("CUTSCENEAI_BODY_PROVIDER_URL", raising=False)

    blocked = executor.readiness()
    assert blocked.ready is False
    assert any(item.modality == "body" and not item.configured for item in blocked.providers)

    _configure_body_provider(tmp_path, monkeypatch)
    ready = executor.readiness()
    assert ready.ready is True
    assert next(item for item in ready.providers if item.modality == "body").configured is True


def test_executor_generates_verified_bundle_and_evidence(tmp_path: Path, monkeypatch) -> None:
    _configure_body_provider(tmp_path, monkeypatch)
    executor = StudioPerformanceExecutor(run_root=tmp_path / "runs")

    record = asyncio.run(
        executor.generate(
            PerformanceGenerateRequest(
                project=_project_without_dialogue(),
                experiment_seed=20260812,
            )
        )
    )

    assert record.status is PerformanceRunStatus.SUCCEEDED
    assert record.bundle_sha256 is not None
    assert record.body_request_count > 0
    assert record.facial_request_count == record.body_request_count
    assert record.camera_request_count > 0
    assert record.audio_track_count == 0

    data = executor.bundle_bytes(record.run_id)
    bundle = load_performance_bundle(data)
    assert bundle.package.project_id == record.project_id
    assert len(bundle.package.body_tracks) == record.body_request_count
    assert len(bundle.package.facial_tracks) == record.facial_request_count
    assert len(bundle.package.camera_tracks) == record.camera_request_count

    run_dir = tmp_path / "runs" / record.run_id
    assert (run_dir / "input.cir.json").exists()
    assert (run_dir / "generation.plan.json").exists()
    assert (run_dir / "provider-readiness.json").exists()
    assert (run_dir / "provider-output-summary.json").exists()
    diagnostic = executor.body_composition_diagnostic(record.run_id)
    assert len(diagnostic.track_metrics) == record.body_request_count
    assert (run_dir / "body-composition-diagnostic.json").exists()
    evaluation = executor.evaluate_run(record.run_id)
    assert evaluation.report.performance_run_id == record.run_id
    assert evaluation.report.stages_evaluated == ["canonical"]
    assert evaluation.report.accepted is False
    assert any(
        issue.code == "canonical_geometry_missing"
        for issue in evaluation.report.issues
    )
    assert evaluation.repair_plan.requires_fresh_inference is True
    assert (run_dir / "evaluation.json").exists()
    assert (run_dir / "repair-plan.json").exists()
    assert executor.get_run(record.run_id).bundle_sha256 == record.bundle_sha256
    assert executor.list_runs()[0].run_id == record.run_id


def test_executor_derives_recomposed_body_run_without_new_inference(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _configure_body_provider(tmp_path, monkeypatch)
    executor = StudioPerformanceExecutor(run_root=tmp_path / "runs")
    source = asyncio.run(
        executor.generate(
            PerformanceGenerateRequest(project=_project_without_dialogue())
        )
    )

    derived = executor.recompose_body_run(source.run_id)

    assert derived.status is PerformanceRunStatus.SUCCEEDED
    assert derived.run_id != source.run_id
    assert derived.derived_from_run_id == source.run_id
    assert derived.derivation == "body-recomposition-v1"
    assert derived.body_request_count == source.body_request_count
    assert derived.bundle_sha256 is not None

    run_dir = tmp_path / "runs" / derived.run_id
    derivation = json.loads(
        (run_dir / "derivation.json").read_text(encoding="utf-8")
    )
    assert derivation["derived_from_run_id"] == source.run_id
    assert derivation["fresh_body_inference"] is False
    assert derivation["reused_body_provider_outputs"] is True
    assert (run_dir / "body-provider-outputs").is_dir()
    assert (run_dir / "body-composition-diagnostic.json").is_file()
    load_performance_bundle(executor.bundle_bytes(derived.run_id))


def test_executor_repairs_canonical_bone_length_instability_without_inference(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("CUTSCENEAI_BODY_PROVIDER_COMMAND", "[\"fixture\"]")
    monkeypatch.setenv("CUTSCENEAI_BODY_PROVIDER", "fixture-humanml")
    monkeypatch.setenv("CUTSCENEAI_BODY_MODEL", "varying-skeleton")
    monkeypatch.setenv("CUTSCENEAI_BODY_MODEL_REVISION", "test-r1")
    monkeypatch.setenv("CUTSCENEAI_BODY_PROVIDER_TIMEOUT_SECONDS", "5")

    class FakeHumanMLBackend:
        configured = True

        def probe_health(self, **kwargs):
            return None, None, {}

        async def generate_body(self, request):
            frame_count = request.end_frame - request.start_frame
            names = [
                "pelvis","left_hip","right_hip","spine1","left_knee","right_knee",
                "spine2","left_ankle","right_ankle","spine3","left_foot","right_foot",
                "neck","left_collar","right_collar","head","left_shoulder","right_shoulder",
                "left_elbow","right_elbow","left_wrist","right_wrist",
            ]
            parents = [-1,0,0,0,1,2,3,4,5,6,7,8,9,9,9,12,13,14,16,17,18,19]
            offsets = [
                (0,0,0),(0.2,-0.1,0),(-0.2,-0.1,0),(0,0.2,0),(0,-0.4,0.1),
                (0,-0.4,0.1),(0,0.2,0),(0,-0.4,-0.1),(0,-0.4,-0.1),(0,0.2,0),
                (0,-0.05,0.2),(0,-0.05,0.2),(0,0.2,0),(0.15,0.05,0),
                (-0.15,0.05,0),(0,0.2,0),(0.25,0,0),(-0.25,0,0),
                (0.25,0,0),(-0.25,0,0),(0.25,0,0),(-0.25,0,0),
            ]
            frames = []
            for frame in range(frame_count):
                scale = 0.8 if frame % 2 == 0 else 1.25
                positions = []
                for index, parent in enumerate(parents):
                    if parent < 0:
                        positions.append([0.0, 1.0, -0.01 * frame])
                    else:
                        px, py, pz = positions[parent]
                        ox, oy, oz = offsets[index]
                        positions.append(
                            [px + ox * scale, py + oy * scale, pz + oz * scale]
                        )
                frames.append(positions)

            artifact = humanml_xyz_to_canonical(
                HumanMLXYZMotion(
                    fps=20,
                    frame_count=frame_count,
                    joint_names=names,
                    positions=frames,
                )
            )
            return ProviderArtifact(
                request_semantic_id=request.semantic_id,
                artifact=artifact,
                provider=request.provider,
                model=request.model,
                model_revision=request.model_revision,
                prompt_sha256=request.prompt_sha256,
                configuration_sha256=request.configuration_sha256,
                seed=request.seed,
                generated_at_inference=True,
                retrieved_pre_authored_clip=False,
                deterministic_algorithms=True,
            )

    fake_backend = FakeHumanMLBackend()
    monkeypatch.setattr(
        performance_executor_module.ExternalCanonicalBodyBackend,
        "from_environment",
        classmethod(lambda cls: fake_backend),
    )

    executor = StudioPerformanceExecutor(run_root=tmp_path / "runs")
    source = asyncio.run(
        executor.generate(
            PerformanceGenerateRequest(project=_project_without_dialogue())
        )
    )

    assert source.status is PerformanceRunStatus.SUCCEEDED
    before = executor.evaluate_run(source.run_id)
    assert any(
        issue.code == "bone_length_instability"
        for issue in before.report.issues
    )

    repaired = executor.repair_run(source.run_id)

    assert repaired.derived_run is not None
    assert repaired.derived_run.derived_from_run_id == source.run_id
    assert repaired.derived_run.derivation == "canonical-skeleton-normalization-v1"
    assert repaired.applied_action_ids
    assert repaired.post_report is not None
    assert not any(
        issue.code == "bone_length_instability"
        for issue in repaired.post_report.issues
    )
    assert repaired.derived_run.bundle_sha256 != source.bundle_sha256
    run_dir = tmp_path / "runs" / repaired.derived_run.run_id
    derivation = json.loads(
        (run_dir / "derivation.json").read_text(encoding="utf-8")
    )
    assert derivation["fresh_body_inference"] is False
    assert (run_dir / "repair-execution.json").is_file()

def test_executor_persists_body_outputs_before_postprocessing_failure(
    tmp_path: Path, monkeypatch
) -> None:
    _configure_body_provider(tmp_path, monkeypatch)
    executor = StudioPerformanceExecutor(run_root=tmp_path / "runs")

    def fail_after_body(*args, **kwargs):
        raise RuntimeError("post-body failure")

    monkeypatch.setattr(
        performance_executor_module,
        "assemble_performance_bundle",
        fail_after_body,
    )

    record = asyncio.run(
        executor.generate(
            PerformanceGenerateRequest(project=_project_without_dialogue())
        )
    )

    assert record.status is PerformanceRunStatus.FAILED
    assert "post-body failure" in (record.error or "")
    output_dir = tmp_path / "runs" / record.run_id / "body-provider-outputs"
    motion_files = sorted(output_dir.glob("*.motion.json"))
    metadata_files = sorted(output_dir.glob("*.metadata.json"))
    assert len(motion_files) == record.body_request_count
    assert len(metadata_files) == record.body_request_count
    metadata = json.loads(metadata_files[0].read_text(encoding="utf-8"))
    assert metadata["request_semantic_id"].startswith("body:")
    assert metadata["artifact_file"] == motion_files[0].name


def test_executor_keeps_failed_run_evidence(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("CUTSCENEAI_BODY_PROVIDER_COMMAND", raising=False)
    monkeypatch.delenv("CUTSCENEAI_BODY_PROVIDER_URL", raising=False)
    executor = StudioPerformanceExecutor(run_root=tmp_path / "runs")

    record = asyncio.run(
        executor.generate(PerformanceGenerateRequest(project=_project_without_dialogue()))
    )

    assert record.status is PerformanceRunStatus.FAILED
    assert "Generated performance is not ready" in (record.error or "")
    run_dir = tmp_path / "runs" / record.run_id
    assert (run_dir / "failure.txt").exists()
    try:
        executor.bundle_bytes(record.run_id)
    except ValueError as exc:
        assert "did not succeed" in str(exc)
    else:
        raise AssertionError("Expected failed runs to refuse bundle download.")


def test_executor_synthesizes_dialogue_and_preserves_manifest(tmp_path: Path, monkeypatch) -> None:
    _configure_body_provider(tmp_path, monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        performance_executor_module,
        "OpenAISpeechBackend",
        lambda: FakeSpeechBackend(),
    )
    executor = StudioPerformanceExecutor(run_root=tmp_path / "runs")

    record = asyncio.run(executor.generate(PerformanceGenerateRequest(project=_project())))

    assert record.status is PerformanceRunStatus.SUCCEEDED
    assert record.audio_track_count > 0
    run_dir = tmp_path / "runs" / record.run_id
    manifest = json.loads((run_dir / "dialogue.manifest.json").read_text(encoding="utf-8"))
    assert manifest["ai_voice_disclosure_required"] is True
    assert all(clip["provenance"]["ai_generated"] for clip in manifest["clips"])
    bundle = load_performance_bundle(executor.bundle_bytes(record.run_id))
    assert len(bundle.package.audio_tracks) == record.audio_track_count


def test_performance_runtime_api_generate_list_and_download(tmp_path: Path, monkeypatch) -> None:
    _configure_body_provider(tmp_path, monkeypatch)
    executor = StudioPerformanceExecutor(run_root=tmp_path / "runs")
    app.dependency_overrides[get_performance_executor] = lambda: executor

    try:
        client = TestClient(app)
        readiness = client.get("/api/v1/studio/performance/readiness")
        generated = client.post(
            "/api/v1/studio/performance/generate",
            json={
                "project": _project_without_dialogue().model_dump(mode="json"),
                "experiment_seed": 20260812,
            },
        )
        assert generated.status_code == 200
        run_id = generated.json()["run_id"]
        fetched = client.get(f"/api/v1/studio/performance/runs/{run_id}")
        listed = client.get("/api/v1/studio/performance/runs?limit=5")
        diagnostic = client.get(
            f"/api/v1/studio/performance/runs/{run_id}/body-composition-diagnostic"
        )
        evaluation = client.post(
            f"/api/v1/studio/performance/runs/{run_id}/evaluate"
        )
        repair = client.post(
            f"/api/v1/studio/performance/runs/{run_id}/repair"
        )
        preview = client.get(
            f"/api/v1/studio/performance/runs/{run_id}/body-composition-preview"
        )
        recomposed = client.post(
            f"/api/v1/studio/performance/runs/{run_id}/recompose-body"
        )
        bundle = client.get(f"/api/v1/studio/performance/runs/{run_id}/bundle")
    finally:
        app.dependency_overrides.clear()

    assert readiness.status_code == 200
    assert readiness.json()["ready"] is True
    assert generated.json()["status"] == "succeeded"
    assert fetched.status_code == 200
    assert listed.status_code == 200
    assert listed.json()[0]["run_id"] == run_id
    assert diagnostic.status_code == 200
    assert len(diagnostic.json()["track_metrics"]) == generated.json()["body_request_count"]
    assert evaluation.status_code == 200
    assert evaluation.json()["report"]["performance_run_id"] == run_id
    assert evaluation.json()["report"]["stages_evaluated"] == ["canonical"]
    assert evaluation.json()["repair_plan"]["requires_fresh_inference"] is True
    assert repair.status_code == 200
    assert repair.json()["derived_run"] is None
    assert repair.json()["applied_action_ids"] == []
    assert repair.json()["deferred_action_ids"]
    assert preview.status_code == 200
    assert len(preview.json()["track_metrics"]) == generated.json()["body_request_count"]
    assert recomposed.status_code == 200
    assert recomposed.json()["derived_from_run_id"] == run_id
    assert recomposed.json()["derivation"] == "body-recomposition-v1"
    assert bundle.status_code == 200
    assert bundle.headers["content-type"].startswith("application/zip")
    load_performance_bundle(bundle.content)


def test_performance_runtime_api_applies_scene_conditioned_project(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _configure_body_provider(tmp_path, monkeypatch)
    executor = StudioPerformanceExecutor(run_root=tmp_path / "runs")

    class FakeStudio:
        def scene_conditioned_project(self, project_id, project, bindings):
            assert project_id == "studio-project-scene"
            assert bindings[0].cir_id == "mina"
            conditioned = project.model_copy(deep=True)
            mina = next(item for item in conditioned.characters if item.id == "mina")
            mina.initial_transform.position.x = 9.0
            mina.initial_transform.position.z = -11.0
            return conditioned

    app.dependency_overrides[get_performance_executor] = lambda: executor
    app.dependency_overrides[get_native_studio_service] = lambda: FakeStudio()

    try:
        client = TestClient(app)
        generated = client.post(
            "/api/v1/studio/performance/generate",
            json={
                "project": _project_without_dialogue().model_dump(mode="json"),
                "project_id": "studio-project-scene",
                "bindings": [
                    {
                        "cir_id": "mina",
                        "project_object_id": "scene:mina",
                    }
                ],
                "experiment_seed": 20260812,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert generated.status_code == 200
    assert generated.json()["status"] == "succeeded"
    run_id = generated.json()["run_id"]
    input_payload = json.loads(
        (tmp_path / "runs" / run_id / "input.cir.json").read_text(encoding="utf-8")
    )
    mina = next(item for item in input_payload["characters"] if item["id"] == "mina")
    assert mina["initial_transform"]["position"]["x"] == 9.0
    assert mina["initial_transform"]["position"]["z"] == -11.0


def test_performance_runtime_api_maps_configuration_and_missing_run_errors(
    tmp_path: Path, monkeypatch
) -> None:
    executor = StudioPerformanceExecutor(run_root=tmp_path / "runs")
    app.dependency_overrides[get_performance_executor] = lambda: executor
    monkeypatch.setenv("CUTSCENEAI_BODY_PROVIDER_TIMEOUT_SECONDS", "invalid")

    try:
        client = TestClient(app)
        readiness = client.get("/api/v1/studio/performance/readiness")
        missing = client.get("/api/v1/studio/performance/runs/not-a-uuid")
        missing_bundle = client.get("/api/v1/studio/performance/runs/not-a-uuid/bundle")
    finally:
        app.dependency_overrides.clear()

    assert readiness.status_code == 422
    assert "numeric" in readiness.json()["detail"]
    assert missing.status_code == 422
    assert missing_bundle.status_code == 422


def test_executor_validates_run_limits_registry_and_bundle_hash(
    tmp_path: Path, monkeypatch
) -> None:
    _configure_body_provider(tmp_path, monkeypatch)
    executor = StudioPerformanceExecutor(run_root=tmp_path / "runs")

    with pytest.raises(ValueError, match="between 1 and 200"):
        executor.list_runs(0)
    with pytest.raises(ValueError, match="Invalid performance run id"):
        executor.get_run("invalid")

    record = asyncio.run(
        executor.generate(PerformanceGenerateRequest(project=_project_without_dialogue()))
    )
    assert record.status is PerformanceRunStatus.SUCCEEDED

    bundle_path = tmp_path / "runs" / record.run_id / "performance.bundle.zip"
    bundle_path.write_bytes(bundle_path.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="SHA-256"):
        executor.bundle_bytes(record.run_id)

    unreadable_id = "00000000-0000-0000-0000-000000000001"
    unreadable = tmp_path / "runs" / unreadable_id
    unreadable.mkdir()
    (unreadable / "run.json").write_text("{not-json", encoding="utf-8")
    with pytest.raises(ValueError, match="unreadable"):
        executor.get_run(unreadable_id)


def test_dialogue_scene_fails_with_retained_evidence_without_tts_key(
    tmp_path: Path, monkeypatch
) -> None:
    _configure_body_provider(tmp_path, monkeypatch)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    executor = StudioPerformanceExecutor(run_root=tmp_path / "runs")

    record = asyncio.run(executor.generate(PerformanceGenerateRequest(project=_project())))

    assert record.status is PerformanceRunStatus.FAILED
    assert "OPENAI_API_KEY" in (record.error or "")
    run_dir = tmp_path / "runs" / record.run_id
    assert (run_dir / "input.cir.json").exists()
    assert (run_dir / "failure.txt").exists()


def test_list_runs_skips_corrupt_records(tmp_path: Path) -> None:
    executor = StudioPerformanceExecutor(run_root=tmp_path / "runs")
    corrupt = tmp_path / "runs" / "00000000-0000-0000-0000-000000000002"
    corrupt.mkdir(parents=True)
    (corrupt / "run.json").write_text("not-json", encoding="utf-8")

    assert executor.list_runs() == []


class _HealthResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self, _: int = -1) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_external_body_local_health_command_verifies_identity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    script = tmp_path / "health_provider.py"
    script.write_text(
        """
import json

print(json.dumps({
    "status": "ready",
    "provider": "mdm-local",
    "model": "humanml-encoder-512-50steps",
    "model_revision": "mdm-test-revision",
}))
""".strip()
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(
        "CUTSCENEAI_BODY_PROVIDER_COMMAND",
        json.dumps([sys.executable, str(script)]),
    )
    monkeypatch.setenv(
        "CUTSCENEAI_BODY_PROVIDER_HEALTH_COMMAND",
        json.dumps([sys.executable, str(script)]),
    )

    backend = ExternalCanonicalBodyBackend.from_environment()
    reachable, status, health = backend.probe_health(
        expected_provider="mdm-local",
        expected_model="humanml-encoder-512-50steps",
        expected_revision="mdm-test-revision",
    )

    assert reachable is True
    assert status == "ready"
    assert health["provider"] == "mdm-local"


def test_external_body_health_probe_verifies_provider_identity(monkeypatch) -> None:
    backend = ExternalCanonicalBodyBackend(
        url="https://provider.example/generate",
        health_url="https://provider.example/health",
        bearer_token="secret",
    )

    def fake_urlopen(request, timeout):
        assert request.get_header("Authorization") == "Bearer secret"
        assert timeout == 5.0
        return _HealthResponse(
            {
                "status": "ready",
                "provider": "tencent-hymotion",
                "model": "HY-Motion-1.0-Lite",
                "model_revision": "checkpoint-sha",
            }
        )

    monkeypatch.setattr(
        performance_providers_module.urllib.request,
        "urlopen",
        fake_urlopen,
    )
    reachable, status, health = backend.probe_health(
        expected_provider="tencent-hymotion",
        expected_model="HY-Motion-1.0-Lite",
        expected_revision="checkpoint-sha",
    )

    assert reachable is True
    assert status == "ready"
    assert health["provider"] == "tencent-hymotion"

    mismatch = backend.probe_health(
        expected_provider="different-provider",
        expected_model="HY-Motion-1.0-Lite",
        expected_revision="checkpoint-sha",
    )
    assert mismatch[0] is False
    assert mismatch[1] == "identity-mismatch"


def test_readiness_blocks_configured_but_unreachable_body_provider(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("CUTSCENEAI_BODY_PROVIDER_URL", "https://provider.example/generate")
    monkeypatch.setenv("CUTSCENEAI_BODY_PROVIDER_HEALTH_URL", "https://provider.example/health")
    monkeypatch.setenv("CUTSCENEAI_BODY_PROVIDER", "tencent-hymotion")
    monkeypatch.setenv("CUTSCENEAI_BODY_MODEL", "HY-Motion-1.0-Lite")
    monkeypatch.setenv("CUTSCENEAI_BODY_MODEL_REVISION", "checkpoint-sha")
    monkeypatch.setattr(
        ExternalCanonicalBodyBackend,
        "probe_health",
        lambda self, **kwargs: (False, "unreachable", {"error": "offline"}),
    )
    executor = StudioPerformanceExecutor(run_root=tmp_path / "runs")

    readiness = executor.readiness()

    assert readiness.ready is False
    body = next(item for item in readiness.providers if item.modality == "body")
    assert body.configured is False
    assert body.reachable is False
    assert body.health_status == "unreachable"
    assert any("health check failed" in issue for issue in readiness.blocking_issues)
