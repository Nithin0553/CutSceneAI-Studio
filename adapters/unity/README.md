# Unity Timeline Adapter v0.1

The Unity adapter compiles validated CIR 0.1 into editable Unity 6000.0 Timeline assets using
Timeline package 1.8.12. It also emits a restart-safe readback exporter for cross-engine parity.

The generated editor script creates:

- one `.playable` Timeline, one `.semantics.json` manifest, and one `.unity` Scene per CIR scene;
- actor or environment prefab instances, or visible primitive fallbacks;
- one native `AnimationTrack` per performing actor, with editable empty clips when unmapped;
- speaker-bound native `AudioTrack` sections when an external asset map supplies clips and measured
  end frames;
- one native `ActivationTrack` per camera cut;
- semantic markers and an adjacent imported JSON manifest carrying the unchanged CIR fingerprint.

No Cinemachine dependency is required for v0.1.

## Generated Performance mapping contract

`compile_performance_bundle` accepts one verified Generated Performance Package and its exact Unity
export plan. It rejects identity, frame-rate, scene, actor, camera-cut, or target-path drift, then
emits `UnityPerformanceMapping` with:

- canonical 22-joint body samples converted to Unity coordinates, mapped to Humanoid bones, and
  declared as reference-pose-relative rotations plus reference-pose root offsets;
- fixed ARKit-52 curve bindings using lower-camel-case blendshape names;
- per-frame Camera transform, sensor, focal-length, and cut bindings;
- deterministic `Assets/CutSceneAI/GeneratedPerformance/...` animation and audio targets; and
- the unchanged bundle SHA-256, CIR fingerprint, artifact references, and model provenance.

The public mapping and native-target contracts are committed at
`schemas/unity-performance-mapping-v0.1.schema.json` and
`schemas/unity-native-performance-target-v0.1.schema.json`.

`compile_unity_native_performance_package` re-verifies the unchanged bundle and exact mapping, then
generates a no-replacement Unity harness. The harness validates Unity `6000.0.x`, Timeline `1.8.12`,
the target Humanoid bones, ARKit-52 blendshapes, WAV hashes, and all destination conflicts before
mutation. It creates reference-pose-correct body clips, facial blendshape clips, generated camera
and focal-length clips, audio tracks, a Timeline, and a Scene. A second editor process reopens the
saved assets, emits four-modality readback, renders every frame, and produces hash-anchored engine
evidence.

Compile one harness from explicit inputs with:

```powershell
cutsceneai-unity-native `
  --bundle .\evidence\performance.bundle.zip `
  --plan .\evidence\unity.plan.json `
  --mapping .\evidence\unity.mapping.json `
  --target .\evidence\unity.native-target.json `
  --output .\evidence\unity.native-harness.zip
```

The deterministic Python tests are harness validation, not Unity acceptance evidence. The full
editor command and evidence criteria are in
[`docs/acceptance/generated-performance-native-realization-v0.1.md`](../../docs/acceptance/generated-performance-native-realization-v0.1.md).

## Generate the editor script

Create an engine-neutral semantic pilot with placeholders:

```bash
python scripts/compile_cross_engine.py \
  cir/examples/office-dialogue.cir.json \
  --output-dir build/cross-engine
```

For project assets, pass the separate example map without editing the CIR:

```bash
python scripts/compile_cross_engine.py \
  cir/examples/office-dialogue.cir.json \
  --unity-asset-map adapters/unity/examples/office-dialogue.asset-map.example.json \
  --output-dir build/cross-engine
```

Every mapped `Assets/...` path must exist in the destination Unity project. The importer performs a
complete preflight and refuses to replace an existing generated Scene, Timeline, or semantic
manifest.

## Run in Unity

1. Use Unity 6000.0 with `com.unity.timeline` 1.8.12.
2. Copy `CutSceneAISemanticMarker.cs` into the Unity project's `Assets/Editor/` folder. Keep this
   exact filename because Unity requires a serialized custom marker's filename to match its class.
3. Select **CutSceneAI > Import Generated Timeline**.
4. Save, close, and reopen the project.
5. Select **CutSceneAI > Export Generated Timeline Readback**.

The readback is written outside `Assets/` at:

```text
CutSceneAIReadbacks/<project-id>.unity.readback.json
```

The exporter reopens the saved Scene and Timeline assets and reads their actual frame rate,
duration, actor objects, semantic markers, animation and audio clips, camera activation ranges, and
camera focal lengths. Asset paths are retained as diagnostic evidence but are not required to match
Unreal paths.

## API

- `POST /api/v1/adapters/unity/export`
- `POST /api/v1/adapters/unity/importer.cs`

The HTTP endpoints compile the placeholder-safe plan directly from CIR. Use the repository compiler
when a separate Unity asset map is required.
