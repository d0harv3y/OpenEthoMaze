"""Presence step on the hysteresis locomotor segmenter (move | still).

Not kpMS. Categories are movement vs immobile spans from NOR ambulation
hysteresis. Grain: animal × phase × condition. Protocol: one-sample t of
paired Δ vs 0 within sex (txs pooled). Primary step: no_obj → identical_obj.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from nor_object_mi.simpler_first_da import apply_bh
from nor_object_mi.simpler_first_presence import NEAR_R_M, STEPS
from nor_object_mi.simpler_first_protocol_prologue import PHASES, ttest_one_sample
from nor_object_mi.simpler_first_q1 import SEX_ORDER, anova_within_sex, weighted_mean

PRIMARY_STEP = "no_obj->identical"
PRIMARY_METRICS = (
    "p_move",
    "median_move_duration_s",
    "mean_move_speed_mps",
    "frac_near",
    "frac_near_move",
)
SESSION_METRICS = (
    "p_move",
    "n_move_bouts",
    "n_still_bouts",
    "median_move_duration_s",
    "median_still_duration_s",
    "mean_move_speed_mps",
    "mean_dist_any_m",
    "frac_near",
    "frac_near_move",
    "frac_near_still",
)


def _clock_session_scalars(df: pd.DataFrame, *, r_m: float) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    g = df.copy()
    g["animal_id"] = g["animal_id"].astype(str)
    frames = pd.to_numeric(g["bout_frames"], errors="coerce").fillna(0.0)
    g["_frames"] = frames
    dist = pd.to_numeric(g["bout_mean_dist_any_m"], errors="coerce")
    g["_near"] = np.isfinite(dist.to_numpy()) & (dist.to_numpy() < float(r_m))
    keys = ["animal_id", "phase_layer", "condition_layer"]
    rows: list[dict[str, object]] = []
    for key, sub in g.groupby(keys, sort=False):
        aid, phase, cond = key
        w = sub["_frames"].to_numpy(dtype=np.float64)
        n_frames = float(np.nansum(w))
        near_w = w[sub["_near"].to_numpy()]
        n_near = float(np.nansum(near_w)) if near_w.size else 0.0
        rec: dict[str, object] = {
            "animal_id": str(aid),
            "phase_layer": phase,
            "condition_layer": cond,
            "n_bouts": int(len(sub)),
            "n_frames": n_frames,
            "n_near_frames": n_near,
            "median_duration_s": float(
                np.nanmedian(pd.to_numeric(sub["bout_duration_s"], errors="coerce").to_numpy())
            ),
            "mean_speed_mps": weighted_mean(
                pd.to_numeric(sub["bout_mean_speed_mps"], errors="coerce").to_numpy(),
                w,
            ),
            "mean_dist_any_m": weighted_mean(
                pd.to_numeric(sub["bout_mean_dist_any_m"], errors="coerce").to_numpy(),
                w,
            ),
            "frac_near": (n_near / n_frames) if n_frames > 0 else float("nan"),
        }
        for c in ("sex", "tx"):
            if c in sub.columns:
                rec[c] = sub[c].iloc[0]
        rows.append(rec)
    return pd.DataFrame(rows)


def session_locomotor_table(
    move: pd.DataFrame,
    still: pd.DataFrame,
    *,
    r_m: float = NEAR_R_M,
) -> pd.DataFrame:
    """One row per animal × phase × condition from move + still clocks."""
    mv = _clock_session_scalars(move, r_m=r_m)
    st = _clock_session_scalars(still, r_m=r_m)
    if mv.empty and st.empty:
        return pd.DataFrame()
    keys = ["animal_id", "phase_layer", "condition_layer"]
    m = mv.rename(
        columns={
            "n_bouts": "n_move_bouts",
            "n_frames": "n_move_frames",
            "n_near_frames": "n_near_move_frames",
            "median_duration_s": "median_move_duration_s",
            "mean_speed_mps": "mean_move_speed_mps",
            "mean_dist_any_m": "mean_dist_move_m",
            "frac_near": "frac_near_move",
        }
    )
    s = st.rename(
        columns={
            "n_bouts": "n_still_bouts",
            "n_frames": "n_still_frames",
            "n_near_frames": "n_near_still_frames",
            "median_duration_s": "median_still_duration_s",
            "mean_speed_mps": "mean_still_speed_mps",
            "mean_dist_any_m": "mean_dist_still_m",
            "frac_near": "frac_near_still",
        }
    )
    out = m.merge(s, on=keys, how="outer", suffixes=("", "_stillmeta"))
    if "sex_stillmeta" in out.columns:
        out["sex"] = out["sex"].fillna(out["sex_stillmeta"])
        out = out.drop(columns=["sex_stillmeta"])
    if "tx_stillmeta" in out.columns:
        out["tx"] = out["tx"].fillna(out["tx_stillmeta"])
        out = out.drop(columns=["tx_stillmeta"])
    for c in (
        "n_move_bouts",
        "n_still_bouts",
        "n_move_frames",
        "n_still_frames",
        "n_near_move_frames",
        "n_near_still_frames",
    ):
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0.0)
    n_lab = out["n_move_frames"] + out["n_still_frames"]
    out["p_move"] = np.where(n_lab > 0, out["n_move_frames"] / n_lab, np.nan)
    n_near = out["n_near_move_frames"] + out["n_near_still_frames"]
    out["frac_near"] = np.where(n_lab > 0, n_near / n_lab, np.nan)
    w_m = pd.to_numeric(out.get("n_move_frames"), errors="coerce").fillna(0.0)
    w_s = pd.to_numeric(out.get("n_still_frames"), errors="coerce").fillna(0.0)
    dm = pd.to_numeric(out.get("mean_dist_move_m"), errors="coerce")
    ds = pd.to_numeric(out.get("mean_dist_still_m"), errors="coerce")
    num = dm.fillna(0.0) * w_m + ds.fillna(0.0) * w_s
    den = np.where(np.isfinite(dm), w_m, 0.0) + np.where(np.isfinite(ds), w_s, 0.0)
    out["mean_dist_any_m"] = np.where(den > 0, num / den, np.nan)
    return out


def paired_step_deltas(sessions: pd.DataFrame) -> pd.DataFrame:
    """Right − left for every STEPS pair, within animal × phase."""
    rows: list[pd.DataFrame] = []
    if sessions.empty:
        return pd.DataFrame()
    metrics = [c for c in SESSION_METRICS if c in sessions.columns]
    for phase in PHASES:
        ac = sessions[sessions["phase_layer"] == phase]
        if ac.empty:
            continue
        for step, left, right in STEPS:
            L = ac[ac["condition_layer"] == left].set_index("animal_id")
            R = ac[ac["condition_layer"] == right].set_index("animal_id")
            common = sorted(set(L.index.astype(str)) & set(R.index.astype(str)))
            recs: list[dict[str, object]] = []
            for aid in common:
                row: dict[str, object] = {
                    "animal_id": aid,
                    "phase_layer": phase,
                    "step": step,
                    "left": left,
                    "right": right,
                    "sex": str(L.loc[aid, "sex"]),
                    "tx": str(L.loc[aid, "tx"]),
                }
                for m in metrics:
                    a = float(L.loc[aid, m])
                    b = float(R.loc[aid, m])
                    row[f"{m}_left"] = a
                    row[f"{m}_right"] = b
                    row[f"delta_{m}"] = (
                        b - a if np.isfinite(a) and np.isfinite(b) else float("nan")
                    )
                recs.append(row)
            if recs:
                rows.append(pd.DataFrame(recs))
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def hunt_tests(paired: pd.DataFrame) -> pd.DataFrame:
    """Primary: presence-step t vs 0 within sex. BH within sex × phase.

    Novelty/span t-tests are companions (not in the BH family).
    Tx coda: Welch ANOVA of presence Δ p_move by tx (uncorrected).
    """
    rows: list[dict[str, object]] = []
    if paired.empty:
        return pd.DataFrame()
    for step, _l, _r in STEPS:
        fam = "primary" if step == PRIMARY_STEP else "companion"
        metrics = PRIMARY_METRICS if fam == "primary" else PRIMARY_METRICS[:3]
        for phase in PHASES:
            g = paired[(paired["step"] == step) & (paired["phase_layer"] == phase)]
            if g.empty:
                continue
            for metric in metrics:
                col = f"delta_{metric}"
                if col not in g.columns:
                    continue
                for sex in SEX_ORDER:
                    gs = g[g["sex"] == sex]
                    rec = ttest_one_sample(gs[col].to_numpy())
                    rows.append(
                        {
                            "sex": sex,
                            "phase_layer": phase,
                            "step": step,
                            "metric": metric,
                            "p": rec["p"],
                            "stat": rec["stat"],
                            "n": rec["n"],
                            "mean_delta": rec["mean_delta"],
                            "median_delta": rec["median_delta"],
                            "frac_gt0": rec["frac_gt0"],
                            "test": rec["test"],
                            "family": fam,
                        }
                    )
            if step == PRIMARY_STEP and "delta_p_move" in g.columns:
                an = anova_within_sex(
                    g[["animal_id", "sex", "tx", "delta_p_move"]].rename(
                        columns={"delta_p_move": "delta_p_move"}
                    ),
                    metric="delta_p_move",
                )
                for rec in an.to_dict("records"):
                    rows.append(
                        {
                            "sex": rec["sex"],
                            "phase_layer": phase,
                            "step": step,
                            "metric": "delta_p_move",
                            "p": rec["p"],
                            "stat": rec["stat"],
                            "n": rec["n"],
                            "mean_delta": float("nan"),
                            "median_delta": float("nan"),
                            "frac_gt0": float("nan"),
                            "test": rec["test"],
                            "family": "tx_coda",
                        }
                    )
    tests = pd.DataFrame(rows)
    if tests.empty:
        return tests
    tests["hit_p05"] = pd.to_numeric(tests["p"], errors="coerce") < 0.05
    tests["q_bh"] = np.nan
    tests["hit_fdr05"] = False
    tests = tests.reset_index(drop=True)
    prim = tests["family"].astype(str) == "primary"
    for _, g in tests.loc[prim].groupby(["sex", "phase_layer"], sort=False):
        bh = apply_bh(g, p_col="p", q_col="q_bh")
        tests.loc[g.index, "q_bh"] = bh["q_bh"].to_numpy()
        tests.loc[g.index, "hit_fdr05"] = bh["hit_fdr05"].to_numpy()
        tests.loc[g.index, "hit_p05"] = bh["hit_p05"].to_numpy()
    return tests
