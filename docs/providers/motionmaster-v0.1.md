# MotionMaster body provider v0.1

CutSceneAI Studio requires a genuine body-motion provider before an arbitrary natural-language
cutscene can become a new Generated Performance Package. This integration uses MotionMaster as the
first research provider because its public inference output contains SMPL-X body parameters directly:

- `global_orient`: `[N, 3]` axis-angle root orientation
- `body_pose`: `[N, 63]` axis-angle values for 21 body joints
- `transl`: `[N, 3]` root translation

Together, the root plus 21 body joints align semantically with the 22-joint
`cutsceneai-humanoid-v1` profile. CutSceneAI converts those values into its engine-independent,
parent-local quaternion body artifact before Unity or Unreal sees the performance.

## Research status

This integration has three distinct acceptance levels:

1. **Software integration** — provider protocol, SMPL-X validation, canonical conversion, package
   assembly and tests.
2. **Provider acceptance** — the real MotionMaster checkpoint produces novel motion through the
   wrapper with recorded model revision, source timebase and coordinate convention.
3. **Engine acceptance** — the same generated canonical artifact is realized visibly in both Unity
   and Unreal without re-inference.

Do not report levels 2 or 3 as passed merely because level 1 is green.

## Upstream requirements

The public MotionMaster repository specifies Python 3.10, a CUDA-capable GPU, its Python
requirements, PyTorch3D, and the bundled `human_body_prior_repo`. The public README requires these
runtime assets:

```text
checkpoints/
  mllm_single_3b/
  tokenizer.pt
  norm_stats.npz
  smplx_model/
    SMPLX_MALE.npz

src/human_body_prior_repo/support_data/dowloads/
  V02_05/
```

The MLLM/tokenizer/statistics checkpoints are distributed by the MotionMaster authors. SMPL-X and
VPoser must be obtained separately from their official project distribution and remain subject to
their own terms. CutSceneAI deliberately does not redistribute those assets.

Upstream repository:
`https://github.com/liyanhu666666/MotionMaster`

## CutSceneAI provider contract

The Studio launches:

```text
<MotionMaster Python 3.10> tools/providers/motionmaster_provider.py
```

The wrapper reads one `cutsceneai.provider.v0.1` JSON request from stdin, calls MotionMaster
`infer.py` with the exact body-generation prompt, and returns:

```json
{
  "artifact_format": "smplx-axis-angle-v0.1",
  "artifact": {
    "fps": "...explicitly configured source fps...",
    "source_forward_axis": "+z or -z",
    "global_orient": [],
    "body_pose": [],
    "transl": []
  }
}
```

The backend validates this structure and converts it into `BodyMotionArtifact`:

```text
skeleton_profile              cutsceneai-humanoid-v1
coordinate system             right-handed, Y-up, -Z forward
root translation              reference-pose offset
joint rotation                reference-pose-relative parent-local quaternion xyzw
joint count                   22
```

The provider echoes the exact semantic request ID, provider/model/revision, prompt SHA-256,
configuration SHA-256 and seed. It also declares:

```text
generated_at_inference        true
retrieved_pre_authored_clip   false
deterministic_algorithms      false
```

The last field is intentionally conservative: the current upstream inference includes SMPL-X
fitting on CUDA and does not expose a complete deterministic-algorithm contract.

## Timebase and coordinate convention

The public MotionMaster pickle does not include an FPS field. CutSceneAI therefore refuses to guess
the source FPS. `Configure-CutSceneAI-MotionMaster.ps1` requires an explicit `-SourceFps`.

Likewise, CutSceneAI requires an explicit `-SourceForwardAxis +z|-z`. Before freezing the research
provider, run a simple locomotion prompt and verify the resulting root displacement. The accepted
timebase and axis convention become part of the provider configuration and evidence.

## Configuration

The repository includes:

```powershell
.\scripts\Configure-CutSceneAI-MotionMaster.ps1
```

The script defaults large provider files to:

```text
E:\CutSceneAI-Research\models\MotionMaster
```

so the CutSceneAI repository and the C: drive do not absorb model checkpoints.

A typical preflight, after model assets are present, is:

```powershell
.\scripts\Configure-CutSceneAI-MotionMaster.ps1 `
    -MotionMasterRoot "E:\CutSceneAI-Research\models\MotionMaster" `
    -MotionMasterPython "E:\CutSceneAI-Research\models\MotionMaster\.venv310\Scripts\python.exe" `
    -SourceFps <validated-source-fps> `
    -SourceForwardAxis <validated-axis>
```

After that passes, repeat with `-WriteEnvironment` to update `.env.local`. Existing unrelated
environment entries such as `OPENAI_API_KEY` are preserved and secrets are not printed.

The script will not activate the provider unless all required model paths exist and the provider
health probe confirms:

- required Python packages import,
- CUDA is available,
- the configured MotionMaster paths exist,
- model identity/revision configuration is internally consistent.

Restart CutSceneAI Studio after writing the environment.

## First acceptance experiment

Do not start with the full guard scene. First use:

```text
A person walks forward and stops.
```

Record:

- input prompt,
- MotionMaster git revision,
- tokenizer/statistics hashes,
- provider revision,
- raw frame count,
- accepted source FPS,
- accepted source forward axis,
- canonical package SHA-256,
- Unity native result/readback,
- Unreal native result/readback,
- visual limitations.

Only after that controlled locomotion probe passes should the original guard prompt be used:

```text
A guard walks through an abandoned hallway, hears a noise, stops,
turns toward a door, and quietly asks who is there.
```

## Cloud execution

The same Studio contract also supports an HTTPS body provider. A cloud service can expose the same
request/response protocol without changing CIR, Generated Performance Package, Unity or Unreal code.

For research integrity, a remote service must expose immutable provider/model/revision identity and
must return raw SMPL-X or canonical CutSceneAI motion rather than a pre-authored animation clip.
