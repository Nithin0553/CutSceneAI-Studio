# Generated-performance native realization v0.1

This gate turns one unchanged Generated Performance Package into native Unity 6000.0 and Unreal
Engine 5.8 assets, proves that those assets survive editor restart, renders the complete frame
window, and emits hash-anchored engine evidence for the experiment ledger.

It is a no-replacement workflow. Use clean destination paths and projects prepared with the exact
target character assets before each run.

## Required inputs

Both engines consume the same `performance.bundle.zip`. Each engine also requires its deterministic
export plan, generated-performance mapping, and native target manifest. Unreal additionally takes
the exact timeline-semantics document used to compile its mapping.

The public target schemas are:

- `adapters/unity/schemas/unity-native-performance-target-v0.1.schema.json`;
- `adapters/unreal/schemas/unreal-native-performance-target-v0.1.schema.json`.

A Unity actor target identifies a non-placeholder prefab, its Humanoid `Animator` path, and a
descendant `SkinnedMeshRenderer` carrying all 52 ARKit blendshapes. An Unreal actor target identifies
a non-placeholder Skeletal Mesh carrying the mapped UE5 Mannequin bones and all 52 ARKit morph
targets. The target's `source_mapping_sha256` must be the SHA-256 of the exact committed-style
mapping JSON bytes.

## Compile the harnesses

From an installed development environment, run:

```powershell
cutsceneai-unity-native `
  --bundle .\evidence\performance.bundle.zip `
  --plan .\evidence\unity.plan.json `
  --mapping .\evidence\unity.mapping.json `
  --target .\evidence\unity.native-target.json `
  --output .\evidence\unity.native-harness.zip

cutsceneai-unreal-native `
  --bundle .\evidence\performance.bundle.zip `
  --plan .\evidence\unreal.plan.json `
  --mapping .\evidence\unreal.mapping.json `
  --target .\evidence\unreal.native-target.json `
  --semantics .\evidence\timeline.semantics.json `
  --output .\evidence\unreal.native-harness.zip
```

Both compilers re-verify the bundle, deterministically recompile the mapping, verify the mapping
hash in the native target, preserve the source bundle bytes, and refuse to replace an existing
output file.

## Unity gate

Requirements:

- Unity `6000.0.x`;
- `com.unity.timeline` exactly `1.8.12`;
- the target prefabs already present at their declared `Assets/...` paths;
- no existing generated clips, Timeline, Scene, copied WAVs, evidence frames, or editor helper at
  the declared destinations.

Extract the harness and run:

```powershell
.\Scripts\run-unity-native.ps1 `
  -UnityEditor "C:\Program Files\Unity\Hub\Editor\6000.0.42f1\Editor\Unity.exe" `
  -ProjectPath "D:\CutSceneAI\UnityNativeGate"
```

The runner verifies the bundle hash and WAV hashes, launches one editor process to create and save
body, facial, camera, audio, Timeline, and Scene assets, then launches a second process to reopen
the saved assets, read every modality, and render every frame to PNG. Body rotations and root
translations are composed with the target reference pose. Facial weights are converted from the
canonical `[0, 1]` range to Unity's `[0, 100]` blendshape range.

Evidence is written under `CutSceneAIEvidence\Unity` in the project root.

## Unreal gate

Requirements:

- Unreal Engine `5.8.0`;
- Python Editor Script, Editor Scripting Utilities, Sequencer Scripting, Movie Render Queue, and
  Movie Render Pipeline Render Passes enabled;
- the target Skeletal Meshes and render map already present at their declared `/Game/...` paths;
- no existing generated Anim Sequences, Sound Waves, Level Sequence, render frames, or evidence at
  the declared destinations.

Extract the harness and run:

```powershell
.\Scripts\run-unreal-native.ps1 `
  -UnrealEditor "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe" `
  -UProject "D:\CutSceneAI\UnrealNativeGate\UnrealNativeGate.uproject"
```

The runner launches three distinct editor processes: import/save, restart/readback, and
restart/Movie Render Queue. It validates mapped bones and morph targets before mutation, composes
body keys with the skeleton reference pose, creates facial curves, imports verified WAVs, creates
camera transform/focal tracks and cuts, reloads the saved Level Sequence, and renders the exact
half-open frame range to PNG.

Evidence is written under `Saved\CutSceneAI\Native\Unreal` in the project.

## Pass criteria

Each evidence directory must contain `lifecycle.json`, `readback.json`, `render-manifest.json`, the
combined editor log, and `engine-run.evidence.json`. The evidence collector rejects mismatched
engine or bundle identities, mapping/readback semantic drift, non-boolean lifecycle states,
non-distinct editor process IDs, invalid render accounting, missing or duplicate source artifact
hashes, and malformed error lists.

The engine record passes native realization only when import, save, restart, readback, and render
are all true; rendered frames equal the mapping duration; body, facial, camera, and audio counts
are exact; every section has a native target reference; placeholders, errors, and warnings are
zero; and artifact hashes equal the source package.

## Evidence boundary

The repository's synthetic tests prove deterministic compilation, validation, archive contents,
generated-script syntax, and failure handling. They do not prove that either editor or a model ran.
Only retained logs, readbacks, manifests, frames, and engine evidence from the commands above are
native engine evidence. Paper evidence additionally requires real inference outputs and therefore
remains behind the external-SSD gate.
