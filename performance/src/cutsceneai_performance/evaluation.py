from __future__ import annotations

from enum import Enum
import hashlib
import json
from typing import Literal, Self

from pydantic import Field, model_validator

from .models import PerformanceModel, SemanticId, Sha256Digest


class EvaluationStage(str, Enum):
    CANONICAL = "canonical"
    ENGINE = "engine"
    RENDER = "render"
    SEMANTIC = "semantic"


class IssueSeverity(str, Enum):
    WARNING = "warning"
    ERROR = "error"


class RepairActionKind(str, Enum):
    NORMALIZE_SKELETON = "normalize_skeleton"
    RECOMPOSE_ROOT = "recompose_root"
    SMOOTH_TRANSITION = "smooth_transition"
    STABILIZE_CONTACT = "stabilize_contact"
    REGENERATE_SEGMENT = "regenerate_segment"
    RETARGET_CHAIN = "retarget_chain"
    EDIT_POSE = "edit_pose"
    EDIT_TRAJECTORY = "edit_trajectory"
    EDIT_CAMERA = "edit_camera"
    EDIT_TIMING = "edit_timing"
    EDIT_DIALOGUE = "edit_dialogue"
    ENGINE_ANIMATION_EDIT = "engine_animation_edit"


class PerformanceIssue(PerformanceModel):
    issue_id: str = Field(min_length=1)
    stage: EvaluationStage
    domain: Literal[
        "motion",
        "retargeting",
        "contact",
        "collision",
        "semantic",
        "camera",
        "timing",
        "dialogue",
        "render",
    ]
    code: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    severity: IssueSeverity
    message: str = Field(min_length=1)
    semantic_id: SemanticId | None = None
    actor_binding_id: SemanticId | None = None
    component: str | None = Field(default=None, min_length=1)
    start_frame: int | None = Field(default=None, ge=0)
    end_frame: int | None = Field(default=None, ge=0)
    metrics: dict[str, float] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)
    suggested_repairs: list[RepairActionKind] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_frame_window(self) -> Self:
        if (
            self.start_frame is not None
            and self.end_frame is not None
            and self.end_frame <= self.start_frame
        ):
            raise ValueError("end_frame must be greater than start_frame.")
        return self


class EvaluationReport(PerformanceModel):
    report_version: Literal["0.1.0"] = "0.1.0"
    report_id: str = Field(min_length=1)
    performance_run_id: str = Field(min_length=1)
    source_bundle_sha256: Sha256Digest
    iteration: int = Field(ge=0)
    stages_evaluated: list[EvaluationStage] = Field(min_length=1)
    issues: list[PerformanceIssue] = Field(default_factory=list)
    accepted: bool

    @model_validator(mode="after")
    def validate_acceptance(self) -> Self:
        blocking = any(issue.severity is IssueSeverity.ERROR for issue in self.issues)
        if self.accepted == blocking:
            raise ValueError(
                "accepted must be true exactly when the report has no error-severity issues."
            )
        if len(self.stages_evaluated) != len(set(self.stages_evaluated)):
            raise ValueError("stages_evaluated must be unique.")
        return self


class RepairAction(PerformanceModel):
    action_id: str = Field(min_length=1)
    kind: RepairActionKind
    issue_ids: list[str] = Field(min_length=1)
    semantic_id: SemanticId | None = None
    actor_binding_id: SemanticId | None = None
    component: str | None = Field(default=None, min_length=1)
    start_frame: int | None = Field(default=None, ge=0)
    end_frame: int | None = Field(default=None, ge=0)
    instruction: str = Field(min_length=1)
    requires_fresh_inference: bool = False
    requires_engine: bool = False
    engine_agnostic: bool = True

    @model_validator(mode="after")
    def validate_frame_window(self) -> Self:
        if (
            self.start_frame is not None
            and self.end_frame is not None
            and self.end_frame <= self.start_frame
        ):
            raise ValueError("end_frame must be greater than start_frame.")
        if self.requires_engine and self.engine_agnostic:
            raise ValueError(
                "Engine-required repair actions cannot be marked engine_agnostic."
            )
        return self


class RepairPlan(PerformanceModel):
    plan_version: Literal["0.1.0"] = "0.1.0"
    source_report_id: str = Field(min_length=1)
    performance_run_id: str = Field(min_length=1)
    iteration: int = Field(ge=0)
    actions: list[RepairAction] = Field(default_factory=list)
    requires_fresh_inference: bool
    requires_engine: bool


class ClosedLoopPolicy(PerformanceModel):
    policy_version: Literal["0.1.0"] = "0.1.0"
    max_iterations: int = Field(default=6, ge=1, le=20)
    stop_when_accepted: bool = True
    stop_when_no_progress: bool = True
    max_fresh_inference_actions_per_iteration: int = Field(default=1, ge=0, le=10)


_REPAIR_RULES: dict[str, tuple[RepairActionKind, str, bool, bool, bool]] = {
    "canonical_geometry_missing": (
        RepairActionKind.REGENERATE_SEGMENT,
        "Regenerate only the affected motion segment with the required canonical body representation.",
        True,
        False,
        True,
    ),
    "bone_length_instability": (
        RepairActionKind.NORMALIZE_SKELETON,
        "Normalize canonical skeleton geometry without changing semantic timing.",
        False,
        False,
        True,
    ),
    "stationary_phase_root_travel": (
        RepairActionKind.RECOMPOSE_ROOT,
        "Constrain the affected phase root trajectory to the stationary semantic intent.",
        False,
        False,
        True,
    ),
    "large_phase_boundary_speed_jump": (
        RepairActionKind.SMOOTH_TRANSITION,
        "Recompose the phase boundary to preserve pose and velocity continuity.",
        False,
        False,
        True,
    ),
    "possible_foot_slide": (
        RepairActionKind.STABILIZE_CONTACT,
        "Preserve detected foot contact while correcting root and limb motion.",
        False,
        False,
        True,
    ),
    "semantic_action_missing": (
        RepairActionKind.REGENERATE_SEGMENT,
        "Regenerate only the failed semantic motion segment and preserve unaffected tracks.",
        True,
        False,
        True,
    ),
    "target_facing_error": (
        RepairActionKind.EDIT_TRAJECTORY,
        "Correct the actor root/heading trajectory toward the bound semantic target.",
        False,
        False,
        True,
    ),
    "retarget_deformation": (
        RepairActionKind.RETARGET_CHAIN,
        "Repair the affected target-rig chain using the canonical pose and target rig profile.",
        False,
        True,
        False,
    ),
    "pose_artifact": (
        RepairActionKind.EDIT_POSE,
        "Edit only the affected pose window while preserving surrounding motion.",
        False,
        True,
        False,
    ),
    "camera_framing_error": (
        RepairActionKind.EDIT_CAMERA,
        "Adjust camera transforms/lens within the affected shot while preserving scene semantics.",
        False,
        True,
        False,
    ),
    "timing_error": (
        RepairActionKind.EDIT_TIMING,
        "Adjust timing for the affected cue without regenerating unrelated performance.",
        False,
        False,
        True,
    ),
    "dialogue_sync_error": (
        RepairActionKind.EDIT_DIALOGUE,
        "Repair dialogue placement or lip-sync timing for the affected cue.",
        False,
        True,
        False,
    ),
}


def stable_issue_id(
    *,
    stage: EvaluationStage,
    code: str,
    semantic_id: str | None = None,
    actor_binding_id: str | None = None,
    component: str | None = None,
    start_frame: int | None = None,
    end_frame: int | None = None,
) -> str:
    payload = {
        "stage": stage.value,
        "code": code,
        "semantic_id": semantic_id,
        "actor_binding_id": actor_binding_id,
        "component": component,
        "start_frame": start_frame,
        "end_frame": end_frame,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]
    return f"issue-{digest}"


def _action_id(issue: PerformanceIssue, kind: RepairActionKind) -> str:
    digest = hashlib.sha256(
        f"{issue.issue_id}:{kind.value}".encode("utf-8")
    ).hexdigest()[:16]
    return f"repair-{digest}"


def plan_repairs(report: EvaluationReport) -> RepairPlan:
    """Create a deterministic, minimal repair plan from one evaluation report.

    The planner intentionally selects one targeted repair per blocking issue and
    never broadens the scope to unaffected tracks. Expensive fresh inference is
    requested only for issue classes that cannot be repaired deterministically.
    """

    actions: list[RepairAction] = []
    for issue in sorted(report.issues, key=lambda item: item.issue_id):
        if issue.severity is not IssueSeverity.ERROR:
            continue

        rule = _REPAIR_RULES.get(issue.code)
        if rule is None:
            kind = RepairActionKind.ENGINE_ANIMATION_EDIT
            instruction = (
                "Inspect and repair the affected engine-native animation window, "
                "then re-evaluate the same issue."
            )
            requires_fresh_inference = False
            requires_engine = True
            engine_agnostic = False
        else:
            (
                kind,
                instruction,
                requires_fresh_inference,
                requires_engine,
                engine_agnostic,
            ) = rule

        actions.append(
            RepairAction(
                action_id=_action_id(issue, kind),
                kind=kind,
                issue_ids=[issue.issue_id],
                semantic_id=issue.semantic_id,
                actor_binding_id=issue.actor_binding_id,
                component=issue.component,
                start_frame=issue.start_frame,
                end_frame=issue.end_frame,
                instruction=instruction,
                requires_fresh_inference=requires_fresh_inference,
                requires_engine=requires_engine,
                engine_agnostic=engine_agnostic,
            )
        )

    return RepairPlan(
        source_report_id=report.report_id,
        performance_run_id=report.performance_run_id,
        iteration=report.iteration,
        actions=actions,
        requires_fresh_inference=any(
            action.requires_fresh_inference for action in actions
        ),
        requires_engine=any(action.requires_engine for action in actions),
    )
