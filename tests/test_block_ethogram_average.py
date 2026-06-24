"""Unit tests for block ethogram tier aggregation."""

from __future__ import annotations

import numpy as np

from maze.pipeline.viz.block_ethogram_average import (
    aggregate_mode_tier_per_second,
    expand_bout_tiers_to_rows,
    rows_to_phase_seconds,
    BoutTierSpan,
)


def test_expand_bout_tiers_to_rows() -> None:
    spans = [
        BoutTierSpan("k", 0, 2, "still", 1),
        BoutTierSpan("k", 2, 4, "fast_transit", 2),
    ]
    tiers = expand_bout_tiers_to_rows(spans, 4)
    assert tiers.tolist() == ["still", "still", "fast_transit", "fast_transit"]


def test_rows_to_phase_seconds_run_only() -> None:
    tiers = np.array(["still", "still", "fast_transit", "fast_transit"])
    states = ["iti", "run", "run", "run"]
    sec_tiers, counts = rows_to_phase_seconds(tiers, states, fps=2.0, phase="run")
    assert len(sec_tiers) >= 1
    assert counts.sum() == 3


def test_aggregate_mode_tier_per_second() -> None:
    trials = [
        (np.array(["still", "still"]), np.array([2, 2])),
        (np.array(["fast_transit", "fast_transit"]), np.array([2, 2])),
    ]
    mode, n = aggregate_mode_tier_per_second(trials, max_seconds=2)
    assert len(mode) == 2
    assert n[0] == 2
