# CutSceneAI Studio

CutSceneAI Studio is a platform-agnostic cinematic generation system. It turns a creative brief into a validated Cinematic Intermediate Representation (CIR), then uses that contract to coordinate characters, full-body motion, facial performance, dialogue, cameras, environments, and engine-specific exports.

The repository is currently at **Foundation v0.1**. The CIR contract and validation API are working; generation agents, preview rendering, and engine adapters follow on top of this stable foundation.

## What works now

- Strict, typed CIR 0.1 models with unknown-field rejection
- Character, environment, performance, dialogue, facial, motion, beat, shot, and camera plans
- Reference, timeline, coordinate-axis, establishing-shot, and environment-detail validation
- A complete office-dialogue fixture with one scene, three beats, and four shots
- `POST /api/v1/cir/validate` with structured success and error responses
- A committed JSON Schema artifact with CI drift detection
- Python 3.11, 3.12, and 3.13 quality gates

## Architecture

| Layer | Responsibility | Status |
| --- | --- | --- |
| CIR | Portable cinematic data contract and domain validation | Foundation v0.1 complete |
| Backend | HTTP boundary for validating and later orchestrating projects | Validation endpoint complete |
| Director and specialist agents | Convert creative intent into CIR plans | Next milestone |
| Preview services | Assemble low-cost visual and audio previews | Planned |
| Engine adapters | Translate CIR into Unreal, then Unity timelines | Planned |

## Local setup

Run these commands from the repository root. Python 3.12 is the recommended local version.

### Windows PowerShell

```powershell
py -3.12 -m venv .venv3.12
.\.venv3.12\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".\cir[dev]" -e ".\backend[dev]"
```

### macOS or Linux

```bash
python3.12 -m venv .venv3.12
source .venv3.12/bin/activate
python -m pip install --upgrade pip
python -m pip install -e "./cir[dev]" -e "./backend[dev]"
```

## Run the quality gate

```powershell
python -m ruff check cir\src cir\scripts cir\tests backend\app backend\tests
python -m ruff format --check cir\src cir\scripts cir\tests backend\app backend\tests
python -m mypy cir\src backend\app
python cir\scripts\export_schema.py --check
python -m pytest cir\tests backend\tests -q --cov=cutsceneai_cir --cov=app --cov-branch --cov-report=term-missing --cov-fail-under=95
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
- `agents/` — Director and specialist agent implementations
- `adapters/` — engine integrations, beginning with Unreal
- `shared/` — reusable fixtures and cross-service components
- `tests/` — future acceptance and integration suites
- `infrastructure/` — deployment assets

## Delivery roadmap

1. **Foundation v0.1:** CIR contract, golden fixture, validation, schema, API, and CI
2. **Director planning:** prompt-to-CIR generation with deterministic structured output and evals
3. **Preview pipeline:** blocking, camera, performance, dialogue, and environment previews
4. **Unreal adapter:** CIR-to-Sequencer export and golden-scene acceptance test
5. **Unity adapter:** portable validation of the same CIR contract
6. **Studio editing:** prompt-driven revisions with traceable CIR diffs
7. **Release:** CineBench++ evaluation, packaging, documentation, and public launch

The immediate next milestone after Foundation is a narrow Director Agent: one prompt in, one validated CIR project out, using the office-dialogue fixture as the first regression target.

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
