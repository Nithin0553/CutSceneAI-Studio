# CutSceneAI Canonical Camera Target Representation v0.1

**Status:** Frozen for the first trainable camera baseline  
**Contract version:** `0.1.0`  
**Depends on:**
- `docs/model/CANONICAL_TRAINING_REPRESENTATION_V0_1.md`
- `docs/model/SCENE_CONDITIONING_REPRESENTATION_V0_1.md`
- `docs/model/CHOREOGRAPHY_TEMPORAL_REPRESENTATION_V0_1.md`
- `docs/model/CANONICAL_BODY_TARGET_REPRESENTATION_V0_1.md`

**Model:** CutSceneAI Cinematic Performance Model  
**Scope:** Engine-neutral camera supervision generated against accepted canonical scene/body state

## Purpose

This representation defines the canonical camera result that a future CutSceneAI camera model or
planner must produce.

The camera system is trained/planned **after** canonical body motion is available.

It must reason from:

- scene conditioning;
- accepted canonical actor motion;
- narrative / shot intent;
- subject / target identity;
- continuity context;

and produce:

- shot/cut timing;
- camera world trajectory;
- camera orientation;
- lens;
- composition/visibility quality.

Unity and Unreal later realize the same canonical camera result.

---

## 1. Camera sequence structure

A camera target sequence contains:

```text
CameraTargetSequence
├── fps = 30
├── frame_count
├── shots[]
├── per-frame camera samples[]
├── visibility/composition supervision
├── collision/clearance supervision
└── provenance
```

The sequence shares the same canonical 30-fps model timebase as body motion.

---

## 2. Shot windows

Each shot has a half-open frame window:

```text
[start_frame, end_frame)
```

Required fields:

- stable `shot_id`;
- `start_frame`;
- `end_frame`;
- symbolic shot purpose;
- subject entity IDs;
- optional target entity IDs.

Recommended symbolic purposes:

```text
establishing
environment_detail
dialogue
reaction
action
transition
insert
custom
```

The vocabulary remains open.

---

## 3. Shot-plan versus camera target

The system distinguishes:

### Shot intent / conditioning

Examples:

- reaction shot;
- medium close-up;
- keep guard and door readable;
- slow push-in.

### Canonical camera target

Exact accepted result:

- actual cut window;
- per-frame camera position;
- per-frame camera orientation;
- focal length;
- visibility/composition annotations.

For a future high-level Camera Director, shot windows may themselves be prediction targets.

For a lower-level camera trajectory model, shot intent/windows may be conditioning.

The canonical camera output remains the same.

---

## 4. Camera frame sample

Each valid frame contains:

```text
frame_index
position_m
rotation_6d_columns
focal_length_mm
```

Example:

```json
{
  "frame_index": 120,
  "position_m": [1.3, 1.7, 3.9],
  "rotation_6d_columns": [1.0, 0.0, 0.0, 0.0, 0.98, -0.20],
  "focal_length_mm": 50.0
}
```

Position and orientation are canonical world values.

No engine camera transform is stored.

---

## 5. Projection and sensor

v0.1 supports perspective projection only.

Each camera sequence or shot declares:

```text
projection = perspective
sensor_width_mm
sensor_height_mm
```

Existing runtime defaults such as 36 mm × 20.25 mm may be used when they are explicit source
configuration.

Unknown sensor dimensions must not be silently fabricated as dataset truth.

If a dataset supplies field-of-view instead of focal length, ingestion must convert using known
sensor geometry or preserve that source in preprocessing until a valid physical conversion is
possible.

---

## 6. Focal length

`focal_length_mm` is a physical target.

It is stored in millimeters.

The model may internally predict:

- focal length;
- log focal length;
- field of view;
- lens class.

Those are model choices.

Decoded canonical camera output uses physical focal length.

---

## 7. Subject and target identity

Each shot keeps symbolic entity references:

```text
subject_entity_ids
target_entity_ids
```

Examples:

- subject = guard;
- target = door;
- subject = guard + second character;
- target empty for a pure environmental establishing shot.

IDs refer to Scene Conditioning entities.

They remain symbolic on disk.

---

## 8. Framing label

Optional symbolic intended framing may include:

```text
extreme_wide
wide
medium_wide
medium
medium_close_up
close_up
extreme_close_up
over_the_shoulder
point_of_view
insert
custom
```

This is semantic conditioning / annotation.

The actual accepted framing quality is measured from projected subject geometry.

---

## 9. Camera angle label

Optional symbolic angle:

```text
eye_level
low
high
dutch
overhead
custom
```

This label is not a substitute for the actual camera rotation.

---

## 10. Movement label

Optional symbolic movement:

```text
static
pan
tilt
dolly
truck
crane
handheld
orbit
custom
```

The actual movement is the frame-level trajectory.

---

## 11. Composition annotations

For each important subject/target and frame, optional composition supervision may contain:

```text
screen_center_xy
screen_bounds_xywh
visible_fraction
in_frame
occlusion_fraction
```

Screen coordinates use normalized image coordinates:

```text
x ∈ [0,1]
y ∈ [0,1]
```

The exact convention is:

```text
origin = top-left
+x = right
+y = down
```

This convention is frozen for v0.1 composition annotations.

---

## 12. Visibility

For a subject/target entity:

```text
visible_fraction ∈ [0,1]
```

When exact visibility is unavailable, it remains masked.

Synthetic datasets may provide exact rasterized or geometry-derived visibility.

Live engine training data may provide measured/derived values later.

Unknown is not treated as visible.

---

## 13. Occlusion

`occlusion_fraction ∈ [0,1]` is optional.

Meaning:

```text
0 = unoccluded
1 = fully occluded
```

The derivation method and provenance are recorded.

This can be used for:

- loss weighting;
- hard camera acceptance gates;
- preference/ranking later.

---

## 14. Collision and clearance

Per frame, optional camera safety supervision may include:

```text
collision
clearance_m
```

`collision` is binary when known.

`clearance_m` is the shortest known camera-to-obstacle clearance in meters.

If dense scene geometry is unavailable, these labels may be absent.

A camera model must not be rewarded for visually good framing that passes through walls.

---

## 15. Look-at / orientation semantics

Camera rotation is the authoritative frame target.

Optional semantic look-at annotations may identify a principal visual target.

However, the camera target must not be reduced to:

```text
camera position + look-at point
```

because cinematic orientation may intentionally offset the subject for composition.

The learned camera model predicts/optimizes full orientation.

---

## 16. Continuity across frames

Within one shot, evaluate:

- position velocity;
- angular velocity;
- acceleration;
- angular acceleration;
- jerk;
- focal-length change rate.

Hard cuts separate shot windows and do not require transform continuity across the cut.

Within-shot discontinuities are quality failures unless explicitly annotated as intentional.

---

## 17. Continuity across cuts

Cross-shot continuity is semantic, not transform continuity.

Useful annotations/metrics may include:

- subject screen-side consistency;
- action direction consistency;
- shot-size progression;
- eyeline consistency;
- 180-degree-rule relation;
- cut timing relative to events/dialogue.

v0.1 allows these as evaluation annotations but does not hard-code a universal film grammar.

---

## 18. Camera is conditioned on accepted body motion

The camera subsystem receives accepted or ground-truth canonical body motion.

This means it may derive:

- actor position per frame;
- head position;
- facing direction;
- motion direction;
- action timing;
- dialogue timing.

The camera model should not independently guess where the actor will be.

This ordering is frozen:

```text
canonical body performance
    ↓
camera generation/planning
```

for the first trainable architecture.

Joint end-to-end body+camera training may be researched later, but it must still decode to the same
canonical contracts.

---

## 19. Guard benchmark camera requirements

For the guard scene, training/evaluation should be able to verify:

- guard is visible when intended;
- reaction is readable;
- turn toward door is readable;
- door is visible when required by shot intent;
- camera does not intersect hallway walls;
- camera motion is smooth within shots;
- cut timing respects reaction/dialogue;
- focal length is physically plausible.

The exact artistic shot sequence is not hard-coded.

Multiple valid camera solutions may exist.

---

## 20. Multi-solution nature

Unlike root-facing constraints, camera composition often has many acceptable solutions.

Therefore evaluation should combine:

- hard physical validity checks;
- semantic visibility/framing checks;
- smoothness/continuity;
- learned or human preference evaluation later.

A camera target dataset provides one valid example, not necessarily the only valid answer.

This is important when selecting losses and evaluation metrics.

---

## 21. Provenance and confidence

Camera labels must retain provenance:

Recommended source kinds:

```text
human_authored
cinematic_dataset
synthetic_ground_truth
optimization_generated
procedural_baseline
human_reviewed
unknown
```

Optional quality/confidence values lie in `[0,1]`.

Generated procedural baseline cameras must not automatically be treated as high-quality ground truth.

---

## 22. Existing runtime compatibility

The existing `CameraCurveArtifact v0.1` already contains:

- canonical camera position;
- canonical rotation;
- focal length;
- sensor width/height;
- frame count;
- resampling metadata.

That runtime boundary is structurally compatible with the core camera target.

Training-side rotations remain `rotation_6d_columns`.

Runtime conversion uses normalized quaternion XYZW.

Additional training annotations such as visibility and collision do not need to be embedded in the
runtime camera artifact unless later required for diagnostics.

---

## 23. Runtime conversion

```text
model / planner output
    ↓
denormalize
    ↓
validate / orthonormalize 6D rotations
    ↓
Canonical Camera Target
    ↓
convert rotations to quaternion_xyzw
    ↓
CameraCurveArtifact
    ↓
Generated Performance Package
    ↓
Unity / Unreal realization
```

This conversion is deterministic.

---

## 24. Validation invariants

A valid camera target must satisfy:

1. fps = 30 at the canonical model/dataset layer;
2. frame count matches the associated sequence;
3. shot windows are valid half-open intervals;
4. shot IDs are unique;
5. every frame belongs to exactly one active camera shot for a single-camera cinematic sequence;
6. camera positions are finite;
7. rotations are valid 6D ground-truth rotations;
8. focal lengths are positive and within configured physical range;
9. sensor dimensions, when present, are positive;
10. subject/target IDs exist in Scene Conditioning;
11. normalized screen annotations remain in valid ranges;
12. confidence/visibility/occlusion values remain in `[0,1]`;
13. engine-native camera identifiers are forbidden.

---

## 25. First camera baseline

The first trainable camera task should be smaller than full automatic editing.

Suggested task:

```text
INPUT
    one shot intent
    scene conditioning
    accepted canonical guard motion
    subject/target identities
    fixed shot duration

OUTPUT
    camera trajectory
    camera orientation
    focal length
```

Initial evaluation:

- subject visibility;
- target visibility when required;
- collision;
- framing;
- trajectory smoothness;
- lens plausibility.

Automatic shot-count and cut-selection can be added after single-shot trajectory quality is reliable.

---

## 26. What is frozen now

Frozen in v0.1:

- camera target is engine-neutral;
- camera uses the 30-fps canonical model timebase;
- shot windows are half-open;
- per-frame canonical-world position;
- per-frame canonical-world 6D orientation;
- physical focal length;
- perspective projection for v0.1;
- explicit sensor dimensions when known;
- symbolic subject/target identities;
- optional framing/angle/movement labels;
- normalized screen-space composition annotations;
- optional visibility/occlusion supervision;
- optional collision/clearance supervision;
- within-shot smoothness semantics;
- camera generation is conditioned on accepted canonical body motion in the first architecture;
- runtime conversion targets the existing canonical camera artifact boundary.

---

## 27. Intentionally not frozen

Do not freeze yet:

- camera neural architecture;
- optimization versus learned trajectory generation;
- exact preference model;
- exact shot-count prediction strategy;
- exact editing grammar;
- exact composition-loss weights;
- multi-camera simultaneous output;
- final artistic quality thresholds.

---

## 28. Machine-readable companion

Frozen invariants are mirrored in:

`docs/model/contracts/canonical-camera-target-representation-v0.1.json`

---

## 29. Exact next development step

Define and freeze:

**Training Dataset Schema v0.1**

It must compose the already-frozen contracts into one legal train/validation/test example with:

- sample/family identity;
- narrative/CIR conditioning;
- Scene Conditioning;
- Choreography;
- Canonical Body Target;
- Contact/Gaze Target;
- optional Camera Target;
- provenance/license metadata;
- artifact references/hashes;
- supervision masks;
- split/leakage rules.
