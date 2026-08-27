"""Toy checks for cluster-13 Δp-by-tx helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.cluster13_tx_delta import (  # noqa: E402
    animal_median_delta_p,
    filter_mapped_deltas,
    kruskal_tx,
)


def test_filter_keeps_mapped_id_only() -> None:
    ids = pd.DataFrame({"model": ["a"], "raw_syllable_id": [7]})
    d = pd.DataFrame(
        {
            "model": ["a", "a", "b"],
            "raw_syllable_id": [7, 1, 7],
            "step": ["identical->novel"] * 3,
            "delta_p": [0.1, 0.2, 0.3],
            "animal_id": ["x", "x", "y"],
            "sex": ["F"] * 3,
            "tx": ["noSD"] * 3,
            "phase_layer": ["NOR_TX"] * 3,
        }
    )
    got = filter_mapped_deltas(d, ids)
    assert list(got["raw_syllable_id"]) == [7]
    assert list(got["model"]) == ["a"]


def test_animal_median_across_two_models() -> None:
    m = pd.DataFrame(
        {
            "animal_id": ["x", "x"],
            "sex": ["F", "F"],
            "tx": ["noSD", "noSD"],
            "phase_layer": ["NOR_TX", "NOR_TX"],
            "step": ["identical->novel", "identical->novel"],
            "model": ["m1", "m2"],
            "delta_p": [0.10, 0.20],
        }
    )
    out = animal_median_delta_p(m)
    assert len(out) == 1
    assert abs(float(out.iloc[0]["delta_p"]) - 0.15) < 1e-12
    assert int(out.iloc[0]["n_models"]) == 2
    assert abs(float(out.iloc[0]["iqr_across_models"]) - 0.05) < 1e-12


def test_kruskal_identical_groups_not_surprising() -> None:
    animals = pd.DataFrame(
        {
            "tx": ["noSD"] * 4 + ["GHSD"] * 4 + ["RBSD"] * 4,
            "delta_p": [0.0] * 12,
        }
    )
    rec = kruskal_tx(animals)
    assert rec["n"] == 12
    assert rec["p"] != rec["p"] or rec["p"] > 0.05  # NaN or large; identical values


def test_kruskal_separated_groups_hits() -> None:
    animals = pd.DataFrame(
        {
            "tx": ["noSD"] * 8 + ["GHSD"] * 8 + ["RBSD"] * 8,
            "delta_p": [0.0] * 8 + [0.01] * 8 + [0.20] * 8,
        }
    )
    rec = kruskal_tx(animals)
    assert rec["p"] < 0.01
    np.testing.assert_allclose(rec["median_RBSD"], 0.20)
