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
