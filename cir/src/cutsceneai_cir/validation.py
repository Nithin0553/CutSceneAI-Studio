from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import Axis, Project, Scene, ShotPurpose


@dataclass(frozen=True, slots=True)
class CIRValidationIssue:
    """One domain-level CIR validation failure."""

    code: str
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


class CIRValidationError(ValueError):
    """Raised when a typed CIR project violates domain invariants."""

    def __init__(self, issues: list[CIRValidationIssue]) -> None:
        self.issues = tuple(issues)
        summary = "; ".join(
            f"{issue.code} at {issue.path}: {issue.message}" for issue in self.issues
        )
        super().__init__(summary)


_TIMELINE_EPSILON = 1e-9


def _add_duplicate_id_issues(
    entries: list[tuple[str, str]], issues: list[CIRValidationIssue]
) -> None:
    first_path_by_id: dict[str, str] = {}
    for path, item_id in entries:
        first_path = first_path_by_id.get(item_id)
        if first_path is None:
            first_path_by_id[item_id] = path
            continue
        issues.append(
            CIRValidationIssue(
                code="duplicate_id",
                path=path,
                message=f"ID '{item_id}' is already used at {first_path}.",
            )
        )


def _add_timeline_issues(
    *, scene: Scene, scene_index: int, issues: list[CIRValidationIssue]
) -> None:
    timeline_groups = (("beats", scene.beats), ("shots", scene.shots))
    for group_name, items in timeline_groups:
        intervals: list[tuple[float, float, str, str]] = []
        for item_index, item in enumerate(items):
            item_path = f"scenes[{scene_index}].{group_name}[{item_index}]"
            end_seconds = item.start_seconds + item.duration_seconds
            if end_seconds > scene.duration_seconds + _TIMELINE_EPSILON:
                issues.append(
                    CIRValidationIssue(
                        code=f"{group_name[:-1]}_out_of_bounds",
                        path=f"{item_path}.duration_seconds",
                        message=(
                            f"Timeline item '{item.id}' ends at {end_seconds:g}s, beyond "
                            f"scene duration {scene.duration_seconds:g}s."
                        ),
                    )
                )
            intervals.append((item.start_seconds, end_seconds, item.id, item_path))

        active_end = -1.0
        active_id = ""
        active_path = ""
        for start_seconds, end_seconds, item_id, item_path in sorted(intervals):
            if start_seconds < active_end - _TIMELINE_EPSILON:
                issues.append(
                    CIRValidationIssue(
                        code=f"{group_name[:-1]}_overlap",
                        path=f"{item_path}.start_seconds",
                        message=(
                            f"Timeline item '{item_id}' overlaps '{active_id}' at {active_path}."
                        ),
                    )
                )
            if end_seconds > active_end:
                active_end = end_seconds
                active_id = item_id
                active_path = item_path


def _axis_dimension(axis: Axis) -> str:
    return axis.value.removeprefix("-")


def validate_project_model(project: Project) -> None:
    """Validate references, timelines, and cinematic requirements."""

    issues: list[CIRValidationIssue] = []

    if _axis_dimension(project.settings.up_axis) == _axis_dimension(
        project.settings.forward_axis
    ):
        issues.append(
            CIRValidationIssue(
                code="coordinate_axes_collinear",
                path="settings.forward_axis",
                message="Forward axis must not be collinear with the up axis.",
            )
        )

    id_entries: list[tuple[str, str]] = [("id", project.id)]
    id_entries.extend(
        (f"characters[{index}].id", character.id)
        for index, character in enumerate(project.characters)
    )
    id_entries.extend(
        (f"environment[{index}].id", item.id)
        for index, item in enumerate(project.environment)
    )
    for scene_index, scene in enumerate(project.scenes):
        id_entries.append((f"scenes[{scene_index}].id", scene.id))
        id_entries.extend(
            (f"scenes[{scene_index}].beats[{index}].id", beat.id)
            for index, beat in enumerate(scene.beats)
        )
        id_entries.extend(
            (f"scenes[{scene_index}].shots[{index}].id", shot.id)
            for index, shot in enumerate(scene.shots)
        )
    _add_duplicate_id_issues(id_entries, issues)

    character_ids = {character.id for character in project.characters}
    environment_ids = {item.id for item in project.environment}
    entity_ids = character_ids | environment_ids

    for scene_index, scene in enumerate(project.scenes):
        beat_ids = {beat.id for beat in scene.beats}

        for beat_index, beat in enumerate(scene.beats):
            beat_path = f"scenes[{scene_index}].beats[{beat_index}]"
            for performance_index, performance in enumerate(beat.performances):
                performance_path = f"{beat_path}.performances[{performance_index}]"
                if performance.character_id not in character_ids:
                    issues.append(
                        CIRValidationIssue(
                            code="unknown_character_reference",
                            path=f"{performance_path}.character_id",
                            message=(
                                f"Character '{performance.character_id}' is not declared in project."
                            ),
                        )
                    )
                if performance.look_at_id and performance.look_at_id not in entity_ids:
                    issues.append(
                        CIRValidationIssue(
                            code="unknown_entity_reference",
                            path=f"{performance_path}.look_at_id",
                            message=f"Entity '{performance.look_at_id}' is not declared in project.",
                        )
                    )

            for focus_index, focus_id in enumerate(beat.environment_focus_ids):
                if focus_id not in environment_ids:
                    issues.append(
                        CIRValidationIssue(
                            code="unknown_environment_reference",
                            path=f"{beat_path}.environment_focus_ids[{focus_index}]",
                            message=f"Environment object '{focus_id}' is not declared in project.",
                        )
                    )

        for shot_index, shot in enumerate(scene.shots):
            shot_path = f"scenes[{scene_index}].shots[{shot_index}]"
            for beat_ref_index, beat_id in enumerate(shot.beat_ids):
                if beat_id not in beat_ids:
                    issues.append(
                        CIRValidationIssue(
                            code="unknown_beat_reference",
                            path=f"{shot_path}.beat_ids[{beat_ref_index}]",
                            message=f"Beat '{beat_id}' is not declared in this scene.",
                        )
                    )
            for subject_index, subject_id in enumerate(shot.subject_ids):
                if subject_id not in entity_ids:
                    issues.append(
                        CIRValidationIssue(
                            code="unknown_entity_reference",
                            path=f"{shot_path}.subject_ids[{subject_index}]",
                            message=f"Entity '{subject_id}' is not declared in project.",
                        )
                    )
            for target_index, target_id in enumerate(shot.camera.target_ids):
                if target_id not in entity_ids:
                    issues.append(
                        CIRValidationIssue(
                            code="unknown_entity_reference",
                            path=f"{shot_path}.camera.target_ids[{target_index}]",
                            message=f"Entity '{target_id}' is not declared in project.",
                        )
                    )

        if not any(shot.purpose is ShotPurpose.ESTABLISHING for shot in scene.shots):
            issues.append(
                CIRValidationIssue(
                    code="missing_establishing_shot",
                    path=f"scenes[{scene_index}].shots",
                    message="Every scene must contain at least one establishing shot.",
                )
            )

        focused_environment_ids = {
            focus_id
            for beat in scene.beats
            for focus_id in beat.environment_focus_ids
            if focus_id in environment_ids
        }
        detail_subject_ids = {
            subject_id
            for shot in scene.shots
            if shot.purpose is ShotPurpose.ENVIRONMENT_DETAIL
            for subject_id in shot.subject_ids
        }
        for focus_id in sorted(focused_environment_ids - detail_subject_ids):
            issues.append(
                CIRValidationIssue(
                    code="missing_environment_detail_shot",
                    path=f"scenes[{scene_index}].shots",
                    message=(
                        f"Focused environment object '{focus_id}' requires an "
                        "environment-detail shot."
                    ),
                )
            )

        _add_timeline_issues(scene=scene, scene_index=scene_index, issues=issues)

    if issues:
        raise CIRValidationError(issues)


def validate_project(payload: dict[str, Any]) -> Project:
    """Validate a CIR payload and return a structurally and semantically valid project."""

    project = Project.model_validate(payload)
    validate_project_model(project)
    return project
