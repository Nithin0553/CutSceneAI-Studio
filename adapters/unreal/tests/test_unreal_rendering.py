from pathlib import Path

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
    assert "unreal.MovieSceneCameraCutTrack" in script
    assert "sequence.add_marked_frame_to_sequence" in script
    assert "save_loaded_asset" in script
    assert "delete_asset" not in script
    assert "Refusing to replace existing asset" in script


def test_importer_escapes_arbitrary_project_text(cir_project: Project) -> None:
    cir_project.name = "Office ''' Dialogue with \\\\ paths and \"quotes\""
    script = render_unreal_import_script(compile_project(cir_project))

    compile(script, "hostile_text_import.py", "exec")
    assert "__PLAN_JSON__" not in script


def test_committed_importer_matches_renderer(unreal_plan: UnrealExportPlan) -> None:
    assert IMPORTER.read_text(encoding="utf-8") == render_unreal_import_script(
        unreal_plan
    )
