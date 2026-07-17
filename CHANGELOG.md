# Changelog

This file records user-visible CutSceneAI Studio changes. Component packages retain independent
versions until the first unified Studio release.

## Unreleased

- Next milestone: Dialogue Engine v0.1 for recorded-audio ingestion, pluggable TTS, voice metadata,
  provenance, and duration-aware timing.

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
