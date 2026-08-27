"""Stratified Wilcoxon DA tests for VAST cohort (tx × sex × strain)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from nor_object_mi.simpler_first_da import apply_bh_grouped
from vast_moseq.cohort_meta import norm_tx


def da_tests_cohort_strat_from_deltas(dtab: pd.DataFrame, *, progress: bool = False) -> pd.DataFrame:
    """Wilcoxon + BH per syllable inside each model × phase × step × tx × sex × strain."""
    need = {
        "model",
        "phase_layer",
        "step",
        "tx",
        "sex",
        "strain",
        "raw_syllable_id",
        "delta_p",
        "p_left",
        "p_right",
        "bc_contrib_frac",
    }
    missing = [c for c in need if c not in dtab.columns]
    if missing:
        raise ValueError(f"da_tests_cohort_strat_from_deltas missing columns: {missing}")
    if dtab.empty:
        return pd.DataFrame()

    out = dtab.copy()
    out["tx"] = out["tx"].map(norm_tx)
    keys = ["model", "phase_layer", "step", "tx", "sex", "strain", "raw_syllable_id"]
    has_left = "left" in out.columns
    has_right = "right" in out.columns
    cols = list(keys) + ["delta_p", "p_left", "p_right", "bc_contrib_frac"]
    if has_left:
        cols.append("left")
    if has_right:
        cols.append("right")
    dt = out.loc[:, cols].sort_values(keys, kind="mergesort")
    n = len(dt)
    if progress:
        print(f"  strat Wilcoxon: sorted {n:,} animal-syllable rows", flush=True)

    key_arr = dt[keys].to_numpy()
    change = np.empty(n, dtype=bool)
    change[0] = True
    change[1:] = np.any(key_arr[1:] != key_arr[:-1], axis=1)
    starts = np.flatnonzero(change)
    ends = np.append(starts[1:], n)
    dp_all = dt["delta_p"].to_numpy(dtype=np.float64)
    pl_all = dt["p_left"].to_numpy(dtype=np.float64)
    pr_all = dt["p_right"].to_numpy(dtype=np.float64)
    bc_all = dt["bc_contrib_frac"].to_numpy(dtype=np.float64)
    left_all = dt["left"].to_numpy() if has_left else None
    right_all = dt["right"].to_numpy() if has_right else None

    rows: list[dict[str, object]] = []
    n_grp = int(starts.size)
    report_every = max(1, n_grp // 20)
    for gi, (a, b) in enumerate(zip(starts, ends), start=1):
        if progress and (gi == 1 or gi % report_every == 0 or gi == n_grp):
            print(f"  strat Wilcoxon groups {gi}/{n_grp}", flush=True)
        rec_key = key_arr[a]
        dp = dp_all[a:b]
        d = dp[np.isfinite(dp)]
        if d.size < 2 or np.all(d == 0):
            rec = {"n": int(d.size), "stat": float("nan"), "p": float("nan")}
        else:
            stat, p = stats.wilcoxon(
                d,
                alternative="two-sided",
                zero_method="wilcox",
                method="asymptotic",
            )
            rec = {"n": int(d.size), "stat": float(stat), "p": float(p)}
        finite = np.isfinite(dp)
        n_fin = int(np.sum(finite))
        row: dict[str, object] = {
            "model": str(rec_key[0]),
            "phase_layer": str(rec_key[1]),
            "step": str(rec_key[2]),
            "tx": str(rec_key[3]),
            "sex": str(rec_key[4]),
            "strain": str(rec_key[5]),
            "raw_syllable_id": int(rec_key[6]),
            "n": rec["n"],
            "n_nonzero": int(np.sum(finite & (dp != 0))),
            "median_p_left": float(np.nanmedian(pl_all[a:b])),
            "median_p_right": float(np.nanmedian(pr_all[a:b])),
            "median_delta_p": float(np.nanmedian(dp)) if n_fin else float("nan"),
            "frac_gt0": float(np.mean(dp[finite] > 0)) if n_fin else float("nan"),
            "median_bc_contrib_frac": float(np.nanmedian(bc_all[a:b])),
            "stat": rec["stat"],
            "p": rec["p"],
            "test": "wilcoxon_signed_rank",
            "question": "DA",
        }
        if has_left:
            row["left"] = str(left_all[a])
        if has_right:
            row["right"] = str(right_all[a])
        rows.append(row)

    tests = pd.DataFrame(rows)
    tests = apply_bh_grouped(tests, ["model", "phase_layer", "step", "tx", "sex", "strain"])
    tests["hit_p05"] = pd.to_numeric(tests["p"], errors="coerce") < 0.05
    return tests
