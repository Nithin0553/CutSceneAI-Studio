"""Training and dataset foundations for the CutSceneAI Cinematic Performance Model."""

from .guard_turn import GuardTurnDatasetConfig, generate_guard_turn_dataset
from .smpl_canonicalize import CanonicalSMPLMotion, canonicalize_smpl_motion
from .smpl_ingestion import ingest_smpl_npz, write_canonical_smpl_record
from .smpl_source import MotionRights, SMPLSourceMotion, load_smpl_npz
from .turn_mining import TurnMiningConfig, TurnWindow, mine_turn_windows

__all__ = [
    "CanonicalSMPLMotion",
    "GuardTurnDatasetConfig",
    "MotionRights",
    "SMPLSourceMotion",
    "TurnMiningConfig",
    "TurnWindow",
    "canonicalize_smpl_motion",
    "generate_guard_turn_dataset",
    "ingest_smpl_npz",
    "load_smpl_npz",
    "mine_turn_windows",
    "write_canonical_smpl_record",
]
