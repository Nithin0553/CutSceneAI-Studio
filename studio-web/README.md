# CutSceneAI Studio Web

The Studio web UI is the outside-user layer defined by the CutSceneAI V3 workflow.

## Current V3 flow

The UI now separates three concerns:

- **Studio** — project selection, natural-language CIR generation, role binding, performance request
  planning, engine-adapter realization, and planning storyboard.
- **Projects** — local Unity/Unreal registration and scoped project discovery.
- **Evidence** — research results and implementation readiness, kept separate from the product flow.

The intended flow is:

```text
Connect project
  -> capability discovery
  -> natural-language CIR
  -> validation
  -> role binding
  -> generated-performance requests
  -> engine adapter
  -> authoritative engine preview
  -> natural-language revisions
  -> readback / parity / render evidence
```

The application does not mark later stages complete merely because their contracts exist. Engine-native
capability discovery, arbitrary model inference orchestration, automatic engine execution, and the
natural-language edit loop are displayed as remaining gates until their real integrations pass.

## Start locally

From the repository root:

```powershell
.\scripts\Start-CutSceneAI-Studio.ps1
```

The launcher starts:

- API: `http://127.0.0.1:8000`
- Studio: `http://127.0.0.1:5173`

The Director requires the existing provider configuration, including `OPENAI_API_KEY` when using
the OpenAI Director backend.

## Project connection

The Projects screen accepts a local Unity or Unreal project root. The current scanner performs a
targeted filesystem preflight and records only adapter-relevant assets and version markers. It does
not claim to know current scene actors or rig compatibility from file names.

The backend also exposes an engine bridge-manifest contract. Once the Unity/Unreal integrations are
implemented, that manifest replaces filesystem guesses with verified engine state and stable object IDs.

## Preview boundary

The browser storyboard is an engine-neutral planning preview. Per V3, the authoritative interactive
preview is the actual Unity Timeline/Game view or Unreal Sequencer/editor viewport.

## Research evidence

The Evidence view reads `GET /api/v1/research/s02`. S02 remains a scoped cross-engine research
result, not a hard-coded product scene and not evidence that every humanoid motion is universally
supported.

See `docs/acceptance/studio-v3-workflow-v0.1.md` for the exact implemented/missing boundary.
