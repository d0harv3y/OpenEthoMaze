"""Litmus for Q5 BoutGrammar Family A — before cohort Kruskal."""

from __future__ import annotations

import numpy as np

from nor_object_mi.bout_grammar import (
    FAMILY_A_SIZE,
    assert_family_a_size,
    bout_grammar_from_masks,
    contiguous_true_runs,
    family_a_cell_keys,
    immobile_mask_from_spans,
    near_mask,
)


def test_family_a_size_is_twenty_four() -> None:
    assert FAMILY_A_SIZE == 24
    assert len(family_a_cell_keys()) == 24
    assert_family_a_size(24)


def test_contiguous_runs_counts_entries() -> None:
    # frames: F T T F F T F T T T
    m = np.array([0, 1, 1, 0, 0, 1, 0, 1, 1, 1], dtype=bool)
    runs = contiguous_true_runs(m)
    assert runs == [(1, 3), (5, 6), (7, 10)]


def test_near_mask_gate() -> None:
    d = np.array([0.05, 0.10, 0.099, np.nan, 0.2])
    v = np.array([True, True, True, True, True])
    m = near_mask(d, v, r_m=0.10)
    assert m.tolist() == [True, False, True, False, False]


def test_worked_visit_durations_at_10_fps() -> None:
    """Two visits of 5 and 10 frames at 10 fps → mean 0.75 s, 2 entries."""
    near = np.zeros(30, dtype=bool)
    near[0:5] = True
    near[10:20] = True
    immobile = np.zeros(30, dtype=bool)
    out = bout_grammar_from_masks(near, immobile, fps=10.0)
    assert out["n_nvl_entries"] == 2.0
    assert abs(out["mean_nvl_visit_dur_s"] - 0.75) < 1e-12
    assert abs(out["median_nvl_visit_dur_s"] - 0.75) < 1e-12
    assert abs(out["total_nvl_near_s"] - 1.5) < 1e-12
    assert out["frac_still_near_nvl"] == 0.0


def test_frac_still_near_known_fraction() -> None:
    near = np.array([True, True, True, True, False])
    immobile = np.array([True, True, False, False, True])
    out = bout_grammar_from_masks(near, immobile, fps=30.0)
    assert abs(out["frac_still_near_nvl"] - 0.5) < 1e-12


def test_no_visits_nan_mean_zero_entries() -> None:
    near = np.zeros(10, dtype=bool)
    immobile = np.ones(10, dtype=bool)
    out = bout_grammar_from_masks(near, immobile, fps=30.0)
    assert out["n_nvl_entries"] == 0.0
    assert np.isnan(out["mean_nvl_visit_dur_s"])
    assert np.isnan(out["frac_still_near_nvl"])


def test_immobile_mask_from_spans() -> None:
    # immobile [0,3) and [7,10)
    m = immobile_mask_from_spans(10, [(0, 0, 3), (1, 7, 10)])
    assert m.tolist() == [True, True, True, False, False, False, False, True, True, True]
