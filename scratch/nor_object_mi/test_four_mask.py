"""Litmus for four-mask (still|move × near|far) hunt."""

from __future__ import annotations

import numpy as np
import pandas as pd

from nor_object_mi.four_mask import (
    MASKS,
    gate_hits,
    hunt_tests,
    mask_name,
    near_flag,
    paired_tx_minus_bl,
    session_mask_table,
)


def test_mask_name_four_cells() -> None:
    loco = np.array(["still", "move", "move", "still", "", "still"])
    near = np.array(["near", "near", "far", "far", "near", ""])
    m = mask_name(loco, near)
    assert list(m) == ["still_near", "move_near", "move_far", "still_far", "", ""]


def test_near_flag_radius() -> None:
    d = np.array([0.05, 0.10, 0.11, np.nan])
    f = near_flag(d, r_m=0.10)
    assert list(f) == ["near", "far", "far", ""]


def test_session_mask_table_frac_and_shannon() -> None:
    labeled = pd.DataFrame(
        {
            "animal_id": ["a"] * 3,
            "phase_layer": ["NOR_BL"] * 3,
            "condition_layer": ["novel_obj"] * 3,
            "mask": ["still_near", "still_near", "move_far"],
            "raw_syllable_id": [1, 2, 1],
            "bout_frames": [10.0, 10.0, 20.0],
            "sex": ["F"] * 3,
            "tx": ["noSD"] * 3,
            "model": ["m"] * 3,
        }
    )
    tab = session_mask_table(labeled)
    assert set(tab["mask"]) == set(MASKS)
    sn = tab[tab["mask"] == "still_near"].iloc[0]
    mf = tab[tab["mask"] == "move_far"].iloc[0]
    empty = tab[tab["mask"] == "move_near"].iloc[0]
    np.testing.assert_allclose(float(sn["frac_mask"]), 0.5)
    np.testing.assert_allclose(float(mf["frac_mask"]), 0.5)
    np.testing.assert_allclose(float(empty["frac_mask"]), 0.0)
    np.testing.assert_allclose(float(sn["shannon_bits"]), 1.0)
    assert not np.isfinite(float(empty["shannon_bits"]))


def test_gate_hits_tx_specific_requires_novel_fdr_and_miss() -> None:
    rows = []
    for sex in ("F", "M"):
        for mask in MASKS:
            for metric in ("delta_frac_mask", "delta_shannon_bits"):
                hit = sex == "F" and mask == "still_near" and metric == "delta_frac_mask"
                rows.append(
                    {
                        "sex": sex,
                        "mask": mask,
                        "metric": metric,
                        "condition_layer": "novel_obj",
                        "contrast": "tx_minus_bl_by_tx",
                        "test": "welch_anova",
                        "p": 1e-6 if hit else 0.4,
                        "q_bh": 0.01 if hit else 0.8,
                        "hit_fdr05": hit,
                    }
                )
                for cond in ("identical_obj", "no_obj"):
                    rows.append(
                        {
                            "sex": sex,
                            "mask": mask,
                            "metric": metric,
                            "condition_layer": cond,
                            "contrast": "tx_minus_bl_by_tx",
                            "test": "welch_anova",
                            "p": 0.4,
                        }
                    )
                bl = "frac_mask" if metric == "delta_frac_mask" else "shannon_bits"
                rows.append(
                    {
                        "sex": sex,
                        "mask": mask,
                        "metric": bl,
                        "condition_layer": "novel_obj",
                        "contrast": "bl_level_by_tx",
                        "test": "welch_anova",
                        "p": 0.4,
                    }
                )
    g = gate_hits(pd.DataFrame(rows))
    spec = g[g["tx_specific"]]
    assert len(spec) == 1
    assert spec.iloc[0]["sex"] == "F"
    assert spec.iloc[0]["mask"] == "still_near"


def test_hunt_bh_is_within_sex() -> None:
    """8 primary ANOVA p's per sex; one tiny p should FDR-hit that sex only."""
    rng = np.random.default_rng(0)
    rows = []
    txs = ("noSD", "GHSD", "RBSD")
    for sex in ("F", "M"):
        for aid_i in range(6):
            tx = txs[aid_i % 3]
            for cond in ("novel_obj", "identical_obj", "no_obj"):
                for mask in MASKS:
                    bl = 0.25
                    bump = 0.0
                    if (
                        sex == "F"
                        and cond == "novel_obj"
                        and mask == "still_near"
                        and tx == "RBSD"
                    ):
                        bump = 0.4
                    noise = float(rng.normal(0, 0.01))
                    rows.append(
                        {
                            "animal_id": f"{sex}{aid_i}",
                            "sex": sex,
                            "tx": tx,
                            "condition_layer": cond,
                            "mask": mask,
                            "frac_mask_bl": bl,
                            "frac_mask_tx": bl + bump + noise,
                            "shannon_bits_bl": 1.0,
                            "shannon_bits_tx": 1.0 + float(rng.normal(0, 0.01)),
                        }
                    )
    paired = pd.DataFrame(rows)
    paired["delta_frac_mask"] = paired["frac_mask_tx"] - paired["frac_mask_bl"]
    paired["delta_shannon_bits"] = paired["shannon_bits_tx"] - paired["shannon_bits_bl"]
    tests = hunt_tests(paired)
    prim = tests[(tests["family"] == "primary") & (tests["test"] == "welch_anova")]
    assert len(prim) == 16
    f_hit = prim[(prim["sex"] == "F") & prim["hit_fdr05"]]
    assert len(f_hit) >= 1
    assert (f_hit["mask"] == "still_near").all()
    m_hit = prim[(prim["sex"] == "M") & prim["hit_fdr05"]]
    assert len(m_hit) == 0
    gates = gate_hits(tests)
    spec = gates[gates["tx_specific"]]
    assert len(spec) >= 1
    assert set(spec["sex"]) == {"F"}


def test_paired_inner_join_bl_tx() -> None:
    sess = pd.DataFrame(
        {
            "animal_id": ["a", "a", "a", "a"],
            "phase_layer": ["NOR_BL", "NOR_TX", "NOR_BL", "NOR_TX"],
            "condition_layer": ["novel_obj"] * 4,
            "mask": ["still_near", "still_near", "move_far", "move_far"],
            "sex": ["F"] * 4,
            "tx": ["noSD"] * 4,
            "frac_mask": [0.1, 0.2, 0.3, 0.4],
            "shannon_bits": [1.0, 1.5, 2.0, 2.1],
        }
    )
    p = paired_tx_minus_bl(sess)
    assert len(p) == 2
    sn = p[p["mask"] == "still_near"].iloc[0]
    np.testing.assert_allclose(float(sn["delta_frac_mask"]), 0.1)
    np.testing.assert_allclose(float(sn["delta_shannon_bits"]), 0.5)
