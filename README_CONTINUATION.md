# CutSceneAI Studio continuation handoff

Last updated: 2026-08-15

This file is the starting point for continuing the CutSceneAI Studio research project in a new
chat. Read it before changing code, downloading models, or running an engine acceptance gate.

## Current Git state

- Repository: `Nithin0553/CutSceneAI-Studio`
- Working branch: `agent/cross-engine-parity-v0.1`
- Latest implementation baseline before this handoff:
  `31a5a107bc73615acaddc4507bd688d806c0a50c`
- Baseline commit title: `Add native generated performance realization harnesses`
- GitHub Actions: CI run 123 passed on Python 3.11, 3.12, and 3.13.
- The Windows checkout successfully fast-forwarded from `6c5f8ab` to `31a5a10`.

Use direct branch commits and pushes. Do not open a pull request and do not deliver ZIP copies;
the user pulls changes from Git. The root `build/` directory contains local generated artifacts,
is untracked, and must not be deleted, modified, or committed.

## Research goal

The paper must demonstrate a full animated cutscene in both Unreal Engine and Unity from one
unchanged portable source. Final paper evidence must use real generated body motion, facial and
lip-sync curves, camera motion, and synchronized audio. AI-generated performance is part of this
paper, not deferred future work.

The fixed evaluation dimensions are:

1. Reliability
2. Repeatability
3. Portability
4. Native realization

Synthetic fixtures validate software behavior only. They cannot be presented as model, editor, or
paper evidence.

## Completed work

### Foundation and baseline cutscene

- CIR v0.1 contracts, validation, schemas, FastAPI endpoints, and deterministic serialization.
- Director, Preview, Dialogue Engine, Unreal adapters, and Unity Timeline adapter.
- Portable dialogue bundle with verified WAV timing, hashes, provenance, and AI-voice disclosure.
- Baseline Unreal office-dialogue sequence with Mina and Arjun, animation sections, audio, camera
  cuts, persistence after restart, and a complete 432-frame Movie Render Queue render.

### Cross-engine parity

- One unchanged CIR is compiled for Unreal and Unity with source hashes and a canonical semantic
  fingerprint.
- Typed engine readbacks and restart-safe readback exporters.
- Automatic comparison of entities, performance timing, dialogue, cameras, and realization.
- Strict `cutsceneai-parity verify` support with both engines required and frame tolerance recorded.

### Generated Performance Package v0.1

- Deterministic CIR-to-generation-plan compiler.
- Canonical 22-joint body-motion schema, validation, reference-pose semantics, and resampling.
- Canonical ARKit-52 facial/lip-sync schema, validation, and resampling.
- Canonical camera transform, filmback, focal-length schema, validation, and resampling.
- Provider-neutral body, facial, and camera interfaces with provenance and exact-frame checks.
- Deterministic package assembly and strict untrusted ZIP loading, including hashes, entry sets,
  safe paths, size limits, and audio timing.
- Unreal 5.8 and Unity 6 mappings for body, face, camera, and audio.

### Experiment and evidence gates

- Fixed paper design: 10 scenes by 5 seeds, giving 50 first-pass attempts.
- Failed attempts remain in the denominator.
- Three clean runs are required for each selected repeatability case.
- One unchanged Generated Performance bundle must be realized in both engines.
- Reliability, repeatability, portability, and native-realization ledgers and aggregate reports.
- Harness mode is always non-publishable; paper mode requires retained real inference and editor
  evidence.

### Native realization automation

- `cutsceneai-unity-native` compiles a Unity 6000.0/Timeline 1.8.12 harness.
- `cutsceneai-unreal-native` compiles an Unreal Engine 5.8.0 harness.
- Typed native-target schemas identify real prefab, Animator, facial renderer, Skeletal Mesh, map,
  sequence, and render destinations.
- Unity automation performs import/save followed by restart/readback/render in a second process.
- Unreal automation performs import/save, restart/readback, and Movie Render Queue in three distinct
  processes.
- Both harnesses refuse replacement, validate required bones and ARKit-52 targets, preserve the
  unchanged bundle, render every expected frame, and collect hash-anchored evidence.
- Native evidence validation requires all four modalities, exact section and frame counts, distinct
  process IDs, zero placeholders, zero warnings/errors, and matching source artifact hashes.

## Last verified repository gates

- Ruff lint and formatting: passed.
- Mypy: passed across 93 source files.
- All seven generated schema/artifact drift checks: passed.
- Full repository suite: 504 tests passed.
- Total branch-aware coverage: 97.46%, above the required 95%.
- Generated Performance suite: 185 tests with 100% statement and branch coverage.
- GitHub Actions run 123: passed for Python 3.11, 3.12, and 3.13.

## Current machine information

The last reported Windows environment was:

- Python 3.12.10 in `.venv3.12`;
- NVIDIA GeForce RTX 3050 Laptop GPU;
- 4 GB VRAM;
- NVIDIA driver 581.95;
- driver-reported CUDA compatibility 13.0;
- Unreal Engine 5.8.0 installed.

Do not infer a PyTorch CUDA build from the driver-reported CUDA version. Select and verify the
runtime only when the SSD setup begins. The 4 GB VRAM limit must be considered when choosing GPU,
CPU-offload, or CPU inference settings.

## Mandatory external-SSD stop condition

All non-SSD implementation work is complete. The external SSD is now mandatory.

Do not download checkpoints, model datasets, SMPL assets, or large runtime caches to the system
drive. Do not begin real inference until the user supplies the SSD's explicit drive letter and
target directory.

The first action after the SSD is connected is to verify:

1. Exact drive letter and absolute target path.
2. Available and total capacity.
3. Filesystem type.
4. Read and write access.
5. A dedicated directory layout for environments, Hugging Face/Torch caches, checkpoints, model
   assets, generated packages, engine evidence, renders, and experiment reports.

Only after those checks should the next chat install the CUDA/PyTorch model environment, obtain the
official MDM checkpoint and HumanML3D/SMPL dependencies, and run retained real inference.

## Next execution phase

After the SSD passes verification:

1. Create the SSD directory layout and configure every relevant cache/output environment variable
   to use explicit SSD paths.
2. Install and smoke-test the selected runtime without changing the repository's system Python or
   existing `.venv3.12` unexpectedly.
3. Download and hash the approved model checkpoints and required conversion assets.
4. Run a minimal real-inference smoke test and validate the canonical body/facial/camera artifacts.
5. Assemble one real Generated Performance bundle and run both native engine harnesses.
6. Confirm import, save, restart, readback, full render, strict four-modality parity, and retained
   evidence for both engines.
7. Run the full paper plan: 10 scenes, 5 seeds, all 50 first-pass attempts, and the selected
   three-run repeatability cases.
8. Produce the auditable paper-mode experiment report. Never omit failed attempts.

## Important evidence rules

- Do not edit the CIR between Unreal and Unity generation.
- Preserve the original CIR hash, canonical fingerprint, bundle hash, mapping hashes, model/config/
  prompt/seed provenance, editor logs, readbacks, render manifests, frames, and final reports.
- Do not label pre-authored, placeholder, synthetic, or dry-run output as generated evidence.
- Python CI cannot prove that Unity, Unreal, or a generation model executed.
- Final acceptance requires real inference, real editor restarts, complete renders, and zero-error
  strict parity for body, facial, camera, and audio realization.

## Key documentation

- `docs/acceptance/generated-performance-ssd-gate.md`
- `docs/acceptance/generated-performance-native-realization-v0.1.md`
- `docs/acceptance/generated-performance-experiment-v0.1.md`
- `docs/acceptance/cross-engine-parity-v0.1.md`
- `performance/README.md`
- `parity/README.md`
- `adapters/unity/README.md`
- `adapters/unreal/README.md`
- `ROADMAP.md`
- `CHANGELOG.md`

## New-chat starter prompt

Copy the following into the next chat:

> Continue the CutSceneAI Studio project from `README_CONTINUATION.md` in the repository. Work on
> branch `agent/cross-engine-parity-v0.1`; the handoff baseline is commit `31a5a10`. Use direct Git
> pushes only—no PR and no ZIP—and do not touch or commit the untracked `build/` directory. All
> non-SSD work is complete. Before any model download or installation, ask me for the external
> SSD's exact drive letter and target path, then verify its capacity, filesystem, and write access.
> Preserve the paper requirement that real AI-generated body, facial/lip-sync, camera, and audio
> performance must be realized in both Unreal 5.8 and Unity 6 from one unchanged source, with
> reliability, repeatability, portability, and native-realization evidence.
