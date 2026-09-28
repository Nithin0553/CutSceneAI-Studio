# CutSceneAI Choreography / Temporal Representation v0.1

**Status:** Frozen for the first trainable baseline  
**Contract version:** `0.1.0`  
**Depends on:**  
- `docs/model/CANONICAL_TRAINING_REPRESENTATION_V0_1.md`
- `docs/model/SCENE_CONDITIONING_REPRESENTATION_V0_1.md`

**Model:** CutSceneAI Cinematic Performance Model  
**Scope:** Engine-neutral temporal plan between narrative/CIR intent and frame-level performance generation

## Purpose

The Choreography / Temporal Representation defines **what should happen, when it should happen,
what may overlap, and what spatial/behavioral goals must be satisfied** before a body generator
produces frame-level motion.

It fixes the central weakness of the current pipeline:

```text
current:
CIR motion phase
→ independent text prompt
→ independent generated segment

target:
CIR / narrative
→ temporal choreography
→ coordinated overlapping goals
→ continuous scene-conditioned body performance
```

The representation is not a Unity Timeline and not an Unreal Sequencer.

It contains no engine-native tracks or clips.

---

## 1. Two training roles

The same choreography record serves two different future learning tasks.

### Temporal Director training

```text
INPUT
    narrative
    CIR
    scene conditioning

TARGET
    choreography / temporal representation
```

### Body Generator training

```text
INPUT
    scene conditioning
    choreography
    previous body state

TARGET
    frame-level canonical body performance
```

This distinction is important.

For Temporal Director training, choreography is a **target**.

For Body Generator training, choreography is **conditioning**.

The canonical record itself does not change; the training task determines the namespace.

---

## 2. Shared temporal rules

The frozen canonical training contract applies:

- 30 fps canonical model timebase;
- frame index is primary;
- temporal windows are half-open: `[start_frame, end_frame)`;
- variable-length sequences are allowed;
- frame padding exists only in training batches.

A choreography record has:

```text
duration_frames
events[]
phases[]
constraints[]
coordination_groups[]
metadata
```

---

## 3. Events

An event is an instantaneous or point-like semantic occurrence.

Examples:

- noise is heard;
- door slams;
- character notices object;
- dialogue begins;
- dialogue ends;
- contact begins;
- a reveal occurs.

Conceptual form:

```json
{
  "event_id": "event-noise",
  "frame": 78,
  "event_type": "sound_cue",
  "subject_entity_id": "guard",
  "source_entity_id": null,
  "target_entity_id": "door",
  "label": "unexplained noise"
}
```

### Event fields

Required:

- stable `event_id`;
- `frame`;
- open symbolic `event_type`.

Optional:

- subject actor/entity;
- source entity;
- target entity;
- semantic label.

Event IDs remain symbolic on disk.

---

## 4. Phases

A phase is a non-zero-duration behavioral intention.

Examples:

- walk;
- decelerate;
- react;
- acquire gaze;
- turn head;
- turn torso;
- turn body;
- hold;
- reach;
- crouch;
- speak;
- listen.

Conceptual form:

```json
{
  "phase_id": "body-turn-door",
  "actor_entity_id": "guard",
  "phase_type": "orientation_change",
  "intent": "turn cautiously toward the door",
  "start_frame": 92,
  "end_frame": 122,
  "priority": 80,
  "channels": ["root", "lower_body", "torso", "head"],
  "target_entity_id": "door",
  "coordination_group_id": "investigate-door"
}
```

### Required phase fields

- `phase_id`
- `actor_entity_id`
- open symbolic `phase_type`
- `start_frame`
- `end_frame`
- `priority`
- one or more affected `channels`

### Optional phase fields

- natural-language intent;
- target entity;
- coordination group;
- style;
- emotion;
- source event IDs;
- goal references.

---

## 5. Phase types

`phase_type` remains an open symbolic string.

Recommended initial vocabulary:

```text
locomotion
locomotion_transition
reaction
orientation_change
gaze_transition
hold
posture_transition
reach
interaction
gesture
dialogue
listen
idle
```

The open vocabulary avoids forcing all future cinematic behavior into a premature enum.

---

## 6. Body channels

Overlapping phases require explicit behavioral scope.

Frozen initial body-channel vocabulary:

- `root`
- `lower_body`
- `torso`
- `head`
- `gaze`
- `left_arm`
- `right_arm`
- `hands`
- `face`
- `voice`

A phase may affect multiple channels.

Example:

```text
walk:
    root + lower_body + torso

noise reaction:
    torso + head + gaze

body turn:
    root + lower_body + torso + head

dialogue:
    face + voice
```

This is why phases can overlap without being treated as independent sequential clips.

---

## 7. Priority

Priority is an integer in `[0, 100]`.

Priority is used only to resolve competing goals that affect the same channel/time window.

It does not mean one phase should erase another.

The future composer / model adapter may use priority as a feature.

Recommended semantics:

```text
0-29   background / style
30-59  ordinary behavior
60-79  important action
80-100 hard narrative-critical behavior
```

These bands are guidance, not separate types.

---

## 8. Coordination groups

A coordination group marks phases that belong to one semantic action sequence.

Example:

```text
group: investigate-door

    noise-reaction
    head-look-door
    torso-follow-door
    body-turn-door
    hold-door-gaze
    dialogue-who-is-there
```

Conceptual form:

```json
{
  "coordination_group_id": "investigate-door",
  "label": "react and orient toward suspicious door",
  "member_phase_ids": [
    "noise-reaction",
    "head-look-door",
    "body-turn-door",
    "hold-door"
  ]
}
```

The group does not prescribe a neural architecture.

It preserves semantic composition structure for training and evaluation.

---

## 9. Goal references

A phase may refer to one or more explicit goals.

Frozen v0.1 goal categories:

- `root_position`
- `root_path`
- `root_velocity`
- `body_facing`
- `gaze_target`
- `support_contact`
- `target_distance`
- `posture`
- `hold`

The concrete goal data lives in the choreography `constraints` collection.

This prevents phase records from becoming large unstructured parameter bags.

---

## 10. Constraints

A choreography constraint describes a desired property over a temporal window.

Conceptual base:

```json
{
  "constraint_id": "face-door",
  "constraint_type": "body_facing",
  "actor_entity_id": "guard",
  "start_frame": 112,
  "end_frame": 168,
  "strength": "hard",
  "weight": 1.0,
  "target_entity_id": "door"
}
```

### Strength

Frozen values:

- `hard`
- `soft`

A hard constraint is expected to be enforced by model generation plus deterministic refinement if
necessary.

A soft constraint contributes to generation/scoring but may trade off against another goal.

---

## 11. Root-position goal

A root-position constraint may specify:

- exact canonical world point;
- target-relative offset;
- tolerance.

Example:

```json
{
  "constraint_type": "root_position",
  "actor_entity_id": "guard",
  "start_frame": 90,
  "end_frame": 92,
  "strength": "soft",
  "position_m": [0.2, 0.0, -1.8],
  "tolerance_m": 0.15
}
```

For model input, actor-relative conversion may be derived by the loader.

---

## 12. Root path

A root path is a sparse intent path, not a frame-perfect ground-truth trajectory.

Conceptual representation:

```json
{
  "constraint_type": "root_path",
  "actor_entity_id": "guard",
  "start_frame": 0,
  "end_frame": 92,
  "strength": "soft",
  "waypoints": [
    {"frame": 0, "position_m": [0.0, 0.0, 2.0]},
    {"frame": 60, "position_m": [0.0, 0.0, -0.8]},
    {"frame": 91, "position_m": [0.1, 0.0, -1.8]}
  ]
}
```

Sparse waypoints describe narrative/spatial intent.

The body target later contains the actual frame-level root trajectory.

This prevents target leakage.

---

## 13. Root velocity / stop goal

A stop must be represented explicitly.

Example:

```json
{
  "constraint_type": "root_velocity",
  "actor_entity_id": "guard",
  "start_frame": 88,
  "end_frame": 96,
  "strength": "hard",
  "target_speed_mps": 0.0,
  "tolerance_mps": 0.08
}
```

The preceding deceleration phase can overlap this window.

This is stronger than hoping the word "stop" in a motion prompt produces the correct root behavior.

---

## 14. Body-facing goal

A body-facing constraint may target:

- explicit world direction; or
- a scene entity / target point.

Preferred semantic form:

```json
{
  "constraint_type": "body_facing",
  "actor_entity_id": "guard",
  "start_frame": 116,
  "end_frame": 168,
  "strength": "hard",
  "target_entity_id": "door",
  "tolerance_degrees": 5.0
}
```

Scene Conditioning resolves the target into geometry.

The choreography does not duplicate target coordinates.

---

## 15. Gaze goal

A gaze constraint defines acquisition / maintenance intent.

Example:

```json
{
  "constraint_type": "gaze_target",
  "actor_entity_id": "guard",
  "start_frame": 90,
  "end_frame": 168,
  "strength": "hard",
  "target_entity_id": "door",
  "target_point_kind": "look",
  "tolerance_degrees": 3.0
}
```

This is intent-level conditioning.

The later Gaze Target Representation defines frame-level supervision such as head/gaze vectors.

---

## 16. Support-contact intent

Choreography may contain coarse contact requirements without leaking full frame-level contact labels.

Examples:

- maintain at least one support foot during a turn;
- plant left foot through a critical interval;
- both feet stable during final hold.

Conceptual form:

```json
{
  "constraint_type": "support_contact",
  "actor_entity_id": "guard",
  "start_frame": 98,
  "end_frame": 112,
  "strength": "hard",
  "contact_requirement": "at_least_one_foot"
}
```

Recommended initial requirements:

- `at_least_one_foot`
- `left_planted`
- `right_planted`
- `both_planted`
- `no_requirement`

The exact frame-level contact truth remains a later target.

---

## 17. Target-distance goal

Useful for approach / interaction behavior:

```json
{
  "constraint_type": "target_distance",
  "actor_entity_id": "guard",
  "target_entity_id": "door",
  "start_frame": 80,
  "end_frame": 92,
  "strength": "soft",
  "distance_m": 2.4,
  "tolerance_m": 0.3
}
```

This expresses spatial intent without hard-coding an engine position.

---

## 18. Posture goal

The v0.1 temporal representation supports symbolic posture goals:

```text
standing
crouching
kneeling
sitting
prone
custom
```

A custom exact pose is deliberately not part of v0.1 choreography.

Frame-level canonical pose targets belong to body supervision, not high-level choreography.

---

## 19. Hold goal

A hold constraint represents stability rather than exact frozen joints.

Example:

```json
{
  "constraint_type": "hold",
  "actor_entity_id": "guard",
  "start_frame": 122,
  "end_frame": 168,
  "strength": "soft",
  "scope": ["root", "lower_body"]
}
```

The model may still produce natural breathing, gaze, speech, or subtle upper-body motion.

---

## 20. Transition windows

A transition is not represented as a separate engine clip blend.

Instead, choreography can intentionally overlap source and destination phases.

Example:

```text
walk            0 ----- 82
decelerate             68 ----- 94
reaction               76 -- 92
head turn                   84 ----- 106
body turn                      94 -------- 122
hold                                       120 -------- 168
```

The overlap itself is the transition plan.

The body generator must learn continuous composition across these windows.

A deterministic refinement layer later verifies velocity, pose, and contact continuity.

---

## 21. Guard benchmark choreography

Illustrative—not hard-coded—guard choreography:

```text
0-82     locomotion / patrol walk
68-94    locomotion transition / decelerate
78       noise event
78-94    reaction
84-106   gaze transition toward door
88-112   head/torso orientation response
94-122   body orientation change toward door
120-168  cautious hold
132      dialogue-start event
132-158  dialogue
158      dialogue-end event
```

Important:

- these frame values are example annotations at the frozen 30-fps model timebase;
- dataset generation should vary them;
- the model must not memorize one fixed timing pattern.

---

## 22. Generalization requirement

The representation is intentionally action-agnostic.

The same structure can represent:

```text
walk → sit
run → stop → look
reach → grasp → lift
crouch → move → peek
approach → handshake
open door → enter room
draw weapon → aim
listen → react → flee
```

Generalization comes from reusable phases, goals, entities, and constraints—not from training one
hard-coded guard timeline.

---

## 23. Multi-actor support

v0.1 allows phases for multiple actors.

Each phase names its `actor_entity_id`.

A relationship/constraint may target another performer.

Example:

```text
actor:a approaches actor:b
actor:a extends right arm
actor:b extends right arm
both enter handshake coordination group
```

The first trainable baseline remains single-actor.

Multi-actor support is present in the representation so the contract does not need an immediate
breaking redesign.

---

## 24. Narrative/CIR provenance

A choreography record may retain metadata references to source CIR:

- source beat ID;
- source performance cue ID;
- source motion phase ID;
- source dialogue cue ID.

These are metadata/provenance.

The body model should consume the canonical choreography semantics, not depend on raw CIR object
layout.

The future Temporal Director may consume CIR directly.

---

## 25. No engine concepts

The following are forbidden from model-visible choreography:

- AnimationClip;
- Animator state;
- Timeline track;
- PlayableDirector;
- Level Sequence;
- Sequencer track;
- engine frame section object;
- Unity/Unreal asset path;
- native bone name.

Choreography describes cinematic behavior, not realization.

---

## 26. Validation invariants

A valid choreography record must satisfy:

1. `duration_frames > 0`;
2. every event frame is inside the sequence;
3. every phase has `0 <= start_frame < end_frame <= duration_frames`;
4. every constraint window is inside the sequence;
5. every phase actor exists in Scene Conditioning;
6. every target entity exists in Scene Conditioning;
7. every coordination-group member phase exists;
8. phase IDs, event IDs, constraint IDs, and coordination-group IDs are unique in their namespace;
9. phase channels are non-empty;
10. hard constraints may overlap, but contradictory hard constraints on the same property/window must be rejected or explicitly resolved before body generation.

---

## 27. Contradiction examples

Invalid unresolved hard constraints:

```text
same actor
same frames
body_facing -> door A
body_facing -> door B
both hard
```

Valid overlapping constraints:

```text
body_facing -> door
gaze -> door
root_velocity -> zero
support_contact -> both planted
```

Valid layered phases:

```text
hold lower body
+ dialogue face/voice
+ gaze target
```

The validation layer should catch impossible plans before model inference.

---

## 28. Relationship to frame-level targets

Choreography intentionally avoids exact future joint rotations.

Example distinction:

```text
CHOREOGRAPHY CONDITION:
    face Door_01 by frame 122

BODY TARGET:
    exact root orientation and 22 joint rotations
    for every frame
```

Similarly:

```text
CHOREOGRAPHY CONDITION:
    maintain at least one support foot

CONTACT TARGET:
    exact left/right contact label per frame
```

This separation is mandatory to prevent accidental label leakage.

---

## 29. First Temporal Director baseline

The first Temporal Director does not need to solve every cinematic action.

Initial supervised task:

```text
INPUT:
    simplified narrative/CIR
    performer
    target entity
    sequence duration

OUTPUT:
    phase windows
    noise/reaction event
    orientation-change window
    hold window
    body-facing constraint
    gaze constraint
    stop/root-velocity constraint
```

This may initially be deterministic or rule-assisted.

The first learned body generator can consume ground-truth/synthetic choreography before a learned
Temporal Director exists.

This decouples body-model research from director-model maturity.

---

## 30. Dataset randomization

For the guard family, vary:

- walking duration;
- event frame;
- reaction latency;
- deceleration duration;
- head-turn lead;
- torso/body follow delay;
- target angle;
- turn duration;
- support-foot intent;
- dialogue timing;
- hold duration.

Test splits must hold out combinations, not merely random near-duplicates.

---

## 31. Acceptance tests for this representation

Required schema/planner tests:

1. overlapping phases serialize deterministically;
2. half-open windows are enforced;
3. out-of-range event/phase/constraint frames are rejected;
4. unknown actor/target references are rejected;
5. contradictory hard facing constraints are detected;
6. guard example supports reaction + gaze + body turn overlap;
7. support-contact intent remains distinct from frame-level contact truth;
8. root sparse path remains distinct from body target root trajectory;
9. no engine-specific track/asset concept appears in model-visible fields;
10. same semantic plan can reference different target locations through Scene Conditioning without changing phase meaning.

---

## 32. What is frozen now

Frozen in v0.1:

- event abstraction;
- overlapping phase abstraction;
- symbolic open phase type;
- body-channel scope;
- phase priority;
- coordination groups;
- hard/soft constraints;
- root position/path/velocity goal categories;
- body-facing goal;
- gaze-target goal;
- coarse support-contact intent;
- target-distance goal;
- symbolic posture goal;
- hold goal;
- 30-fps half-open temporal semantics inherited from canonical contract;
- explicit distinction between choreography intent and frame-level target truth.

---

## 33. Intentionally not frozen

Do not freeze yet:

- neural Temporal Director architecture;
- exact phase vocabulary/tokenizer;
- exact phase-priority generation algorithm;
- whether phases are generated autoregressively or in parallel;
- exact loss functions;
- learned versus deterministic contradiction resolver;
- multi-actor neural coordination architecture;
- exact dialogue/phoneme representation.

---

## 34. Machine-readable companion

Frozen invariants are mirrored in:

`docs/model/contracts/choreography-temporal-representation-v0.1.json`

Future Pydantic implementation must preserve this contract.

---

## 35. Exact next development step

With Choreography / Temporal Representation v0.1 frozen, define and freeze:

**Canonical Body Target Representation v0.1**

It must specify the exact frame-level body supervision to be predicted:

- explicit root position;
- explicit root orientation;
- canonical joint rotations;
- optional auxiliary joint positions;
- velocities / derived features;
- continuity semantics;
- masks;
- conversion to the runtime Generated Performance Package.

Contact and gaze targets remain the following dedicated representation step.
