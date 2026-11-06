"""Toy litmus for soft equate + accent residualize helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.alphabet_equate_soft_shape import (  # noqa: E402
    average_over_animals,
    paramscan_stem,
    residualize_within_animal,
    soft_nn_metrics,
)


def test_residualize_within_animal_zeros_median() -> None:
    df = pd.DataFrame(
        {
            "animal_id": ["a", "a", "b", "b"],
            "bout_mean_nose_tail_m": [0.10, 0.12, 0.20, 0.22],
            "bout_iqr_nose_tail_m": [0.01, 0.03, 0.02, 0.04],
        }
    )
    out = residualize_within_animal(
        df, ["bout_mean_nose_tail_m", "bout_iqr_nose_tail_m"]
    )
    assert abs(out.groupby("animal_id")["bout_mean_nose_tail_m"].median().sum()) < 1e-12


def test_paramscan_stem_strips_animal() -> None:
    assert (
        paramscan_stem("3115_paramscan_s1-1e7_s2-1e4_ss-50_ct-0.2")
        == "paramscan_s1-1e7_s2-1e4_ss-50_ct-0.2"
    )
    assert paramscan_stem("paramscan_s1-1e6_s2-1e4_ss-50") == "paramscan_s1-1e6_s2-1e4_ss-50"


def test_average_over_animals_pooled_collapses_animals() -> None:
    df = pd.DataFrame(
        {
            "animal_id": ["a", "b", "a"],
            "model": ["paramscan_x", "paramscan_x", "paramscan_x"],
            "raw_syllable_id": [1, 1, 2],
            "n_bouts": [3, 6, 3],
            "bout_mean_speed_mps": [0.1, 0.3, 0.5],
        }
    )
    out = average_over_animals(
        df, ["bout_mean_speed_mps"], layout="pooled", min_bouts=3
    )
    assert len(out) == 2
    row1 = out.loc[out["raw_syllable_id"] == 1].iloc[0]
    # bout-weighted: (0.1*3 + 0.3*6) / 9
    assert abs(float(row1["bout_mean_speed_mps"]) - (2.1 / 9.0)) < 1e-12
    assert int(row1["n_animals"]) == 2


def test_soft_nn_prefers_same_animal_when_clumped() -> None:
    # Two animals, well-separated clumps
    Z = np.vstack(
        [
            np.zeros((5, 2)),
            np.ones((5, 2)) * 10.0,
        ]
    )
    animals = np.array(["a"] * 5 + ["b"] * 5)
    m = soft_nn_metrics(Z, animals, k_neighborhood=3)
    assert m["frac_5nn_same_animal"] > 0.9
    assert m["mean_cross_animal_1nn_dist"] > 5.0
