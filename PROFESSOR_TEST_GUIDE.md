# CutSceneAI v0.1 — Professor Test Guide

Evaluation branch: Cutsceneai_test-v.1
Repository: Nithin0553/CutSceneAI-Studio
Prepared: 2026-09-27

This guide provides the shortest reproducible path for evaluating the current CutSceneAI Studio research prototype. The codebase is engine-neutral at the CIR/performance-contract layer and has Unity and Unreal realization paths. The browser storyboard is a planning preview; the authoritative 3D result is the connected engine Timeline or Sequencer view.

## 1. What is included

The branch includes the CIR models and validation, FastAPI backend, React/Vite Studio frontend, Generated Performance Package contracts, Unity Timeline and Unreal Sequencer adapters, local editor bridges, semantic parity/readback tooling, automated tests, and acceptance documentation.

A complete Unity project or Unreal .uproject is not embedded in this repository. Native-engine testing requires a compatible project supplied separately.

## 2. Prerequisites

For the simplest test path use Windows with Git, Python 3.12, Node.js/npm, and Unity 6 for the current Unity path or Unreal Engine 5.8 for the Unreal path. Internet access is needed for initial Python/npm dependency installation. An OpenAI API key is needed when testing natural-language Director generation.

Full generated body motion additionally requires a configured CutSceneAI body-motion provider. Without that external provider, the Studio can still be inspected and the CIR, binding, storyboard, and performance-planning stages can be evaluated, but the complete Generated Performance Package cannot be produced.

## 3. Package the supplied Unity project (project owner)

If the Unity project is being handed to the evaluator separately, create a clean source-only archive from the CutSceneAI repository root:

    .\scripts\Package-CutSceneAI-Unity-Professor.ps1 -ProjectPath "C:\path\to\your\UnityProject"

The script verifies the Unity project root, reads the Unity editor version, packages only Assets, Packages, and ProjectSettings, adds a package manifest/readme, excludes generated folders such as Library, Temp, Logs, obj, Builds, and IDE caches, and writes a SHA-256 checksum.

By default the output is written under:

    build\professor-submission

Upload the generated ZIP and its .sha256.txt file together. The evaluator should extract the ZIP before opening the project in Unity Hub.

## 4. Clone the exact evaluation branch


Run in PowerShell:

    git clone --branch Cutsceneai_test-v.1 --single-branch https://github.com/Nithin0553/CutSceneAI-Studio.git
    cd CutSceneAI-Studio
    git branch --show-current

Expected branch:

    Cutsceneai_test-v.1

## 5. Configure the Director without sharing secrets

Create a local environment file:

    Copy-Item .env.example .env.local

Open .env.local and set your own API key:

    OPENAI_API_KEY=your_key_here

Do not commit .env.local. It is ignored by Git.

If a compatible external body provider is available, configure it separately. The repository contains scripts/Configure-CutSceneAI-BodyProvider.ps1 for a supported HTTPS or localhost provider endpoint. Provider credentials are local-only and must never be committed.

## 6. Start the backend and frontend

From the repository root:

    .\scripts\Start-CutSceneAI-Studio.ps1

The launcher creates or repairs the repository Python environment, installs required local packages when needed, installs frontend dependencies when needed, and starts:

- API: http://127.0.0.1:8000
- Studio: http://127.0.0.1:5173

A healthy backend returns {"status":"ok"} from http://127.0.0.1:8000/health.

Keep the launcher terminal open while testing.

## 7. Connect an engine project

In Projects, connect the local root folder of the supplied Unity or Unreal project. For Unity, the folder must be the project root containing Assets, Packages, and ProjectSettings. For Unreal, select the project root containing the .uproject file.

Return to Studio, select the connected project, and choose Install bridge.

For Unity the backend installs managed bridge files into:

    Assets/Editor/CutSceneAI/CutSceneAIStudioBridge.cs
    Assets/Editor/CutSceneAI/CutSceneAIHallwayBenchmarkSetup.cs
    Assets/CutSceneAI/Bridge/cutsceneai-bridge.json

The generated bridge configuration points to the local API at http://127.0.0.1:8000.

Open the Unity project and allow scripts to compile. Keep Unity and the CutSceneAI launcher running on the same computer. After a successful heartbeat, Studio should show the bridge as connected.

## 8. Run the Studio workflow

Use the text from SAMPLE_PROMPT.txt:

    A guard walks through an abandoned hallway, hears a noise, stops, turns toward a door, and quietly asks, "Who is there?"

Then evaluate the workflow in this order:

1. Generate CIR — creates and validates an engine-neutral cinematic plan.
2. Bind cinematic roles — map required CIR roles to compatible objects in the connected project.
3. Validate bindings — required roles must be valid before later stages are enabled.
4. Prepare performance — creates deterministic body, facial, and camera generation requests and hashes.
5. Generate performance — available only when the required body provider reports ready.
6. Compile realization — builds the selected engine bound adapter plan.
7. Build native performance — requires both a live engine bridge and a successfully generated verified performance package.
8. Use the engine controls and readback to inspect the authoritative Unity Timeline or Unreal Sequencer result.

The Studio intentionally disables later buttons when their prerequisites are not satisfied.

## 9. What to inspect

Useful evaluation artifacts include the generated CIR JSON, deterministic planning storyboard, role-binding manifest, performance plan and run ID, Generated Performance Package ZIP and SHA-256 when generation succeeds, engine realization plan, native Unity Timeline or Unreal Level Sequence, bridge command/readback status, and parity/evidence artifacts.

## 10. Run automated tests

The main README contains the complete quality gate. A focused functional run can be started from the configured Python environment with:

    .\.venv3.12\Scripts\python.exe -m pytest cir\tests preview\tests dialogue\tests performance\tests parity\tests adapters\unreal\tests adapters\unity\tests backend\tests -q --import-mode=importlib

## 11. Important evaluation boundary

This is a research prototype, not a hosted SaaS release. The engine bridge currently uses localhost because the backend must access the same local engine project that Unity or Unreal is editing. A remotely hosted frontend alone is therefore not equivalent to an end-to-end native-engine test.

See KNOWN_LIMITATIONS.md for the current scoped limitations and README_CONTINUATION.md for the deeper research handoff and history.
