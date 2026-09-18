# CutSceneAI Studio V3 outside-user workflow v0.1

This document maps the September 8, 2026 CutSceneAI V3 Master Specification to the current
Studio implementation. It deliberately distinguishes implemented product workflow from contracts,
research evidence, and remaining engine/model gates.

## V3 user workflow

The product workflow is:

1. Connect a Unity or Unreal project.
2. Discover supported project capabilities and objects.
3. Enter a natural-language cutscene request.
4. Generate and validate CIR.
5. Bind generic CIR roles to project objects.
6. Generate or resolve body, facial, dialogue/audio, camera, and interaction artifacts.
7. Compile the validated CIR plus bindings through the selected engine adapter.
8. Preview authoritatively in the connected engine.
9. Apply natural-language edits as validated CIR revisions and incremental engine updates.
10. Save/render/read back and preserve parity/evidence artifacts.

The browser storyboard is a planning preview. The authoritative interactive preview remains the
Unity Timeline/Game view or Unreal Sequencer/editor viewport.

## Implemented in the current Studio layer

- Local Studio project registry under `.cutsceneai-studio/state`.
- Unity and Unreal project-path validation.
- Scoped filesystem preflight for likely project assets, scenes/timelines, version markers, and
  adapter-relevant paths.
- A bridge-manifest API contract for future engine-native scanners.
- Natural-language Director API and CIR validation.
- Deterministic storyboard preview.
- Manual role binding with deterministic candidate suggestions.
- Binding validation with required character roles separated from optional environment roles.
- Deterministic Generated Performance request planning for body, facial, and camera modalities.
- Bound Unity/Unreal adapter-plan compilation.
- Bound importer generation.
- Product UI split into Studio, Projects, and Evidence views.
- Explicit separation of the retained S02 research result from the general product workflow.
- Backend capability reporting so missing gates appear in the UI instead of being presented as
  completed behavior.

## Important evidence boundary

Filesystem preflight is not engine-native capability verification. It cannot establish current-level
actor identity, valid Humanoid/Mannequin rig compatibility, morph/blendshape support, or live camera
state. Those claims require an engine-side bridge.

Preparing a performance generation plan is not model inference. The repository has strict provider
contracts and generated-performance packaging, but the Studio backend still needs general provider
execution/orchestration before arbitrary prompts can become complete performance bundles.

Generating an importer is not engine execution. The engine runner/bridge must execute the adapter,
focus the native preview, read the result back, and return evidence before the UI can mark realization
complete.

## Remaining blocking gates

### 1. Engine-native project bridge

Implement Unity and Unreal integrations that publish verified capability manifests with stable object
IDs, rig compatibility, active scene/map state, cameras, props, facial capabilities, timebase, engine
version, and supported operations.

### 2. General performance provider orchestration

Connect real body, facial, and camera providers to the existing provider protocols. Normalize outputs,
assemble the deterministic Generated Performance Package, retain provenance/hashes, and expose job
progress to the Studio UI.

The retained S02 motion is research evidence for one motion and must not be used as a fake general
provider.

### 3. Native engine execution and preview handoff

Implement the bidirectional runner that executes a generated realization in the connected editor,
opens/focuses the Level Sequence or Timeline, reports progress, and returns native readback/render
evidence.

Unity native AnimationClip/Timeline playback also needs the known S02 realization issue resolved;
direct canonical runtime playback is research evidence but not a substitute for the final native
Timeline gate.

### 4. Facial/dialogue realization

Complete an engine-tested facial/lip-sync path at the supported representation level, including
character compatibility checks. Body-only characters must remain valid when a scene does not require
facial tracks.

### 5. Natural-language incremental editing

Implement edit interpretation against the current CIR, targeted patches, validation, CIR revision
history, dependency-local regeneration, engine incremental update, and undo/redo.

### 6. Paper-grade evaluation

Run the predefined multi-scene benchmark, repeat controlled generations, retain failures as well as
passes, and report portability, repeatability, reliability, editability, efficiency, and quality.

## Acceptance rule

The complete V3 workflow is accepted only when a user can connect a real project, generate a new
scene without editing source code, bind roles, obtain generated performance, realize and preview the
cutscene in the selected engine, make at least one natural-language edit, and retain readback/evidence
that matches the scoped research claims.
