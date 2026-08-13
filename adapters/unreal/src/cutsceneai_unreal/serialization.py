import json

from .models import UnrealExportPlan
from .performance_models import UnrealPerformanceMapping


def render_unreal_plan(plan: UnrealExportPlan) -> str:
    return json.dumps(plan.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"


def render_unreal_performance_mapping(mapping: UnrealPerformanceMapping) -> str:
    return json.dumps(mapping.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
