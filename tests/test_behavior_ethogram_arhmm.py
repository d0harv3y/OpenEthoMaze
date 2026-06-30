"""Unit tests for bout AR-HMM batching (no GPU required)."""

from __future__ import annotations

import numpy as np
import pytest

from maze.kpms.behavior_ethogram.arhmm import (
    TrialBoutSequence,
    batch_trial_bout_sequences,
    build_trial_sequences_from_table,
    decode_behavior_tokens,
    fit_bout_arhmm,
    zscore_batched_features,
)
from maze.kpms.behavior_ethogram.arhmm_config import BoutArhmmConfig
from maze.kpms.behavior_ethogram.bout_scalars import BoutScalarFeatures


def _feat(speed: float, *, area: float = 100.0) -> BoutScalarFeatures:
    return BoutScalarFeatures(
        raw_syllable_id=1,
        bout_index=0,
        row_start=0,
        row_end_exclusive=3,
        bout_frames=3,
        bout_duration_s=0.1,
        bout_mean_speed_mps=speed,
        bout_mean_abs_dheading=0.1,
        bout_mean_blob_area_px2=area,
        bout_iqr_speed_mps=0.01,
        bout_iqr_abs_dheading=0.01,
        bout_iqr_blob_area_px2=1.0,
    )


def test_batch_trial_bout_sequences_padding() -> None:
    seqs = [
        TrialBoutSequence("a", "042", np.ones((2, 12)), (_feat(0.1), _feat(0.2))),
        TrialBoutSequence("b", "042", np.ones((4, 12)) * 2, tuple(_feat(0.1) for _ in range(4))),
    ]
    batched = batch_trial_bout_sequences(seqs)
    assert batched.x.shape == (2, 4, 12)
    assert batched.mask[0, 2] == 0.0
    assert batched.mask[1, 3] == 1.0


def test_zscore_batched_features_masked_rows() -> None:
    seqs = [
        TrialBoutSequence(
            "t0",
            "042",
            np.array([[1.0, 10.0], [3.0, 30.0], [5.0, 50.0]]),
            (_feat(0.1), _feat(0.2), _feat(0.3)),
        )
    ]
    batched = batch_trial_bout_sequences(seqs)
    scaled, mean, std = zscore_batched_features(batched)
    vals = scaled.x[scaled.mask > 0]
    assert np.allclose(vals.mean(axis=0), 0.0, atol=1e-10)
    assert np.allclose(vals.std(axis=0), 1.0, atol=1e-10)
    assert mean.shape == (2,)
    assert std.shape == (2,)


def test_fit_bout_arhmm_smoke() -> None:
    rng = np.random.default_rng(0)
    seqs = [
        TrialBoutSequence(
            f"t{i}",
            "042",
            rng.normal(size=(5 + i, 12)),
            tuple(_feat(0.1) for _ in range(5 + i)),
        )
        for i in range(3)
    ]
    batched = batch_trial_bout_sequences(seqs)
    cfg = BoutArhmmConfig(num_iters=3, num_states=5, nlags=2)
    fit_result = fit_bout_arhmm(batched, cfg)
    decoded = decode_behavior_tokens(fit_result.model, fit_result.scaled, nlags=cfg.nlags)
    assert len(decoded) == 3
    assert len(decoded[0][2]) == 5


def test_fit_bout_arhmm_returns_zscore_metadata() -> None:
    pytest.importorskip("jax_moseq")
    rng = np.random.default_rng(2)
    n_bouts = 20
    mat = np.column_stack(
        [
            np.linspace(0.05, 0.4, n_bouts) + rng.normal(0, 0.01, n_bouts),
            rng.uniform(0.05, 0.2, n_bouts),
            np.linspace(100.0, 5000.0, n_bouts) + rng.normal(0, 50.0, n_bouts),
            rng.uniform(0.01, 0.05, n_bouts),
            rng.uniform(0.01, 0.05, n_bouts),
            rng.uniform(0.2, 2.0, n_bouts),
            rng.uniform(0.2, 1.0, n_bouts),
            rng.uniform(-0.5, 0.5, n_bouts),
            rng.uniform(0.3, 1.0, n_bouts),
            rng.uniform(0.05, 0.4, n_bouts),
            rng.uniform(0.05, 0.2, n_bouts),
            np.linspace(100.0, 5000.0, n_bouts) + rng.normal(0, 50.0, n_bouts),
        ]
    )
    rows = tuple(_feat(float(s), area=float(a)) for s, a in zip(mat[:, 0], mat[:, 2], strict=True))
    batched = batch_trial_bout_sequences([TrialBoutSequence("t0", "042", mat, rows)])
    raw = batched.x[batched.mask > 0]
    raw_ratio = float(raw.std(axis=0).max() / max(raw.std(axis=0).min(), 1e-9))

    cfg = BoutArhmmConfig(num_iters=3, num_states=5, nlags=2)
    fit_result = fit_bout_arhmm(batched, cfg)
    scaled = fit_result.scaled.x[fit_result.scaled.mask > 0]
    scaled_ratio = float(scaled.std(axis=0).max() / max(scaled.std(axis=0).min(), 1e-9))
    assert scaled_ratio < raw_ratio / 10
    assert np.allclose(scaled.mean(axis=0), 0.0, atol=1e-10)
    assert fit_result.feature_mean.shape == (12,)
    assert fit_result.feature_std.shape == (12,)


def test_build_trial_sequences_appends_syllable_signature_columns() -> None:
    table = [
        {
            "seed": "042",
            "trial_key": "1-S01-T01",
            "raw_syllable_id": "1",
            "bout_index": "0",
            "row_start": "0",
            "row_end_exclusive": "3",
            "bout_frames": "3",
            "bout_duration_s": "0.1",
            "bout_mean_speed_mps": "0.1",
            "bout_mean_abs_dheading": "0.05",
            "bout_mean_blob_area_px2": "100",
            "bout_iqr_speed_mps": "0.01",
            "bout_iqr_abs_dheading": "0.01",
            "bout_iqr_blob_area_px2": "1",
            "bout_net_dheading_rad": "0",
            "bout_straightness": "1",
        },
        {
            "seed": "042",
            "trial_key": "1-S01-T01",
            "raw_syllable_id": "2",
            "bout_index": "1",
            "row_start": "3",
            "row_end_exclusive": "5",
            "bout_frames": "2",
            "bout_duration_s": "0.067",
            "bout_mean_speed_mps": "0.2",
            "bout_mean_abs_dheading": "0.1",
            "bout_mean_blob_area_px2": "200",
            "bout_iqr_speed_mps": "0.02",
            "bout_iqr_abs_dheading": "0.02",
            "bout_iqr_blob_area_px2": "2",
            "bout_net_dheading_rad": "0.1",
            "bout_straightness": "0.8",
        },
    ]
    seqs = build_trial_sequences_from_table(table)
    assert len(seqs) == 1
    assert seqs[0].features.shape == (2, 12)


def test_build_trial_sequences_rejects_cluster_feature_flag() -> None:
    with pytest.raises(ValueError, match="include_cluster_feature"):
        build_trial_sequences_from_table([], include_cluster_feature=True)
