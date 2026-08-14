# Changelog

This file records user-visible CutSceneAI Studio changes. Component packages retain independent
versions until the first unified Studio release.

## Unreleased

### Added

- Generated Performance Package v0.1 with one unchanged, hashed body/facial/camera/audio
  realization contract for both Unreal and Unity, including model, prompt, configuration, seed,
  and inference provenance.
- Deterministic CIR-to-generation-plan compilation with stable semantic IDs, exact frame windows,
  request hashes, and controlled per-request seeds for body, face, and camera generation.
- A strict `cutsceneai-humanoid-v1` 22-joint body-motion schema with fixed hierarchy,
  finite-value and unit-quaternion validation, deterministic rendering and hashing, and exact-frame
  linear/root plus shortest-path-SLERP rotation resampling.
- A strict `arkit-52` facial and lip-sync curve schema with fixed curve order, bounded finite
  weights, deterministic rendering and hashing, and endpoint-preserving exact-frame resampling.
- A canonical perspective-camera curve schema with right-handed Y-up transforms, explicit sensor
  dimensions, bounded focal lengths, deterministic rendering and hashing, and exact-frame linear
  plus shortest-path-SLERP resampling.
- Provider-neutral body, facial, and camera backend protocols with strict request metadata,
  inference-origin, pre-authored-retrieval, profile, provenance, and exact-frame normalization
  gates.
- Deterministic Generated Performance ZIP assembly and untrusted loading with exact plan/manifest
  relationships, artifact entry sets, SHA-256 and byte-length checks, PCM frame timing, archive
  limits, safe paths, and compression/encryption rejection.
- Exact bundle-to-timeline semantic verification for project, fingerprint, frame rate, scene,
  body, face, camera, audio, and dialogue-window identities before engine mapping.
- Typed Unreal 5.8 generated-performance mappings from the canonical 22-joint profile to UE5
  Mannequin bones, ARKit-52 face curves, Cine Camera samples, and deterministic `/Game/...` targets.
- Typed Unity 6 generated-performance mappings from the same bundle to Humanoid bones, ARKit-52
  blendshapes, Camera samples, and deterministic `Assets/...` animation and audio targets.
- Explicit reference-pose semantics for canonical body root offsets and parent-local joint rotation
  deltas, carried through both engine mappings and composed with each target rig's reference pose.
- Public Unreal and Unity generated-performance mapping JSON Schemas with preserved source bundle,
  artifact, CIR, and provider-provenance hashes.
- Public Unity and Unreal native-target schemas for exact prefab/Animator/face-renderer and Skeletal
  Mesh/map destinations, strict versions, render settings, unique actors, and safe output paths.
- `cutsceneai-unity-native` and `cutsceneai-unreal-native` one-command compilers that re-verify the
  unchanged bundle and deterministic mapping, refuse output replacement, and package exact editor
  import/save/restart/readback/render automation.
- Unity 6000.0/Timeline 1.8.12 native realization with reference-pose-correct Humanoid body clips,
  layered ARKit-52 facial clips, generated camera/lens animation, audio, saved Timeline/Scene,
  second-process readback, and complete PNG rendering.
- Unreal 5.8.0 native realization with reference-pose-correct Anim Sequences, ARKit-52 facial
  curves, verified Sound Waves, Cine Camera transform/focal tracks and cuts, saved Level Sequence,
  separate restart/readback, and Movie Render Queue processes.
- A self-contained evidence collector that requires distinct editor processes and binds exact
  mapping, log, readback, canonical timeline, render manifest, lifecycle, modality, artifact, and
  native target evidence into the experiment ledger.
- Strict parity coverage for native body animation, facial curves, generated camera sections, and
  audio, with explicit four-modality and required-engine settings retained in every report.
- A typed generated-performance experiment plan, per-attempt evidence record, aggregate report,
  CLI, and public schemas for the fixed 10-scene by 5-seed reliability denominator, three-run
  repeatability, unchanged-bundle portability, and native restart/readback/render evidence.
- Explicit harness and paper evidence modes: synthetic fixtures can validate the aggregator but
  can never produce a publishable report, while failed attempts remain in the planned denominator.
- An explicit external-SSD dependency gate that allows contracts, adapters, packaging, and
  experiment harnesses to continue while preventing dry runs from being presented as real
  generated-performance evidence.
- Unity Timeline Adapter v0.1 for Unity 6000.0 and Timeline 1.8.12, with native animation,
  audio, camera activation, actor binding, semantic marker, and visible fallback compilation.
- A separate typed Unity asset map so project-specific prefab, animation, and audio paths can be
  resolved without editing portable CIR 0.1.
- Canonical CIR semantic fingerprints and a typed engine readback contract for entities,
  performance, dialogue, cameras, and native realization evidence.
- Restart-safe Unity and Unreal readback exporters that reopen saved native timeline assets and
  inspect actual frame rate, duration, bindings, markers, clips, camera cuts, and focal lengths.
- `cutsceneai-parity verify` with CIR-to-engine and Unreal-to-Unity comparisons, one-frame
  tolerance, required-engine enforcement, and optional strict body/facial/camera/audio coverage.
- `scripts/compile_cross_engine.py` to generate both engine import/readback bundles from one
  unchanged CIR while recording its source byte hash and canonical hash.
- `POST /api/v1/adapters/unity/export`, `POST /api/v1/adapters/unity/importer.cs`, and
  `POST /api/v1/adapters/unreal/readback.py`.
- Dialogue Engine v0.1 package with provider-neutral cue planning, recorded PCM WAV ingestion, and
  pluggable asynchronous speech generation.
- Stable cue IDs and `cutsceneai://dialogue/...` URIs derived from validated CIR scene, beat,
  character, and performance identities.
- Exact WAV duration, frame ranges, SHA-256 hashes, voice settings, provider request metadata, and
  recorded/generated provenance in a public manifest contract.
- Byte-for-byte deterministic ZIP bundles containing updated CIR, manifest, WAV files, and a
  generated-voice disclosure notice when applicable.
- `POST /api/v1/dialogue/plan` and `POST /api/v1/dialogue/synthesize`, with OpenAI speech provided
  through a replaceable backend and no live calls in automated tests.
- `cutsceneai-dialogue` CLI commands for planning cues and bundling recorded audio.
- Canonicalization of streamed provider WAV headers with placeholder RIFF/data lengths, preserving
  strict rejection of genuinely truncated or frame-misaligned PCM payloads.
- Strict loading of Dialogue v0.1 ZIPs as untrusted input, including archive path and size limits,
  exact entry sets, CIR/manifest/cue consistency, WAV structure, SHA-256, measured duration,
  disclosure, and frame-timing verification.
- Unreal Adapter v0.6 `audio_imports` with deterministic Sound Wave names, portable-URI mapping,
  and manifest-derived audio section end frames.
- `POST /api/v1/adapters/unreal/dialogue-bundle` for deterministic Unreal import ZIPs containing
  the generated importer, typed plan, source contracts, disclosure, and WAV files.
- Generated Unreal 5.8 import preflight that verifies extracted WAV checksums, reports every asset
  conflict before mutation, refuses replacement, imports with `AssetImportTask`, and verifies the
  resulting `SoundBase` assets.

### Boundaries

- Large model environments, MDM/HumanML3D and SMPL assets, retained inference outputs, and final
  inference-backed engine evidence remain blocked until the external SSD is connected and its
  explicit target path is verified.
- Automated tests cannot execute Unity or Unreal in Python CI. Cross-engine implementation is
  complete, but final acceptance requires both readbacks after editor restart and a zero-error
  parity report. Placeholder animation and missing audio remain explicit realization warnings and
  fail the strict production gate.
- Native realization automation is implemented and deterministically tested, but Python CI cannot
  execute either editor. Retained real-editor output remains required for native acceptance, and
  real inference-backed acceptance remains SSD-blocked.
- CIR 0.1 has no dialogue-duration field, so exact audio end timing lives in the Dialogue manifest;
  beat and shot pacing are never silently extended. Project-wide asset discovery, environment
  resolution, facial animation, spatial audio, and voice cloning remain later milestones.

### Validated

- Deterministic generation, schema drift, semantic mismatch detection, native-target validation,
  generated-script syntax, archive integrity, lifecycle enforcement, and evidence collection cover
  the native harness locally. Real Unity 6000.0 and Unreal 5.8.0 readback evidence remains pending.
- Live OpenAI speech acceptance produced two audible WAV files with no warnings: Mina used `marin`
  at frames `120-178`, Arjun used `cedar` at `216-302`, portable CIR URIs and request provenance
  were present, and the required AI-voice disclosure was included.
- Unreal v0.6 archive, compiler, package, backend, checksum, conflict, and generated-script tests
  use local WAV fixtures and make no billable provider calls.
- Ruff check and formatting, mypy across 93 source files, all seven schema/artifact drift checks,
  and 504 automated tests passed locally with 97.46% branch-aware coverage. The 185 Generated
  Performance tests retain 100% statement and branch coverage.
- Unreal Engine 5.8 restart and Movie Render Queue acceptance for the v0.6 automatic import remains
  required before merge.

## Unreal Adapter 0.5.0 - 2026-07-17

### Added

- Typed `audio_sections` in the Unreal Sequencer plan and JSON Schema.
- Compilation of compatible CIR `DialoguePlan.audio_uri` values into speaker-associated sections
  beginning at the exact dialogue start frame and ending at the enclosing performance boundary.
- One named, non-looping `MovieSceneAudioTrack` per speaker in the generated Unreal importer.
- Explicit warnings for unsupported Unreal audio paths and dialogue starts outside the performance
  range.
- API, schema, compiler, and generated-importer tests for dialogue audio binding.

### Validated

- Ruff check, formatting, mypy, and CIR, Preview, and Unreal artifact drift checks passed.
- 91 automated tests passed with 97.41% branch-aware coverage.
- GitHub Actions CI run 87 passed on Python 3.11, 3.12, and 3.13.
- Unreal Engine 5.8 persisted Mina's `120-336` and Arjun's `216-336` dialogue sections after
  restart, with both sounds audible during Sequencer playback.
- Movie Render Queue produced 432 non-empty PNG frames (`0000-0431`) and two synchronized WAV
  outputs; Mina began near 5 seconds and Arjun near 9 seconds without looping.
- Existing mannequin animation sections and camera cuts remained correct, with no output-log errors.

### Boundaries

- v0.5 resolves explicit Sound Wave and Sound Cue object paths; it does not discover assets, select
  or generate voices, calculate audio duration, attach spatial audio, or generate facial animation.
  Those capabilities remain in the Dialogue Engine and later performance milestones.

Publication note: the code milestone is complete, but its component tag and GitHub release remain
deferred until release permissions are available.

Implementation and acceptance history: [pull request #14](https://github.com/Nithin0553/CutSceneAI-Studio/pull/14).

## Unreal Adapter 0.4.0 - 2026-07-16

### Added

- Typed `animation_sections` in the Unreal Sequencer plan contract and JSON Schema.
- Compilation of compatible CIR `MotionPlan.asset_uri` values into exact Sequencer frame ranges.
- One editable `MovieSceneSkeletalAnimationTrack` per skeletal character binding.
- Self-contained Unreal Editor Python support for loading animation assets, assigning sections, and
  enabling custom Sequencer animation mode.
- Explicit warnings for unsupported animation URIs and animation requests targeting proxy actors.
- Unreal 5.8 acceptance documentation for character assets and mannequin animations.

### Validated

- Ruff, formatting, mypy, schema/artifact drift, and 95% branch-coverage gates passed.
- 85 automated tests passed with 97.48% branch-aware coverage before merge.
- GitHub Actions passed on Python 3.11, 3.12, and 3.13 before and after merge.
- Unreal Engine 5.8 persisted two editable animation sections for each character after restart.
- Movie Render Queue produced 432 frames with both characters animated, correct camera cuts, and no
  black or empty frames.

### Boundaries

- v0.4 resolves explicit Skeletal Mesh and Anim Sequence object paths; it does not discover assets,
  infer compatibility, retarget skeletons, generate motion, animate faces, place dialogue audio,
  generate camera curves, or launch unattended final renders.

See the [full v0.4 release notes](docs/releases/unreal-adapter-v0.4.0.md) and
[pull request #12](https://github.com/Nithin0553/CutSceneAI-Studio/pull/12).
