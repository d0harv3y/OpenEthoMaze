"""S1 evaluation harness tests (file seam only)."""

from __future__ import annotations

import numpy as np

from maze.kpms.behavior_ethogram.anchor_store import IsMovingAnchor, TrialAnchorFrames, write_is_moving_anchor
from maze.kpms.behavior_ethogram.evaluate import (
    cross_seed_reproducibility,
    evaluate_behavior_producer,
    evaluate_behavior_producers,
)
from maze.kpms.behavior_ethogram.labeling import BehaviorLabeling, TrialFrameLabels, write_behavior_labeling
from maze.kpms.behavior_ethogram.paths import anchor_dir, producer_dir


def _write_fixtures(tmp_path) -> tuple:
    anchor_art = anchor_dir(tmp_path, "is_moving", "cal")
    producer_art = producer_dir(tmp_path, "dummy", "seed_a")
    write_is_moving_anchor(
        anchor_art,
        IsMovingAnchor(
            calibration_id="cal",
            fps=10.0,
            trials=(
                TrialAnchorFrames(
                    trial_key="1-S01-T01",
                    source_frame_index=np.array([0, 1, 2, 3, 4], dtype=np.int64),
                    is_moving=np.array([False, True, True, False, False]),
                ),
            ),
            params={"enter_mps": 0.2, "exit_mps": 0.05, "min_dwell_ms": 100.0},
        ),
    )
    write_behavior_labeling(
        producer_art,
        BehaviorLabeling(
            producer="dummy",
            fit_id="seed_a",
            fps=10.0,
            trials=(
                TrialFrameLabels(
                    trial_key="1-S01-T01",
                    source_frame_index=np.array([0, 1, 2, 3, 4], dtype=np.int64),
                    behavior_id=np.array([0, 2, 2, 0, 0], dtype=np.int32),
                ),
            ),
            behavior_names={0: "pause", 2: "locomote"},
        ),
    )
    return anchor_art, producer_art


def test_evaluate_behavior_producer_anchor_agreement(tmp_path) -> None:
    anchor_art, producer_art = _write_fixtures(tmp_path)
    report = evaluate_behavior_producer(producer_art, anchor_art)
    assert report.producer == "dummy"
    assert report.n_trials == 1
    assert report.mean_anchor_agreement == 1.0
    assert report.mean_producer_moving_fraction == 0.4
    assert report.mean_anchor_moving_fraction == 0.4


def test_evaluate_behavior_producers_and_cross_seed(tmp_path) -> None:
    anchor_art, producer_art = _write_fixtures(tmp_path)
    producer_b = producer_dir(tmp_path, "dummy", "seed_b")
    write_behavior_labeling(
        producer_b,
        BehaviorLabeling(
            producer="dummy",
            fit_id="seed_b",
            fps=10.0,
            trials=(
                TrialFrameLabels(
                    trial_key="1-S01-T01",
                    source_frame_index=np.array([0, 1, 2, 3, 4], dtype=np.int64),
                    behavior_id=np.array([2, 2, 2, 2, 0], dtype=np.int32),
                ),
            ),
            behavior_names={0: "pause", 2: "locomote"},
        ),
    )
    reports = evaluate_behavior_producers([producer_art, producer_b], anchor_art)
    assert len(reports) == 2
    cross = cross_seed_reproducibility(reports)
    assert cross.n_producers == 2
    assert cross.shared_trial_keys == ("1-S01-T01",)
    assert cross.mean_moving_fraction_std > 0.0
