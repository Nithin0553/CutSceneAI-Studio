# CutSceneAI Canonical Training Representation v0.1

**Status:** Frozen for the first trainable baseline  
**Contract version:** `0.1.0`  
**Model:** CutSceneAI Cinematic Performance Model  
**Scope:** Shared representation rules for every training example, independent of Unity and Unreal

## Purpose

This document freezes the representation conventions that all later model inputs, labels, targets,
datasets, losses, and evaluation code must obey.

It intentionally does **not** define the complete scene-conditioning schema, choreography label
schema, body-target schema, contact/gaze schema, or camera-target schema. Those are the next
development steps. Instead, it fixes the common coordinate, time, rotation, normalization,
identity, masking, and conversion rules so those schemas cannot drift independently.

The first benchmark remains the guard-scene family described in
`docs/CUTSCENEAI_CINEMATIC_MODEL_HANDOFF.md`.

## Frozen invariants

### 1. One training example is one canonical cinematic sequence

A training example represents one temporally continuous canonical performance sequence. The
on-disk representation is variable length. Fixed-length windows may be sampled for training, but
windowing is a training transform and must not redefine the source sequence.

Each sequence has:

- a stable `sample_id`;
- a `family_id` used to group procedural variations of the same semantic scene family;
- a declared source/provenance record;
- one canonical frame count;
- one shared canonical timebase;
- conditioning data;
- target data;
- explicit availability/supervision masks where labels are incomplete.

### 2. Canonical model timebase is 30 fps

The v0.1 model timebase is exactly **30 frames per second**.

Source datasets may use other rates. Dataset ingestion must resample them into the canonical
30-fps representation before they become trainable examples.

Frame index is the primary temporal key:

```text
time_seconds = frame_index / 30
```

Intervals use half-open frame windows `[start_frame, end_frame)`, matching the existing CutSceneAI
timeline conventions.

Reasons for the fixed model timebase:

- one shared frame grid for body, gaze, contacts, dialogue timing, and camera supervision;
- deterministic alignment across heterogeneous datasets;
- sufficient temporal resolution for stop/turn/reaction timing;
- straightforward conversion to common game-engine timeline rates.

Engine realization is free to resample the accepted canonical result afterward.

### 3. Canonical coordinate space is unchanged

Training uses the same canonical space already established by the generated-performance contract:

```text
distance unit: meters
handedness: right-handed
up axis: +Y
forward axis: -Z
```

No Unity- or Unreal-specific coordinates, centimeters, left-handed transforms, import offsets, or
engine bone bases are permitted in model training examples.

Scene conditioning and target motion must be expressed in the same canonical space before model
ingestion.

### 4. Canonical skeleton identity is fixed

The v0.1 body representation uses:

```text
cutsceneai-humanoid-v1
```

with the existing 22-joint ordering already defined by `CANONICAL_HUMANOID_JOINTS`.

Source rigs must be normalized to this profile during dataset ingestion. Target-engine rigs are
not part of the model representation.

### 5. Training rotations use continuous 6D rotation representation

Neural-network rotation targets and conditioning rotations use the continuous 6D representation
formed by the first two columns of a proper 3x3 rotation matrix.

Canonical order:

```text
[r00, r10, r20, r01, r11, r21]
```

This is called `rotation_6d_columns` in CutSceneAI v0.1.

The two 3-vectors in stored ground-truth examples must be unit length and mutually orthogonal
within numerical tolerance. Dataset ingestion is responsible for producing valid values.

The runtime Generated Performance Package remains quaternion-based
(`quaternion_xyzw`). Conversion between 6D rotations and normalized quaternions happens only at
well-defined dataset/runtime boundaries.

We do **not** train directly on Euler angles.

### 6. Physical values remain unnormalized on disk

Canonical dataset artifacts store physical values in their real canonical units:

- positions and distances in meters;
- frame indices in canonical 30-fps frames;
- focal lengths in millimeters when camera targets are added;
- scalar intensities in their declared natural ranges.

Training normalization is a separate transform.

Mean/std, scale, clipping, whitening, or learned normalization statistics must be versioned as
training-run artifacts and must never silently change the meaning of the canonical dataset.

This keeps examples inspectable and prevents a checkpoint-specific normalization choice from
becoming part of the data contract.

### 7. World and local spaces must be explicit

Every spatial field added by later schemas must declare its space.

The v0.1 convention reserves these meanings:

- actor root translation/orientation: canonical world space;
- articulated joint rotations: canonical parent-local space;
- optional joint-position auxiliary supervision: root-relative canonical space unless a field
  explicitly declares otherwise;
- target/object transforms in conditioning: canonical world space;
- gaze vectors: a later gaze schema must explicitly state world-space or actor-local semantics and
  use only one convention within a version.

No field may rely on an implicit engine transform space.

### 8. Missing supervision is represented by masks, not zeros

Zero is often a valid physical value. Therefore missing labels must never be encoded by filling a
target channel with zero and pretending it is observed.

Later schemas must provide explicit supervision availability at the narrowest practical level.

Examples:

- a sequence with body mocap but no camera labels;
- frames where gaze target is unknown;
- synthetic examples with exact contacts;
- public mocap where contact labels are derived and have lower confidence.

Batch padding also uses an explicit frame-valid mask. Padding is not part of the stored canonical
sequence.

### 9. Stable semantic identities stay symbolic on disk

Actors, targets, events, phases, dialogue cues, and camera subjects are referenced by stable
semantic IDs in the canonical dataset.

Token IDs, embedding indices, categorical integer encodings, and vocabulary hashes belong to the
training transform/configuration layer, not the canonical source data.

This ensures dataset records remain meaningful when tokenizers or model architectures change.

### 10. Conditioning and targets are separate namespaces

Every final training example will have a strict conceptual split:

```text
conditioning -> information available to the model
targets      -> canonical performance the model must predict
metadata     -> provenance / quality / split information not implicitly exposed to the model
```

A field must not move between these namespaces implicitly.

Data leakage is therefore a schema violation, not just a training-code bug.

### 11. Provenance is mandatory

Every sample must retain enough metadata to answer:

- where did the example come from;
- was it captured, public mocap, synthetic, procedural, or manually authored;
- what source asset/record identifies it;
- what transformation pipeline version produced the canonical sample;
- what license/usage class applies;
- whether labels are measured, derived, procedural, or human-reviewed.

Provenance fields are metadata by default and are not model conditioning unless a later model
contract explicitly promotes one.

### 12. Deterministic canonicalization is required

Given the same source record, canonicalization version, and configuration, dataset ingestion must
produce byte-equivalent canonical numerical content except for explicitly documented
nondeterministic preprocessing.

Random augmentation occurs after canonicalization and is never written back as if it were source
truth.

## Machine-readable companion contract

The frozen shared values are mirrored in:

`docs/model/contracts/canonical-training-representation-v0.1.json`

Later input/target schemas must reference these values rather than inventing conflicting
conventions.

## Tensorization boundary

The canonical disk representation is not required to be the exact in-memory tensor layout.

The dataset loader is responsible for:

1. parsing canonical records;
2. validating contract version and spaces;
3. applying versioned normalization;
4. converting symbolic IDs/text into model features;
5. assembling tensors;
6. generating padding and supervision masks;
7. applying training-only augmentation.

The decoder/output adapter reverses model-specific transforms and produces canonical physical
targets before any Unity/Unreal realization occurs.

## Guard benchmark implications

For the first guard-scene family, all generated variants must eventually be expressible on this
shared frame grid and coordinate system.

A future accepted body target must therefore make it possible to measure, in canonical units:

- root path;
- stop/deceleration timing;
- final body facing direction;
- head/gaze direction toward the bound door;
- foot contact stability;
- floor penetration;
- transition continuity.

Those specific target fields are deliberately defined in later representation steps, not in this
shared contract.

## Acceptance checklist for this step

Canonical Training Representation v0.1 is frozen when all of the following are true:

- [x] fixed model timebase selected;
- [x] canonical coordinate space selected;
- [x] canonical skeleton identity selected;
- [x] training rotation representation selected;
- [x] raw-vs-normalized storage boundary selected;
- [x] world/local-space rule selected;
- [x] variable-length and padding semantics selected;
- [x] missing-supervision semantics selected;
- [x] conditioning/target/metadata separation selected;
- [x] provenance and deterministic-canonicalization rules selected;
- [x] machine-readable companion contract committed.

## Compatibility rule

Any future change to one of these frozen invariants requires a new representation contract version.
Do not silently mutate v0.1 datasets or reinterpret existing examples.

## Exact next development step

Define and freeze **Scene Conditioning Representation v0.1**.

That schema must express the information the model is allowed to know about the live scene,
including actor and object transforms, target relationships, floor/ground context, environment
bounds, and extensible obstacle/visibility information, all in this canonical representation.
