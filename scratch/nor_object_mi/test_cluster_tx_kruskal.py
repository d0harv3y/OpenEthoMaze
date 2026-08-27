"""Litmus for cluster × phase Kruskal overview."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.cluster_tx_kruskal import (  # noqa: E402
    animal_delta_p_by_model,
    animal_median_delta_p_by_cluster,
    attach_cluster_ids,
    kruskal_by_cluster_phase_step_sex,
    kruskal_by_syllable_phase_step_sex,
    representative_cluster_ids,
)


def test_representative_picks_max_n_bouts() -> None:
    proto = pd.DataFrame(
        {
            "model": ["mA", "mA", "mA"],
            "cluster_id": [1, 1, 2],
            "raw_syllable_id": [10, 11, 20],
            "n_bouts": [5, 50, 8],
        }
    )
    rep = representative_cluster_ids(proto)
    assert len(rep) == 2
    row = rep[(rep["model"] == "mA") & (rep["cluster_id"] == 1)].iloc[0]
    assert int(row["raw_syllable_id"]) == 11


def test_kruskal_grid_shape() -> None:
    mapped = pd.DataFrame(
        {
            "cluster_id": [0, 0, 0, 0],
            "animal_id": [1, 1, 2, 2],
            "sex": ["F", "F", "F", "F"],
            "tx": ["noSD", "GHSD", "noSD", "GHSD"],
            "phase_layer": ["NOR_BL"] * 4,
            "step": ["no_obj->identical"] * 4,
            "delta_p": [0.01, 0.02, 0.5, 0.6],
            "model": ["m1", "m1", "m1", "m1"],
        }
    )
    med = animal_median_delta_p_by_cluster(mapped)
    kr = kruskal_by_cluster_phase_step_sex(med)
    assert len(kr) == 1 * 4 * 3 * 2  # 1 cluster, 4 phases, 3 steps, 2 sexes
    assert "q_bh" in kr.columns


def test_syllable_kruskal_grid_shape() -> None:
    animals = pd.DataFrame(
        {
            "raw_syllable_id": [3, 3, 3, 3, 7, 7, 7, 7],
            "animal_id": [1, 1, 2, 2, 1, 1, 2, 2],
            "sex": ["F"] * 8,
            "tx": ["noSD", "GHSD", "noSD", "GHSD"] * 2,
            "phase_layer": ["NOR_BL"] * 8,
            "step": ["no_obj->identical"] * 8,
            "delta_p": [0.01, 0.02, 0.5, 0.6, 0.0, 0.01, 0.02, 0.03],
        }
    )
    kr = kruskal_by_syllable_phase_step_sex(animals)
    # 2 syllables × 4 phases × 3 steps × 2 sexes
    assert len(kr) == 2 * 4 * 3 * 2
    assert "q_bh" in kr.columns
    assert set(kr["raw_syllable_id"]) == {3, 7}


def test_cluster13_merge_median_two_syllables() -> None:
    mapped = pd.DataFrame(
        {
            "model": ["mA", "mA", "mA", "mA"],
            "raw_syllable_id": [4, 9, 4, 9],
            "animal_id": [1, 1, 1, 1],
            "sex": ["F", "F", "F", "F"],
            "tx": ["noSD", "noSD", "GHSD", "GHSD"],
            "phase_layer": ["NOR_BL"] * 4,
            "step": ["no_obj->identical"] * 4,
            "delta_p": [0.10, 0.20, 0.30, 0.50],
        }
    )
    med = animal_delta_p_by_model(mapped)
    assert len(med) == 2
    nosd = med[med["tx"] == "noSD"].iloc[0]
    assert abs(float(nosd["delta_p"]) - 0.15) < 1e-9
    assert int(nosd["n_syllables"]) == 2
