# Changelog

This file records user-visible CutSceneAI Studio changes. Component packages retain independent
versions until the first unified Studio release.

## Unreleased

### Added

- Asset Resolver v0.1 with strict Asset Index and Asset Resolution models, JSON Schemas, canonical
  SHA-256 index identity, duplicate detection, and exact project/index/plan consistency checks.
- Deterministic environment-prop and scene-set matching using normalized semantic terms, curated
  priority, stable lexical tie-breaking, explicit CIR URI precedence, and visible fallback records.
- Office-dialogue and outdoor-action resolution fixtures covering matched props, matched sets,
  environment-detail shots, establishing shots, and unresolved fallbacks.
- `POST /api/v1/assets/resolve` with structured structural, CIR-domain, and Asset Index errors.
- A read-only Unreal 5.8 Static Mesh indexer at
  `GET /api/v1/adapters/unreal/asset-indexer.py`; generated entries require creator curation and the
  script never modifies Content Browser assets.
- Unreal Adapter v0.7 resolution evidence on props and set pieces, resolved Static Mesh imports,
  engine-visible set fallbacks, and preflight of every referenced project asset before mutation.
- `POST /api/v1/adapters/unreal/environment-bundle` for deterministic ZIPs containing the CIR,
  exact Asset Index, verified Asset Resolution plan, Unreal plan, and self-contained importer.
- `POST /api/v1/adapters/unreal/dialogue-environment-bundle` for a cumulative, size-bounded
  multipart workflow that preserves Dialogue manifest timing, WAV provenance and disclosure,
  character and animation bindings, cameras, resolved props, and the resolved set in one package.
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

- CIR 0.1 has no dialogue-duration field, so exact audio end timing lives in the Dialogue manifest;
  beat and shot pacing are never silently extended. Asset Resolver v0.1 does not use an LLM,
  download assets, generate geometry, or infer skeleton compatibility. Facial animation, spatial
  audio, voice cloning, motion generation, and keyframed camera trajectories remain later
  milestones.

### Validated

- Live OpenAI speech acceptance produced two audible WAV files with no warnings: Mina used `marin`
  at frames `120-178`, Arjun used `cedar` at `216-302`, portable CIR URIs and request provenance
  were present, and the required AI-voice disclosure was included.
- Unreal v0.6 archive, compiler, package, backend, checksum, conflict, and generated-script tests
  use local WAV fixtures and make no billable provider calls.
- Unreal Engine 5.8 import and playback acceptance passed for v0.6: both Sound Waves and the Level
  Sequence were created, Mina played at frames `120-178`, Arjun at `216-302`, animations and camera
  changes were present, no audible pop occurred, and there were no importer or playback errors.
- Asset Resolver and Unreal v0.7 automated tests cover deterministic office and outdoor matches,
  fallbacks, tamper rejection, Windows/Linux collection, generated indexer execution, package
  reproducibility, API failures, and Unreal missing-asset preflight without live provider calls.
- The complete local gate passes 223 tests with 95.89% branch-aware coverage, 57 typed source
  files, clean Ruff lint and formatting, and current CIR, Preview, Dialogue, Asset Resolver, and
  Unreal generated contracts.
- Unreal Engine 5.8 acceptance for the v0.7 project indexer and resolved environment package remains
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
