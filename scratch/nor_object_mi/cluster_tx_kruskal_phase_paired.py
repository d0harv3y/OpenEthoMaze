"""Kruskal Δp ~ tx for between-phase paired DA (condition held).

Mirrors ``cluster13_tx_delta`` / ``cluster_tx_kruskal`` but pairing axis = phase
and facet = trial (not condition steps × NOR phase).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from nor_object_mi._pub_style import SEX_ORDER
from nor_object_mi.cluster13_tx_delta import _iqr, kruskal_condition
from nor_object_mi.cluster_tx_kruskal import (
    attach_column_bh,
    cluster_syllable_ids,
    order_cluster_ids,
    representative_cluster_ids,
)
from nor_object_mi.simpler_first_da import apply_bh, apply_bh_grouped
from nor_object_mi.simpler_first_phase_paired import PHASE_STEP_NAMES as PHASE_STEPS, STEP_LAB


def attach_cluster_ids(deltas: pd.DataFrame, rep: pd.DataFrame) -> pd.DataFrame:
    keys = rep[["model", "raw_syllable_id", "cluster_id"]].drop_duplicates()
    out = deltas.merge(keys, on=["model", "raw_syllable_id"], how="inner")
    if "session_step" in out.columns:
        return out[out["session_step"].isin(PHASE_STEPS)].copy()
    return out[out["step"].isin(PHASE_STEPS)].copy()


def attach_model_cluster_deltas(deltas: pd.DataFrame, cmap: pd.DataFrame) -> pd.DataFrame:
    keys = cmap[["model", "raw_syllable_id"]].drop_duplicates()
    out = deltas.merge(keys, on=["model", "raw_syllable_id"], how="inner")
    if "session_step" in out.columns:
        return out[out["session_step"].isin(PHASE_STEPS)].copy()
    return out[out["step"].isin(PHASE_STEPS)].copy()

TRIALS = ("no_obj", "id_obj", "nvl_obj")
COND_LAB = {
    "no_obj": "no_obj",
    "id_obj": "id_obj",
    "nvl_obj": "nvl_obj",
}


def filter_mapped_deltas(deltas: pd.DataFrame, id_map: pd.DataFrame) -> pd.DataFrame:
    """Keep mapped pause-syllable rows for all phase steps."""
    keys = id_map[["model", "raw_syllable_id"]].drop_duplicates()
    out = deltas.merge(keys, on=["model", "raw_syllable_id"], how="inner")
    if "session_step" in out.columns:
        return out[out["session_step"].isin(PHASE_STEPS)].copy()
    return out[out["step"].isin(PHASE_STEPS)].copy()


def animal_median_delta_p(mapped: pd.DataFrame) -> pd.DataFrame:
    """One row per animal × condition × session_step: median Δp across models."""
    step_col = "session_step" if "session_step" in mapped.columns else "step"
    keys = ["animal_id", "sex", "condition", "trial", step_col]
    rows: list[dict[str, object]] = []
    for key_vals, g in mapped.groupby(keys, sort=True):
        key_map = dict(zip(keys, key_vals if isinstance(key_vals, tuple) else (key_vals,)))
        if step_col != "session_step":
            key_map["session_step"] = key_map.pop(step_col)
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


def kruskal_by_trial_session_step_sex(med: pd.DataFrame) -> pd.DataFrame:
    """Kruskal Δp ~ tx inside each condition × session_step × sex."""
    rows: list[dict[str, object]] = []
    for cond in TRIALS:
        for step in PHASE_STEPS:
            for sex in SEX_ORDER:
                g = med[
                    (med["trial"] == cond)
                    & (med["session_step"] == step)
                    & (med["sex"] == sex)
                ]
                rec = kruskal_condition(g)
                rows.append({"trial": cond, "session_step": step, "sex": sex, **rec})
    return apply_bh(pd.DataFrame(rows))


def animal_median_delta_p_by_cluster(mapped: pd.DataFrame) -> pd.DataFrame:
    """One row per cluster × animal × condition × session_step."""
    step_col = "session_step" if "session_step" in mapped.columns else "step"
    keys = ["cluster_id", "animal_id", "sex", "condition", "trial", step_col]
    rows: list[dict[str, object]] = []
    for key_vals, g in mapped.groupby(keys, sort=True):
        key_map = dict(zip(keys, key_vals if isinstance(key_vals, tuple) else (key_vals,)))
        if step_col != "session_step":
            key_map["session_step"] = key_map.pop(step_col)
        v = pd.to_numeric(g["delta_p"], errors="coerce").to_numpy(dtype=float)
        v = v[v == v]
        rows.append(
            {
                **key_map,
                "delta_p": float(np.median(v)) if v.size else float("nan"),
                "n_models": int(g["model"].nunique()),
                "n_finite": int(v.size),
            }
        )
    return pd.DataFrame(rows)


def kruskal_by_cluster_trial_session_step_sex(med: pd.DataFrame) -> pd.DataFrame:
    """Kruskal Δp ~ tx inside each cluster × condition × session_step × sex.

    Panel BH family = cluster × session_step within each sex × condition.
    Column BH family = clusters within each sex × condition × session_step.
    """
    rows: list[dict[str, object]] = []
    clusters = order_cluster_ids(med["cluster_id"])
    for cid in clusters:
        sub_c = med[med["cluster_id"] == cid]
        for cond in TRIALS:
            for step in PHASE_STEPS:
                for sex in SEX_ORDER:
                    g = sub_c[
                        (sub_c["trial"] == cond)
                        & (sub_c["session_step"] == step)
                        & (sub_c["sex"] == sex)
                    ]
                    rec = kruskal_condition(g)
                    rows.append(
                        {
                            "cluster_id": cid,
                            "trial": cond,
                            "session_step": step,
                            "sex": sex,
                            **rec,
                        }
                    )
    out = apply_bh_grouped(pd.DataFrame(rows), ["sex", "trial"])
    return attach_column_bh(out, ["sex", "trial", "session_step"])

def animal_delta_p_by_model(mapped: pd.DataFrame) -> pd.DataFrame:
    """One row per model × animal × condition × session_step × tx."""
    step_col = "session_step" if "session_step" in mapped.columns else "step"
    keys = ["model", "animal_id", "sex", "condition", "trial", step_col]
    rows: list[dict[str, object]] = []
    for key_vals, g in mapped.groupby(keys, sort=True):
        key_map = dict(zip(keys, key_vals if isinstance(key_vals, tuple) else (key_vals,)))
        if step_col != "session_step":
            key_map["session_step"] = key_map.pop(step_col)
        v = pd.to_numeric(g["delta_p"], errors="coerce").to_numpy(dtype=float)
        v = v[np.isfinite(v)]
        rows.append(
            {
                **key_map,
                "delta_p": float(np.median(v)) if v.size else float("nan"),
                "n_syllables": int(g["raw_syllable_id"].nunique()),
                "n_finite": int(v.size),
            }
        )
    return pd.DataFrame(rows)


def kruskal_by_model_trial_session_step_sex(med: pd.DataFrame) -> pd.DataFrame:
    """Kruskal Δp ~ tx inside each model × condition × session_step × sex.

    BH family = model × session_step cells within each sex × condition panel.
    """
    rows: list[dict[str, object]] = []
    models = sorted(str(x) for x in med["model"].unique())
    for model in models:
        sub_m = med[med["model"] == model]
        for cond in TRIALS:
            for step in PHASE_STEPS:
                for sex in SEX_ORDER:
                    g = sub_m[
                        (sub_m["trial"] == cond)
                        & (sub_m["session_step"] == step)
                        & (sub_m["sex"] == sex)
                    ]
                    rec = kruskal_condition(g)
                    rows.append(
                        {
                            "model": model,
                            "trial": cond,
                            "session_step": step,
                            "sex": sex,
                            **rec,
                        }
                    )
    out = pd.DataFrame(rows)
    return apply_bh_grouped(out, ["sex", "trial"])


def kruskal_by_syllable_trial_session_step_sex(animals: pd.DataFrame) -> pd.DataFrame:
    """Kruskal Δp ~ tx inside each raw_syllable_id × condition × session_step × sex.

    Caller should pass one kpMS model. Panel BH family = all syllable × condition ×
    session_step cells within each sex (matches locus heatmap panels).
    """
    need = {
        "raw_syllable_id",
        "animal_id",
        "sex",
        "condition",
        "trial",
        "session_step",
        "delta_p",
    }
    missing = need - set(animals.columns)
    if missing:
        raise ValueError(f"animals missing {sorted(missing)}")
    rows: list[dict[str, object]] = []
    sylls = sorted(int(x) for x in animals["raw_syllable_id"].unique())
    for sid in sylls:
        sub_s = animals[animals["raw_syllable_id"] == sid]
        for cond in TRIALS:
            for step in PHASE_STEPS:
                for sex in SEX_ORDER:
                    g = sub_s[
                        (sub_s["trial"] == cond)
                        & (sub_s["session_step"] == step)
                        & (sub_s["sex"] == sex)
                    ]
                    rec = kruskal_condition(g)
                    rows.append(
                        {
                            "raw_syllable_id": sid,
                            "trial": cond,
                            "session_step": step,
                            "sex": sex,
                            "locus": f"{cond}|{step}",
                            **rec,
                        }
                    )
    out = pd.DataFrame(rows)
    return apply_bh_grouped(out, ["sex"])


def pp_locus_labels() -> list[str]:
    """Y-axis order matching co-occurrence x (sex stripped): alpha condition × steps."""
    return [f"{cond}|{step}" for cond in sorted(TRIALS) for step in PHASE_STEPS]


__all__ = [
    "TRIALS",
    "COND_LAB",
    "PHASE_STEPS",
    "STEP_LAB",
    "animal_delta_p_by_model",
    "animal_median_delta_p",
    "animal_median_delta_p_by_cluster",
    "attach_cluster_ids",
    "attach_model_cluster_deltas",
    "cluster_syllable_ids",
    "filter_mapped_deltas",
    "kruskal_by_cluster_trial_session_step_sex",
    "kruskal_by_trial_session_step_sex",
    "kruskal_by_model_trial_session_step_sex",
    "kruskal_by_syllable_trial_session_step_sex",
    "pp_locus_labels",
    "representative_cluster_ids",
]
