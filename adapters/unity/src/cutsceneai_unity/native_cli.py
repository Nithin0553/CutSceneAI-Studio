from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TypeVar

from cutsceneai_performance import (
    load_performance_bundle,
    render_native_evidence_collector_script,
)
from pydantic import BaseModel

from .models import UnityExportPlan
from .native import (
    compile_unity_native_performance_package,
    render_unity_native_performance_package,
)
from .native_models import UnityNativeRealizationTarget
from .performance_models import UnityPerformanceMapping


ModelT = TypeVar("ModelT", bound=BaseModel)


def _model(path: Path, model: type[ModelT]) -> ModelT:
    return model.model_validate(json.loads(path.read_bytes()))


def compile_native_harness(
    *,
    bundle_path: Path,
    plan_path: Path,
    mapping_path: Path,
    target_path: Path,
    output_path: Path,
) -> Path:
    """Compile verified Unity inputs into a no-replacement native harness."""

    bundle = load_performance_bundle(bundle_path.read_bytes())
    package = compile_unity_native_performance_package(
        bundle,
        plan=_model(plan_path, UnityExportPlan),
        mapping=_model(mapping_path, UnityPerformanceMapping),
        target=_model(target_path, UnityNativeRealizationTarget),
    )
    rendered = render_unity_native_performance_package(
        package,
        evidence_collector_script=render_native_evidence_collector_script(),
    )
    output = output_path.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("xb") as stream:
            stream.write(rendered)
    except FileExistsError as exc:
        raise FileExistsError(f"refusing to replace existing output: {output}") from exc
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compile a CutSceneAI Unity native-performance harness."
    )
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    output = compile_native_harness(
        bundle_path=args.bundle,
        plan_path=args.plan,
        mapping_path=args.mapping,
        target_path=args.target,
        output_path=args.output,
    )
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
