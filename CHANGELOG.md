# Changelog

This file records user-visible CutSceneAI Studio changes. Component packages retain independent
versions until the first unified Studio release.

## Unreleased

### Added

- Unreal Adapter v0.5 candidate with typed `audio_sections` in the Sequencer plan and JSON Schema.
- Compilation of compatible CIR `DialoguePlan.audio_uri` values into speaker-associated sections
  beginning at the exact dialogue start frame and ending at the enclosing performance boundary.
- One named, non-looping `MovieSceneAudioTrack` per speaker in the generated Unreal importer.
- Explicit warnings for unsupported Unreal audio paths and dialogue starts outside the performance
  range.
- API, schema, compiler, and generated-importer tests for dialogue audio binding.

### Pending acceptance

- Confirm two dialogue clips and their speaker tracks persist after an Unreal Engine 5.8 restart.
- Confirm Movie Render Queue produces synchronized WAV audio alongside the 432-frame image render.

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
