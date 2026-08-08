import json

from .models import UnityAssetMap, UnityExportPlan


def render_unity_plan(plan: UnityExportPlan) -> str:
    return json.dumps(plan.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"


def render_unity_asset_map(asset_map: UnityAssetMap) -> str:
    return (
        json.dumps(asset_map.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    )
