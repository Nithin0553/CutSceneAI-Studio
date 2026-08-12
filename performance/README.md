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

Regenerate or check the committed schema with:

```powershell
python performance\scripts\export_artifacts.py
python performance\scripts\export_artifacts.py --check
```
