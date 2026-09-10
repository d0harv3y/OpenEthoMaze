"""Litmus for mean-per-model Kruskal aggregation."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.cluster_tx_mean_model_p import (  # noqa: E402
    aggregate_mean_p_models_as_family,
)


def test_mean_p_and_any_star() -> None:
    per = pd.DataFrame(
        {
            "model": ["m1", "m2", "m3"],
            "cluster_id": [0, 0, 0],
            "session": ["NOR_BL"] * 3,
            "step": ["no_obj->id_obj"] * 3,
            "sex": ["F"] * 3,
            "p": [0.001, 0.002, 0.90],
        }
    )
    agg = aggregate_mean_p_models_as_family(
        per,
        ["cluster_id", "session", "step", "sex"],
        star="any",
    )
    assert len(agg) == 1
    assert abs(float(agg.iloc[0]["mean_p"]) - (0.001 + 0.002 + 0.90) / 3) < 1e-12
    assert int(agg.iloc[0]["n_hit_fdr05_models"]) == 2
    assert bool(agg.iloc[0]["hit_fdr05"]) is True


def test_majority_star_stricter() -> None:
    per = pd.DataFrame(
        {
            "model": [f"m{i}" for i in range(5)],
            "cluster_id": [1] * 5,
            "trial": ["nvl_obj"] * 5,
            "session_step": ["BL->TX"] * 5,
            "sex": ["M"] * 5,
            "p": [0.001, 0.9, 0.9, 0.9, 0.9],
        }
    )
    any_hit = aggregate_mean_p_models_as_family(
        per, ["cluster_id", "trial", "session_step", "sex"], star="any"
    )
    maj = aggregate_mean_p_models_as_family(
        per, ["cluster_id", "trial", "session_step", "sex"], star="majority"
    )
    assert bool(any_hit.iloc[0]["hit_fdr05"]) is True
    assert bool(maj.iloc[0]["hit_fdr05"]) is False


def test_absent_models_count_as_non_hits() -> None:
    """Sparse cluster: 3/3 tested hit, but ensemble=21 → majority fails."""
    per = pd.DataFrame(
        {
            "model": ["a", "b", "c"],
            "cluster_id": [30, 30, 30],
            "session": ["NOR_TX"] * 3,
            "step": ["id_obj->nvl_obj"] * 3,
            "sex": ["F"] * 3,
            "p": [0.001, 0.002, 0.003],
        }
    )
    ensemble = [f"m{i}" for i in range(18)] + ["a", "b", "c"]
    maj = aggregate_mean_p_models_as_family(
        per,
        ["cluster_id", "session", "step", "sex"],
        star="majority",
        ensemble_models=ensemble,
    )
    assert int(maj.iloc[0]["n_ensemble"]) == 21
    assert int(maj.iloc[0]["n_absent"]) == 18
    assert int(maj.iloc[0]["n_hit_fdr05_models"]) == 3
    assert bool(maj.iloc[0]["hit_fdr05"]) is False

    # 11 hits among 11 present, ensemble 21 → majority (need >10.5)
    models = [f"m{i}" for i in range(21)]
    per11 = pd.DataFrame(
        {
            "model": models[:11],
            "cluster_id": [13] * 11,
            "session": ["NOR_TX"] * 11,
            "step": ["id_obj->nvl_obj"] * 11,
            "sex": ["F"] * 11,
            "p": [0.001] * 11,
        }
    )
    ok = aggregate_mean_p_models_as_family(
        per11,
        ["cluster_id", "session", "step", "sex"],
        star="majority",
        ensemble_models=models,
    )
    assert int(ok.iloc[0]["n_hit_fdr05_models"]) == 11
    assert bool(ok.iloc[0]["hit_fdr05"]) is True
