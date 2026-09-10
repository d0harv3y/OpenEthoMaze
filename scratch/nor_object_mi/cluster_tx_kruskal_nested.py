"""Kruskal Δ²p ~ tx for nested DA (cluster / model overviews)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from nor_object_mi._pub_style import SEX_ORDER
from nor_object_mi.cluster13_tx_delta import kruskal_condition
from nor_object_mi.cluster_tx_kruskal import cluster_syllable_ids
from nor_object_mi.nested_da_delta import COND_STEP_LAB
from nor_object_mi.simpler_first_da import DA_STEPS, apply_bh_grouped
from nor_object_mi.simpler_first_phase_paired import PHASE_STEP_NAMES, STEP_LAB


def attach_model_cluster_deltas_nested(deltas: pd.DataFrame, cmap: pd.DataFrame) -> pd.DataFrame:
    """Keep cluster-mapped syllables; no step filter (nested uses condition_step + session_step)."""
    keys = cmap[["model", "raw_syllable_id"]].drop_duplicates()
    return deltas.merge(keys, on=["model", "raw_syllable_id"], how="inner")


def animal_delta_p_by_model_nested(mapped: pd.DataFrame, *, axis: str) -> pd.DataFrame:
    """One row per model × animal × inner_step × outer_step × tx."""
    if axis == "session_on_trial":
        inner, outer = "condition_step", "session_step"
    elif axis == "trial_on_session":
        inner, outer = "session_step", "condition_step"
    else:
        raise ValueError(axis)
    keys = ["model", "animal_id", "sex", "condition", inner, outer]
    rows: list[dict[str, object]] = []
    for key_vals, g in mapped.groupby(keys, sort=True):
        key_map = dict(zip(keys, key_vals if isinstance(key_vals, tuple) else (key_vals,)))
        v = pd.to_numeric(g["delta_p"], errors="coerce").to_numpy(dtype=np.float64)
        v = v[np.isfinite(v)]
        n_syll = int(g["raw_syllable_id"].nunique()) if "raw_syllable_id" in g.columns else 1
        rows.append(
            {
                **key_map,
                "delta_p": float(np.median(v)) if v.size else float("nan"),
                "n_syllables": n_syll,
                "n_finite": int(v.size),
            }
        )
    return pd.DataFrame(rows)


def kruskal_by_model_session_on_trial_sex(med: pd.DataFrame) -> pd.DataFrame:
    """Kruskal Δ²p ~ tx; panels = sex × condition_step; cols = session_step."""
    rows: list[dict[str, object]] = []
    models = sorted(str(x) for x in med["model"].unique())
    for model in models:
        sub_m = med[med["model"] == model]
        for cond_step in DA_STEPS:
            for session_step in PHASE_STEP_NAMES:
                for sex in SEX_ORDER:
                    g = sub_m[
                        (sub_m["condition_step"] == cond_step)
                        & (sub_m["session_step"] == session_step)
                        & (sub_m["sex"] == sex)
                    ]
                    rec = kruskal_condition(g)
                    rows.append(
                        {
                            "model": model,
                            "condition_step": cond_step,
                            "session_step": session_step,
                            "sex": sex,
                            **rec,
                        }
                    )
    out = pd.DataFrame(rows)
    return apply_bh_grouped(out, ["sex", "condition_step"])


def kruskal_by_model_trial_on_session_sex(med: pd.DataFrame) -> pd.DataFrame:
    """Kruskal Δ²p ~ tx; panels = sex × session_step; cols = condition_step."""
    rows: list[dict[str, object]] = []
    models = sorted(str(x) for x in med["model"].unique())
    for model in models:
        sub_m = med[med["model"] == model]
        for session_step in PHASE_STEP_NAMES:
            for cond_step in DA_STEPS:
                for sex in SEX_ORDER:
                    g = sub_m[
                        (sub_m["session_step"] == session_step)
                        & (sub_m["condition_step"] == cond_step)
                        & (sub_m["sex"] == sex)
                    ]
                    rec = kruskal_condition(g)
                    rows.append(
                        {
                            "model": model,
                            "session_step": session_step,
                            "condition_step": cond_step,
                            "sex": sex,
                            **rec,
                        }
                    )
    out = pd.DataFrame(rows)
    return apply_bh_grouped(out, ["sex", "session_step"])


__all__ = [
    "COND_STEP_LAB",
    "STEP_LAB",
    "animal_delta_p_by_model_nested",
    "attach_model_cluster_deltas_nested",
    "cluster_syllable_ids",
    "kruskal_by_model_trial_on_session_sex",
    "kruskal_by_model_session_on_trial_sex",
]
