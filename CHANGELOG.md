# Changelog

This file records user-visible CutSceneAI Studio changes. Component packages retain independent
versions until the first unified Studio release.

## Unreleased

### Added

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

### Boundaries

- CIR 0.1 has no dialogue-duration field, so exact audio end timing lives in the Dialogue manifest;
  beat and shot pacing are never silently extended. Unreal asset import, portable-URI resolution,
  facial animation, and voice cloning remain later milestones.

### Validated

- Ruff check and formatting, mypy across 45 source files, and CIR, Preview, Dialogue, and Unreal
  artifact-drift checks passed locally.
- 147 automated tests passed with 97.78% branch-aware coverage; OpenAI speech tests use a fake
  streaming client and make no billable provider calls.
- Live provider and audible-WAV acceptance remains required before the milestone is merged.

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
