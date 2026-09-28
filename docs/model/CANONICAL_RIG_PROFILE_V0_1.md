# CutSceneAI CanonicalRigProfile v0.1

**Status:** Frozen for the first trainable body baseline  
**Contract version:** `0.1.0`  
**Profile ID:** `cutsceneai-humanoid-v1`

## Purpose

This profile removes ambiguity about what a CutSceneAI canonical joint rotation means.

A source rig is not canonical merely because its joints have the same names.

To become training data, source motion must be converted into the rotation basis defined here.

---

## 1. Hierarchy

The canonical 22-joint order is:

```text
0  pelvis
1  left_hip
2  right_hip
3  spine1
4  left_knee
5  right_knee
6  spine2
7  left_ankle
8  right_ankle
9  spine3
10 left_foot
11 right_foot
12 neck
13 left_collar
14 right_collar
15 head
16 left_shoulder
17 right_shoulder
18 left_elbow
19 right_elbow
20 left_wrist
21 right_wrist
```

Parent indices:

```text
[-1, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9, 9, 12, 13, 14, 16, 17, 18, 19]
```

This is the same hierarchy already used by `BodyMotionArtifact`.

---

## 2. Canonical rotation basis

The canonical joint frame is an **axis-aligned parent-space delta frame**.

At canonical neutral/reference pose:

```text
root_rotation = identity
joint_rotation[j] = identity for every j
```

A canonical joint rotation therefore means:

> the reference-pose-relative rotation delta of that joint, expressed in the canonical parent
> component axes.

It is not:

- an engine bind rotation;
- an Unreal bone-local bind transform;
- a Unity Humanoid muscle value;
- a source-rig joint-orient matrix;
- a world-space joint rotation.

The root/global actor orientation remains a separate target.

---

## 3. Coordinate basis

The canonical actor/world basis is:

```text
right-handed
+Y up
-Z forward
meters
```

Training rotations use `rotation_6d_columns`.

The canonical neutral parent axes are the canonical world/model axes before articulated deltas are
applied.

---

## 4. Reference-offset directions

The v0.1 profile freezes the existing direction-only neutral skeleton used by CutSceneAI's HumanML
canonicalization.

Parent-relative reference-offset directions:

```text
pelvis          [ 0,  0,  0]
left_hip        [ 1,  0,  0]
right_hip       [-1,  0,  0]
spine1          [ 0,  1,  0]
left_knee       [ 0, -1,  0]
right_knee      [ 0, -1,  0]
spine2          [ 0,  1,  0]
left_ankle      [ 0, -1,  0]
right_ankle     [ 0, -1,  0]
spine3          [ 0,  1,  0]
left_foot       [ 0,  0,  1]
right_foot      [ 0,  0,  1]
neck            [ 0,  1,  0]
left_collar     [ 1,  0,  0]
right_collar    [-1,  0,  0]
head            [ 0,  0,  1]
left_shoulder   [ 0, -1,  0]
right_shoulder  [ 0, -1,  0]
left_elbow      [ 0, -1,  0]
right_elbow     [ 0, -1,  0]
left_wrist      [ 0, -1,  0]
right_wrist     [ 0, -1,  0]
```

These values freeze **direction**, not metric bone length.

---

## 5. Metric bone lengths

CanonicalRigProfile v0.1 does **not** freeze one metric bone-length vector.

Reason:

The first target-conditioned-turn baseline is rotation/root focused and does not require canonical
joint-position auxiliary supervision.

Until a metric morphology profile is separately frozen:

- AMASS/SMPL ingestion must leave `joint_positions_root_relative_m` unavailable;
- no canonical joint positions may be fabricated from unit reference offsets;
- contact labels requiring actual feet geometry remain unavailable unless derived from a
  separately validated geometric source.

A later metric morphology contract may extend the rig profile without changing the v0.1 rotation
basis semantics.

---

## 6. Generic source-rig conversion rule

A source-rig pose delta may be copied into canonical form only after its reference basis is known.

For a source parent reference basis `S_parent` expressed in canonical coordinate axes and a source
local pose delta `R_source_delta`:

```text
R_canonical_delta =
    S_parent
    · R_source_delta
    · inverse(S_parent)
```

If source coordinates themselves differ from canonical coordinates, coordinate-basis conversion is
applied first/consistently.

A source format with non-identity bind/joint-orient axes therefore needs a SourceRigProfile.

Semantic joint-name matching alone is never sufficient.

---

## 7. SMPL / SMPL-X source profile

For the supported first 22 SMPL-family joints:

- semantic hierarchy matches the CutSceneAI 22-joint hierarchy;
- `global_orient` is the explicit actor/root orientation;
- `body_pose` provides 21 local pose rotations;
- source rest rotations are identity in the SMPL kinematic transform;
- rest joint offsets are translations, not extra bind rotations.

Primary implementation evidence:

`vchoutas/smplx/smplx/lbs.py::batch_rigid_transform`

The official implementation builds each joint transform from the pose rotation and relative rest
joint translation and notes that no additional rotation is required at rest because it is
identity.

Therefore, after source-coordinate basis conversion:

```text
canonical root rotation =
    source global_orient

canonical pelvis-local rotation =
    identity

canonical joint rotations 1..21 =
    source body_pose rotations 0..20
```

This is exactly the policy implemented by the training-specific SMPL canonicalizer.

---

## 8. +Z-forward SMPL/AMASS basis conversion

When the source coordinate system is right-handed, +Y-up, +Z-forward, CutSceneAI converts it to
right-handed, +Y-up, -Z-forward with a 180-degree Y-axis basis rotation:

```text
B = diag(-1, 1, -1)

p_canonical = B · p_source

R_canonical = B · R_source · B^-1
```

Because `B` is a proper rotation with determinant +1, handedness is preserved.

The same basis conversion applies to root orientation and articulated local deltas.

---

## 9. Neutral-pose invariant

Every supported source-rig canonicalizer must prove:

```text
source neutral/reference pose
    ↓
canonical root orientation = identity
canonical articulated joint rotations = identity
```

unless the source record explicitly contains a non-neutral root/world orientation.

This is a hard test requirement.

---

## 10. Cross-source consistency invariant

Before two source formats may be mixed in one training pool, CutSceneAI must test equivalent
synthetic/reference poses through both canonicalizers.

The accepted comparison is:

- same canonical root orientation;
- same canonical joint-delta rotations for identifiable degrees of freedom;
- same semantic hierarchy;
- any source ambiguity (for example twist missing from XYZ-only motion) must be explicitly masked or
  documented.

A source with swing-only reconstruction must not be treated as equivalent to full twist
supervision.

---

## 11. HumanML relationship

The existing HumanML canonicalizer reconstructs local swing rotations from observed XYZ joints
against an axis-aligned reference skeleton.

That is compatible with this canonical parent-axis convention for **swing**.

HumanML XYZ does not determine arbitrary bone twist, so its reconstructed rotations remain
incomplete pose supervision for twist.

Future mixed-source training must either:

- mask/weight twist-incomplete supervision appropriately; or
- train on geometric joint targets for those samples instead of pretending twist is known.

---

## 12. Runtime retargeting relationship

The existing runtime retargeter already assumes the same conceptual rule:

canonical rotations are axis-aligned parent-space deltas, then target bind/reference component
rotations are used to express those deltas in the target rig's parent basis.

This profile makes that implicit runtime assumption explicit on the training side.

---

## 13. Acceptance tests

Required for v0.1:

1. neutral SMPL body pose maps every canonical local joint rotation to identity;
2. SMPL global orientation affects only canonical root orientation;
3. source +Z→canonical -Z basis conversion is a proper handedness-preserving rotation;
4. a known source local axis rotation conjugates into the expected canonical axis rotation;
5. canonical joint hierarchy/order matches runtime `cutsceneai-humanoid-v1`;
6. no source bind/joint-orient data may be silently ignored for a future non-SMPL source;
7. metric joint-position supervision remains unavailable when no metric canonical morphology is
   defined.

---

## 14. Frozen decisions

Frozen:

- canonical neutral local rotations are identity;
- canonical joint deltas are axis-aligned parent-space/reference-pose-relative rotations;
- root orientation is separate;
- v0.1 22-joint hierarchy/order;
- direction-only reference offsets;
- SMPL 22-body mapping policy;
- SMPL rest rotation basis = identity;
- coordinate conversion uses proper basis conjugation;
- source rigs with non-identity bind orientation require explicit source-rig basis metadata.

Not frozen:

- canonical metric bone lengths;
- body-shape/morphology conditioning;
- twist-bone expansion;
- finger rig;
- target-engine rig profiles.

## Exact next step

Keep the current training-specific SMPL canonicalizer, add this profile's invariants as executable
tests, then run the AMASS research pilot only on locally licensed files.

Do not mix HumanML swing-only rotations and SMPL full pose rotations indiscriminately in one
unmasked loss.
