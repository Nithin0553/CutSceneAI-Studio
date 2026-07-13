import argparse
import json
from pathlib import Path

from cutsceneai_cir import validate_project
from cutsceneai_preview import (
    compile_project,
    render_preview_json_schema,
    render_preview_manifest,
)


ROOT = Path(__file__).resolve().parents[2]
CIR_EXAMPLE = ROOT / "cir" / "examples" / "office-dialogue.cir.json"
SCHEMA_OUTPUT = ROOT / "preview" / "schemas" / "preview-v0.1.schema.json"
EXAMPLE_OUTPUT = ROOT / "preview" / "examples" / "office-dialogue.preview.json"


def expected_artifacts() -> dict[Path, str]:
    payload = json.loads(CIR_EXAMPLE.read_text(encoding="utf-8"))
    manifest = compile_project(validate_project(payload))
    return {
        SCHEMA_OUTPUT: render_preview_json_schema(),
        EXAMPLE_OUTPUT: render_preview_manifest(manifest),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export deterministic Preview v0.1 artifacts."
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
                print(f"Preview artifact is stale: {path}")
            return 1
        print("Preview artifacts are current.")
        return 0

    for path, content in artifacts.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
