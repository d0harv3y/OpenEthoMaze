"""Litmus for near-any gate and redefined Q1 preference."""

from __future__ import annotations

import pandas as pd

from nor_object_mi.simpler_first_near import animal_near_q1, gate_near_any


def test_gate_keeps_only_any_lt_r() -> None:
    rows = [
        {
            "animal_id": "a",
            "sex": "F",
            "tx": "noSD",
            "phase_layer": "NOR_TX",
            "condition_layer": "novel_obj",
            "bout_frames": 10,
            "bout_mean_dist_any_m": 0.05,
            "bout_mean_dist_fam_m": 0.20,
            "bout_mean_dist_nvl_m": 0.05,
            "raw_syllable_id": 1,
        },
        {
            "animal_id": "a",
            "sex": "F",
            "tx": "noSD",
            "phase_layer": "NOR_TX",
            "condition_layer": "novel_obj",
            "bout_frames": 10,
            "bout_mean_dist_any_m": 0.20,
            "bout_mean_dist_fam_m": 0.20,
            "bout_mean_dist_nvl_m": 0.25,
            "raw_syllable_id": 2,
        },
    ]
    sess, near = gate_near_any(pd.DataFrame(rows), phase_layer="NOR_TX", r_m=0.10)
    assert len(sess) == 2
    assert len(near) == 1
    assert float(near.iloc[0]["bout_mean_dist_any_m"]) == 0.05


def test_pref_among_near_known() -> None:
    # One near bout: nvl closer → pref=1; far bout ignored for pref
    rows = [
        {
            "animal_id": "a",
            "sex": "F",
            "tx": "noSD",
            "phase_layer": "NOR_TX",
            "condition_layer": "novel_obj",
            "bout_frames": 40,
            "bout_mean_dist_any_m": 0.05,
            "bout_mean_dist_fam_m": 0.30,
            "bout_mean_dist_nvl_m": 0.05,
            "raw_syllable_id": 1,
        },
        {
            "animal_id": "a",
            "sex": "F",
            "tx": "noSD",
            "phase_layer": "NOR_TX",
            "condition_layer": "novel_obj",
            "bout_frames": 60,
            "bout_mean_dist_any_m": 0.40,
            "bout_mean_dist_fam_m": 0.10,
            "bout_mean_dist_nvl_m": 0.40,
            "raw_syllable_id": 2,
        },
    ]
    df = pd.DataFrame(rows)
    sess, near = gate_near_any(df, phase_layer="NOR_TX", r_m=0.10)
    out = animal_near_q1(sess, near, phase_layer="NOR_TX", min_near_frames=10)
    assert len(out) == 1
    assert int(out.loc[0, "n_near_frames"]) == 40
    assert abs(float(out.loc[0, "frac_near"]) - 0.4) < 1e-12
    assert abs(float(out.loc[0, "pref_nvl_among_near"]) - 1.0) < 1e-12
    assert bool(out.loc[0, "kept"]) is True
