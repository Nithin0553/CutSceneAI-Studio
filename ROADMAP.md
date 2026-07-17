# CutSceneAI Studio Roadmap

## North star

A creator supplies a script, reviews an editable preview, generates synchronized character
performance and cinematography, revises the result through natural language, and exports an
engine-native cutscene without manually editing JSON or Python.

The milestones below are ordered by dependency. Existing components keep their independent package
versions until the unified CutSceneAI Studio v1.0 release.

| Order | Milestone | Primary outcome | Exit gate |
| ---: | --- | --- | --- |
| 0 | Foundation and Unreal vertical slice - complete | CIR 0.1, Director 0.1, Preview 0.1, and Unreal Adapter 0.4 | Prompt-to-CIR, storyboard, character and animation bindings, camera cuts, and a 432-frame MRQ render pass |
| 1 | v0.4 release closure - publication deferred | Current documentation, changelog, and release notes; tag when permissions allow | Clean install instructions and the golden-scene acceptance record match `main` |
| 2 | Unreal Adapter v0.5 - dialogue audio binding - complete | Typed, speaker-associated, frame-aligned Sequencer audio sections | Two dialogue clips persist after restart and remain synchronized in MRQ |
| 3 | Dialogue Engine v0.1 - complete | Recorded-audio ingestion, pluggable TTS, voice metadata, provenance, and exact WAV duration calculation | Recorded and generated bundles carry stable CIR audio URIs plus deterministic start/end seconds and frames without changing CIR 0.1 scene pacing |
| 4 | Unreal Adapter v0.6 - portable dialogue import | Verify Dialogue v0.1 bundles, import their WAV files without replacement, resolve portable URIs, and preserve manifest timing | A generated dialogue ZIP creates checksum-verified Sound Waves and exact Sequencer sections that persist after restart and remain synchronized in MRQ |
| 5 | Asset Resolver and Environment v0.1 with Unreal v0.7 | Project asset index, deterministic matching, props, sets, and environment-detail and establishing shots | Office and outdoor fixtures resolve assets predictably with visible fallbacks |
| 6 | Cinematography v0.1 and Unreal v0.8 | Keyframed camera trajectories, focus and lens curves, composition checks, and automated MRQ jobs | Smooth framing passes cinematic checks and renders unattended |
| 7 | Character Performance v0.1 and Unreal v0.9 | Skeleton compatibility, retargeting, root motion, transitions, and pluggable text-to-motion generation | Generated or selected motion works across supported characters without T-poses |
| 8 | Facial Performance v0.1 and Unreal v0.10 | Lip-sync, emotion curves, facial assets, and body-face-audio synchronization | Dialogue stays synchronized after restart and in rendered frames |
| 9 | Multi-Agent Orchestrator and CIR 0.2 | Director, Camera, Performance, Sound, Environment, and Critic agents with RAG, MCP tools, traces, and multi-scene memory | Agents produce valid CIR, preserve continuity, and recover safely from provider failures |
| 10 | Cross-engine portability | Unity Adapter parity plus a Godot contract proof | The same CIR fixture creates equivalent editable Unreal and Unity timelines |
| 11 | Studio Platform v0.1 | Project database, asset storage, background jobs, authentication, secrets, quotas, auditing, and observability | Projects and jobs survive deployment restarts with controlled access |
| 12 | Studio Editor v0.1 | Script upload, storyboard and timeline UI, previews, prompt revisions, CIR diffs, undo, and approvals | A non-programmer creates and revises a cutscene without editing code |
| 13 | CineBench++ v0.1 | Beat, motion, lip-sync, camera, environment, continuity, and editing metrics | Golden scenes meet automated thresholds calibrated with human review |
| 14 | CutSceneAI Studio v1.0 release candidate | Security, performance and cost limits, installers, migrations, docs, samples, and recovery rehearsal | Clean-machine installation, rollback, and full release rehearsal pass |
| 15 | CutSceneAI Studio v1.0 | Supported public product release | Documented Unreal and Unity workflows pass with benchmarks and release support |

## v1.0 acceptance scenes

1. **Office dialogue:** dialogue audio, facial performance, emotional delivery, and camera coverage.
2. **Outdoor action:** generated body motion, environmental context, and moving cameras.
3. **Multi-scene narrative:** persistent emotion, prop state, and continuity.
4. **Cross-engine export:** the same CIR project produces editable Unreal and Unity timelines.

## Delivery rule

Every milestone follows the same evidence chain:

```text
Contract -> implementation -> API -> automated tests -> documentation
-> real-engine acceptance -> merge
```

CineBench++ coverage grows with every milestone rather than being postponed until release candidate
work. For v1.0, CutSceneAI integrates proven motion, speech, and facial providers behind portable
interfaces; training proprietary foundation models and real-time photoreal generation remain post-v1
research.
