# CutSceneAI Contact / Gaze Target Representation v0.1

**Status:** Frozen for the first trainable body baseline  
**Contract version:** `0.1.0`  
**Depends on:**
- `docs/model/CANONICAL_TRAINING_REPRESENTATION_V0_1.md`
- `docs/model/SCENE_CONDITIONING_REPRESENTATION_V0_1.md`
- `docs/model/CHOREOGRAPHY_TEMPORAL_REPRESENTATION_V0_1.md`
- `docs/model/CANONICAL_BODY_TARGET_REPRESENTATION_V0_1.md`

**Model:** CutSceneAI Cinematic Performance Model  
**Scope:** Frame-level contact and gaze supervision associated with canonical body motion

## Purpose

This contract defines two kinds of supervision that are critical for cinematic correctness but are
not identical to body-pose supervision:

1. **support contact** — whether the left/right foot is planted and what support surface is involved;
2. **gaze** — whether attention is active, what entity/point is being attended to, and what direction
   the head/gaze is oriented.

These labels are kept separate from the body target because they may be measured, derived,
procedural, human-reviewed, or unavailable even when full body motion exists.

---

## 1. Shared principles

The frozen canonical training contract applies:

- 30 fps;
- meters;
- right-handed, +Y up, -Z forward;
- symbolic IDs remain symbolic on disk;
- missing supervision uses explicit masks;
- provenance is mandatory;
- physical values remain unnormalized on disk.

Contact and gaze are frame-aligned with the canonical body sequence.

---

# CONTACT

## 2. Contact target sequence

Per body frame, v0.1 can supervise:

```text
left_foot_contact
right_foot_contact

optional left_support_surface_id
optional right_support_surface_id

optional left_contact_point_world_m
optional right_contact_point_world_m

confidence / provenance
```

The first baseline uses foot-level contact only.

Toe/heel subdivisions are intentionally deferred.

---

## 3. Binary contact semantics

`left_foot_contact` and `right_foot_contact` are binary ground-truth labels when supervision is
available.

Meaning:

> the foot is considered mechanically planted/supporting or in stable support contact with the
> environment for the current frame.

A foot merely passing close to the floor is not automatically "contact."

The exact derivation method is versioned in provenance.

---

## 4. Contact availability mask

Each side has an explicit availability mask:

```text
left_contact_available
right_contact_available
```

This allows datasets where one or both foot labels are unavailable.

Unavailable contact is not encoded as false.

---

## 5. Contact confidence

Each supervised side may include:

```text
confidence ∈ [0, 1]
```

Examples:

- exact procedural synthetic label: 1.0;
- force-plate / measured contact: high confidence;
- kinematically derived mocap contact: lower confidence;
- human-reviewed corrected label: according to annotation policy.

Confidence is available for loss weighting and dataset QA.

It is not a substitute for the availability mask.

---

## 6. Contact provenance

Each contact label source uses a symbolic method, recommended initial values:

```text
measured
synthetic_ground_truth
derived_kinematic
derived_physics
human_reviewed
unknown
```

A method version string must be retained whenever labels are derived.

Example:

```text
derived_kinematic / cutsceneai-contact-deriver-v0.1
```

---

## 7. Support surface identity

When known, each contacting foot may reference a Scene Conditioning support surface:

```text
left_support_surface_id
right_support_surface_id
```

For the first flat hallway benchmark this may be:

```text
floor-main
```

If support identity is unknown, the contact label may still be valid.

---

## 8. Contact point

Optional contact point:

```text
contact_point_world_m = [x, y, z]
```

Space: canonical world.

This is useful for:

- foot-lock refinement;
- sliding measurement;
- ground penetration checks;
- stairs/slopes later.

It is not required for the first baseline.

---

## 9. Planted-foot stability

A planted interval is a contiguous run of contact=true frames.

For any planted interval with a known contact point or derivable foot position, evaluation can
measure:

```text
foot_sliding_distance_m
max_foot_drift_m
vertical_clearance_error_m
```

The contact contract does not hard-code one final acceptance threshold.

Thresholds belong to the evaluation contract.

---

## 10. Contact derivation for public mocap

When exact contact is not measured, a kinematic derivation may use:

- foot height above support surface;
- foot linear speed;
- persistence across neighboring frames.

The canonical dataset must record:

- method name/version;
- parameters;
- confidence.

Changing those rules creates a new derivation version.

It must not silently relabel an existing dataset.

---

## 11. Choreography contact versus contact target

Important distinction:

### Choreography

```text
"keep at least one foot planted during the turn"
```

### Contact target

```text
frame 98: left=true, right=false
frame 99: left=true, right=false
...
```

The body generator receives the coarse choreography intent.

Exact frame labels remain supervision.

---

# GAZE

## 12. Gaze target sequence

Per frame, gaze supervision may contain:

```text
gaze_active
target_entity_id
optional target_point_id
head_direction_world
optional gaze_direction_world
confidence / provenance
```

The representation separates head direction from eye gaze.

---

## 13. Gaze-active mask

`gaze_active` indicates that a meaningful attention target is supervised for this frame.

Separate availability flags indicate whether the annotation itself is known.

Examples:

- synthetic guard scene: gaze active toward the door;
- generic mocap with no attention annotations: gaze unavailable;
- body mocap with head orientation but unknown semantic target: head direction available, target ID unavailable.

Unknown target identity is not represented as "no gaze."

---

## 14. Target identity

When known:

```text
target_entity_id
```

references a Scene Conditioning entity.

Optional:

```text
target_point_id
```

may reference an entity target point such as:

```text
visual-center
face
handle
```

The first guard benchmark uses the bound door's look target / visual center.

---

## 15. Head direction

`head_direction_world` is a normalized canonical-world direction vector.

It represents the forward direction of the head, derived from or measured against the canonical
head orientation.

It is useful even when eye tracking is unavailable.

This is separate from the body's root facing direction.

---

## 16. Gaze direction

`gaze_direction_world` is optional.

When available, it represents the actual visual/eye gaze direction in canonical world space.

The first body baseline does not require measured eye gaze.

Synthetic data may provide it exactly.

If unavailable, the model may initially use head direction as the principal attention supervision.

---

## 17. Gaze availability masks

v0.1 uses explicit availability for:

- gaze-active supervision;
- target identity;
- head direction;
- gaze direction.

A dataset may therefore provide head direction without semantic target identity, or semantic target
identity without measured eye direction.

No unavailable field is replaced with a zero vector.

---

## 18. Gaze confidence and provenance

Recommended provenance methods:

```text
measured_eye_tracking
synthetic_ground_truth
derived_from_head_pose
procedural_target
human_reviewed
unknown
```

Confidence ∈ [0, 1].

Derived head-direction labels should record derivation version.

---

## 19. Gaze angle error

When target geometry and direction are both available, evaluation may compute:

```text
target_vector =
    normalize(target_point_world - head_origin_world)

head_error_deg =
    angle(head_direction_world, target_vector)

gaze_error_deg =
    angle(gaze_direction_world, target_vector)
```

The evaluation contract will define which error is required for each benchmark.

---

## 20. Head/torso/body sequencing

The body target already contains neck/head joint rotations.

The gaze contract adds semantic direction/target supervision.

This allows evaluation of cinematic sequencing such as:

```text
eyes/head acquire target
→ torso follows
→ root/body completes turn
```

without conflating all three with one facing vector.

---

## 21. Choreography gaze versus gaze target

Again:

### Choreography

```text
look toward Door_01 during frames 90–168
```

### Gaze target supervision

```text
per-frame active mask
semantic target
head direction
optional eye direction
```

The body generator must learn the temporal acquisition behavior rather than receiving the exact
future head direction sequence as conditioning.

---

# SHARED VALIDATION

## 22. Validation invariants

A valid v0.1 Contact/Gaze target must satisfy:

1. frame count matches the body target sequence;
2. frame indices align exactly;
3. availability masks are explicit;
4. confidence values lie in `[0,1]`;
5. support-surface IDs, when present, exist in Scene Conditioning;
6. gaze target entity IDs, when present, exist in Scene Conditioning;
7. target-point IDs, when present, belong to the referenced entity;
8. direction vectors are finite and normalized within tolerance;
9. contact points, when present, are finite canonical-world meters;
10. missing labels are not represented by fabricated zeros.

---

## 23. First guard benchmark

The first guard benchmark should eventually provide:

### Contact

- left/right foot contact per frame;
- exact synthetic labels where possible;
- support surface = hallway floor;
- optional contact points for foot-lock evaluation.

### Gaze

- gaze-active interval toward the door;
- door target identity;
- door visual-center target point;
- head direction per frame;
- optional synthetic gaze direction.

This allows us to determine whether the guard merely rotates or actually performs a believable
target acquisition and stable turn.

---

## 24. First body-model output strategy

The first model may predict contact jointly with body motion as auxiliary heads:

```text
left_contact_probability
right_contact_probability
```

and may predict a head/gaze direction auxiliary output.

But the canonical dataset labels remain binary/physical supervision as defined here.

Whether auxiliary heads are part of the architecture is not frozen.

---

## 25. Deterministic refinement use

Contact labels may drive deterministic post-generation refinement:

- detect planted intervals;
- lock planted foot world position;
- correct root drift;
- solve IK;
- enforce support plane.

Gaze labels/intent may drive:

- head/neck look-at correction;
- torso follow;
- eye-look correction where a facial rig supports it.

Refinement must preserve the accepted canonical semantics and remain engine-neutral.

---

## 26. What is frozen now

Frozen in v0.1:

- left/right foot contact as first-class frame labels;
- explicit per-side availability;
- optional support-surface identity;
- optional world contact point;
- confidence and provenance;
- gaze-active supervision;
- optional semantic target identity;
- optional target-point identity;
- head-direction world vector;
- optional gaze-direction world vector;
- explicit availability for each gaze component;
- confidence/provenance;
- no silent zero-filling;
- contact/gaze sequence must align with body target frame count.

---

## 27. Intentionally not frozen

Do not freeze yet:

- heel/toe subdivisions;
- hand contacts;
- object grasp state;
- exact contact-loss formulation;
- exact gaze neural head;
- detailed eye-joint representation;
- blink behavior;
- final acceptance thresholds;
- exact target-acquisition timing model.

---

## 28. Machine-readable companion

Frozen invariants are mirrored in:

`docs/model/contracts/contact-gaze-target-representation-v0.1.json`

---

## 29. Exact next development step

Define and freeze:

**Canonical Camera Target Representation v0.1**

It must specify:

- shot/cut timing;
- camera world position and orientation;
- focal length / sensor semantics;
- subject and target identities;
- framing/composition annotations;
- visibility / occlusion supervision;
- collision/clearance supervision;
- continuity and smoothness semantics;
- relationship to accepted canonical body motion.
