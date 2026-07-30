from copy import deepcopy

import pytest
from cutsceneai_assets import (
    AssetIndex,
    AssetKind,
    AssetRecord,
    AssetValidationError,
    ResolutionSourceKind,
    ResolutionStatus,
    asset_index_sha256,
    render_asset_resolution_plan,
    resolve_project,
    validate_resolution_plan,
)
from cutsceneai_cir import EnvironmentObject, Project


def _resolution_by_source(plan) -> dict[tuple[ResolutionSourceKind, str], object]:
    return {
        (resolution.source_kind, resolution.source_id): resolution
        for resolution in plan.resolutions
    }


def test_office_fixture_resolves_props_and_set_predictably(
    office_project: Project, asset_index: AssetIndex
) -> None:
    plan = resolve_project(office_project, asset_index)
    resolutions = _resolution_by_source(plan)

    contract = resolutions[(ResolutionSourceKind.ENVIRONMENT_OBJECT, "contract")]
    table = resolutions[(ResolutionSourceKind.ENVIRONMENT_OBJECT, "conference-table")]
    scene_set = resolutions[(ResolutionSourceKind.SCENE_SET, "scene-meeting")]

    assert contract.status is ResolutionStatus.MATCHED
    assert contract.asset_id == "office-contract"
    assert "contract" in contract.matched_terms
    assert table.asset_id == "office-conference-table"
    assert scene_set.asset_id == "office-conference-room"
    assert scene_set.score is not None and scene_set.score >= 100
    assert plan.warnings == []


def test_outdoor_fixture_resolves_props_and_set_predictably(
    outdoor_project: Project, asset_index: AssetIndex
) -> None:
    plan = resolve_project(outdoor_project, asset_index)
    resolutions = _resolution_by_source(plan)

    assert (
        resolutions[(ResolutionSourceKind.ENVIRONMENT_OBJECT, "boulder")].asset_id
        == "granite-boulder"
    )
    assert (
        resolutions[(ResolutionSourceKind.ENVIRONMENT_OBJECT, "trail-marker")].asset_id
        == "wooden-trail-marker"
    )
    assert (
        resolutions[(ResolutionSourceKind.SCENE_SET, "scene-clearing")].asset_id
        == "pine-forest-clearing"
    )


def test_explicit_cir_environment_uri_is_authoritative(
    office_project: Project, asset_index: AssetIndex
) -> None:
    explicit_uri = "/Game/ArtistApproved/SM_FinalContract.SM_FinalContract"
    office_project.environment[0].asset_uri = explicit_uri

    resolution = resolve_project(office_project, asset_index).resolutions[0]

    assert resolution.status is ResolutionStatus.EXPLICIT
    assert resolution.asset_uri == explicit_uri
    assert resolution.asset_id is None
    assert resolution.score is None
    assert resolution.matched_terms == []


def test_unmatched_assets_receive_visible_fallback_evidence(
    office_project: Project, asset_index: AssetIndex
) -> None:
    asset_index.assets = []

    plan = resolve_project(office_project, asset_index)

    assert all(
        resolution.status is ResolutionStatus.FALLBACK
        for resolution in plan.resolutions
    )
    assert {warning.code for warning in plan.warnings} == {
        "unresolved_environment_prop",
        "unresolved_environment_set",
    }


def test_prop_cannot_match_on_scene_location_alone(
    office_project: Project,
) -> None:
    index = AssetIndex(
        id="location-only",
        name="Location Only",
        target_engine="Unreal Engine",
        target_engine_version="5.8.0",
        assets=[
            AssetRecord(
                id="office-chair",
                name="Chair",
                kind=AssetKind.ENVIRONMENT_PROP,
                asset_uri="/Game/Props/SM_Chair.SM_Chair",
                location_terms=["Corporate conference room"],
            )
        ],
    )

    plan = resolve_project(office_project, index)
    prop_resolutions = [
        resolution
        for resolution in plan.resolutions
        if resolution.source_kind is ResolutionSourceKind.ENVIRONMENT_OBJECT
    ]

    assert all(
        resolution.status is ResolutionStatus.FALLBACK
        for resolution in prop_resolutions
    )


def test_ties_use_priority_then_lexical_asset_id(
    office_project: Project,
) -> None:
    base = {
        "name": "Contract",
        "kind": AssetKind.ENVIRONMENT_PROP,
        "aliases": ["Unsigned Contract"],
    }
    index = AssetIndex(
        id="tie-index",
        name="Tie Index",
        target_engine="Unreal Engine",
        target_engine_version="5.8.0",
        assets=[
            AssetRecord(
                id="contract-z",
                asset_uri="/Game/Props/SM_ContractZ.SM_ContractZ",
                priority=30,
                **base,
            ),
            AssetRecord(
                id="contract-b",
                asset_uri="/Game/Props/SM_ContractB.SM_ContractB",
                priority=50,
                **base,
            ),
            AssetRecord(
                id="contract-a",
                asset_uri="/Game/Props/SM_ContractA.SM_ContractA",
                priority=50,
                **base,
            ),
        ],
    )

    plan = resolve_project(office_project, index)
    contract = next(
        resolution
        for resolution in plan.resolutions
        if resolution.source_id == "contract"
        and resolution.source_kind is ResolutionSourceKind.ENVIRONMENT_OBJECT
    )

    assert contract.asset_id == "contract-a"


def test_resolution_is_deterministic_and_does_not_mutate_inputs(
    office_project: Project, asset_index: AssetIndex
) -> None:
    project_before = office_project.model_copy(deep=True)
    index_before = asset_index.model_copy(deep=True)

    first = resolve_project(office_project, asset_index)
    second = resolve_project(deepcopy(office_project), deepcopy(asset_index))

    assert render_asset_resolution_plan(first) == render_asset_resolution_plan(second)
    assert office_project == project_before
    assert asset_index == index_before
    assert first.asset_index_sha256 == asset_index_sha256(asset_index)


def test_resolution_validation_rejects_tampered_index_digest(
    office_project: Project, asset_index: AssetIndex
) -> None:
    plan = resolve_project(office_project, asset_index)
    plan.asset_index_sha256 = "0" * 64

    with pytest.raises(AssetValidationError, match="resolution_index_digest_mismatch"):
        validate_resolution_plan(office_project, asset_index, plan)


def test_resolution_validation_rejects_missing_and_unknown_sources(
    office_project: Project, asset_index: AssetIndex
) -> None:
    plan = resolve_project(office_project, asset_index)
    plan.resolutions.pop()
    extra = plan.resolutions[0].model_copy(
        update={"source_id": "invented", "source_name": "Invented"}
    )
    plan.resolutions.append(extra)

    with pytest.raises(AssetValidationError) as exc_info:
        validate_resolution_plan(office_project, asset_index, plan)

    assert {issue.code for issue in exc_info.value.issues} >= {
        "missing_resolution_source",
        "unknown_resolution_source",
    }


def test_resolution_validation_rejects_tampered_asset_metadata(
    office_project: Project, asset_index: AssetIndex
) -> None:
    plan = resolve_project(office_project, asset_index)
    plan.resolutions[0].asset_uri = "/Game/Tampered/SM_Wrong.SM_Wrong"

    with pytest.raises(AssetValidationError, match="resolved_asset_metadata_mismatch"):
        validate_resolution_plan(office_project, asset_index, plan)


def test_resolution_validation_rejects_noncanonical_match_evidence(
    office_project: Project, asset_index: AssetIndex
) -> None:
    plan = resolve_project(office_project, asset_index)
    plan.resolutions[0].reason = "Substituted explanation."

    with pytest.raises(AssetValidationError, match="resolution_not_canonical"):
        validate_resolution_plan(office_project, asset_index, plan)


@pytest.mark.parametrize(
    ("field", "value", "expected_code"),
    [
        ("project_id", "different-project", "resolution_project_mismatch"),
        ("asset_index_id", "different-index", "resolution_index_mismatch"),
        ("target_engine", "Different Engine", "resolution_target_mismatch"),
    ],
)
def test_resolution_validation_rejects_contract_identity_mismatches(
    office_project: Project,
    asset_index: AssetIndex,
    field: str,
    value: str,
    expected_code: str,
) -> None:
    plan = resolve_project(office_project, asset_index)
    setattr(plan, field, value)

    with pytest.raises(AssetValidationError, match=expected_code):
        validate_resolution_plan(office_project, asset_index, plan)


def test_resolution_validation_rejects_duplicate_source_and_wrong_kind(
    office_project: Project, asset_index: AssetIndex
) -> None:
    plan = resolve_project(office_project, asset_index)
    duplicate = plan.resolutions[0].model_copy(
        update={"expected_asset_kind": AssetKind.ENVIRONMENT_SET}
    )
    plan.resolutions.append(duplicate)

    with pytest.raises(AssetValidationError) as exc_info:
        validate_resolution_plan(office_project, asset_index, plan)

    assert {issue.code for issue in exc_info.value.issues} >= {
        "duplicate_resolution_source",
        "resolution_asset_kind_mismatch",
    }


def test_resolution_validation_requires_known_asset_and_match_evidence(
    office_project: Project, asset_index: AssetIndex
) -> None:
    plan = resolve_project(office_project, asset_index)
    resolution = plan.resolutions[0]
    resolution.asset_id = "missing-asset"
    resolution.score = None
    resolution.matched_terms = []

    with pytest.raises(AssetValidationError) as exc_info:
        validate_resolution_plan(office_project, asset_index, plan)

    assert {issue.code for issue in exc_info.value.issues} >= {
        "unknown_resolved_asset",
        "missing_match_evidence",
    }


def test_resolution_validation_rejects_invalid_explicit_match_evidence(
    office_project: Project, asset_index: AssetIndex
) -> None:
    office_project.environment[0].asset_uri = "/Game/Approved/SM_Contract.SM_Contract"
    plan = resolve_project(office_project, asset_index)
    resolution = plan.resolutions[0]
    resolution.asset_uri = "/Game/Wrong/SM_Contract.SM_Contract"
    resolution.asset_name = "Claimed Match"

    with pytest.raises(AssetValidationError) as exc_info:
        validate_resolution_plan(office_project, asset_index, plan)

    assert {issue.code for issue in exc_info.value.issues} >= {
        "invalid_explicit_resolution",
        "explicit_resolution_has_match_evidence",
    }


def test_resolution_validation_rejects_asset_on_fallback(
    office_project: Project, asset_index: AssetIndex
) -> None:
    asset_index.assets = []
    plan = resolve_project(office_project, asset_index)
    plan.resolutions[0].asset_uri = "/Game/Wrong/SM_Contract.SM_Contract"

    with pytest.raises(AssetValidationError, match="fallback_resolution_has_asset"):
        validate_resolution_plan(office_project, asset_index, plan)


def test_unreferenced_prop_uses_project_scene_context_deterministically(
    office_project: Project, asset_index: AssetIndex
) -> None:
    office_project.environment.append(EnvironmentObject(id="lamp", name="Desk Lamp"))
    asset_index.assets.append(
        AssetRecord(
            id="desk-lamp",
            name="Desk Lamp",
            kind=AssetKind.ENVIRONMENT_PROP,
            asset_uri="/Game/Props/SM_DeskLamp.SM_DeskLamp",
            location_terms=["Corporate conference room"],
        )
    )

    plan = resolve_project(office_project, asset_index)
    lamp = next(
        resolution for resolution in plan.resolutions if resolution.source_id == "lamp"
    )

    assert lamp.asset_id == "desk-lamp"
    assert "conference" in lamp.matched_terms
