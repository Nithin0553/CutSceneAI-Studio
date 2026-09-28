# CutSceneAI Training Dataset Schema v0.1

**Status:** Frozen for first dataset generation and baseline training  
**Contract version:** `0.1.0`  
**Depends on all frozen v0.1 model representation contracts**

## Purpose

This schema composes the previously frozen model representations into one legal CutSceneAI training
example.

A dataset example is not an engine scene dump. It is a canonical, auditable training record with a
strict separation between:

- conditioning;
- targets;
- metadata/provenance.

The schema supports body-only, body+contact/gaze, and later body+camera supervision without changing
the top-level dataset format.

---

## 1. Dataset directory

Recommended v0.1 layout:

```text
dataset/
  manifest.json
  train/
    <sample_id>/
      example.json
      body.npz
      contact_gaze.npz        # optional when unavailable
      camera.npz              # optional
      geometry.npz            # optional
      audio.wav               # optional future use
  val/
  test/
```

Dense numeric arrays live in compact artifacts.

Semantic structure, provenance, rights, masks, and references live in `example.json`.

---

## 2. Dataset manifest

The dataset root manifest contains:

```text
dataset_id
dataset_version
schema_version
canonical_contract_versions
creation_timestamp
generator / canonicalizer version
sample counts
split counts
family counts
rights summary
artifact hashing algorithm
```

The dataset manifest must list the exact versions of:

- canonical training representation;
- scene conditioning;
- choreography;
- body target;
- contact/gaze target;
- camera target.

A dataset is invalid if its component records silently use incompatible contract versions.

---

## 3. Sample identity

Every sample requires:

```text
sample_id
family_id
split
sequence_frame_count
fps = 30
```

### sample_id

Unique across the entire dataset.

Example:

```text
guard-hallway-000184
```

### family_id

Groups semantic/procedural siblings that could leak across splits.

Example:

```text
guard-hallway-family-v0.1
```

or a finer procedural seed family such as:

```text
guard-layout-042
```

Split policy operates on family/group identity, not only individual sample identity.

---

## 4. Split

Frozen split values:

```text
train
val
test
```

No sample may belong to more than one split.

The same source sequence, near-duplicate procedural seed, mirrored copy, retimed copy, or trivially
augmented derivative must not appear across splits.

---

## 5. Top-level example namespaces

One `example.json` has:

```text
identity
conditioning
targets
metadata
artifacts
```

This namespace separation is mandatory.

---

## 6. Conditioning namespace

`conditioning` contains information legally and causally available to the model for the selected
training task.

It may include:

```text
narrative
structured CIR intent
scene_conditioning
choreography
previous_body_state
task_configuration
```

Not every training task exposes every field.

Example:

### Body-generator task

```text
conditioning:
    narrative
    scene_conditioning
    choreography
    previous_body_state

targets:
    body
    contact_gaze
```

### Temporal-director task

```text
conditioning:
    narrative
    scene_conditioning

targets:
    choreography
```

### Camera task

```text
conditioning:
    narrative / shot intent
    scene_conditioning
    accepted body performance
    choreography events

targets:
    camera
```

The training-task view determines exposure.

The canonical example keeps all components separately addressable.

---

## 7. Target namespace

Possible target components:

- choreography;
- canonical body;
- contact/gaze;
- camera;
- future facial/dialogue targets.

Each component has an explicit availability flag.

Unavailable components are omitted or referenced as unavailable.

They are never replaced by zero-valued fake labels.

---

## 8. Artifact references

Dense artifacts use content-addressed references.

Each artifact reference stores:

```text
kind
relative_path
sha256
byte_length
format
contract_version
```

Recommended v0.1 formats:

```text
body.npz
contact_gaze.npz
camera.npz
geometry.npz
```

SHA-256 is computed over exact file bytes.

A dataset validator must verify hashes before training.

---

## 9. Narrative record

Narrative conditioning may include:

```text
prompt
scene_intent
style
emotion
language
source_text_id
```

The exact tokenizer is not stored in the canonical example.

Tokenizer and text-encoder configuration belong to the training run.

---

## 10. CIR reference

A sample may keep:

- full canonical CIR fragment; or
- stable CIR artifact reference / fingerprint.

The dataset contract does not require the original engine project.

If CIR is included as conditioning, it must already be engine-neutral.

---

## 11. Scene Conditioning component

Scene conditioning follows:

`cutsceneai-scene-conditioning-representation v0.1`

The record may be embedded in `example.json` or stored as a referenced canonical JSON artifact.

For first dataset generation, embedding is recommended for inspectability.

---

## 12. Choreography component

Choreography follows:

`cutsceneai-choreography-temporal-representation v0.1`

It may be:

- conditioning for body generation;
- target for Temporal Director training.

The sample metadata must declare the intended supervision role for each training view.

---

## 13. Body artifact

`body.npz` follows the canonical body target contract.

Required arrays:

```text
root_position_m              [T, 3]
root_rotation_6d_columns     [T, 6]
joint_rotations_6d_columns   [T, 22, 6]
```

Optional:

```text
joint_positions_root_relative_m [T, 22, 3]
```

The JSON record stores masks and availability.

---

## 14. Contact/gaze artifact

Recommended arrays:

```text
left_foot_contact            [T]
right_foot_contact           [T]

left_contact_available       [T]
right_contact_available      [T]

left_contact_confidence      [T]
right_contact_confidence     [T]

gaze_active                  [T]
gaze_active_available        [T]

head_direction_world         [T, 3]    optional/masked
gaze_direction_world         [T, 3]    optional/masked
```

Symbolic target IDs and support-surface IDs remain in JSON or a deterministic symbolic sidecar
rather than being baked into arbitrary integer token IDs.

---

## 15. Camera artifact

When present:

```text
position_m                   [T, 3]
rotation_6d_columns          [T, 6]
focal_length_mm              [T]
```

Optional dense composition/visibility arrays may also be present.

Shot windows and symbolic entity references remain in JSON.

---

## 16. Previous-body-state conditioning

For continuation or phase-level training, a task may expose a fixed number of preceding body frames.

Those frames come from the canonical body target but are copied into the training view only for
causal conditioning.

The task configuration must record:

```text
context_frames
prediction_start_frame
prediction_end_frame
```

No future frames beyond the allowed context may leak into conditioning.

---

## 17. Supervision masks

The example must make availability explicit for:

- body target;
- auxiliary joint positions;
- left/right contact;
- gaze-active;
- gaze target identity;
- head direction;
- gaze direction;
- camera;
- composition/visibility/collision annotations.

Batch-level frame padding uses a separate runtime mask.

Stored sample masks describe source supervision only.

---

## 18. Provenance record

Every sample requires provenance sufficient to reconstruct its origin.

Minimum:

```text
source_kind
source_dataset_or_generator
source_record_id
canonicalizer_version
generation_seed when applicable
derivation_versions
human_review_status
```

Recommended source kinds:

```text
owned_capture
licensed_capture
public_dataset
synthetic
procedural
human_authored
derived
```

---

## 19. Rights / license record

Friday's research identified data rights as a first-order model-development constraint.

Every sample therefore requires a rights record.

Frozen fields:

```text
rights_status
license_name
license_reference
commercial_training_status
redistribution_status
model_weight_distribution_status
review_status
notes
```

Recommended symbolic `rights_status`:

```text
owned
commercially_licensed
permissive
research_only
restricted
unknown
```

Recommended status values for training/distribution decisions:

```text
allowed
not_allowed
unclear
not_reviewed
```

These fields record project policy/review state.

They are not a substitute for legal review.

---

## 20. Research-only versus production-cleared pools

The dataset tooling must support at least two explicit usage pools:

```text
research
production_candidate
```

A sample may enter `production_candidate` only when the project's rights policy says its training
and intended weight-distribution use is allowed.

Research-only samples must never silently flow into a production-cleared checkpoint.

Training run manifests must record the selected usage pool.

---

## 21. Quality metadata

Each sample may include quality flags such as:

```text
body_quality
contact_quality
gaze_quality
camera_quality
canonicalization_warnings
human_review_status
```

Quality metadata is not model conditioning by default.

It may be used for:

- filtering;
- curriculum;
- loss weighting;
- audit.

---

## 22. Canonicalization record

Required:

```text
canonicalizer_name
canonicalizer_version
source_fps
target_fps = 30
source_coordinate_space
target_coordinate_space
source_skeleton
target_skeleton
rotation_conversion_version
resampling_version
```

The same source + same canonicalizer version/configuration must produce deterministic canonical
numeric content.

---

## 23. Augmentation rule

Random training augmentations are not persisted as source truth.

Examples:

- mirroring;
- time scaling;
- target perturbation;
- text dropout;
- noise injection;
- scene-entity dropout.

Augmentation configuration belongs to the training run.

If an augmentation produces a new persistent dataset sample, it must receive:

- a new sample ID;
- provenance back to the parent;
- family linkage;
- explicit deterministic generation parameters.

---

## 24. Split leakage rules

At minimum, group together across one split:

- same original source sequence;
- same capture take;
- same procedural base layout if variants are near duplicates;
- mirrored variants;
- retimed variants;
- small-noise variants;
- same cinematic camera trajectory paired with trivially altered labels.

For the guard synthetic family, hold out combinations of:

- target-bearing ranges;
- hallway geometry;
- actor starting heading;
- walk distance;
- reaction timing;
- turn duration;
- support-foot conditions.

This tests compositional generalization.

---

## 25. Dataset family for first benchmark

Initial dataset:

```text
cutsceneai-guard-turn-v0.1
```

First task scope:

```text
target-conditioned turn
```

Vary:

- starting root heading;
- target bearing;
- target distance;
- initial pose;
- support-foot state;
- turn duration;
- subtle style;
- target bounds/height.

Later family:

```text
cutsceneai-guard-locomotion-stop-v0.1
```

Then composition:

```text
cutsceneai-guard-hallway-v0.1
```

---

## 26. Training-run manifest

Every training run must write a manifest containing:

```text
dataset_id/version
dataset fingerprint
split fingerprint
usage pool
selected task/view
contract versions
normalization statistics/version
augmentation configuration
tokenizer/text encoder
model config
seed
optimizer config
checkpoint hashes
code commit SHA
```

This is required for reproducibility.

---

## 27. Dataset fingerprint

A dataset fingerprint should be deterministic over:

- sorted sample IDs;
- per-sample example JSON hash;
- referenced artifact hashes;
- dataset manifest core fields.

The exact canonical hashing procedure will be implemented and versioned.

Two differently ordered directory listings must produce the same fingerprint.

---

## 28. Validation gates before training

A sample is rejected if:

- contract versions mismatch;
- artifact hash fails;
- required body arrays have wrong shape;
- frame counts disagree;
- symbolic references are invalid;
- rights policy excludes the selected training pool;
- NaN/Inf exists;
- canonical rotation validation fails;
- split/family leakage policy is violated.

Dataset validation is a hard gate.

---

## 29. First-body-baseline training view

For target-conditioned turning:

### Conditioning exposed

```text
narrative/action text
performer scene state
target scene state
derived target-relative geometry
choreography turn phase
body-facing goal
coarse support-contact intent
previous body pose/state
```

### Targets exposed

```text
canonical body sequence
left/right contact labels
head/gaze supervision when available
```

### Hidden

```text
future exact root trajectory
future exact joint rotations
future exact contact sequence
future exact gaze-direction sequence
camera target
metadata-only source/engine fields
```

---

## 30. What is frozen now

Frozen in v0.1:

- top-level conditioning/targets/metadata/artifacts split;
- sample ID + family ID;
- train/val/test;
- family-aware leakage policy;
- explicit contract-version composition;
- content-addressed artifact references;
- sample-level provenance;
- sample-level rights/license review state;
- research versus production-candidate usage pools;
- explicit supervision masks;
- deterministic canonicalization metadata;
- training-run reproducibility manifest;
- dataset fingerprint requirement.

---

## 31. Intentionally not frozen

Do not freeze yet:

- final storage backend beyond the first filesystem/NPZ implementation;
- distributed dataset sharding format;
- cloud object-store layout;
- exact compression;
- exact numeric dtype for every artifact;
- exact tokenizer;
- exact batch sampler;
- exact augmentation policy.

---

## 32. Machine-readable companion

Frozen invariants are mirrored in:

`docs/model/contracts/training-dataset-schema-v0.1.json`

---

## 33. Exact next development step

Define and freeze:

**Evaluation & Acceptance Metrics v0.1**

It must specify deterministic metrics for:

- body motion;
- semantic/choreography satisfaction;
- target facing;
- root path / stop timing;
- contact / foot sliding;
- floor penetration;
- gaze;
- camera visibility/framing/collision/smoothness;
- runtime retarget fidelity;
- cross-engine parity.

After evaluation metrics are frozen, generate the first guard-scene training/evaluation dataset.
