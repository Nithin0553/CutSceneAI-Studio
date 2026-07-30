from __future__ import annotations

import json
from hashlib import sha256

from .models import AssetIndex, AssetResolutionPlan


def _canonical_json_bytes(value: AssetIndex | AssetResolutionPlan) -> bytes:
    return json.dumps(
        value.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def asset_index_sha256(index: AssetIndex) -> str:
    """Return the SHA-256 of the canonical Asset Index JSON representation."""

    return sha256(_canonical_json_bytes(index)).hexdigest()


def render_asset_index(index: AssetIndex) -> str:
    return (
        json.dumps(
            index.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True
        )
        + "\n"
    )


def render_asset_resolution_plan(plan: AssetResolutionPlan) -> str:
    return (
        json.dumps(
            plan.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True
        )
        + "\n"
    )
