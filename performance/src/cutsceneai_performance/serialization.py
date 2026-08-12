from __future__ import annotations

import hashlib
import json

from .camera import CameraCurveArtifact
from .facial import FacialCurveArtifact
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


def render_facial_curves(facial: FacialCurveArtifact) -> str:
    return json.dumps(facial.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"


def facial_curve_artifact_sha256(facial: FacialCurveArtifact) -> str:
    return hashlib.sha256(render_facial_curves(facial).encode("utf-8")).hexdigest()


def render_camera_curves(camera: CameraCurveArtifact) -> str:
    return json.dumps(camera.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"


def camera_curve_artifact_sha256(camera: CameraCurveArtifact) -> str:
    return hashlib.sha256(render_camera_curves(camera).encode("utf-8")).hexdigest()


def performance_package_fingerprint(package: GeneratedPerformancePackage) -> str:
    canonical = json.dumps(
        package.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
