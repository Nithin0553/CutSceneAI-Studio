# Unreal Adapter v0.4

The CutSceneAI Unreal Adapter compiles validated CIR into a deterministic Unreal Sequencer plan
and a self-contained Unreal Editor Python importer. The plan is the stable, testable contract; the
generated script turns it into editable Level Sequence assets inside Unreal Engine 5.8.0. Version
0.4 keeps deterministic proxy scene assembly and Skeletal Mesh binding, then adds explicit,
frame-aligned Anim Sequence sections for CIR motion assets.

## Output

For each CIR scene, v0.4 creates a Level Sequence plan containing:

- Character and environment spawnable bindings with meter-to-centimeter coordinate conversion
- Visible 180 cm character proxies and semantic document, table, and generic-object dimensions
- Skeletal Mesh character spawnables when `Character.asset_uri` contains an Unreal `/Game/...` path
- Editable skeletal Animation tracks when `MotionPlan.asset_uri` contains a compatible Unreal
  `/Game/...` Anim Sequence path
- An editable floor stage plus a three-wall shell for indoor scene locations
- A Cine Camera Actor per CIR shot and an exact frame-aligned Camera Cuts track
- Focal lengths, shot purpose, composition, targets, and source IDs
- Performance and dialogue markers retaining motion prompts, facial, lip-sync, and look-at intent
- Explicit warnings for placeholders, inferred cameras, unsupported animation paths, and remaining
  metadata-only features

The golden office scene produces `/Game/CutSceneAI/Sequences/LS_SceneMeeting` with four semantic
actor bindings, four generated set pieces, four cameras, four cuts, and four performance cues.
Supplying an Unreal `/Game/...` environment asset path bypasses that entity's proxy visual.
Adapter patch 0.2.1 configures both the Sequencer template and live bound Static Mesh Actor before
saving the default spawnable state, so proxy geometry persists into Movie Render Queue sessions.
Patch 0.2.2 applies the same template/live persistence rule to Cine Camera Actors, preventing Unreal
5.8 from reopening generated camera bindings at the world origin with a zero rotation.
Patch 0.2.3 removes the auto-generated zero-valued Transform track from static blocking bindings,
so Sequencer does not override the persisted actor and camera transforms during evaluation.
Patch 0.2.4 makes over-the-shoulder blocking subject-aware: the first target is framed as the
primary subject while the second target is retained as a foreground shoulder reference.
Version 0.3.0 adds an explicit `mesh_type` to the adapter plan and configures both the template and
live `SkeletalMeshActor` before saving its default spawnable state. Missing or unsupported character
asset URIs retain the existing visible cylinder fallback.
Version 0.4.0 adds a typed `animation_sections` collection. The importer groups sections by actor,
creates one editable `MovieSceneSkeletalAnimationTrack` per actor, assigns the referenced animation,
sets the exact CIR start/end frame range, and enables custom animation mode for Sequencer playback.

## Generate the committed artifacts

From the repository root:

```powershell
python adapters\unreal\scripts\export_artifacts.py
python adapters\unreal\scripts\export_artifacts.py --check
```

The generated products are:

- `schemas/unreal-sequencer-plan-v0.4.schema.json`
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

## Bind mannequin animations for the v0.4 acceptance test

1. Complete the v0.3 character acceptance first: the Third Person content pack is installed, Mina
   uses `SKM_Quinn_Simple`, and Arjun uses `SKM_Manny_Simple`.
2. In the Content Drawer, open `Characters/Mannequins/Animations`. Find `MF_Idle` under `Quinn` and
   `MM_Idle` under `Manny`.
3. Right-click each Anim Sequence and choose **Copy Reference**. CIR uses only the object path inside
   the quotes. The standard Third Person paths are:

```json
"/Game/Characters/Mannequins/Animations/Quinn/MF_Idle.MF_Idle"
"/Game/Characters/Mannequins/Animations/Manny/MM_Idle.MM_Idle"
```

If Unreal shows a different path, use the copied reference from your project.

4. From the repository root, create an animated copy of the already working character CIR file:

```powershell
$cir = Get-Content .\office-dialogue.characters.cir.json -Raw | ConvertFrom-Json
$quinnIdle = "/Game/Characters/Mannequins/Animations/Quinn/MF_Idle.MF_Idle"
$mannyIdle = "/Game/Characters/Mannequins/Animations/Manny/MM_Idle.MM_Idle"

foreach ($beat in $cir.scenes[0].beats) {
    foreach ($performance in $beat.performances) {
        $animation = if ($performance.character_id -eq "mina") { $quinnIdle } else { $mannyIdle }
        $performance.motion | Add-Member `
            -NotePropertyName asset_uri `
            -NotePropertyValue $animation `
            -Force
    }
}

$cir | ConvertTo-Json -Depth 30 | Set-Content .\office-dialogue.animated.cir.json
```

5. Start the backend, compile the plan, and verify that it contains four animation sections:

```powershell
$body = Get-Content .\office-dialogue.animated.cir.json -Raw
$plan = Invoke-RestMethod `
    -Uri http://127.0.0.1:8000/api/v1/adapters/unreal/export `
    -Method Post `
    -ContentType "application/json" `
    -Body $body

$plan.sequences[0].animation_sections |
    Select-Object actor_binding_id, start_frame, end_frame, asset_path
```

The rows should cover `0-96` and `96-336` for Mina, plus `96-336` and `336-432` for Arjun.

6. Generate the v0.4 importer:

```powershell
Invoke-WebRequest `
  -Uri http://127.0.0.1:8000/api/v1/adapters/unreal/importer.py `
  -Method Post `
  -ContentType "application/json" `
  -Body $body `
  -OutFile cutsceneai-unreal-animated.py
```

7. Delete the previous `LS_SceneMeeting` intentionally, execute `cutsceneai-unreal-animated.py`, and
   save all.
8. Open `LS_SceneMeeting`. Expand `ACT_Mina` and `ACT_Arjun`; each must have one **CutSceneAI
   Animation** track containing two editable sections. Scrub the timeline and confirm both mannequin
   poses animate.
9. Restart Unreal, reopen `L_CutSceneAI_Preview` and the sequence, then confirm the tracks and motion
   persisted.
10. Run MRQ again. Acceptance requires 432 frames, both characters animated and visible, working
    camera cuts, and no black or empty frames.

## v0.4 boundary

This release resolves explicit Skeletal Mesh and Anim Sequence object paths; it does not search a
project, choose an asset, infer skeleton compatibility, or retarget animation. AI motion generation,
Control Rig keying, facial animation, dialogue audio placement, camera movement curves, and automated
final rendering remain later adapter phases and are identified in the plan warnings.
