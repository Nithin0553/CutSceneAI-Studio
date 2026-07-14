import sys
from pathlib import Path
from types import ModuleType

from cutsceneai_cir import Project
from cutsceneai_unreal import (
    UnrealExportPlan,
    compile_project,
    render_unreal_import_script,
)


UNREAL_ROOT = Path(__file__).resolve().parents[1]
IMPORTER = UNREAL_ROOT / "examples" / "import_office_dialogue.py"


def test_importer_is_self_contained_syntax_valid_and_non_destructive(
    unreal_plan: UnrealExportPlan,
) -> None:
    script = render_unreal_import_script(unreal_plan)

    compile(script, "cutsceneai_unreal_import.py", "exec")
    assert "subsystem.add_spawnable_from_class" in script
    assert "LevelSequenceEditorBlueprintLibrary.get_bound_objects" in script
    assert "component.set_current_focal_length" in script
    assert "subsystem.save_default_spawnable_state" in script
    assert "unreal.MovieSceneCameraCutTrack" in script
    assert "sequence.add_marked_frame_to_sequence" in script
    assert "save_loaded_asset" in script
    assert "delete_asset" not in script
    assert "Refusing to replace existing asset" in script


def test_importer_configures_live_58_camera_when_template_component_is_missing(
    unreal_plan: UnrealExportPlan,
    monkeypatch,
) -> None:
    script = render_unreal_import_script(unreal_plan)

    class LensSettings:
        def __init__(self) -> None:
            self.values = {"min_focal_length": 30.0, "max_focal_length": 300.0}

        def get_editor_property(self, name: str) -> float:
            return self.values[name]

        def set_editor_property(self, name: str, value: float) -> None:
            self.values[name] = value

    class CameraComponent:
        def __init__(self) -> None:
            self.lens_settings = LensSettings()
            self.current_focal_length = 35.0

        def get_editor_property(self, name: str):
            assert name == "lens_settings"
            return self.lens_settings

        def set_editor_property(self, name: str, value) -> None:
            assert name == "lens_settings"
            self.lens_settings = value

        def set_current_focal_length(self, value: float) -> None:
            self.current_focal_length = value

    class CineCameraActor:
        def __init__(self, component) -> None:
            self.component = component
            self.label = ""
            self.transform_calls = []

        def get_cine_camera_component(self):
            return self.component

        def set_actor_label(self, value: str) -> None:
            self.label = value

        def set_actor_location(self, *args) -> None:
            self.transform_calls.append(("location", args))

        def set_actor_rotation(self, *args) -> None:
            self.transform_calls.append(("rotation", args))

        def set_actor_scale3d(self, *args) -> None:
            self.transform_calls.append(("scale", args))

    class Binding:
        def __init__(self, template) -> None:
            self.template = template
            self.display_name = ""

        def get_object_template(self):
            return self.template

        def set_display_name(self, value: str) -> None:
            self.display_name = value

    component = CameraComponent()
    live_actor = CineCameraActor(component)
    template_actor = CineCameraActor(None)
    binding = Binding(template_actor)

    class Sequence:
        def get_binding_id(self, value):
            assert value is binding
            return "camera-binding-id"

    class Subsystem:
        def __init__(self) -> None:
            self.saved = []

        def add_spawnable_from_class(self, sequence, actor_class):
            return binding

        def save_default_spawnable_state(self, value) -> None:
            self.saved.append(value)

    subsystem = Subsystem()

    class BlueprintLibrary:
        @staticmethod
        def force_update() -> None:
            return None

        @staticmethod
        def get_bound_objects(binding_id):
            assert binding_id == "camera-binding-id"
            return [live_actor]

    class Quat:
        def __init__(self, *values) -> None:
            self.values = values

        def rotator(self):
            return self.values

    unreal = ModuleType("unreal")
    unreal.CineCameraActor = CineCameraActor
    unreal.LevelSequenceEditorBlueprintLibrary = BlueprintLibrary
    unreal.Vector = lambda *values: values
    unreal.Quat = Quat
    unreal.load_class = lambda outer, path: CineCameraActor
    monkeypatch.setitem(sys.modules, "unreal", unreal)

    namespace = {"__name__": "cutsceneai_generated_importer"}
    exec(script, namespace)
    camera = unreal_plan.sequences[0].cameras[0].model_dump(mode="json")

    result = namespace["_add_camera"](Sequence(), subsystem, camera)

    assert result is binding
    assert binding.display_name == "CAM_ShotEstablishing"
    assert live_actor.label == "CAM_ShotEstablishing"
    assert component.current_focal_length == 28.0
    assert component.lens_settings.values["min_focal_length"] == 28.0
    assert subsystem.saved == [binding]


def test_importer_escapes_arbitrary_project_text(cir_project: Project) -> None:
    cir_project.name = "Office ''' Dialogue with \\\\ paths and \"quotes\""
    script = render_unreal_import_script(compile_project(cir_project))

    compile(script, "hostile_text_import.py", "exec")
    assert "__PLAN_JSON__" not in script


def test_committed_importer_matches_renderer(unreal_plan: UnrealExportPlan) -> None:
    assert IMPORTER.read_text(encoding="utf-8") == render_unreal_import_script(
        unreal_plan
    )
