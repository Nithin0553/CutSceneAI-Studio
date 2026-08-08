from __future__ import annotations

from collections.abc import Callable, Sequence
from itertools import combinations
from typing import TypeVar

from cutsceneai_cir import Project

from .compiler import compile_semantics
from .models import (
    EngineName,
    EngineTimelineReadback,
    IssueSeverity,
    ParityIssue,
    ParityReport,
    ReadbackSummary,
    SemanticCameraCut,
    SemanticDialogueCue,
    SemanticEntity,
    SemanticPerformanceCue,
    SemanticScene,
    TimelineSemantics,
)


T = TypeVar("T")


def _stringify(value: object) -> str:
    if isinstance(value, list):
        return "[" + ",".join(str(item) for item in value) + "]"
    return str(value)


def _issue(
    issues: list[ParityIssue],
    *,
    scope: str,
    code: str,
    message: str,
    semantic_id: str | None = None,
    field: str | None = None,
    expected: object | None = None,
    actual: object | None = None,
    delta_frames: int | None = None,
    severity: IssueSeverity = IssueSeverity.ERROR,
) -> None:
    issues.append(
        ParityIssue(
            severity=severity,
            scope=scope,
            code=code,
            semantic_id=semantic_id,
            field=field,
            expected=None if expected is None else _stringify(expected),
            actual=None if actual is None else _stringify(actual),
            delta_frames=delta_frames,
            message=message,
        )
    )


def _index_unique(
    values: Sequence[T],
    key: Callable[[T], str],
    *,
    scope: str,
    collection: str,
    issues: list[ParityIssue],
) -> dict[str, T]:
    indexed: dict[str, T] = {}
    for value in values:
        item_id = key(value)
        if item_id in indexed:
            _issue(
                issues,
                scope=scope,
                code="duplicate_semantic_id",
                semantic_id=item_id,
                field=collection,
                message=f"{collection} contains duplicate semantic ID '{item_id}'.",
            )
            continue
        indexed[item_id] = value
    return indexed


def _compare_value(
    issues: list[ParityIssue],
    *,
    scope: str,
    semantic_id: str,
    field: str,
    expected: object,
    actual: object,
) -> None:
    if expected != actual:
        _issue(
            issues,
            scope=scope,
            code="semantic_value_mismatch",
            semantic_id=semantic_id,
            field=field,
            expected=expected,
            actual=actual,
            message=f"Semantic field '{field}' differs for '{semantic_id}'.",
        )


def _compare_frame(
    issues: list[ParityIssue],
    *,
    scope: str,
    semantic_id: str,
    field: str,
    expected: int,
    actual: int,
    tolerance_frames: int,
) -> None:
    delta = abs(actual - expected)
    if delta > tolerance_frames:
        _issue(
            issues,
            scope=scope,
            code="frame_mismatch",
            semantic_id=semantic_id,
            field=field,
            expected=expected,
            actual=actual,
            delta_frames=delta,
            message=(
                f"Frame field '{field}' differs by {delta} frames for '{semantic_id}', "
                f"exceeding tolerance {tolerance_frames}."
            ),
        )


def _compare_collection(
    expected: Sequence[T],
    actual: Sequence[T],
    *,
    key: Callable[[T], str],
    collection: str,
    scope: str,
    issues: list[ParityIssue],
) -> tuple[dict[str, T], dict[str, T]]:
    expected_by_id = _index_unique(
        expected,
        key,
        scope=scope,
        collection=f"expected.{collection}",
        issues=issues,
    )
    actual_by_id = _index_unique(
        actual,
        key,
        scope=scope,
        collection=f"actual.{collection}",
        issues=issues,
    )
    for semantic_id in sorted(expected_by_id.keys() - actual_by_id.keys()):
        _issue(
            issues,
            scope=scope,
            code="missing_semantic_item",
            semantic_id=semantic_id,
            field=collection,
            message=f"Actual timeline is missing {collection} item '{semantic_id}'.",
        )
    for semantic_id in sorted(actual_by_id.keys() - expected_by_id.keys()):
        _issue(
            issues,
            scope=scope,
            code="unexpected_semantic_item",
            semantic_id=semantic_id,
            field=collection,
            message=f"Actual timeline contains unexpected {collection} item '{semantic_id}'.",
        )
    return expected_by_id, actual_by_id


def _compare_entities(
    expected: Sequence[SemanticEntity],
    actual: Sequence[SemanticEntity],
    *,
    scope: str,
    issues: list[ParityIssue],
) -> None:
    expected_by_id, actual_by_id = _compare_collection(
        expected,
        actual,
        key=lambda item: item.binding_id,
        collection="entities",
        scope=scope,
        issues=issues,
    )
    for semantic_id in sorted(expected_by_id.keys() & actual_by_id.keys()):
        left = expected_by_id[semantic_id]
        right = actual_by_id[semantic_id]
        _compare_value(
            issues,
            scope=scope,
            semantic_id=semantic_id,
            field="source_entity_id",
            expected=left.source_entity_id,
            actual=right.source_entity_id,
        )
        _compare_value(
            issues,
            scope=scope,
            semantic_id=semantic_id,
            field="kind",
            expected=left.kind.value,
            actual=right.kind.value,
        )


def _compare_performances(
    expected: Sequence[SemanticPerformanceCue],
    actual: Sequence[SemanticPerformanceCue],
    *,
    scope: str,
    tolerance_frames: int,
    issues: list[ParityIssue],
) -> None:
    expected_by_id, actual_by_id = _compare_collection(
        expected,
        actual,
        key=lambda item: item.cue_id,
        collection="performance_cues",
        scope=scope,
        issues=issues,
    )
    for semantic_id in sorted(expected_by_id.keys() & actual_by_id.keys()):
        left = expected_by_id[semantic_id]
        right = actual_by_id[semantic_id]
        for field in (
            "source_beat_id",
            "actor_binding_id",
            "motion_intent_sha256",
            "look_at_binding_id",
        ):
            _compare_value(
                issues,
                scope=scope,
                semantic_id=semantic_id,
                field=field,
                expected=getattr(left, field),
                actual=getattr(right, field),
            )
        for field in ("start_frame", "end_frame"):
            _compare_frame(
                issues,
                scope=scope,
                semantic_id=semantic_id,
                field=field,
                expected=getattr(left, field),
                actual=getattr(right, field),
                tolerance_frames=tolerance_frames,
            )


def _compare_dialogues(
    expected: Sequence[SemanticDialogueCue],
    actual: Sequence[SemanticDialogueCue],
    *,
    scope: str,
    tolerance_frames: int,
    issues: list[ParityIssue],
) -> None:
    expected_by_id, actual_by_id = _compare_collection(
        expected,
        actual,
        key=lambda item: item.cue_id,
        collection="dialogue_cues",
        scope=scope,
        issues=issues,
    )
    for semantic_id in sorted(expected_by_id.keys() & actual_by_id.keys()):
        left = expected_by_id[semantic_id]
        right = actual_by_id[semantic_id]
        for field in (
            "source_beat_id",
            "actor_binding_id",
            "text_sha256",
            "language",
        ):
            _compare_value(
                issues,
                scope=scope,
                semantic_id=semantic_id,
                field=field,
                expected=getattr(left, field),
                actual=getattr(right, field),
            )
        for field in ("start_frame", "window_end_frame"):
            _compare_frame(
                issues,
                scope=scope,
                semantic_id=semantic_id,
                field=field,
                expected=getattr(left, field),
                actual=getattr(right, field),
                tolerance_frames=tolerance_frames,
            )


def _compare_cameras(
    expected: Sequence[SemanticCameraCut],
    actual: Sequence[SemanticCameraCut],
    *,
    scope: str,
    tolerance_frames: int,
    issues: list[ParityIssue],
) -> None:
    expected_by_id, actual_by_id = _compare_collection(
        expected,
        actual,
        key=lambda item: item.cut_id,
        collection="camera_cuts",
        scope=scope,
        issues=issues,
    )
    for semantic_id in sorted(expected_by_id.keys() & actual_by_id.keys()):
        left = expected_by_id[semantic_id]
        right = actual_by_id[semantic_id]
        for field in (
            "source_shot_id",
            "source_beat_ids",
            "purpose",
            "framing",
            "angle",
            "movement",
            "lens_mm",
            "subject_binding_ids",
            "target_binding_ids",
        ):
            expected_value = getattr(left, field)
            actual_value = getattr(right, field)
            if hasattr(expected_value, "value"):
                expected_value = expected_value.value
            if hasattr(actual_value, "value"):
                actual_value = actual_value.value
            _compare_value(
                issues,
                scope=scope,
                semantic_id=semantic_id,
                field=field,
                expected=expected_value,
                actual=actual_value,
            )
        for field in ("start_frame", "end_frame"):
            _compare_frame(
                issues,
                scope=scope,
                semantic_id=semantic_id,
                field=field,
                expected=getattr(left, field),
                actual=getattr(right, field),
                tolerance_frames=tolerance_frames,
            )


def _compare_scene(
    expected: SemanticScene,
    actual: SemanticScene,
    *,
    scope: str,
    tolerance_frames: int,
    issues: list[ParityIssue],
) -> None:
    _compare_frame(
        issues,
        scope=scope,
        semantic_id=expected.source_scene_id,
        field="duration_frames",
        expected=expected.duration_frames,
        actual=actual.duration_frames,
        tolerance_frames=tolerance_frames,
    )
    _compare_entities(expected.entities, actual.entities, scope=scope, issues=issues)
    _compare_performances(
        expected.performance_cues,
        actual.performance_cues,
        scope=scope,
        tolerance_frames=tolerance_frames,
        issues=issues,
    )
    _compare_dialogues(
        expected.dialogue_cues,
        actual.dialogue_cues,
        scope=scope,
        tolerance_frames=tolerance_frames,
        issues=issues,
    )
    _compare_cameras(
        expected.camera_cuts,
        actual.camera_cuts,
        scope=scope,
        tolerance_frames=tolerance_frames,
        issues=issues,
    )


def _compare_semantics(
    expected: TimelineSemantics,
    actual: TimelineSemantics,
    *,
    scope: str,
    tolerance_frames: int,
    issues: list[ParityIssue],
) -> None:
    for field in (
        "semantics_version",
        "cir_schema_version",
        "cir_fingerprint_sha256",
        "project_id",
        "fps",
    ):
        _compare_value(
            issues,
            scope=scope,
            semantic_id=expected.project_id,
            field=field,
            expected=getattr(expected, field),
            actual=getattr(actual, field),
        )
    expected_scenes, actual_scenes = _compare_collection(
        expected.scenes,
        actual.scenes,
        key=lambda item: item.source_scene_id,
        collection="scenes",
        scope=scope,
        issues=issues,
    )
    for scene_id in sorted(expected_scenes.keys() & actual_scenes.keys()):
        _compare_scene(
            expected_scenes[scene_id],
            actual_scenes[scene_id],
            scope=scope,
            tolerance_frames=tolerance_frames,
            issues=issues,
        )


def _expected_ids(semantics: TimelineSemantics) -> tuple[set[str], set[str]]:
    performance_ids = {
        cue.cue_id for scene in semantics.scenes for cue in scene.performance_cues
    }
    dialogue_ids = {
        cue.cue_id for scene in semantics.scenes for cue in scene.dialogue_cues
    }
    return performance_ids, dialogue_ids


def _check_realization(
    readback: EngineTimelineReadback,
    expected: TimelineSemantics,
    *,
    require_animation: bool,
    require_audio: bool,
    tolerance_frames: int,
    issues: list[ParityIssue],
) -> None:
    scope = f"realization:{readback.engine.value}"
    performance_ids, dialogue_ids = _expected_ids(expected)
    animations = _index_unique(
        readback.evidence.animation_sections,
        lambda item: item.semantic_id,
        scope=scope,
        collection="animation_sections",
        issues=issues,
    )
    audio = _index_unique(
        readback.evidence.audio_sections,
        lambda item: item.semantic_id,
        scope=scope,
        collection="audio_sections",
        issues=issues,
    )
    production_animations = {
        cue_id: section
        for cue_id, section in animations.items()
        if not section.placeholder
    }
    production_audio = {
        cue_id: section for cue_id, section in audio.items() if not section.placeholder
    }
    performance_by_id = {
        cue.cue_id: cue for scene in expected.scenes for cue in scene.performance_cues
    }
    dialogue_by_id = {
        cue.cue_id: cue for scene in expected.scenes for cue in scene.dialogue_cues
    }

    missing_animation_severity = (
        IssueSeverity.ERROR if require_animation else IssueSeverity.WARNING
    )
    missing_audio_severity = (
        IssueSeverity.ERROR if require_audio else IssueSeverity.WARNING
    )
    for cue_id in sorted(performance_ids - production_animations.keys()):
        _issue(
            issues,
            scope=scope,
            code="missing_realized_animation",
            semantic_id=cue_id,
            severity=missing_animation_severity,
            message=f"Performance cue '{cue_id}' has no native animation section.",
        )
    for cue_id in sorted(dialogue_ids - production_audio.keys()):
        _issue(
            issues,
            scope=scope,
            code="missing_realized_audio",
            semantic_id=cue_id,
            severity=missing_audio_severity,
            message=f"Dialogue cue '{cue_id}' has no native audio section.",
        )
    for cue_id in sorted(animations.keys() - performance_ids):
        _issue(
            issues,
            scope=scope,
            code="unexpected_realized_animation",
            semantic_id=cue_id,
            message=f"Animation section '{cue_id}' has no CIR performance cue.",
        )
    for cue_id in sorted(audio.keys() - dialogue_ids):
        _issue(
            issues,
            scope=scope,
            code="unexpected_realized_audio",
            semantic_id=cue_id,
            message=f"Audio section '{cue_id}' has no CIR dialogue cue.",
        )

    for cue_id in sorted(animations.keys() & performance_ids):
        section = animations[cue_id]
        cue = performance_by_id[cue_id]
        _compare_frame(
            issues,
            scope=scope,
            semantic_id=cue_id,
            field="animation.start_frame",
            expected=cue.start_frame,
            actual=section.start_frame,
            tolerance_frames=tolerance_frames,
        )
        _compare_frame(
            issues,
            scope=scope,
            semantic_id=cue_id,
            field="animation.end_frame",
            expected=cue.end_frame,
            actual=section.end_frame,
            tolerance_frames=tolerance_frames,
        )
        _compare_value(
            issues,
            scope=scope,
            semantic_id=cue_id,
            field="animation.actor_binding_id",
            expected=cue.actor_binding_id,
            actual=section.actor_binding_id,
        )

    for cue_id in sorted(audio.keys() & dialogue_ids):
        section = audio[cue_id]
        cue = dialogue_by_id[cue_id]
        _compare_frame(
            issues,
            scope=scope,
            semantic_id=cue_id,
            field="audio.start_frame",
            expected=cue.start_frame,
            actual=section.start_frame,
            tolerance_frames=tolerance_frames,
        )
        if section.end_frame > cue.window_end_frame + tolerance_frames:
            _issue(
                issues,
                scope=scope,
                code="audio_exceeds_dialogue_window",
                semantic_id=cue_id,
                field="audio.end_frame",
                expected=f"<= {cue.window_end_frame}",
                actual=section.end_frame,
                delta_frames=section.end_frame - cue.window_end_frame,
                message=f"Audio section '{cue_id}' exceeds its CIR performance window.",
            )
        _compare_value(
            issues,
            scope=scope,
            semantic_id=cue_id,
            field="audio.actor_binding_id",
            expected=cue.actor_binding_id,
            actual=section.actor_binding_id,
        )


def _compare_audio_realization(
    left: EngineTimelineReadback,
    right: EngineTimelineReadback,
    *,
    tolerance_frames: int,
    issues: list[ParityIssue],
) -> None:
    scope = f"realization:{left.engine.value}_to_{right.engine.value}"
    left_by_id = {item.semantic_id: item for item in left.evidence.audio_sections}
    right_by_id = {item.semantic_id: item for item in right.evidence.audio_sections}
    for cue_id in sorted(left_by_id.keys() & right_by_id.keys()):
        for field in ("start_frame", "end_frame"):
            _compare_frame(
                issues,
                scope=scope,
                semantic_id=cue_id,
                field=f"audio.{field}",
                expected=getattr(left_by_id[cue_id], field),
                actual=getattr(right_by_id[cue_id], field),
                tolerance_frames=tolerance_frames,
            )


def verify_readbacks(
    project: Project,
    readbacks: Sequence[EngineTimelineReadback],
    *,
    tolerance_frames: int = 1,
    require_animation: bool = False,
    require_audio: bool = False,
    required_engines: Sequence[EngineName] = (),
) -> ParityReport:
    """Verify engine readbacks against CIR and against one another."""

    if tolerance_frames < 0:
        raise ValueError("tolerance_frames must be non-negative")
    if not readbacks:
        raise ValueError("At least one engine readback is required.")

    expected = compile_semantics(project)
    issues: list[ParityIssue] = []
    seen_engines: set[str] = set()
    for readback in readbacks:
        engine = readback.engine.value
        if engine in seen_engines:
            _issue(
                issues,
                scope="readbacks",
                code="duplicate_engine_readback",
                semantic_id=engine,
                message=f"More than one readback was supplied for engine '{engine}'.",
            )
        seen_engines.add(engine)
        _compare_semantics(
            expected,
            readback.semantics,
            scope=f"cir_to_{engine}",
            tolerance_frames=tolerance_frames,
            issues=issues,
        )
        _check_realization(
            readback,
            expected,
            require_animation=require_animation,
            require_audio=require_audio,
            tolerance_frames=tolerance_frames,
            issues=issues,
        )

    for engine in sorted(set(required_engines), key=lambda item: item.value):
        if engine.value not in seen_engines:
            _issue(
                issues,
                scope="readbacks",
                code="missing_engine_readback",
                semantic_id=engine.value,
                message=f"Required engine readback '{engine.value}' was not supplied.",
            )

    for left, right in combinations(readbacks, 2):
        _compare_semantics(
            left.semantics,
            right.semantics,
            scope=f"{left.engine.value}_to_{right.engine.value}",
            tolerance_frames=tolerance_frames,
            issues=issues,
        )
        _compare_audio_realization(
            left,
            right,
            tolerance_frames=tolerance_frames,
            issues=issues,
        )

    error_count = sum(issue.severity is IssueSeverity.ERROR for issue in issues)
    warning_count = sum(issue.severity is IssueSeverity.WARNING for issue in issues)
    return ParityReport(
        project_id=expected.project_id,
        cir_fingerprint_sha256=expected.cir_fingerprint_sha256,
        tolerance_frames=tolerance_frames,
        equivalent=error_count == 0,
        error_count=error_count,
        warning_count=warning_count,
        readbacks=[
            ReadbackSummary(
                engine=readback.engine,
                engine_version=readback.engine_version,
                adapter_version=readback.adapter_version,
                timeline_asset=readback.timeline_asset,
                animation_section_count=len(readback.evidence.animation_sections),
                audio_section_count=len(readback.evidence.audio_sections),
            )
            for readback in readbacks
        ],
        issues=issues,
    )
