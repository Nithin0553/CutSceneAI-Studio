# Retained MDM body provider v0.1

CutSceneAI already has a validated Human Motion Diffusion Model (MDM) research runtime under the
external research root. The Studio body-provider integration reuses that retained runtime rather than
downloading or installing a second motion model.

## Evidence boundary

The retained runtime assets and prior S02 experiments establish that the selected MDM checkpoint can
produce HumanML3D joint-position motion. They do not, by themselves, prove that an arbitrary Studio
prompt now realizes correctly in Unity or Unreal. This provider closes the software boundary:

```text
CIR body performance request
    -> MDM text-to-motion inference
    -> HumanML XYZ positions
    -> CutSceneAI canonical 22-joint motion
    -> Generated Performance Package
    -> Unity / Unreal native realization
```

A new prompt is accepted only after inference, canonical conversion, package assembly, native engine
realization, readback, and visual review all complete.

## Retained checkpoint

The expected research checkpoint is:

```text
E:\CutSceneAI-Research\models\mdm\checkpoints\humanml-encoder-512-50steps\model000750000.pt
```

Expected SHA-256:

```text
0fbdc8547c8f262b8838645586790b55f983d90db3bb7ed58e4b5d49429587ca
```

The provider refuses to run when that hash changes. This prevents a floating or silently replaced
checkpoint from being reported as the same experiment.

## Provider protocol

The local provider command is:

```text
<retained MDM Python> tools/providers/mdm_humanml_provider.py
```

It consumes one `cutsceneai.provider.v0.1` body request from stdin and invokes the official MDM
HumanML text-to-motion generation entry point with:

- the exact motion text derived from the CIR performance cue;
- one sample;
- one repetition;
- the request seed;
- the requested duration;
- the hash-locked checkpoint;
- a fresh temporary output directory.

The wrapper validates the official `results.npy` structure and emits
`humanml-xyz-v0.1` containing the generated `[frames, 22, 3]` positions. Direct `.npy` engine
import remains prohibited.

## Canonicalization

`cutsceneai_performance.humanml_xyz_to_canonical` converts the 22 HumanML joint positions to the
engine-independent body contract.

The conversion records a new repository implementation identifier:

```text
cutsceneai-position-to-parent-local-swing-v0.2
```

It reconstructs swing-only parent-local rotations geometrically. XYZ joint positions do not encode
twist, so this limitation must remain visible in quality evaluation. The converter also rebases root
translation to frame zero and applies the established HumanML +Z-forward to CutSceneAI -Z-forward
coordinate boundary.

MDM HumanML generation is 20 FPS. The Generated Performance Package normalizer resamples the
canonical result to the CIR timebase and exact request frame count.

## Activation

Use:

```powershell
.\scripts\Configure-CutSceneAI-MDM.ps1
```

The script:

1. verifies the retained checkpoint hash;
2. verifies the retained CLIP hash when present;
3. discovers the existing MDM source checkout;
4. discovers an existing Python environment that can import the retained MDM runtime;
5. runs the provider health probe;
6. makes no reinstall attempt;
7. optionally writes the provider configuration to `.env.local`.

After a clean preflight:

```powershell
.\scripts\Configure-CutSceneAI-MDM.ps1 -WriteEnvironment
```

Restart Studio after activation.

The local provider is configured with body concurrency 1 because separate command-provider
invocations each load the motion model. This favors reproducible operation on the retained
single-GPU research environment over throughput.

## First acceptance sequence

Do not use the full dialogue scene as the first model acceptance. Start with a bounded body-motion
probe such as:

```text
A person walks forward and stops.
```

For the first new inference preserve:

- complete CIR;
- MDM source revision;
- checkpoint SHA-256;
- seed;
- exact prompt;
- raw HumanML frame count;
- provider output provenance;
- canonical/package SHA-256;
- Unity native importer/readback;
- Unreal native importer/readback;
- visual limitations.

Only after that controlled action passes should the current guard scene be used for the full
multi-track workflow.
