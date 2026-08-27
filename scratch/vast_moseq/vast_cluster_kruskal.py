"""Cluster × session Δp group tests for VAST (mapped syllable per model × cluster)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from nor_object_mi._pub_style import SEX_ORDER
from nor_object_mi.simpler_first_da import apply_bh_grouped
from vast_moseq.cohort_meta import STRAIN_ORDER, TX_ORDER, norm_tx

VAST_PHASES = ("S01", "S02", "S03", "S04", "S05")
VAST_STEPS = ("mid_early", "late_mid", "late_early")
STEP_LAB = {
    "mid_early": "mid−early",
    "late_mid": "late−mid",
    "late_early": "late−early",
}
STX_LEVELS = tuple(f"{s}|{t}" for s in STRAIN_ORDER for t in TX_ORDER)


def attach_cluster_ids(deltas: pd.DataFrame, rep: pd.DataFrame) -> pd.DataFrame:
    keys = rep[["model", "raw_syllable_id", "cluster_id"]].drop_duplicates()
    out = deltas.merge(keys, on=["model", "raw_syllable_id"], how="inner")
    return out[out["step"].isin(VAST_STEPS)].copy()


def animal_median_delta_p_by_cluster(mapped: pd.DataFrame) -> pd.DataFrame:
    """One row per cluster × animal × session × step; median Δp across alphabets."""
    keys = ["cluster_id", "animal_id", "sex", "strain", "tx", "phase_layer", "step"]
    rows: list[dict[str, object]] = []
    for key_vals, g in mapped.groupby(keys, sort=True):
        key_map = dict(zip(keys, key_vals if isinstance(key_vals, tuple) else (key_vals,)))
        v = pd.to_numeric(g["delta_p"], errors="coerce").to_numpy(dtype=float)
        v = v[np.isfinite(v)]
        rows.append(
            {
                **key_map,
                "delta_p": float(np.median(v)) if v.size else float("nan"),
                "n_models": int(g["model"].nunique()),
                "n_finite": int(v.size),
            }
        )
    return pd.DataFrame(rows)


def _samples_by_level(
    animals: pd.DataFrame,
    *,
    factor: str,
    levels: tuple[str, ...],
    col: str = "delta_p",
) -> tuple[list[np.ndarray], dict[str, int], dict[str, float]]:
    samples: list[np.ndarray] = []
    ns: dict[str, int] = {}
    meds: dict[str, float] = {}
    for level in levels:
        v = pd.to_numeric(animals.loc[animals[factor] == level, col], errors="coerce")
        v = v.to_numpy(dtype=np.float64)
        v = v[np.isfinite(v)]
        samples.append(v)
        ns[level] = int(v.size)
        meds[level] = float(np.median(v)) if v.size else float("nan")
    return samples, ns, meds


def _mann_whitney_two(
    animals: pd.DataFrame,
    *,
    factor: str,
    level_a: str,
    level_b: str,
    col: str = "delta_p",
) -> dict[str, object]:
    samples, ns, meds = _samples_by_level(animals, factor=factor, levels=(level_a, level_b), col=col)
    va, vb = samples
    ok = va.size >= 2 and vb.size >= 2
    if ok:
        stat, p = stats.mannwhitneyu(va, vb, alternative="two-sided")
        stat_f, p_f = float(stat), float(p)
    else:
        stat_f, p_f = float("nan"), float("nan")
    return {
        "test": "mannwhitneyu",
        "contrast_factor": factor,
        "level_a": level_a,
        "level_b": level_b,
        "stat": stat_f,
        "p": p_f,
        "n": int(va.size + vb.size),
        f"n_{level_a}": ns[level_a],
        f"n_{level_b}": ns[level_b],
        f"median_{level_a}": meds[level_a],
        f"median_{level_b}": meds[level_b],
    }


def _kruskal_k(
    animals: pd.DataFrame,
    *,
    factor: str,
    levels: tuple[str, ...],
    col: str = "delta_p",
) -> dict[str, object]:
    samples, ns, meds = _samples_by_level(animals, factor=factor, levels=levels, col=col)
    ok = all(s.size >= 2 for s in samples)
    if ok:
        stat, p = stats.kruskal(*samples)
        stat_f, p_f = float(stat), float(p)
    else:
        stat_f, p_f = float("nan"), float("nan")
    out: dict[str, object] = {
        "test": "kruskal",
        "contrast_factor": factor,
        "level_a": "(all)",
        "level_b": "",
        "stat": stat_f,
        "p": p_f,
        "n": int(sum(ns.values())),
    }
    for level in levels:
        safe = level.replace("|", "_")
        out[f"n_{safe}"] = ns[level]
        out[f"median_{safe}"] = meds[level]
    return out


def _with_stx_label(med: pd.DataFrame) -> pd.DataFrame:
    out = med.copy()
    out["tx"] = out["tx"].map(norm_tx)
    out["stx"] = out["strain"].astype(str) + "|" + out["tx"].astype(str)
    return out


def kruskal_by_cluster_session_step_sex_tx_pairwise(med: pd.DataFrame) -> pd.DataFrame:
    """Mann–Whitney Δp ~ tx (RBSF-1 vs n/a); strain pooled; within sex."""
    rows: list[dict[str, object]] = []
    clusters = sorted(int(x) for x in med["cluster_id"].unique())
    for cid in clusters:
        sub_c = med[med["cluster_id"] == cid]
        for phase in VAST_PHASES:
            for step in VAST_STEPS:
                for sex in SEX_ORDER:
                    g = sub_c[
                        (sub_c["phase_layer"] == phase)
                        & (sub_c["step"] == step)
                        & (sub_c["sex"] == sex)
                    ]
                    rec = _mann_whitney_two(
                        g,
                        factor="tx",
                        level_a=TX_ORDER[0],
                        level_b=TX_ORDER[1],
                    )
                    rows.append(
                        {
                            "cluster_id": cid,
                            "phase_layer": phase,
                            "step": step,
                            "sex": sex,
                            **rec,
                        }
                    )
    return apply_bh_grouped(pd.DataFrame(rows), ["sex", "step"])


def kruskal_by_cluster_session_step_sex_strain_pairwise(med: pd.DataFrame) -> pd.DataFrame:
    """Mann–Whitney Δp ~ strain (wt vs tg); tx pooled; within sex."""
    rows: list[dict[str, object]] = []
    clusters = sorted(int(x) for x in med["cluster_id"].unique())
    for cid in clusters:
        sub_c = med[med["cluster_id"] == cid]
        for phase in VAST_PHASES:
            for step in VAST_STEPS:
                for sex in SEX_ORDER:
                    g = sub_c[
                        (sub_c["phase_layer"] == phase)
                        & (sub_c["step"] == step)
                        & (sub_c["sex"] == sex)
                    ]
                    rec = _mann_whitney_two(
                        g,
                        factor="strain",
                        level_a=STRAIN_ORDER[0],
                        level_b=STRAIN_ORDER[1],
                    )
                    rows.append(
                        {
                            "cluster_id": cid,
                            "phase_layer": phase,
                            "step": step,
                            "sex": sex,
                            **rec,
                        }
                    )
    return apply_bh_grouped(pd.DataFrame(rows), ["sex", "step"])


def kruskal_by_cluster_session_step_sex_stx(med: pd.DataFrame) -> pd.DataFrame:
    """Kruskal Δp ~ strain×tx (4 groups); within sex."""
    labeled = _with_stx_label(med)
    rows: list[dict[str, object]] = []
    clusters = sorted(int(x) for x in labeled["cluster_id"].unique())
    for cid in clusters:
        sub_c = labeled[labeled["cluster_id"] == cid]
        for phase in VAST_PHASES:
            for step in VAST_STEPS:
                for sex in SEX_ORDER:
                    g = sub_c[
                        (sub_c["phase_layer"] == phase)
                        & (sub_c["step"] == step)
                        & (sub_c["sex"] == sex)
                    ]
                    rec = _kruskal_k(g, factor="stx", levels=STX_LEVELS)
                    rows.append(
                        {
                            "cluster_id": cid,
                            "phase_layer": phase,
                            "step": step,
                            "sex": sex,
                            **rec,
                        }
                    )
    return apply_bh_grouped(pd.DataFrame(rows), ["sex", "step"])
