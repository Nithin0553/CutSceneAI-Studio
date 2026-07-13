from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cutsceneai_cir import render_project_json_schema, write_project_json_schema


DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[1] / "schemas" / "cir-v0.1.schema.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export the CutSceneAI CIR 0.1 JSON Schema."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Schema destination (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when the committed schema is missing or differs from the model.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = args.output.resolve()

    if args.check:
        expected = render_project_json_schema()
        if not output.exists():
            print(f"Schema artifact is missing: {output}", file=sys.stderr)
            return 1
        if output.read_text(encoding="utf-8") != expected:
            print(
                "CIR schema artifact is stale. Run "
                "`python cir/scripts/export_schema.py` and commit the result.",
                file=sys.stderr,
            )
            return 1
        print(f"CIR schema is current: {output}")
        return 0

    written = write_project_json_schema(output)
    print(f"Wrote CIR schema: {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
