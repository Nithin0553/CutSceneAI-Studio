import json
import sys
from pathlib import Path
from types import ModuleType

import pytest
from cutsceneai_cir import Project
from cutsceneai_parity import compile_semantics
from cutsceneai_unreal import (
    UnrealExportPlan,
    render_unreal_marker_upgrade_script,
)

UNREAL_ROOT = Path(__file__).resolve().parents[1]
UPGRADE = UNREAL_ROOT / "examples" / "upgrade_office_dialogue_markers.py"


def test_marker_upgrade_renderer_is_deterministic_and_committed(
    cir_project: Project, unreal_plan: UnrealExportPlan
) -> None:
    semantics = compile_semantics(cir_project)
    first = render_unreal_marker_upgrade_script(unreal_plan, semantics)
    second = render_unreal_marker_upgrade_script(unreal_plan, semantics)

    assert first == second
    compile(first, "cutsceneai-unreal-upgrade-markers.py", "exec")
    assert UPGRADE.read_text(encoding="utf-8") == first
    assert "CSA|TIMELINE|" in first
    assert "PERF {index:02d}" in first
    assert "save_loaded_asset(sequence, False)" in first


def _fake_unreal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    plan: UnrealExportPlan,
    *,
    playback_end: int = 432,
    swap_camera_bindings: bool = False,
) -> tuple[ModuleType, list[object], list[str], list[object]]:
    scene = plan.sequences[0].model_dump(mode="json")

    class Value:
        def __init__(self, **values) -> None:
            self.values = values

        def get_editor_property(self, name: str):
            return self.values[name]

    class FrameNumber(Value):
        def __init__(self, value: int) -> None:
            super().__init__(value=value)

        def __int__(self) -> int:
            return int(self.values["value"])

    class MovieSceneMarkedFrame(Value):
        def __init__(self, frame_number: FrameNumber, label: str) -> None:
            super().__init__(frame_number=frame_number, label=label, comment="")

        def set_editor_property(self, name: str, value) -> None:
            self.values[name] = value

    class BindingId:
        def __init__(self, value: str) -> None:
            self.value = value

        def get_guid(self) -> str:
            return self.value

    class CameraBindingId:
        def __init__(self, value: str) -> None:
            self.value = value

    class Binding:
        def __init__(self, display_name: str, key: str) -> None:
            self.display_name = display_name
            self.key = key

        def get_display_name(self) -> str:
            return self.display_name

    class CameraSection:
        def __init__(self, key: str, start: int, end: int) -> None:
            self.key = key
            self.start = start
            self.end = end

        def get_camera_binding_id(self) -> CameraBindingId:
            return CameraBindingId(self.key)

        def get_start_frame(self) -> int:
            return self.start

        def get_end_frame(self) -> int:
            return self.end

    class CameraTrack:
        def __init__(self, sections: list[CameraSection]) -> None:
            self.sections = sections

        def get_sections(self) -> list[CameraSection]:
            return self.sections

    class MovieSceneCameraCutTrack:
        pass

    markers: list[object] = []
    for index, cue in enumerate(scene["performance_cues"], start=1):
        actor_id = cue["actor_binding_id"].split(":", 1)[-1]
        comment = json.dumps(
            {
                "motion_prompt": cue["motion_prompt"],
                "motion_style": cue["motion_style"],
                "emotion": cue["emotion"],
                "emotion_intensity": cue["emotion_intensity"],
                "lip_sync": cue["lip_sync"],
                "look_at_binding_id": cue["look_at_binding_id"],
            },
            sort_keys=True,
        )
        performance = MovieSceneMarkedFrame(
            FrameNumber(cue["start_frame"]),
            f"PERF {index:02d} {actor_id} {cue['source_beat_id']}",
        )
        performance.set_editor_property("comment", comment)
        markers.append(performance)
        if cue["dialogue"] is not None and cue["dialogue_start_frame"] is not None:
            dialogue = MovieSceneMarkedFrame(
                FrameNumber(cue["dialogue_start_frame"]),
                f"DIALOGUE {index:02d} {actor_id}",
            )
            dialogue.set_editor_property("comment", cue["dialogue"])
            markers.append(dialogue)

    bindings = []
    for actor in scene["actors"]:
        bindings.append(Binding(actor["display_name"], actor["binding_id"]))
    camera_sections = []
    semantics = compile_semantics_from_plan_fixture()
    for cut, camera in zip(semantics["camera_cuts"], scene["cameras"]):
        bindings.append(Binding(camera["display_name"], camera["binding_id"]))
        camera_sections.append(
            CameraSection(camera["binding_id"], cut["start_frame"], cut["end_frame"])
        )
    if swap_camera_bindings:
        camera_sections[0].key, camera_sections[1].key = (
            camera_sections[1].key,
            camera_sections[0].key,
        )

    class LevelSequence:
        @staticmethod
        def get_marked_frames_from_sequence(time_unit) -> list[object]:
            assert time_unit == MovieSceneTimeUnit.DISPLAY_RATE
            return markers

        @staticmethod
        def add_marked_frame_to_sequence(marker, time_unit) -> None:
            assert time_unit == MovieSceneTimeUnit.DISPLAY_RATE
            markers.append(marker)

        @staticmethod
        def get_display_rate() -> Value:
            return Value(numerator=24, denominator=1)

        @staticmethod
        def get_playback_start() -> int:
            return 0

        @staticmethod
        def get_playback_end() -> int:
            return playback_end

        @staticmethod
        def get_bindings() -> list[Binding]:
            return bindings

        @staticmethod
        def get_binding_id(binding: Binding) -> BindingId:
            return BindingId(binding.key)

        @staticmethod
        def resolve_binding_id(binding_id: CameraBindingId) -> Binding | None:
            return next(
                (binding for binding in bindings if binding.key == binding_id.value),
                None,
            )

        @staticmethod
        def find_tracks_by_exact_type(track_type) -> list[CameraTrack]:
            if track_type is MovieSceneCameraCutTrack:
                return [CameraTrack(camera_sections)]
            return []

    sequence = LevelSequence()
    saves: list[object] = []

    class EditorAssetLibrary:
        @staticmethod
        def load_asset(path: str) -> LevelSequence:
            assert path.endswith("/LS_SceneMeeting")
            return sequence

        @staticmethod
        def save_loaded_asset(asset, only_if_is_dirty: bool) -> bool:
            assert asset is sequence
            assert only_if_is_dirty is False
            saves.append(asset)
            return True

    class MovieSceneTimeUnit:
        DISPLAY_RATE = "display-rate"

    logs: list[str] = []
    unreal = ModuleType("unreal")
    unreal.LevelSequence = LevelSequence
    unreal.FrameNumber = FrameNumber
    unreal.MovieSceneMarkedFrame = MovieSceneMarkedFrame
    unreal.MovieSceneCameraCutTrack = MovieSceneCameraCutTrack
    unreal.MovieSceneTimeUnit = MovieSceneTimeUnit
    unreal.EditorAssetLibrary = EditorAssetLibrary
    unreal.log = logs.append
    monkeypatch.setitem(sys.modules, "unreal", unreal)
    return unreal, markers, logs, saves


def compile_semantics_from_plan_fixture() -> dict:
    path = (
        UNREAL_ROOT.parents[1]
        / "parity"
        / "examples"
        / "office-dialogue.semantics.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))["scenes"][0]


def test_upgrade_adds_only_canonical_markers_to_valid_legacy_sequence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cir_project: Project,
    unreal_plan: UnrealExportPlan,
) -> None:
    _, markers, logs, saves = _fake_unreal(tmp_path, monkeypatch, unreal_plan)
    semantics = compile_semantics(cir_project)
    script = render_unreal_marker_upgrade_script(unreal_plan, semantics)

    namespace = {"__name__": "cutsceneai_generated_marker_upgrade"}
    exec(script, namespace)  # noqa: S102

    canonical = [
        marker
        for marker in markers
        if marker.get_editor_property("label").startswith("CSA|")
    ]
    legacy = [
        marker
        for marker in markers
        if not marker.get_editor_property("label").startswith("CSA|")
    ]
    assert len(canonical) == 15
    assert len(legacy) == 6
    assert len(saves) == 1
    assert logs == [
        (
            "CutSceneAI Unreal semantic marker upgrade: "
            "/Game/CutSceneAI/Sequences/LS_SceneMeeting "
            "(15 canonical markers added; native tracks unchanged)"
        )
    ]

    namespace = {"__name__": "cutsceneai_generated_marker_upgrade_second_run"}
    exec(script, namespace)  # noqa: S102
    assert len(saves) == 1
    assert logs[-1] == (
        "CutSceneAI Unreal semantic markers already current: "
        "/Game/CutSceneAI/Sequences/LS_SceneMeeting"
    )


def test_upgrade_refuses_a_legacy_sequence_with_a_changed_playback_range(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cir_project: Project,
    unreal_plan: UnrealExportPlan,
) -> None:
    _, markers, _, saves = _fake_unreal(
        tmp_path, monkeypatch, unreal_plan, playback_end=431
    )
    semantics = compile_semantics(cir_project)
    script = render_unreal_marker_upgrade_script(unreal_plan, semantics)

    with pytest.raises(RuntimeError, match="playback range does not match"):
        exec(  # noqa: S102
            script, {"__name__": "cutsceneai_invalid_marker_upgrade"}
        )

    assert not any(
        marker.get_editor_property("label").startswith("CSA|") for marker in markers
    )
    assert saves == []


def test_upgrade_refuses_changed_camera_targets_even_when_ranges_match(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cir_project: Project,
    unreal_plan: UnrealExportPlan,
) -> None:
    _, markers, _, saves = _fake_unreal(
        tmp_path, monkeypatch, unreal_plan, swap_camera_bindings=True
    )
    semantics = compile_semantics(cir_project)
    script = render_unreal_marker_upgrade_script(unreal_plan, semantics)

    with pytest.raises(RuntimeError, match="camera cuts do not match"):
        exec(  # noqa: S102
            script, {"__name__": "cutsceneai_wrong_camera_marker_upgrade"}
        )

    assert not any(
        marker.get_editor_property("label").startswith("CSA|") for marker in markers
    )
    assert saves == []
