# CutSceneAI Studio

CutSceneAI Studio is a platform-agnostic cinematic generation system. It turns a creative brief into a validated Cinematic Intermediate Representation (CIR), then uses that contract to coordinate characters, full-body motion, facial performance, dialogue, cameras, environments, and engine-specific exports.

The repository includes the CIR foundation, Director Agent v0.1, an engine-neutral Preview v0.1
pipeline, an Unreal Adapter v0.6 that produces editable Sequencer imports and imports verified
portable dialogue bundles, and Dialogue Engine v0.1 for recorded WAV ingestion and pluggable
generated speech with exact timing and provenance.

## What works now

- Strict, typed CIR 0.1 models with unknown-field rejection
- Character, environment, performance, dialogue, facial, motion, beat, shot, and camera plans
- Reference, timeline, coordinate-axis, establishing-shot, and environment-detail validation
- A complete office-dialogue fixture with one scene, three beats, and four shots
- `POST /api/v1/cir/validate` with structured success and error responses
- `POST /api/v1/director/generate` for prompt-to-CIR generation
- `POST /api/v1/preview/compile` for deterministic preview manifests
- `POST /api/v1/preview/storyboard.svg` for user-visible storyboard timelines
- `POST /api/v1/adapters/unreal/export` for typed Unreal Sequencer plans
- `POST /api/v1/adapters/unreal/importer.py` for self-contained Unreal Editor import scripts
- `POST /api/v1/adapters/unreal/dialogue-bundle` for verified, self-contained Unreal WAV import
  packages
- `POST /api/v1/dialogue/plan` for deterministic cue IDs, filenames, and frame positions
- `POST /api/v1/dialogue/synthesize` for portable generated-speech WAV bundles
- Recorded PCM WAV bundling through the `cutsceneai-dialogue` CLI
- Exact audio duration, hashes, source provenance, per-character voice profiles, and timing warnings
- Asset-independent Unreal proxy characters, semantic props, and editable interior set shells
- Optional CIR character asset references resolved to editable Unreal Skeletal Mesh spawnables
- Compatible CIR motion asset references resolved to editable, frame-aligned Anim Sequence sections
- Compatible CIR dialogue audio references resolved to editable, frame-aligned, non-looping audio
  sections grouped by speaker
- Portable Dialogue ZIPs verified for archive safety, CIR/manifest consistency, WAV hashes, and
  timing before deterministic Sound Wave import targets are generated
- Committed CIR, Preview, Dialogue, and Unreal JSON Schema artifacts with CI drift detection
- Python 3.11, 3.12, and 3.13 quality gates

## Architecture

| Layer | Responsibility | Status |
| --- | --- | --- |
| CIR | Portable cinematic data contract and domain validation | Foundation v0.1 complete |
| Backend | HTTP boundary for validation, generation, preview, and engine export | v0.1 complete |
| Director and specialist agents | Convert creative intent into CIR plans | Director v0.1 complete |
| Preview services | Compile portable manifests and SVG storyboard timelines | Preview v0.1 complete |
| Dialogue services | Bind recorded WAV or generated speech with timing and provenance | v0.1 complete |
| Engine adapters | Translate CIR into Unreal, then Unity timelines | Unreal v0.6 in engine acceptance; Unity planned |

## Local setup

Run these commands from the repository root. Python 3.12 is the recommended local version.

### Windows PowerShell

```powershell
py -3.12 -m venv .venv3.12
.\.venv3.12\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".\cir[dev]" -e ".\preview[dev]" -e ".\dialogue[dev]" -e ".\adapters\unreal[dev]" -e ".\backend[dev]"
```

### macOS or Linux

```bash
python3.12 -m venv .venv3.12
source .venv3.12/bin/activate
python -m pip install --upgrade pip
python -m pip install -e "./cir[dev]" -e "./preview[dev]" -e "./dialogue[dev]" -e "./adapters/unreal[dev]" -e "./backend[dev]"
```

## Run the quality gate

```powershell
python -m ruff check cir\src cir\scripts cir\tests preview\src preview\scripts preview\tests dialogue\src dialogue\scripts dialogue\tests adapters\unreal\src adapters\unreal\scripts adapters\unreal\tests backend\app backend\tests
python -m ruff format --check cir\src cir\scripts cir\tests preview\src preview\scripts preview\tests dialogue\src dialogue\scripts dialogue\tests adapters\unreal\src adapters\unreal\scripts adapters\unreal\tests backend\app backend\tests
python -m mypy cir\src preview\src dialogue\src adapters\unreal\src backend\app
python cir\scripts\export_schema.py --check
python preview\scripts\export_artifacts.py --check
python dialogue\scripts\export_artifacts.py --check
python adapters\unreal\scripts\export_artifacts.py --check
python -m pytest cir\tests preview\tests dialogue\tests adapters\unreal\tests backend\tests -q --cov=cutsceneai_cir --cov=cutsceneai_preview --cov=cutsceneai_dialogue --cov=cutsceneai_unreal --cov=app --cov-branch --cov-report=term-missing --cov-fail-under=95
```

## Run the API

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs` for the interactive API documentation.

Validate the golden fixture from another PowerShell terminal:

```powershell
$body = Get-Content cir\examples\office-dialogue.cir.json -Raw
Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/api/v1/cir/validate `
  -Method Post `
  -ContentType "application/json" `
  -Body $body | ConvertTo-Json -Depth 5
```

The response should report one scene, three beats, and four shots.

## JSON Schema

The public CIR 0.1 contract is committed at `cir/schemas/cir-v0.1.schema.json`.

After intentionally changing a CIR model, regenerate the artifact and run its drift check:

```powershell
python cir\scripts\export_schema.py
python cir\scripts\export_schema.py --check
```

## Docker

```powershell
docker compose up --build
```

The API is then available at `http://127.0.0.1:8000`.

## Repository layout

- `cir/` — typed CIR package, semantic validation, schema artifact, tests, and examples
- `backend/` — FastAPI application and API tests
- `preview/` — portable preview contract, compiler, storyboard renderer, and fixtures
- `dialogue/` — recorded-audio bundling, pluggable speech generation, timing, and provenance
- `agents/` — Director and specialist agent implementations
- `adapters/` — engine integrations, beginning with Unreal
- `shared/` — reusable fixtures and cross-service components
- `tests/` — future acceptance and integration suites
- `infrastructure/` — deployment assets
- `ROADMAP.md` — ordered product milestones and acceptance gates through Studio v1.0
- `CHANGELOG.md` — user-visible release history and current unreleased scope
- `docs/releases/` — durable release notes and engine acceptance records
- `docs/acceptance/` — repeatable live-provider and engine milestone gates

## Delivery roadmap

The detailed dependency-ordered plan and exit gates are maintained in [`ROADMAP.md`](ROADMAP.md).

1. **Foundation v0.1:** CIR contract, golden fixture, validation, schema, API, and CI
2. **Director planning:** prompt-to-CIR generation with deterministic structured output and evals
3. **Preview pipeline:** blocking, camera, performance, dialogue, and environment previews
4. **Unreal adapter through v0.6:** CIR-to-Sequencer export, asset binding, animation and dialogue
   sections, plus verified portable-WAV import; v0.6 Unreal 5.8 acceptance is next
5. **Unreal production pipeline:** environment resolution,
   camera trajectories, body motion, and facial performance
6. **Cross-engine validation:** CIR 0.2 plus Unity timeline parity
7. **Studio editing:** prompt-driven revisions with traceable CIR diffs
8. **Release:** CineBench++ evaluation, packaging, hardening, documentation, and public launch

Unreal Adapter v0.5 completed acceptance in Unreal Engine 5.8.0 on 2026-07-17. It adds typed
dialogue audio sections for explicit Unreal `/Game/...` sound assets. The speaker tracks persisted
after restart, and Movie Render Queue produced 432 non-empty PNG frames plus synchronized WAV audio
without regressing animation or camera cuts. Dialogue Engine v0.1 subsequently passed live speech
acceptance with two audible clips, portable URIs, exact measured ranges, provider provenance, and
the required AI-voice disclosure. Unreal Adapter v0.6 now connects that verified bundle to Unreal;
its real-engine restart and MRQ gate remains pending.
Component tag and GitHub release publication remain deferred until permissions are available.

## Director Agent v0.1

Run the backend from `backend/` with the local environment file:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --env-file ..\.env.local
```

Send `POST /api/v1/director/generate` with JSON such as:

```json
{"prompt":"Stage a tense 20-second office dialogue between two coworkers beside a desk."}
```

Keep `OPENAI_API_KEY` in `.env.local`; never commit it. `CUTSCENEAI_DIRECTOR_MODEL` can override
the default `gpt-5.6-terra` model.

## Preview Pipeline v0.1

Compile the golden CIR fixture into a portable manifest:

```powershell
$body = Get-Content cir\examples\office-dialogue.cir.json -Raw
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/preview/compile -Method Post -ContentType "application/json" -Body $body
```

Render the user-visible storyboard timeline:

```powershell
Invoke-WebRequest -Uri http://127.0.0.1:8000/api/v1/preview/storyboard.svg -Method Post -ContentType "application/json" -Body $body -OutFile office-dialogue.storyboard.svg
Start-Process .\office-dialogue.storyboard.svg
```

## Unreal Adapter v0.6

Export an Unreal Sequencer plan and importer from the same golden CIR fixture:

```powershell
$body = Get-Content cir\examples\office-dialogue.cir.json -Raw
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/adapters/unreal/export -Method Post -ContentType "application/json" -Body $body
Invoke-WebRequest -Uri http://127.0.0.1:8000/api/v1/adapters/unreal/importer.py -Method Post -ContentType "application/json" -Body $body -OutFile cutsceneai-unreal-import.py
```

Enable Unreal Engine 5.8.0's Python Editor Script, Editor Scripting Utilities, and Sequencer
Scripting plugins, then run the generated script with **File > Execute Python Script**. The importer creates
`/Game/CutSceneAI/Sequences/LS_SceneMeeting` with proxy characters, semantic props, an interior shell,
and four camera cuts. When a CIR character supplies `asset_uri` as an Unreal `/Game/...` Skeletal
Mesh object path, the importer binds that asset instead of creating the cylinder proxy. When that
character's performance motion supplies a compatible Unreal `/Game/...` Anim Sequence object path,
the importer adds an editable Animation track with an exact CIR frame range. When dialogue supplies
an Unreal `/Game/...` Sound Wave or Sound Cue object path in `audio_uri`, the importer adds one
non-looping root Audio track per speaker and places the section at the CIR dialogue start frame. It
refuses to overwrite an existing Level Sequence.

Convert an accepted Dialogue v0.1 ZIP directly into an Unreal import package:

```powershell
Invoke-WebRequest `
  -Uri http://127.0.0.1:8000/api/v1/adapters/unreal/dialogue-bundle `
  -Method Post `
  -ContentType "application/zip" `
  -InFile .\office-dialogue.tts.zip `
  -OutFile .\office-dialogue.unreal-v0.6.zip

Expand-Archive `
  .\office-dialogue.unreal-v0.6.zip `
  -DestinationPath .\office-dialogue.unreal-v0.6 `
  -Force
```

Execute the extracted `cutsceneai-unreal-import.py` from disk. Before importing anything, the
script verifies the bundled WAV checksums and refuses every existing Sound Wave or Level Sequence
target. See [`docs/acceptance/unreal-adapter-v0.6.md`](docs/acceptance/unreal-adapter-v0.6.md) for
the Unreal 5.8 restart and MRQ gate.

## Dialogue Engine v0.1

Dialogue Engine plans stable cues, accepts recorded WAV files, or generates speech through a
replaceable backend. See [`dialogue/README.md`](dialogue/README.md) for the contract and usage, and
[`docs/acceptance/dialogue-engine-v0.1.md`](docs/acceptance/dialogue-engine-v0.1.md) for the complete
Windows acceptance gate. Live synthesis is never part of CI.
