"""Synthetic tests for stimulus-conditioned mutual information."""

from __future__ import annotations

import numpy as np
import pytest

from maze.kpms.behavior_ethogram.stimulus_mi import (
    assign_bins,
    compute_animal_mi,
    compute_global_bin_edges,
    compute_per_trial_mi,
    compute_trial_animal_summaries,
    cum_run_bouts_for_animal,
    global_quantile_bin_edges,
    occupancy_mi,
    parse_ordinal_suffix,
    run_group_mi_tests,
    run_group_mi_tests_sliced,
    run_group_mi_when_tests,
    transition_mi,
    trial_order_for_animal,
)
from maze.kpms.behavior_ethogram.stimulus_mi_contract import (
    FDR_FAMILY_POOLED,
    FDR_FAMILY_SLOPE,
    MIN_SLICE_ARM_N,
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


def test_parse_ordinal_suffix() -> None:
    assert parse_ordinal_suffix("S01") == 1
    assert parse_ordinal_suffix("T12") == 12
    with pytest.raises(ValueError, match="cannot parse"):
        parse_ordinal_suffix("bad")


def _multi_trial_rows(
    *,
    n_trials: int = 8,
    duty_slope: float = 0.0,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for t in range(n_trials):
        session = f"S{(t // 4) + 1:02d}"
        trial = f"T{(t % 4) + 1:02d}"
        trial_key = f"3243/{session}/{trial}"
        base_duty = 0.2 + duty_slope * t
        for i in range(6):
            rows.append(
                _bout_row(
                    trial_key=trial_key,
                    session=session,
                    trial=trial,
                    bout_index=str(i),
                    raw_syllable_id=str((i + t) % 4),
                    bout_mean_duty=f"{min(0.95, base_duty + i * 0.05):.2f}",
                    bout_mean_dist_px=f"{100 + t * 5 + i}.0",
                    bout_primary_state="run",
                )
            )
    return rows


def test_trial_order_and_cum_run_bouts() -> None:
    rows = _multi_trial_rows(n_trials=4)
    order = trial_order_for_animal(rows)
    assert [e.trial_ord for e in order] == [0, 1, 2, 3]
    assert order[0].session == "S01"
    cum = cum_run_bouts_for_animal(rows, order)
    assert cum[order[0].trial_key] == 6
    assert cum[order[-1].trial_key] == 24


def test_compute_per_trial_mi_full_factorial() -> None:
    rows = _multi_trial_rows(n_trials=4)
    edges = compute_global_bin_edges(rows, n_bins=4)
    trial_results = compute_per_trial_mi(rows, edges=edges)
    assert trial_results
    combos = {(r.phase, r.stim_var, r.mi_type) for r in trial_results}
    assert ("run", "duty", "occupancy") in combos
    assert ("run", "dist", "transition") in combos
    assert all(r.trial_ord >= 0 for r in trial_results)
    assert all(r.cum_run_bouts > 0 for r in trial_results)


def test_early_late_delta_requires_six_trials() -> None:
    rows = _multi_trial_rows(n_trials=5)
    edges = compute_global_bin_edges(rows, n_bins=4)
    trial_results = compute_per_trial_mi(rows, edges=edges)
    summaries = compute_trial_animal_summaries(
        [r for r in trial_results if r.phase == "run" and r.stim_var == "duty" and r.mi_type == "occupancy"]
    )
    assert summaries
    assert all(np.isnan(s.early_late_delta) for s in summaries)


def test_slope_sign_with_rising_coupling() -> None:
    rows = _multi_trial_rows(n_trials=8, duty_slope=0.08)
    edges = compute_global_bin_edges(rows, n_bins=4)
    trial_results = compute_per_trial_mi(rows, edges=edges)
    summaries = compute_trial_animal_summaries(
        [r for r in trial_results if r.phase == "run" and r.stim_var == "duty" and r.mi_type == "occupancy"]
    )
    assert len(summaries) == 1
    assert summaries[0].slope_vs_trial_ord > 0


def test_run_group_mi_when_tests_primary_cells_only() -> None:
    summary_rows = [
        {
            "animal_id": "1",
            "sex": "F",
            "strain": "wt",
            "tx": "n/a",
            "phase": "run",
            "stim_var": "duty",
            "mi_type": "occupancy",
            "slope_vs_trial_ord": 0.05,
            "early_late_delta": 0.02,
            "slope_vs_excess": float("nan"),
            "early_late_delta_excess": float("nan"),
        },
        {
            "animal_id": "2",
            "sex": "M",
            "strain": "wt",
            "tx": "n/a",
            "phase": "run",
            "stim_var": "duty",
            "mi_type": "occupancy",
            "slope_vs_trial_ord": -0.01,
            "early_late_delta": -0.03,
            "slope_vs_excess": float("nan"),
            "early_late_delta_excess": float("nan"),
        },
        {
            "animal_id": "1",
            "sex": "F",
            "strain": "wt",
            "tx": "n/a",
            "phase": "iti",
            "stim_var": "duty",
            "mi_type": "occupancy",
            "slope_vs_trial_ord": 0.99,
            "early_late_delta": 0.99,
            "slope_vs_excess": float("nan"),
            "early_late_delta_excess": float("nan"),
        },
    ]
    out = run_group_mi_when_tests(summary_rows, trial_nulls=False)
    assert out
    assert all(r["phase"] == "run" for r in out)
    assert all(r["mi_type"] == "occupancy" for r in out)
    assert all(r["metric"] in ("slope_vs_trial_ord", "early_late_delta") for r in out)
    assert not any(r["phase"] == "iti" for r in out)


def test_compute_per_trial_mi_with_nulls_populates_excess() -> None:
    rows = _multi_trial_rows(n_trials=4)
    edges = compute_global_bin_edges(rows, n_bins=4)
    trial_results = compute_per_trial_mi(
        rows,
        edges=edges,
        trial_nulls=True,
        n_perm=20,
        rng=np.random.default_rng(0),
    )
    run_occ = [r for r in trial_results if r.phase == "run" and r.stim_var == "duty" and r.mi_type == "occupancy"]
    assert run_occ
    assert all(np.isfinite(r.null_circ_mean) for r in run_occ)
    assert all(np.isfinite(r.excess) for r in run_occ)
    summaries = compute_trial_animal_summaries(run_occ, trial_nulls=True)
    assert summaries
    assert np.isfinite(summaries[0].null_clear_fraction)


def _within_session_trial_rows(*, trials_per_session: int = 6) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for s in range(2):
        session = f"S{s + 1:02d}"
        for t in range(trials_per_session):
            trial = f"T{t + 1:02d}"
            trial_key = f"3243/{session}/{trial}"
            base_duty = 0.2 + 0.05 * t + 0.1 * s
            for i in range(4):
                rows.append(
                    _bout_row(
                        trial_key=trial_key,
                        session=session,
                        trial=trial,
                        bout_index=str(i),
                        raw_syllable_id=str((i + t) % 4),
                        bout_mean_duty=f"{min(0.95, base_duty + i * 0.03):.2f}",
                        bout_mean_dist_px=f"{100 + s * 50 + t * 5 + i}.0",
                        bout_primary_state="run",
                    )
                )
    return rows


def test_within_session_early_late_delta() -> None:
    rows = _within_session_trial_rows(trials_per_session=6)
    edges = compute_global_bin_edges(rows, n_bins=4)
    trial_results = compute_per_trial_mi(rows, edges=edges)
    summaries = compute_trial_animal_summaries(
        [r for r in trial_results if r.phase == "run" and r.stim_var == "duty" and r.mi_type == "occupancy"]
    )
    assert len(summaries) == 1
    assert summaries[0].n_sessions_used == 2
    assert np.isfinite(summaries[0].early_late_delta_within_session)


def _factorial_cohort_fixture(*, n_per_cell: int) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    pooled: list[dict[str, object]] = []
    summaries: list[dict[str, object]] = []
    animal_id = 0
    for sex in ("F", "M"):
        for strain in ("wt", "tg"):
            for tx in ("a", "b"):
                for rep in range(n_per_cell):
                    animal_id += 1
                    aid = str(animal_id)
                    genotype_effect = 0.2 if strain == "tg" else 0.05
                    sex_effect = 0.03 if sex == "M" else 0.0
                    tx_effect = 0.02 if tx == "b" else 0.0
                    mi_mm = genotype_effect + sex_effect + tx_effect + 0.001 * rep
                    slope = genotype_effect / 10.0
                    pooled.append(
                        {
                            "animal_id": aid,
                            "sex": sex,
                            "strain": strain,
                            "tx": tx,
                            "phase": "run",
                            "stim_var": "duty",
                            "mi_type": "occupancy",
                            "mi_mm": mi_mm,
                        }
                    )
                    summaries.append(
                        {
                            "animal_id": aid,
                            "sex": sex,
                            "strain": strain,
                            "tx": tx,
                            "phase": "run",
                            "stim_var": "duty",
                            "mi_type": "occupancy",
                            "slope_vs_trial_ord": slope,
                            "early_late_delta": mi_mm / 5.0,
                            "early_late_delta_within_session": mi_mm / 7.0,
                            "slope_vs_excess": float("nan"),
                            "early_late_delta_excess": float("nan"),
                            "early_late_delta_within_session_excess": float("nan"),
                        }
                    )
    return pooled, summaries


def test_run_group_mi_tests_sliced_2x2x2_catalog_and_bh() -> None:
    pooled, summaries = _factorial_cohort_fixture(n_per_cell=MIN_SLICE_ARM_N)
    out = run_group_mi_tests_sliced(pooled, summaries, trial_nulls=False)
    assert out
    families = {str(r["fdr_family"]) for r in out}
    assert FDR_FAMILY_POOLED in families
    assert FDR_FAMILY_SLOPE in families
    assert all(r["phase"] == "run" for r in out)
    assert all(r["mi_type"] == "occupancy" for r in out)
    pooled_rows = [r for r in out if r["fdr_family"] == FDR_FAMILY_POOLED]
    assert pooled_rows
    assert any(np.isfinite(float(r["q_bh"])) for r in pooled_rows)

    def _n_holds(row: dict[str, object]) -> int:
        return sum(1 for col in ("hold_sex", "hold_strain", "hold_tx") if str(row.get(col, "")).strip())

    one_hold = [r for r in out if _n_holds(r) == 1]
    two_hold = [r for r in out if _n_holds(r) == 2]
    assert one_hold
    assert two_hold


def test_run_group_mi_tests_sliced_omits_small_arms() -> None:
    pooled: list[dict[str, object]] = []
    summaries: list[dict[str, object]] = []
    for i in range(3):
        base = {
            "animal_id": f"wt{i}",
            "sex": "F",
            "strain": "wt",
            "tx": "a",
            "phase": "run",
            "stim_var": "duty",
            "mi_type": "occupancy",
        }
        pooled.append({**base, "mi_mm": 0.1})
        summaries.append(
            {
                **base,
                "slope_vs_trial_ord": 0.01,
                "early_late_delta": 0.01,
                "early_late_delta_within_session": 0.01,
            }
        )
    for i in range(3):
        base = {
            "animal_id": f"tg{i}",
            "sex": "F",
            "strain": "tg",
            "tx": "a",
            "phase": "run",
            "stim_var": "duty",
            "mi_type": "occupancy",
        }
        pooled.append({**base, "mi_mm": 0.2})
        summaries.append(
            {
                **base,
                "slope_vs_trial_ord": 0.02,
                "early_late_delta": 0.02,
                "early_late_delta_within_session": 0.02,
            }
        )
    out = run_group_mi_tests_sliced(pooled, summaries, trial_nulls=False)
    assert out == []
