import argparse
import json
from pathlib import Path

from cutsceneai_cir import validate_project
from cutsceneai_dialogue import (
    plan_project,
    render_dialogue_plan,
    render_dialogue_manifest_json_schema,
    render_dialogue_plan_json_schema,
)


ROOT = Path(__file__).resolve().parents[2]
CIR_EXAMPLE = ROOT / "cir" / "examples" / "office-dialogue.cir.json"
PLAN_SCHEMA_OUTPUT = ROOT / "dialogue" / "schemas" / "dialogue-plan-v0.1.schema.json"
MANIFEST_SCHEMA_OUTPUT = ROOT / "dialogue" / "schemas" / "dialogue-manifest-v0.1.schema.json"
EXAMPLE_OUTPUT = ROOT / "dialogue" / "examples" / "office-dialogue.dialogue-plan.json"


def expected_artifacts() -> dict[Path, str]:
    payload = json.loads(CIR_EXAMPLE.read_text(encoding="utf-8"))
    plan = plan_project(validate_project(payload))
    return {
        PLAN_SCHEMA_OUTPUT: render_dialogue_plan_json_schema(),
        MANIFEST_SCHEMA_OUTPUT: render_dialogue_manifest_json_schema(),
        EXAMPLE_OUTPUT: render_dialogue_plan(plan),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export deterministic Dialogue Engine v0.1 artifacts."
    )
    parser.add_argument("--check", action="store_true", help="Fail if committed artifacts drift.")
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
                print(f"Dialogue artifact is stale: {path}")
            return 1
        print("Dialogue artifacts are current.")
        return 0

    for path, content in artifacts.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
