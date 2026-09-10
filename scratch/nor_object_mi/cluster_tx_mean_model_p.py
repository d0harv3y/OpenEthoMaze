"""Per-model Kruskal p, then mean across models (hidden z = alphabet).

For each model × cluster × locus × sex: Kruskal Δp_k ~ tx on that model's
representative syllable. Cell = mean uncorrected p across **tested** models.
BH (Benjamini–Hochberg) family = finite model p-values **within that cell**.

``hit_fdr05`` uses the full ensemble: models with no mapped syllable for that
cluster are scored as **non-hits** (default ``star='majority'`` → need more than
half of the ensemble, not half of the models that happen to carry the cluster).
"""

from __future__ import annotations

from typing import Literal, Sequence

import numpy as np
import pandas as pd

from nor_object_mi._pub_style import SESSIONS, SEX_ORDER
from nor_object_mi.cluster13_tx_delta import STEPS, kruskal_condition
from nor_object_mi.cluster_tx_kruskal import order_cluster_ids
from nor_object_mi.cluster_tx_kruskal_phase_paired import TRIALS, PHASE_STEPS
from nor_object_mi.simpler_first_da import apply_bh_grouped

StarRule = Literal["any", "majority", "all"]


def kruskal_per_model_cluster_da(mapped: pd.DataFrame) -> pd.DataFrame:
    """One Kruskal p per model × cluster × phase × step × sex (no BH yet)."""
    need = {
        "model",
        "cluster_id",
        "animal_id",
        "sex",
        "condition",
        "session",
        "step",
        "delta_p",
    }
    missing = need - set(mapped.columns)
    if missing:
        raise ValueError(f"mapped missing {sorted(missing)}")
    rows: list[dict[str, object]] = []
    models = sorted(str(x) for x in mapped["model"].unique())
    clusters = order_cluster_ids(mapped["cluster_id"])
    for model in models:
        sub_m = mapped[mapped["model"].astype(str) == model]
        for cid in clusters:
            sub_c = sub_m[sub_m["cluster_id"] == cid]
            if sub_c.empty:
                continue
            for phase in SESSIONS:
                for step in STEPS:
                    for sex in SEX_ORDER:
                        g = sub_c[
                            (sub_c["session"] == phase)
                            & (sub_c["step"] == step)
                            & (sub_c["sex"] == sex)
                        ]
                        rec = kruskal_condition(g)
                        rows.append(
                            {
                                "model": model,
                                "cluster_id": cid,
                                "session": phase,
                                "step": step,
                                "sex": sex,
                                **rec,
                            }
                        )
    return pd.DataFrame(rows)


def kruskal_per_model_cluster_pp(mapped: pd.DataFrame) -> pd.DataFrame:
    """One Kruskal p per model × cluster × condition × session_step × sex."""
    need = {
        "model",
        "cluster_id",
        "animal_id",
        "sex",
        "condition",
        "trial",
        "session_step",
        "delta_p",
    }
    missing = need - set(mapped.columns)
    if missing:
        raise ValueError(f"mapped missing {sorted(missing)}")
    rows: list[dict[str, object]] = []
    models = sorted(str(x) for x in mapped["model"].unique())
    clusters = order_cluster_ids(mapped["cluster_id"])
    for model in models:
        sub_m = mapped[mapped["model"].astype(str) == model]
        for cid in clusters:
            sub_c = sub_m[sub_m["cluster_id"] == cid]
            if sub_c.empty:
                continue
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
                                "model": model,
                                "cluster_id": cid,
                                "trial": cond,
                                "session_step": step,
                                "sex": sex,
                                **rec,
                            }
                        )
    return pd.DataFrame(rows)


def _cell_hit(n_hit: int, n_denom: int, star: StarRule) -> bool:
    """Star against ``n_denom`` (ensemble size); absent models already excluded from ``n_hit``."""
    if n_denom <= 0:
        return False
    if star == "any":
        return n_hit >= 1
    if star == "majority":
        return n_hit > (n_denom / 2.0)
    if star == "all":
        return n_hit == n_denom
    raise ValueError(f"unknown star rule: {star!r}")


def aggregate_mean_p_models_as_family(
    per_model: pd.DataFrame,
    cell_cols: list[str],
    *,
    star: StarRule = "majority",
    ensemble_models: Sequence[str] | None = None,
) -> pd.DataFrame:
    """BH across tested models within each cell; return mean_p + cell hit.

    Adds per-model ``q_bh`` / ``hit_fdr05`` first (BH family = models **with a
    finite p** in that cell). Mean/median/min ``p`` average those tested models
    only.

    Cell ``*`` uses the **ensemble** denominator: models missing from the cell
    (no mapped cluster syllable) count as non-hits. Default ``star='majority'``
    requires more than half of ``n_ensemble`` models to hit — not half of the
    models that carry the cluster.

    ``ensemble_models`` defaults to every distinct ``model`` in ``per_model``
    (typically the full paramscan set when the cache spans all clusters).
    """
    if per_model.empty:
        return pd.DataFrame()
    if "model" not in per_model.columns:
        raise ValueError("per_model needs a model column for ensemble non-hit scoring")
    if ensemble_models is None:
        ensemble = sorted({str(x) for x in per_model["model"].astype(str).unique()})
    else:
        ensemble = sorted({str(x) for x in ensemble_models})
    n_ensemble = len(ensemble)
    ensemble_set = set(ensemble)

    with_bh = apply_bh_grouped(per_model, cell_cols)
    rows: list[dict[str, object]] = []
    for key_vals, g in with_bh.groupby(cell_cols, sort=True):
        key_map = dict(
            zip(cell_cols, key_vals if isinstance(key_vals, tuple) else (key_vals,))
        )
        p = pd.to_numeric(g["p"], errors="coerce").to_numpy(dtype=np.float64)
        ok = np.isfinite(p)
        n_finite = int(ok.sum())
        hits = g["hit_fdr05"].fillna(False).astype(bool).to_numpy()
        n_hit = int(hits[ok].sum()) if n_finite else 0
        present = {str(x) for x in g["model"].astype(str).unique()}
        n_present = len(present & ensemble_set) if ensemble_set else len(present)
        n_absent = max(0, n_ensemble - n_present)
        rows.append(
            {
                **key_map,
                "p": float(np.mean(p[ok])) if n_finite else float("nan"),
                "mean_p": float(np.mean(p[ok])) if n_finite else float("nan"),
                "median_p": float(np.median(p[ok])) if n_finite else float("nan"),
                "min_p": float(np.min(p[ok])) if n_finite else float("nan"),
                "n_models": int(len(g)),
                "n_finite": n_finite,
                "n_present": n_present,
                "n_absent": n_absent,
                "n_ensemble": n_ensemble,
                "n_hit_fdr05_models": n_hit,
                "hit_fdr05": _cell_hit(n_hit, n_ensemble, star),
                "star_rule": star,
            }
        )
    return pd.DataFrame(rows)


__all__ = [
    "StarRule",
    "aggregate_mean_p_models_as_family",
    "kruskal_per_model_cluster_da",
    "kruskal_per_model_cluster_pp",
]
