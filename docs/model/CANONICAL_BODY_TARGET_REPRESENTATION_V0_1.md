# CutSceneAI Canonical Body Target Representation v0.1

**Status:** Frozen for the first trainable body baseline  
**Contract version:** `0.1.0`  
**Depends on:**
- `docs/model/CANONICAL_TRAINING_REPRESENTATION_V0_1.md`
- `docs/model/SCENE_CONDITIONING_REPRESENTATION_V0_1.md`
- `docs/model/CHOREOGRAPHY_TEMPORAL_REPRESENTATION_V0_1.md`

**Model:** CutSceneAI Cinematic Performance Model  
**Scope:** Frame-level engine-neutral body supervision produced by the body generator

## Purpose

This representation defines exactly what the CutSceneAI body model is expected to predict.

It is deliberately separate from:

- scene conditioning;
- choreography intent;
- foot-contact targets;
- gaze targets;
- Unity humanoid animation;
- Unreal skeletal animation.

The body target is the canonical physical performance that later systems evaluate, refine, and
realize in engines.

---

## 1. Canonical body sequence

One body target sequence has:

```text
BodyTargetSequence
├── actor_entity_id
├── skeleton_profile
├── fps = 30
├── frame_count
├── frames[]
├── supervision masks
└── metadata / provenance
```

The sequence is variable length on disk.

Every body frame shares the same canonical skeleton and coordinate conventions.

---

## 2. Canonical skeleton

v0.1 uses the existing:

```text
cutsceneai-humanoid-v1
```

with the fixed 22-joint ordering already defined by `CANONICAL_HUMANOID_JOINTS`:

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

Target-engine bone names are not part of this representation.

---

## 3. Frame target

Each supervised frame contains:

```text
frame_index
root_position_m
root_rotation_6d
joint_rotations_6d[22]
optional joint_positions_root_relative_m[22]
```

Conceptual example:

```json
{
  "frame_index": 0,
  "root_position_m": [0.0, 0.0, 2.0],
  "root_rotation_6d_columns": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
  "joint_rotations_6d_columns": [
    "... 22 parent-local 6D rotations ..."
  ],
  "joint_positions_root_relative_m": [
    "... optional 22 root-relative positions ..."
  ]
}
```

---

## 4. Root position

`root_position_m` is the actor root position in canonical world space.

Frozen semantics:

- units: meters;
- space: canonical world;
- one value per frame;
- absolute physical position in the canonical scene, not an accumulated engine delta;
- valid vertical position is included.

The first model may internally predict root velocity or root deltas.

Those are model parameterization choices.

The canonical target remains absolute world-space root position.

---

## 5. Root orientation

`root_rotation_6d_columns` is explicit and mandatory.

It represents the actor's global root orientation in canonical world space using the frozen 6D
rotation convention:

```text
[r00, r10, r20, r01, r11, r21]
```

This field is critical for:

- target-facing supervision;
- locomotion heading;
- turn generation;
- root angular velocity;
- cross-engine parity.

Root orientation must not be inferred from the direction of root translation.

A stationary actor can rotate in place.

---

## 6. Joint rotations

`joint_rotations_6d_columns` contains exactly 22 rotations.

Frozen semantics:

- order: `cutsceneai-humanoid-v1`;
- space: canonical parent-local;
- representation: `rotation_6d_columns`;
- one rotation per canonical joint per frame.

The root/global actor orientation is not duplicated into these local rotations.

The pelvis joint remains an articulated parent-local joint target relative to the explicit actor
root frame.

This separation prevents global heading from being conflated with pelvis articulation.

---

## 7. Optional joint-position auxiliary supervision

`joint_positions_root_relative_m` is optional.

When present:

- exactly 22 vectors;
- units: meters;
- space: canonical root-relative;
- same joint ordering as the canonical skeleton.

This is auxiliary supervision, not an alternate canonical body definition.

Primary motion identity remains:

```text
root world transform
+
parent-local articulated rotations
```

Joint positions can improve:

- geometric plausibility;
- limb-length monitoring;
- contact derivation;
- retarget diagnostics;
- model auxiliary losses.

If unavailable, the field is absent and its supervision mask is false.

---

## 8. Reference pose and bone lengths

A body target sequence assumes one canonical skeleton profile and reference pose.

The dataset canonicalizer is responsible for normalizing source motion into the canonical rig.

Per-example target-engine bone lengths are forbidden.

Optional canonical morphology information, if introduced later, belongs to actor conditioning and
must use a new contract version.

The first body baseline trains on normalized `cutsceneai-humanoid-v1` geometry.

---

## 9. Derived root velocity

Root linear velocity is derived from canonical root position.

For interior frames:

```text
v_t = (p_{t+1} - p_{t-1}) / (2 * dt)
```

with:

```text
dt = 1 / 30 s
```

Endpoints use a deterministic one-sided difference.

Velocity units:

```text
meters / second
```

Root velocity is a derived feature/metric.

It is not mandatory duplicated source truth in the canonical body target.

A dataset may cache derived values for efficiency only if the derivation version is recorded.

---

## 10. Derived root angular velocity

Root angular velocity is derived from successive root orientations.

The implementation should compute relative rotation:

```text
R_delta = R_t^-1 * R_{t+1}
```

then convert to axis-angle / logarithmic rotation divided by `dt`.

Units:

```text
radians / second
```

The exact numerical implementation must be versioned and tested.

The canonical source target remains the absolute root rotation.

---

## 11. Derived joint angular velocity

Joint angular velocities are derived from successive parent-local joint rotations.

They are useful for:

- smoothness losses;
- transition evaluation;
- jerk / discontinuity detection.

They are not mandatory serialized labels.

---

## 12. Facing vector

The canonical actor-local forward axis remains:

```text
[0, 0, -1]
```

The world facing vector at frame `t` is derived by applying the explicit root orientation to that
local vector.

Horizontal body-facing metrics project this vector to the ground plane.

This is the authoritative source for target-facing evaluation.

---

## 13. Continuity semantics

A body target sequence is one continuous performance.

Adjacent frames must not be treated as independent poses.

Training/evaluation should be able to measure:

- root position continuity;
- root speed continuity;
- root angular-speed continuity;
- joint angular continuity;
- transition jerk.

No clip-boundary reset exists inside a canonical sequence unless represented as a real
discontinuity in the source data and explicitly marked invalid for continuous-performance
training.

---

## 14. Frame-valid mask

Stored canonical sequences contain only valid source frames.

Batch padding is not written into the sequence.

During batching, a mandatory `frame_valid_mask` marks real frames versus padding.

Padded frames contribute zero training loss.

---

## 15. Body supervision mask

A body sequence has a body-target availability mask.

For full body supervision:

```text
body_target_available = true
```

If partial datasets are supported later, finer-grained masks may be introduced for individual
joint groups.

v0.1 does not silently fill missing body rotations with identity.

---

## 16. Auxiliary joint-position mask

```text
joint_positions_available
```

is explicit.

If false, auxiliary position loss is disabled.

If true, all 22 joint positions must be present for all valid frames in v0.1.

Mixed per-frame presence is not allowed in one v0.1 sequence.

---

## 17. No foot-contact labels in this contract

Exact foot-contact truth is deliberately not included here.

Reason:

```text
body target = physical pose / root motion
contact target = semantic/support state derived or measured from that motion
```

The next dedicated Contact / Gaze Representation defines exact contact supervision.

This keeps contact confidence/provenance separate from body pose truth.

---

## 18. No gaze labels in this contract

Head and neck rotations are part of body pose.

But the intended / measured gaze target and gaze direction are separate semantic targets.

Those belong to the next Contact / Gaze Representation.

This matters because:

- head direction is not identical to eye gaze;
- some datasets have body mocap without gaze annotation;
- gaze may be derived, measured, procedural, or unavailable.

---

## 19. Model output parameterization is not the disk contract

A trainable network may output:

- absolute root positions;
- root deltas;
- velocities integrated to position;
- residual rotations;
- diffusion noise targets;
- flow vectors;
- latent motion tokens.

Those are model choices.

Before evaluation and runtime conversion, outputs must decode to this exact canonical physical
representation.

Therefore diffusion and flow-matching baselines can be compared fairly on identical decoded
targets.

---

## 20. Training loss families enabled by this representation

The representation supports, without freezing weights:

- root-position reconstruction;
- root-orientation rotation loss;
- joint-rotation geodesic / 6D reconstruction loss;
- optional joint-position loss;
- root-velocity loss;
- root-angular-velocity loss;
- joint-angular-velocity loss;
- acceleration / jerk regularization;
- bone-length consistency;
- choreography constraint losses after decoding.

Loss weights are training configuration, not representation.

---

## 21. Root world trajectory versus choreography path

The distinction is mandatory.

### Choreography root path

Sparse intent:

```text
walk generally through these waypoints
stop near here
```

### Body target root trajectory

Exact frame-level supervision:

```text
p_0, p_1, p_2, ... p_T
```

The sparse choreography path must not simply copy all target root positions.

Otherwise the body model would receive the answer.

---

## 22. Root facing versus choreography facing

Likewise:

### Choreography condition

```text
face the door by / during this window
```

### Body target

```text
exact root orientation at every frame
```

The body model learns how to physically transition between headings rather than receiving the
target rotation sequence as conditioning.

---

## 23. First target-conditioned-turn task

For the first trainable skill:

### Conditioning

- previous canonical pose;
- previous root orientation;
- previous velocity;
- target-relative geometry;
- turn duration;
- final body-facing constraint;
- coarse support-contact intent.

### Body target

For every generated frame:

- root world position;
- root world orientation;
- 22 parent-local joint rotations;
- optional 22 root-relative joint positions.

### Evaluation

- final body-facing error;
- root drift;
- angular continuity;
- joint plausibility;
- foot sliding after contact labels are added;
- ground penetration.

---

## 24. Locomotion-to-stop task

Later task:

### Conditioning

- initial body state;
- root path / endpoint intent;
- stop timing;
- desired speed profile or stop constraint.

### Body target

Same canonical frame target.

No new body representation is required.

This is a key design goal: new behaviors should use the same body-output contract.

---

## 25. Runtime Generated Performance Package boundary

The current runtime `BodyMotionArtifact v0.1` contains:

- root translation;
- 22 joint rotations;
- optional joint positions;

but it does **not** contain an explicit actor root orientation field.

The new trainable body contract requires explicit root orientation.

Therefore:

**The new model path must not silently discard root orientation.**

Before the first trained model is integrated into the runtime performance package, CutSceneAI must
introduce a versioned runtime canonical motion contract that preserves explicit root orientation
(e.g. `BodyMotionArtifact v0.2` or an equivalent backward-compatible field/version).

Do not encode world root heading implicitly into pelvis local rotation as a permanent workaround.

That would conflate global locomotion heading with articulated pelvis motion and damage
retargeting semantics.

Legacy v0.1 performance artifacts may remain readable for compatibility.

---

## 26. Runtime conversion

The eventual decoder boundary should perform:

```text
model output
    ↓
denormalize
    ↓
orthonormalize / validate 6D rotations
    ↓
canonical BodyTargetSequence
    ↓
convert 6D rotations to normalized quaternion_xyzw
    ↓
versioned runtime BodyMotionArtifact with explicit root rotation
    ↓
Generated Performance Package
```

This conversion is deterministic and tested.

Engine conversion occurs later.

---

## 27. Validation invariants

A valid v0.1 body target must satisfy:

1. `fps == 30`;
2. `frame_count > 0`;
3. frame indices are contiguous `0..frame_count-1`;
4. every root position is finite;
5. every root rotation is valid orthonormal 6D ground truth within tolerance;
6. every frame has exactly 22 joint rotations;
7. all joint rotations are valid 6D ground truth within tolerance;
8. joint positions, when present, contain exactly 22 finite vectors on every frame;
9. skeleton profile is exactly `cutsceneai-humanoid-v1`;
10. root transform is canonical world space;
11. joint rotations are canonical parent-local;
12. optional joint positions are canonical root-relative;
13. no engine-native identifiers appear in target fields.

---

## 28. Quality checks separate from schema validity

A sequence can be schema-valid and still be bad motion.

Quality checks should additionally measure:

- impossible bone-length changes;
- extreme joint angular speed;
- implausible root acceleration;
- discontinuities;
- severe floor penetration;
- foot sliding once contact labels exist;
- target-facing failure;
- choreography mismatch.

These belong to dataset QA and evaluation, not basic serialization validation.

---

## 29. Dataset storage

Dense body arrays should be stored in a compact numeric artifact.

Recommended first implementation:

```text
body.npz

root_position_m                [T, 3]
root_rotation_6d_columns       [T, 6]
joint_rotations_6d_columns     [T, 22, 6]
joint_positions_root_relative  [T, 22, 3]   optional
```

The surrounding `example.json` stores:

- actor ID;
- skeleton profile;
- frame count;
- availability masks;
- provenance;
- artifact hash / reference.

NPZ is a first implementation choice, not a claim that production datasets must remain NPZ
forever.

---

## 30. Cross-engine significance

Unity and Unreal should never become training targets for body motion.

Both engines receive the same accepted decoded canonical body sequence.

Cross-engine evaluation later asks:

```text
How closely did Unity reproduce canonical root position/orientation and pose?
How closely did Unreal reproduce them?
How closely do Unity and Unreal agree with each other?
```

Explicit root orientation makes those comparisons substantially cleaner.

---

## 31. What is frozen now

Frozen in v0.1:

- body target is frame-level;
- 30-fps canonical model timebase;
- `cutsceneai-humanoid-v1` 22-joint identity;
- explicit canonical-world root position;
- explicit canonical-world root orientation;
- mandatory 6D rotation representation on training/dataset side;
- 22 canonical parent-local joint rotations;
- optional root-relative 22-joint positions;
- velocities are deterministic derived quantities;
- frame padding is outside stored source truth;
- missing supervision uses masks;
- contact and gaze remain separate target contracts;
- model-specific output parameterization is decoded before evaluation;
- runtime integration must preserve root orientation explicitly.

---

## 32. Intentionally not frozen

Do not freeze yet:

- diffusion versus flow-matching output parameterization;
- exact model latent representation;
- exact loss weighting;
- morphology conditioning;
- finger joints;
- detailed face joints;
- physics residual representation;
- exact runtime v0.2 class name / migration mechanism.

---

## 33. Machine-readable companion

Frozen invariants are mirrored in:

`docs/model/contracts/canonical-body-target-representation-v0.1.json`

---

## 34. Exact next development step

Define and freeze:

**Contact / Gaze Target Representation v0.1**

It must define:

- exact left/right foot contact labels;
- contact confidence/provenance;
- support-surface identity where known;
- planted-foot stability semantics;
- gaze-active masks;
- gaze target identity;
- gaze/head direction supervision;
- confidence/provenance;
- derived versus measured labels.

Only after body, contact, and gaze targets are frozen should camera-target representation be
finalized.
