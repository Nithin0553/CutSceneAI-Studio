# Known Limitations — CutSceneAI test v0.1

This file records the boundaries of the professor evaluation branch so current prototype behavior is not confused with the broader product vision.

## Local engine architecture

The current Studio-to-engine bridge is intentionally local. Installing the bridge writes http://127.0.0.1:8000 as the backend URL. Unity or Unreal and the CutSceneAI backend should therefore run on the same computer for the native-engine test.

The React/Vite frontend can be viewed independently, but a cloud-hosted frontend by itself does not provide native access to a professor's local Unity or Unreal project.

## Engine project not stored in this repository

This repository contains adapter and bridge source code, but it does not currently contain a complete Unity project with Assets, Packages, and ProjectSettings, or an Unreal .uproject. The engine project used for the demonstration must be supplied as a separate package.

## External provider requirement

Natural-language CIR generation requires a configured Director provider. The current OpenAI Director expects OPENAI_API_KEY in the local environment.

Full Generated Performance Package creation requires a configured body-motion provider. Facial and camera baseline generation exist in the backend, but body-provider readiness remains a gate for the complete performance run.

## Research-grade visual quality

The repository separates semantic and contract parity from cinematic polish. A semantic or native-realization PASS does not mean the resulting animation has production-quality acting or visuals.

## Native realization prerequisites

Build native performance is intentionally disabled unless required role bindings are valid, a performance package has been generated successfully, and the connected engine bridge has sent a fresh heartbeat.

If Unity reports HTTP 0: Cannot connect to destination host, first verify that the CutSceneAI API is still running at http://127.0.0.1:8000/health on the same machine, then refresh or reinstall the bridge and wait for a fresh heartbeat before retrying.

## Scope of claims

Synthetic and unit tests validate contracts and automation logic. They are not substitutes for a real Unity or Unreal import, save, restart, readback, and render acceptance run. The deeper acceptance history and research evidence rules are documented in README_CONTINUATION.md and docs/acceptance/.
