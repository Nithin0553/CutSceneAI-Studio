import json

from .models import EngineTimelineReadback, ParityReport, TimelineSemantics


def _render(value: TimelineSemantics | EngineTimelineReadback | ParityReport) -> str:
    return json.dumps(value.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"


def render_timeline_semantics(semantics: TimelineSemantics) -> str:
    return _render(semantics)


def render_engine_readback(readback: EngineTimelineReadback) -> str:
    return _render(readback)


def render_parity_report(report: ParityReport) -> str:
    return _render(report)
