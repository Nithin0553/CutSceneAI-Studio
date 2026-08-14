from __future__ import annotations

import argparse
import json
from pathlib import Path

from cutsceneai_cir import validate_project

from .comparison import verify_readbacks
from .compiler import compile_semantics
from .experiment import verify_generated_performance_experiment
from .experiment_models import (
    GeneratedPerformanceAttemptEvidence,
    GeneratedPerformanceExperimentPlan,
)
from .models import EngineName, EngineTimelineReadback
from .serialization import (
    render_generated_performance_experiment_report,
    render_parity_report,
    render_timeline_semantics,
)


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_or_print(content: str, output: Path | None) -> None:
    if output is None:
        print(content, end="")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")


def _expected(args: argparse.Namespace) -> int:
    payload = _load_json(args.cir)
    if not isinstance(payload, dict):
        raise ValueError("CIR JSON must be an object.")
    semantics = compile_semantics(validate_project(payload))
    _write_or_print(render_timeline_semantics(semantics), args.output)
    return 0


def _verify(args: argparse.Namespace) -> int:
    payload = _load_json(args.cir)
    if not isinstance(payload, dict):
        raise ValueError("CIR JSON must be an object.")
    readbacks = [
        EngineTimelineReadback.model_validate(_load_json(path))
        for path in args.readback
    ]
    report = verify_readbacks(
        validate_project(payload),
        readbacks,
        tolerance_frames=args.tolerance_frames,
        require_animation=args.require_animation,
        require_facial=args.require_facial,
        require_camera=args.require_camera,
        require_audio=args.require_audio,
        required_engines=(
            (EngineName.UNREAL, EngineName.UNITY) if args.require_both_engines else ()
        ),
    )
    _write_or_print(render_parity_report(report), args.output)
    return 0 if report.equivalent else 1


def _verify_experiment(args: argparse.Namespace) -> int:
    plan = GeneratedPerformanceExperimentPlan.model_validate(_load_json(args.plan))
    attempts = [
        GeneratedPerformanceAttemptEvidence.model_validate(_load_json(path))
        for path in args.attempt
    ]
    report = verify_generated_performance_experiment(plan, attempts)
    _write_or_print(render_generated_performance_experiment_report(report), args.output)
    return 0 if report.gate_passed else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compile CIR semantics and verify engine timeline readbacks."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    expected = commands.add_parser(
        "expected", help="Compile CIR into canonical timeline semantics."
    )
    expected.add_argument("cir", type=Path)
    expected.add_argument("--output", "-o", type=Path)
    expected.set_defaults(handler=_expected)

    verify = commands.add_parser(
        "verify", help="Verify one or more engine readbacks against CIR."
    )
    verify.add_argument("cir", type=Path)
    verify.add_argument("--readback", type=Path, action="append", required=True)
    verify.add_argument("--tolerance-frames", type=int, default=1)
    verify.add_argument("--require-animation", action="store_true")
    verify.add_argument("--require-facial", action="store_true")
    verify.add_argument("--require-camera", action="store_true")
    verify.add_argument("--require-audio", action="store_true")
    verify.add_argument("--require-both-engines", action="store_true")
    verify.add_argument("--output", "-o", type=Path)
    verify.set_defaults(handler=_verify)

    experiment = commands.add_parser(
        "experiment-verify",
        help="Verify reliability, repeatability, portability, and native evidence.",
    )
    experiment.add_argument("plan", type=Path)
    experiment.add_argument("--attempt", type=Path, action="append", default=[])
    experiment.add_argument("--output", "-o", type=Path)
    experiment.set_defaults(handler=_verify_experiment)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return args.handler(args)
