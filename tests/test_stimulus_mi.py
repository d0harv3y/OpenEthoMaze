"""Synthetic tests for stimulus-conditioned mutual information."""

from __future__ import annotations

import numpy as np
import pytest

from maze.kpms.behavior_ethogram.stimulus_mi import (
    assign_bins,
    compute_animal_mi,
    compute_global_bin_edges,
    global_quantile_bin_edges,
    occupancy_mi,
    run_group_mi_tests,
    transition_mi,
)

def _bout_row(**kwargs: str) -> dict[str, str]:
    base = {
        "stream": "anatomical",
        "seed": "042",
        "trial_key": "3243/S01/T01",
        "animal_id": "3243",
        "session": "S01",
        "trial": "T01",
        "phase": "experimental",
        "exit_number": "1",
        "sex": "F",
        "strain": "wt",
        "tx": "n/a",
        "experiment": "VASTcont",
        "drug": "n/a",
        "cohort": "",
        "researcher": "",
        "is_habituation": "0",
        "raw_syllable_id": "1",
        "bout_index": "0",
        "row_start": "0",
        "row_end_exclusive": "3",
        "bout_frames": "3",
        "bout_duration_s": "0.1",
        "bout_primary_state": "run",
        "bout_mean_duty": "0.25",
        "bout_mean_dist_px": "200.0",
    }
    base.update(kwargs)
    return base


def test_monotone_map_occupancy_mi_positive_and_mm_below_raw() -> None:
    rng = np.random.default_rng(0)
    k = 4
    n = 2000
    stim = rng.integers(0, k, size=n)
    noise = rng.random(n) < 0.2
    syll = np.where(noise, rng.integers(0, k, size=n), stim)
    mi_raw, mi_mm, _, _, _ = occupancy_mi(syll, stim)
    assert mi_raw > 0.1
    assert mi_mm < mi_raw


def test_independent_streams_mi_near_null_band() -> None:
    rng = np.random.default_rng(1)
    k = 4
    n = 3000
    syll = rng.integers(0, k, size=n)
    stim = rng.integers(0, k, size=n)
    _, mi_mm, _, _, _ = occupancy_mi(syll, stim)
    assert mi_mm < 0.15


def test_flat_stimulus_occupancy_mi_zero() -> None:
    rng = np.random.default_rng(2)
    syll = rng.integers(0, 4, size=2000)
    stim = np.zeros(2000, dtype=int)
    mi_raw, mi_mm, _, _, _ = occupancy_mi(syll, stim)
    assert mi_raw == pytest.approx(0.0)
    assert mi_mm == pytest.approx(0.0)


def test_transition_mi_monotone_positive() -> None:
    rng = np.random.default_rng(3)
    n = 1500
    cur = np.zeros(n, dtype=int)
    stim = rng.integers(0, 4, size=n)
    next_s = np.where(rng.random(n) < 0.15, rng.integers(0, 4, size=n), stim)
    mi_raw, mi_mm, _, _, _ = transition_mi(cur, next_s, stim)
    assert mi_raw > 0.05
    assert mi_mm <= mi_raw


def test_global_quantile_bins_and_assign() -> None:
    vals = list(range(100))
    edges = global_quantile_bin_edges(vals, n_bins=4)
    bins = assign_bins(vals, edges)
    assert bins.min() >= 0
    assert bins.max() <= 3


def test_compute_animal_mi_synthetic_cohort() -> None:
    rows: list[dict[str, str]] = []
    duty_vals = [0.1, 0.3, 0.5, 0.7, 0.2, 0.4, 0.6, 0.8]
    for i, duty in enumerate(duty_vals):
        rows.append(
            _bout_row(
                bout_index=str(i),
                raw_syllable_id=str(i % 4),
                bout_mean_duty=f"{duty:.2f}",
                bout_mean_dist_px=f"{100 + i * 10}.0",
                bout_primary_state="run" if i % 3 else "iti_wait",
            )
        )
    edges = compute_global_bin_edges(rows, n_bins=4)
    results = compute_animal_mi(rows, edges=edges, n_perm=50, rng=np.random.default_rng(0))
    assert results
    phases = {r.phase for r in results}
    assert "run" in phases
    assert all(r.n_bouts > 0 for r in results)


def test_run_group_mi_tests_mann_whitney() -> None:
    rows = [
        {
            "animal_id": "1",
            "sex": "F",
            "strain": "wt",
            "tx": "n/a",
            "phase": "run",
            "stim_var": "duty",
            "mi_type": "occupancy",
            "mi_mm": "0.5",
        },
        {
            "animal_id": "2",
            "sex": "M",
            "strain": "wt",
            "tx": "n/a",
            "phase": "run",
            "stim_var": "duty",
            "mi_type": "occupancy",
            "mi_mm": "0.1",
        },
    ]
    out = run_group_mi_tests(rows)
    sex_tests = [r for r in out if r["factor"] == "sex"]
    assert len(sex_tests) == 1
    assert sex_tests[0]["test"] == "mannwhitneyu"
