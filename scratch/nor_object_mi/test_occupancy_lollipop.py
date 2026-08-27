"""Litmus for occupancy × DA lollipop join."""

from __future__ import annotations

import numpy as np
import pandas as pd

from nor_object_mi.occupancy_lollipop import (
    consensus_across_models,
    join_da_occupancy,
    occupancy_tests,
    set_overlap_summary,
    signed_overlap_summary,
)


def test_occupancy_t_detects_move_enrichment() -> None:
    occ = pd.DataFrame(
        {
            "phase_layer": ["NOR_BL"] * 10,
            "raw_syllable_id": [7] * 10,
            "enrich_move": np.linspace(0.2, 0.4, 10),
        }
    )
    t = occupancy_tests(occ, min_n=8)
    assert len(t) == 1
    assert t.iloc[0]["locomotor_class"] == "move"
    assert bool(t.iloc[0]["hit_fdr05"])


def test_join_flags_da_hit_that_is_move() -> None:
    occ_t = pd.DataFrame(
        {
            "phase_layer": ["NOR_BL"],
            "raw_syllable_id": [7],
            "n": [10],
            "mean_enrich_move": [0.3],
            "median_enrich_move": [0.3],
            "p": [1e-6],
            "q_bh": [1e-5],
            "hit_fdr05": [True],
            "locomotor_class": ["move"],
        }
    )
    da = pd.DataFrame(
        {
            "model": ["m"] * 2,
            "phase_layer": ["NOR_BL", "NOR_BL"],
            "step": ["no_obj->identical", "no_obj->identical"],
            "raw_syllable_id": [7, 8],
            "median_delta_p": [0.02, -0.01],
            "hit_fdr05": [True, True],
        }
    )
    j = join_da_occupancy(da, occ_t, model="m")
    assert bool(j.loc[j["raw_syllable_id"] == 7, "da_and_move"].iloc[0])
    assert not bool(j.loc[j["raw_syllable_id"] == 8, "da_and_move"].iloc[0])
    s = set_overlap_summary(j)
    row = s[(s["phase_layer"] == "NOR_BL") & (s["step"] == "no_obj->identical")].iloc[0]
    assert int(row["n_da_and_move"]) == 1
    assert int(row["n_da_fdr"]) == 2


def test_consensus_median_frac_across_models() -> None:
    s = pd.DataFrame(
        {
            "model": ["a", "b", "c"],
            "phase_layer": ["NOR_BL"] * 3,
            "step": ["identical->novel"] * 3,
            "n_da_fdr": [4, 6, 0],
            "frac_da_move": [1.0, 0.5, np.nan],
            "frac_da_still": [0.0, 0.5, np.nan],
        }
    )
    c = consensus_across_models(s)
    row = c[(c["phase_layer"] == "NOR_BL") & (c["step"] == "identical->novel")].iloc[0]
    assert int(row["n_models"]) == 3
    assert int(row["n_models_with_da"]) == 2
    np.testing.assert_allclose(float(row["median_frac_da_move"]), 0.75)
    assert int(row["n_models_move_majority"]) == 1


def test_join_uses_destination_condition_occupancy() -> None:
    occ_t = pd.DataFrame(
        {
            "phase_layer": ["NOR_BL", "NOR_BL"],
            "condition_layer": ["identical_obj", "novel_obj"],
            "raw_syllable_id": [7, 7],
            "n": [10, 10],
            "mean_enrich_move": [-0.3, 0.3],
            "median_enrich_move": [-0.3, 0.3],
            "p": [1e-6, 1e-6],
            "q_bh": [1e-5, 1e-5],
            "hit_fdr05": [True, True],
            "locomotor_class": ["still", "move"],
        }
    )
    da = pd.DataFrame(
        {
            "model": ["m", "m"],
            "phase_layer": ["NOR_BL", "NOR_BL"],
            "step": ["no_obj->identical", "identical->novel"],
            "right": ["identical_obj", "novel_obj"],
            "raw_syllable_id": [7, 7],
            "median_delta_p": [0.02, 0.02],
            "hit_fdr05": [True, True],
        }
    )
    j = join_da_occupancy(da, occ_t, model="m")
    id_row = j[j["step"] == "no_obj->identical"].iloc[0]
    nv_row = j[j["step"] == "identical->novel"].iloc[0]
    assert id_row["locomotor_class"] == "still"
    assert bool(id_row["da_and_still"])
    assert nv_row["locomotor_class"] == "move"
    assert bool(nv_row["da_and_move"])


def test_signed_overlap_splits_gain_loss_by_occupancy() -> None:
    j = pd.DataFrame(
        {
            "phase_layer": ["NOR_BL"] * 4,
            "step": ["identical->novel"] * 4,
            "raw_syllable_id": [1, 2, 3, 4],
            "median_delta_p": [0.04, 0.02, -0.03, -0.01],
            "hit_da_fdr05": [True, True, True, True],
            "locomotor_class": ["move", "still", "move", "still"],
        }
    )
    s = signed_overlap_summary(j)
    row = s[(s["phase_layer"] == "NOR_BL") & (s["step"] == "identical->novel")].iloc[0]
    assert int(row["n_gain"]) == 2
    assert int(row["n_loss"]) == 2
    assert int(row["n_move_gain"]) == 1
    assert int(row["n_still_gain"]) == 1
    assert int(row["n_move_loss"]) == 1
    np.testing.assert_allclose(float(row["frac_gain_move"]), 0.5)
