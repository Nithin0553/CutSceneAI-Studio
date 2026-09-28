# CutSceneAI Evaluation & Acceptance Metrics v0.1

Status: Frozen for first benchmark generation and baseline training.

## Purpose

This contract defines the metrics used to decide whether canonical performance and engine realization are actually correct. Metric formulas are fixed here; benchmark thresholds are stored in separate versioned profiles.

## Canonical semantic metrics

- hard_constraint_satisfaction_rate
- event_timing_absolute_error_frames
- phase_temporal_iou

## Canonical body metrics

- root_position_error_m: mean, RMSE, max, endpoint
- root_orientation_geodesic_error_deg: mean, max, final
- target_facing_error_deg during active facing constraints
- root_path_deviation_m from sparse choreography intent
- stop_speed_mps, stop_timing_error_frames, hold_drift_m
- per_joint_rotation_error_deg when reference motion exists
- joint_position_error_m when auxiliary positions exist
- bone_length_error_m
- root acceleration and jerk
- joint angular-velocity and angular-acceleration discontinuity

Target-facing error compares actor horizontal forward with the horizontal actor-to-target direction. Exact-reference motion metrics are not used to imply that only one valid performance exists; constraint metrics remain primary for multi-solution tasks.

## Contact and grounding metrics

- left/right contact precision, recall, F1, accuracy
- planted_foot_sliding_distance_m
- max_planted_foot_drift_m
- ground_penetration_m
- ground_clearance_error_m while planted

## Gaze metrics

- head_target_error_deg
- gaze_target_error_deg when gaze direction is supervised
- target_acquisition_latency_frames
- gaze_maintenance_ratio

## Camera metrics

- subject/target visible fraction
- framing center/size error
- collision_rate and minimum_clearance_m
- within-shot translational/angular acceleration and jerk
- focal_length_change_rate
- optional continuity-rule annotations where available

## Engine fidelity metrics

After engine readback is converted back to canonical space, report canonical-to-engine root position/orientation error, joint/end-effector error where available, duration/event/dialogue timing error, and camera transform/lens error.

## Cross-engine parity

Report Unity-vs-Unreal root position, root orientation, joint/end-effector, event timing, and camera differences after both readbacks are canonicalized. Cross-engine agreement does not replace canonical correctness.

## Acceptance states

Every benchmark reports independent states:

- schema_valid
- canonical_semantic_pass
- canonical_body_pass
- contact_grounding_pass
- gaze_pass
- camera_pass
- unity_fidelity_pass
- unreal_fidelity_pass
- cross_engine_parity_pass

## Threshold profiles

Thresholds are versioned separately from metric definitions. Initial guard-scene candidate thresholds remain provisional until experiments calibrate them: final body-facing error 5 degrees or less, exact gaze error 3 degrees or less when supervised, planted-foot drift 0.02 m or less, floor penetration 0.01 m or less, required camera visibility at least 0.95, and all hard choreography constraints satisfied.

## Reproducibility

Every evaluation run records metric implementation version, benchmark-profile version, model/checkpoint hash, sample IDs, canonical performance hash, and engine realization hashes when applicable. Human visual review remains required for cinematic acceptance and must be linked to metric results.

## Exact next development step

Build Guard Turn Dataset Generator v0.1. A small deterministic dataset must pass dataset and evaluation validation before the first learned baseline is trained.
