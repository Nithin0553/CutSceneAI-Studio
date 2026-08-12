from __future__ import annotations

import hashlib
import json
from typing import TypedDict

from cutsceneai_cir import Project, validate_project_model
from cutsceneai_parity import compile_semantics
from cutsceneai_preview import compile_project as compile_preview

from .models import (
    BodyGenerationRequest,
    CameraGenerationRequest,
    FacialGenerationRequest,
    GenerationModelConfig,
    PerformanceCompilerConfig,
    PerformanceGenerationPlan,
)


class _RequestFields(TypedDict):
    semantic_id: str
    start_frame: int
    end_frame: int
    prompt: str
    prompt_sha256: str
    configuration_sha256: str
    seed: int
    provider: str
    model: str
    model_revision: str
    prompt_version: str


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _request_seed(experiment_seed: int, semantic_id: str) -> int:
    digest = hashlib.sha256(f"{experiment_seed}:{semantic_id}".encode()).digest()
    return int.from_bytes(digest[:4], byteorder="big", signed=False)


def _configuration_sha256(config: GenerationModelConfig) -> str:
    return _canonical_sha256(config.model_dump(mode="json"))


def _request_fields(
    *,
    semantic_id: str,
    start_frame: int,
    end_frame: int,
    prompt: str,
    config: GenerationModelConfig,
    experiment_seed: int,
) -> _RequestFields:
    return {
        "semantic_id": semantic_id,
        "start_frame": start_frame,
        "end_frame": end_frame,
        "prompt": prompt,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "configuration_sha256": _configuration_sha256(config),
        "seed": _request_seed(experiment_seed, semantic_id),
        "provider": config.provider,
        "model": config.model,
        "model_revision": config.model_revision,
        "prompt_version": config.prompt_version,
    }


def compile_generation_plan(
    project: Project,
    *,
    config: PerformanceCompilerConfig,
) -> PerformanceGenerationPlan:
    """Compile one validated CIR into deterministic model-generation requests."""

    if len(project.scenes) != 1:
        raise ValueError("Performance generation plan v0.1 requires exactly one scene.")
    validate_project_model(project)
    preview = compile_preview(project)
    semantics = compile_semantics(project)

    scene = project.scenes[0]
    preview_scene = preview.scenes[0]
    semantic_scene = semantics.scenes[0]
    source_performances = [
        performance for beat in scene.beats for performance in beat.performances
    ]
    if not (
        len(source_performances)
        == len(preview_scene.performance_cues)
        == len(semantic_scene.performance_cues)
    ):
        raise RuntimeError("CIR, preview, and parity performance cues diverged.")

    body_requests: list[BodyGenerationRequest] = []
    facial_requests: list[FacialGenerationRequest] = []
    dialogue_by_actor_and_start = {
        (cue.actor_binding_id, cue.start_frame): cue
        for cue in semantic_scene.dialogue_cues
    }
    for source, preview_cue, semantic_cue in zip(
        source_performances,
        preview_scene.performance_cues,
        semantic_scene.performance_cues,
        strict=True,
    ):
        body_id = semantic_cue.cue_id.replace("performance:", "body:", 1)
        body_prompt = (
            f"Generate novel full-body motion. Action: {source.motion.prompt} "
            f"Style: {source.motion.style or 'natural'}. "
            f"Emotion: {source.facial.emotion} at {source.facial.intensity:.2f} intensity. "
            f"Duration: {semantic_cue.end_frame - semantic_cue.start_frame} frames at "
            f"{project.settings.fps} fps. Preserve balanced foot contact and continuous motion."
        )
        body_requests.append(
            BodyGenerationRequest(
                **_request_fields(
                    semantic_id=body_id,
                    start_frame=semantic_cue.start_frame,
                    end_frame=semantic_cue.end_frame,
                    prompt=body_prompt,
                    config=config.body,
                    experiment_seed=config.experiment_seed,
                ),
                actor_binding_id=semantic_cue.actor_binding_id,
                source_performance_cue_id=semantic_cue.cue_id,
                skeleton_profile=config.skeleton_profile,
                look_at_binding_id=semantic_cue.look_at_binding_id,
            )
        )

        dialogue_cue = None
        if preview_cue.dialogue_start_frame is not None:
            dialogue_cue = dialogue_by_actor_and_start.get(
                (semantic_cue.actor_binding_id, preview_cue.dialogue_start_frame)
            )
            if dialogue_cue is None:
                raise RuntimeError("Parity semantics omitted a CIR dialogue cue.")
        face_id = semantic_cue.cue_id.replace("performance:", "face:", 1)
        dialogue_instruction = (
            f"Dialogue: {source.dialogue.text}"
            if source.dialogue is not None
            else "No dialogue; generate emotional expression only."
        )
        face_prompt = (
            f"Generate facial animation for {source.facial.emotion} emotion at "
            f"{source.facial.intensity:.2f} intensity. {dialogue_instruction} "
            f"Lip sync required: {str(source.facial.lip_sync).lower()}. "
            f"Duration: {semantic_cue.end_frame - semantic_cue.start_frame} frames at "
            f"{project.settings.fps} fps. Maintain temporal continuity and natural blinks."
        )
        facial_requests.append(
            FacialGenerationRequest(
                **_request_fields(
                    semantic_id=face_id,
                    start_frame=semantic_cue.start_frame,
                    end_frame=semantic_cue.end_frame,
                    prompt=face_prompt,
                    config=config.facial,
                    experiment_seed=config.experiment_seed,
                ),
                actor_binding_id=semantic_cue.actor_binding_id,
                source_performance_cue_id=semantic_cue.cue_id,
                source_dialogue_cue_id=(dialogue_cue.cue_id if dialogue_cue else None),
                curve_profile=config.facial_curve_profile,
                emotion=source.facial.emotion,
                emotion_intensity=source.facial.intensity,
                lip_sync=source.facial.lip_sync,
                dialogue_text=(source.dialogue.text if source.dialogue else None),
                dialogue_start_frame=preview_cue.dialogue_start_frame,
            )
        )

    camera_requests: list[CameraGenerationRequest] = []
    for source_shot, preview_cut, semantic_cut in zip(
        scene.shots,
        preview_scene.camera_cuts,
        semantic_scene.camera_cuts,
        strict=True,
    ):
        camera_id = semantic_cut.cut_id.replace("camera:", "camera-motion:", 1)
        camera_prompt = (
            f"Generate a cinematic camera trajectory. Shot: {source_shot.description} "
            f"Purpose: {source_shot.purpose.value}. Framing: "
            f"{source_shot.camera.framing.value}. Angle: {source_shot.camera.angle.value}. "
            f"Movement: {source_shot.camera.movement.value}. Lens: "
            f"{source_shot.camera.lens_mm:.1f} mm. Composition: "
            f"{source_shot.camera.composition or 'maintain clear subject framing'}. "
            f"Duration: {semantic_cut.end_frame - semantic_cut.start_frame} frames at "
            f"{project.settings.fps} fps. Avoid collisions, discontinuities, and excessive jerk."
        )
        camera_requests.append(
            CameraGenerationRequest(
                **_request_fields(
                    semantic_id=camera_id,
                    start_frame=semantic_cut.start_frame,
                    end_frame=semantic_cut.end_frame,
                    prompt=camera_prompt,
                    config=config.camera,
                    experiment_seed=config.experiment_seed,
                ),
                camera_binding_id=f"camera:{preview_cut.shot_id}",
                source_camera_cut_id=semantic_cut.cut_id,
                subject_binding_ids=semantic_cut.subject_binding_ids,
                target_binding_ids=semantic_cut.target_binding_ids,
                lens_mm=semantic_cut.lens_mm,
            )
        )

    return PerformanceGenerationPlan(
        project_id=project.id,
        cir_fingerprint_sha256=semantics.cir_fingerprint_sha256,
        fps=project.settings.fps,
        duration_frames=preview_scene.duration_frames,
        experiment_seed=config.experiment_seed,
        body_requests=body_requests,
        facial_requests=facial_requests,
        camera_requests=camera_requests,
    )
