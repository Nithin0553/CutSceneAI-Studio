# Unreal Adapter v0.6 Acceptance

Target: Windows PowerShell, Python 3.12, Unreal Engine 5.8.0, and a Dialogue v0.1 ZIP whose CIR
already contains the character and animation references accepted in Unreal v0.4/v0.5.

This gate makes no speech-provider call. It consumes an existing recorded or generated Dialogue
bundle, verifies it again, and imports its WAV files into Unreal. Run repository commands from the
`cutscene-ai` root, not its parent or `backend` subdirectory.

## 1. Install and run the automated gate

```powershell
python -m pip install `
  -e ".\cir[dev]" `
  -e ".\preview[dev]" `
  -e ".\dialogue[dev]" `
  -e ".\adapters\unreal[dev]" `
  -e ".\backend[dev]"

python -m ruff check `
  dialogue\src dialogue\tests `
  adapters\unreal\src adapters\unreal\scripts adapters\unreal\tests `
  backend\app backend\tests
python -m ruff format --check `
  dialogue\src dialogue\tests `
  adapters\unreal\src adapters\unreal\scripts adapters\unreal\tests `
  backend\app backend\tests
python -m mypy cir\src preview\src dialogue\src adapters\unreal\src backend\app
python dialogue\scripts\export_artifacts.py --check
python adapters\unreal\scripts\export_artifacts.py --check
python -m pytest dialogue\tests adapters\unreal\tests backend\tests -q
```

## 2. Confirm the source bundle retains the staged scene

Use the Dialogue ZIP that already passed `docs/acceptance/dialogue-engine-v0.1.md`. The accepted
office example is named `office-dialogue.tts.zip`.

```powershell
$source = Join-Path $PWD "office-dialogue.tts.source"
if (Test-Path $source) {
    throw "Choose a new empty source-inspection directory: $source already exists."
}
Expand-Archive .\office-dialogue.tts.zip -DestinationPath $source
$cir = Get-Content "$source\project.cir.json" -Raw | ConvertFrom-Json

$cir.characters | Select-Object id, asset_uri
$cir.scenes[0].beats |
  ForEach-Object { $_.performances } |
  Select-Object character_id, @{Name="animation";Expression={$_.motion.asset_uri}}
```

For full regression acceptance, Mina and Arjun must retain their accepted Skeletal Mesh paths and
the four performances must retain compatible Anim Sequence paths. If those fields are empty, the
bundle can still test automatic WAV import, but it cannot prove animation preservation. Build a new
Dialogue bundle from the previously accepted staged CIR and legitimate source audio instead. Do
not label AI-generated WAV files as recorded audio; preserve their TTS provenance and disclosure.

## 3. Start the backend

In terminal A:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Confirm `http://127.0.0.1:8000/health` reports `{"status":"ok"}`.

## 4. Build the Unreal import package

In terminal B:

```powershell
Invoke-WebRequest `
  -Uri http://127.0.0.1:8000/api/v1/adapters/unreal/dialogue-bundle `
  -Method Post `
  -ContentType "application/zip" `
  -InFile .\office-dialogue.tts.zip `
  -OutFile .\office-dialogue.unreal-v0.6.zip

$output = Join-Path $PWD "office-dialogue.unreal-v0.6"
if (Test-Path $output) {
    throw "Choose a new empty Unreal-package directory: $output already exists."
}
Expand-Archive .\office-dialogue.unreal-v0.6.zip -DestinationPath $output

$plan = Get-Content "$output\unreal.plan.json" -Raw | ConvertFrom-Json
$plan.adapter_version
$plan.audio_imports |
  Select-Object source_cue_id, source_relative_path, source_sha256, asset_path
$plan.sequences[0].audio_sections |
  Select-Object source_cue_id, actor_binding_id, start_frame, end_frame, timing_source
$plan.sequences[0].animation_sections.Count
```

For the live bundle accepted on 2026-07-17, expect:

- adapter version `0.6.0`;
- two audio imports under `/Game/CutSceneAI/Audio`;
- Mina at frames `120-178`;
- Arjun at frames `216-302`;
- `timing_source=dialogue_manifest` for both sections; and
- four animation sections when the source bundle used the fully staged CIR.

The output ZIP must also retain `dialogue.manifest.json`, `project.cir.json`, both WAV files, and
`AI_VOICE_DISCLOSURE.txt` when the source audio is AI-generated.

## 5. Prepare Unreal without losing work

1. Open the accepted `CutSceneAIStudio` project in Unreal Engine 5.8.0.
2. Confirm **Python Editor Script Plugin**, **Editor Scripting Utilities**, and **Sequencer
   Scripting** remain enabled.
3. Back up or duplicate any manually edited `LS_SceneMeeting` asset.
4. Intentionally delete `/Game/CutSceneAI/Sequences/LS_SceneMeeting`, then empty no other content.
5. Search `/Game/CutSceneAI/Audio` for the two planned `SW_Dialogue...` names. They must not already
   exist. If they do, preserve or delete them intentionally before continuing.
6. Keep the extracted package intact. The Python file must remain beside its `audio` directory.

The importer performs its own complete conflict preflight and refuses to replace anything. Do not
weaken that guard to make the test pass.

## 6. Execute the importer

1. Choose **File > Execute Python Script**.
2. Select `office-dialogue.unreal-v0.6\cutsceneai-unreal-import.py` from the extracted folder.
3. Wait for completion, then inspect **Output Log**.

Expected success lines include two mappings and the sequence creation:

```text
CutSceneAI imported audio/...mina-1.wav -> /Game/CutSceneAI/Audio/SW_Dialogue...
CutSceneAI imported audio/...arjun-2.wav -> /Game/CutSceneAI/Audio/SW_Dialogue...
CutSceneAI created /Game/CutSceneAI/Sequences/LS_SceneMeeting
```

Warnings about placeholder environment objects, inferred camera transforms, and metadata-only
camera movement are expected at this milestone. A traceback, checksum failure, missing WAV,
failed Sound Wave verification, or replacement warning is not a pass.

## 7. Inspect and save the editable result

1. Confirm two new Sound Wave assets exist under `/Game/CutSceneAI/Audio` and each plays.
2. Open `LS_SceneMeeting`.
3. Confirm **CutSceneAI Dialogue - ACT_Mina** has one section at `120-178`.
4. Confirm **CutSceneAI Dialogue - ACT_Arjun** has one section at `216-302`.
5. Confirm both sections are non-looping and reference the newly imported Sound Waves.
6. Confirm Mina and Arjun still have two Animation sections each when the source bundle retained
   the staged asset references.
7. Scrub all four camera cuts and play the sequence once.
8. Choose **Save All**.

## 8. Restart persistence gate

Close Unreal completely, reopen the project, load `L_CutSceneAI_Preview`, and reopen
`LS_SceneMeeting`. Confirm:

- both imported Sound Waves remain playable;
- both dialogue tracks and exact end frames persist;
- both mannequin meshes and four animation sections persist;
- all four camera cuts remain correct; and
- no actor or camera has reset to the world origin.

## 9. Movie Render Queue gate

1. Queue `LS_SceneMeeting` in Movie Render Queue.
2. Render frames `0-431` to a new empty output directory.
3. Keep PNG output and add **Export > WAV Audio**.
4. Render after the restart, not only in the original editor session.

Acceptance requires 432 PNG files (`0000-0431`), two audible lines at approximately 5 and 9
seconds, no looping, both animated characters visible, changing camera angles, no black or empty
frames, and no output-log errors. The rendered timing should correspond to Mina `120-178` and Arjun
`216-302`, not the old v0.5 performance-end ranges.

## 10. Report the result

```text
Adapter version: 0.6.0
Unreal version: 5.8.0
Audio imports created: 2
Mina section: 120-178
Arjun section: 216-302
Sound Waves persisted after restart:
Tracks persisted after restart:
Mina and Arjun animated after restart:
Camera cuts correct after restart:
MRQ completed:
PNG frame count:
First/last PNG:
WAV output present:
Both lines audible at expected times:
Audio loops:
Black/empty frames:
Output-log errors:
```

## Failure handling

- `invalid_dialogue_bundle`: keep the source ZIP unchanged and inspect the returned message. Do not
  bypass manifest, hash, disclosure, or path validation.
- `Refusing to replace existing assets`: back up and resolve every listed Unreal asset
  intentionally, then rerun the same script.
- `Bundled WAV checksum does not match`: delete the extracted folder and expand the server-produced
  ZIP again. Do not edit the WAV inside the package.
- `Bundled WAV file does not exist`: execute the script from the intact extracted folder rather
  than copying the `.py` file elsewhere.
