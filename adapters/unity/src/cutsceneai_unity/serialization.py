import json

from .models import UnityAssetMap, UnityExportPlan
from .native_models import UnityNativeRealizationTarget
from .performance_models import UnityPerformanceMapping


def render_unity_plan(plan: UnityExportPlan) -> str:
    return json.dumps(plan.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"


def render_unity_asset_map(asset_map: UnityAssetMap) -> str:
    return (
        json.dumps(asset_map.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    )


def render_unity_performance_mapping(mapping: UnityPerformanceMapping) -> str:
    return json.dumps(mapping.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"


def render_unity_native_target(target: UnityNativeRealizationTarget) -> str:
    return json.dumps(target.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
