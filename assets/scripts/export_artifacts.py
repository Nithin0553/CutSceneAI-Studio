import argparse
import json
from pathlib import Path

from cutsceneai_assets import (
    AssetIndex,
    render_asset_index_json_schema,
    render_asset_resolution_json_schema,
    render_asset_resolution_plan,
    resolve_project,
)
from cutsceneai_cir import validate_project

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "assets" / "examples" / "unreal-project.asset-index.json"
OFFICE = ROOT / "cir" / "examples" / "office-dialogue.cir.json"
OUTDOOR = ROOT / "assets" / "examples" / "outdoor-action.cir.json"
INDEX_SCHEMA = ROOT / "assets" / "schemas" / "asset-index-v0.1.schema.json"
RESOLUTION_SCHEMA = ROOT / "assets" / "schemas" / "asset-resolution-v0.1.schema.json"
OFFICE_RESOLUTION = (
    ROOT / "assets" / "examples" / "office-dialogue.asset-resolution.json"
)
OUTDOOR_RESOLUTION = (
    ROOT / "assets" / "examples" / "outdoor-action.asset-resolution.json"
)


def _load_project(path: Path):
    return validate_project(json.loads(path.read_text(encoding="utf-8")))


def expected_artifacts() -> dict[Path, str]:
    index = AssetIndex.model_validate(json.loads(INDEX.read_text(encoding="utf-8")))
    return {
        INDEX_SCHEMA: render_asset_index_json_schema(),
        RESOLUTION_SCHEMA: render_asset_resolution_json_schema(),
        OFFICE_RESOLUTION: render_asset_resolution_plan(
            resolve_project(_load_project(OFFICE), index)
        ),
        OUTDOOR_RESOLUTION: render_asset_resolution_plan(
            resolve_project(_load_project(OUTDOOR), index)
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export deterministic Asset Resolver v0.1 artifacts."
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
                print(f"Asset Resolver artifact is stale: {path}")
            return 1
        print("Asset Resolver artifacts are current.")
        return 0

    for path, content in artifacts.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
