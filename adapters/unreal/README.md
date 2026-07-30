# Unreal Adapter v0.7

The CutSceneAI Unreal Adapter compiles validated CIR into a deterministic Unreal Sequencer plan
and a self-contained Unreal Editor Python importer. The plan is the stable, testable contract; the
generated script turns it into editable Level Sequence assets inside Unreal Engine 5.8.0. Version
0.7 retains the accepted portable Dialogue workflow and adds traceable project-asset indexing,
deterministic environment resolution, resolved props and sets, and preflight of every referenced
engine asset before mutation.

## Status

Version 0.6.0 completed Unreal Engine 5.8 import and playback acceptance before merge. Both
checksum-verified Sound Waves and `LS_SceneMeeting` were created; Mina played at frames `120-178`,
Arjun at `216-302`, animations and camera changes remained present, and no importer or playback
errors occurred. Version 0.7.0 has completed its local contract, resolver, compiler, package, API,
indexer, and generated-script gates. Its real Unreal 5.8 environment acceptance remains required
before merge. Component tag and GitHub release publication remain deferred.

## Output

For each CIR scene, v0.7 creates a Level Sequence plan containing:

- Character and environment spawnable bindings with meter-to-centimeter coordinate conversion
- Visible 180 cm character proxies and semantic document, table, and generic-object dimensions
- Skeletal Mesh character spawnables when `Character.asset_uri` contains an Unreal `/Game/...` path
- Editable skeletal Animation tracks when `MotionPlan.asset_uri` contains a compatible Unreal
  `/Game/...` Anim Sequence path
- Editable, non-looping Audio tracks grouped by speaker when `DialoguePlan.audio_uri` contains a
  compatible Unreal `/Game/...` Sound Wave or Sound Cue path
- Optional checksum-verified WAV imports mapped from portable `cutsceneai://dialogue/...` URIs to
  deterministic `/Game/CutSceneAI/Audio/SW_*` Sound Wave targets
- An optional verified Asset Resolution plan with the exact Asset Index SHA-256
- Resolved environment props and a scene set with selected asset IDs, scores, matched terms, and
  source identities preserved in the plan
- An editable floor stage plus a three-wall shell when no environment set resolves
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
Version 0.4.0 added a typed `animation_sections` collection. The importer groups sections by actor,
creates one editable `MovieSceneSkeletalAnimationTrack` per actor, assigns the referenced animation,
sets the exact CIR start/end frame range, and enables custom animation mode for Sequencer playback.
Version 0.5.0 adds a typed `audio_sections` collection. Each section retains its CIR beat, speaker
binding, sound asset path, dialogue text, language, start frame, and exclusive end frame. The
importer creates one root `MovieSceneAudioTrack` per speaker, names it after the actor binding,
assigns the sound, preserves the exact dialogue start, and disables looping. CIR 0.1 has no audio
duration field, so the deterministic section end is the enclosing performance end; shorter sound
assets finish naturally rather than looping.
Version 0.6.0 adds typed `audio_imports`, a strict Dialogue ZIP loader, and a deterministic Unreal
import ZIP. The server verifies archive paths and limits, CIR/manifest identity, exact cue mapping,
AI-voice disclosure, WAV structure, duration, and SHA-256 before producing any engine plan. The
generated Unreal script then rechecks each extracted WAV checksum, preflights every Sound Wave and
Level Sequence target, refuses replacement, imports through `AssetImportTask`, and verifies the
result as a `SoundBase`. Audio section end frames come from the Dialogue manifest rather than the
enclosing performance range.
Version 0.7.0 adds the engine-neutral Asset Index and Asset Resolution contracts. A generated
read-only Unreal script inventories project Static Meshes; a creator then curates semantic aliases,
location terms, priorities, and set roles. The deterministic resolver never calls a model or
network service. The generated importer verifies that every selected `/Game/...` asset still exists
before it creates a Level Sequence, and it preserves engine-visible proxy fallbacks for unresolved
objects and sets.

## Generate the committed artifacts

From the repository root:

```powershell
python adapters\unreal\scripts\export_artifacts.py
python adapters\unreal\scripts\export_artifacts.py --check
```

The generated products are:

- `schemas/unreal-sequencer-plan-v0.7.schema.json`
- `examples/office-dialogue.unreal.json`
- `examples/import_office_dialogue.py`
- `examples/index_project_static_meshes.py`

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

## Resolve project environment assets

Download and execute the read-only indexer in Unreal:

```powershell
Invoke-WebRequest `
  -Uri http://127.0.0.1:8000/api/v1/adapters/unreal/asset-indexer.py `
  -OutFile .\cutsceneai-unreal-asset-index.py
```

It inventories `/Game` Static Meshes and writes
`Saved/CutSceneAI/unreal-project.asset-index.json`. It does not save, rename, delete, or modify any
Content Browser asset. Every entry deliberately defaults to `environment_prop`; a creator must
review aliases, keywords, location terms, priorities, and which meshes are complete
`environment_set` assets.

Post the CIR plus curated index to `/api/v1/assets/resolve` to inspect the evidence, or to
`/api/v1/adapters/unreal/environment-bundle` to receive a deterministic ZIP containing:

- `asset.index.json`
- `asset.resolution.json`
- `project.cir.json`
- `unreal.plan.json`
- `cutsceneai-unreal-import.py`

The importer refuses to mutate the project if a selected asset is missing or the target Level
Sequence already exists. See the
[v0.7 acceptance guide](../../docs/acceptance/unreal-adapter-v0.7.md) for the complete Windows and
Unreal 5.8 procedure.

To preserve the complete v0.6 dialogue result, send the verified Dialogue ZIP and reviewed index to
`POST /api/v1/adapters/unreal/dialogue-environment-bundle` as multipart fields
`dialogue_bundle_file` and `asset_index_file`. The cumulative ZIP contains both WAV files and both
asset contracts; its single Unreal plan retains manifest-derived audio end frames, character and
animation bindings, cameras, resolved props, and the resolved set.

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

## Import a portable Dialogue bundle

With the backend running, send the already accepted Dialogue v0.1 ZIP as raw `application/zip`:

```powershell
Invoke-WebRequest `
  -Uri http://127.0.0.1:8000/api/v1/adapters/unreal/dialogue-bundle `
  -Method Post `
  -ContentType "application/zip" `
  -InFile .\office-dialogue.tts.zip `
  -OutFile .\office-dialogue.unreal-v0.7.zip

$output = Join-Path $PWD "office-dialogue.unreal-v0.7"
Expand-Archive .\office-dialogue.unreal-v0.7.zip -DestinationPath $output -Force
$plan = Get-Content "$output\unreal.plan.json" -Raw | ConvertFrom-Json

$plan.adapter_version
$plan.audio_imports |
  Select-Object source_cue_id, source_relative_path, asset_path
$plan.sequences[0].audio_sections |
  Select-Object source_cue_id, start_frame, end_frame, timing_source, asset_path
```

Expected for the accepted live office bundle: adapter `0.7.0`, two imports, Mina at frames
`120-178`, Arjun at `216-302`, and `timing_source=dialogue_manifest`. Keep the extracted folder
intact and execute `$output\cutsceneai-unreal-import.py` through **File > Execute Python Script**;
the script needs the adjacent `audio` folder. It stops before import if a WAV changed, a source file
is missing, two targets collide, or any target asset already exists.

The accepted v0.6 import procedure remains archived in
[`docs/acceptance/unreal-adapter-v0.6.md`](../../docs/acceptance/unreal-adapter-v0.6.md).

## Bind mannequin animations for the v0.4 acceptance test

1. Complete the v0.3 character acceptance first: the Third Person content pack is installed, Mina
   uses `SKM_Quinn_Simple`, and Arjun uses `SKM_Manny_Simple`.
2. In the Content Drawer, search all project content for `MF_Idle` and `MM_Idle`; the exact folder
   layout varies between Third Person content pack revisions.
3. Right-click each Anim Sequence and choose **Copy Reference**. CIR uses only the `/Game/...`
   object path inside the quotes, not the surrounding `/Script/Engine.AnimSequence'...'` wrapper.
   Common layouts include:

```json
"/Game/Characters/Mannequins/Animations/Quinn/MF_Idle.MF_Idle"
"/Game/Characters/Mannequins/Animations/Manny/MM_Idle.MM_Idle"
"/Game/Characters/Mannequins/Anims/Unarmed/MM_Idle.MM_Idle"
```

If Unreal shows a different path, use the copied `/Game/...` reference from your project. The
accepted Unreal 5.8 project exposed only the `Anims/Unarmed/MM_Idle` asset; that animation was
compatible with both `SKM_Quinn_Simple` and `SKM_Manny_Simple`. Skeleton compatibility remains
project-specific, so verify both characters move normally rather than assuming one asset fits both.

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

6. Generate the importer:

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

## Bind dialogue audio for the v0.5 acceptance test

1. Create or record two short WAV files containing the exact fixture dialogue:

   - Mina: `You said this would be signed yesterday.`
   - Arjun: `Legal changed the final clause. I was waiting for approval.`

2. In Unreal's Content Drawer, create `/Game/CutSceneAI/Audio`, click **Import**, and import both
   WAV files. Rename the resulting assets `SW_Mina_Line01` and `SW_Arjun_Line01` if needed.
3. Right-click each imported Sound Wave, choose **Copy Reference**, and retain only its `/Game/...`
   object path. For the names above, the expected paths are:

```text
/Game/CutSceneAI/Audio/SW_Mina_Line01.SW_Mina_Line01
/Game/CutSceneAI/Audio/SW_Arjun_Line01.SW_Arjun_Line01
```

Do not include a surrounding `/Script/Engine.SoundWave'...'` wrapper.

4. Start from the CIR file that already passed the v0.4 character and animation test. The command
   below expects `office-dialogue.animated.cir.json`; substitute the golden fixture if testing audio
   without the mannequin bindings.

```powershell
$cir = Get-Content .\office-dialogue.animated.cir.json -Raw | ConvertFrom-Json
$audioByCharacter = @{
    mina  = "/Game/CutSceneAI/Audio/SW_Mina_Line01.SW_Mina_Line01"
    arjun = "/Game/CutSceneAI/Audio/SW_Arjun_Line01.SW_Arjun_Line01"
}

foreach ($beat in $cir.scenes[0].beats) {
    foreach ($performance in $beat.performances) {
        if ($null -ne $performance.dialogue) {
            $performance.dialogue | Add-Member `
                -NotePropertyName audio_uri `
                -NotePropertyValue $audioByCharacter[$performance.character_id] `
                -Force
        }
    }
}

$cir | ConvertTo-Json -Depth 30 | Set-Content .\office-dialogue.audio.cir.json
```

5. With the backend running, compile the plan and verify its two audio sections:

```powershell
$body = Get-Content .\office-dialogue.audio.cir.json -Raw
$plan = Invoke-RestMethod `
    -Uri http://127.0.0.1:8000/api/v1/adapters/unreal/export `
    -Method Post `
    -ContentType "application/json" `
    -Body $body

$plan.adapter_version
$plan.sequences[0].audio_sections |
    Select-Object actor_binding_id, start_frame, end_frame, asset_path
```

The current adapter version is `0.7.0`. Mina must cover frames `120-336`; Arjun must cover
`216-336`; this preserves the accepted v0.5 behavior.

6. Generate the importer:

```powershell
Invoke-WebRequest `
  -Uri http://127.0.0.1:8000/api/v1/adapters/unreal/importer.py `
  -Method Post `
  -ContentType "application/json" `
  -Body $body `
  -OutFile cutsceneai-unreal-audio.py
```

7. Back up manual edits, intentionally delete the previous `LS_SceneMeeting`, execute
   `cutsceneai-unreal-audio.py`, and choose **Save All**.
8. Open the sequence. Confirm the root tracks **CutSceneAI Dialogue - ACT_Mina** and
   **CutSceneAI Dialogue - ACT_Arjun** each contain one editable, non-looping section at the expected
   start frame. Scrub or play the sequence and confirm the lines begin on the dialogue markers.
9. Restart Unreal, reopen `L_CutSceneAI_Preview` and `LS_SceneMeeting`, and confirm both tracks,
   sound assignments, and frame ranges persisted.
10. In Movie Render Queue settings, keep the PNG output and add **+ Setting > Export > WAV Audio**.
    Render frames `0-431`. Acceptance requires 432 non-empty frames, a WAV output, both lines once
    at the expected timeline positions, both animated characters, and correct camera cuts. Epic's
    [MRQ export-format documentation](https://dev.epicgames.com/documentation/unreal-engine/cinematic-rendering-export-formats-in-unreal-engine)
    confirms WAV Audio can be emitted alongside image sequences.

## v0.7 boundary

Version 0.7 inventories project Static Meshes, resolves CIR props and scene locations against a
creator-curated index, and imports selected sets and props with explicit match evidence. It does
not mutate assets during indexing, download marketplace content, infer skeletal compatibility,
retarget animation, generate geometry, attach spatial audio, generate lip-sync or facial
animation, key camera movement curves, or launch unattended final rendering. An LLM cannot write
directly into the Unreal project through this workflow.

Portable Dialogue implementation and Unreal acceptance history:
[pull request #16](https://github.com/Nithin0553/CutSceneAI-Studio/pull/16).
