"""Cluster-13 pause syllable: animal Δp by tx (mapped id per model).

Filter per-animal DA deltas to the duration-band / cluster_id 13 id, then
median Δp across alphabets so one point is one animal (ids are not stacked).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from nor_object_mi._pub_style import PHASES, SEX_ORDER, TX_ORDER
from nor_object_mi.simpler_first_da import apply_bh

STEPS = ("no_obj->identical", "identical->novel", "no_obj->novel")
STEP_LAB = {
    "no_obj->identical": "presence",
    "identical->novel": "novelty",
    "no_obj->novel": "span",
}


def filter_mapped_deltas(deltas: pd.DataFrame, id_map: pd.DataFrame) -> pd.DataFrame:
    """Keep rows whose (model, raw_syllable_id) is the mapped pause syllable."""
    keys = id_map[["model", "raw_syllable_id"]].drop_duplicates()
    out = deltas.merge(keys, on=["model", "raw_syllable_id"], how="inner")
    return out[out["step"].isin(STEPS)].copy()


def _iqr(v: np.ndarray) -> float:
    v = np.asarray(v, dtype=np.float64)
    v = v[np.isfinite(v)]
    if v.size < 2:
        return float("nan")
    q75, q25 = np.percentile(v, [75.0, 25.0])
    return float(q75 - q25)


def animal_median_delta_p(mapped: pd.DataFrame) -> pd.DataFrame:
    """One row per animal × phase × step: median Δp and across-model IQR (salt)."""
    keys = ["animal_id", "sex", "tx", "phase_layer", "step"]
    rows: list[dict[str, object]] = []
    for key_vals, g in mapped.groupby(keys, sort=True):
        key_map = dict(zip(keys, key_vals if isinstance(key_vals, tuple) else (key_vals,)))
        v = pd.to_numeric(g["delta_p"], errors="coerce").to_numpy(dtype=np.float64)
        v = v[np.isfinite(v)]
        rows.append(
            {
                **key_map,
                "delta_p": float(np.median(v)) if v.size else float("nan"),
                "iqr_across_models": _iqr(v),
                "n_models": int(g["model"].nunique()),
                "n_finite": int(v.size),
            }
        )
    return pd.DataFrame(rows)


def kruskal_tx(animals: pd.DataFrame, *, col: str = "delta_p") -> dict[str, object]:
    """k-group rank test of Δp across tx (caller's sex filter)."""
    samples = []
    med: dict[str, float] = {}
    ns: dict[str, int] = {}
    for tx in TX_ORDER:
        v = pd.to_numeric(animals.loc[animals["tx"] == tx, col], errors="coerce")
        v = v.to_numpy(dtype=np.float64)
        v = v[np.isfinite(v)]
        samples.append(v)
        ns[tx] = int(v.size)
        med[tx] = float(np.median(v)) if v.size else float("nan")
    ok = all(s.size >= 2 for s in samples)
    if ok:
        stat, p = stats.kruskal(*samples)
        stat_f, p_f = float(stat), float(p)
    else:
        stat_f, p_f = float("nan"), float("nan")
    return {
        "test": "kruskal",
        "stat": stat_f,
        "p": p_f,
        "n": int(sum(ns.values())),
        **{f"n_{t}": ns[t] for t in TX_ORDER},
        **{f"median_{t}": med[t] for t in TX_ORDER},
    }


def kruskal_by_phase_step(med: pd.DataFrame) -> pd.DataFrame:
    """Kruskal Δp ~ tx inside each phase × step; BH family = those cells (sex pooled)."""
    rows: list[dict[str, object]] = []
    for phase in PHASES:
        for step in STEPS:
            g = med[(med["phase_layer"] == phase) & (med["step"] == step)]
            rec = kruskal_tx(g)
            rows.append({"phase_layer": phase, "step": step, "sex": "all", **rec})
    return apply_bh(pd.DataFrame(rows))


def kruskal_by_phase_step_sex(med: pd.DataFrame) -> pd.DataFrame:
    """Kruskal Δp ~ tx inside each phase × step × sex; BH family = those cells."""
    rows: list[dict[str, object]] = []
    for phase in PHASES:
        for step in STEPS:
            for sex in SEX_ORDER:
                g = med[
                    (med["phase_layer"] == phase)
                    & (med["step"] == step)
                    & (med["sex"] == sex)
                ]
                rec = kruskal_tx(g)
                rows.append({"phase_layer": phase, "step": step, "sex": sex, **rec})
    return apply_bh(pd.DataFrame(rows))
