import base64
import json
import re
from pathlib import Path

from cutsceneai_cir import Project
from cutsceneai_unity import (
    UNITY_EDITOR_SCRIPT_FILENAME,
    compile_project,
    render_unity_editor_script,
)

UNITY_ROOT = Path(__file__).resolve().parents[1]


def _embedded_plan(script: str) -> dict[str, object]:
    match = re.search(r'private const string PlanBase64 = "([A-Za-z0-9+/=]+)";', script)
    assert match is not None
    return json.loads(base64.b64decode(match.group(1)).decode("utf-8"))


def test_editor_script_is_deterministic_self_contained_and_non_destructive(
    cir_project: Project,
) -> None:
    plan = compile_project(cir_project)
    first = render_unity_editor_script(plan)
    second = render_unity_editor_script(plan.model_copy(deep=True))

    assert first == second
    assert "__PLAN_BASE64__" not in first
    assert _embedded_plan(first) == plan.model_dump(mode="json")
    assert "Refusing to replace existing Timeline asset" in first
    assert "Refusing to replace existing Scene asset" in first
    assert "Refusing to replace existing semantic metadata asset" in first
    assert "AssetDatabase.LoadAssetAtPath<AnimationClip>" in first
    assert "AssetDatabase.LoadAssetAtPath<AudioClip>" in first
    assert "AssetDatabase.AddObjectToAsset" not in first
    assert 'private const string MetadataSuffix = ".semantics.json";' in first
    assert "File.WriteAllText(" in first
    assert "AssetDatabase.LoadAssetAtPath<TextAsset>(metadataPath)" in first
    assert "placeholder = playable.clip == null" in first
    assert UNITY_EDITOR_SCRIPT_FILENAME == "CutSceneAISemanticMarker.cs"
    assert "public sealed class CutSceneAISemanticMarker" in first
    assert "Keep this file named CutSceneAISemanticMarker.cs" in first
    import_index = first.index("AssetDatabase.ImportAsset(")
    save_index = first.rindex("AssetDatabase.SaveAssets();", 0, import_index)
    scene_save_index = first.index("EditorSceneManager.SaveScene(", import_index)
    assert save_index < import_index < scene_save_index
    assert "BindSavedTracks(savedTimeline, director, actors, cameras);" in first
    assert "Unity could not reload the saved Timeline asset" in first
    assert "Unity could not import semantic metadata asset" in first


def test_editor_script_builds_native_tracks_and_engine_readback(
    cir_project: Project,
) -> None:
    script = render_unity_editor_script(compile_project(cir_project))

    required_surfaces = [
        "TimelineAsset",
        "PlayableDirector",
        "AnimationTrack",
        "AnimationPlayableAsset",
        "AudioTrack",
        "AudioPlayableAsset",
        "ActivationTrack",
        "CutSceneAISemanticMarker",
        "CreateMarker<CutSceneAISemanticMarker>",
        "GetOutputTracks()",
        "Application.unityVersion",
        "cir_fingerprint_sha256",
        "CutSceneAIReadbacks",
        "Unknown CutSceneAI performance marker",
        "Duplicate CutSceneAI dialogue marker",
        "Unmapped native camera ActivationTrack",
    ]
    for surface in required_surfaces:
        assert surface in script


def test_hostile_project_text_never_enters_csharp_source(cir_project: Project) -> None:
    hostile = 'Office "Dialogue"; } public static void Attack() { //'
    cir_project.name = hostile
    script = render_unity_editor_script(compile_project(cir_project))

    assert hostile not in script
    assert _embedded_plan(script)["project_name"] == hostile


def test_committed_editor_script_matches_renderer(cir_project: Project) -> None:
    expected = render_unity_editor_script(compile_project(cir_project))
    actual = (UNITY_ROOT / "examples" / UNITY_EDITOR_SCRIPT_FILENAME).read_text(
        encoding="utf-8"
    )
    assert actual == expected
