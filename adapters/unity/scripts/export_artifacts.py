import argparse
import json
from pathlib import Path

from cutsceneai_cir import validate_project
from cutsceneai_parity import compile_semantics
from cutsceneai_unity import (
    UnityAnimationAsset,
    UnityAssetMap,
    UnityAudioAsset,
    UnityEntityAsset,
    compile_project,
    render_unity_asset_map,
    render_unity_asset_map_json_schema,
    render_unity_editor_script,
    render_unity_plan,
    render_unity_plan_json_schema,
    render_unity_performance_mapping_json_schema,
)

ROOT = Path(__file__).resolve().parents[3]
CIR_EXAMPLE = ROOT / "cir" / "examples" / "office-dialogue.cir.json"
UNITY_ROOT = ROOT / "adapters" / "unity"


def _example_asset_map(project) -> UnityAssetMap:
    semantics = compile_semantics(project)
    scene = semantics.scenes[0]
    return UnityAssetMap(
        project_id=project.id,
        entities=[
            UnityEntityAsset(
                source_entity_id="mina",
                prefab_path="Assets/CutSceneAI/Characters/Mina.prefab",
            ),
            UnityEntityAsset(
                source_entity_id="arjun",
                prefab_path="Assets/CutSceneAI/Characters/Arjun.prefab",
            ),
        ],
        animations=[
            UnityAnimationAsset(
                cue_id=cue.cue_id,
                asset_path=(
                    "Assets/CutSceneAI/Animations/MinaIdle.anim"
                    if cue.actor_binding_id == "actor:mina"
                    else "Assets/CutSceneAI/Animations/ArjunIdle.anim"
                ),
            )
            for cue in scene.performance_cues
        ],
        audio=[
            UnityAudioAsset(
                cue_id=scene.dialogue_cues[0].cue_id,
                asset_path="Assets/CutSceneAI/Audio/MinaConfrontation.wav",
                end_frame=178,
            ),
            UnityAudioAsset(
                cue_id=scene.dialogue_cues[1].cue_id,
                asset_path="Assets/CutSceneAI/Audio/ArjunResponse.wav",
                end_frame=302,
            ),
        ],
    )


def expected_artifacts() -> dict[Path, str]:
    payload = json.loads(CIR_EXAMPLE.read_text(encoding="utf-8"))
    project = validate_project(payload)
    plan = compile_project(project)
    return {
        UNITY_ROOT / "schemas" / "unity-timeline-plan-v0.1.schema.json": (
            render_unity_plan_json_schema()
        ),
        UNITY_ROOT / "schemas" / "unity-asset-map-v0.1.schema.json": (
            render_unity_asset_map_json_schema()
        ),
        UNITY_ROOT / "schemas" / "unity-performance-mapping-v0.1.schema.json": (
            render_unity_performance_mapping_json_schema()
        ),
        UNITY_ROOT / "examples" / "office-dialogue.unity.json": (
            render_unity_plan(plan)
        ),
        UNITY_ROOT / "examples" / "office-dialogue.asset-map.example.json": (
            render_unity_asset_map(_example_asset_map(project))
        ),
        UNITY_ROOT / "examples" / "CutSceneAISemanticMarker.cs": (
            render_unity_editor_script(plan)
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export deterministic Unity Adapter v0.1 artifacts."
    )
    parser.add_argument(
        "--check", action="store_true", help="Fail if committed artifacts drift."
    )
    args = parser.parse_args()
    artifacts = expected_artifacts()
    if args.check:
        stale = [
            path
            for path, expected in artifacts.items()
            if not path.exists() or path.read_text(encoding="utf-8") != expected
        ]
        if stale:
            for path in stale:
                print(f"Unity Adapter artifact is stale: {path}")
            return 1
        print("Unity Adapter artifacts are current.")
        return 0

    for path, content in artifacts.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
