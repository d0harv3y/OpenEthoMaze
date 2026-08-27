"""Litmus for hysteresis locomotor presence step."""

from __future__ import annotations

import numpy as np
import pandas as pd

from nor_object_mi.locomotor_presence import (
    hunt_tests,
    paired_step_deltas,
    session_locomotor_table,
)


def test_session_p_move_from_frame_counts() -> None:
    move = pd.DataFrame(
        {
            "animal_id": ["a", "a"],
            "phase_layer": ["NOR_BL", "NOR_BL"],
            "condition_layer": ["no_obj", "no_obj"],
            "sex": ["F", "F"],
            "tx": ["noSD", "noSD"],
            "bout_frames": [10.0, 10.0],
            "bout_duration_s": [1.0, 1.0],
            "bout_mean_speed_mps": [0.2, 0.4],
            "bout_mean_dist_any_m": [0.2, 0.05],
        }
    )
    still = pd.DataFrame(
        {
            "animal_id": ["a"],
            "phase_layer": ["NOR_BL"],
            "condition_layer": ["no_obj"],
            "sex": ["F"],
            "tx": ["noSD"],
            "bout_frames": [20.0],
            "bout_duration_s": [2.0],
            "bout_mean_speed_mps": [0.01],
            "bout_mean_dist_any_m": [0.04],
        }
    )
    s = session_locomotor_table(move, still, r_m=0.10)
    assert len(s) == 1
    np.testing.assert_allclose(float(s.iloc[0]["p_move"]), 0.5)
    np.testing.assert_allclose(float(s.iloc[0]["frac_near"]), 30.0 / 40.0)
    np.testing.assert_allclose(float(s.iloc[0]["frac_near_move"]), 0.5)
    np.testing.assert_allclose(float(s.iloc[0]["mean_move_speed_mps"]), 0.3)


def test_presence_delta_is_right_minus_left() -> None:
    sess = pd.DataFrame(
        {
            "animal_id": ["a", "a"],
            "phase_layer": ["NOR_BL", "NOR_BL"],
            "condition_layer": ["no_obj", "identical_obj"],
            "sex": ["F", "F"],
            "tx": ["noSD", "noSD"],
            "p_move": [0.4, 0.55],
            "n_move_bouts": [5, 6],
            "n_still_bouts": [5, 4],
            "median_move_duration_s": [1.0, 1.2],
            "median_still_duration_s": [2.0, 2.0],
            "mean_move_speed_mps": [0.2, 0.2],
            "mean_dist_any_m": [0.3, 0.2],
            "frac_near": [0.1, 0.2],
            "frac_near_move": [0.05, 0.1],
            "frac_near_still": [0.15, 0.3],
        }
    )
    p = paired_step_deltas(sess)
    pr = p[p["step"] == "no_obj->identical"].iloc[0]
    np.testing.assert_allclose(float(pr["delta_p_move"]), 0.15)


def test_presence_ttest_hits_known_shift() -> None:
    rows = []
    for i in range(12):
        sex = "F" if i < 6 else "M"
        rows.append(
            {
                "animal_id": f"{sex}{i}",
                "phase_layer": "NOR_BL",
                "step": "no_obj->identical",
                "sex": sex,
                "tx": "noSD",
                "delta_p_move": 0.2,
                "delta_median_move_duration_s": 0.0,
                "delta_mean_move_speed_mps": 0.0,
                "delta_frac_near": 0.0,
                "delta_frac_near_move": 0.0,
            }
        )
    tests = hunt_tests(pd.DataFrame(rows))
    prim = tests[(tests["family"] == "primary") & (tests["metric"] == "p_move")]
    assert bool(prim["hit_fdr05"].all())
    assert (pd.to_numeric(prim["mean_delta"]) > 0).all()
