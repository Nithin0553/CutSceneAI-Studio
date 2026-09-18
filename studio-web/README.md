# CutSceneAI Studio Web

The Studio web UI is the human-facing layer for the existing CutSceneAI backend.

## Current browser flow

1. Enter a creative brief.
2. Generate typed CIR through the Director API.
3. Validate the CIR contract.
4. Render the engine-neutral storyboard.
5. Download the CIR JSON.
6. Compile Unreal and Unity importer scripts from the same validated project.
7. Review the locked S02 cross-engine research result.

Engine execution remains local. The browser does not claim that a generated importer has run in an installed engine until engine-side evidence is returned.

## Start locally

From the repository root:

    .\scripts\Start-CutSceneAI-Studio.ps1

The launcher starts:

- API: http://127.0.0.1:8000
- Web UI: http://127.0.0.1:5173

The Director requires the existing backend provider configuration, including OPENAI_API_KEY when using the OpenAI backend.

## Research status shown in the UI

The UI reads GET /api/v1/research/s02. The endpoint deliberately keeps the result scoped:

- same hash-locked S02 canonical motion;
- Unreal research realization: pass with known limitation;
- Unity direct canonical runtime realization: pass with known limitation;
- Unity native AnimationClip/Timeline validation: pending;
- no claim of empirical universality across every possible humanoid motion.

## Next integration layer

The next product step is a local CutSceneAI Runner API that can accept a generated job from this page, invoke the installed Unreal/Unity tooling on the user machine, stream progress, and return evidence/readback artifacts to the browser.
