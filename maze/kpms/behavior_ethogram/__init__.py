"""Behavior ethogram: producer-agnostic Behavior labels above kpMS syllables.

Behavior is the target; Option A (syllable-sequence grammar), Option B
(B-SOiD/MotionMapper frame states), and Option D (enriched bout AR-HMM) are
competing producers that all emit the same ``BehaviorLabeling`` artifact.
See ``CONTEXT.md`` and ``docs/adr/0001-behavior-producer-agnostic-target.md``.
"""

from .anchor import (
    IsMovingParams,
    calibrate_is_moving_params,
    calibrate_min_dwell_ms,
    is_moving,
    speed_histogram_antimode,
    speed_mps_from_xy_px,
)
from .anchor_build import build_is_moving_anchor
from .anchor_store import IsMovingAnchor, TrialAnchorFrames, read_is_moving_anchor, write_is_moving_anchor
from .evaluate import EvaluationReport, evaluate_behavior_producer, evaluate_behavior_producers
from .labeling import (
    UNLABELED,
    BehaviorBout,
    BehaviorLabeling,
    TrialFrameLabels,
    labeling_to_bouts,
    read_behavior_labeling,
    write_behavior_labeling,
)
from .paths import anchor_dir, behavior_ethogram_root, producer_dir, stage_ii_dir, stage_iii_dir

__all__ = [
    "IsMovingParams",
    "IsMovingAnchor",
    "TrialAnchorFrames",
    "EvaluationReport",
    "is_moving",
    "speed_mps_from_xy_px",
    "speed_histogram_antimode",
    "calibrate_min_dwell_ms",
    "calibrate_is_moving_params",
    "build_is_moving_anchor",
    "write_is_moving_anchor",
    "read_is_moving_anchor",
    "evaluate_behavior_producer",
    "evaluate_behavior_producers",
    "anchor_dir",
    "behavior_ethogram_root",
    "stage_ii_dir",
    "stage_iii_dir",
    "producer_dir",
    "BehaviorLabeling",
    "TrialFrameLabels",
    "BehaviorBout",
    "UNLABELED",
    "labeling_to_bouts",
    "write_behavior_labeling",
    "read_behavior_labeling",
]
