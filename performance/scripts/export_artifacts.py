from __future__ import annotations

import argparse
from pathlib import Path

from cutsceneai_performance import render_performance_package_json_schema

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_OUTPUT = (
    ROOT / "performance" / "schemas" / "performance-package-v0.1.schema.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export deterministic Generated Performance Package v0.1 artifacts."
    )
    parser.add_argument("--check", action="store_true", help="Fail if artifacts drift.")
    args = parser.parse_args()
    expected = render_performance_package_json_schema()
    if args.check:
        if (
            not SCHEMA_OUTPUT.exists()
            or SCHEMA_OUTPUT.read_text(encoding="utf-8") != expected
        ):
            print(f"Performance artifact is stale: {SCHEMA_OUTPUT}")
            return 1
        print("Generated Performance Package artifacts are current.")
        return 0

    SCHEMA_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    SCHEMA_OUTPUT.write_text(expected, encoding="utf-8")
    print(f"Wrote {SCHEMA_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
