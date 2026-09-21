from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path
import re
import sys
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from huggingface_hub import snapshot_download
from pydantic import BaseModel, ConfigDict, Field

from providers.hymotion.canonical import convert_hymotion_smplh_to_cutsceneai


HY_MOTION_CODE_REVISION = "4e426f5a1021cbcf7f375458c37b840ee7225229"
HY_MOTION_MODEL_REPO = "tencent/HY-Motion-1.0"
HY_MOTION_MODEL_NAME = "HY-Motion-1.0-Lite"
HY_MOTION_LITE_CHECKPOINT_SHA256 = (
    "d83f118f8d74db76249db86dcf9982a8229f43ef4e9fa11f683019d6230dd486"
)
HY_MOTION_SOURCE_FPS = 30


class ProviderModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class BodyRequest(ProviderModel):
    semantic_id: str
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)
    prompt: str
    prompt_sha256: str
    configuration_sha256: str
    seed: int = Field(ge=0, le=2**32 - 1)
    provider: str
    model: str
    model_revision: str
    prompt_version: str
    actor_binding_id: str
    source_performance_cue_id: str
    skeleton_profile: str
    look_at_binding_id: str | None = None


class ProviderEnvelope(ProviderModel):
    protocol_version: str
    kind: str
    request: BodyRequest


class ProviderResponse(ProviderModel):
    request_semantic_id: str
    provider: str
    model: str
    model_revision: str
    prompt_sha256: str
    configuration_sha256: str
    seed: int
    generated_at_inference: bool = True
    retrieved_pre_authored_clip: bool = False
    deterministic_algorithms: bool
    artifact: dict[str, Any]


app = FastAPI(
    title="CutSceneAI HY-Motion Provider",
    version="0.1.0",
    docs_url="/docs",
)

_runtime: Any | None = None
_runtime_lock = asyncio.Lock()
_model_path: Path | None = None


def _bearer_token() -> str | None:
    value = os.getenv("CUTSCENEAI_PROVIDER_BEARER_TOKEN")
    return value.strip() if value and value.strip() else None


def _authorize(authorization: str | None) -> None:
    expected = _bearer_token()
    if expected is None:
        return
    if authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="Invalid provider bearer token.")


def _target_fps(prompt: str) -> int:
    matches = re.findall(r"\bat\s+(\d{1,3})\s+fps\b", prompt, re.IGNORECASE)
    if not matches:
        return 24
    return max(1, min(240, int(matches[-1])))


def _motion_prompt(prompt: str) -> str:
    action = re.search(
        r"Action:\s*(.+?)\s+Style:",
        prompt,
        flags=re.IGNORECASE | re.DOTALL,
    )
    style = re.search(
        r"Style:\s*(.+?)\.\s+Emotion:",
        prompt,
        flags=re.IGNORECASE | re.DOTALL,
    )
    emotion = re.search(
        r"Emotion:\s*(.+?)\.\s+Duration:",
        prompt,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if action is None:
        cleaned = re.sub(r"\s+", " ", prompt).strip()
        return cleaned[:500]

    parts = [action.group(1).strip()]
    if style and style.group(1).strip().lower() != "natural":
        parts.append(f"Style: {style.group(1).strip()}.")
    if emotion:
        emotion_text = emotion.group(1).strip()
        emotion_text = re.sub(r"\s+at\s+[0-9.]+\s+intensity$", "", emotion_text)
        if emotion_text and emotion_text.lower() not in {"neutral", "none"}:
            parts.append(f"Emotion: {emotion_text}.")
    return " ".join(parts)[:500]


def _resolve_hymotion_root() -> Path:
    configured = os.getenv("HY_MOTION_ROOT")
    if not configured:
        raise RuntimeError(
            "HY_MOTION_ROOT must point to the checked-out official HY-Motion-1.0 repository."
        )
    root = Path(configured).expanduser().resolve()
    if not (root / "hymotion").is_dir():
        raise RuntimeError(
            f"HY_MOTION_ROOT does not contain the hymotion package: {root}"
        )
    return root


def _resolve_model_path() -> Path:
    configured = os.getenv("HY_MOTION_MODEL_PATH")
    if configured:
        candidate = Path(configured).expanduser().resolve()
    else:
        cache_root = Path(
            os.getenv("HY_MOTION_MODEL_CACHE", "/models/tencent")
        ).expanduser()
        local_dir = snapshot_download(
            repo_id=HY_MOTION_MODEL_REPO,
            revision=os.getenv("HY_MOTION_MODEL_REVISION", "main"),
            allow_patterns=f"{HY_MOTION_MODEL_NAME}/*",
            local_dir=str(cache_root),
            token=os.getenv("HF_TOKEN") or None,
        )
        candidate = Path(local_dir) / HY_MOTION_MODEL_NAME

    config_path = candidate / "config.yml"
    checkpoint_path = candidate / "latest.ckpt"
    if not config_path.exists() or not checkpoint_path.exists():
        raise RuntimeError(
            f"HY-Motion model path must contain config.yml and latest.ckpt: {candidate}"
        )
    if os.getenv("HY_MOTION_VERIFY_CHECKPOINT_SHA256", "true").lower() not in {
        "0",
        "false",
        "no",
    }:
        digest = hashlib.sha256()
        with checkpoint_path.open("rb") as handle:
            for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
                digest.update(block)
        actual = digest.hexdigest()
        if actual != HY_MOTION_LITE_CHECKPOINT_SHA256:
            raise RuntimeError(
                "HY-Motion Lite checkpoint SHA-256 mismatch. "
                f"Expected {HY_MOTION_LITE_CHECKPOINT_SHA256}, got {actual}."
            )
    return candidate


def _load_runtime() -> Any:
    global _runtime, _model_path
    if _runtime is not None:
        return _runtime

    root = _resolve_hymotion_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from hymotion.utils.t2m_runtime import T2MRuntime

    _model_path = _resolve_model_path()
    device_ids_raw = os.getenv("HY_MOTION_DEVICE_IDS", "0")
    device_ids = [
        int(value.strip()) for value in device_ids_raw.split(",") if value.strip()
    ]
    _runtime = T2MRuntime(
        config_path=str(_model_path / "config.yml"),
        ckpt_name=str(_model_path / "latest.ckpt"),
        device_ids=device_ids,
        disable_prompt_engineering=True,
    )
    return _runtime


def _generate_sync(request: BodyRequest) -> ProviderResponse:
    runtime = _load_runtime()
    target_fps = _target_fps(request.prompt)
    target_frames = request.end_frame - request.start_frame
    duration = target_frames / target_fps
    if not 0.5 <= duration <= 12.0:
        raise RuntimeError(
            f"HY-Motion supports 0.5-12 second requests; received {duration:.3f}s."
        )

    prompt = _motion_prompt(request.prompt)
    output_dir = os.getenv("HY_MOTION_OUTPUT_DIR", "/tmp/cutsceneai-hymotion")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    _, _, model_output = runtime.generate_motion(
        text=prompt,
        seeds_csv=str(request.seed),
        duration=duration,
        cfg_scale=float(os.getenv("HY_MOTION_CFG_SCALE", "5.0")),
        output_format="dict",
        output_dir=output_dir,
        output_filename=request.semantic_id.replace(":", "_"),
        original_text=prompt,
        use_special_game_feat=True,
    )

    rot6d = model_output["rot6d"]
    transl = model_output["transl"]
    if rot6d.shape[0] != 1 or transl.shape[0] != 1:
        raise RuntimeError("HY-Motion provider expected exactly one generated sample.")

    from hymotion.pipeline.body_model import construct_smpl_data_dict

    smpl = construct_smpl_data_dict(
        rot6d[0].detach().cpu(),
        transl[0].detach().cpu(),
    )
    poses = smpl["poses"].tolist()
    translations = smpl["trans"].tolist()
    artifact = convert_hymotion_smplh_to_cutsceneai(
        poses,
        translations,
        source_fps=HY_MOTION_SOURCE_FPS,
    )

    return ProviderResponse(
        request_semantic_id=request.semantic_id,
        provider=request.provider,
        model=request.model,
        model_revision=request.model_revision,
        prompt_sha256=request.prompt_sha256,
        configuration_sha256=request.configuration_sha256,
        seed=request.seed,
        deterministic_algorithms=os.getenv(
            "HY_MOTION_DETERMINISTIC_ALGORITHMS",
            "false",
        ).lower()
        in {"1", "true", "yes"},
        artifact=artifact,
    )


@app.get("/health")
async def health(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _authorize(authorization)
    return {
        "status": "ready" if _runtime is not None else "cold",
        "provider": "tencent-hymotion",
        "model": HY_MOTION_MODEL_NAME,
        "code_revision": HY_MOTION_CODE_REVISION,
        "checkpoint_sha256": HY_MOTION_LITE_CHECKPOINT_SHA256,
        "source_fps": HY_MOTION_SOURCE_FPS,
        "model_loaded": _runtime is not None,
    }


@app.post("/generate", response_model=ProviderResponse)
async def generate(
    envelope: ProviderEnvelope,
    authorization: str | None = Header(default=None),
) -> ProviderResponse:
    _authorize(authorization)
    if envelope.protocol_version != "cutsceneai.provider.v0.1":
        raise HTTPException(
            status_code=422, detail="Unsupported CutSceneAI provider protocol."
        )
    if envelope.kind != "body_motion":
        raise HTTPException(
            status_code=422, detail="HY-Motion provider only generates body motion."
        )
    if envelope.request.skeleton_profile != "cutsceneai-humanoid-v1":
        raise HTTPException(status_code=422, detail="Unsupported skeleton profile.")

    async with _runtime_lock:
        try:
            return await asyncio.to_thread(_generate_sync, envelope.request)
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"{type(exc).__name__}: {exc}",
            ) from exc


def main() -> None:
    import uvicorn

    uvicorn.run(
        "providers.hymotion.service:app",
        host=os.getenv("CUTSCENEAI_PROVIDER_HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8080")),
        workers=1,
    )


if __name__ == "__main__":
    main()
