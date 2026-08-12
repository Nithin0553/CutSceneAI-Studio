from __future__ import annotations

import hashlib
import json

from .models import GeneratedPerformancePackage, PerformanceGenerationPlan
from .motion import BodyMotionArtifact


def render_performance_package(package: GeneratedPerformancePackage) -> str:
    return json.dumps(package.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"


def render_generation_plan(plan: PerformanceGenerationPlan) -> str:
    return json.dumps(plan.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"


def render_body_motion(motion: BodyMotionArtifact) -> str:
    return json.dumps(motion.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"


def body_motion_artifact_sha256(motion: BodyMotionArtifact) -> str:
    return hashlib.sha256(render_body_motion(motion).encode("utf-8")).hexdigest()


def performance_package_fingerprint(package: GeneratedPerformancePackage) -> str:
    canonical = json.dumps(
        package.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
