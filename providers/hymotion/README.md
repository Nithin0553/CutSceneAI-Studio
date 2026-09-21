# HY-Motion body provider for CutSceneAI

CutSceneAI's body-generation boundary is intentionally engine-independent. The Studio sends one
`cutsceneai.provider.v0.1` body request to a persistent GPU service and receives a canonical
`cutsceneai-humanoid-v1` motion artifact. Unity and Unreal never consume HY-Motion-specific data.

## Why HY-Motion 1.0 Lite

The first production research integration targets Tencent HY-Motion 1.0 Lite. The official release
uses a 22-joint SMPL-H body representation whose first 22 joints match CutSceneAI's canonical joint
order exactly. HY-Motion publishes local joint rotations and global root translation at 30 FPS, so
the provider converts those values into CutSceneAI's parent-local quaternion representation and
lets the existing Generated Performance normalizer fit the result to the exact CIR frame window.

Pinned research identities:

- HY-Motion code revision:
  `4e426f5a1021cbcf7f375458c37b840ee7225229`
- model: `tencent/HY-Motion-1.0/HY-Motion-1.0-Lite`
- Hub snapshot revision: `e156af266a810d4873998baa1af44ea1962498cc`
- Lite checkpoint SHA-256 / CutSceneAI model revision:
  `d83f118f8d74db76249db86dcf9982a8229f43ef4e9fa11f683019d6230dd486`
- source representation: SMPL-H, first 22 body joints
- source FPS: 30
- CutSceneAI target: `cutsceneai-humanoid-v1`

The model remains external intellectual property and is not vendored into the CutSceneAI repository.

## Coordinate conversion

HY-Motion's public body representation is meter-scale, Y-up, with +Z as forward. CutSceneAI's
canonical body contract is meter-scale, right-handed, Y-up, with -Z as forward.

The provider therefore:

1. converts the SMPL-H axis-angle local rotations to normalized quaternions;
2. changes basis with a Z reflection, mapping quaternion `(x, y, z, w)` to
   `(-x, -y, z, w)`;
3. preserves quaternion sign continuity from frame to frame;
4. subtracts the first global translation so canonical root translation is a
   reference-pose offset;
5. maps root translation `(x, y, z)` to `(x, y, -z)`;
6. emits exactly 22 joints in canonical order;
7. leaves final 30 FPS -> CIR FPS/window fitting to CutSceneAI's existing
   endpoint-preserving linear/SLERP normalizer.

No FBX is used as the interchange representation.

## GPU service

`providers/hymotion/service.py` is a persistent FastAPI GPU service. It loads HY-Motion once,
accepts a CutSceneAI provider request, generates exactly one seeded sample, converts the generated
SMPL-H data to the canonical motion contract, and echoes the immutable request provenance.

The service deliberately serializes requests per worker because the research path values
reproducibility and clear evidence over maximum throughput.

### Container build

From the CutSceneAI repository root:

```bash
docker build -f providers/hymotion/Dockerfile -t cutsceneai-hymotion:0.1 .
```

Run it on a CUDA GPU host with model cache persisted:

```bash
docker run --rm --gpus all \
  -p 8080:8080 \
  -e CUTSCENEAI_PROVIDER_BEARER_TOKEN="<strong-random-token>" \
  -e HF_TOKEN="<optional-huggingface-token>" \
  -v hymotion-models:/models \
  cutsceneai-hymotion:0.1
```

The first cold start downloads HY-Motion 1.0 Lite and verifies the published checkpoint SHA-256.
For a research run, keep the container/model cache and record the image digest.

### Health

```bash
curl -H "Authorization: Bearer <token>" http://HOST:8080/health
```

A cold service reports `status=cold`; the first generation loads the model. A warm service reports
`status=ready`.

## Studio configuration

The CutSceneAI backend can point at any HTTPS deployment of the provider:

```dotenv
CUTSCENEAI_BODY_PROVIDER_URL=https://YOUR-GPU-ENDPOINT/generate
CUTSCENEAI_BODY_PROVIDER_HEALTH_URL=https://YOUR-GPU-ENDPOINT/health
CUTSCENEAI_BODY_PROVIDER_TOKEN=YOUR_PROVIDER_TOKEN
CUTSCENEAI_BODY_PROVIDER=tencent-hymotion
CUTSCENEAI_BODY_MODEL=HY-Motion-1.0-Lite
CUTSCENEAI_BODY_MODEL_REVISION=d83f118f8d74db76249db86dcf9982a8229f43ef4e9fa11f683019d6230dd486
CUTSCENEAI_BODY_PROMPT_VERSION=body-v0.1
CUTSCENEAI_BODY_DETERMINISTIC=false
CUTSCENEAI_BODY_PROVIDER_TIMEOUT_SECONDS=600
```

Restart Studio after changing `.env.local`. Stage 04 now verifies the health endpoint and immutable
provider/model/checkpoint identity before enabling generation. A configured endpoint that is offline
or serving a different checkpoint is displayed as unavailable rather than falsely marked ready.

Do not place the cloud token in `studio-web`, commit it, or expose it to the browser.

## Research acceptance gate

The provider is not considered accepted merely because an HTTP request succeeds. Acceptance requires
a retained run proving:

- the output was generated at inference time and was not a pre-authored clip;
- the request seed/prompt/configuration/model identity round-trips exactly;
- the canonical artifact validates as 22 joints with contiguous samples;
- the output is normalized to the exact CIR frame window;
- the resulting performance bundle hash is retained;
- the same bundle is realized in both Unity and Unreal without re-inference;
- semantic and visual acceptance are recorded separately;
- failures remain in the evidence directory.

HY-Motion's published limitations around foot sliding/floating should be treated as model-quality
limitations, not hidden by the retargeting layer.
