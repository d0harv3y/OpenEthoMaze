"""Mean-model Kruskal on scalar paired Δ (engagement / COUNT / UNCERTAINTY).

Same hidden-z design as cluster mean-model-p overviews, but rows = metrics
(not clusters): frac_near, mean_dist_any_m, richness, shannon_bits.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from nor_object_mi._pub_style import SESSIONS, SEX_ORDER
from nor_object_mi.cluster13_tx_delta import STEPS, kruskal_condition
from nor_object_mi.cluster_tx_kruskal_phase_paired import TRIALS, PHASE_STEPS
from nor_object_mi.cluster_tx_mean_model_p import StarRule, aggregate_mean_p_models_as_family

SCALAR_METRICS = ("frac_near", "mean_dist_any_m", "richness", "shannon_bits")
METRIC_LAB = {
    "frac_near": "frac_near",
    "mean_dist_any_m": "mean_dist",
    "richness": "richness",
    "shannon_bits": "shannon",
}


def kruskal_per_model_scalar_da(deltas: pd.DataFrame) -> pd.DataFrame:
    """Kruskal on delta_<metric> ~ tx per model × metric × phase × step × sex."""
    need = {"model", "animal_id", "sex", "condition", "session", "step"}
    missing = need - set(deltas.columns)
    if missing:
        raise ValueError(f"deltas missing {sorted(missing)}")
    rows: list[dict[str, object]] = []
    models = sorted(str(x) for x in deltas["model"].unique())
    for model in models:
        sub_m = deltas[deltas["model"].astype(str) == model]
        for metric in SCALAR_METRICS:
            col = f"delta_{metric}"
            if col not in sub_m.columns:
                raise ValueError(f"missing {col}")
            for phase in SESSIONS:
                for step in STEPS:
                    for sex in SEX_ORDER:
                        g = sub_m[
                            (sub_m["session"] == phase)
                            & (sub_m["step"] == step)
                            & (sub_m["sex"] == sex)
                        ]
                        rec = kruskal_condition(g, col=col)
                        rows.append(
                            {
                                "model": model,
                                "metric": metric,
                                "session": phase,
                                "step": step,
                                "sex": sex,
                                **rec,
                            }
                        )
    return pd.DataFrame(rows)


def kruskal_per_model_scalar_pp(deltas: pd.DataFrame) -> pd.DataFrame:
    """Kruskal on delta_<metric> ~ tx per model × metric × condition × session_step × sex."""
    need = {"model", "animal_id", "sex", "condition", "trial", "session_step"}
    missing = need - set(deltas.columns)
    if missing:
        raise ValueError(f"deltas missing {sorted(missing)}")
    rows: list[dict[str, object]] = []
    models = sorted(str(x) for x in deltas["model"].unique())
    for model in models:
        sub_m = deltas[deltas["model"].astype(str) == model]
        for metric in SCALAR_METRICS:
            col = f"delta_{metric}"
            if col not in sub_m.columns:
                raise ValueError(f"missing {col}")
            for cond in TRIALS:
                for step in PHASE_STEPS:
                    for sex in SEX_ORDER:
                        g = sub_m[
                            (sub_m["trial"] == cond)
                            & (sub_m["session_step"] == step)
                            & (sub_m["sex"] == sex)
                        ]
                        rec = kruskal_condition(g, col=col)
                        rows.append(
                            {
                                "model": model,
                                "metric": metric,
                                "trial": cond,
                                "session_step": step,
                                "sex": sex,
                                **rec,
                            }
                        )
    return pd.DataFrame(rows)


def aggregate_scalar_da(per_model: pd.DataFrame, *, star: StarRule = "majority") -> pd.DataFrame:
    return aggregate_mean_p_models_as_family(
        per_model,
        ["metric", "session", "step", "sex"],
        star=star,
    )


def aggregate_scalar_pp(per_model: pd.DataFrame, *, star: StarRule = "majority") -> pd.DataFrame:
    return aggregate_mean_p_models_as_family(
        per_model,
        ["metric", "trial", "session_step", "sex"],
        star=star,
    )


__all__ = [
    "METRIC_LAB",
    "SCALAR_METRICS",
    "aggregate_scalar_da",
    "aggregate_scalar_pp",
    "kruskal_per_model_scalar_da",
    "kruskal_per_model_scalar_pp",
]
