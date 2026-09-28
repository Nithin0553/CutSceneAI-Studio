"""Training and dataset foundations for the CutSceneAI Cinematic Performance Model."""

from .amass_pilot import run_amass_turn_pilot
from .guard_turn import GuardTurnDatasetConfig, generate_guard_turn_dataset
from .smpl_canonicalize import CanonicalSMPLMotion, canonicalize_smpl_motion
from .smpl_ingestion import ingest_smpl_npz, write_canonical_smpl_record
from .smpl_source import MotionRights, SMPLSourceMotion, load_smpl_npz
from .turn_candidates import TurnCandidateConfig, materialize_turn_candidates
from .turn_mining import TurnMiningConfig, TurnWindow, mine_turn_windows
from .turn_qa import evaluate_turn_dataset, evaluate_turn_sample

__all__ = [
    "CanonicalSMPLMotion",
    "run_amass_turn_pilot",
    "GuardTurnDatasetConfig",
    "MotionRights",
    "SMPLSourceMotion",
    "TurnCandidateConfig",
    "TurnMiningConfig",
    "TurnWindow",
    "canonicalize_smpl_motion",
    "evaluate_turn_dataset",
    "evaluate_turn_sample",
    "generate_guard_turn_dataset",
    "ingest_smpl_npz",
    "load_smpl_npz",
    "materialize_turn_candidates",
    "mine_turn_windows",
    "write_canonical_smpl_record",
]
