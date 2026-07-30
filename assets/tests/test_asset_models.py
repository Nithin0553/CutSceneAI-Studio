from copy import deepcopy

import pytest
from cutsceneai_assets import (
    AssetIndex,
    AssetKind,
    AssetValidationError,
    AssetValidationIssue,
    render_asset_index,
    validate_asset_index_model,
)
from pydantic import ValidationError


def test_asset_index_is_strict_and_typed(asset_index: AssetIndex) -> None:
    assert asset_index.schema_version == "0.1.0"
    assert asset_index.target_engine == "Unreal Engine"
    assert asset_index.assets[0].kind is AssetKind.ENVIRONMENT_SET
    assert asset_index.model_json_schema()["additionalProperties"] is False
    assert (
        AssetIndex.model_validate_json(render_asset_index(asset_index)) == asset_index
    )


def test_asset_validation_issue_has_api_safe_shape() -> None:
    issue = AssetValidationIssue(
        code="invalid_asset", path="assets[0]", message="Asset is invalid."
    )

    assert issue.as_dict() == {
        "code": "invalid_asset",
        "path": "assets[0]",
        "message": "Asset is invalid.",
    }


def test_asset_index_rejects_unknown_fields(asset_index: AssetIndex) -> None:
    payload = asset_index.model_dump(mode="json")
    payload["assets"][0]["unexpected"] = True

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        AssetIndex.model_validate(payload)


def test_asset_index_rejects_duplicate_ids_and_uris(
    asset_index: AssetIndex,
) -> None:
    duplicate = deepcopy(asset_index.assets[0])
    asset_index.assets.append(duplicate)

    with pytest.raises(AssetValidationError) as exc_info:
        validate_asset_index_model(asset_index)

    assert {issue.code for issue in exc_info.value.issues} == {
        "duplicate_asset_id",
        "duplicate_asset_uri",
    }


def test_asset_priority_range_is_bounded(asset_index: AssetIndex) -> None:
    payload = asset_index.model_dump(mode="json")
    payload["assets"][0]["priority"] = 101

    with pytest.raises(ValidationError, match="less than or equal to 100"):
        AssetIndex.model_validate(payload)
