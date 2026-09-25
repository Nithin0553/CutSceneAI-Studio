# CutSceneAI Closed-Loop Studio Architecture

## Goal

CutSceneAI is a cross-engine autonomous cutscene studio that generates, realizes,
evaluates, and repairs semantic 3D character performances from natural-language
direction.

The system must not depend on an engine-specific animation library or on a single
motion provider. Existing clips, generative models, procedural animation, IK,
Control Rig/Animation Rigging, and direct keyframe edits are tools available to the
Director, not the core research contribution.

## Core loop

1. Intent -> CIR.
2. CIR -> canonical performance plan.
3. Generate or construct canonical performance.
4. Evaluate canonical performance before any engine sees it.
5. Repair canonical failures locally.
6. Realize the accepted canonical performance through a target-rig profile.
7. Evaluate engine-native motion and scene behavior.
8. Repair rig/engine-specific failures locally.
9. Render the cutscene.
10. Evaluate semantic and cinematic output.
11. Repair only the failed region/layer.
12. Repeat until accepted or the closed-loop policy stops.

## Non-negotiable gates

### Gate A: canonical motion

A body track cannot proceed to retargeting if the canonical evaluator reports a
blocking error. Canonical evaluation covers at least:

- skeleton-length stability,
- root trajectory,
- phase-boundary continuity,
- semantic motion class,
- contact consistency,
- target-facing constraints,
- motion completeness.

### Gate B: target-rig realization

A realized body track cannot proceed to cinematic acceptance if engine evidence
reports blocking deformation or constraint errors. This stage covers at least:

- chain geometry,
- joint limits,
- bend planes,
- twist distribution,
- feet/hands,
- ground and self contact,
- interpenetration,
- root/pose coherence.

### Gate C: rendered semantics

The final cutscene must be evaluated from rendered evidence for:

- requested actions and ordering,
- actor/target relationships,
- dialogue timing,
- camera framing and visibility,
- collisions and scene mistakes,
- overall visual continuity.

## Repair policy

Repairs are scoped to the smallest failing region.

Preferred order:

1. deterministic canonical repair,
2. deterministic target-rig repair,
3. engine-native pose/trajectory/keyframe repair,
4. segment-only fresh generation,
5. broader regeneration only when local repair cannot satisfy semantics.

Fresh model inference is therefore not the default response to a visual failure.

## Canonical motion representation

XYZ joints are useful for geometry checks and end-effector constraints, but they
are not a sufficient final animation representation because positions do not
uniquely preserve bone twist.

CutSceneAI's richer canonical body representation should preserve, when the source
provides it:

- root orientation/translation or velocity,
- local joint rotations,
- joint positions,
- joint velocities,
- explicit foot/contact state,
- semantic events and constraints.

For HumanML3D-family providers this means preserving the native 263-dimensional
representation components instead of discarding rotations, velocities, and contact
channels after recovering XYZ.

## Engine adapters

Unity and Unreal implement the same high-level repair operations through different
native mechanisms.

Examples of universal operations:

- edit_pose
- edit_trajectory
- stabilize_contact
- retarget_chain
- look_at_target
- set_keyframe
- adjust_timing
- edit_camera
- render_preview
- collect_engine_evidence

The canonical performance and evaluation result remain engine-independent.

## Research distinction

The research target is not merely LLM-driven engine automation. The contribution is
the combination of:

- semantic performance representation,
- generated/constructed motion not limited to pre-authored clips,
- rich motion/contact preservation,
- cross-engine target-rig realization,
- layered quantitative and visual evaluation,
- autonomous localized repair.

The same accepted canonical performance should be realizable and comparable in both
Unity and Unreal.
