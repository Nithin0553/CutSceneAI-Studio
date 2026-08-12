from __future__ import annotations

import argparse
import json
from pathlib import Path

from cutsceneai_cir import validate_project
from cutsceneai_performance import (
    GenerationModelConfig,
    PerformanceCompilerConfig,
    compile_generation_plan,
    render_generation_plan,
    render_generation_plan_json_schema,
    render_performance_package_json_schema,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_OUTPUT = (
    ROOT / "performance" / "schemas" / "performance-package-v0.1.schema.json"
)
PLAN_SCHEMA_OUTPUT = (
    ROOT / "performance" / "schemas" / "generation-plan-v0.1.schema.json"
)
EXAMPLE_OUTPUT = (
    ROOT / "performance" / "examples" / "office-dialogue.generation-plan.json"
)
CIR_EXAMPLE = ROOT / "cir" / "examples" / "office-dialogue.cir.json"


def _example_config() -> PerformanceCompilerConfig:
    return PerformanceCompilerConfig(
        body=GenerationModelConfig(
            provider="research",
            model="body-model",
            model_revision="checkpoint-pending",
            prompt_version="body-v1",
        ),
        facial=GenerationModelConfig(
            provider="research",
            model="face-model",
            model_revision="checkpoint-pending",
            prompt_version="face-v1",
        ),
        camera=GenerationModelConfig(
            provider="research",
            model="camera-model",
            model_revision="checkpoint-pending",
            prompt_version="camera-v1",
        ),
    )


def expected_artifacts() -> dict[Path, str]:
    project = validate_project(json.loads(CIR_EXAMPLE.read_text(encoding="utf-8")))
    plan = compile_generation_plan(project, config=_example_config())
    return {
        SCHEMA_OUTPUT: render_performance_package_json_schema(),
        PLAN_SCHEMA_OUTPUT: render_generation_plan_json_schema(),
        EXAMPLE_OUTPUT: render_generation_plan(plan),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export deterministic Generated Performance Package v0.1 artifacts."
    )
    parser.add_argument("--check", action="store_true", help="Fail if artifacts drift.")
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
                print(f"Performance artifact is stale: {path}")
            return 1
        print("Generated Performance Package artifacts are current.")
        return 0

    for path, content in artifacts.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
