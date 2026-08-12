# Generated Performance Package

This package defines the engine-neutral realization contract between CutSceneAI's generative
models and its Unreal and Unity adapters.

The CIR remains the source of cinematic intent. A generated performance package records the
inference-time realization of that intent:

- canonical humanoid body motion samples;
- facial and lip-sync curves;
- camera transforms and lens curves;
- dialogue WAV references;
- model revisions, prompt/configuration hashes, and seeds;
- content hashes for every artifact.

Both engine adapters must consume the same package without semantic edits. Native Unreal and Unity
assets are derived outputs and are not part of this portable contract.

Before generation, `compile_generation_plan` converts one validated CIR scene into deterministic
body, facial, and camera requests. Each request carries a stable semantic ID, exact frame window,
prompt and configuration hashes, model revision, and a seed derived from the declared experiment
seed. Repeating the compiler with the same CIR, configuration, and experiment seed is byte-for-byte
repeatable; changing only the experiment seed provides controlled diversity.

The committed Office Dialogue plan contains four body requests, four facial requests, and four
camera requests while preserving the Gate 1 CIR fingerprint. It is a model-ready request plan, not
generated animation output and not evidence that model inference has already succeeded.

The v0.1 coordinate system is right-handed, Y-up, negative-Z-forward, measured in meters. Body,
face, and camera artifacts use CutSceneAI JSON profiles so adapters can convert the same numerical
samples into engine-native tracks.

## Canonical body motion

`body-motion-v0.1.schema.json` defines the first numerical artifact boundary. A body artifact has
one sample for every frame in its owning half-open track window, so `frame_count` must equal
`end_frame - start_frame`. Root translations are global-space meters. Each sample then stores one
parent-relative `xyzw` quaternion for every joint in the fixed `cutsceneai-humanoid-v1` order.

The profile contains the 22 SMPL/HumanML3D body joints from `pelvis` through `left_wrist` and
`right_wrist`, together with fixed parent indices. Validators reject reordered joints, altered
hierarchies, missing rotations, non-contiguous frame indices, non-finite values, and non-unit
quaternions before either engine can consume the data.

`resample_body_motion` fits provider output to an exact CIR frame window. It linearly interpolates
root translation, uses shortest-path quaternion SLERP for joint rotations, preserves the source
endpoints, rounds calculated values to nine decimal places, and records the source FPS and frame
count under `resampling`. This conversion is deterministic and does not retrieve or substitute a
pre-authored motion clip.

The large model runtime, checkpoints, model datasets, SMPL assets, and real inference outputs are
intentionally deferred until the external-SSD gate in
[`docs/acceptance/generated-performance-ssd-gate.md`](../docs/acceptance/generated-performance-ssd-gate.md).
The schema, validators, resampler, adapter boundaries, package assembly, and experiment harnesses
remain normal repository work and do not depend on that storage device.

Regenerate or check the committed schema with:

```powershell
python performance\scripts\export_artifacts.py
python performance\scripts\export_artifacts.py --check
```
