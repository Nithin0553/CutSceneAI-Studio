import json
from pathlib import Path
import sys
from types import ModuleType

import pytest

from cutsceneai_cir import Project
from cutsceneai_parity import (
    EngineName,
    EngineTimelineReadback,
    TimelineSemantics,
    compile_semantics,
    verify_readbacks,
)
from cutsceneai_unreal import (
    UnrealExportPlan,
    render_unreal_import_script,
    render_unreal_readback_script,
)


UNREAL_ROOT = Path(__file__).resolve().parents[1]
READBACK = UNREAL_ROOT / "examples" / "readback_office_dialogue.py"


def test_semantic_importer_and_readback_are_self_contained(
    cir_project: Project, unreal_plan: UnrealExportPlan
) -> None:
    semantics = compile_semantics(cir_project)
    importer = render_unreal_import_script(unreal_plan, semantics)
    readback = render_unreal_readback_script(unreal_plan, semantics)

    compile(importer, "cutsceneai-unreal-import.py", "exec")
    compile(readback, "cutsceneai-unreal-readback.py", "exec")
    assert semantics.cir_fingerprint_sha256 in importer
    assert semantics.cir_fingerprint_sha256 in readback
    assert "CSA|TIMELINE|" in importer
    assert "CSA|PERFORMANCE|" in importer
    assert "CSA|DIALOGUE|" in importer
    assert "CSA|CAMERA|" in importer
    assert "get_marked_frames_from_sequence" in readback
    assert "find_tracks_by_exact_type" in readback
    assert "MovieSceneSkeletalAnimationTrack" in readback
    assert "MovieSceneAudioTrack" in readback
    assert "MovieSceneCameraCutTrack" in readback
    assert "project_saved_dir" in readback
    assert "__PLAN_JSON__" not in readback
    assert "__SEMANTICS_JSON__" not in readback


def test_readback_renderer_is_deterministic_and_committed(
    cir_project: Project, unreal_plan: UnrealExportPlan
) -> None:
    semantics = compile_semantics(cir_project)
    first = render_unreal_readback_script(unreal_plan, semantics)
    second = render_unreal_readback_script(unreal_plan, semantics)

    assert first == second
    assert READBACK.read_text(encoding="utf-8") == first


def test_readback_rejects_project_mismatch(
    cir_project: Project, unreal_plan: UnrealExportPlan
) -> None:
    semantics = compile_semantics(cir_project).model_copy(
        update={"project_id": "other-project"}
    )

    with pytest.raises(ValueError, match="project IDs"):
        render_unreal_readback_script(unreal_plan, semantics)


def test_readback_rejects_frame_rate_mismatch(
    cir_project: Project, unreal_plan: UnrealExportPlan
) -> None:
    semantics = compile_semantics(cir_project).model_copy(update={"fps": 30})

    with pytest.raises(ValueError, match="frame rates"):
        render_unreal_readback_script(unreal_plan, semantics)


def test_readback_rejects_scene_mismatch(
    unreal_plan: UnrealExportPlan, cir_project: Project
) -> None:
    semantics = TimelineSemantics.model_validate(
        {
            **compile_semantics(cir_project).model_dump(mode="json"),
            "scenes": [],
        }
    )

    with pytest.raises(ValueError, match="different scenes"):
        render_unreal_readback_script(unreal_plan, semantics)


def test_generated_readback_inspects_saved_native_sequence(
    tmp_path: Path,
    monkeypatch,
    cir_project: Project,
    unreal_plan: UnrealExportPlan,
) -> None:
    semantics = compile_semantics(cir_project)
    scene_semantics = semantics.scenes[0].model_dump(mode="json")
    scene_plan = unreal_plan.sequences[0].model_dump(mode="json")

    class Value:
        def __init__(self, **values) -> None:
            self.values = values

        def get_editor_property(self, name: str):
            return self.values[name]

    class Marker(Value):
        pass

    class BindingId:
        def __init__(self, value: str) -> None:
            self.value = value

        def get_guid(self) -> str:
            return self.value

    class CameraComponent(Value):
        pass

    class CineCameraActor:
        def __init__(self, lens_mm: float) -> None:
            self.component = CameraComponent(current_focal_length=lens_mm)

        def get_cine_camera_component(self) -> CameraComponent:
            return self.component

    class Asset:
        def __init__(self, path: str) -> None:
            self.path = path

        def get_path_name(self) -> str:
            return self.path

    class NativeSection:
        def __init__(self, start: int, end: int, asset: Asset) -> None:
            self.start = start
            self.end = end
            self.asset = asset

        def get_start_frame(self) -> int:
            return self.start

        def get_end_frame(self) -> int:
            return self.end

        def get_editor_property(self, name: str):
            assert name == "params"
            return Value(animation=self.asset)

        def get_sound(self) -> Asset:
            return self.asset

    class NativeTrack:
        def __init__(self, display_name: str, sections: list[NativeSection]) -> None:
            self.display_name = display_name
            self.sections = sections

        def get_display_name(self) -> str:
            return self.display_name

        def get_sections(self) -> list[NativeSection]:
            return self.sections

    class Binding:
        def __init__(
            self,
            name: str,
            value: str,
            template=None,
            animation_sections: list[NativeSection] | None = None,
        ) -> None:
            self.name = name
            self.value = value
            self.template = template
            self.animation_sections = (
                [] if animation_sections is None else animation_sections
            )

        def get_display_name(self) -> str:
            return self.name

        def get_object_template(self):
            return self.template

        def find_tracks_by_exact_type(self, track_type) -> list:
            if (
                track_type is MovieSceneSkeletalAnimationTrack
                and self.animation_sections
            ):
                return [NativeTrack("CutSceneAI Animation", self.animation_sections)]
            return []

    class CameraSection:
        def __init__(self, binding_id: BindingId, start: int, end: int) -> None:
            self.binding_id = binding_id
            self.start = start
            self.end = end

        def get_camera_binding_id(self) -> BindingId:
            return self.binding_id

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

    class MovieSceneAudioTrack:
        pass

    class MovieSceneSkeletalAnimationTrack:
        pass

    markers: list[Marker] = []

    def marker(kind: str, value: dict, frame: int, label: str) -> None:
        payload = {**value, "semantic_kind": kind}
        markers.append(
            Marker(
                label=label,
                comment=json.dumps({"cutsceneai": payload}, sort_keys=True),
                frame_number=Value(value=frame),
            )
        )

    marker(
        "timeline",
        {
            "semantics_version": semantics.semantics_version,
            "cir_schema_version": semantics.cir_schema_version,
            "cir_fingerprint_sha256": semantics.cir_fingerprint_sha256,
            "project_id": semantics.project_id,
            "fps": semantics.fps,
            "source_scene_id": scene_semantics["source_scene_id"],
            "duration_frames": scene_semantics["duration_frames"],
        },
        0,
        "CSA|TIMELINE|scene-meeting",
    )

    actor_plan_by_id = {item["binding_id"]: item for item in scene_plan["actors"]}
    animation_sections_by_actor = {
        item["binding_id"]: [] for item in scene_plan["actors"]
    }
    bindings = []
    for entity in scene_semantics["entities"]:
        actor = actor_plan_by_id[entity["binding_id"]]
        marker(
            "entity",
            {**entity, "display_name": actor["display_name"]},
            0,
            f"CSA|ENTITY|{entity['binding_id']}",
        )
        bindings.append(
            Binding(
                actor["display_name"],
                entity["binding_id"],
                animation_sections=animation_sections_by_actor[entity["binding_id"]],
            )
        )

    for cue in scene_semantics["performance_cues"]:
        marker(
            "performance",
            cue,
            cue["start_frame"],
            f"CSA|PERFORMANCE|{cue['cue_id']}",
        )
        animation_sections_by_actor[cue["actor_binding_id"]].append(
            NativeSection(
                cue["start_frame"],
                cue["end_frame"],
                Asset(f"/Game/Animations/{cue['cue_id']}"),
            )
        )
    audio_sections_by_actor = {item["binding_id"]: [] for item in scene_plan["actors"]}
    for cue in scene_semantics["dialogue_cues"]:
        marker(
            "dialogue",
            cue,
            cue["start_frame"],
            f"CSA|DIALOGUE|{cue['cue_id']}",
        )
        audio_sections_by_actor[cue["actor_binding_id"]].append(
            NativeSection(
                cue["start_frame"],
                cue["start_frame"] + 24,
                Asset(f"/Game/Audio/{cue['cue_id']}"),
            )
        )
    audio_tracks = [
        NativeTrack(
            f"CutSceneAI Dialogue - {actor_plan_by_id[binding_id]['display_name']}",
            sections,
        )
        for binding_id, sections in audio_sections_by_actor.items()
        if sections
    ]

    camera_sections = []
    for cut, camera in zip(scene_semantics["camera_cuts"], scene_plan["cameras"]):
        marker(
            "camera",
            {**cut, "display_name": camera["display_name"]},
            cut["start_frame"],
            f"CSA|CAMERA|{cut['cut_id']}",
        )
        binding_id = BindingId(camera["binding_id"])
        bindings.append(
            Binding(
                camera["display_name"],
                binding_id.value,
                CineCameraActor(cut["lens_mm"]),
            )
        )
        camera_sections.append(
            CameraSection(binding_id, cut["start_frame"], cut["end_frame"])
        )

    class LevelSequence:
        @staticmethod
        def get_marked_frames_from_sequence(time_unit) -> list[Marker]:
            assert time_unit == MovieSceneTimeUnit.DISPLAY_RATE
            return markers

        @staticmethod
        def get_bindings() -> list[Binding]:
            return bindings

        @staticmethod
        def get_binding_id(binding: Binding) -> BindingId:
            return BindingId(binding.value)

        @staticmethod
        def find_tracks_by_exact_type(track_type) -> list:
            if track_type is MovieSceneCameraCutTrack:
                return [CameraTrack(camera_sections)]
            if track_type is MovieSceneAudioTrack:
                return audio_tracks
            return []

        @staticmethod
        def get_display_rate() -> Value:
            return Value(numerator=24, denominator=1)

        @staticmethod
        def get_playback_start() -> int:
            return 0

        @staticmethod
        def get_playback_end() -> int:
            return 432

    sequence = LevelSequence()

    class EditorAssetLibrary:
        @staticmethod
        def load_asset(path: str) -> LevelSequence:
            assert path.endswith("/LS_SceneMeeting")
            return sequence

    class SystemLibrary:
        @staticmethod
        def get_engine_version() -> str:
            return "5.8.0-test"

    class Paths:
        @staticmethod
        def project_saved_dir() -> str:
            return str(tmp_path)

    class MovieSceneTimeUnit:
        DISPLAY_RATE = "display-rate"

    unreal = ModuleType("unreal")
    unreal.LevelSequence = LevelSequence
    unreal.CineCameraActor = CineCameraActor
    unreal.MovieSceneCameraCutTrack = MovieSceneCameraCutTrack
    unreal.MovieSceneAudioTrack = MovieSceneAudioTrack
    unreal.MovieSceneSkeletalAnimationTrack = MovieSceneSkeletalAnimationTrack
    unreal.MovieSceneTimeUnit = MovieSceneTimeUnit
    unreal.EditorAssetLibrary = EditorAssetLibrary
    unreal.SystemLibrary = SystemLibrary
    unreal.Paths = Paths
    unreal.log = lambda message: None
    monkeypatch.setitem(sys.modules, "unreal", unreal)

    namespace = {"__name__": "cutsceneai_generated_readback"}
    exec(render_unreal_readback_script(unreal_plan, semantics), namespace)
    output_path = namespace["export_readback"]()
    readback = EngineTimelineReadback.model_validate(
        json.loads(output_path.read_text(encoding="utf-8"))
    )

    assert readback.engine is EngineName.UNREAL
    assert readback.semantics.cir_fingerprint_sha256 == semantics.cir_fingerprint_sha256
    assert len(readback.semantics.scenes[0].camera_cuts) == 4
    assert len(readback.evidence.animation_sections) == 4
    assert len(readback.evidence.audio_sections) == 2
    report = verify_readbacks(
        cir_project,
        [readback],
        tolerance_frames=0,
        require_animation=True,
        require_audio=True,
    )
    assert report.equivalent is True
