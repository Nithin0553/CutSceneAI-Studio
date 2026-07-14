import json

from .models import UnrealExportPlan


def render_unreal_plan(plan: UnrealExportPlan) -> str:
    return json.dumps(plan.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
