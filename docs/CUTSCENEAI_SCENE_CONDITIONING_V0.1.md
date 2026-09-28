# CutSceneAI Scene Conditioning Representation v0.1

**Status:** Frozen design draft for first implementation  
**Date:** 2026-09-28  
**Repository:** `Nithin0553/CutSceneAI-Studio`  
**Working branch:** `agent/cross-engine-parity-v0.1`

## Purpose

Scene Conditioning Representation v0.1 defines the engine-neutral spatial context consumed by the future CutSceneAI Cinematic Performance Model.

Its job is to answer questions such as:

- Where is the performing actor?
- Where is the target object?
- What direction and distance separate them?
- What is the target's size and orientation?
- What nearby geometry can affect locomotion, turning, gaze, or camera placement?
- What support / floor information is known?
- Which objects are semantic targets versus background context?

This representation is model-facing and canonical. Unity and Unreal remain scene-data sources and realization targets; neither engine is part of the learned representation.

---

# 1. Architectural boundary

```text
Unity scene snapshot ─┐
                      │
                      ├─> Scene Conditioning Normalizer
                      │            ↓
Unreal scene snapshot ┘   SceneConditioning v0.1
                                   ↓
                    Temporal / Motion Director
                                   ↓
                    Cinematic Performance Model
```

The raw engine snapshots may contain engine-specific IDs, paths, component names, or metadata.

The normalized model-facing representation must not.

---

# 2. Relationship to current repository

The existing Studio scene snapshot already provides a useful source contract:

- object ID
- display name
- hierarchy path
- parent object ID
- kind
- active flag
- static flag
- tag / layer
- prefab path
- canonical transform
- optional canonical bounds
- component names

Unity currently publishes this snapshot in canonical right-handed, Y-up, -Z-forward meters.

The current Unreal bridge publishes verified actor/asset records and canonical actor positions in metadata, but it does not yet publish a full `scene_snapshot` equivalent.

Therefore:

1. Scene Conditioning v0.1 must not depend on Unity-only data.
2. The Unreal bridge will later need scene-snapshot parity.
3. Missing fields must be represented explicitly as unavailable rather than silently fabricated.

---

# 3. Core design rules

1. **Engine neutral.**
   No Unity GameObject path, Unreal Actor path, Timeline identifier, Sequencer identifier, component class path, or engine coordinate convention enters model tensors.

2. **Physical values on disk.**
   Persist transforms, distances, bounds, and directions in canonical physical units. Tensor normalization happens during dataset loading.

3. **Conditioning is separate from targets.**
   Scene context must not accidentally contain future ground-truth body poses, camera trajectories, or other labels that leak the answer.

4. **Symbolic identity is preserved.**
   The model / director must be able to distinguish `actor:guard`, `target:door`, and nearby context entities.

5. **Unknown is not zero.**
   Missing bounds, visibility, floor, geometry, or affordance data must have explicit presence masks / optional fields.

6. **Local relationships are derivable.**
   Store canonical world facts; derive actor-relative features reproducibly.

7. **Scales from minimal to richer geometry.**
   v0.1 supports transforms and bounds. Later versions may add occupancy, point clouds, nav data, meshes, SDFs, or learned geometry tokens without changing the basic entity/relationship model.

---

# 4. Top-level record

Proposed conceptual schema:

```json
{
  "scene_conditioning_version": "0.1.0",
  "scene_id": "hallway-scene-001",
  "coordinate_space": {
    "distance_unit": "meter",
    "handedness": "right",
    "up_axis": "y",
    "forward_axis": "-z",
    "rotation_representation": "quaternion_xyzw"
  },
  "entities": [],
  "relationships": [],
  "surfaces": [],
  "geometry": null,
  "provenance": {}
}
```

The exact Pydantic / JSON schema will follow this document.

---

# 5. Scene entities

Every model-visible scene entity should contain:

```json
{
  "entity_id": "door-01",
  "semantic_type": "door",
  "role": "target",
  "active": true,
  "dynamic": false,
  "transform": {
    "position_m": {"x": 3.4, "y": 0.0, "z": -1.2},
    "rotation": {"x": 0.0, "y": 0.7071, "z": 0.0, "w": 0.7071},
    "scale": {"x": 1.0, "y": 1.0, "z": 1.0}
  },
  "bounds": {
    "center_m": {"x": 3.4, "y": 1.0, "z": -1.2},
    "extents_m": {"x": 0.5, "y": 1.0, "z": 0.1}
  },
  "affordances": ["look_target"]
}
```

## Required v0.1 entity fields

- `entity_id`: stable engine-neutral ID within the conditioning record
- `semantic_type`: coarse semantic category
- `role`: relationship to the current performance
- `active`
- `dynamic`
- canonical transform

## Optional v0.1 entity fields

- bounds
- parent entity ID
- affordances
- approximate support / interaction points
- geometry reference

---

# 6. Semantic types

v0.1 should use an open string vocabulary with recommended common values rather than a closed enum that will quickly become restrictive.

Recommended initial values:

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
camera_landmark
environment
unknown
```

Dataset-specific semantics may extend this list.

The model should also receive a broader structural category where useful:

```text
actor
target
obstacle
support_surface
context
```

This prevents overdependence on object names.

---

# 7. Performance role

An entity's `role` is not its semantic class.

Example:

```text
semantic_type = door
role = target
```

Another door in the same hallway may be:

```text
semantic_type = door
role = context
```

Recommended roles:

- `performer`
- `target`
- `interaction_object`
- `obstacle`
- `support`
- `context`

One entity may eventually have multiple role tags, but v0.1 should keep one primary role plus optional affordances.

---

# 8. Canonical transforms

All entity transforms are canonical world transforms:

```text
meters
right-handed
+Y up
-Z forward
quaternion XYZW
```

Do not train directly on engine-local transforms.

For an actor at position `A` and target at position `T`, derive:

```text
target_relative_world = T - A
horizontal_target_vector = project_to_ground(T - A)
target_distance = ||T - A||
horizontal_distance = ||horizontal_target_vector||
target_bearing = signed ground-plane angle(actor_forward, horizontal_target_vector)
target_elevation = vertical angle to target
```

These derived features are deterministic dataset-loader features, not authoritative stored geometry.

---

# 9. Actor-relative conditioning view

Although world-space values remain authoritative on disk, the first body model should primarily consume actor-relative geometry.

Example derived model input:

```json
{
  "target_relative_position_m": {
    "x": 2.1,
    "y": 0.3,
    "z": -3.8
  },
  "target_distance_m": 4.35,
  "target_bearing_rad": 0.92,
  "target_elevation_rad": 0.07
}
```

Why:

- translation invariance
- easier learning across different scene origins
- direct relevance to turn / gaze / locomotion constraints
- no dependency on Unity or Unreal world placement conventions

World-space values remain available for full-scene planning and camera generation.

---

# 10. Bounds

Axis-aligned canonical world bounds are sufficient for v0.1:

```json
{
  "center_m": {"x": 3.4, "y": 1.0, "z": -1.2},
  "extents_m": {"x": 0.5, "y": 1.0, "z": 0.1}
}
```

Bounds are important because an object point alone is insufficient for:

- camera framing
- collision approximation
- interaction approach
- gaze aiming at meaningful height
- distinguishing a wall from a small prop

If bounds are unknown, `bounds = null`.

Do not substitute zero extents.

---

# 11. Target points

Some interactions need a meaningful point rather than an object's origin.

Optional target points:

```json
{
  "target_points": [
    {
      "id": "visual-center",
      "kind": "look",
      "position_m": {"x": 3.4, "y": 1.35, "z": -1.2}
    },
    {
      "id": "handle",
      "kind": "interaction",
      "position_m": {"x": 3.0, "y": 1.0, "z": -1.15}
    }
  ]
}
```

v0.1 does not require target points for every object.

When absent:

- gaze may use bounds center or object position according to deterministic rules;
- interaction generation should not pretend a precise affordance point is known.

---

# 12. Affordances

Affordances represent semantically possible uses.

Recommended initial vocabulary:

```text
look_target
approach_target
touch_target
grasp_target
openable
closable
sit_surface
stand_surface
cover
support
walkable
```

Affordances are conditioning hints, not guaranteed capabilities.

For the first guard benchmark, `Door_01` needs only:

```text
look_target
```

Opening the door is outside the first benchmark.

---

# 13. Relationships

Important pairwise relationships may be precomputed and stored when they are semantically meaningful.

Example:

```json
{
  "source_entity_id": "guard",
  "target_entity_id": "door-01",
  "relation": "attention_target"
}
```

Recommended initial relations:

- `attention_target`
- `interaction_target`
- `approach_target`
- `avoid`
- `supported_by`
- `inside`
- `near`

Metric spatial facts should still be derived from transforms rather than duplicated as authoritative fields.

---

# 14. Ground / support surfaces

The motion model needs an explicit concept of support.

Minimum v0.1 support surface:

```json
{
  "surface_id": "floor-main",
  "kind": "ground",
  "point_m": {"x": 0.0, "y": 0.0, "z": 0.0},
  "normal": {"x": 0.0, "y": 1.0, "z": 0.0},
  "walkable": true
}
```

This is enough for the first flat-floor guard benchmark.

Later versions can support:

- polygonal surfaces
- stairs
- slopes
- nav meshes
- terrain height fields

Do not silently assume `y=0` globally when a support plane is available.

---

# 15. Obstacle context

For first model experiments, obstacle context may use nearby entity bounds.

The model-facing local crop can select:

- performer
- explicit targets
- N nearest obstacles / context objects within radius R

The selection algorithm must be deterministic and versioned.

Do not feed every object in a large game level to the first body model.

A future scene encoder can handle larger graphs.

---

# 16. Geometry references

v0.1 may include an optional opaque canonical geometry reference in dataset metadata:

```json
{
  "geometry": {
    "kind": "occupancy_grid",
    "artifact": "geometry/scene-001.npz"
  }
}
```

But the first body baseline must not require it.

Initial target-conditioned turn training should work with:

- actor transform
- target transform
- target bounds
- ground plane

This keeps the first experiment tractable.

---

# 17. Visibility and line of sight

Visibility matters for gaze and camera, but the current engine snapshots do not provide reliable engine-neutral visibility.

Therefore v0.1 defines it as optional derived annotation:

```json
{
  "source_entity_id": "guard",
  "target_entity_id": "door-01",
  "visible": true,
  "method": "synthetic_ground_truth"
}
```

For synthetic datasets we can know or compute this exactly.

For live engine conditioning, a future bridge query / geometry processor may supply it.

Missing visibility must not be interpreted as visible.

---

# 18. Model-visible vs metadata-only data

## Model-visible

- semantic type
- performance role
- canonical transforms
- canonical bounds
- target points where known
- affordances
- selected relationships
- support surfaces
- optional local obstacle geometry

## Metadata-only

- source engine
- source engine version
- Unity hierarchy path
- Unreal actor path
- prefab path
- asset path
- source bridge object ID
- source dataset filename
- license / provenance

This separation is mandatory to prevent engine-specific overfitting and data leakage.

---

# 19. Binding normalization

Studio role bindings currently map CIR IDs to engine-discovered object IDs.

The scene-conditioning builder should convert:

```text
CIR character guard
    +
binding → RobotKyle asset / scene state

CIR environment door
    +
binding → Door_01 scene object
```

into canonical entities:

```text
actor:guard
target:door
```

The model should never need to know:

```text
Assets/Starter Assets/...
GameObject instance ID
/Game/...
Unreal actor path
```

This also solves part of the current asset-vs-scene-instance ambiguity by making scene state and realization asset identity separate concerns.

---

# 20. Character asset versus scene instance

This is an explicit architectural distinction.

A performing character has two independent concepts:

```text
Character realization asset
    e.g. RobotKyle prefab

Character scene state
    position
    rotation
    bounds
    current pose / velocity
```

The current Studio binding flow sometimes overloads one binding to serve both purposes.

Scene Conditioning v0.1 treats only **scene state** as model conditioning.

The later Realization Target selects the engine-native character asset.

This separation should eventually remove duplicate-character and asset-vs-instance ambiguity.

---

# 21. Guard benchmark conditioning example

For:

> A guard walks through an abandoned hallway, hears a noise, stops, turns toward a door, and quietly asks who is there.

Minimal body conditioning:

```text
performer:
    id = guard
    position = guard world position
    orientation = guard world orientation
    current pose
    current velocity

attention target:
    id = door
    position = Door_01 world position
    bounds = Door_01 bounds
    look target = visual center

support:
    hallway floor plane

context:
    nearby wall / obstacle bounds if relevant
```

Derived features:

```text
door relative position
door horizontal bearing
door distance
required final facing vector
gaze vector
available floor/support
```

This is the information the current text-only body request is missing.

---

# 22. First baseline conditioning tensor

The first target-conditioned-turn model should consume approximately:

```text
previous canonical pose
previous root orientation
previous root velocity

target relative XYZ
target horizontal distance
target bearing
target elevation
target bounds size

desired duration
desired final facing direction
phase/action embedding

ground plane orientation
left/right initial contact state
```

Do not freeze exact neural tensor packing in this representation document.

The dataset loader owns tensorization.

---

# 23. Normalization

Recommended learned-input normalization:

- positions / distances: dataset statistics or bounded scene scale
- angles: sin/cos or continuous directional representation
- rotations: likely 6D representation for neural tensors
- durations: seconds or normalized frame duration
- categorical semantics: embeddings
- presence: explicit masks

Canonical serialized values remain meters and quaternions.

Do not serialize normalized neural values as the canonical scene record.

---

# 24. Live-scene conditioning flow

Runtime flow should become:

```text
Engine bridge
    ↓
raw scene snapshot
    ↓
binding resolution
    ↓
SceneConditioningBuilder
    ↓
canonical SceneConditioning v0.1
    ↓
Temporal Director / model
```

This builder should be deterministic and independently unit tested.

---

# 25. Synthetic dataset flow

Synthetic-data generation should write Scene Conditioning v0.1 directly.

```text
procedural scene generator
    ↓
canonical geometry / entities
    ↓
scene conditioning
    ↓
ground-truth choreography / motion
    ↓
training example
```

Synthetic training data must not depend on Unity or Unreal serialization.

Unity / Unreal may later be used to render or validate synthetic examples, but not as the canonical data format.

---

# 26. Engine bridge gaps discovered

## Unity

Current bridge already provides most v0.1 raw inputs:

- canonical transform
- bounds
- hierarchy
- active/static state
- components
- scene object identity

Needed later:

- explicit support surfaces / ground extraction
- optional visibility / collision queries
- clear exclusion of prior CutSceneAI-generated output from user-source scene conditioning

## Unreal

Current bridge does not yet provide the full `StudioSceneSnapshot` payload.

Needed before cross-engine live conditioning parity:

- actor transform in full canonical position + rotation + scale
- actor bounds
- parent / hierarchy where meaningful
- static/dynamic state
- scene object snapshot payload matching the Studio contract
- optional support / visibility information later

This is an integration requirement, not a reason to make the model Unreal-specific.

---

# 27. Acceptance tests for Scene Conditioning v0.1

Before model training, the builder should pass tests such as:

1. Same synthetic scene encoded through equivalent Unity and Unreal source fixtures produces the same canonical entities within tolerance.
2. Changing world origin without changing actor-relative layout leaves derived local conditioning unchanged.
3. Rotating the whole scene consistently changes canonical world transforms but preserves actor-relative target geometry.
4. Missing bounds stays missing rather than becoming zero bounds.
5. Engine-specific paths never appear in model-visible serialized fields.
6. Bound door position produces the expected target bearing and distance.
7. Generated CutSceneAI output objects can be excluded from source-scene conditioning.
8. Asset identity and scene-instance state remain distinct.

---

# 28. What is frozen in v0.1

Freeze now:

- canonical coordinate system
- entity / role distinction
- canonical transform requirement
- optional bounds
- explicit missing-data semantics
- support surfaces
- model-visible versus metadata-only separation
- actor-relative features are derived, not the sole stored truth
- engine asset identity is separate from scene state

Do not freeze yet:

- dense geometry encoding
- scene neural encoder architecture
- graph neural network versus transformer scene encoder
- exact obstacle crop size
- exact semantic vocabulary
- exact tensor dimensions
- visibility implementation
- navmesh representation

---

# 29. Immediate implementation step

Implement:

`cutsceneai_performance.scene_conditioning`

with versioned Pydantic models for:

- `SceneConditioning`
- `SceneEntity`
- `SceneEntityRole`
- `SceneTransform`
- `SceneBounds`
- `SceneTargetPoint`
- `SceneRelationship`
- `SupportSurface`
- `SceneConditioningProvenance`

Then implement deterministic derived geometry functions:

- target-relative position
- horizontal distance
- full distance
- actor forward vector
- signed target bearing
- target elevation
- desired facing vector

After those models/tests pass, implement a Studio `SceneConditioningBuilder` that converts the current live scene snapshot + role bindings into the new canonical representation.

---

# 30. Next milestone after implementation

For the current guard test, we must be able to inspect one deterministic record and answer numerically:

```text
Where is the guard?
Where is Door_01?
How far away is it?
At what horizontal bearing?
What exact direction must the guard end facing?
What point should the head/gaze target?
What ground/support plane is available?
```

Only after those answers are correct do we begin the first trainable target-conditioned-turn dataset generator.
