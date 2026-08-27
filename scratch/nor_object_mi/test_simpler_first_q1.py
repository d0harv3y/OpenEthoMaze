"""Litmus checks for Q1 Δ_prox (frame-weighted means)."""

from __future__ import annotations

import pandas as pd

from nor_object_mi.simpler_first_q1 import animal_delta_prox, judge_q1, kruskal_within_sex, weighted_mean


def test_weighted_mean_identity() -> None:
    assert weighted_mean([2.0, 2.0], [1, 99]) == 2.0
    assert abs(weighted_mean([0.0, 2.0], [1, 1]) - 1.0) < 1e-12


def test_delta_prox_known_case() -> None:
    rows = []
    for i, (fam, nvl, frames) in enumerate([(0.4, 0.1, 10), (0.4, 0.1, 30)]):
        rows.append(
            {
                "animal_id": "a1",
                "sex": "F",
                "tx": "noSD",
                "phase_layer": "NOR_TX",
                "condition_layer": "novel_obj",
                "bout_frames": frames,
                "bout_mean_dist_fam_m": fam,
                "bout_mean_dist_nvl_m": nvl,
            }
        )
    # identical_obj must be ignored
    rows.append(
        {
            "animal_id": "a1",
            "sex": "F",
            "tx": "noSD",
            "phase_layer": "NOR_TX",
            "condition_layer": "identical_obj",
            "bout_frames": 1000,
            "bout_mean_dist_fam_m": 9.0,
            "bout_mean_dist_nvl_m": 9.0,
        }
    )
    out = animal_delta_prox(pd.DataFrame(rows))
    assert len(out) == 1
    assert abs(float(out.loc[0, "delta_prox"]) - 0.3) < 1e-12
    assert abs(float(out.loc[0, "pref_nvl_closer"]) - 1.0) < 1e-12


def test_judge_q1_miss_when_ns() -> None:
    animals = pd.DataFrame(
        {
            "sex": ["F"] * 6 + ["M"] * 6,
            "tx": (["noSD", "GHSD", "RBSD"] * 4),
            "delta_prox": [0.01] * 12,
        }
    )
    tests = kruskal_within_sex(animals)
    v = judge_q1(tests)
    assert v["q1"] == "miss"
