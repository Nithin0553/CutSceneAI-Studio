# CutSceneAI Cinematic Training Representation v0.1

**Status:** Draft architecture specification  
**Date:** 2026-09-27  
**Repository:** `Nithin0553/CutSceneAI-Studio`  
**Working branch:** `agent/cross-engine-parity-v0.1`

## Purpose

This document defines the first training-data contract for a trainable, engine-neutral **CutSceneAI Cinematic Performance Model**.

The representation must support learning a canonical performance before Unity or Unreal realization. It is deliberately separate from engine-native assets.

The current runtime contracts are useful and should be preserved where possible:

- CIR already provides narrative intent, characters, environment objects, beats, motion phases, dialogue, and shot intent.
- `cutsceneai-humanoid-v1` already defines the canonical 22-joint hierarchy.
- `BodyMotionArtifact` already stores canonical root translation, joint rotations, and optional joint positions.
- `CameraCurveArtifact` already stores camera position, rotation, and focal length.
- Generated Performance Packages already provide versioned canonical artifacts and provenance.

Training representation v0.1 extends these concepts with the missing **scene conditioning, choreography, contacts, gaze, constraints, and evaluation labels**.

## Design principles

1. Engine neutral. No Unity Transform, Unreal Actor, Timeline, Sequencer, Animator, or engine-specific bone identifier may be part of the learned canonical target.
2. Scene conditioned. A semantic target such as `door` must resolve to geometry and spatial relationships.
3. Temporally explicit. Multi-phase performance must be represented as overlapping intervals and constraints, not only independent text prompts.
4. Constraint aware. Training examples must expose contacts, target facing, gaze, root goals, and motion continuity.
5. Separately measurable. Every important requirement should have a label that can also become an evaluation metric.
6. Backward compatible where practical. Existing CIR, BodyMotionArtifact, CameraCurveArtifact, and package contracts should remain reusable rather than replaced without need.
7. Versioned and deterministic. One record must be reproducibly parseable and convertible to model tensors.

---

# 1. One training example

A training example represents one canonical cinematic performance window.

Conceptually:

```text
TrainingExample
├── identity
├── narrative / CIR context
├── scene graph
├── actor state
├── choreography
├── hard / soft constraints
├── canonical body target
├── contact target
├── gaze target
├── camera target
├── dialogue / facial target
└── evaluation annotations
```

The first baseline may train only on a subset:

```text
INPUT
  narrative
  actor start state
  target-object state
  choreography phase
  root / facing goal

OUTPUT
  canonical body motion
  foot contacts
```

The full schema is defined now so later stages do not require an incompatible redesign.

---

# 2. Coordinate system

Use the existing CutSceneAI canonical coordinate space:

```text
distance unit: meter
handedness: right
up axis: +Y
forward axis: -Z
rotation: quaternion XYZW
```

Every scene, body, gaze, camera, and geometric constraint must be expressed in this same space before entering the model.

Engine adapters are responsible for conversion.

---

# 3. Identity and provenance

Each training record should include:

```json
{
  "schema_version": "0.1.0",
  "example_id": "guard-hallway-000001",
  "source_kind": "synthetic",
  "source_dataset": "cutsceneai-guard-family-v0.1",
  "split": "train",
  "fps": 24,
  "frame_count": 168,
  "seed": 10421
}
```

Recommended `source_kind` values:

- `synthetic`
- `mocap`
- `public_dataset`
- `manual_capture`
- `curated_cinematic`

The data pipeline must preserve license and provenance metadata outside model tensors.

---

# 4. Narrative conditioning

The representation should preserve both free text and structured intent.

Example:

```json
{
  "narrative": {
    "prompt": "A guard walks through an abandoned hallway, hears a noise, stops, turns toward a door, and quietly asks who is there.",
    "scene_intent": "cautious hallway investigation",
    "emotion": "alert",
    "style": "natural cautious"
  }
}
```

The model should not be forced to infer every constraint from text if the CIR / Temporal Director has already resolved it structurally.

---

# 5. Scene graph

The scene graph provides model-visible spatial context.

Each entity should contain:

```json
{
  "entity_id": "door-01",
  "semantic_type": "door",
  "role": "target",
  "transform": {
    "position": {"x": 3.4, "y": 0.0, "z": -1.2},
    "rotation": {"x": 0.0, "y": 0.7071, "z": 0.0, "w": 0.7071},
    "scale": {"x": 1.0, "y": 1.0, "z": 1.0}
  },
  "bounds": {
    "center": {"x": 3.4, "y": 1.0, "z": -1.2},
    "extents": {"x": 0.5, "y": 1.0, "z": 0.1}
  },
  "affordances": ["look_target"],
  "dynamic": false
}
```

Minimum v0.1 scene entity features:

- stable entity ID
- semantic type
- role relative to the performance
- world transform
- bounding box or capsule where available
- dynamic / static flag
- basic affordances

Future versions may add meshes, signed-distance fields, occupancy grids, navigation graphs, semantic point clouds, or learned scene tokens.

Do not require dense geometry for the first body baseline.

---

# 6. Actor state

Each performing actor should expose canonical start state.

```json
{
  "actor_id": "guard",
  "skeleton_profile": "cutsceneai-humanoid-v1",
  "start_root_position": {"x": 0.0, "y": 0.0, "z": 2.0},
  "start_root_rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
  "start_linear_velocity": {"x": 0.0, "y": 0.0, "z": -1.1},
  "start_angular_velocity": {"x": 0.0, "y": 0.0, "z": 0.0},
  "reference_height_m": 1.75
}
```

For continuation tasks, include one or more preceding canonical poses / frames.

The first model baseline should support conditioning on at least:

- previous root transform
- previous root velocity
- previous joint pose

This is necessary for smooth multi-phase generation.

---

# 7. Temporal choreography

This is a central addition.

A performance is represented as a set of possibly overlapping phases.

Example:

```json
{
  "phases": [
    {
      "phase_id": "walk",
      "type": "locomotion",
      "start_frame": 0,
      "end_frame": 78,
      "priority": 1,
      "target_entity_id": null
    },
    {
      "phase_id": "decelerate",
      "type": "locomotion_transition",
      "start_frame": 68,
      "end_frame": 92,
      "priority": 2
    },
    {
      "phase_id": "noise-reaction",
      "type": "reaction",
      "start_frame": 76,
      "end_frame": 92,
      "priority": 3
    },
    {
      "phase_id": "head-look-door",
      "type": "gaze_transition",
      "start_frame": 84,
      "end_frame": 105,
      "priority": 4,
      "target_entity_id": "door-01"
    },
    {
      "phase_id": "body-turn-door",
      "type": "orientation_change",
      "start_frame": 90,
      "end_frame": 120,
      "priority": 4,
      "target_entity_id": "door-01"
    },
    {
      "phase_id": "hold-door",
      "type": "hold",
      "start_frame": 120,
      "end_frame": 168,
      "priority": 2,
      "target_entity_id": "door-01"
    }
  ]
}
```

Phases may overlap.

The Temporal Director will eventually predict or refine these labels from CIR.

For initial training, phases may be supplied as ground truth or generated deterministically.

---

# 8. Spatial and motion constraints

Constraints should be explicit objects.

Recommended v0.1 types:

- root_position
- root_path
- root_velocity
- body_facing
- gaze_target
- foot_contact
- ground_height
- target_distance
- hold_pose
- collision_avoidance

Example:

```json
{
  "constraints": [
    {
      "type": "body_facing",
      "start_frame": 110,
      "end_frame": 168,
      "target_entity_id": "door-01",
      "tolerance_degrees": 5.0,
      "weight": 1.0
    },
    {
      "type": "gaze_target",
      "start_frame": 100,
      "end_frame": 168,
      "target_entity_id": "door-01",
      "tolerance_degrees": 3.0,
      "weight": 1.0
    }
  ]
}
```

Training records should distinguish:

- hard constraints: should be satisfied by refinement / projection;
- soft constraints: contribute to learning / scoring.

---

# 9. Canonical body target

Continue using `cutsceneai-humanoid-v1` initially.

The current hierarchy is 22 joints:

```text
pelvis
left_hip
right_hip
spine1
left_knee
right_knee
spine2
left_ankle
right_ankle
spine3
left_foot
right_foot
neck
left_collar
right_collar
head
left_shoulder
right_shoulder
left_elbow
right_elbow
left_wrist
right_wrist
```

Each body frame should minimally contain:

```json
{
  "frame": 0,
  "root_position": {"x": 0.0, "y": 0.0, "z": 2.0},
  "root_rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
  "joint_rotations": ["22 canonical quaternions"],
  "joint_positions": ["22 canonical positions"]
}
```

Important change relative to the current runtime artifact:

Training should treat **root orientation** as an explicit target.

The current `BodyMotionArtifact` stores root translation plus joint rotations. For model training and target-facing constraints, root orientation should not remain implicit.

Do not modify the runtime artifact immediately. First prove the training representation, then decide whether runtime schema v0.2 should add explicit root orientation.

Recommended derived training features:

- root linear velocity
- root angular velocity
- local joint velocity
- facing vector
- phase embedding
- contact state

These may be computed rather than permanently stored.

---

# 10. Contact target

Foot contacts should be first-class labels.

Per frame:

```json
{
  "left_foot_contact": true,
  "right_foot_contact": false,
  "left_toe_contact": true,
  "right_toe_contact": false
}
```

Initial baseline may simplify to left / right foot contact.

Contact labels should be derived from:

- end-effector velocity
- floor distance
- persistence window

and corrected for synthetic data where exact contacts are known.

These labels enable:

- contact-aware losses
- foot-lock refinement
- foot-sliding metrics

---

# 11. Gaze target

Gaze should not be represented only as text.

Per frame or interval:

```json
{
  "target_entity_id": "door-01",
  "head_direction": {"x": 0.82, "y": 0.10, "z": -0.56},
  "gaze_direction": {"x": 0.84, "y": 0.08, "z": -0.54},
  "active": true
}
```

The first body baseline may predict head orientation while gaze direction is derived.

Later versions may separate:

- eyes
- head
- neck
- torso

for natural staggered target acquisition.

---

# 12. Camera target

Camera training remains engine neutral.

Each frame:

```json
{
  "position": {"x": 1.2, "y": 1.7, "z": 4.3},
  "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
  "focal_length_mm": 50.0
}
```

Each shot should additionally expose:

- shot purpose
- subject IDs
- target IDs
- desired framing
- desired angle
- continuity relation to previous shot

Future camera training may add screen-space annotations:

- subject bounding rectangle
- face visibility
- target visibility
- occlusion percentage
- composition score

The camera model should consume canonical body motion rather than be generated independently from body movement.

---

# 13. Dialogue and facial target

For dialogue examples:

```text
text
audio timing
phoneme timing
viseme timing
emotion envelope
canonical facial curves
```

The current ARKit-52 representation can remain a practical canonical face target for v0.1.

For the first body-only model, this field may be absent.

---

# 14. Evaluation annotations

Training examples should include or permit derivation of the following metrics:

### Body / semantic

- root path error
- root endpoint error
- body-facing error to target
- gaze angular error
- foot contact precision / recall
- planted-foot sliding distance
- ground penetration depth
- root velocity discontinuity
- joint angular velocity discontinuity
- transition jerk
- action / phase timing error

### Camera

- subject visibility
- target visibility
- framing error
- camera collision
- occlusion ratio
- shot continuity measures
- trajectory jerk

### Dialogue / face

- phoneme / viseme timing error
- dialogue start / end error
- facial curve continuity

### Cross-engine

Cross-engine metrics belong to realization evaluation, not training labels:

- canonical-vs-Unity pose error
- canonical-vs-Unreal pose error
- Unity-vs-Unreal root path error
- timing parity
- camera parity

---

# 15. Proposed tensorization for first body baseline

Do not begin with the complete schema.

First baseline input per example:

```text
text embedding
actor start root transform
actor previous pose
target relative position
target relative direction
desired root displacement
desired final facing vector
duration
phase / action type
```

First baseline output per frame:

```text
root delta position
root orientation
22 joint rotations
left foot contact probability
right foot contact probability
```

Optional auxiliary output:

```text
22 joint positions
```

Possible representation for rotations should be tested experimentally. Quaternions remain the canonical serialized representation, but model tensors may use a continuous 6D rotation representation and convert back to quaternions at the boundary.

This is a model-level implementation choice, not a canonical format change.

---

# 16. First training task: target-conditioned turn

Before training the full guard performance, train the simplest scene-conditioned behavior that proves the architecture works.

Task:

```text
Given:
- current canonical pose
- current heading
- target relative position
- desired duration

Generate:
- natural body turn
- final body facing toward target
- stable feet
- plausible head / torso sequencing
```

Dataset should vary:

- target angle
- target distance
- starting pose
- support foot
- duration
- character proportions after canonicalization

Acceptance metrics:

- final facing error
- foot sliding
- transition smoothness
- ground penetration
- pose plausibility

Once this works, compose it with locomotion and reaction.

---

# 17. Second training task: locomotion-to-target-stop

Input:

```text
start pose
start velocity
desired root path / endpoint
stop frame
duration
```

Output:

```text
walk
decelerate
plant
stop
```

Acceptance:

- endpoint error
- stop-time error
- root velocity at stop
- foot sliding
- floor penetration

---

# 18. Third training task: guard benchmark composition

Only after the primitive tasks work:

```text
walk
+ react
+ decelerate
+ plant
+ head turn
+ torso turn
+ body turn
+ hold gaze
+ dialogue timing
```

The model / Temporal Director should be tested over randomized guard-scene families rather than one fixed hallway.

---

# 19. Dataset split rules

Avoid leakage.

Do not randomly split near-identical synthetic parameter samples across train and test.

Hold out combinations such as:

- unseen target-angle ranges
- unseen hallway dimensions
- unseen actor starting headings
- unseen target placements
- unseen timing combinations
- later, unseen character body proportions

This tests generalization rather than memorization.

---

# 20. Storage recommendation

Start with a simple versioned record format:

```text
dataset/
  manifest.json
  train/
    <example-id>/
      example.json
      body.npz
      camera.npz          # optional
      face.npz            # optional
      audio.wav           # optional
  val/
  test/
```

`example.json` stores metadata, scene graph, choreography, constraints, and provenance.

Dense frame arrays should use a compact numeric format such as NPZ initially.

Do not store engine-native assets in the model dataset.

---

# 21. Relationship to existing runtime contracts

Training representation v0.1 does not replace:

- CIR
- BodyMotionArtifact
- CameraCurveArtifact
- GeneratedPerformancePackage

Instead:

```text
Training representation
        ↓
model training
        ↓
model inference
        ↓
canonical outputs
        ↓
runtime conversion
        ↓
Generated Performance Package
```

Runtime schema changes should happen only when a training requirement proves they are necessary.

The strongest known candidate change is explicit canonical root orientation.

---

# 22. Decisions intentionally deferred

Do not freeze these until the research assignment returns:

- diffusion vs flow matching vs transformer vs hybrid
- text encoder choice
- dense scene geometry encoding
- exact rotation tensor representation
- exact canonical skeleton expansion beyond 22 joints
- camera network architecture
- whether Temporal Director is learned jointly or separately
- whether body and camera are jointly trained
- exact public pretraining datasets
- exact loss weighting

These should be informed by research evidence and the first dataset experiments.

---

# 23. Immediate implementation order

1. Define Pydantic / JSON schema for this training example.
2. Add canonical root orientation to the **training** target schema.
3. Build scene-graph extraction from the existing Studio scene snapshot.
4. Build target-relative geometry features.
5. Build contact-label computation.
6. Build target-facing / gaze-label computation.
7. Build a synthetic target-conditioned-turn dataset generator.
8. Build train / validation / test split generation.
9. Train the smallest useful baseline.
10. Evaluate numerically before engine realization.

---

# 24. First milestone

The first model milestone is not the entire cutscene.

It is:

> Given a canonical humanoid pose and a target object's relative position, generate a natural target-conditioned turn that ends facing the target with stable planted feet.

When that passes, add locomotion-to-stop.

When both pass independently, compose them into the randomized guard benchmark.

This progression gives CutSceneAI a measurable path from a simple learned scene-conditioned skill to a complete cinematic performance.
