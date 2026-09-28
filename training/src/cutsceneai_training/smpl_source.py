from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


_ALLOWED_RIGHTS = {
    "owned",
    "licensed",
    "permissive",
    "research_only",
    "restricted",
    "unknown",
}
_ALLOWED_DECISIONS = {"allowed", "not_allowed", "unclear", "not_reviewed"}
_ALLOWED_POOLS = {"research", "production_candidate"}


@dataclass(frozen=True)
class MotionRights:
    rights_status: str
    training_use_status: str
    model_distribution_status: str
    redistribution_status: str = "not_reviewed"
    review_status: str = "not_reviewed"
    license_name: str | None = None
    license_reference: str | None = None
    notes: str | None = None

    def validate(self, *, usage_pool: str) -> None:
        if self.rights_status not in _ALLOWED_RIGHTS:
            raise ValueError(f"Unsupported rights_status: {self.rights_status}")
        for name, value in (
            ("training_use_status", self.training_use_status),
            ("model_distribution_status", self.model_distribution_status),
            ("redistribution_status", self.redistribution_status),
            ("review_status", self.review_status),
        ):
            if value not in _ALLOWED_DECISIONS:
                raise ValueError(f"Unsupported {name}: {value}")
        if usage_pool not in _ALLOWED_POOLS:
            raise ValueError(f"Unsupported usage_pool: {usage_pool}")

        if usage_pool == "production_candidate":
            if self.rights_status not in {"owned", "licensed", "permissive"}:
                raise ValueError(
                    "production_candidate data requires owned, licensed, or permissive rights."
                )
            if self.training_use_status != "allowed":
                raise ValueError(
                    "production_candidate data requires training_use_status='allowed'."
                )
            if self.model_distribution_status != "allowed":
                raise ValueError(
                    "production_candidate data requires model_distribution_status='allowed'."
                )

    def as_dict(self) -> dict[str, str | None]:
        return {
            "rights_status": self.rights_status,
            "training_use_status": self.training_use_status,
            "model_distribution_status": self.model_distribution_status,
            "redistribution_status": self.redistribution_status,
            "review_status": self.review_status,
            "license_name": self.license_name,
            "license_reference": self.license_reference,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class SMPLSourceMotion:
    global_orient: np.ndarray
    body_pose: np.ndarray
    transl: np.ndarray
    fps: float
    source_forward_axis: str = "+z"
    source_record_id: str = "unknown"

    def validate(self) -> None:
        global_orient = np.asarray(self.global_orient)
        body_pose = np.asarray(self.body_pose)
        transl = np.asarray(self.transl)

        if global_orient.ndim != 2 or global_orient.shape[1] != 3:
            raise ValueError("global_orient must have shape [T, 3].")
        if body_pose.ndim == 2 and body_pose.shape[1] == 63:
            pass
        elif body_pose.ndim == 3 and body_pose.shape[1:] == (21, 3):
            pass
        else:
            raise ValueError("body_pose must have shape [T, 63] or [T, 21, 3].")
        if transl.ndim != 2 or transl.shape[1] != 3:
            raise ValueError("transl must have shape [T, 3].")
        if not (global_orient.shape[0] == body_pose.shape[0] == transl.shape[0]):
            raise ValueError("SMPL source arrays must have identical frame counts.")
        if global_orient.shape[0] < 1:
            raise ValueError("SMPL source must contain at least one frame.")
        if not np.isfinite(global_orient).all():
            raise ValueError("global_orient contains non-finite values.")
        if not np.isfinite(body_pose).all():
            raise ValueError("body_pose contains non-finite values.")
        if not np.isfinite(transl).all():
            raise ValueError("transl contains non-finite values.")
        if self.fps <= 0.0:
            raise ValueError("fps must be positive.")
        if self.source_forward_axis not in {"+z", "-z"}:
            raise ValueError("source_forward_axis must be '+z' or '-z'.")

    def body_pose_21x3(self) -> np.ndarray:
        self.validate()
        pose = np.asarray(self.body_pose, dtype=np.float64)
        if pose.ndim == 2:
            return pose.reshape(pose.shape[0], 21, 3)
        return pose


def load_smpl_npz(
    path: str | Path,
    *,
    fps_override: float | None = None,
    source_forward_axis: str = "+z",
) -> SMPLSourceMotion:
    source_path = Path(path)
    with np.load(source_path, allow_pickle=False) as data:
        keys = set(data.files)

        if {"global_orient", "body_pose"}.issubset(keys):
            global_orient = np.asarray(data["global_orient"], dtype=np.float64)
            body_pose = np.asarray(data["body_pose"], dtype=np.float64)
        elif "poses" in keys:
            poses = np.asarray(data["poses"], dtype=np.float64)
            if poses.ndim != 2 or poses.shape[1] < 66:
                raise ValueError("poses must have shape [T, >=66] for SMPL ingestion.")
            global_orient = poses[:, :3]
            body_pose = poses[:, 3:66]
        else:
            raise ValueError(
                "SMPL NPZ must provide global_orient/body_pose or a poses array."
            )

        if "transl" in keys:
            transl = np.asarray(data["transl"], dtype=np.float64)
        elif "trans" in keys:
            transl = np.asarray(data["trans"], dtype=np.float64)
        else:
            raise ValueError("SMPL NPZ must provide transl or trans.")

        fps = fps_override
        if fps is None:
            for key in ("mocap_framerate", "fps", "frame_rate"):
                if key in keys:
                    fps = float(np.asarray(data[key]).reshape(-1)[0])
                    break
        if fps is None:
            raise ValueError(
                "Source FPS is missing. Provide fps_override or an FPS field in the NPZ."
            )

    source = SMPLSourceMotion(
        global_orient=global_orient,
        body_pose=body_pose,
        transl=transl,
        fps=float(fps),
        source_forward_axis=source_forward_axis,
        source_record_id=source_path.name,
    )
    source.validate()
    return source
