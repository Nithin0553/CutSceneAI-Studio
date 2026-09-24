from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
from typing import Any
import uuid

from cutsceneai_cir import Project
from cutsceneai_dialogue import DialogueEngine
from cutsceneai_performance import (
    BodyCompositionDiagnostic,
    BodyMotionArtifact,
    DialogueAudioArtifact,
    PerformanceGenerationPlan,
    ProviderArtifact,
    assemble_performance_bundle,
    canonical_scene_transforms,
    compose_body_sequence,
    decode_performance_bundle,
    diagnose_body_composition,
    compile_generation_plan,
    load_performance_bundle,
    render_body_motion,
    render_generation_plan,
    render_performance_bundle,
    render_performance_package,
    normalize_body_output,
)

from app.models.performance_runtime import (
    PerformanceGenerateRequest,
    PerformanceProviderState,
    PerformanceReadinessResponse,
    PerformanceRunRecord,
    PerformanceRunStatus,
)
from app.services.openai_speech import OpenAISpeechBackend
from app.services.performance_providers import (
    ExternalCanonicalBodyBackend,
    ProceduralCameraBackend,
    ProceduralFacialBackend,
    performance_compiler_config,
)


_REPO_ROOT = Path(__file__).resolve().parents[3]
_PERFORMANCE_RUN_ROOT = _REPO_ROOT / ".cutsceneai-studio" / "runs" / "performance"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _body_concurrency() -> int:
    raw = os.getenv("CUTSCENEAI_BODY_MAX_CONCURRENCY", "1")
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError("CUTSCENEAI_BODY_MAX_CONCURRENCY must be an integer.") from exc
    if value < 1 or value > 16:
        raise RuntimeError("CUTSCENEAI_BODY_MAX_CONCURRENCY must be between 1 and 16.")
    return value


def _safe_run_id(run_id: str) -> str:
    try:
        parsed = uuid.UUID(run_id)
    except ValueError as exc:
        raise ValueError("Invalid performance run id.") from exc
    if str(parsed) != run_id:
        raise ValueError("Performance run id must use canonical UUID format.")
    return run_id


class StudioPerformanceExecutor:
    def __init__(self, run_root: Path | None = None) -> None:
        self.run_root = run_root or _PERFORMANCE_RUN_ROOT
        self.run_root.mkdir(parents=True, exist_ok=True)

    def readiness(self, experiment_seed: int = 20260812) -> PerformanceReadinessResponse:
        config = performance_compiler_config(experiment_seed)
        body = ExternalCanonicalBodyBackend.from_environment()
        body_identity_configured = (
            all(
                value != "unconfigured"
                for value in (
                    config.body.model,
                    config.body.model_revision,
                )
            )
            and config.body.provider != "unconfigured-body"
        )
        body_transport_ready = body.configured and body_identity_configured
        body_reachable: bool | None = None
        body_health_status: str | None = None
        body_health: dict[str, object] = {}
        if body_transport_ready:
            body_reachable, body_health_status, body_health = body.probe_health(
                expected_provider=config.body.provider,
                expected_model=config.body.model,
                expected_revision=config.body.model_revision,
            )
        body_ready = body_transport_ready and body_reachable is not False
        tts_ready = bool(os.getenv("OPENAI_API_KEY"))

        providers = [
            PerformanceProviderState(
                modality="body",
                configured=body_ready,
                provider=config.body.provider,
                model=config.body.model,
                description=(
                    "Canonical external text-to-motion provider over a strict JSON command/HTTPS "
                    "contract. Configure both transport and truthful provider/model provenance."
                ),
                reachable=body_reachable,
                health_status=body_health_status,
                health=body_health,
            ),
            PerformanceProviderState(
                modality="facial",
                configured=True,
                provider=config.facial.provider,
                model=config.facial.model,
                description=(
                    "Deterministic ARKit-52 facial baseline for orchestration and ablation. "
                    "Replaceable by an external learned provider without changing the package contract."
                ),
            ),
            PerformanceProviderState(
                modality="camera",
                configured=True,
                provider=config.camera.provider,
                model=config.camera.model,
                description=(
                    "Deterministic camera baseline for portable pipeline execution and ablation."
                ),
            ),
            PerformanceProviderState(
                modality="dialogue",
                configured=tts_ready,
                provider="openai" if tts_ready else "unconfigured",
                model=os.getenv("CUTSCENEAI_TTS_MODEL", "gpt-4o-mini-tts"),
                description=(
                    "OpenAI WAV speech synthesis. Required only when the CIR contains dialogue."
                ),
            ),
        ]
        blocking: list[str] = []
        if not body.configured:
            blocking.append(
                "Configure CUTSCENEAI_BODY_PROVIDER_COMMAND or CUTSCENEAI_BODY_PROVIDER_URL."
            )
        if body.configured and not body_identity_configured:
            blocking.append(
                "Set CUTSCENEAI_BODY_PROVIDER, CUTSCENEAI_BODY_MODEL, and "
                "CUTSCENEAI_BODY_MODEL_REVISION to the actual motion generator identity."
            )
        if body_transport_ready and body_reachable is False:
            blocking.append(
                "The configured body provider health check failed"
                + (f" ({body_health_status})." if body_health_status else ".")
                + " Verify CUTSCENEAI_BODY_PROVIDER_HEALTH_URL, credentials, and provider identity."
            )
        return PerformanceReadinessResponse(
            ready=not blocking,
            providers=providers,
            blocking_issues=blocking,
        )

    async def generate(self, request: PerformanceGenerateRequest) -> PerformanceRunRecord:
        run_id = str(uuid.uuid4())
        run_dir = self.run_root / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        record = PerformanceRunRecord(
            run_id=run_id,
            project_id=request.project.id,
            status=PerformanceRunStatus.RUNNING,
            created_at_utc=_utc_now(),
            experiment_seed=request.experiment_seed,
            run_directory=self._portable_run_path(run_dir),
        )
        self._write_record(run_dir, record)
        self._write_json(
            run_dir / "input.cir.json",
            request.project.model_dump(mode="json"),
        )

        try:
            readiness = self.readiness(request.experiment_seed)
            self._write_json(
                run_dir / "provider-readiness.json",
                readiness.model_dump(mode="json"),
            )
            if not readiness.ready:
                raise RuntimeError(
                    "Generated performance is not ready: " + "; ".join(readiness.blocking_issues)
                )

            plan = compile_generation_plan(
                request.project,
                config=performance_compiler_config(request.experiment_seed),
            )
            rendered_plan = render_generation_plan(plan).encode("utf-8")
            (run_dir / "generation.plan.json").write_bytes(rendered_plan)

            record = record.model_copy(
                update={
                    "generation_plan_sha256": _sha256(rendered_plan),
                    "body_request_count": len(plan.body_requests),
                    "facial_request_count": len(plan.facial_requests),
                    "camera_request_count": len(plan.camera_requests),
                    "provider_summary": {
                        "body": f"{plan.body_requests[0].provider}/{plan.body_requests[0].model}",
                        "facial": (
                            f"{plan.facial_requests[0].provider}/{plan.facial_requests[0].model}"
                        ),
                        "camera": (
                            f"{plan.camera_requests[0].provider}/{plan.camera_requests[0].model}"
                        ),
                    },
                }
            )
            self._write_record(run_dir, record)

            body_backend = ExternalCanonicalBodyBackend.from_environment()
            facial_backend = ProceduralFacialBackend()
            camera_backend = ProceduralCameraBackend()

            semaphore = asyncio.Semaphore(_body_concurrency())

            async def body_one(item):
                async with semaphore:
                    output = await body_backend.generate_body(item)
                    self._persist_body_provider_output(run_dir, output)
                    return output

            # Dialogue is comparatively cheap and has strict timing constraints. Validate it
            # before expensive body inference so bad audio cannot waste a full GPU generation run.
            audio_outputs, dialogue_manifest = await self._dialogue_outputs(request, plan)

            body_outputs = await asyncio.gather(*(body_one(item) for item in plan.body_requests))
            facial_outputs = await asyncio.gather(
                *(facial_backend.generate_facial(item) for item in plan.facial_requests)
            )
            camera_outputs = await asyncio.gather(
                *(camera_backend.generate_camera(item) for item in plan.camera_requests)
            )

            bundle = assemble_performance_bundle(
                plan,
                body_outputs=body_outputs,
                facial_outputs=facial_outputs,
                camera_outputs=camera_outputs,
                audio_outputs=audio_outputs,
                project=request.project,
            )
            bundle_data = render_performance_bundle(bundle)
            bundle_sha = _sha256(bundle_data)

            (run_dir / "performance.bundle.zip").write_bytes(bundle_data)
            (run_dir / "performance.package.json").write_text(
                render_performance_package(bundle.package),
                encoding="utf-8",
                newline="\n",
            )
            if dialogue_manifest is not None:
                self._write_json(
                    run_dir / "dialogue.manifest.json",
                    dialogue_manifest,
                )

            self._write_json(
                run_dir / "provider-output-summary.json",
                {
                    "body": self._provider_output_summary(body_outputs),
                    "facial": self._provider_output_summary(facial_outputs),
                    "camera": self._provider_output_summary(camera_outputs),
                    "bundle_sha256": bundle_sha,
                },
            )

            warnings: list[str] = []
            if dialogue_manifest is not None:
                raw_warnings = dialogue_manifest.get("warnings")
                if isinstance(raw_warnings, list):
                    for item in raw_warnings:
                        if isinstance(item, dict) and item.get("message"):
                            warnings.append(str(item["message"]))

            record = record.model_copy(
                update={
                    "status": PerformanceRunStatus.SUCCEEDED,
                    "completed_at_utc": _utc_now(),
                    "bundle_sha256": bundle_sha,
                    "bundle_byte_length": len(bundle_data),
                    "audio_track_count": len(bundle.package.audio_tracks),
                    "warnings": warnings,
                }
            )
            self._write_record(run_dir, record)
            return record
        except Exception as exc:
            failure_message = f"{type(exc).__name__}: {exc}"
            failed = record.model_copy(
                update={
                    "status": PerformanceRunStatus.FAILED,
                    "completed_at_utc": _utc_now(),
                    "error": failure_message,
                }
            )
            self._write_record(run_dir, failed)
            (run_dir / "failure.txt").write_text(
                failure_message + "\n",
                encoding="utf-8",
                newline="\n",
            )
            return failed

    async def _dialogue_outputs(
        self,
        request: PerformanceGenerateRequest,
        plan: PerformanceGenerationPlan,
    ) -> tuple[list[DialogueAudioArtifact], dict[str, object] | None]:
        dialogue_requests = [
            item for item in plan.facial_requests if item.source_dialogue_cue_id is not None
        ]
        if not dialogue_requests:
            return [], None
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError(
                "This CIR contains dialogue but OPENAI_API_KEY is not configured for WAV speech."
            )

        dialogue = await DialogueEngine(OpenAISpeechBackend()).synthesize_project(
            request.project,
            default_voice=request.default_voice,
            voices=request.voices,
            replace_existing=False,
        )
        clips = {
            (f"actor:{clip.character_id}", clip.start_frame): clip
            for clip in dialogue.manifest.clips
        }
        outputs: list[DialogueAudioArtifact] = []
        for facial_request in dialogue_requests:
            dialogue_cue_id = facial_request.source_dialogue_cue_id
            dialogue_start_frame = facial_request.dialogue_start_frame
            if dialogue_cue_id is None or dialogue_start_frame is None:
                raise RuntimeError(
                    "Dialogue-linked facial request is missing its cue or start frame: "
                    f"{facial_request.semantic_id}"
                )
            key = (
                facial_request.actor_binding_id,
                dialogue_start_frame,
            )
            clip = clips.get(key)
            if clip is None:
                raise RuntimeError(
                    "Synthesized dialogue could not be matched to performance request "
                    f"'{facial_request.semantic_id}'."
                )
            if clip.end_frame > facial_request.end_frame:
                raise RuntimeError(
                    f"Dialogue '{facial_request.source_dialogue_cue_id}' exceeds its semantic "
                    "performance window. Revise timing, shorten the line, or increase the beat."
                )
            outputs.append(
                DialogueAudioArtifact(
                    dialogue_cue_id=dialogue_cue_id,
                    actor_binding_id=facial_request.actor_binding_id,
                    start_frame=clip.start_frame,
                    end_frame=clip.end_frame,
                    data=dialogue.audio_files[clip.relative_path],
                )
            )
        return outputs, dialogue.manifest.model_dump(mode="json")

    def get_run(self, run_id: str) -> PerformanceRunRecord:
        path = self.run_root / _safe_run_id(run_id) / "run.json"
        if not path.exists():
            raise ValueError(f"Unknown performance run '{run_id}'.")
        try:
            return PerformanceRunRecord.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"Performance run '{run_id}' is unreadable.") from exc

    def list_runs(self, limit: int = 50) -> list[PerformanceRunRecord]:
        if limit < 1 or limit > 200:
            raise ValueError("Performance run limit must be between 1 and 200.")
        records: list[PerformanceRunRecord] = []
        for path in self.run_root.glob("*/run.json"):
            try:
                records.append(
                    PerformanceRunRecord.model_validate_json(path.read_text(encoding="utf-8"))
                )
            except (OSError, ValueError):
                continue
        records.sort(key=lambda item: item.created_at_utc, reverse=True)
        return records[:limit]

    def bundle_bytes(self, run_id: str) -> bytes:
        record = self.get_run(run_id)
        if record.status is not PerformanceRunStatus.SUCCEEDED:
            raise ValueError("Performance bundle is unavailable because the run did not succeed.")
        path = self.run_root / run_id / "performance.bundle.zip"
        if not path.exists():
            raise ValueError("Performance run is missing its bundle.")
        data = path.read_bytes()
        if record.bundle_sha256 is None or _sha256(data) != record.bundle_sha256:
            raise ValueError("Performance bundle SHA-256 no longer matches its run record.")
        return data

    def _raw_normalized_body_outputs(
        self,
        run_id: str,
        plan: PerformanceGenerationPlan,
    ) -> dict[str, Any]:
        run_dir = self.run_root / _safe_run_id(run_id)
        request_by_id = {
            request.semantic_id: request for request in plan.body_requests
        }
        output_dir = run_dir / "body-provider-outputs"
        if not output_dir.is_dir():
            raise ValueError("Performance run is missing persisted body provider outputs.")

        raw_normalized: dict[str, Any] = {}
        for metadata_path in sorted(output_dir.glob("*.metadata.json")):
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError(
                    f"Body provider metadata is unreadable: {metadata_path.name}"
                ) from exc
            semantic_id = str(metadata.get("request_semantic_id") or "")
            if semantic_id not in request_by_id:
                continue
            artifact_name = str(metadata.get("artifact_file") or "")
            artifact_path = output_dir / artifact_name
            if not artifact_name or not artifact_path.is_file():
                raise ValueError(
                    f"Body provider metadata '{metadata_path.name}' references a missing artifact."
                )
            try:
                artifact = BodyMotionArtifact.model_validate_json(
                    artifact_path.read_text(encoding="utf-8")
                )
            except (OSError, ValueError) as exc:
                raise ValueError(
                    f"Body provider artifact is unreadable: {artifact_path.name}"
                ) from exc

            provider_output = ProviderArtifact(
                request_semantic_id=semantic_id,
                artifact=artifact,
                provider=str(metadata["provider"]),
                model=str(metadata["model"]),
                model_revision=str(metadata["model_revision"]),
                prompt_sha256=str(metadata["prompt_sha256"]),
                configuration_sha256=str(metadata["configuration_sha256"]),
                seed=int(metadata["seed"]),
                generated_at_inference=bool(metadata["generated_at_inference"]),
                retrieved_pre_authored_clip=bool(metadata["retrieved_pre_authored_clip"]),
                deterministic_algorithms=bool(metadata["deterministic_algorithms"]),
            )
            raw_normalized[semantic_id] = normalize_body_output(
                request_by_id[semantic_id],
                provider_output,
                target_fps=plan.fps,
            )

        missing = sorted(set(request_by_id) - set(raw_normalized))
        if missing:
            raise ValueError(
                "Performance run is missing persisted body provider outputs: "
                + ", ".join(missing)
            )
        return raw_normalized

    def body_composition_diagnostic(self, run_id: str) -> BodyCompositionDiagnostic:
        record = self.get_run(run_id)
        if record.status is not PerformanceRunStatus.SUCCEEDED:
            raise ValueError(
                "Body composition diagnostic is unavailable because the run did not succeed."
            )
        run_dir = self.run_root / _safe_run_id(run_id)
        bundle = load_performance_bundle(self.bundle_bytes(run_id))
        decoded = decode_performance_bundle(bundle)
        raw_normalized = self._raw_normalized_body_outputs(run_id, bundle.plan)

        diagnostic = diagnose_body_composition(
            bundle.plan,
            raw_normalized,
            decoded.body_artifacts,
        )
        self._write_json(
            run_dir / "body-composition-diagnostic.json",
            diagnostic.model_dump(mode="json"),
        )
        return diagnostic

    def body_composition_preview(self, run_id: str) -> BodyCompositionDiagnostic:
        record = self.get_run(run_id)
        if record.status is not PerformanceRunStatus.SUCCEEDED:
            raise ValueError(
                "Body composition preview is unavailable because the run did not succeed."
            )
        run_dir = self.run_root / _safe_run_id(run_id)
        bundle = load_performance_bundle(self.bundle_bytes(run_id))
        raw_normalized = self._raw_normalized_body_outputs(run_id, bundle.plan)

        input_path = run_dir / "input.cir.json"
        if not input_path.is_file():
            raise ValueError("Performance run is missing its scene-conditioned CIR input.")
        try:
            project = Project.model_validate_json(input_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError("Performance run scene-conditioned CIR is unreadable.") from exc
        if project.id != bundle.plan.project_id:
            raise ValueError("Performance run CIR no longer matches its generation plan.")

        recomposed = compose_body_sequence(
            bundle.plan.body_requests,
            raw_normalized,
            scene_transforms=canonical_scene_transforms(project),
        )
        diagnostic = diagnose_body_composition(
            bundle.plan,
            raw_normalized,
            {
                semantic_id: normalized.artifact
                for semantic_id, normalized in recomposed.items()
            },
        )
        self._write_json(
            run_dir / "body-composition-preview.json",
            diagnostic.model_dump(mode="json"),
        )
        return diagnostic

    @staticmethod
    def _persist_body_provider_output(
        run_dir: Path,
        output: ProviderArtifact[Any],
    ) -> None:
        output_dir = run_dir / "body-provider-outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        digest = _sha256(output.request_semantic_id.encode("utf-8"))[:12]
        stem = f"{digest}"
        (output_dir / f"{stem}.motion.json").write_text(
            render_body_motion(output.artifact),
            encoding="utf-8",
            newline="\n",
        )
        metadata = {
            "request_semantic_id": output.request_semantic_id,
            "provider": output.provider,
            "model": output.model,
            "model_revision": output.model_revision,
            "prompt_sha256": output.prompt_sha256,
            "configuration_sha256": output.configuration_sha256,
            "seed": output.seed,
            "generated_at_inference": output.generated_at_inference,
            "retrieved_pre_authored_clip": output.retrieved_pre_authored_clip,
            "deterministic_algorithms": output.deterministic_algorithms,
            "artifact_file": f"{stem}.motion.json",
        }
        (output_dir / f"{stem}.metadata.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    @staticmethod
    def _provider_output_summary(
        outputs: list[ProviderArtifact[Any]],
    ) -> list[dict[str, object]]:
        return [
            {
                "request_semantic_id": item.request_semantic_id,
                "provider": item.provider,
                "model": item.model,
                "model_revision": item.model_revision,
                "prompt_sha256": item.prompt_sha256,
                "configuration_sha256": item.configuration_sha256,
                "seed": item.seed,
                "generated_at_inference": item.generated_at_inference,
                "retrieved_pre_authored_clip": item.retrieved_pre_authored_clip,
                "deterministic_algorithms": item.deterministic_algorithms,
            }
            for item in outputs
        ]

    @staticmethod
    def _portable_run_path(run_dir: Path) -> str:
        try:
            return run_dir.relative_to(_REPO_ROOT).as_posix()
        except ValueError:
            return run_dir.as_posix()

    @staticmethod
    def _write_json(path: Path, value: object) -> None:
        path.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    def _write_record(self, run_dir: Path, record: PerformanceRunRecord) -> None:
        target = run_dir / "run.json"
        temp = run_dir / "run.json.tmp"
        temp.write_text(
            record.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        temp.replace(target)
