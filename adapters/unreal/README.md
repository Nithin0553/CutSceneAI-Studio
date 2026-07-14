# Unreal Adapter v0.1

The CutSceneAI Unreal Adapter compiles validated CIR into a deterministic Unreal Sequencer plan
and a self-contained Unreal Editor Python importer. The plan is the stable, testable contract; the
generated script turns it into editable Level Sequence assets inside Unreal Engine 5.8.0.

## Output

For each CIR scene, v0.1 creates a Level Sequence plan containing:

- Character and environment spawnable bindings with meter-to-centimeter coordinate conversion
- A Cine Camera Actor per CIR shot and an exact frame-aligned Camera Cuts track
- Focal lengths, shot purpose, composition, targets, and source IDs
- Performance and dialogue markers retaining motion, facial, lip-sync, and look-at intent
- Explicit warnings for placeholders, inferred cameras, and metadata awaiting animation binding

The golden office scene produces `/Game/CutSceneAI/Sequences/LS_SceneMeeting` with four actor
bindings, four cameras, four cuts, and four performance cues.

## Generate the committed artifacts

From the repository root:

```powershell
python adapters\unreal\scripts\export_artifacts.py
python adapters\unreal\scripts\export_artifacts.py --check
```

The generated products are:

- `schemas/unreal-sequencer-plan-v0.1.schema.json`
- `examples/office-dialogue.unreal.json`
- `examples/import_office_dialogue.py`

## Export through the API

With the backend running:

```powershell
$body = Get-Content cir\examples\office-dialogue.cir.json -Raw

Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/api/v1/adapters/unreal/export `
  -Method Post `
  -ContentType "application/json" `
  -Body $body | ConvertTo-Json -Depth 20

Invoke-WebRequest `
  -Uri http://127.0.0.1:8000/api/v1/adapters/unreal/importer.py `
  -Method Post `
  -ContentType "application/json" `
  -Body $body `
  -OutFile cutsceneai-unreal-import.py
```

## Import in Unreal Engine 5.8.0

1. Install the bundled Microsoft Visual C++ Redistributable from
   `Engine/Extras/Redist/en-us/vc_redist.x64.exe`; Unreal 5.8 requires version `14.50.35719.0`
   or newer.
2. Create or open an Unreal project.
3. Enable **Python Editor Script Plugin**, **Editor Scripting Utilities**, and
   **Sequencer Scripting**, then restart the editor if prompted.
4. Choose **File > Execute Python Script** and select `cutsceneai-unreal-import.py`.
5. Open `/Game/CutSceneAI/Sequences/LS_SceneMeeting` in Sequencer.
6. Confirm the four camera cuts at frames `0`, `96`, `144`, `336`, and the end at `432`.

The importer never deletes or replaces assets. If the Level Sequence already exists, it stops with
an actionable error so replacement remains an intentional editor action.

## v0.1 boundary

This release creates blocking actors, cameras, cuts, focal lengths, and editorial markers. Motion
generation, Control Rig keying, facial animation, dialogue audio placement, camera movement curves,
and final rendering remain later adapter phases and are identified in the plan warnings.
