from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from collections.abc import Sequence

from cutsceneai_cir import Project, validate_project

from .errors import DialogueError
from .planning import plan_project
from .serialization import render_dialogue_bundle, render_dialogue_plan
from .service import RecordedAudioInput, build_recorded_bundle


def _project(path: Path) -> Project:
    return validate_project(json.loads(path.read_text(encoding="utf-8")))


def _recordings(values: list[str]) -> dict[str, RecordedAudioInput]:
    recordings: dict[str, RecordedAudioInput] = {}
    for value in values:
        cue_id, separator, raw_path = value.partition("=")
        if not separator or not cue_id or not raw_path:
            raise DialogueError("Recordings must use CUE_ID=PATH syntax.")
        path = Path(raw_path)
        if cue_id in recordings:
            raise DialogueError(f"Recording for '{cue_id}' was supplied more than once.")
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise DialogueError(f"Could not read recording '{path}': {exc}") from exc
        recordings[cue_id] = RecordedAudioInput(data=data, filename=path.name)
    return recordings


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cutsceneai-dialogue")
    commands = parser.add_subparsers(dest="command", required=True)

    plan = commands.add_parser("plan", help="List deterministic dialogue cues in a CIR project.")
    plan.add_argument("project", type=Path)
    plan.add_argument("--output", type=Path)

    recorded = commands.add_parser(
        "bundle-recorded", help="Create a portable bundle from recorded WAV files."
    )
    recorded.add_argument("project", type=Path)
    recorded.add_argument(
        "--recording",
        action="append",
        default=[],
        metavar="CUE_ID=PATH",
        help="Repeat once for every cue returned by the plan command.",
    )
    recorded.add_argument("--output", type=Path, required=True)
    recorded.add_argument("--replace-existing", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        project = _project(args.project)
        if args.command == "plan":
            rendered = render_dialogue_plan(plan_project(project))
            if args.output is None:
                sys.stdout.write(rendered)
            else:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(rendered, encoding="utf-8")
            return 0

        bundle = build_recorded_bundle(
            project,
            _recordings(args.recording),
            replace_existing=args.replace_existing,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(render_dialogue_bundle(bundle))
        return 0
    except (DialogueError, OSError, ValueError) as exc:
        print(f"cutsceneai-dialogue: {exc}", file=sys.stderr)
        return 2
