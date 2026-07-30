from __future__ import annotations

import re
from dataclasses import dataclass

from cutsceneai_cir import EnvironmentObject, Project, Scene, validate_project_model

from .models import (
    AssetIndex,
    AssetKind,
    AssetRecord,
    AssetResolution,
    AssetResolutionPlan,
    AssetResolutionWarning,
    ResolutionSourceKind,
    ResolutionStatus,
)
from .serialization import asset_index_sha256
from .validation import validate_asset_index_model

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")
_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "asset",
        "assets",
        "environment",
        "game",
        "mesh",
        "model",
        "of",
        "prop",
        "props",
        "scene",
        "set",
        "sm",
        "static",
        "the",
        "to",
    }
)


@dataclass(frozen=True, slots=True)
class _Candidate:
    asset: AssetRecord
    score: int
    matched_terms: tuple[str, ...]


def _tokens(*values: str | None) -> frozenset[str]:
    terms: set[str] = set()
    for value in values:
        if value is None:
            continue
        separated = _CAMEL_BOUNDARY.sub(" ", value)
        terms.update(
            token.lower()
            for token in _TOKEN_PATTERN.findall(separated)
            if token.lower() not in _STOP_WORDS
        )
    return frozenset(terms)


def _phrase(value: str) -> str:
    return "-".join(sorted(_tokens(value)))


def _asset_identity_phrases(asset: AssetRecord) -> frozenset[str]:
    return frozenset(
        phrase
        for phrase in (
            _phrase(value) for value in (asset.id, asset.name, *asset.aliases)
        )
        if phrase
    )


def _asset_semantic_tokens(
    asset: AssetRecord, *, include_location_terms: bool
) -> frozenset[str]:
    return _tokens(
        asset.id,
        asset.name,
        asset.description,
        asset.asset_uri,
        *asset.aliases,
        *asset.keywords,
        *(asset.location_terms if include_location_terms else []),
    )


def _referenced_scene_locations(
    project: Project, environment_id: str
) -> frozenset[str]:
    referenced: list[str] = []
    for scene in project.scenes:
        used = any(
            environment_id in beat.environment_focus_ids
            or any(
                performance.look_at_id == environment_id
                for performance in beat.performances
            )
            for beat in scene.beats
        ) or any(
            environment_id in shot.subject_ids
            or environment_id in shot.camera.target_ids
            for shot in scene.shots
        )
        if used:
            referenced.append(scene.location)
    return _tokens(*(referenced or [scene.location for scene in project.scenes]))


def _score_prop(
    project: Project, source: EnvironmentObject, asset: AssetRecord
) -> _Candidate | None:
    source_phrases = {
        phrase for phrase in (_phrase(source.id), _phrase(source.name)) if phrase
    }
    exact = bool(source_phrases & _asset_identity_phrases(asset))
    asset_tokens = _asset_semantic_tokens(asset, include_location_terms=False)
    identity_overlap = _tokens(source.id, source.name) & asset_tokens
    description_overlap = _tokens(source.description) & asset_tokens
    if not exact and not identity_overlap and not description_overlap:
        return None

    location_overlap = _referenced_scene_locations(project, source.id) & _tokens(
        *asset.location_terms
    )
    score = (
        (100 if exact else 0)
        + 20 * len(identity_overlap)
        + 8 * len(description_overlap)
        + 3 * len(location_overlap)
    )
    matched_terms = tuple(
        sorted(identity_overlap | description_overlap | location_overlap)
    )
    return _Candidate(asset=asset, score=score, matched_terms=matched_terms)


def _score_set(scene: Scene, asset: AssetRecord) -> _Candidate | None:
    location_phrase = _phrase(scene.location)
    candidate_phrases = _asset_identity_phrases(asset) | {
        phrase
        for phrase in (_phrase(value) for value in asset.location_terms)
        if phrase
    }
    exact = bool(location_phrase and location_phrase in candidate_phrases)
    asset_tokens = _asset_semantic_tokens(asset, include_location_terms=True)
    location_overlap = _tokens(scene.location) & asset_tokens
    if not exact and not location_overlap:
        return None

    title_overlap = _tokens(scene.title) & asset_tokens
    score = (100 if exact else 0) + 20 * len(location_overlap) + 5 * len(title_overlap)
    return _Candidate(
        asset=asset,
        score=score,
        matched_terms=tuple(sorted(location_overlap | title_overlap)),
    )


def _select(candidates: list[_Candidate]) -> _Candidate | None:
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda candidate: (
            -candidate.score,
            -candidate.asset.priority,
            candidate.asset.id,
            candidate.asset.asset_uri,
        ),
    )


def _matched_resolution(
    *,
    source_kind: ResolutionSourceKind,
    source_id: str,
    source_name: str,
    expected_kind: AssetKind,
    candidate: _Candidate,
) -> AssetResolution:
    asset = candidate.asset
    return AssetResolution(
        source_kind=source_kind,
        source_id=source_id,
        source_name=source_name,
        expected_asset_kind=expected_kind,
        status=ResolutionStatus.MATCHED,
        asset_id=asset.id,
        asset_name=asset.name,
        asset_uri=asset.asset_uri,
        score=candidate.score,
        priority=asset.priority,
        matched_terms=list(candidate.matched_terms),
        asset_default_transform=asset.default_transform,
        reason=(
            f"Selected '{asset.id}' by deterministic semantic score "
            f"{candidate.score} and priority {asset.priority}."
        ),
    )


def resolve_project(project: Project, index: AssetIndex) -> AssetResolutionPlan:
    """Resolve CIR environment intent against a deterministic project Asset Index."""

    validate_project_model(project)
    validate_asset_index_model(index)
    prop_assets = [
        asset for asset in index.assets if asset.kind is AssetKind.ENVIRONMENT_PROP
    ]
    set_assets = [
        asset for asset in index.assets if asset.kind is AssetKind.ENVIRONMENT_SET
    ]
    resolutions: list[AssetResolution] = []
    warnings: list[AssetResolutionWarning] = []

    for source in project.environment:
        if source.asset_uri is not None:
            resolutions.append(
                AssetResolution(
                    source_kind=ResolutionSourceKind.ENVIRONMENT_OBJECT,
                    source_id=source.id,
                    source_name=source.name,
                    expected_asset_kind=AssetKind.ENVIRONMENT_PROP,
                    status=ResolutionStatus.EXPLICIT,
                    asset_uri=source.asset_uri,
                    reason="Preserved the explicit CIR environment asset URI.",
                )
            )
            continue

        selected = _select(
            [
                candidate
                for asset in prop_assets
                if (candidate := _score_prop(project, source, asset)) is not None
            ]
        )
        if selected is not None:
            resolutions.append(
                _matched_resolution(
                    source_kind=ResolutionSourceKind.ENVIRONMENT_OBJECT,
                    source_id=source.id,
                    source_name=source.name,
                    expected_kind=AssetKind.ENVIRONMENT_PROP,
                    candidate=selected,
                )
            )
            continue

        resolutions.append(
            AssetResolution(
                source_kind=ResolutionSourceKind.ENVIRONMENT_OBJECT,
                source_id=source.id,
                source_name=source.name,
                expected_asset_kind=AssetKind.ENVIRONMENT_PROP,
                status=ResolutionStatus.FALLBACK,
                reason="No environment-prop asset shared a semantic identity term.",
            )
        )
        warnings.append(
            AssetResolutionWarning(
                code="unresolved_environment_prop",
                source_kind=ResolutionSourceKind.ENVIRONMENT_OBJECT,
                source_id=source.id,
                message=(
                    f"Environment object '{source.id}' has no deterministic project-asset "
                    "match and requires an engine-visible fallback."
                ),
            )
        )

    for scene in project.scenes:
        selected = _select(
            [
                candidate
                for asset in set_assets
                if (candidate := _score_set(scene, asset)) is not None
            ]
        )
        if selected is not None:
            resolutions.append(
                _matched_resolution(
                    source_kind=ResolutionSourceKind.SCENE_SET,
                    source_id=scene.id,
                    source_name=scene.location,
                    expected_kind=AssetKind.ENVIRONMENT_SET,
                    candidate=selected,
                )
            )
            continue

        resolutions.append(
            AssetResolution(
                source_kind=ResolutionSourceKind.SCENE_SET,
                source_id=scene.id,
                source_name=scene.location,
                expected_asset_kind=AssetKind.ENVIRONMENT_SET,
                status=ResolutionStatus.FALLBACK,
                reason="No environment-set asset shared a scene-location term.",
            )
        )
        warnings.append(
            AssetResolutionWarning(
                code="unresolved_environment_set",
                source_kind=ResolutionSourceKind.SCENE_SET,
                source_id=scene.id,
                message=(
                    f"Scene '{scene.id}' has no deterministic set match and requires an "
                    "engine-visible stage fallback."
                ),
            )
        )

    plan = AssetResolutionPlan(
        project_id=project.id,
        asset_index_id=index.id,
        asset_index_sha256=asset_index_sha256(index),
        target_engine=index.target_engine,
        target_engine_version=index.target_engine_version,
        resolutions=resolutions,
        warnings=warnings,
    )
    return plan
