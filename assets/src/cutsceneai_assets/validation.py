from __future__ import annotations

from dataclasses import dataclass

from cutsceneai_cir import Project, validate_project_model

from .models import (
    AssetIndex,
    AssetKind,
    AssetResolution,
    AssetResolutionPlan,
    ResolutionSourceKind,
    ResolutionStatus,
)
from .serialization import asset_index_sha256


@dataclass(frozen=True, slots=True)
class AssetValidationIssue:
    code: str
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


class AssetValidationError(ValueError):
    """Raised when an Asset Index or resolution plan violates domain invariants."""

    def __init__(self, issues: list[AssetValidationIssue]) -> None:
        self.issues = tuple(issues)
        summary = "; ".join(
            f"{issue.code} at {issue.path}: {issue.message}" for issue in self.issues
        )
        super().__init__(summary)


def validate_asset_index_model(index: AssetIndex) -> None:
    issues: list[AssetValidationIssue] = []
    first_id_path: dict[str, str] = {}
    first_uri_path: dict[str, str] = {}

    for asset_index, asset in enumerate(index.assets):
        asset_path = f"assets[{asset_index}]"
        first_path = first_id_path.get(asset.id)
        if first_path is None:
            first_id_path[asset.id] = f"{asset_path}.id"
        else:
            issues.append(
                AssetValidationIssue(
                    code="duplicate_asset_id",
                    path=f"{asset_path}.id",
                    message=f"Asset ID '{asset.id}' is already used at {first_path}.",
                )
            )

        first_path = first_uri_path.get(asset.asset_uri)
        if first_path is None:
            first_uri_path[asset.asset_uri] = f"{asset_path}.asset_uri"
        else:
            issues.append(
                AssetValidationIssue(
                    code="duplicate_asset_uri",
                    path=f"{asset_path}.asset_uri",
                    message=f"Asset URI '{asset.asset_uri}' is already used at {first_path}.",
                )
            )

    if issues:
        raise AssetValidationError(issues)


def _resolution_key(
    resolution: AssetResolution,
) -> tuple[ResolutionSourceKind, str]:
    return resolution.source_kind, resolution.source_id


def validate_resolution_plan(
    project: Project,
    index: AssetIndex,
    plan: AssetResolutionPlan,
) -> None:
    """Validate that a resolution plan exactly describes the supplied project and index."""

    validate_project_model(project)
    validate_asset_index_model(index)
    issues: list[AssetValidationIssue] = []

    if plan.project_id != project.id:
        issues.append(
            AssetValidationIssue(
                code="resolution_project_mismatch",
                path="project_id",
                message=(
                    f"Resolution project '{plan.project_id}' does not match CIR project "
                    f"'{project.id}'."
                ),
            )
        )
    if plan.asset_index_id != index.id:
        issues.append(
            AssetValidationIssue(
                code="resolution_index_mismatch",
                path="asset_index_id",
                message=(
                    f"Resolution index '{plan.asset_index_id}' does not match Asset Index "
                    f"'{index.id}'."
                ),
            )
        )
    expected_digest = asset_index_sha256(index)
    if plan.asset_index_sha256 != expected_digest:
        issues.append(
            AssetValidationIssue(
                code="resolution_index_digest_mismatch",
                path="asset_index_sha256",
                message="Resolution plan was not produced from the supplied Asset Index.",
            )
        )
    if (
        plan.target_engine != index.target_engine
        or plan.target_engine_version != index.target_engine_version
    ):
        issues.append(
            AssetValidationIssue(
                code="resolution_target_mismatch",
                path="target_engine",
                message="Resolution target does not match the supplied Asset Index target.",
            )
        )

    expected_keys = {
        (ResolutionSourceKind.ENVIRONMENT_OBJECT, item.id)
        for item in project.environment
    } | {(ResolutionSourceKind.SCENE_SET, scene.id) for scene in project.scenes}
    first_resolution_path: dict[tuple[ResolutionSourceKind, str], str] = {}
    actual_keys: set[tuple[ResolutionSourceKind, str]] = set()
    asset_by_id = {asset.id: asset for asset in index.assets}
    environment_by_id = {item.id: item for item in project.environment}

    for resolution_index, resolution in enumerate(plan.resolutions):
        resolution_path = f"resolutions[{resolution_index}]"
        key = _resolution_key(resolution)
        first_path = first_resolution_path.get(key)
        if first_path is not None:
            issues.append(
                AssetValidationIssue(
                    code="duplicate_resolution_source",
                    path=f"{resolution_path}.source_id",
                    message=f"Resolution source is already declared at {first_path}.",
                )
            )
        else:
            first_resolution_path[key] = resolution_path
        actual_keys.add(key)

        expected_kind = (
            AssetKind.ENVIRONMENT_PROP
            if resolution.source_kind is ResolutionSourceKind.ENVIRONMENT_OBJECT
            else AssetKind.ENVIRONMENT_SET
        )
        if resolution.expected_asset_kind is not expected_kind:
            issues.append(
                AssetValidationIssue(
                    code="resolution_asset_kind_mismatch",
                    path=f"{resolution_path}.expected_asset_kind",
                    message=(
                        f"Source kind '{resolution.source_kind.value}' requires asset kind "
                        f"'{expected_kind.value}'."
                    ),
                )
            )

        if resolution.status is ResolutionStatus.MATCHED:
            selected = (
                asset_by_id.get(resolution.asset_id)
                if resolution.asset_id is not None
                else None
            )
            if selected is None:
                issues.append(
                    AssetValidationIssue(
                        code="unknown_resolved_asset",
                        path=f"{resolution_path}.asset_id",
                        message="Matched resolution must reference an asset in the supplied index.",
                    )
                )
            elif (
                selected.kind is not expected_kind
                or resolution.asset_uri != selected.asset_uri
                or resolution.asset_name != selected.name
                or resolution.priority != selected.priority
                or resolution.asset_default_transform != selected.default_transform
            ):
                issues.append(
                    AssetValidationIssue(
                        code="resolved_asset_metadata_mismatch",
                        path=resolution_path,
                        message=(
                            f"Resolution metadata does not match Asset Index record "
                            f"'{selected.id}'."
                        ),
                    )
                )
            if resolution.score is None or not resolution.matched_terms:
                issues.append(
                    AssetValidationIssue(
                        code="missing_match_evidence",
                        path=resolution_path,
                        message="Matched resolution must include a score and matched terms.",
                    )
                )
        elif resolution.status is ResolutionStatus.EXPLICIT:
            source = environment_by_id.get(resolution.source_id)
            if (
                resolution.source_kind is not ResolutionSourceKind.ENVIRONMENT_OBJECT
                or source is None
                or source.asset_uri is None
                or resolution.asset_uri != source.asset_uri
            ):
                issues.append(
                    AssetValidationIssue(
                        code="invalid_explicit_resolution",
                        path=resolution_path,
                        message="Explicit resolution must preserve a CIR environment asset URI.",
                    )
                )
            if (
                any(
                    value is not None
                    for value in (
                        resolution.asset_id,
                        resolution.asset_name,
                        resolution.score,
                        resolution.priority,
                        resolution.asset_default_transform,
                    )
                )
                or resolution.matched_terms
            ):
                issues.append(
                    AssetValidationIssue(
                        code="explicit_resolution_has_match_evidence",
                        path=resolution_path,
                        message="Explicit resolution cannot claim Asset Index match evidence.",
                    )
                )
        elif (
            any(
                value is not None
                for value in (
                    resolution.asset_id,
                    resolution.asset_name,
                    resolution.asset_uri,
                    resolution.score,
                    resolution.priority,
                    resolution.asset_default_transform,
                )
            )
            or resolution.matched_terms
        ):
            issues.append(
                AssetValidationIssue(
                    code="fallback_resolution_has_asset",
                    path=resolution_path,
                    message="Fallback resolution cannot reference a selected asset.",
                )
            )

    for source_kind, source_id in sorted(
        expected_keys - actual_keys, key=lambda value: (value[0].value, value[1])
    ):
        issues.append(
            AssetValidationIssue(
                code="missing_resolution_source",
                path="resolutions",
                message=f"Missing resolution for {source_kind.value} '{source_id}'.",
            )
        )
    for source_kind, source_id in sorted(
        actual_keys - expected_keys, key=lambda value: (value[0].value, value[1])
    ):
        issues.append(
            AssetValidationIssue(
                code="unknown_resolution_source",
                path="resolutions",
                message=f"Unknown resolution source {source_kind.value} '{source_id}'.",
            )
        )

    if not issues:
        from .resolution import resolve_project

        expected_plan = resolve_project(project, index)
        if plan != expected_plan:
            issues.append(
                AssetValidationIssue(
                    code="resolution_not_canonical",
                    path="$",
                    message=(
                        "Resolution plan does not exactly match the deterministic result "
                        "for the supplied CIR project and Asset Index."
                    ),
                )
            )

    if issues:
        raise AssetValidationError(issues)
