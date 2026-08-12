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
