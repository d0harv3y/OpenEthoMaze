"""Unit tests for bout AR-HMM batching (no GPU required)."""

from __future__ import annotations

import numpy as np
import pytest

from maze.kpms.behavior_ethogram.arhmm import (
    TrialBoutSequence,
    batch_trial_bout_sequences,
    decode_behavior_tokens,
    fit_bout_arhmm,
)
from maze.kpms.behavior_ethogram.arhmm_config import BoutArhmmConfig
from maze.kpms.behavior_ethogram.bout_scalars import BoutScalarFeatures


def _feat(speed: float) -> BoutScalarFeatures:
    return BoutScalarFeatures(
        raw_syllable_id=1,
        bout_index=0,
        row_start=0,
        row_end_exclusive=3,
        bout_frames=3,
        bout_duration_s=0.1,
        bout_mean_speed_mps=speed,
        bout_mean_abs_dheading=0.1,
        bout_mean_blob_area_px2=100.0,
        bout_iqr_speed_mps=0.01,
        bout_iqr_abs_dheading=0.01,
        bout_iqr_blob_area_px2=1.0,
    )


def test_batch_trial_bout_sequences_padding() -> None:
    seqs = [
        TrialBoutSequence("a", "042", np.ones((2, 7)), (_feat(0.1), _feat(0.2))),
        TrialBoutSequence("b", "042", np.ones((4, 7)) * 2, tuple(_feat(0.1) for _ in range(4))),
    ]
    batched = batch_trial_bout_sequences(seqs)
    assert batched.x.shape == (2, 4, 7)
    assert batched.mask[0, 2] == 0.0
    assert batched.mask[1, 3] == 1.0


def test_fit_bout_arhmm_smoke() -> None:
    rng = np.random.default_rng(0)
    seqs = [
        TrialBoutSequence(
            f"t{i}",
            "042",
            rng.normal(size=(5 + i, 7)),
            tuple(_feat(0.1) for _ in range(5 + i)),
        )
        for i in range(3)
    ]
    batched = batch_trial_bout_sequences(seqs)
    model = fit_bout_arhmm(batched, BoutArhmmConfig(num_iters=3, num_states=5))
    decoded = decode_behavior_tokens(model, batched)
    assert len(decoded) == 3
    assert len(decoded[0][2]) == 5
