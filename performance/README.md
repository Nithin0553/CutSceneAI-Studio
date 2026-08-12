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

## Canonical facial and lip-sync curves

`facial-curves-v0.1.schema.json` defines a fixed `arkit-52` profile. Every frame contains exactly
52 blendshape weights in the schema-declared order, with each value constrained to the inclusive
range `[0, 1]`. Validators reject reordered curve names, missing or extra weights, non-contiguous
frame indices, frame-count mismatches, and non-finite values.

The owning generated-performance track binds the artifact to its actor and performance cue and,
when dialogue drives lip sync, to the exact dialogue cue. `resample_facial_curves` linearly fits
provider weights to that track's exact frame window, preserves both endpoints, rounds calculated
values to nine decimal places, and records the source sampling metadata. Provider-specific output
such as Audio2Face curves must be normalized to this contract before either engine adapter sees it.

## Canonical camera curves

`camera-curves-v0.1.schema.json` stores one perspective-camera sample per frame: world-space
position in meters, orientation as a unit `xyzw` quaternion, and focal length in millimeters.
Artifacts explicitly carry the right-handed, Y-up, negative-Z-forward coordinate convention plus
sensor width and height, so both engines derive the same field of view instead of assuming
different filmbacks.

`resample_camera_curves` linearly interpolates position and focal length, applies shortest-path
quaternion SLERP to orientation, preserves endpoints and custom sensor dimensions, and records the
source FPS and frame count. The owning track binds the artifact to the exact camera cut and camera
binding from the unchanged generation plan.

## Provider normalization

`BodyGenerationBackend`, `FacialGenerationBackend`, and `CameraGenerationBackend` are narrow async
protocols for model-specific adapters. A backend returns canonical source samples inside a
`ProviderArtifact`, together with the exact semantic ID, provider/model revision, prompt and
configuration hashes, seed, and inference-origin flags it used.

The modality normalizers reject any request-metadata mismatch, output not generated at inference
time, retrieved pre-authored clip, or incompatible skeleton/curve profile. Accepted samples are
then fitted to the request's exact frame count and plan FPS. This keeps provider parsing at the
edge while one validated numerical contract reaches packaging and both engine adapters.

## Deterministic package assembly

`assemble_performance_bundle` requires exactly one body, facial, and camera result for every
generation request, plus one PCM WAV for every referenced dialogue cue. It creates stable artifact
paths, hashes the rendered bytes, calculates byte lengths, validates WAV-derived frame timing, and
builds one package manifest without changing the generation plan or CIR fingerprint.

`render_performance_bundle` emits a byte-for-byte deterministic ZIP containing
`generation.plan.json`, `performance.package.json`, and exactly the referenced body, face, camera,
and audio files. `load_performance_bundle` treats that ZIP as untrusted input: it enforces entry and
expanded-size limits, safe POSIX paths, supported compression, exact entry sets, contract parsing,
artifact hashes, provenance, identities, profiles, coordinate spaces, frame counts, and audio
timing before returning a bundle to an engine adapter.

The automated bundle tests use small synthetic numerical and PCM fixtures. They validate the
contract and failure behavior only; they are not evidence that a body, facial, or camera model has
run successfully.

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
