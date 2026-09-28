# CutSceneAI Cinematic Performance Model — Continuation Handoff

**Last updated:** 2026-09-27  
**Repository:** `Nithin0553/CutSceneAI-Studio`  
**Primary working branch:** `agent/cross-engine-parity-v0.1`

## Why this document exists

This file is the durable handoff for the next phase of CutSceneAI: replacing the weak middle of the current pipeline with a purpose-built, trainable, engine-neutral cinematic performance model.

When continuing in a new ChatGPT conversation, read this file before making architectural or implementation changes. Do not restart from old MDM-only assumptions.

## Current product goal

The target workflow remains:

```text
User connects an existing Unity or Unreal project
→ user describes a cutscene in natural language
→ CutSceneAI generates a CIR
→ user binds CIR roles to actual project characters / objects / environment
→ CutSceneAI creates ONE canonical complete performance
→ Unity and Unreal adapters realize that SAME canonical performance
→ both engines should be semantically and visually equivalent
→ later edits should regenerate only what is necessary
```

Unity and Unreal are realization targets, not motion-generation sources.

## Current architecture that should be preserved

The following infrastructure is valuable and should not be discarded:

- CIR and validation
- project connection and project discovery
- role / asset binding
- Studio UI
- local engine bridge
- Generated Performance Package contracts
- provenance / hashing
- Unity realization path
- Unreal realization path
- readback / verification infrastructure
- natural-language revision foundations

The main failure is not that these pieces do not run. The latest full user-flow test successfully reached native Unity cutscene generation.

## Latest important test result

A complete Unity user flow was exercised:

```text
Connect Unity project
→ install / connect bridge
→ generate CIR
→ bind:
   Guard → RobotKyle verified prefab
   Abandoned Hallway → HallwayEnvironment live scene object
   Closed Door → Door_01 live scene object
→ validate bindings
→ prepare performance
→ generate canonical performance package
→ compile Unity realization
→ build native performance
→ Unity cutscene generated successfully
```

The generated result was visually unacceptable.

The user reported that movement, camera behavior, and the overall cutscene were completely wrong.

This is now considered the central evidence that infrastructure success is not equal to cinematic success.

## What the current system is missing

### 1. A real Motion Director / choreography solver

The current Performance Compiler mainly decomposes CIR performance phases into separate generation requests.

That is not enough.

A real cinematic performance needs explicit coordination of:

- start and end root positions
- root trajectory
- velocity and deceleration
- phase overlap
- foot plants
- turn direction and angle
- body orientation
- head / torso sequencing
- gaze target
- environmental target constraints
- entry and exit poses
- timing relationships
- dialogue timing
- reaction timing

For the benchmark guard scene, the system needs to reason more like:

```text
0.0–3.2  walk toward patrol endpoint
3.0–3.6  decelerate
3.2      hear-noise event
3.3–3.7 reaction
3.6      plant support foot
3.7–4.2 head turns toward Door_01
3.9–4.6 torso follows
4.1–4.9 body rotates with foot repositioning
4.9–6.7 cautious hold / maintain gaze
5.4      dialogue: "Who's there?"
```

These exact values can be generated dynamically, but this level of choreography must exist.

### 2. Scene-conditioned physical constraints

Binding a semantic role to `Door_01` is not enough.

The model / compiler needs actual physical conditioning such as:

- actor world transform
- door world transform
- relative target vector
- required final facing direction
- root path constraints
- target distance
- target visibility
- floor / ground information
- environment bounds
- collision / obstacle information where available

The desired relation is:

```text
semantic target
+ live scene geometry
→ physical constraints
→ generation / refinement
```

not just:

```text
target object ID
→ text prompt
```

### 3. Motion composition and cleanup

Independently generated motion segments do not automatically form a believable performance.

The canonical body pipeline likely needs:

```text
generated segments
→ root alignment
→ pose matching
→ velocity matching
→ transition blending
→ contact detection
→ foot locking
→ grounding
→ IK
→ look-at constraints
→ environmental constraints
→ motion cleanup
→ final canonical motion
```

### 4. Robust retargeting

A generic bone-name map is not enough.

We need explicit abstractions such as:

```text
CanonicalRigProfile
TargetRigProfile
RetargetProfile
```

They should encode:

- canonical reference pose
- target reference pose
- bone basis conversion
- local coordinate axes
- scale ratios
- root / pelvis orientation
- spine distribution
- twist-bone handling
- limb pole vectors
- foot orientation
- IK targets
- hierarchy differences

### 5. A real cinematic camera system

The current camera backend is intentionally only a deterministic baseline.

It does simple procedural movement and does not properly solve:

- actual subject position
- actual target position
- look-at orientation
- framing
- actor bounds
- occlusion
- collision
- shot continuity
- screen composition
- 180-degree rule
- lens continuity
- environment geometry

A real camera subsystem needs to condition on the live scene and canonical actor motion.

### 6. Better facial / dialogue performance

The current facial generator is also a procedural baseline.

Future target:

```text
dialogue text
→ generated / supplied audio
→ phoneme timestamps
→ visemes
→ facial curves
→ emotional expression overlay
→ natural blink / micro-expression
```

### 7. Canonical acceptance before engine realization

The pipeline must stop treating successful files / hashes / importers as success.

Before Unity or Unreal realization, the canonical performance should pass semantic and kinematic checks such as:

- actor actually moves in requested direction
- stop timing is correct
- final facing direction matches target
- gaze error is within tolerance
- planted feet remain stable
- feet do not penetrate the floor
- root motion is continuous
- segment boundaries do not snap
- joint motion is plausible
- dialogue timing is correct
- camera frames intended subjects
- camera does not collide with known geometry

Only a canonical performance that passes this gate should proceed to Unity / Unreal parity testing.

## New strategic direction

Build a purpose-built trainable model for CutSceneAI rather than relying on a generic text-to-motion model as the central intelligence.

Working name:

**CutSceneAI Cinematic Performance Model**

The model should be engine-neutral.

Its job is not to generate Unity or Unreal assets.

Its job is to generate a canonical cinematic performance.

## Proposed model input

The model should condition on a structured combination of:

- natural-language intent
- CIR
- role bindings
- scene graph
- actor transforms
- object transforms
- target relationships
- character / rig profile
- requested timing
- previous pose / motion context
- optional future pose constraints
- dialogue / emotion
- camera intent

Conceptually:

```text
Prompt
+
CIR
+
Scene graph
+
Character state
+
Bound targets
+
Temporal constraints
+
Rig profile
→ CutSceneAI Cinematic Performance Model
```

## Proposed model output

The canonical output should contain, at minimum:

### Body

- root position per frame
- root orientation per frame
- canonical joint rotations
- optional canonical joint positions
- left / right foot contact state
- phase identity
- target identity
- gaze direction / target
- event timing

### Camera

- shot / cut timing
- camera position
- camera rotation
- focal length
- target / subject references
- composition metadata

### Face / dialogue

- dialogue timing
- phoneme / viseme timing where available
- canonical facial curves
- emotion timing

## Proposed model architecture

Do not initially assume one monolithic network is best.

A practical architecture could be:

```text
Prompt / CIR ───────────────┐
                            │
Scene Graph ────────────────┤
                            ↓
Character / Rig ─────→ Scene-Conditioned Encoder
                            ↓
                     Temporal Director
                            ↓
              ┌─────────────┴─────────────┐
              ↓                           ↓
       Body Motion Model            Camera Model
              ↓                           ↓
    Contact / Gaze Head          Composition Head
              └─────────────┬─────────────┘
                            ↓
                  Constraint Refiner
                            ↓
                  Canonical Performance
```

The most important component is the **Temporal Director**.

It should learn coordinated, overlapping cinematic phases rather than treating motion clips as independent sequential requests.

## Body-generation requirement

The body generator should not be merely:

```text
text → motion
```

It should be closer to:

```text
text
+ current pose
+ previous velocity
+ future target pose
+ root path
+ target object / target vector
+ foot contacts
+ duration
+ environment constraints
→ motion
```

Candidate model families may include:

- transformer-based motion generation
- diffusion
- flow matching
- hybrid autoregressive + refinement systems

The architecture should be selected after defining the representation, dataset, losses, and benchmark.

## Training data requirement

The training data problem is at least as important as the model architecture.

Ordinary motion datasets are insufficient because CutSceneAI needs:

```text
motion
+
environment
+
targets
+
events
+
gaze
+
contacts
+
timing
+
camera
```

A training example should look conceptually like:

```text
scene geometry
actor start transform
target object transform
narrative intent
temporal choreography labels
canonical body frames
foot contacts
gaze labels
camera trajectory
dialogue timing
```

## Dataset strategy

A new CutSceneAI dataset can combine:

1. existing public motion / mocap datasets for generic motion priors;
2. synthetic scene-conditioned examples generated in Blender / Unity / Unreal;
3. procedural annotation of:
   - contacts
   - root paths
   - gaze targets
   - target-facing angles
   - environment relationships
   - camera framing
4. curated high-quality cinematic examples;
5. later, manually reviewed or captured scene-performance pairs.

Using existing datasets does not prevent the model from being a new CutSceneAI model if we own the architecture, conditioning, objectives, training pipeline, evaluation, and weights.

## Evaluation targets

Do not use "perfect" as the scientific claim.

Use measurable constraints.

Candidate metrics:

- semantic action completion
- root-path error
- final target-facing error
- gaze-angle error
- planted-foot sliding distance
- ground penetration
- transition jerk
- pose discontinuity
- camera subject visibility
- camera framing error
- camera collision rate
- dialogue synchronization error
- cross-engine parity after realization

Example target criteria for the guard benchmark may eventually be:

- final body facing error to Door_01 < 5 degrees
- head / gaze error < 3 degrees
- planted-foot sliding < 2 cm
- floor penetration < 1 cm
- camera subject visibility > 95%

These thresholds should be validated experimentally rather than treated as fixed final requirements today.

## First benchmark / milestone

Use this scene as the first canonical benchmark:

> A guard walks through an abandoned hallway, hears a noise, stops, turns toward a door, and quietly asks who is there.

Do not hard-code the benchmark.

Create a scene family with varied:

- guard start positions
- guard headings
- door positions
- door headings
- hallway dimensions
- timing
- walk distance
- reaction timing
- camera intent

The first meaningful milestone is:

**Generate one visually correct canonical body performance for the guard scene family before sending it to Unity or Unreal.**

Acceptance should include:

- natural walk
- coherent root trajectory
- believable reaction
- natural deceleration and stop
- correct turn toward the bound door
- coordinated head / torso / body motion
- stable feet
- maintained gaze
- correct dialogue timing
- no obvious skeletal distortion

After canonical acceptance:

1. realize the SAME performance in Unity;
2. realize the SAME performance in Unreal;
3. compare them;
4. fix retargeting / realization differences;
5. only then expand to more complex scenes.

## Development rule from now on

At every step ask:

> Does this directly improve the correctness of the canonical cinematic performance?

If not, it is secondary unless it directly blocks the milestone.

Do not claim success because:

- an API returned 200;
- a performance bundle exists;
- a hash exists;
- an importer ran;
- a Timeline exists;
- a Sequencer exists;
- an animation asset exists;
- readback succeeds.

Success requires semantic and visual evidence.

## Immediate next work

Before writing training code, the next phase should define and freeze:

1. canonical training representation;
2. scene-conditioning representation;
3. choreography / temporal labels;
4. body target representation;
5. contact / gaze labels;
6. camera target representation;
7. training dataset schema;
8. evaluation metrics;
9. first guard-scene training/evaluation dataset;
10. minimum trainable baseline model.

After that, implement the training pipeline and train the first CutSceneAI-specific model.

## Resume instruction for future chats

When starting a new conversation, tell the assistant:

> Read `docs/CUTSCENEAI_CINEMATIC_MODEL_HANDOFF.md` from the `Nithin0553/CutSceneAI-Studio` repository on the current working branch, verify the latest branch/commit state, and continue from the exact latest model-development step. Do not revert to MDM-only development or Unity-specific motion fixes.

Also verify the current branch state before making changes because commits may have been added after this document was written.

## Model-development progress after initial handoff

### 2026-09-27 — Canonical Training Representation v0.1 frozen

Immediate-next-work item 1 is complete.

Frozen shared conventions:

- 30 fps canonical model timebase;
- right-handed, Y-up, -Z-forward, meter coordinate space;
- `cutsceneai-humanoid-v1` canonical skeleton identity;
- continuous 6D rotation representation for model training;
- existing `quaternion_xyzw` retained at the runtime performance-package boundary;
- raw physical values stored in canonical datasets;
- normalization kept as a versioned training transform;
- explicit supervision masks for missing labels and batch padding;
- strict separation of conditioning, targets, and metadata;
- stable symbolic semantic IDs on disk;
- mandatory provenance and deterministic canonicalization.

Authoritative files:

- `docs/model/CANONICAL_TRAINING_REPRESENTATION_V0_1.md`
- `docs/model/contracts/canonical-training-representation-v0.1.json`

**Exact next development step:** define and freeze **Scene Conditioning Representation v0.1**
(immediate-next-work item 2). Do not start model training before the remaining representation,
dataset, and evaluation contracts are frozen.


### 2026-09-28 — Scene Conditioning Representation v0.1 frozen

Immediate-next-work item 2 is complete.

Frozen scene-conditioning rules:

- model-visible scene facts are engine-neutral;
- entity state is stored in canonical world space;
- conditioning rotations use the frozen `rotation_6d_columns` representation;
- semantic type and performance role are distinct;
- bounds, target points, affordances, relationships, and support surfaces are explicit;
- missing scene facts remain explicitly missing rather than being replaced with zeros;
- actor-relative distance, bearing, elevation, and desired-facing features are deterministic derivations;
- character realization asset identity is separate from character scene state;
- prior managed CutSceneAI generated objects are excluded from source-scene conditioning by default;
- dense geometry is optional for the first body baseline;
- engine-specific paths and IDs remain metadata-only.

Authoritative files:

- `docs/model/SCENE_CONDITIONING_REPRESENTATION_V0_1.md`
- `docs/model/contracts/scene-conditioning-representation-v0.1.json`

Repository-state finding:

- Unity currently publishes most raw scene-snapshot facts required by this contract.
- Unreal currently lacks equivalent full `StudioSceneSnapshot` publication; this is a later bridge-parity task and does not alter the model contract.

**Exact next development step:** define and freeze **Choreography / Temporal Representation v0.1**
(immediate-next-work item 3). It must represent overlapping phases, events, targets, root/path goals,
contacts/gaze windows, transition constraints, and future goals before frame-level body generation.

### 2026-09-28 — Choreography / Temporal Representation v0.1 frozen

Immediate-next-work item 3 is complete.

Frozen temporal/choreography rules:

- choreography is engine-neutral and uses the 30-fps canonical model timebase;
- point events and overlapping behavioral phases are separate abstractions;
- phases explicitly declare affected body channels and priority;
- semantically related overlapping phases can be grouped through coordination groups;
- root position/path/velocity, body-facing, gaze, support-contact, target-distance, posture, and hold constraints are explicit;
- hard and soft constraints are distinct;
- sparse root paths are intent-level conditioning, not leaked frame-level body targets;
- choreography is a Temporal Director target but a Body Generator input;
- exact future joint rotations and exact frame contact truth are forbidden from choreography conditioning.

Authoritative files:

- `docs/model/CHOREOGRAPHY_TEMPORAL_REPRESENTATION_V0_1.md`
- `docs/model/contracts/choreography-temporal-representation-v0.1.json`

**Exact next development step:** define and freeze **Canonical Body Target Representation v0.1**
(immediate-next-work item 4). It must define explicit root position/orientation, 22-joint canonical
rotations, optional joint-position auxiliary supervision, continuity/velocity semantics, masks,
and the conversion boundary to the runtime Generated Performance Package.

### 2026-09-28 — Canonical Body Target Representation v0.1 frozen

Immediate-next-work item 4 is complete.

Frozen body-target rules:

- frame-level body targets use the 30-fps canonical model timebase;
- root world position and root world orientation are explicit targets;
- root orientation is not inferred from root velocity and is not permanently folded into pelvis articulation;
- all 22 canonical joint rotations are parent-local `rotation_6d_columns`;
- optional 22-joint root-relative positions are auxiliary supervision;
- linear/angular velocities are deterministic derived features rather than duplicated mandatory source truth;
- body sequences are temporally continuous;
- padding exists only at batch time and uses an explicit frame-valid mask;
- exact contact and gaze supervision remain separate target contracts;
- model-specific diffusion/flow/latent outputs must decode to this canonical physical body representation before evaluation;
- current runtime `BodyMotionArtifact v0.1` lacks explicit root orientation, so trained-model integration requires a versioned runtime motion contract that preserves it.

Authoritative files:

- `docs/model/CANONICAL_BODY_TARGET_REPRESENTATION_V0_1.md`
- `docs/model/contracts/canonical-body-target-representation-v0.1.json`

**Exact next development step:** define and freeze **Contact / Gaze Target Representation v0.1**
(immediate-next-work item 5).

### 2026-09-28 — Contact / Gaze Target Representation v0.1 frozen

Immediate-next-work item 5 is complete.

Frozen contact/gaze rules:

- left/right foot contact are first-class frame-aligned supervision;
- unavailable contact is masked, not encoded as false;
- optional support-surface identity and world contact points are supported;
- contact confidence and derivation provenance are explicit;
- gaze-active state, semantic target identity, head direction, and optional eye-gaze direction are separate;
- gaze components have independent availability masks and confidence/provenance;
- head direction is not treated as identical to body/root facing;
- exact frame-level contact/gaze truth remains separate from coarse choreography intent;
- contact/gaze targets align exactly with the canonical body sequence.

Authoritative files:

- `docs/model/CONTACT_GAZE_TARGET_REPRESENTATION_V0_1.md`
- `docs/model/contracts/contact-gaze-target-representation-v0.1.json`

**Exact next development step:** define and freeze **Canonical Camera Target Representation v0.1**
(immediate-next-work item 6).

### 2026-09-28 — Canonical Camera Target Representation v0.1 frozen

Immediate-next-work item 6 is complete.

Frozen camera-target rules:

- camera output is engine-neutral and frame-aligned to the canonical 30-fps model timebase;
- shot windows use half-open frame semantics;
- per-frame camera position, 6D orientation, and physical focal length are canonical targets;
- perspective projection is the v0.1 camera target;
- sensor dimensions are explicit when known rather than silently fabricated;
- subject/target identities remain symbolic Scene Conditioning references;
- framing/angle/movement labels are semantic annotations, not substitutes for physical camera curves;
- normalized screen-space composition, visibility/occlusion, and collision/clearance supervision are optional but explicitly masked;
- camera generation is conditioned on accepted canonical body motion in the first architecture;
- the existing runtime `CameraCurveArtifact` remains the conversion boundary after 6D→quaternion conversion.

Authoritative files:

- `docs/model/CANONICAL_CAMERA_TARGET_REPRESENTATION_V0_1.md`
- `docs/model/contracts/canonical-camera-target-representation-v0.1.json`

**Exact next development step:** define and freeze **Training Dataset Schema v0.1**
(immediate-next-work item 7).

### 2026-09-28 — Training Dataset Schema v0.1 frozen

Immediate-next-work item 7 is complete.

Frozen dataset rules:

- every sample separates identity, conditioning, targets, metadata, and artifacts;
- sample IDs and family IDs are distinct;
- train/validation/test splitting is family-aware to prevent near-duplicate leakage;
- dense artifacts are content-addressed and hash-verified;
- supervision availability is explicit;
- deterministic canonicalization metadata is required;
- provenance is required at sample level;
- rights/use review state is required at sample level;
- research and production-candidate data pools are distinct;
- training runs must record dataset/split fingerprints, contract versions, normalization, augmentation, model configuration, seed, checkpoint hashes, and code commit;
- dataset validation is a hard gate before training.

Authoritative files:

- `docs/model/TRAINING_DATASET_SCHEMA_V0_1.md`
- `docs/model/contracts/training-dataset-schema-v0.1.json`

**Exact next development step:** define and freeze **Evaluation & Acceptance Metrics v0.1**
(immediate-next-work item 8).

### 2026-09-28 — Evaluation & Acceptance Metrics v0.1 frozen

Immediate-next-work item 8 is complete.

Frozen evaluation structure now covers:

- hard choreography satisfaction, event timing, and phase temporal overlap;
- root trajectory/orientation, target facing, stop behavior, joint error, bone consistency, and continuity;
- contact quality, planted-foot sliding, and grounding;
- head/gaze target accuracy and acquisition/maintenance;
- camera visibility, framing, collision/clearance, smoothness, and lens behavior;
- canonical-to-engine retarget fidelity;
- Unity-vs-Unreal parity after canonicalized readback;
- independent acceptance states rather than one importer-success boolean;
- versioned benchmark threshold profiles separate from metric formulas;
- required human visual review linked to deterministic metric results.

Authoritative files:

- `docs/model/EVALUATION_ACCEPTANCE_METRICS_V0_1.md`
- `docs/model/contracts/evaluation-acceptance-metrics-v0.1.json`

The representation and evaluation foundation (items 1–8) is now frozen.

**Exact next development step:** build **Guard Turn Dataset Generator v0.1** and generate the first small deterministic dataset before training any learned baseline.

### 2026-09-28 — Guard Turn Dataset Generator v0.1 foundation verified

Immediate-next-work item 9 has begun with a deterministic contract-validation dataset generator.

Implemented in the new isolated `training` package:

- deterministic canonical geometry helpers;
- procedural target-conditioned turn reference generation;
- Scene Conditioning builder for performer + target + support surface;
- Choreography builder with overlapping gaze/turn/hold phases and hard facing/gaze/support constraints;
- deterministic per-array `.npy` artifacts and canonical JSON;
- family-aware train/val/test assignment;
- deterministic dataset/sample fingerprints;
- sample provenance, rights-review state, and explicit `research` usage pool;
- tests for deterministic generation, family split isolation, final target-facing correctness, support-foot preservation, and prevention of accidentally treating this contract dataset as training-ready;
- dedicated CI job for the `training` package.

Verification:

- GitHub Actions job **Training foundation** passed on branch `agent/cross-engine-parity-v0.1`.
- lint/format validation passed;
- training-package tests passed.

Important limitation:

The generated body motion is intentionally labeled:

`contract_validation_only / procedural_contract_reference`

It validates the representation, artifact, split, hashing, and evaluation plumbing. It is **not**
high-quality data that should train the final CutSceneAI model.

**Exact next development step:** build the first **training-quality, rights-cleared motion ingestion
and canonicalization path** for target-conditioned turns. It must map real/high-quality human motion
into the frozen 30-fps canonical body/contact/gaze contracts while preserving provenance and usage
rights. Do not train a learned baseline on the procedural contract-reference dataset.

### 2026-09-28 — Training-specific SMPL/SMPL-X ingestion foundation verified

The first training-quality motion ingestion path is now implemented in the isolated `training`
package.

Implemented:

- common SMPL/SMPL-X NPZ loading from either `global_orient/body_pose/transl` or AMASS-style
  `poses/trans` fields;
- explicit source FPS validation/override;
- canonical +Z-forward to CutSceneAI -Z-forward basis conversion;
- deterministic endpoint-preserving linear translation resampling and quaternion SLERP rotation
  resampling to the frozen 30-fps model timebase;
- explicit global root orientation in `root_rotation_6d_columns`;
- pelvis-local rotation remains identity while the 21 SMPL body-pose joints map to canonical joints
  1..21;
- canonical root translation with explicit origin policy;
- deterministic per-array artifacts and source-file SHA-256 provenance;
- auditable rights/use record;
- a hard `production_candidate` gate requiring owned/licensed/permissive status plus explicitly
  allowed training and model-distribution use;
- CLI: `cutsceneai-ingest-smpl`.

Verification:

- dedicated GitHub Actions **Training foundation** lint/format gate passed;
- all training tests passed;
- tests specifically prove global turn orientation is preserved separately from pelvis articulation,
  60→30 FPS resampling preserves endpoints, +Z source basis conversion is correct, common NPZ layouts
  load, rights gating works, and ingestion artifacts are deterministic.

Important scope:

This canonicalizer makes rights-cleared human motion usable by the frozen CutSceneAI training
representation. It does not by itself create scene-conditioned turn examples.

**Exact next development step:** implement **Canonical Turn Clip Mining v0.1**. Mine target-turn
windows from canonicalized human motion, reject clips with inadequate heading change or excessive
translation, then attach synthetic engine-neutral target geometry along the observed final facing.
Preserve the source record/family identity so train/val/test splits cannot leak sibling clips.
