import base64
import json
import re
from pathlib import Path

from cutsceneai_cir import Project
from cutsceneai_unity import compile_project, render_unity_editor_script


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
    assert "AssetDatabase.LoadAssetAtPath<AnimationClip>" in first
    assert "AssetDatabase.LoadAssetAtPath<AudioClip>" in first


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
    actual = (UNITY_ROOT / "examples" / "CutSceneAIGeneratedTimeline.cs").read_text(
        encoding="utf-8"
    )
    assert actual == expected
