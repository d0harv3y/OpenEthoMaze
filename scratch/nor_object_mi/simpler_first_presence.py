"""Paired simpler-first presence steps: no_obj → identical → novel_obj.

Question (plain): when objects appear (then when novel replaces identical),
does near-locus engagement or syllable composition change *within animal*?

Not MI. Operations: scalar rates (S0); COUNT / UNCERTAINTY / DIFFERENCE (S1–S2).
Association structure: paired / repeated (same animal across condition_layer).

Grain: animal × phase × condition_layer (full session; spot bout-means).
Near rate uses gate A: bout_mean_dist_any_m < 0.10 m (same as near-grain).

Default: all paramscan models × BL/TX/REC3hr/REC11hr → long tests table + agreement.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from scipy.spatial.distance import braycurtis

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.simpler_first_q1 import LOCKED, SEX_ORDER, kruskal_within_sex  # noqa: E402
from nor_object_mi.simpler_first_q2 import shannon_bits  # noqa: E402

NEAR_R_M = 0.10
CONTROL_TX = "noSD"
TX_STRATUM_ALL = "all"
TX_STRATUM_CONTROL = "noSD"
CONDS = ("no_obj", "identical_obj", "novel_obj")
STEPS: tuple[tuple[str, str, str], ...] = (
    ("no_obj->identical", "no_obj", "identical_obj"),
    ("identical->novel", "identical_obj", "novel_obj"),
    ("no_obj->novel", "no_obj", "novel_obj"),
)
PHASES: tuple[tuple[str, str], ...] = (
    ("NOR_BL", "condition_ladder_NOR_BL"),
    ("NOR_TX", "condition_ladder"),
    ("NOR_REC3hr", "condition_ladder_NOR_REC3hr"),
    ("NOR_REC11hr", "condition_ladder_NOR_REC11hr"),
)
AGREE_METRICS = ("frac_near", "mean_dist_any_m", "richness", "shannon_bits")
AGREE_STEPS = ("no_obj->identical", "identical->novel")


GRAINS = ("full_session", "near_0p10")
WEIGHTINGS = ("frame_share", "bout_count")


def _animal_condition_row(
    g: pd.DataFrame,
    *,
    r_m: float,
    grain: str = "full_session",
    weighting: str = "frame_share",
) -> dict[str, object]:
    """Session engagement scalars always use the full bout table.

    ``grain`` selects which bouts feed the syllable composition:
    ``full_session`` or ``near_0p10`` (bout-mean ``dist_any`` < r_m).

    ``weighting`` selects the composition representation:
    ``frame_share`` (sum ``bout_frames``) or ``bout_count`` (one per bout).
    Zero near frames → empty counts and NaN Shannon.
    """
    if grain not in GRAINS:
        raise ValueError(f"grain must be one of {GRAINS}, got {grain!r}")
    if weighting not in WEIGHTINGS:
        raise ValueError(f"weighting must be one of {WEIGHTINGS}, got {weighting!r}")
    w = g["bout_frames"].to_numpy(dtype=np.float64)
    d_any = g["bout_mean_dist_any_m"].to_numpy(dtype=np.float64)
    ok = np.isfinite(w) & (w > 0)
    n_frames = int(np.nansum(w[ok])) if np.any(ok) else 0
    near_ok = ok & np.isfinite(d_any) & (d_any < float(r_m))
    n_near = int(np.nansum(w[near_ok])) if np.any(near_ok) else 0
    d_ok = ok & np.isfinite(d_any)
    mean_any = (
        float(np.sum(d_any[d_ok] * w[d_ok]) / np.sum(w[d_ok])) if np.any(d_ok) else float("nan")
    )
    if grain == "near_0p10":
        g_comp = g[near_ok]
    else:
        g_comp = g[ok]
    if g_comp.empty:
        counts = pd.Series(dtype=np.float64)
    elif weighting == "bout_count":
        counts = g_comp.groupby("raw_syllable_id").size().astype(np.float64)
    else:
        counts = g_comp.groupby("raw_syllable_id")["bout_frames"].sum()
    tot = float(counts.sum()) if len(counts) else 0.0
    p = (counts / tot).to_dict() if tot > 0 else {}
    return {
        "n_frames": n_frames,
        "n_near_frames": n_near,
        "frac_near": float(n_near / n_frames) if n_frames > 0 else float("nan"),
        "mean_dist_any_m": mean_any,
        "richness": int((counts > 0).sum()) if len(counts) else 0,
        "shannon_bits": (
            shannon_bits(np.asarray(list(p.values()), dtype=np.float64)) if p else float("nan")
        ),
        "counts": counts.to_dict() if len(counts) else {},
    }


def build_animal_condition_table(
    bouts: pd.DataFrame,
    *,
    phase_layer: str,
    r_m: float = NEAR_R_M,
    grain: str = "full_session",
    weighting: str = "frame_share",
) -> pd.DataFrame:
    sub = bouts[bouts["phase_layer"] == phase_layer].copy()
    sub["animal_id"] = sub["animal_id"].astype(str)
    rows: list[dict[str, object]] = []
    for (aid, cond), g in sub.groupby(["animal_id", "condition_layer"], sort=True):
        if str(cond) not in CONDS:
            continue
        base = _animal_condition_row(g, r_m=r_m, grain=grain, weighting=weighting)
        rows.append(
            {
                "animal_id": str(aid),
                "sex": str(g["sex"].iloc[0]),
                "tx": str(g["tx"].iloc[0]),
                "phase_layer": phase_layer,
                "condition_layer": str(cond),
                "grain": grain,
                "weighting": weighting,
                "n_frames": base["n_frames"],
                "n_near_frames": base["n_near_frames"],
                "frac_near": base["frac_near"],
                "mean_dist_any_m": base["mean_dist_any_m"],
                "richness": base["richness"],
                "shannon_bits": base["shannon_bits"],
                "counts": base["counts"],
            }
        )
    return pd.DataFrame(rows)


def _paired_delta_table(
    ac: pd.DataFrame,
    *,
    step: str,
    left: str,
    right: str,
    metrics: tuple[str, ...],
    pair_col: str = "condition_layer",
) -> pd.DataFrame:
    L = ac[ac[pair_col] == left].set_index("animal_id")
    R = ac[ac[pair_col] == right].set_index("animal_id")
    if L.index.has_duplicates or R.index.has_duplicates:
        raise ValueError(
            f"duplicate animal_id after pairing on {pair_col}; filter the other axis first"
        )
    common = sorted(set(L.index) & set(R.index))
    rows = []
    for aid in common:
        row: dict[str, object] = {
            "animal_id": aid,
            "sex": str(L.loc[aid, "sex"]),
            "tx": str(L.loc[aid, "tx"]),
            "step": step,
            "left": left,
            "right": right,
        }
        for m in metrics:
            a = float(L.loc[aid, m])
            b = float(R.loc[aid, m])
            row[f"{m}_left"] = a
            row[f"{m}_right"] = b
            row[f"delta_{m}"] = b - a if np.isfinite(a) and np.isfinite(b) else float("nan")
        cl = L.loc[aid, "counts"]
        cr = R.loc[aid, "counts"]
        keys = sorted(set(cl) | set(cr))
        if not keys:
            row["braycurtis"] = float("nan")
        else:
            vl = np.array([float(cl.get(k, 0.0)) for k in keys], dtype=np.float64)
            vr = np.array([float(cr.get(k, 0.0)) for k in keys], dtype=np.float64)
            row["braycurtis"] = (
                float("nan")
                if vl.sum() <= 0 or vr.sum() <= 0
                else float(braycurtis(vl, vr))
            )
        rows.append(row)
    return pd.DataFrame(rows)


def wilcoxon_paired(deltas: np.ndarray) -> dict[str, object]:
    d = np.asarray(deltas, dtype=np.float64)
    d = d[np.isfinite(d)]
    if d.size < 2:
        return {
            "n": int(d.size),
            "median_delta": float("nan"),
            "frac_gt0": float("nan"),
            "stat": float("nan"),
            "p": float("nan"),
            "test": "wilcoxon_signed_rank",
        }
    if np.all(d == 0):
        return {
            "n": int(d.size),
            "median_delta": 0.0,
            "frac_gt0": 0.0,
            "stat": float("nan"),
            "p": float("nan"),
            "test": "wilcoxon_signed_rank",
        }
    stat, p = stats.wilcoxon(d, alternative="two-sided", zero_method="wilcox")
    return {
        "n": int(d.size),
        "median_delta": float(np.median(d)),
        "frac_gt0": float(np.mean(d > 0)),
        "stat": float(stat),
        "p": float(p),
        "test": "wilcoxon_signed_rank",
    }


def wilcoxon_control_arm_rows(
    dtab: pd.DataFrame,
    metrics: tuple[str, ...],
    *,
    extra: dict[str, object],
) -> list[dict[str, object]]:
    """Wilcoxon on Δ within sex, ``tx == noSD`` only (evolution I primary)."""
    rows: list[dict[str, object]] = []
    for sex in SEX_ORDER:
        sub = dtab[(dtab["sex"] == sex) & (dtab["tx"] == CONTROL_TX)]
        for m in metrics:
            rec = wilcoxon_paired(sub[f"delta_{m}"].to_numpy())
            rows.append(
                {
                    **extra,
                    "sex": sex,
                    "metric": m,
                    "question": "S0" if m in {"frac_near", "mean_dist_any_m", "frac_near", "mean_dist_any_m"} else "S1_S2",
                    **rec,
                    "hit_p05": bool(np.isfinite(rec["p"]) and float(rec["p"]) < 0.05),
                    "tx_stratum": TX_STRATUM_CONTROL,
                }
            )
    return rows


def restrict_tx_stratum(
    df: pd.DataFrame, stratum: str = TX_STRATUM_ALL
) -> pd.DataFrame:
    """Keep Wilcoxon/Kruskal rows for one tx pooling rule. Missing column = legacy."""
    if df.empty or "tx_stratum" not in df.columns:
        return df
    return df.loc[df["tx_stratum"] == stratum].copy()


DELTA_METRIC_COLS = (
    "delta_frac_near",
    "delta_mean_dist_any_m",
    "delta_richness",
    "delta_shannon_bits",
)

# Engagement scalars share physical units across kpMS alphabets.
# COUNT / UNCERTAINTY Δs do not when ss (K) differs — dispersion of magnitude
# across the full grid is exploratory only; prefer within-ss or sign agreement.
ENGAGEMENT_DELTA_METRICS = ("delta_frac_near", "delta_mean_dist_any_m")
COUNT_UNCERTAINTY_DELTA_METRICS = ("delta_richness", "delta_shannon_bits")
_SS_RE = re.compile(r"_ss-(\d+)(?:_|$)")


def model_num_states(model: str) -> int | float:
    """Parse kpMS alphabet size ``ss`` from ``paramscan_*_ss-N`` names."""
    m = _SS_RE.search(str(model))
    return int(m.group(1)) if m else float("nan")


def _mad(values: np.ndarray) -> float:
    v = np.asarray(values, dtype=np.float64)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return float("nan")
    med = float(np.median(v))
    return float(np.median(np.abs(v - med)))


def _iqr(values: np.ndarray) -> float:
    v = np.asarray(values, dtype=np.float64)
    v = v[np.isfinite(v)]
    if v.size < 2:
        return float("nan")
    q75, q25 = np.percentile(v, [75.0, 25.0])
    return float(q75 - q25)


def across_model_dispersion(
    deltas: pd.DataFrame,
    *,
    keys: tuple[str, ...] | None = None,
    metric_cols: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """Per-animal across-model dispersion of each paired Δ.

    One row = animal × grouping keys × metric. Primary salt columns: ``iqr``,
    ``mad``. ``sd`` / ``var`` are companions. ``iqr_over_abs_median`` is relative
    dispersion (NaN when |median| is tiny).

    ``magnitude_commensurate_across_models`` is True only for engagement Δs.
    """
    keys_l = list(keys or ("animal_id", "sex", "tx", "step", "phase_layer"))
    metrics = metric_cols or DELTA_METRIC_COLS
    need = {"model", *keys_l, *metrics}
    missing = need - set(deltas.columns)
    if missing:
        raise KeyError(f"across_model_dispersion missing columns: {sorted(missing)}")

    keys = keys_l
    rows: list[dict[str, object]] = []
    for key_vals, g in deltas.groupby(keys, sort=False):
        key_map = dict(zip(keys, key_vals if isinstance(key_vals, tuple) else (key_vals,)))
        n_models = int(g["model"].nunique())
        for metric in metrics:
            v = g[metric].to_numpy(dtype=np.float64)
            v = v[np.isfinite(v)]
            med = float(np.median(v)) if v.size else float("nan")
            iqr = _iqr(v)
            mad = _mad(v)
            if v.size >= 2:
                sd = float(np.std(v, ddof=1))
                var = float(np.var(v, ddof=1))
            else:
                sd = float("nan")
                var = float("nan")
            abs_med = abs(med)
            rel = float(iqr / abs_med) if np.isfinite(iqr) and abs_med > 1e-12 else float("nan")
            rows.append(
                {
                    **key_map,
                    "metric": metric,
                    "n_models": n_models,
                    "n_finite": int(v.size),
                    "median": med,
                    "mean": float(np.mean(v)) if v.size else float("nan"),
                    "iqr": iqr,
                    "mad": mad,
                    "sd": sd,
                    "var": var,
                    "min": float(np.min(v)) if v.size else float("nan"),
                    "max": float(np.max(v)) if v.size else float("nan"),
                    "iqr_over_abs_median": rel,
                    "magnitude_commensurate_across_models": metric in ENGAGEMENT_DELTA_METRICS,
                    "salt_role": (
                        "primary"
                        if metric in ENGAGEMENT_DELTA_METRICS
                        else "exploratory_only_not_commensurate_across_K"
                    ),
                }
            )
    return pd.DataFrame(rows)


def across_model_dispersion_summary(
    disp: pd.DataFrame,
    *,
    group_keys: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """Cohort salt: median of per-animal IQR/MAD within the grouping keys."""
    if disp.empty:
        return disp.copy()
    if group_keys is None:
        group_keys_l = ["phase_layer", "step", "metric"]
        if "ss" in disp.columns:
            group_keys_l = ["ss", *group_keys_l]
        if "condition_layer" in disp.columns and "phase_layer" not in disp.columns:
            group_keys_l = [c for c in ("condition_layer", "phase_step", "metric") if c in disp.columns]
    else:
        group_keys_l = list(group_keys)
    group_keys = group_keys_l
    rows: list[dict[str, object]] = []
    for key_vals, g in disp.groupby(group_keys, sort=True):
        key_map = dict(zip(group_keys, key_vals if isinstance(key_vals, tuple) else (key_vals,)))
        commensurate = bool(g["magnitude_commensurate_across_models"].iloc[0])
        salt_role = str(g["salt_role"].iloc[0])
        rows.append(
            {
                **key_map,
                "n_animals": int(len(g)),
                "median_of_median": float(g["median"].median()),
                "median_of_iqr": float(g["iqr"].median()),
                "median_of_mad": float(g["mad"].median()),
                "median_of_sd": float(g["sd"].median()),
                "median_of_iqr_over_abs_median": float(g["iqr_over_abs_median"].median()),
                "magnitude_commensurate_across_models": commensurate,
                "salt_role": salt_role,
            }
        )
    return pd.DataFrame(rows)


def across_model_dispersion_by_ss(deltas: pd.DataFrame) -> pd.DataFrame:
    """Same as ``across_model_dispersion``, but models pooled only within one ``ss``.

    Preferred salt path for COUNT / UNCERTAINTY Δs (alphabet size fixed).
    """
    d = deltas.copy()
    d["ss"] = d["model"].map(model_num_states)
    if not np.isfinite(d["ss"]).any():
        return pd.DataFrame()
    parts: list[pd.DataFrame] = []
    for ss, g in d.groupby("ss", sort=True):
        if not np.isfinite(ss):
            continue
        part = across_model_dispersion(g)
        part.insert(0, "ss", int(ss))
        # Within fixed K, magnitude is more defensible for COUNT/UNCERTAINTY.
        part["magnitude_commensurate_across_models"] = True
        part["salt_role"] = "within_ss_primary"
        parts.append(part)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def animal_median_across_models(deltas: pd.DataFrame) -> pd.DataFrame:
    """One row per animal × phase × step: median Δ across models."""
    keys = ["animal_id", "sex", "tx", "step", "phase_layer"]
    out = deltas.groupby(keys, as_index=False)[list(DELTA_METRIC_COLS)].median()
    n_mod = deltas.groupby(keys)["model"].nunique()
    if int(n_mod.min()) != int(n_mod.max()):
        raise AssertionError(f"uneven model coverage per animal: {n_mod.min()}–{n_mod.max()}")
    out["n_models"] = int(n_mod.min())
    return out


def consensus_tests(med: pd.DataFrame) -> pd.DataFrame:
    """Wilcoxon + Kruskal on animal-level median-across-models Δ.

    Grain is one animal (not 21 copies). Kruskal metric names are delta_* .
    """
    rows: list[dict[str, object]] = []
    n_models = int(med["n_models"].iloc[0]) if len(med) else 0
    empty_tx_med = {"median_noSD": "", "median_GHSD": "", "median_RBSD": ""}
    for (phase, step), g in med.groupby(["phase_layer", "step"], sort=False):
        for m in AGREE_METRICS:
            col = f"delta_{m}"
            q = "S0" if m in {"frac_near", "mean_dist_any_m"} else "S1_S2"
            rec = wilcoxon_paired(g[col].to_numpy())
            rows.append(
                {
                    "phase_layer": phase,
                    "step": step,
                    "sex": "all",
                    "metric": m,
                    "question": q,
                    **rec,
                    "hit_p05": bool(np.isfinite(rec["p"]) and float(rec["p"]) < 0.05),
                    "n_models": n_models,
                    "tx_stratum": TX_STRATUM_ALL,
                    **empty_tx_med,
                }
            )
            for sex in SEX_ORDER:
                rec_s = wilcoxon_paired(g.loc[g["sex"] == sex, col].to_numpy())
                rows.append(
                    {
                        "phase_layer": phase,
                        "step": step,
                        "sex": sex,
                        "metric": m,
                        "question": q,
                        **rec_s,
                        "hit_p05": bool(np.isfinite(rec_s["p"]) and float(rec_s["p"]) < 0.05),
                        "n_models": n_models,
                        "tx_stratum": TX_STRATUM_ALL,
                        **empty_tx_med,
                    }
                )
            rows.extend(
                wilcoxon_control_arm_rows(
                    g,
                    (m,),
                    extra={
                        "phase_layer": phase,
                        "step": step,
                        "n_models": n_models,
                        **empty_tx_med,
                    },
                )
            )
            k = kruskal_within_sex(
                pd.DataFrame(
                    {
                        "sex": g["sex"].to_numpy(),
                        "tx": g["tx"].to_numpy(),
                        m: g[col].to_numpy(),
                    }
                ),
                metric=m,
            )
            for _, r in k.iterrows():
                p = r["p"]
                rows.append(
                    {
                        "phase_layer": phase,
                        "step": step,
                        "sex": r["sex"],
                        "metric": f"delta_{m}",
                        "question": "tx_on_paired_delta",
                        "n": r["n"],
                        "median_delta": "",
                        "frac_gt0": "",
                        "stat": r["stat"],
                        "p": p,
                        "test": "kruskal",
                        "hit_p05": bool(pd.notna(p) and float(p) < 0.05),
                        "n_models": n_models,
                        "tx_stratum": TX_STRATUM_ALL,
                        "median_noSD": r["median_noSD"],
                        "median_GHSD": r["median_GHSD"],
                        "median_RBSD": r["median_RBSD"],
                    }
                )
    return pd.DataFrame(rows)


def tests_from_dtab(
    dtab: pd.DataFrame,
    *,
    metrics: tuple[str, ...],
    keys: dict[str, object],
) -> list[dict[str, object]]:
    """Wilcoxon (pooled + noSD-by-sex) and Kruskal on one paired Δ table."""
    test_rows: list[dict[str, object]] = []
    s0 = {"frac_near", "mean_dist_any_m", "frac_near", "mean_dist_any_m"}
    for m in metrics:
        rec = wilcoxon_paired(dtab[f"delta_{m}"].to_numpy())
        test_rows.append(
            {
                **keys,
                "sex": "all",
                "metric": m,
                "question": "S0" if m in s0 else "S1_S2",
                **rec,
                "hit_p05": bool(np.isfinite(rec["p"]) and float(rec["p"]) < 0.05),
                "tx_stratum": TX_STRATUM_ALL,
            }
        )
    bc = dtab["braycurtis"].to_numpy(dtype=np.float64) if "braycurtis" in dtab.columns else np.array([])
    bc = bc[np.isfinite(bc)]
    test_rows.append(
        {
            **keys,
            "sex": "all",
            "metric": "braycurtis_paired",
            "question": "S1_S2_DIFFERENCE",
            "n": int(bc.size),
            "median_delta": float(np.median(bc)) if bc.size else float("nan"),
            "frac_gt0": float(np.mean(bc > 0)) if bc.size else float("nan"),
            "stat": "",
            "p": "",
            "test": "descriptive_median_BC",
            "hit_p05": False,
            "tx_stratum": TX_STRATUM_ALL,
        }
    )
    for sex in SEX_ORDER:
        sub = dtab[dtab["sex"] == sex]
        for m in metrics:
            rec = wilcoxon_paired(sub[f"delta_{m}"].to_numpy())
            test_rows.append(
                {
                    **keys,
                    "sex": sex,
                    "metric": m,
                    "question": "S0" if m in s0 else "S1_S2",
                    **rec,
                    "hit_p05": bool(np.isfinite(rec["p"]) and float(rec["p"]) < 0.05),
                    "tx_stratum": TX_STRATUM_ALL,
                }
            )
    test_rows.extend(
        wilcoxon_control_arm_rows(
            dtab,
            metrics,
            extra=dict(keys),
        )
    )
    for m in metrics:
        k = kruskal_within_sex(
            pd.DataFrame(
                {
                    "sex": dtab["sex"].to_numpy(),
                    "tx": dtab["tx"].to_numpy(),
                    m: dtab[f"delta_{m}"].to_numpy(),
                }
            ),
            metric=m,
        )
        for _, r in k.iterrows():
            test_rows.append(
                {
                    **keys,
                    "sex": r["sex"],
                    "metric": f"delta_{m}",
                    "question": "tx_on_paired_delta",
                    "n": r["n"],
                    "median_delta": "",
                    "frac_gt0": "",
                    "stat": r["stat"],
                    "p": r["p"],
                    "test": "kruskal",
                    "hit_p05": bool(pd.notna(r["p"]) and float(r["p"]) < 0.05),
                    "tx_stratum": TX_STRATUM_ALL,
                    "median_noSD": r["median_noSD"],
                    "median_GHSD": r["median_GHSD"],
                    "median_RBSD": r["median_RBSD"],
                }
            )
    return test_rows


def rebuild_tests_from_delta_csv(deltas: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rebuild Wilcoxon/Kruskal rows from a saved per-animal Δ table (any name scheme)."""
    d = deltas.copy()
    if "model" not in d.columns:
        raise ValueError("delta table needs a model column")
    phase_col = "phase_layer" if "phase_layer" in d.columns else "phase_layer"
    step_col = "step"
    delta_cols = [c for c in d.columns if c.startswith("delta_")]
    metrics = tuple(c[len("delta_") :] for c in delta_cols)
    rows: list[dict[str, object]] = []
    for (model, phase, step), g in d.groupby(["model", phase_col, step_col], sort=False):
        recs = tests_from_dtab(
            g, metrics=metrics, keys={phase_col: phase, step_col: step}
        )
        for r in recs:
            r["model"] = model
        rows.extend(recs)
    tests = pd.DataFrame(rows)
    id_col = "animal_id" if "animal_id" in d.columns else "animal_id"
    med_keys = [id_col, "sex", "tx", step_col, phase_col]
    med = d.groupby(med_keys, as_index=False)[delta_cols].median()
    n_mod = d.groupby(med_keys)["model"].nunique()
    med["n_models"] = int(n_mod.min())
    if "braycurtis" in d.columns:
        med["braycurtis"] = d.groupby(med_keys)["braycurtis"].median().to_numpy()
    cons_rows: list[dict[str, object]] = []
    n_models = int(med["n_models"].iloc[0]) if len(med) else 0
    for (phase, step), g in med.groupby([phase_col, step_col], sort=False):
        recs = tests_from_dtab(
            g, metrics=metrics, keys={phase_col: phase, step_col: step}
        )
        for r in recs:
            r["n_models"] = n_models
        cons_rows.extend(recs)
    return tests, pd.DataFrame(cons_rows)


def run_phase(
    bout_csv: Path, phase: str, *, r_m: float = NEAR_R_M
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    bouts = pd.read_csv(bout_csv)
    ac = build_animal_condition_table(bouts, phase_layer=phase, r_m=r_m)
    metrics = ("frac_near", "mean_dist_any_m", "richness", "shannon_bits")
    delta_parts = []
    test_rows: list[dict[str, object]] = []
    for step, left, right in STEPS:
        dtab = _paired_delta_table(ac, step=step, left=left, right=right, metrics=metrics)
        dtab["phase_layer"] = phase
        delta_parts.append(dtab)
        test_rows.extend(
            tests_from_dtab(
                dtab, metrics=metrics, keys={"phase_layer": phase, "step": step}
            )
        )

    deltas = pd.concat(delta_parts, ignore_index=True)
    tests = pd.DataFrame(test_rows)

    def _hit(step: str, metric: str, sex: str = "all") -> bool:
        sub = tests[
            (tests["step"] == step)
            & (tests["metric"] == metric)
            & (tests["sex"] == sex)
            & (tests["test"] == "wilcoxon_signed_rank")
            & (tests["tx_stratum"] == TX_STRATUM_ALL)
        ]
        return bool(sub["hit_p05"].any()) if len(sub) else False

    summary = {
        "phase_layer": phase,
        "grain": f"animal × {phase} × condition_layer (full session)",
        "near_gate_for_frac": f"bout_mean_dist_any_m < {r_m:g} m",
        "n_animals": int(ac["animal_id"].nunique()),
        "presence_no_to_id": {
            m: ("hit" if _hit("no_obj->identical", m) else "miss") for m in AGREE_METRICS
        },
        "novelty_id_to_novel": {
            m: ("hit" if _hit("identical->novel", m) else "miss") for m in AGREE_METRICS
        },
    }
    return ac.drop(columns=["counts"]), deltas, tests, summary


def agreement_table(tests: pd.DataFrame) -> pd.DataFrame:
    """Fraction of models with hit + sign agreement (sex=all Wilcoxon)."""
    sub = tests[
        (tests["sex"].isin(("all", "all")))
        & (tests["test"] == "wilcoxon_signed_rank")
        & (tests["step"].isin(AGREE_STEPS))
        & (tests["metric"].isin(AGREE_METRICS))
    ].copy()
    if "tx_stratum" in sub.columns:
        sub = sub[sub["tx_stratum"] == TX_STRATUM_ALL]
    if sub.empty:
        return pd.DataFrame()
    rows = []
    pcol = "phase_layer" if "phase_layer" in sub.columns else "phase_layer"
    for (phase, step, metric), g in sub.groupby([pcol, "step", "metric"], sort=True):
        n = int(len(g))
        n_hit = int(g["hit_p05"].sum())
        signs = np.sign(pd.to_numeric(g["median_delta"], errors="coerce").to_numpy(dtype=float))
        signs = signs[np.isfinite(signs) & (signs != 0)]
        if signs.size:
            maj = int(np.sign(np.sum(signs)))
            n_agree_sign = int(np.sum(signs == maj))
        else:
            maj = 0
            n_agree_sign = 0
        rows.append(
            {
                "phase_layer": phase,
                "step": step,
                "metric": metric,
                "n_models": n,
                "n_hit_p05": n_hit,
                "frac_hit": float(n_hit / n) if n else float("nan"),
                "median_of_median_delta": float(pd.to_numeric(g["median_delta"]).median()),
                "sign_majority": maj,
                "n_models_agree_sign": n_agree_sign,
                "frac_sign_agree": float(n_agree_sign / signs.size) if signs.size else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def agreement_table_noSD_by_sex(tests: pd.DataFrame) -> pd.DataFrame:
    """Cross-model agreement for Wilcoxon on Δ, tx=noSD, within sex."""
    sub = tests[
        (tests["sex"].isin(SEX_ORDER))
        & (tests["test"] == "wilcoxon_signed_rank")
        & (tests["step"].isin(AGREE_STEPS))
        & (tests["metric"].isin(AGREE_METRICS))
    ].copy()
    if "tx_stratum" in sub.columns:
        sub = sub[sub["tx_stratum"] == TX_STRATUM_CONTROL]
    if sub.empty:
        return pd.DataFrame()
    rows = []
    pcol = "phase_layer" if "phase_layer" in sub.columns else "phase_layer"
    for (phase, step, metric, sex), g in sub.groupby(
        [pcol, "step", "metric", "sex"], sort=True
    ):
        n = int(len(g))
        n_hit = int(g["hit_p05"].sum())
        signs = np.sign(pd.to_numeric(g["median_delta"], errors="coerce").to_numpy(dtype=float))
        signs = signs[np.isfinite(signs) & (signs != 0)]
        if signs.size:
            maj = int(np.sign(np.sum(signs)))
            n_agree_sign = int(np.sum(signs == maj))
        else:
            maj = 0
            n_agree_sign = 0
        rows.append(
            {
                "phase_layer": phase,
                "step": step,
                "metric": metric,
                "sex": sex,
                "tx_stratum": TX_STRATUM_CONTROL,
                "n_models": n,
                "n_hit_p05": n_hit,
                "frac_hit": float(n_hit / n) if n else float("nan"),
                "median_of_median_delta": float(pd.to_numeric(g["median_delta"]).median()),
                "sign_majority": maj,
                "n_models_agree_sign": n_agree_sign,
                "frac_sign_agree": float(n_agree_sign / signs.size) if signs.size else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    root = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017")
    ap.add_argument("--ensemble-root", type=Path, default=root)
    ap.add_argument(
        "--model",
        type=str,
        default=None,
        help="Single model; default = all paramscan_* with bout CSVs",
    )
    ap.add_argument("--r-m", type=float, default=NEAR_R_M)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument(
        "--from-deltas",
        action="store_true",
        help="Rebuild tests from presence_step_deltas_per_animal.csv (no bout reload)",
    )
    ap.add_argument(
        "--skip-deltas",
        action="store_true",
        help="Skip per-animal delta CSV (tests + agreement only)",
    )
    args = ap.parse_args(argv)

    art_root = args.ensemble_root / "_nor_object_mi"
    out = args.out_dir or (art_root / "simpler_first_presence_steps")
    out.mkdir(parents=True, exist_ok=True)

    if args.from_deltas:
        delta_path = out / "presence_step_deltas_per_animal.csv"
        if not delta_path.exists():
            raise SystemExit(f"missing {delta_path}")
        print(f"rebuild tests from {delta_path}", flush=True)
        tests_df, cons = rebuild_tests_from_delta_csv(pd.read_csv(delta_path))
        tests_path = out / "presence_step_tests_long.csv"
        tests_df.to_csv(tests_path, index=False)
        if not cons.empty:
            cons.to_csv(out / "presence_step_consensus_tests.csv", index=False)
        models = sorted(tests_df["model"].unique().tolist()) if "model" in tests_df.columns else []
        agree = agreement_table(tests_df)
        agree_path = out / "presence_step_agreement_by_model.csv"
        if not agree.empty:
            agree.to_csv(agree_path, index=False)
        agree_ctrl = agreement_table_noSD_by_sex(tests_df)
        agree_ctrl_path = out / "presence_step_agreement_noSD_by_sex.csv"
        if not agree_ctrl.empty:
            agree_ctrl.to_csv(agree_ctrl_path, index=False)
        payload = {
            "n_models": len(models),
            "models": models,
            "r_m": float(args.r_m),
            "phases": [p for p, _ in PHASES],
            "n_test_rows": int(len(tests_df)),
            "tests_path": str(tests_path),
            "agreement_path": str(agree_path),
            "agreement_noSD_by_sex_path": str(agree_ctrl_path),
            "hit_rule": (
                "companion: sex=all Wilcoxon on paired delta, p<0.05, txs pooled"
            ),
            "hit_rule_evolution_primary": (
                "Wilcoxon on paired delta, tx=noSD, within sex, p<0.05 (tx_stratum=noSD)"
            ),
            "rebuilt_from_deltas": str(delta_path),
            "agreement": agree.to_dict(orient="records") if not agree.empty else [],
            "pilot_model_note": str(LOCKED["model"]),
        }
        (out / "run_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(
            json.dumps(
                {"path": str(out), "n_models": len(models), "n_test_rows": int(len(tests_df))},
                indent=2,
            )
        )
        return 0

    if args.model:
        models = [args.model]
    else:
        models = sorted(
            p.name
            for p in art_root.glob("paramscan_*")
            if p.is_dir()
            and any((p / tag / "ladder_bout_features.csv").exists() for _, tag in PHASES)
        )

    all_tests: list[pd.DataFrame] = []
    all_deltas: list[pd.DataFrame] = []
    n_jobs = len(models) * len(PHASES)
    done = 0
    for model in models:
        art = art_root / model
        for phase, tag in PHASES:
            done += 1
            bout_csv = art / tag / "ladder_bout_features.csv"
            if not bout_csv.exists():
                print(f"[{done}/{n_jobs}] MISSING {model} {phase}", flush=True)
                continue
            print(f"[{done}/{n_jobs}] {model} {phase}", flush=True)
            _ac, deltas, tests, _summary = run_phase(bout_csv, phase, r_m=float(args.r_m))
            tests = tests.copy()
            tests.insert(0, "model", model)
            all_tests.append(tests)
            if not args.skip_deltas:
                deltas = deltas.copy()
                deltas.insert(0, "model", model)
                all_deltas.append(deltas)

    tests_df = pd.concat(all_tests, ignore_index=True) if all_tests else pd.DataFrame()
    tests_path = out / "presence_step_tests_long.csv"
    tests_df.to_csv(tests_path, index=False)
    if all_deltas:
        deltas_df = pd.concat(all_deltas, ignore_index=True)
        deltas_df.to_csv(out / "presence_step_deltas_per_animal.csv", index=False)
        cons = consensus_tests(animal_median_across_models(deltas_df))
        cons.to_csv(out / "presence_step_consensus_tests.csv", index=False)
        disp = across_model_dispersion(deltas_df)
        disp.to_csv(out / "presence_step_across_model_dispersion.csv", index=False)
        across_model_dispersion_summary(disp).to_csv(
            out / "presence_step_across_model_dispersion_summary.csv", index=False
        )
        across_model_dispersion_summary(
            disp, group_keys=("sex", "phase_layer", "step", "metric")
        ).to_csv(
            out / "presence_step_across_model_dispersion_summary_by_sex.csv",
            index=False,
        )
        across_model_dispersion_summary(
            disp.loc[disp["tx"] == CONTROL_TX],
            group_keys=("sex", "phase_layer", "step", "metric"),
        ).to_csv(
            out / "presence_step_across_model_dispersion_summary_by_sex_noSD.csv",
            index=False,
        )
        disp_ss = across_model_dispersion_by_ss(deltas_df)
        if not disp_ss.empty:
            disp_ss.to_csv(out / "presence_step_across_model_dispersion_by_ss.csv", index=False)
            across_model_dispersion_summary(disp_ss).to_csv(
                out / "presence_step_across_model_dispersion_by_ss_summary.csv",
                index=False,
            )

    agree = agreement_table(tests_df)
    agree_path = out / "presence_step_agreement_by_model.csv"
    if not agree.empty:
        agree.to_csv(agree_path, index=False)
    agree_ctrl = agreement_table_noSD_by_sex(tests_df)
    agree_ctrl_path = out / "presence_step_agreement_noSD_by_sex.csv"
    if not agree_ctrl.empty:
        agree_ctrl.to_csv(agree_ctrl_path, index=False)

    payload = {
        "n_models": len(models),
        "models": models,
        "r_m": float(args.r_m),
        "phases": [p for p, _ in PHASES],
        "n_test_rows": int(len(tests_df)),
        "tests_path": str(tests_path),
        "agreement_path": str(agree_path),
        "agreement_noSD_by_sex_path": str(agree_ctrl_path),
        "hit_rule": (
            "companion: sex=all Wilcoxon on paired delta, p<0.05, txs pooled"
        ),
        "hit_rule_evolution_primary": (
            "Wilcoxon on paired delta, tx=noSD, within sex, p<0.05 (tx_stratum=noSD)"
        ),
        "agreement": agree.to_dict(orient="records") if not agree.empty else [],
        "pilot_model_note": str(LOCKED["model"]),
    }
    (out / "run_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if not agree.empty:
        print("\n=== cross-model agreement (sex=all Wilcoxon) ===", flush=True)
        show = agree.copy()
        show["frac_hit"] = show["frac_hit"].map(lambda x: f"{x:.2f}")
        show["frac_sign_agree"] = show["frac_sign_agree"].map(
            lambda x: f"{x:.2f}" if pd.notna(x) else ""
        )
        print(
            show[
                [
                    "phase_layer",
                    "step",
                    "metric",
                    "n_hit_p05",
                    "n_models",
                    "frac_hit",
                    "median_of_median_delta",
                    "sign_majority",
                    "frac_sign_agree",
                ]
            ].to_string(index=False),
            flush=True,
        )
    print(
        json.dumps(
            {"path": str(out), "n_models": len(models), "n_test_rows": int(len(tests_df))},
            indent=2,
        )
    )
    return 0


# Names used by tests / figures (keep both spellings).
TX_STRATUM_ALL = TX_STRATUM_ALL
TX_STRATUM_CONTROL = TX_STRATUM_CONTROL
restrict_tx_stratum = restrict_tx_stratum
wilcoxon_control_arm_rows = wilcoxon_control_arm_rows


if __name__ == "__main__":
    raise SystemExit(main())
