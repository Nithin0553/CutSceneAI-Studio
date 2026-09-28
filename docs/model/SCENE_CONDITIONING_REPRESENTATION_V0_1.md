# CutSceneAI Scene Conditioning Representation v0.1

**Status:** Frozen for the first trainable baseline  
**Contract version:** `0.1.0`  
**Depends on:** `docs/model/CANONICAL_TRAINING_REPRESENTATION_V0_1.md`  
**Model:** CutSceneAI Cinematic Performance Model  
**Scope:** Engine-neutral information the model is allowed to know about a scene before predicting performance

## Purpose

Scene Conditioning Representation v0.1 defines the canonical spatial and semantic scene context
available to the future CutSceneAI Cinematic Performance Model.

It exists to turn facts such as:

- the guard is here;
- the door is there;
- the door is the current attention target;
- the floor is this support plane;
- these nearby objects may obstruct movement or camera placement;

into one deterministic, engine-neutral conditioning record.

The representation is **not** a Unity scene format and **not** an Unreal level format.

Unity and Unreal are allowed to supply raw observations. A normalizer converts those observations
into this representation before any model consumes them.

## Dependency on the frozen canonical training contract

Every rule in
`docs/model/CANONICAL_TRAINING_REPRESENTATION_V0_1.md`
applies here.

In particular:

- canonical model timebase is 30 fps;
- distance is meters;
- coordinates are right-handed, +Y up, -Z forward;
- model/dataset rotations use `rotation_6d_columns`;
- engine/runtime quaternions are converted at the boundary;
- raw physical values remain unnormalized on disk;
- symbolic semantic IDs remain symbolic on disk;
- missing information uses explicit optional fields / masks, not fabricated zeros;
- conditioning, targets, and metadata remain separate namespaces.

Scene Conditioning itself has no future motion labels and therefore must not leak target performance.

---

## 1. Source-to-model boundary

```text
Unity StudioSceneSnapshot ─┐
                           │
                           ├─> SceneConditioningBuilder
                           │          ↓
Unreal StudioSceneSnapshot ┘  SceneConditioning v0.1
                                      ↓
                           Temporal / Motion Director
                                      ↓
                           Cinematic Performance Model
```

Synthetic datasets may write Scene Conditioning v0.1 directly.

Raw engine snapshots can contain engine IDs, paths, classes, tags, component names, or native
coordinate systems.

The model-facing conditioning namespace cannot contain those engine-specific identifiers.

---

## 2. Current repository reality

The current Unity bridge already publishes most of the raw facts needed for v0.1:

- object identity;
- hierarchy / parent identity;
- kind;
- active state;
- static state;
- canonical world position;
- canonical world rotation;
- scale;
- optional canonical bounds;
- components.

The current Unreal bridge publishes verified actor records and canonical actor positions in asset
metadata, but does **not** yet publish a full `StudioSceneSnapshot` with transform, bounds, parent,
and static/dynamic parity.

That is an engine-integration gap to fix later.

It must not change the model contract.

---

## 3. Top-level structure

One scene-conditioning record contains:

```text
SceneConditioning
├── scene_id
├── entities
├── relationships
├── support_surfaces
├── optional geometry descriptor
└── metadata
```

Machine-readable frozen constants are mirrored in:

`docs/model/contracts/scene-conditioning-representation-v0.1.json`

---

## 4. Scene entity

Each model-visible entity has:

- stable engine-neutral `entity_id`;
- open-string `semantic_type`;
- one primary performance `role`;
- active state;
- dynamic/static state;
- canonical world transform;
- optional canonical world bounds;
- optional target points;
- optional affordances.

Conceptual example:

```json
{
  "entity_id": "door",
  "semantic_type": "door",
  "role": "target",
  "active": true,
  "dynamic": false,
  "transform": {
    "position_m": [3.4, 0.0, -1.2],
    "rotation_6d_columns": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
    "scale": [1.0, 1.0, 1.0]
  },
  "bounds": {
    "center_m": [3.4, 1.0, -1.2],
    "extents_m": [0.5, 1.0, 0.1]
  },
  "affordances": ["look_target"]
}
```

### Semantic type

`semantic_type` is intentionally an open string.

Recommended initial values include:

```text
character
door
window
wall
floor
ceiling
furniture
prop
vehicle
weapon
environment
unknown
```

A later vocabulary/tokenizer version may map these strings to learned IDs.

The canonical source record keeps them symbolic.

### Primary role

Frozen v0.1 roles:

- `performer`
- `target`
- `interaction_object`
- `obstacle`
- `support`
- `context`

Role is not the same as semantic type.

A `door` may be the current `target`; another door may simply be `context`.

---

## 5. Transform representation

Scene entity transforms are canonical world transforms.

### Position

```text
position_m = [x, y, z]
```

Units: meters.

### Rotation

Training/dataset storage follows the frozen representation:

```text
rotation_6d_columns =
[r00, r10, r20, r01, r11, r21]
```

Raw bridge quaternions are converted deterministically to this representation by the
SceneConditioningBuilder.

### Scale

```text
scale = [sx, sy, sz]
```

Scale is dimensionless.

No engine-local transform enters model-visible conditioning.

---

## 6. Bounds

v0.1 uses optional world-space axis-aligned bounds:

```text
center_m  = [x, y, z]
extents_m = [ex, ey, ez]
```

Bounds are important for:

- camera framing;
- approximate collision context;
- approach distance;
- gaze target height;
- distinguishing large surfaces from point-like props.

If bounds are not known, the field is absent/null.

Unknown bounds must never be represented as zero extents.

---

## 7. Target points

Objects may expose optional semantic points:

```json
{
  "point_id": "visual-center",
  "kind": "look",
  "position_m": [3.4, 1.35, -1.2]
}
```

Initial target-point kinds:

- `look`
- `approach`
- `interaction`

For the first guard benchmark, the door may use a derived visual center from its bounds.

A target point is conditioning only if it is available before motion generation.

---

## 8. Affordances

Affordances are optional semantic hints.

Recommended initial vocabulary:

- `look_target`
- `approach_target`
- `touch_target`
- `grasp_target`
- `openable`
- `closable`
- `sit_surface`
- `stand_surface`
- `cover`
- `support`
- `walkable`

The first target-conditioned-turn baseline requires only `look_target`.

Affordances are not promises that an interaction animation exists.

---

## 9. Relationships

Relationships encode semantic links, not duplicated geometry.

A relationship is:

```text
source_entity_id
target_entity_id
relation
```

Frozen recommended relation strings:

- `attention_target`
- `interaction_target`
- `approach_target`
- `avoid`
- `supported_by`
- `inside`
- `near`

Distance, bearing, and direction are derived from authoritative transforms.

They are not duplicated as source truth.

---

## 10. Support surfaces

Foot grounding cannot rely on an implicit `y = 0` assumption.

v0.1 supports planar support surfaces:

```json
{
  "surface_id": "floor-main",
  "kind": "ground",
  "point_m": [0.0, 0.0, 0.0],
  "normal": [0.0, 1.0, 0.0],
  "walkable": true
}
```

The first guard family can use a single flat floor.

Future representation versions may add:

- polygons;
- height fields;
- stairs;
- slopes;
- navigation meshes;
- signed-distance fields.

---

## 11. Optional geometry descriptor

Dense environment geometry is intentionally not required for the first trainable body baseline.

The schema reserves an optional descriptor:

```json
{
  "geometry": {
    "kind": "occupancy_grid",
    "artifact": "geometry/hallway-001.npz"
  }
}
```

Future allowed kinds may include:

- `occupancy_grid`
- `point_cloud`
- `sdf`
- `mesh_proxy`
- `nav_graph`

The first target-conditioned-turn baseline should work with transforms, bounds, and a support plane.

---

## 12. Model-visible conditioning versus metadata

### Model-visible conditioning

Allowed:

- entity semantic type;
- primary role;
- canonical transform;
- optional bounds;
- optional target points;
- optional affordances;
- semantic relationships;
- support surfaces;
- explicitly selected geometry artifact.

### Metadata-only

Never implicitly exposed to the model:

- source engine;
- Unity hierarchy path;
- Unity prefab path;
- Unreal actor path;
- engine object ID;
- asset path;
- bridge agent ID;
- source dataset path;
- licensing / provenance fields;
- original engine coordinate values.

Metadata exists for auditing and reproducibility.

It is not conditioning unless a future contract explicitly promotes a field.

---

## 13. Actor-relative derived features

World-space scene facts are authoritative on disk.

The dataset loader / model adapter derives actor-relative features deterministically.

For performer position `A`, performer forward vector `F`, and target point `T`:

```text
relative_world = T - A

horizontal = [relative_world.x, 0, relative_world.z]

distance =
    length(relative_world)

horizontal_distance =
    length(horizontal)

desired_facing =
    normalize(horizontal)

bearing =
    signed_angle_on_ground(F, desired_facing)

elevation =
    atan2(relative_world.y, horizontal_distance)
```

These values are ideal first-baseline inputs because they are invariant to arbitrary world origin.

They are derived features, not a replacement for stored canonical transforms.

---

## 14. Performer forward vector

The actor's canonical forward direction is:

```text
local forward = [0, 0, -1]
```

Apply the actor's canonical world rotation to this vector.

Then project to the ground plane when computing horizontal target bearing.

This rule is frozen in v0.1.

---

## 15. Character realization asset versus character scene state

This distinction is now explicit.

A character has two different concerns:

### Realization asset

Example:

```text
RobotKyle prefab
Manny skeletal mesh
```

This is needed when Unity/Unreal realizes accepted canonical motion.

### Scene state

Example:

```text
position
orientation
bounds
current pose
current velocity
```

This is what the model needs.

Scene Conditioning contains scene state only.

It must never require a Unity prefab or Unreal SkeletalMesh reference.

This resolves a current architecture ambiguity where one Studio binding may be asked to serve both
asset-selection and scene-state purposes.

A later Studio UX/API change should make these two concepts explicit.

---

## 16. Live binding normalization

The SceneConditioningBuilder consumes:

- CIR;
- Studio bindings;
- live scene snapshot;
- optional performer current state.

### Environment / target objects

If a bound environment entity resolves to a live scene-snapshot object:

- use its live canonical transform;
- use live bounds when present;
- assign a stable CIR-derived engine-neutral entity ID.

### Performer

If a selected character binding is a scene instance:

- use the scene-instance transform/state for conditioning;
- keep realization asset identity outside conditioning.

If a selected character binding is only an asset/prefab and there is no bound scene instance:

- use the CIR initial transform as the v0.1 performer scene state;
- record in metadata that state came from CIR rather than live scene;
- do not invent a live world transform from the asset.

This fallback is explicit and inspectable.

---

## 17. Generated-output exclusion

Prior CutSceneAI-generated realization objects must not silently become source conditioning for the
next generation.

The SceneConditioningBuilder must support a deterministic exclusion policy for managed generated
objects such as:

```text
CSA|...
Assets/CutSceneAI/Studio/Run_...
generated realization cameras / actors
```

unless the user explicitly chooses a generated object as an intentional input.

The default source-scene view is the user's project scene, not previous generated output.

---

## 18. Missing-data semantics

Optional scene facts remain optional.

Examples:

- bounds unavailable -> `bounds = null`;
- target point unavailable -> no target point entry;
- visibility unavailable -> no visibility annotation;
- dense geometry unavailable -> `geometry = null`.

The builder must not fabricate values merely to satisfy a tensor shape.

The dataset loader later creates explicit presence masks.

---

## 19. Visibility

Visibility is useful for gaze and camera but is not yet available consistently from live bridges.

v0.1 reserves optional relationship metadata for measured/known visibility.

Synthetic data may provide exact visibility.

Live-engine visibility can be added later using canonicalized raycast / geometry processing.

Unknown visibility is not equivalent to visible.

---

## 20. Deterministic local context selection

The full scene may contain thousands of objects.

For the first body model, model-visible local context should be selected deterministically.

Required inclusions:

1. performer;
2. every explicit target / interaction object;
3. relevant support surface.

Optional nearby context:

- nearest obstacles or context entities within a configured radius;
- capped at a configured maximum entity count.

The selection policy and its parameters belong to a versioned dataset/model configuration.

They are not silently changed inside the canonical source record.

---

## 21. Guard benchmark instance

For the current benchmark:

> A guard walks through an abandoned hallway, hears a noise, stops, turns toward a door, and quietly asks who is there.

the minimum useful Scene Conditioning record contains:

```text
performer
    actor:guard
    canonical position
    canonical orientation

target
    target:door
    Door_01 canonical position
    Door_01 bounds when available
    look_target affordance

relationship
    guard -> door = attention_target

support
    hallway floor plane

optional context
    nearby walls / obstacle bounds
```

Derived first-model features include:

- door relative XYZ;
- door horizontal bearing;
- door distance;
- door elevation;
- desired final facing vector.

This is the spatial information missing from the current text-only body-generation request.

---

## 22. First baseline conditioning subset

The first target-conditioned-turn model should consume:

```text
previous canonical body pose
previous root orientation
previous root velocity

target relative position
target distance
target bearing
target elevation
target approximate size / bounds mask

desired duration
desired final facing direction
action / phase identity

ground/support normal
initial left/right contact state
```

The exact tensor packing is deliberately not frozen here.

It belongs to the model/dataset-loader configuration.

---

## 23. Acceptance tests for this representation

Scene Conditioning v0.1 is only useful if it can be verified independently of model quality.

Required builder/schema tests:

1. canonical serialization rejects engine-space units / incompatible contract versions;
2. equivalent Unity and Unreal source fixtures normalize to equivalent canonical entities within tolerance;
3. changing the scene's world origin preserves actor-relative target features;
4. consistent whole-scene rotation preserves relative geometry in actor coordinates;
5. missing bounds remain missing;
6. engine-specific paths never appear in model-visible fields;
7. guard-to-door distance and bearing match analytical geometry;
8. target visual center derived from bounds is correct;
9. generated CutSceneAI realization objects are excluded by default;
10. character realization asset identity is not required by Scene Conditioning;
11. CIR fallback performer state is explicitly marked in metadata;
12. all referenced relationship entity IDs exist.

---

## 24. What is frozen now

Frozen for v0.1:

- dependency on canonical training representation v0.1;
- model-facing entity abstraction;
- symbolic semantic type;
- primary performance role;
- canonical world position;
- 6D canonical training rotation representation;
- optional canonical world bounds;
- target points;
- affordances;
- semantic relationships;
- planar support surfaces;
- optional geometry descriptor;
- actor-relative geometry derivation rules;
- performer forward convention;
- model-visible versus metadata-only boundary;
- realization asset versus scene-state separation;
- explicit missing-data semantics;
- default exclusion of prior managed CutSceneAI generated output.

---

## 25. Intentionally not frozen

Do not freeze yet:

- graph neural network versus transformer scene encoder;
- exact semantic vocabulary/tokenizer;
- dense geometry representation;
- exact local-context radius;
- exact maximum object count;
- visibility implementation;
- navmesh encoding;
- camera-specific scene tokenization;
- learned scene embedding dimension.

These are model/training decisions, not canonical scene facts.

---

## 26. Machine-readable companion

The frozen invariants are mirrored in:

`docs/model/contracts/scene-conditioning-representation-v0.1.json`

That file is a compact contract, not the full future JSON Schema for every record.

When the Pydantic implementation is added, generated JSON Schema must remain compatible with these
frozen invariants.

---

## 27. Exact next development step

With Scene Conditioning Representation v0.1 frozen, the next representation step is:

**Choreography / Temporal Representation v0.1**

It must define how a narrative performance is represented as overlapping phases, events,
constraints, targets, transition windows, and future goals before frame-level body generation.

Do not begin full model training until choreography, body target, contact/gaze, dataset, and
evaluation contracts are also frozen.
