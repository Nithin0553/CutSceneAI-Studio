# Unreal Adapter v0.7 acceptance

This gate proves that Asset Resolver v0.1 and Unreal Adapter v0.7 index real project Static Meshes,
resolve reviewed environment intent deterministically, and import editable props and a set without
regressing the accepted Dialogue v0.1 timing, character animation, or camera plan. It also proves
that unresolved outdoor assets remain visible as fallbacks. Run it against Unreal Engine 5.8.0
before merging the milestone.

The generated indexer uses Unreal's documented
[`AssetRegistry`](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/AssetRegistry?application_version=5.8)
read API. The importer uses
[`EditorAssetLibrary`](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/EditorAssetLibrary?application_version=5.8)
only after a full non-destructive preflight.

## 1. Automated gate

From the repository root in the v0.7 environment:

```powershell
python -m mypy cir\src preview\src dialogue\src assets\src adapters\unreal\src backend\app
python cir\scripts\export_schema.py --check
python preview\scripts\export_artifacts.py --check
python dialogue\scripts\export_artifacts.py --check
python assets\scripts\export_artifacts.py --check
python adapters\unreal\scripts\export_artifacts.py --check
python -m pytest cir\tests preview\tests dialogue\tests assets\tests adapters\unreal\tests backend\tests -q
```

All commands must pass before opening Unreal.

## 2. Start the backend and download the indexer

Terminal A:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Terminal B:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health

Invoke-WebRequest `
  -Uri http://127.0.0.1:8000/api/v1/adapters/unreal/asset-indexer.py `
  -OutFile .\cutsceneai-unreal-asset-index.py
```

The health response must be `ok`. The downloaded Python file must contain no project-specific
paths.

## 3. Inventory the Unreal project

1. Open `CutSceneAIStudio` in Unreal Engine 5.8.0.
2. Enable **Python Editor Script Plugin**, **Editor Scripting Utilities**, and
   **Sequencer Scripting**.
3. Choose **File > Execute Python Script** and select
   `cutsceneai-unreal-asset-index.py`.
4. Confirm the Output Log reports:

```text
CutSceneAI indexed <count> Static Mesh assets -> ...\Saved\CutSceneAI\unreal-project.asset-index.json
```

The Content Browser must not gain, lose, rename, or resave an asset. The output file is an
inventory, not an approval. Every entry initially has `kind=environment_prop`.

Set the exact output path and inspect it:

```powershell
$generatedIndexPath = "D:\Path\To\CutSceneAIStudio\Saved\CutSceneAI\unreal-project.asset-index.json"
$generated = Get-Content $generatedIndexPath -Raw | ConvertFrom-Json

"Indexed assets: $($generated.assets.Count)"
$generated.assets |
  Select-Object name, asset_uri, kind |
  Sort-Object asset_uri |
  Format-Table -AutoSize
```

Choose three distinct existing `/Game/...` Static Mesh object paths:

- A small mesh to represent the unsigned contract.
- A table or desk mesh.
- A complete room/set mesh. If the project has no complete set mesh, duplicate a reviewed
  project mesh for this acceptance fixture and treat it only as the set proof.

Do not use a Skeletal Mesh, Blueprint, World, redirector, `/Engine/...` path, or nonexistent path.

## 4. Create the reviewed office index

Replace the three values below with object paths copied from Unreal:

```powershell
$contractUri = "/Game/Replace/SM_Contract.SM_Contract"
$tableUri = "/Game/Replace/SM_Table.SM_Table"
$roomSetUri = "/Game/Replace/SM_RoomSet.SM_RoomSet"

$indexedUris = @($generated.assets.asset_uri)
foreach ($uri in @($contractUri, $tableUri, $roomSetUri)) {
  if ($uri -notin $indexedUris) {
    throw "The reviewed asset was not produced by the Unreal indexer: $uri"
  }
}

$curated = [ordered]@{
  schema_version = "0.1.0"
  id = "cutsceneai-studio-reviewed-assets"
  name = "CutSceneAI Studio Reviewed Assets"
  target_engine = "Unreal Engine"
  target_engine_version = "5.8.0"
  assets = @(
    [ordered]@{
      id = "office-contract"
      name = "Unsigned Contract"
      kind = "environment_prop"
      asset_uri = $contractUri
      aliases = @("contract", "legal document")
      keywords = @("paper", "signature", "unsigned")
      location_terms = @("office", "conference room")
      priority = 90
    },
    [ordered]@{
      id = "office-conference-table"
      name = "Conference Table"
      kind = "environment_prop"
      asset_uri = $tableUri
      aliases = @("meeting table", "conference-table")
      keywords = @("desk", "office", "table")
      location_terms = @("office", "conference room")
      priority = 80
    },
    [ordered]@{
      id = "office-conference-room"
      name = "Office Conference Room Set"
      kind = "environment_set"
      asset_uri = $roomSetUri
      aliases = @("Corporate conference room")
      keywords = @("office", "conference", "interior")
      location_terms = @("corporate conference room", "office")
      priority = 100
    }
  )
}

$curatedPath = Join-Path $PWD "unreal-project.reviewed.asset-index.json"
$curated | ConvertTo-Json -Depth 20 | Set-Content $curatedPath -Encoding utf8
```

This curation is the human approval boundary. The resolver does not invent these roles.

## 5. Resolve and package the office fixture

```powershell
$project = Get-Content .\cir\examples\office-dialogue.cir.json -Raw |
  ConvertFrom-Json
$index = Get-Content $curatedPath -Raw | ConvertFrom-Json
$request = @{project = $project; asset_index = $index} |
  ConvertTo-Json -Depth 40

$resolution = Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/api/v1/assets/resolve `
  -Method Post `
  -ContentType "application/json" `
  -Body $request

$resolution.resolutions |
  Select-Object source_kind, source_id, status, asset_id, score, matched_terms |
  Format-Table -AutoSize

"Warnings: $($resolution.warnings.Count)"
```

Expected:

- `contract` -> `office-contract`, `matched`
- `conference-table` -> `office-conference-table`, `matched`
- `scene-meeting` -> `office-conference-room`, `matched`
- Three non-empty scores and matched-term lists
- Zero warnings

Build a cumulative package from the already accepted staged Dialogue bundle and the reviewed Asset
Index. This reuses the verified WAV files and preserves their manifest timing, provenance, and AI
voice disclosure; it does not make a TTS request.

```powershell
$dialogueBundle = Join-Path $PWD "office-dialogue.staged.tts.zip"
$package = Join-Path $PWD "office-dialogue.dialogue-environment.unreal-v0.7.zip"
$output = Join-Path $PWD "office-dialogue.dialogue-environment.unreal-v0.7"

if (-not (Test-Path $dialogueBundle)) {
  throw "Accepted staged Dialogue bundle is missing: $dialogueBundle"
}
if (Test-Path $package) { throw "Output already exists: $package" }
if (Test-Path $output) { throw "Output already exists: $output" }

curl.exe --fail-with-body `
  --form "dialogue_bundle_file=@$dialogueBundle;type=application/zip" `
  --form "asset_index_file=@$curatedPath;type=application/json" `
  --output "$package" `
  http://127.0.0.1:8000/api/v1/adapters/unreal/dialogue-environment-bundle

if ($LASTEXITCODE -ne 0) {
  throw "The cumulative Unreal package request failed with exit code $LASTEXITCODE."
}

Expand-Archive $package -DestinationPath $output
$plan = Get-Content "$output\unreal.plan.json" -Raw | ConvertFrom-Json
$packagedResolution = Get-Content "$output\asset.resolution.json" -Raw |
  ConvertFrom-Json

"Adapter: $($plan.adapter_version)"
"Audio imports: $($plan.audio_imports.Count)"
"Audio sections: $($plan.sequences[0].audio_sections.Count)"
"Animation sections: $($plan.sequences[0].animation_sections.Count)"
"Cameras: $($plan.sequences[0].cameras.Count)"
"Index SHA-256: $($plan.asset_resolution.asset_index_sha256)"
"Resolution SHA matches plan: $(
  $plan.asset_resolution.asset_index_sha256 -eq
  $packagedResolution.asset_index_sha256
)"
"Set pieces: $($plan.sequences[0].set_pieces.Count)"

$plan.sequences[0].audio_sections |
  Select-Object source_cue_id, actor_binding_id, start_frame, end_frame, timing_source

$plan.sequences[0].actors |
  Where-Object kind -eq "environment" |
  Select-Object source_entity_id, asset_path, placeholder, resolution_status, resolved_asset_id

$plan.sequences[0].set_pieces |
  Select-Object source_scene_id, mesh_asset_path, placeholder, resolution_status, resolved_asset_id
```

Expected:

- Adapter `0.7.0`
- Two audio imports and two audio sections
- Mina: `actor:mina`, frames `120-178`, timing source `dialogue_manifest`
- Arjun: `actor:arjun`, frames `216-302`, timing source `dialogue_manifest`
- Four animation sections and four cameras
- Two resolved environment actors and one resolved set piece
- All three environment objects have `placeholder=False`
- The plan and `asset.resolution.json` contain the same Asset Index SHA-256

## 6. Import and inspect the office sequence

1. Close any open `LS_SceneMeeting` Sequencer tab.
2. Duplicate the accepted v0.6 sequence as `LS_SceneMeeting_v06_Backup` and confirm the backup
   opens.
3. Rename the two accepted v0.6 Sound Waves so the deterministic v0.7 targets are free:

   - `SW_DialogueSceneMeetingBeatConfrontationMina1` ->
     `SW_DialogueSceneMeetingBeatConfrontationMina1_v06_Backup`
   - `SW_DialogueSceneMeetingBeatConfrontationArjun2` ->
     `SW_DialogueSceneMeetingBeatConfrontationArjun2_v06_Backup`

4. In `/Game/CutSceneAI/Audio`, choose **Fix Up Redirectors in Folder**, then confirm both original
   Sound Wave target names are absent.
5. Intentionally delete only the original `/Game/CutSceneAI/Sequences/LS_SceneMeeting`.
6. Confirm the three reviewed Static Mesh object paths from Section 4 still exist.
7. Execute the extracted `cutsceneai-unreal-import.py`.
8. Confirm the Output Log reports both WAV imports, contains `CutSceneAI created
   /Game/CutSceneAI/Sequences/LS_SceneMeeting`, and contains no traceback.
9. Open the sequence and confirm:

   - Mina is audible at frames `120-178`.
   - Arjun is audible at frames `216-302`.
   - Mina and Arjun retain their two character assets and four animation sections.
   - `ACT_Contract` uses the reviewed contract mesh.
   - `ACT_ConferenceTable` uses the reviewed table mesh.
   - `SET_SceneMeeting` uses the reviewed set mesh.
   - The establishing camera covers frames `0-96`.
   - The environment-detail camera covers frames `96-144`.
   - Camera cuts remain at `0`, `96`, `144`, and `336`, ending at `432`.
   - All audio, animation, object, and camera tracks remain editable.
   - The Dialogue manifest still requires AI voice disclosure and identifies the clips as
     TTS-generated.

Execute the same importer a second time. It must refuse the existing Level Sequence before creating
or replacing anything, including the two Sound Waves. This expected refusal proves the
non-destructive conflict gate.

## 7. Prove visible outdoor fallbacks

Create an empty reviewed index and compile the outdoor fixture:

```powershell
$fallbackIndex = [ordered]@{
  schema_version = "0.1.0"
  id = "cutsceneai-fallback-assets"
  name = "CutSceneAI Fallback Acceptance"
  target_engine = "Unreal Engine"
  target_engine_version = "5.8.0"
  assets = @()
}
$outdoor = Get-Content .\assets\examples\outdoor-action.cir.json -Raw |
  ConvertFrom-Json
$fallbackRequest = @{
  project = $outdoor
  asset_index = $fallbackIndex
} | ConvertTo-Json -Depth 40

$fallbackResolution = Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/api/v1/assets/resolve `
  -Method Post `
  -ContentType "application/json" `
  -Body $fallbackRequest

$fallbackResolution.resolutions |
  Select-Object source_kind, source_id, status, reason
"Warnings: $($fallbackResolution.warnings.Count)"
```

Expected: `boulder`, `trail-marker`, and `scene-clearing` are all `fallback`, with three warnings.

Build, extract, and execute the outdoor package:

```powershell
$fallbackPackage = Join-Path $PWD "outdoor-action.fallback.unreal-v0.7.zip"
$fallbackOutput = Join-Path $PWD "outdoor-action.fallback.unreal-v0.7"

if (Test-Path $fallbackPackage) { throw "Output already exists: $fallbackPackage" }
if (Test-Path $fallbackOutput) { throw "Output already exists: $fallbackOutput" }

Invoke-WebRequest `
  -Uri http://127.0.0.1:8000/api/v1/adapters/unreal/environment-bundle `
  -Method Post `
  -ContentType "application/json" `
  -Body $fallbackRequest `
  -OutFile $fallbackPackage

Expand-Archive $fallbackPackage -DestinationPath $fallbackOutput
```

In Unreal, execute the extracted importer and open `LS_SceneClearing`. The scout cylinder, boulder
proxy, trail-marker proxy, and floor must be visible. The establishing cut covers `0-96`; the
environment-detail cut covers `96-192`. A traceback or invisible fallback fails the gate.

## 8. Persistence and report

Save all, restart Unreal, reopen both generated sequences, and confirm the bindings, meshes,
fallbacks, cameras, and frame ranges persist.

Report:

```text
Automated gate:
Indexed Static Mesh count:
Indexer created/renamed/deleted Content Browser assets:
Office resolutions (3 matched):
Office warnings:
Mina audible at frames 120-178:
Arjun audible at frames 216-302:
Character assets and four animations preserved:
Dialogue provenance/disclosure preserved:
Office set and props visible/editable:
Office establishing/detail cameras correct:
Second office import refused replacement:
Outdoor resolutions (3 fallback):
Outdoor warnings:
Outdoor fallbacks visible/editable:
Persisted after restart:
Tracebacks or unexpected errors:
Other CutSceneAI warnings:
```

Do not merge or publish a component release until every item is confirmed.
