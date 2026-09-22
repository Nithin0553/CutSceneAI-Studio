from __future__ import annotations

from typing import Any

import pytest
from cutsceneai_parity import TimelineSemantics
from cutsceneai_performance import (
    PerformanceBundle,
    PerformanceOutputError,
    assemble_performance_bundle,
    verify_performance_bundle_semantics,
)
from cutsceneai_performance.semantics import _verify_body_track_semantics


def assembled(fixture: Any) -> PerformanceBundle:
    return assemble_performance_bundle(
        fixture.plan,
        body_outputs=fixture.body_outputs,
        facial_outputs=fixture.facial_outputs,
        camera_outputs=fixture.camera_outputs,
        audio_outputs=fixture.audio_outputs,
    )


def test_bundle_matches_exact_timeline_semantics(
    performance_fixture: Any,
    timeline_semantics: TimelineSemantics,
) -> None:
    scene = verify_performance_bundle_semantics(
        assembled(performance_fixture), timeline_semantics
    )

    assert scene == timeline_semantics.scenes[0]
    assert scene is not timeline_semantics.scenes[0]


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("multiple_scenes", "exactly one semantic scene"),
        ("identity", "identity or timeline"),
        ("body", "body tracks"),
        ("facial", "facial tracks"),
        ("camera", "camera tracks"),
        ("audio", "audio tracks"),
        ("audio_window", "exceeds its semantic dialogue window"),
    ],
)
def test_bundle_rejects_timeline_semantic_drift(
    performance_fixture: Any,
    timeline_semantics: TimelineSemantics,
    mutation: str,
    message: str,
) -> None:
    semantics = timeline_semantics.model_copy(deep=True)
    scene = semantics.scenes[0]
    if mutation == "multiple_scenes":
        semantics.scenes.append(scene.model_copy(deep=True))
    elif mutation == "identity":
        semantics = semantics.model_copy(update={"project_id": "different-project"})
    elif mutation == "body":
        scene.performance_cues[0] = scene.performance_cues[0].model_copy(
            update={"actor_binding_id": "actor:other"}
        )
    elif mutation == "facial":
        scene.dialogue_cues[0] = scene.dialogue_cues[0].model_copy(
            update={"cue_id": "dialogue:fixture:other"}
        )
    elif mutation == "camera":
        scene.camera_cuts[0] = scene.camera_cuts[0].model_copy(
            update={"source_shot_id": "other-shot"}
        )
    elif mutation == "audio":
        scene.dialogue_cues[0] = scene.dialogue_cues[0].model_copy(
            update={"start_frame": 2}
        )
    elif mutation == "audio_window":
        scene.dialogue_cues[0] = scene.dialogue_cues[0].model_copy(
            update={"window_end_frame": 2}
        )

    with pytest.raises(PerformanceOutputError, match=message):
        verify_performance_bundle_semantics(assembled(performance_fixture), semantics)


def test_body_phase_tracks_may_exactly_partition_one_semantic_cue(
    performance_fixture: Any,
    timeline_semantics: TimelineSemantics,
) -> None:
    bundle = assembled(performance_fixture)
    cue = timeline_semantics.scenes[0].performance_cues[0]
    source = next(
        track
        for track in bundle.package.body_tracks
        if track.source_performance_cue_id == cue.cue_id
    )
    midpoint = cue.start_frame + (cue.end_frame - cue.start_frame) // 2
    first = source.model_copy(
        update={
            "semantic_id": source.semantic_id + ":phase-a",
            "start_frame": cue.start_frame,
            "end_frame": midpoint,
        },
        deep=True,
    )
    second = source.model_copy(
        update={
            "semantic_id": source.semantic_id + ":phase-b",
            "start_frame": midpoint,
            "end_frame": cue.end_frame,
        },
        deep=True,
    )

    _verify_body_track_semantics([first, second], [cue])


@pytest.mark.parametrize(
    "mutation",
    ["gap", "overlap", "wrong_actor", "outside_window"],
)
def test_body_phase_partition_rejects_semantic_drift(
    performance_fixture: Any,
    timeline_semantics: TimelineSemantics,
    mutation: str,
) -> None:
    bundle = assembled(performance_fixture)
    cue = timeline_semantics.scenes[0].performance_cues[0]
    source = next(
        track
        for track in bundle.package.body_tracks
        if track.source_performance_cue_id == cue.cue_id
    )
    midpoint = cue.start_frame + (cue.end_frame - cue.start_frame) // 2
    first_end = midpoint
    second_start = midpoint
    actor = cue.actor_binding_id
    second_end = cue.end_frame

    if mutation == "gap":
        second_start += 1
    elif mutation == "overlap":
        second_start -= 1
    elif mutation == "wrong_actor":
        actor = "actor:other"
    elif mutation == "outside_window":
        second_end += 1

    tracks = [
        source.model_copy(
            update={
                "semantic_id": source.semantic_id + ":phase-a",
                "start_frame": cue.start_frame,
                "end_frame": first_end,
            },
            deep=True,
        ),
        source.model_copy(
            update={
                "semantic_id": source.semantic_id + ":phase-b",
                "actor_binding_id": actor,
                "start_frame": second_start,
                "end_frame": second_end,
            },
            deep=True,
        ),
    ]

    with pytest.raises(PerformanceOutputError, match="body tracks"):
        _verify_body_track_semantics(tracks, [cue])
