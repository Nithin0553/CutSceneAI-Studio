# CutSceneAI Studio — Authoritative Continuation / AI Handoff

**Last updated:** 2026-09-16  
**Purpose:** This is the authoritative handoff for continuing the CutSceneAI Studio research and implementation work in a new chat, with another AI model, or by another developer. Read this file before changing code, rerunning model inference, modifying Unreal/Unity assets, or claiming a research result.

> **Important status rule:** A PASS in this project is always scoped. A semantic PASS, package-integrity PASS, preflight PASS, conversion PASS, controller-probe PASS, engine import PASS, visual PASS, and final research PASS are different things. Never upgrade one scope into another claim.

---

## 1. Project identity and core objective

**Repository:** `Nithin0553/CutSceneAI-Studio`  
**Primary working branch:** `agent/cross-engine-parity-v0.1`  
**GitHub branch head observed on 2026-09-16:** `cd81c5f41d30dab09b0ffc0e052eee421719ec25`  
**Latest observed commit title:** `Cover UE 5.8 data-model frame-rate accessor`  
**Main Windows checkout historically used:** `D:\Research\CutSceneAI Foundation v0.1\cutscene-ai`  
**Research/evidence root:** `E:\CutSceneAI-Research`

CutSceneAI Studio is a platform-agnostic cutscene-generation research system. The architectural principle is:

```text
Natural-language cutscene request
        ↓
Director / planning layer
        ↓
Typed, validated Cinematic Intermediate Representation (CIR)
        ↓
Hash/fingerprint + generation plan
        ↓
Generated Performance Package
(body + face/lip-sync + camera + audio + provenance)
        ↓
Engine-specific adapters only at the final realization boundary
        ↓
Unreal Engine 5.8 Level Sequence      Unity 6 Timeline
        ↓                                  ↓
Save → close/restart → readback → render in each engine
        ↓                                  ↓
Canonicalized engine evidence / semantic readbacks
        └─────────────── parity verifier ───────────────┘
                              ↓
                        PASS / FAIL evidence
```

The research claim is **not** that Unreal and Unity produce pixel-identical images. The claim to prove is that one unchanged engine-neutral source preserves the same cinematic meaning and generated performance across engine-specific native timelines, with traceable evidence.

---

## 2. Two different definitions of “final” — do not confuse them

### 2.1 Minimum final research/paper deliverable

For the current research paper, the project must prove all of the following:

1. **One unchanged portable source** is used for both Unreal and Unity.
2. **Real AI-generated full-body motion** is part of the final result; pre-authored idle clips are not sufficient.
3. **Real generated facial/lip-sync performance** is represented by a canonical portable facial curve format and realized natively.
4. **Generated camera motion/shot data** is represented portably and realized natively.
5. **Synchronized dialogue audio** is packaged once and realized natively in both engines.
6. The same package carries full provenance: model/checkpoint, prompt, configuration, seed, hashes, and timing.
7. Unreal and Unity each import the unchanged package into editable native assets.
8. Both engines save the native assets, close/restart, independently read the saved timelines back, and fully render them.
9. Strict cross-engine verification passes with no missing-realization errors for the required modalities.
10. Reliability, repeatability, portability, and native-realization metrics are collected using the fixed experiment plan.
11. Failed first-pass attempts stay in the denominator; evidence cannot be cherry-picked.
12. The final paper clearly distinguishes semantic parity from visual/cinematic quality.

### 2.2 Broader product vision after the minimum paper gate

The broader CutSceneAI vision includes:

- user connects an Unreal/Unity project;
- CutSceneAI scans the project and discovers available characters, environments, props, rigs, and relevant assets;
- available characters can be shown to the user as role-binding choices/dropdowns;
- the user writes a cutscene in natural language;
- the Director/agent system creates or revises CIR;
- body motion, facial performance, dialogue, cameras, environmental/establishing shots, and timing are generated;
- the user previews the result;
- the user edits the cutscene through natural-language requests;
- edits become traceable CIR diffs rather than opaque engine-only changes;
- the system re-realizes the scene into one or more engines;
- multi-agent orchestration, RAG/cinematic knowledge, Critic/visual reasoning, and richer environment generation are added as the product matures.

The broad vision is a target. It must **not** be described as already completed.

---

## 3. What has already been proven

### 3.1 CIR foundation and backend foundation — completed

The repository already contains the engine-neutral foundation:

- CIR v0.1 typed models and validation;
- unknown-field rejection and semantic validation;
- character, environment, performance, dialogue, facial, motion, beat, shot, and camera planning data;
- deterministic CIR serialization;
- source SHA-256 and canonical semantic fingerprinting;
- FastAPI validation/generation/preview/adapter endpoints;
- Director Agent v0.1;
- Preview v0.1 portable preview manifest and SVG storyboard support;
- Dialogue Engine v0.1 with recorded WAV and generated-speech packaging;
- Unreal and Unity adapters;
- engine-neutral parity readbacks and verification;
- Generated Performance Package contracts and native realization harnesses.

The repository-level documentation and acceptance files are listed later in this document.

### 3.2 Baseline Unreal “Office Dialogue” — completed as baseline evidence

The baseline Unreal fixture used Mina and Arjun in an office-dialogue scene. Important accepted baseline facts:

- Unreal project sequence: `/Game/CutSceneAI/Sequences/LS_SceneMeeting`;
- Mina mapped to the Quinn mannequin proxy;
- Arjun mapped to the Manny mannequin proxy;
- visible placeholder environment objects included a contract and conference table;
- four animation sections using `MM_Idle` were created:
  - Mina: frames `0–96`;
  - Mina: frames `96–336`;
  - Arjun: frames `96–336`;
  - Arjun: frames `336–432`;
- dialogue/audio sections were imported and synchronized;
- four camera cuts and semantic markers were created;
- save/restart persistence was verified;
- Movie Render Queue produced a complete 432-frame output (`0000–0431`);
- both actors were visible;
- camera changes worked;
- there were no black/empty frames.

This baseline proves the adapter and timeline workflow. It does **not** prove final generative body motion because those idle clips are pre-authored.

### 3.3 Gate 1 cross-engine semantic parity — PASS

Gate 1 is one of the strongest completed milestones.

One unchanged `office-dialogue.cir.json` was compiled into native Unreal and Unity timelines. Both engine timelines were saved, the editors were reopened, independent readbacks were exported, and the parity verifier compared the recovered semantics.

Accepted Gate 1 result:

- duration: 432 frames;
- verifier exit code: `0`;
- `equivalent = true`;
- `error_count = 0`;
- source hash/fingerprint matched;
- semantic identities matched;
- actor bindings matched;
- performance timing matched;
- dialogue cue timing/order matched;
- camera timing matched after persistence.

**Research claim allowed now:** semantic portability has been demonstrated for the Office Dialogue fixture.

**Research claim not allowed yet:** full AI-generated native-media equivalence has not been demonstrated.

The earlier Gate 1 report explicitly recorded Unity native-realization gaps for the baseline fixture (four performance cues without final native generated clips and two dialogue cues without native audio sections). Those warnings are why Gate 1 is semantic portability evidence, not final strict generated-performance evidence.

### 3.4 Repository software-quality baseline — strong and already established

The last full repository quality baseline recorded before the recent engine-specific debugging work was:

- 504 tests passed;
- branch-aware coverage: 97.46% (minimum required: 95%);
- Generated Performance suite: 185 tests with 100% statement and branch coverage;
- Ruff passed;
- formatting checks passed;
- mypy passed across 93 source files;
- all generated schema/artifact drift checks passed;
- CI passed on Python 3.11, 3.12, and 3.13.

Do not assume a newer local experimental tool package changed these repository numbers unless the full suite is rerun and recorded.

---

## 4. Generated Performance Package work already completed in the repository

The repository already implements the software contracts needed for portable generated performance.

### 4.1 Body motion contract

- canonical 22-joint humanoid representation;
- root translation;
- joint rotations as normalized quaternions;
- exact-frame deterministic resampling;
- explicit reference-pose semantics;
- validation for finite values, quaternion normalization, frame coverage, and timing.

### 4.2 Facial/lip-sync contract

- canonical ARKit-52 curve ordering;
- bounded weights;
- deterministic frame resampling;
- engine mapping support for Unity blendshapes and Unreal morph targets.

### 4.3 Camera contract

- transform curves;
- world-space/canonical coordinate handling;
- focal-length curves;
- filmback metadata;
- deterministic translation/interpolation and quaternion resampling;
- camera cut/timing mapping.

### 4.4 Audio/provenance contract

- frame-accurate dialogue timing;
- speaker identity;
- WAV hashes;
- model/provider provenance;
- AI-voice disclosure support;
- deterministic portable bundle assembly.

### 4.5 Package verification

The package loader/assembler is designed to enforce:

- exact expected file/entry sets;
- entry hashes;
- path safety;
- archive size/compression safety;
- source-to-package identity;
- prompt/model/configuration/seed provenance;
- timing consistency;
- deterministic manifests.

### 4.6 Native engine harnesses

Repository automation exists for:

- Unity native realization;
- Unreal native realization;
- import/save;
- restart/readback;
- rendering;
- strict four-modality evidence collection;
- experiment ledger/report generation.

The existence of these harnesses does not mean the real final generated package has already passed them.

---

## 5. Model/runtime environment already prepared

Heavy model/runtime assets were moved away from the normal repository and placed under the research root on drive E.

### 5.1 Important research-root layout

The main external research root is:

```text
E:\CutSceneAI-Research
```

Important subdirectories used over the project include:

```text
E:\CutSceneAI-Research\cache
E:\CutSceneAI-Research\checkpoints
E:\CutSceneAI-Research\config
E:\CutSceneAI-Research\datasets
E:\CutSceneAI-Research\downloads
E:\CutSceneAI-Research\environments
E:\CutSceneAI-Research\evidence
E:\CutSceneAI-Research\experiments
E:\CutSceneAI-Research\generated
E:\CutSceneAI-Research\hashes
E:\CutSceneAI-Research\logs
E:\CutSceneAI-Research\models
E:\CutSceneAI-Research\outputs
E:\CutSceneAI-Research\plans
E:\CutSceneAI-Research\tools
```

Do not move large model/checkpoint/cache data back to `C:` unless explicitly required.

### 5.2 MDM runtime assets — installed and validated

The Human Motion Diffusion Model (MDM) runtime setup was successfully prepared and validated.

Important retained assets:

```text
E:\CutSceneAI-Research\models\mdm\checkpoints\humanml-encoder-512-50steps\model000750000.pt
E:\CutSceneAI-Research\models\mdm\checkpoints\humanml-encoder-512-50steps\args.json
E:\CutSceneAI-Research\models\mdm\downloads\humanml-encoder-512-50steps.zip
E:\CutSceneAI-Research\models\mdm\downloads\smpl.zip
E:\CutSceneAI-Research\models\mdm\assets\body_models\smpl\SMPL_NEUTRAL.pkl
E:\CutSceneAI-Research\cache\clip\ViT-B-32.pt
E:\CutSceneAI-Research\environments\manifests\mdm-runtime-assets.json
```

Recorded hashes from validated setup:

- MDM model checkpoint `model000750000.pt`:
  `0fbdc8547c8f262b8838645586790b55f983d90db3bb7ed58e4b5d49429587ca`
- CLIP ViT-B/32:
  `40d365715913c9da98579312b702a82c18be219cc2a73407c4526f58eba950af`
- HumanML encoder ZIP:
  `4d87cd647b89752d16867f25972e30e561ea7e3e138098abb1d333ddb3d157ac`
- SMPL archive:
  `26a100f2b765fb14214aa57dd1a5e74f92a3994e97539f9a749fd50611224dc2`

HumanML3D source was pinned during setup; the retained installation evidence recorded commit/tree identifiers.

### 5.3 Runtime setup logs that previously passed

Examples of retained PASS evidence include:

```text
E:\CutSceneAI-Research\logs\mdm-pytorch-20260830-171247.txt
E:\CutSceneAI-Research\logs\mdm-source-20260830-173952.txt
E:\CutSceneAI-Research\logs\mdm-inference-dependencies-20260830-180113.txt
E:\CutSceneAI-Research\logs\mdm-runtime-assets-20260830-190006.txt
E:\CutSceneAI-Research\logs\mdm-inference-validation-20260830-191021-20260830-191902.txt
E:\CutSceneAI-Research\logs\mdm-motion-bridge-preflight-20260830-214911.txt
E:\CutSceneAI-Research\logs\mdm-motion-contract-validation-20260830-224557.txt
E:\CutSceneAI-Research\logs\mdm-motion-repeatability-20260830-225856.txt
```

Therefore: **do not restart model installation from scratch merely because a later Unreal import fails.** The current principal blockers are downstream engine realization/integration issues, not an uninstalled MDM environment.

---

## 6. Current Request 1 / S02 motion lineage — exact status

This is the most important active work.

### 6.1 Retained Request 1 MDM inference source

A valid retained model-output tensor from Request 1 was recovered without rerunning inference:

```text
E:\CutSceneAI-Research\evidence\motion-generation\cutsceneai-request1-v0.5-phase-preview-v0.1\inference\results.npy
```

Source SHA-256:

```text
f0aee2823ed8c306e0fefebf266f6acfed1fb81d9fa247068e50fc2bf5fcdff0
```

Retained source shape used by the salvage workflow:

```text
(12, 22, 3, 50)
```

Important rule: the recovery workflow intentionally **did not rerun MDM inference** and **did not modify the v0.5 source evidence**.

### 6.2 Salvage/preview recovery v0.4 — PASS for its scope

Evidence root:

```text
E:\CutSceneAI-Research\evidence\motion-generation\cutsceneai-request1-v0.6-salvage-preview-recovery-v0.4\run-20260912-232321-e6c1be06bf114307a4520160
```

The workflow selected walk candidate `W02`, then derived `S01`, `S02`, and `S03` variants. `S02` was later chosen because it better represented the intended “walk forward, stop, and look down” behavior.

Comparison artifacts:

```text
E:\CutSceneAI-Research\evidence\motion-generation\cutsceneai-request1-v0.6-salvage-preview-recovery-v0.4\run-20260912-232321-e6c1be06bf114307a4520160\output\previews\all-salvage-candidates-comparison.mp4
E:\CutSceneAI-Research\evidence\motion-generation\cutsceneai-request1-v0.6-salvage-preview-recovery-v0.4\run-20260912-232321-e6c1be06bf114307a4520160\output\previews\all-salvage-candidates-contact-sheet.png
```

This recovery PASS means valid retained source data and preview candidates were recovered. It was not engine acceptance.

### 6.3 S02 semantic acceptance — PASS, but explicitly not production polish

Hash-locked semantic acceptance run:

```text
E:\CutSceneAI-Research\evidence\motion-generation\cutsceneai-request1-v0.6-s02-semantic-acceptance-v0.2\run-20260913-033643-6de3dc3e23d84bc380e21aa9
```

Accepted artifact:

```text
E:\CutSceneAI-Research\evidence\motion-generation\cutsceneai-request1-v0.6-s02-semantic-acceptance-v0.2\run-20260913-033643-6de3dc3e23d84bc380e21aa9\accepted\S02-preview-motion.npy
```

Accepted artifact SHA-256:

```text
031b7a550a02c619a120b7b514157191056d32fcf0e9236a5c48a9af1ef464f9
```

Accepted shape/timing:

- joints: 22;
- axes: 3;
- frames: 96;
- FPS: 24;
- all values finite;
- semantic intent: `WALK_FORWARD_STOP_AND_LOOK_DOWN`;
- selected construction: `W02 + L02`.

The semantic acceptance record deliberately says:

```text
SEMANTIC_RESEARCH_PASS_NOT_PRODUCTION_ANIMATION_POLISH
```

That sentence must remain visible in future handoffs. The user later visually observed that the motion exists but still does not look good enough. Therefore the current project has two separate questions:

1. Can the accepted motion be realized correctly and portably in both engines? — still being debugged.
2. Is the motion visually/cinematically good enough for the final demonstration? — not yet established.

Do not “fix” perceived quality by silently altering the hash-locked S02 artifact. If the final visual-quality gate requires a better motion, create a new versioned candidate/acceptance artifact with new provenance and hashes rather than rewriting S02 evidence.

### 6.4 Canonical body conversion — PASS for conversion scope

Canonical conversion run:

```text
E:\CutSceneAI-Research\evidence\motion-generation\cutsceneai-request1-v0.6-s02-canonical-body-conversion-v0.2\run-20260913-220817-a09ad311db3842e8b4813889cd93b18f
```

Canonical artifact:

```text
E:\CutSceneAI-Research\evidence\motion-generation\cutsceneai-request1-v0.6-s02-canonical-body-conversion-v0.2\run-20260913-220817-a09ad311db3842e8b4813889cd93b18f\canonical\S02-canonical-body-motion.json
```

Canonical artifact SHA-256:

```text
f708f7a0ca84f055d9c357a6c72bc30f726108400c8c9b799d728f8f58fca461
```

Canonical format/profile:

```text
format:           cutsceneai.motion+json
skeleton_profile: cutsceneai-humanoid-v1
frame_count:      96
fps:              24
```

Conversion algorithm recorded:

```text
cutsceneai-position-to-parent-local-swing-v0.1
```

Converter SHA-256:

```text
ff3f56055dc766ee02688d03392b9dafbb6f3f0247463b20cbd6fbb5d38592dc
```

Reference-skeleton SHA-256:

```text
00a9f6245b17d682606320089e6df2ae68bda602f011ee66fed0654e3c1aebe0
```

Coordinate boundary recorded during conversion:

```text
source axis:    right-handed, Y-up, +Z-forward
canonical axis: right-handed, Y-up, -Z-forward
```

Direct `.npy` engine import is not permitted. Engines should consume the validated canonical representation/mapping boundary.

---

## 7. Unreal Engine environment and active native-realization debugging

### 7.1 Unreal installation/project

```text
Unreal Engine: 5.8.0
Editor-Cmd:
D:\Research\Unreal\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe

Project:
D:\Research\Unreal\UnrealProjects\CutSceneAIStudio 5.8\CutSceneAIStudio.uproject
```

Current body target used for S02:

```text
Target mesh:
/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple.SKM_Manny_Simple

Target skeleton:
/Game/Characters/Mannequins/Meshes/SK_Mannequin.SK_Mannequin

Target generated animation:
/Game/CutSceneAI/GeneratedPerformance/Request1/S02/AN_Request1_S02
```

The baseline/protected Office Dialogue sequence must not be damaged while debugging Request 1. New generated targets under `/Game/CutSceneAI/GeneratedPerformance/...` are preferred.

### 7.2 S02 Unreal controller probe — important positive result

A disposable diagnostic probe proved the relevant Unreal 5.8 controller path can work.

Probe evidence root/report:

```text
E:\CutSceneAI-Research\evidence\motion-generation\cutsceneai-request1-v0.6-s02-unreal-controller-probe-v0.1\run-20260915-061554-065cea3dad4c40d08dd5264aaf8639b2\reports\unreal-controller-probe-report.json
```

Key diagnosis:

```text
CONTROLLER_PATH_PROVEN:
pelvis track exists and keys can be authored.
Use the observed model/skeleton initialization sequence in the S02 importer.
```

Observed Unreal 5.8 API/controller capabilities included:

- `get_model_interface` available;
- `set_frame_rate` available;
- `set_number_of_frames` available;
- `add_bone_curve` available;
- `add_bone_track` available;
- `insert_bone_track` available;
- `set_bone_track_keys` available.

The probe successfully demonstrated:

- initial animation rate around 30 fps;
- bridge rate 120 fps;
- final rate 24 fps;
- pelvis bone track creation/existence;
- pelvis keys written successfully.

The probe did not constitute final engine acceptance, and one diagnostic cleanup issue was noted (the disposable diagnostic asset was not confirmed deleted).

### 7.3 Unreal import failure history — keep this chronology

Several failures were diagnostic progress, not wasted work. Preserve them.

#### Import v0.2 — frame-rate incompatibility

Error:

```text
AnimationDataController: ... Incompatible frame rate provided:
24 fps not a multiple or factor of 30 fps
```

This motivated the 30 → 120 → 24 compatible bridge strategy.

#### Import v0.3 — animation data model unavailable in that creation path

Error:

```text
The S02 AnimSequence has no animation data model.
```

This motivated disposable controller/data-model probing rather than continuing blind mutation.

#### Import v0.4 — bone-track/import path still failed

A later attempt reached bone-track authoring and reported a runtime error around adding the Unreal pelvis/bone track. Rollback was attempted. The follow-up controller probe was created specifically to isolate and prove the correct UE 5.8 API sequence.

#### Import v0.5.1 — latest preserved engine-import error before branch fix

Evidence root:

```text
E:\CutSceneAI-Research\evidence\motion-generation\cutsceneai-request1-v0.6-s02-engine-parity-import-v0.5.1\run-20260915-212634-acd7289ce62241fa9533280a2350edce
```

Report:

```text
...\reports\unreal-import-report.json
```

Log:

```text
...\logs\unreal-import-editor.log
```

Evidence ZIP was preserved at the time under Downloads:

```text
C:\Users\nithi\Downloads\CutSceneAI-S02-Unreal-Import-v0.5.1-run-20260915-212634-acd7289ce62241fa9533280a2350edce-Evidence.zip
```

ZIP SHA-256:

```text
0286d1fce03cd2c0c1f87d3518ab0f28bc52cd09c6b1251c68234b8c730e2b6d
```

Latest preserved v0.5.1 error:

```text
AttributeError: 'AnimationDataModel' object has no attribute 'frame_rate'
```

The log showed that reading `frame_rate` as an editor property/attribute was wrong for this UE 5.8 data-model wrapper. The later Git branch head `cd81c5f...` adds test coverage for a `get_frame_rate()` accessor. Before rerunning, sync the local checkout and verify the generated/importer code actually uses the proven accessor path, not only the test expectation.

### 7.4 Corrupt/stale generated asset cleanup risk

The v0.5.1 failure log also recorded an Unreal warning that force-deleting the failed generated `AN_Request1_S02` asset could not fully unload the package because an `AnimSequencerController` still referenced the model interface. Unreal warned that the package could be potentially corrupt and recommended restarting before deletion.

Therefore:

- do not repeatedly force-delete a still-referenced animation asset in the same editor process;
- use clean process boundaries;
- prefer a new destination/versioned asset when appropriate;
- if deletion is required, restart the editor first and verify no lingering asset/package remains;
- never accept a run that reports rollback failure or a potentially corrupt destination package.

---

## 8. Separate active blocker: Gate 1A Unreal character-context export/build

On 2026-09-16 a separate Gate 1A context-export/plugin build attempt failed before compilation because UnrealBuildTool could not validate the Win64 SDK.

Evidence root:

```text
E:\CutSceneAI-Research\evidence\context-export\cutsceneai-gate1a-unreal-character-context-v0.1\run-20260916-024620-e9111c93fe574d7aaaf7708be16be691
```

Primary build log:

```text
...\logs\build-plugin.log
```

Diagnostic file created under Downloads:

```text
C:\Users\nithi\Downloads\CutSceneAI-Gate1A-build-errors.txt
```

Important error:

```text
Platform Win64 is not a valid platform to build. SDK validation failed:
Sdk: not found. Required version 10.0.19041.0.
```

Result:

```text
Failed (OtherCompilationError)
AutomationTool ExitCode=6
```

This is an infrastructure/build-toolchain blocker for that plugin/context-export route. It is **not evidence that CIR, MDM, canonical conversion, or the previously proven Unreal Python controller path failed**.

Before retrying Gate 1A, verify the Windows SDK/Visual Studio Build Tools installation and Unreal's SDK discovery. Because the system `C:` drive is low on space, keep large caches/build outputs on the external research drive where practical, but do not invent unsupported SDK paths. First verify what UnrealBuildTool actually detects.

---

## 9. Storage state and disk rules

The project has already consumed substantial storage. The user reported that the Windows `C:` drive has very little free space and wants external storage used wherever practical.

Current practical policy:

- repository source stays in the established checkout unless intentionally migrated;
- heavy research assets, model checkpoints, caches, outputs, evidence, renders, temporary packages, and experiments should remain under `E:\CutSceneAI-Research` or another explicitly approved external path;
- do not duplicate large model archives unnecessarily;
- use retained evidence rather than rerunning downloads/inference when hashes prove it is the same artifact;
- keep system-drive-only requirements (for example some Visual Studio/Windows SDK components) minimal and deliberate;
- do not delete old failed evidence runs simply to recover space unless they have been safely archived and the user explicitly approves. Failed runs are research evidence.

---

## 10. Unity status

Unity support is implemented in the repository and was used successfully for the earlier semantic Gate 1. However, the **current S02 real generated body-motion path has not yet completed the equivalent strict Unity native realization**.

An early parity preflight on 2026-09-13 intentionally blocked engine launch because the system had not yet hash-bound all conversion/reference-pose/target information and did not discover the expected Unity 6000.0 project/editor in that bounded search. After that preflight, the canonical conversion work advanced and Unreal probing became the immediate focus.

Do not interpret the early Unity discovery blocker as “Unity support is missing.” The repository has a Unity adapter and Gate 1 semantic evidence. The specific new S02 generated-performance run still needs a clean target/project discovery, import, save/restart/readback, render, and parity pass using the same canonical S02 source.

---

## 11. Exact working method to follow

This project has become reliable because it uses evidence-first, stage-gated work. Any AI continuing the project should follow this method.

### Rule 1 — establish scope before every run

Every tool/run must declare whether it is:

- discovery/preflight;
- source recovery;
- semantic acceptance;
- canonical conversion;
- engine API probe;
- import/save test;
- restart/readback acceptance;
- visual acceptance;
- strict cross-engine parity;
- experiment/reliability run.

Never call a narrow PASS a final project PASS.

### Rule 2 — check Git and hashes before mutation

Before a high-value engine run:

1. verify repository path;
2. verify current branch;
3. record `git rev-parse HEAD`;
4. ensure expected source files are unchanged;
5. verify accepted artifact SHA-256;
6. verify canonical artifact SHA-256;
7. verify engine/project paths;
8. verify destination target does not already exist or define an explicit safe cleanup/versioning strategy.

### Rule 3 — protect accepted artifacts

Once an artifact is accepted and hash-locked:

- never edit it in place;
- never regenerate it silently;
- never substitute a visually “better” file under the same path/hash identity;
- create a new versioned run if the artifact needs improvement.

### Rule 4 — reuse validated inference outputs

Model inference is expensive and introduces variance. If valid retained output exists and the next stage is adapter/debugging work, reuse it. Do not rerun MDM merely because Unreal import failed.

### Rule 5 — debug engine APIs with disposable targets

When an Unreal/Unity API behavior is uncertain:

- use a disposable asset/scene;
- probe one operation at a time;
- record the engine version and exposed API surface;
- only then update the protected/generated importer.

This method already paid off with the UE 5.8 controller probe.

### Rule 6 — one failure, one preserved evidence package

For each failed run, preserve:

- run ID;
- inputs and hashes;
- configuration;
- script/tool package version;
- editor log;
- structured report;
- rollback result;
- resulting asset-existence state;
- evidence ZIP/hash when generated.

Never erase a failed attempt from the experiment story.

### Rule 7 — process boundaries matter

Final engine evidence should separate lifecycle stages:

- import/save;
- engine/editor shutdown;
- restart;
- readback;
- full render.

This guards against transient in-memory state masquerading as persisted success.

### Rule 8 — protect the baseline scene

Do not overwrite `/Game/CutSceneAI/Sequences/LS_SceneMeeting` while debugging generated Request 1 motion. Use dedicated generated-performance destinations.

### Rule 9 — visual quality is a separate gate

A structurally correct animation can still look bad. After engine correctness passes, perform a visual/cinematic review for:

- recognizable semantic action;
- natural pose transitions;
- foot sliding/contact;
- root motion stability;
- limb twisting;
- spine/head behavior;
- timing;
- camera framing;
- dialogue synchronization;
- facial expression/lip sync;
- narrative readability.

Do not hide a quality problem behind a semantic/structural PASS.

### Rule 10 — no pixel-equality requirement across engines

Unreal and Unity use different renderers. Cross-engine acceptance should focus on:

- same source identity;
- same actors/roles;
- same generated performance semantics;
- same timing;
- same audio cues;
- corresponding cameras/shot intent;
- matching canonical/modality hashes and mappings;
- native realization completeness.

### Rule 11 — preserve Git discipline

Existing working convention:

- continue on `agent/cross-engine-parity-v0.1` unless the user explicitly changes branches;
- use direct commits/pushes for this research branch;
- do not create unnecessary PRs for the continuation workflow;
- do not commit local generated evidence or model assets unless the repository contract explicitly expects a small schema/fixture/document;
- the root `build/` directory is local/generated and historically untracked; do not casually delete or commit it.

### Rule 12 — prefer fixes in the repository, not one-off Downloads scripts

Temporary self-contained packages under `E:\CutSceneAI-Research\tools` are useful for controlled experiments, but once an engine compatibility behavior is proven, the durable fix and regression test should live in the repository so the next AI does not repeat the same discovery.

---

## 12. Immediate next plan of action

The following order is recommended. Do not jump directly to the 50-run experiment while S02 cannot yet complete one clean native realization.

### Phase A — synchronize and stabilize the Unreal S02 importer

1. Pull/sync `agent/cross-engine-parity-v0.1` and confirm the current branch head.
2. Inspect the generated native-realization/importer path and confirm UE 5.8 frame rate is read using the proven method (`get_frame_rate()` or the exact data-model interface shown by the controller probe), not via nonexistent `.frame_rate` property access.
3. Confirm the importer follows the proven animation-data model/controller initialization sequence.
4. Ensure the 30 → 120 → 24 compatible frame-rate bridge is applied safely.
5. Avoid stale/corrupt destination assets. Start from a clean editor process and a clean/versioned destination.
6. Import all expected canonical bone tracks and keys.
7. Verify expected bone-track count (`22`) and frame count (`96`).
8. Save the generated AnimSequence.
9. Exit the editor cleanly.
10. Restart Unreal.
11. Read the AnimSequence/timeline back and verify the generated asset persisted.
12. Render/preview the motion in the intended character context.
13. Record structural acceptance separately from visual acceptance.

### Phase B — solve visual motion quality, if still unacceptable

The user has already observed that motion appears but does not look good enough. After importer correctness is stable:

1. diagnose whether the visual problem comes from source motion, conversion, skeleton mapping, rest-pose alignment, root orientation, joint twist, coordinate conversion, or retargeting;
2. compare canonical skeleton motion to the Unreal result;
3. check pelvis/root transform, foot contact, leg chains, spine/head rotations, and reference-pose offsets;
4. if the canonical artifact is correct but engine mapping is bad, fix the mapping/retargeting without changing canonical S02;
5. if canonical S02 itself is not good enough for the final demo, create a new candidate/versioned semantic acceptance rather than replacing the S02 evidence in place.

### Phase C — fix Gate 1A character-context build toolchain

1. verify whether Windows SDK 10.0.19041.0 or an Unreal-compatible newer SDK is installed;
2. verify Visual Studio Build Tools/C++ workload state;
3. verify UnrealBuildTool SDK discovery;
4. keep large intermediate/build/cache outputs off `C:` where supported;
5. rerun the Gate 1A build only after the SDK preflight passes.

The context-export gate is important to the final “scan connected project and discover available characters/assets” workflow, but it should not block finishing the currently proven Python-controller S02 import path if the two tasks are independent.

### Phase D — mirror S02 into Unity using the same canonical artifact

After Unreal body realization is correct:

1. discover/verify the exact Unity 6 project/editor path;
2. bind a clean native target;
3. use the same canonical S02 artifact/hash;
4. import to native Unity animation/timeline data;
5. save and close;
6. reopen;
7. export readback;
8. render;
9. compare the canonicalized results to Unreal and to the source.

### Phase E — complete the four-modality generated package

Body-only progress is not the final paper gate. Build one real unchanged package containing:

- body motion;
- face/lip-sync curves;
- generated camera trajectories/lens data;
- synchronized audio;
- provenance and hashes.

Realize the exact same package in Unreal and Unity.

### Phase F — strict final cross-engine acceptance

Require:

- no missing modality;
- no placeholder realization;
- no unhandled engine errors;
- save/restart/readback in both engines;
- complete renders;
- source/package hashes unchanged;
- canonical timeline/parity report PASS;
- visual inspection recorded.

### Phase G — scaled research experiment

Run the fixed evaluation plan:

- 10 scenes;
- 5 seeds per scene;
- 50 first-pass attempts total;
- failed attempts remain in the denominator;
- selected cases get three clean same-source/same-seed repeatability runs;
- collect package hashes, mapping hashes, timeline fingerprints, engine logs, readbacks, render manifests, timings, failures, and repair counts.

Compute/report:

- reliability;
- repeatability;
- portability;
- native realization;
- supporting efficiency/timing information;
- qualitative/cinematic quality evidence.

---

## 13. Final definition of done

### 13.1 Research/paper “DONE”

The paper is ready only when there is retained evidence for a real generated performance that:

- starts from a natural-language scene request and/or its resulting validated CIR;
- has an immutable source hash/fingerprint;
- has generated body, face/lip-sync, camera, and audio artifacts;
- has full model/config/prompt/seed provenance;
- is packaged once;
- is consumed unchanged by Unreal and Unity;
- is realized into editable native assets in both engines;
- survives save/restart;
- can be independently read back;
- fully renders in both engines;
- passes strict modality and semantic parity checks;
- has no missing-realization warnings/errors at the final strict gate;
- has reliability/repeatability results from the fixed experiment design;
- includes honest disclosure of any remaining limitations and visual-quality issues.

### 13.2 Full CutSceneAI product “DONE”

The broader system is complete when an outside user can:

1. connect a supported Unreal/Unity project;
2. let CutSceneAI discover usable characters/assets/environment context;
3. select/bind characters to story roles;
4. describe a cutscene in natural language;
5. generate a platform-neutral CIR and performance package;
6. automatically realize it into a native timeline;
7. preview the scene;
8. ask for natural-language edits such as “make Mina more nervous,” “move the camera closer,” “slow the walk,” or “add an establishing shot”;
9. see those changes reflected as traceable/reproducible CIR/performance changes;
10. export/reproduce the same scene in another supported engine while preserving semantic intent;
11. inspect evidence/provenance for what the AI generated and what assets were used;
12. repeat the process reliably without manual low-level timeline authoring.

---

## 14. Known open risks

### Engine API instability

Unreal 5.8 Python wrappers expose some animation APIs differently from prior versions or from assumptions based on properties. Always probe the exact version.

### Retargeting/reference-pose quality

Canonical semantics can pass while the native result looks poor because of skeleton rest-pose, twist, bone-axis, pelvis/root, or retargeting differences.

### Model quality

MDM can generate semantically recognizable motion that is not production-quality. The research should be honest about this and separate semantic correctness from aesthetic quality.

### 4 GB laptop GPU constraints

The previously recorded laptop GPU is an NVIDIA RTX 3050 Laptop GPU with 4 GB VRAM. Heavy inference may require reduced settings, CPU offload, or CPU execution depending on the model.

### Disk pressure

System `C:` storage is constrained. Avoid accidental caches/downloads/build outputs there.

### Windows SDK/toolchain

Gate 1A currently has a concrete SDK-discovery blocker. Do not repeatedly run BuildPlugin until it is resolved.

### Unity target discovery

The current S02 run still needs an exact Unity 6 target/project and full generated-performance native realization.

### Visual quality vs. paper timeline

The project is on track architecturally, but the final demonstration must not stop at “motion exists.” Quality needs to be sufficient for a convincing research demo or clearly bounded in the paper.

---

## 15. What not to do

Do **not**:

- claim the project is finished because Gate 1 passed;
- claim S02 is polished because semantic acceptance passed;
- rerun MDM every time an Unreal script fails;
- modify the accepted S02 `.npy` or canonical JSON in place;
- use a different generated body artifact in Unreal and Unity and still call it a portability test;
- overwrite the baseline Office Dialogue Level Sequence while debugging;
- hide failed attempts;
- remove hashes/provenance to make a pipeline simpler;
- call a synthetic unit test “engine evidence”;
- call an engine import without restart/readback “persistence evidence”;
- call a structural pass “visual quality pass”;
- compare pixels between Unity and Unreal as the portability definition;
- put large model/checkpoint/cache data on `C:` without a clear reason;
- force-delete referenced Unreal assets repeatedly in the same process after the editor has warned about package corruption;
- move to scaled experiments before one clean four-modality two-engine result exists.

---

## 16. Repository map

Key repository folders:

```text
cir/                     Typed CIR package, validation, schema, examples
backend/                 FastAPI application and API tests
preview/                 Portable preview compiler/storyboard
agents/                  Director/specialist-agent code
dialogue/                Recorded/generated dialogue packaging and provenance
performance/             Generated Performance Package, canonical modalities, providers
parity/                  Engine-neutral readbacks and verifier
adapters/unreal/         Unreal Sequencer/native realization integration
adapters/unity/          Unity Timeline/native realization integration
scripts/                  Cross-engine orchestration scripts
cutsceneai_test_support/ Shared deterministic test fixtures
shared/                  Shared project components
infrastructure/          Deployment/support assets
docs/acceptance/         Repeatable acceptance procedures
ROADMAP.md               Product/research milestones
CHANGELOG.md             User-visible project changes
README.md                General repository entry point
README_CONTINUATION.md   This authoritative AI/developer handoff
```

---

## 17. Critical repository documentation to read

Before modifying the related subsystem, read:

```text
README.md
ROADMAP.md
CHANGELOG.md
performance/README.md
parity/README.md
adapters/unreal/README.md
adapters/unity/README.md
docs/acceptance/cross-engine-parity-v0.1.md
docs/acceptance/generated-performance-ssd-gate.md
docs/acceptance/generated-performance-native-realization-v0.1.md
docs/acceptance/generated-performance-experiment-v0.1.md
docs/acceptance/unreal-adapter-v0.6.md
docs/acceptance/dialogue-engine-v0.1.md
```

The broader research vision is also described in the CutSceneAI research/specification documents prepared outside the repository. That vision includes multi-agent/RAG orchestration, environment/establishing shots, automatic project context discovery, and natural-language editing. Treat those as product/research targets unless repository evidence explicitly marks them complete.

---

## 18. Important evidence paths — quick index

### MDM/runtime

```text
E:\CutSceneAI-Research\models\mdm\...
E:\CutSceneAI-Research\environments\manifests\mdm-runtime-assets.json
E:\CutSceneAI-Research\logs\mdm-*.txt
```

### Retained Request 1 inference

```text
E:\CutSceneAI-Research\evidence\motion-generation\cutsceneai-request1-v0.5-phase-preview-v0.1\inference\results.npy
```

### Salvage previews

```text
E:\CutSceneAI-Research\evidence\motion-generation\cutsceneai-request1-v0.6-salvage-preview-recovery-v0.4\run-20260912-232321-e6c1be06bf114307a4520160
```

### S02 semantic acceptance

```text
E:\CutSceneAI-Research\evidence\motion-generation\cutsceneai-request1-v0.6-s02-semantic-acceptance-v0.2\run-20260913-033643-6de3dc3e23d84bc380e21aa9
```

### S02 canonical conversion

```text
E:\CutSceneAI-Research\evidence\motion-generation\cutsceneai-request1-v0.6-s02-canonical-body-conversion-v0.2\run-20260913-220817-a09ad311db3842e8b4813889cd93b18f
```

### S02 parity preflight

```text
E:\CutSceneAI-Research\evidence\motion-generation\cutsceneai-request1-v0.6-s02-parity-import-preflight-v0.3\run-20260913-042240-355a832e7e9d48cc901672d3
```

### S02 Unreal controller probe

```text
E:\CutSceneAI-Research\evidence\motion-generation\cutsceneai-request1-v0.6-s02-unreal-controller-probe-v0.1\run-20260915-061554-065cea3dad4c40d08dd5264aaf8639b2
```

### Latest preserved S02 Unreal import v0.5.1 failure

```text
E:\CutSceneAI-Research\evidence\motion-generation\cutsceneai-request1-v0.6-s02-engine-parity-import-v0.5.1\run-20260915-212634-acd7289ce62241fa9533280a2350edce
```

### Gate 1A Unreal character-context build attempt

```text
E:\CutSceneAI-Research\evidence\context-export\cutsceneai-gate1a-unreal-character-context-v0.1\run-20260916-024620-e9111c93fe574d7aaaf7708be16be691
```

---

## 19. Status dashboard as of this handoff

| Area | Status | Meaning |
|---|---|---|
| CIR v0.1 | **DONE** | Typed portable cinematic contract exists and is validated |
| Director/Preview/Dialogue foundations | **DONE** | Implemented and tested at repository level |
| Unreal baseline Office Dialogue | **DONE** | Editable native sequence, cameras/audio/animation, persisted/rendered |
| Unity baseline Timeline | **DONE for Gate 1** | Used successfully for semantic parity fixture |
| Cross-engine semantic Gate 1 | **PASS** | One unchanged CIR survived save/restart/readback semantically |
| Generated Performance contracts | **DONE** | Body/face/camera/audio package and provenance contracts implemented |
| MDM runtime assets | **PASS** | Model/checkpoint/dependencies installed and hashed under research root |
| Request 1 retained inference recovery | **PASS** | Valid retained MDM tensor recovered without rerun |
| S02 semantic acceptance | **PASS (scoped)** | Research semantic pass; explicitly not production-polish acceptance |
| S02 canonical body conversion | **PASS** | 96-frame, 24-fps canonical JSON hash-locked |
| UE 5.8 controller API probe | **PASS (scoped)** | Pelvis track/keys and frame-rate bridge proven on disposable asset |
| S02 Unreal native import | **IN PROGRESS / FAILING** | Latest preserved v0.5.1 failure: wrong frame-rate accessor path; branch now has follow-up coverage |
| S02 Unreal visual quality | **NOT ACCEPTED** | Motion exists but user reports quality is not good enough |
| S02 Unity native import | **NOT YET FINALIZED** | Must use same canonical artifact after Unreal stabilization |
| Gate 1A context export/plugin | **BLOCKED** | Windows SDK 10.0.19041.0 not detected by UnrealBuildTool |
| Full real 4-modality package in both engines | **NOT YET PASSED** | Mandatory next major research gate |
| Strict final two-engine parity/render | **NOT YET PASSED** | Depends on real four-modality realization |
| 10×5 reliability experiment | **NOT STARTED** | Do only after one clean end-to-end result |
| Repeatability experiment | **NOT STARTED** | Three clean runs required for selected cases |
| Natural-language editing product loop | **FUTURE / PARTIAL FOUNDATIONS** | Broader product target, not current completed claim |
| Automatic connected-project character discovery UI | **ACTIVE FUTURE/GATE WORK** | Gate 1A context export is related; not completed end-to-end |

---

## 20. Are we on track?

Architecturally, **yes**. The difficult foundational research pieces—engine-neutral representation, deterministic identity/hashing, two-engine semantic parity, portable generated-performance contracts, MDM runtime preparation, retained inference recovery, canonical body conversion, and evidence-first workflow—are already in place.

The project is not yet at the point where success should be declared. The remaining work is concentrated in the hardest integration layer:

- realizing generated motion cleanly in native engine animation data;
- maintaining cross-engine consistency;
- improving visual motion quality;
- completing all four modalities;
- proving save/restart/readback/render evidence;
- running scaled experiments.

The present Unreal issues are concrete, diagnosable integration/toolchain problems, not a collapse of the overall architecture. The project can succeed, but the continuation model should prioritize correctness and quality over rushing into the final experiment.

---

## 21. New-chat / new-AI starter prompt

Copy this into a new chat if needed:

> Continue the CutSceneAI Studio project using the repository's `README_CONTINUATION.md` as the authoritative handoff. Repository: `Nithin0553/CutSceneAI-Studio`; branch: `agent/cross-engine-parity-v0.1`. First verify the current Git branch/head and do not assume an older commit hash is still current. Preserve accepted hashes and evidence. Do not rerun MDM unless there is a proven reason; the retained Request 1 source and S02 canonical artifact are hash-locked. The current primary task is to stabilize S02 native realization in Unreal Engine 5.8 using the proven controller/data-model path, then perform restart/readback and visual review, then realize the exact same canonical source in Unity. Treat S02 semantic acceptance as `SEMANTIC_RESEARCH_PASS_NOT_PRODUCTION_ANIMATION_POLISH`; do not claim visual acceptance. Also keep the separate Gate 1A blocker visible: UnrealBuildTool reports Windows SDK 10.0.19041.0 not found. Keep large data/evidence on `E:\CutSceneAI-Research` because `C:` is space-constrained. Final research success requires one unchanged four-modality generated package (body, face/lip-sync, camera, audio) realized in Unreal and Unity, save/restart/readback/render evidence, strict parity, and the fixed reliability/repeatability experiments.

---

## 22. Final instruction to any AI model taking over

Do not restart this project from the beginning. Do not replace evidence with assumptions. Read the repository docs, inspect the latest run reports, verify hashes, and continue from the current failing boundary.

The immediate engineering problem is downstream of successful model setup and canonical conversion. Solve the native realization path first, prove it with persisted engine evidence, then improve visual quality, mirror the same artifact into Unity, and only then scale to the full four-modality paper experiment.
