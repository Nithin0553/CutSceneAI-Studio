# Changelog

This file records user-visible CutSceneAI Studio changes. Component packages retain independent
versions until the first unified Studio release.

## Unreleased

- Next milestone: Unreal Adapter v0.5 dialogue audio binding.

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
