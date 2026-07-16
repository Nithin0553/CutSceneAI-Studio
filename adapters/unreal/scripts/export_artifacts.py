import argparse
import json
from pathlib import Path

from cutsceneai_cir import validate_project
from cutsceneai_unreal import (
    compile_project,
    render_unreal_import_script,
    render_unreal_plan,
    render_unreal_plan_json_schema,
)


ROOT = Path(__file__).resolve().parents[3]
CIR_EXAMPLE = ROOT / "cir" / "examples" / "office-dialogue.cir.json"
SCHEMA_OUTPUT = (
    ROOT / "adapters" / "unreal" / "schemas" / "unreal-sequencer-plan-v0.3.schema.json"
)
EXAMPLE_OUTPUT = (
    ROOT / "adapters" / "unreal" / "examples" / "office-dialogue.unreal.json"
)
IMPORTER_OUTPUT = (
    ROOT / "adapters" / "unreal" / "examples" / "import_office_dialogue.py"
)


def expected_artifacts() -> dict[Path, str]:
    payload = json.loads(CIR_EXAMPLE.read_text(encoding="utf-8"))
    plan = compile_project(validate_project(payload))
    return {
        SCHEMA_OUTPUT: render_unreal_plan_json_schema(),
        EXAMPLE_OUTPUT: render_unreal_plan(plan),
        IMPORTER_OUTPUT: render_unreal_import_script(plan),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export deterministic Unreal Adapter v0.3 artifacts."
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
                print(f"Unreal Adapter artifact is stale: {path}")
            return 1
        print("Unreal Adapter artifacts are current.")
        return 0

    for path, content in artifacts.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
