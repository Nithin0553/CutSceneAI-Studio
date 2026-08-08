import argparse
import json
from pathlib import Path

from cutsceneai_cir import validate_project
from cutsceneai_parity import (
    compile_semantics,
    render_engine_readback_json_schema,
    render_parity_report_json_schema,
    render_timeline_semantics,
    render_timeline_semantics_json_schema,
)


ROOT = Path(__file__).resolve().parents[2]
CIR_EXAMPLE = ROOT / "cir" / "examples" / "office-dialogue.cir.json"
SCHEMA_ROOT = ROOT / "parity" / "schemas"
EXAMPLE_OUTPUT = ROOT / "parity" / "examples" / "office-dialogue.semantics.json"


def expected_artifacts() -> dict[Path, str]:
    payload = json.loads(CIR_EXAMPLE.read_text(encoding="utf-8"))
    semantics = compile_semantics(validate_project(payload))
    return {
        SCHEMA_ROOT / "timeline-semantics-v0.1.schema.json": (
            render_timeline_semantics_json_schema()
        ),
        SCHEMA_ROOT / "engine-readback-v0.1.schema.json": (
            render_engine_readback_json_schema()
        ),
        SCHEMA_ROOT / "parity-report-v0.1.schema.json": (
            render_parity_report_json_schema()
        ),
        EXAMPLE_OUTPUT: render_timeline_semantics(semantics),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export deterministic cross-engine parity v0.1 artifacts."
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
                print(f"Parity artifact is stale: {path}")
            return 1
        print("Parity artifacts are current.")
        return 0

    for path, content in artifacts.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
