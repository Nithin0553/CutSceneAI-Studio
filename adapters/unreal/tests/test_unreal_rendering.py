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
    assert 'for set_piece in scene["set_pieces"]' in script
    assert "_configure_static_mesh" in script
    assert "_configure_skeletal_mesh" in script
    assert "set_skeletal_mesh_asset" in script
    assert "LevelSequenceEditorBlueprintLibrary.get_bound_objects" in script
    assert "binding.remove_track(track)" in script
    assert 'component.set_editor_property("current_focal_length", lens_mm)' in script
    assert "subsystem.save_default_spawnable_state" in script
    assert "unreal.MovieSceneCameraCutTrack" in script
    assert "sequence.add_marked_frame_to_sequence" in script
    assert "save_loaded_asset" in script
    assert "delete_asset" not in script
    assert "Refusing to replace existing asset" in script


def test_importer_builds_visible_proxy_actor_and_room_set_piece(
    unreal_plan: UnrealExportPlan,
    monkeypatch,
) -> None:
    script = render_unreal_import_script(unreal_plan)

    class StaticMesh:
        pass

    class StaticMeshComponent:
        def __init__(self) -> None:
            self.mesh = None

        def set_static_mesh(self, mesh) -> None:
            self.mesh = mesh

    class StaticMeshActor:
        def __init__(self) -> None:
            self.component = StaticMeshComponent()
            self.label = ""
            self.location = None
            self.rotation = None
            self.scale = None

        def get_editor_property(self, name: str):
            assert name == "static_mesh_component"
            return self.component

        def set_actor_label(self, value: str) -> None:
            self.label = value

        def set_actor_location(self, value, sweep: bool, teleport: bool) -> None:
            self.location = value

        def set_actor_rotation(self, value, teleport: bool) -> None:
            self.rotation = value

        def set_actor_scale3d(self, value) -> None:
            self.scale = value

    class MovieScene3DTransformTrack:
        pass

    class MovieSceneSpawnTrack:
        pass

    class Binding:
        def __init__(self, binding_id: str) -> None:
            self.binding_id = binding_id
            self.template = StaticMeshActor()
            self.live_actor = StaticMeshActor()
            self.display_name = ""
            self.tracks = [MovieScene3DTransformTrack(), MovieSceneSpawnTrack()]

        def get_object_template(self):
            return self.template

        def set_display_name(self, value: str) -> None:
            self.display_name = value

        def find_tracks_by_exact_type(self, track_type):
            return [track for track in self.tracks if type(track) is track_type]

        def remove_track(self, track) -> None:
            self.tracks.remove(track)

    class Subsystem:
        def __init__(self) -> None:
            self.bindings = []
            self.saved = []

        def add_spawnable_from_class(self, sequence, actor_class):
            assert actor_class is StaticMeshActor
            binding = Binding(f"binding-{len(self.bindings)}")
            self.bindings.append(binding)
            return binding

        def save_default_spawnable_state(self, value) -> None:
            self.saved.append(value)

    class Quat:
        def __init__(self, *values) -> None:
            self.values = values

        def rotator(self):
            return self.values

    mesh = StaticMesh()

    class EditorAssetLibrary:
        @staticmethod
        def load_asset(path: str):
            assert path in {
                "/Engine/BasicShapes/Cube.Cube",
                "/Engine/BasicShapes/Cylinder.Cylinder",
            }
            return mesh

    subsystem = Subsystem()

    class Sequence:
        @staticmethod
        def get_binding_id(binding: Binding) -> str:
            return binding.binding_id

    class BlueprintLibrary:
        force_update_count = 0

        @classmethod
        def force_update(cls) -> None:
            cls.force_update_count += 1

        @staticmethod
        def get_bound_objects(binding_id: str):
            binding = next(
                item for item in subsystem.bindings if item.binding_id == binding_id
            )
            return [binding.live_actor]

    unreal = ModuleType("unreal")
    unreal.StaticMesh = StaticMesh
    unreal.StaticMeshActor = StaticMeshActor
    unreal.MovieScene3DTransformTrack = MovieScene3DTransformTrack
    unreal.EditorAssetLibrary = EditorAssetLibrary
    unreal.LevelSequenceEditorBlueprintLibrary = BlueprintLibrary
    unreal.Vector = lambda *values: values
    unreal.Quat = Quat
    unreal.load_class = lambda outer, path: StaticMeshActor
    monkeypatch.setitem(sys.modules, "unreal", unreal)

    namespace = {"__name__": "cutsceneai_generated_importer"}
    exec(script, namespace)
    sequence = Sequence()

    actor = unreal_plan.sequences[0].actors[0].model_dump(mode="json")
    actor_binding = namespace["_add_actor"](sequence, subsystem, actor)
    set_piece = unreal_plan.sequences[0].set_pieces[0].model_dump(mode="json")
    set_binding = namespace["_add_set_piece"](sequence, subsystem, set_piece)

    assert actor_binding.display_name == "ACT_Mina"
    assert actor_binding.template.label == "ACT_Mina"
    assert actor_binding.template.location == (-100.0, -150.0, 90.0)
    assert actor_binding.template.scale == (0.45, 0.45, 1.8)
    assert actor_binding.template.component.mesh is mesh
    assert actor_binding.live_actor.label == "ACT_Mina"
    assert actor_binding.live_actor.location == (-100.0, -150.0, 90.0)
    assert actor_binding.live_actor.scale == (0.45, 0.45, 1.8)
    assert actor_binding.live_actor.component.mesh is mesh
    assert len(actor_binding.tracks) == 1
    assert isinstance(actor_binding.tracks[0], MovieSceneSpawnTrack)
    assert set_binding.display_name == "SET_Floor"
    assert set_binding.template.component.mesh is mesh
    assert set_binding.live_actor.component.mesh is mesh
    assert len(set_binding.tracks) == 1
    assert isinstance(set_binding.tracks[0], MovieSceneSpawnTrack)
    assert BlueprintLibrary.force_update_count == 2
    assert subsystem.saved == [actor_binding, set_binding]


def test_importer_configures_template_and_live_skeletal_character(
    cir_project: Project,
    monkeypatch,
) -> None:
    asset_path = "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple.SKM_Manny_Simple"
    cir_project.characters[0].asset_uri = asset_path
    plan = compile_project(cir_project)
    script = render_unreal_import_script(plan)

    class SkeletalMesh:
        pass

    class SkeletalMeshComponent:
        def __init__(self) -> None:
            self.mesh = None

        def set_skeletal_mesh_asset(self, mesh) -> None:
            self.mesh = mesh

    class SkeletalMeshActor:
        def __init__(self) -> None:
            self.component = SkeletalMeshComponent()
            self.label = ""
            self.location = None
            self.rotation = None
            self.scale = None

        def get_editor_property(self, name: str):
            assert name == "skeletal_mesh_component"
            return self.component

        def set_actor_label(self, value: str) -> None:
            self.label = value

        def set_actor_location(self, value, sweep: bool, teleport: bool) -> None:
            self.location = value

        def set_actor_rotation(self, value, teleport: bool) -> None:
            self.rotation = value

        def set_actor_scale3d(self, value) -> None:
            self.scale = value

    class MovieScene3DTransformTrack:
        pass

    class MovieSceneSpawnTrack:
        pass

    class Binding:
        def __init__(self) -> None:
            self.binding_id = "skeletal-binding"
            self.template = SkeletalMeshActor()
            self.live_actor = SkeletalMeshActor()
            self.display_name = ""
            self.tracks = [MovieScene3DTransformTrack(), MovieSceneSpawnTrack()]

        def get_object_template(self):
            return self.template

        def set_display_name(self, value: str) -> None:
            self.display_name = value

        def find_tracks_by_exact_type(self, track_type):
            return [track for track in self.tracks if type(track) is track_type]

        def remove_track(self, track) -> None:
            self.tracks.remove(track)

    binding = Binding()

    class Subsystem:
        def __init__(self) -> None:
            self.saved = []

        def add_spawnable_from_class(self, sequence, actor_class):
            assert actor_class is SkeletalMeshActor
            return binding

        def save_default_spawnable_state(self, value) -> None:
            self.saved.append(value)

    subsystem = Subsystem()

    class Sequence:
        @staticmethod
        def get_binding_id(value: Binding) -> str:
            assert value is binding
            return binding.binding_id

    class BlueprintLibrary:
        @staticmethod
        def force_update() -> None:
            return None

        @staticmethod
        def get_bound_objects(binding_id: str):
            assert binding_id == binding.binding_id
            return [binding.live_actor]

    mesh = SkeletalMesh()

    class EditorAssetLibrary:
        @staticmethod
        def load_asset(path: str):
            assert path == asset_path
            return mesh

    class Quat:
        def __init__(self, *values) -> None:
            self.values = values

        def rotator(self):
            return self.values

    unreal = ModuleType("unreal")
    unreal.SkeletalMesh = SkeletalMesh
    unreal.SkeletalMeshActor = SkeletalMeshActor
    unreal.MovieScene3DTransformTrack = MovieScene3DTransformTrack
    unreal.EditorAssetLibrary = EditorAssetLibrary
    unreal.LevelSequenceEditorBlueprintLibrary = BlueprintLibrary
    unreal.Vector = lambda *values: values
    unreal.Quat = Quat
    unreal.load_class = lambda outer, path: SkeletalMeshActor
    monkeypatch.setitem(sys.modules, "unreal", unreal)

    namespace = {"__name__": "cutsceneai_generated_importer"}
    exec(script, namespace)
    actor = next(
        item for item in plan.sequences[0].actors if item.source_entity_id == "mina"
    ).model_dump(mode="json")

    result = namespace["_add_actor"](Sequence(), subsystem, actor)

    assert result is binding
    assert binding.display_name == "ACT_Mina"
    assert binding.template.label == "ACT_Mina"
    assert binding.template.location == (-100.0, -150.0, 0.0)
    assert binding.template.component.mesh is mesh
    assert binding.live_actor.label == "ACT_Mina"
    assert binding.live_actor.location == (-100.0, -150.0, 0.0)
    assert binding.live_actor.component.mesh is mesh
    assert len(binding.tracks) == 1
    assert isinstance(binding.tracks[0], MovieSceneSpawnTrack)
    assert subsystem.saved == [binding]


def test_importer_configures_template_and_live_58_camera_when_template_component_is_missing(
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
            if name == "lens_settings":
                self.lens_settings = value
            elif name == "current_focal_length":
                self.current_focal_length = value
            else:
                raise AssertionError(f"Unexpected camera property: {name}")

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

    class MovieScene3DTransformTrack:
        pass

    class MovieSceneSpawnTrack:
        pass

    class Binding:
        def __init__(self, template) -> None:
            self.template = template
            self.display_name = ""
            self.tracks = [MovieScene3DTransformTrack(), MovieSceneSpawnTrack()]

        def get_object_template(self):
            return self.template

        def set_display_name(self, value: str) -> None:
            self.display_name = value

        def find_tracks_by_exact_type(self, track_type):
            return [track for track in self.tracks if type(track) is track_type]

        def remove_track(self, track) -> None:
            self.tracks.remove(track)

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
            assert template_actor.transform_calls
            assert live_actor.transform_calls
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
    unreal.MovieScene3DTransformTrack = MovieScene3DTransformTrack
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
    assert len(binding.tracks) == 1
    assert isinstance(binding.tracks[0], MovieSceneSpawnTrack)
    assert template_actor.label == "CAM_ShotEstablishing"
    assert template_actor.transform_calls == [
        ("location", ((-675.0, -25.0, 160.0), False, True)),
        ("rotation", ((0.0, 0.0, 0.0, 1.0), True)),
        ("scale", ((1.0, 1.0, 1.0),)),
    ]
    assert live_actor.label == "CAM_ShotEstablishing"
    assert live_actor.transform_calls == template_actor.transform_calls
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
