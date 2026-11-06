"""Litmus for nearest-object prox MI categories."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from nor_object_mi.nearest_prox_mi import (
    NEAREST_FAM,
    NEAREST_NEITHER,
    NEAREST_NVL,
    assign_nearest_prox_bin,
    animal_median_across_models,
    category_fractions,
    compute_nearest_prox_mi,
    label_for_row,
    mi_stratum_agreement_by_model,
    mi_stratum_summary,
    mi_stratum_tests,
)


def test_assign_nearest_prox_bin() -> None:
    assert assign_nearest_prox_bin(0.05, 0.20) == NEAREST_FAM
    assert assign_nearest_prox_bin(0.20, 0.05) == NEAREST_NVL
    assert assign_nearest_prox_bin(0.12, 0.15) == NEAREST_NEITHER
    assert assign_nearest_prox_bin(0.05, 0.08) == NEAREST_FAM
    assert assign_nearest_prox_bin(0.08, 0.05) == NEAREST_NVL
    assert assign_nearest_prox_bin(0.05, 0.05) == NEAREST_FAM


def test_category_fractions_sum_to_one() -> None:
    stim = np.array([0, 0, 1, 2, 2], dtype=np.int64)
    fr = category_fractions(stim)
    assert abs(fr["fam"] + fr["nvl"] + fr["neither"] - 1.0) < 1e-12


def test_compute_mi_on_toy_bouts() -> None:
    rows = []
    for bout in range(12):
        rows.append(
            {
                "animal_id": "a1",
                "sex": "F",
                "condition": "noSD",
                "session": "NOR_TX",
                "trial": "nvl_obj",
                "trial_key": "t1",
                "bout_index": bout,
                "raw_syllable_id": bout % 4,
                "bout_mean_dist_fam_m": 0.05 if bout % 3 == 0 else 0.20,
                "bout_mean_dist_nvl_m": 0.20 if bout % 3 == 0 else 0.06,
            }
        )
    out = compute_nearest_prox_mi(rows, n_perm=20, seed=0)
    assert len(out) == 1
    assert np.isfinite(out.iloc[0]["mi_mm"])
    assert np.isfinite(out.iloc[0]["H_stim"])


def test_mi_stratum_summary_groups() -> None:
    mi = pd.DataFrame(
        {
            "animal_id": ["a1", "a2", "a3", "a4"],
            "sex": ["F", "F", "M", "M"],
            "condition": ["noSD", "GHSD", "noSD", "GHSD"],
            "session": ["NOR_TX"] * 4,
            "mi_mm": [0.1, 0.2, 0.15, 0.05],
            "excess": [0.01, 0.02, 0.03, 0.0],
            "H_syll": [4.0, 4.1, 4.0, 4.2],
            "H_stim": [1.0, 1.1, 1.0, 1.2],
            "frac_fam": [0.1, 0.1, 0.1, 0.1],
            "frac_nvl": [0.2, 0.2, 0.2, 0.2],
            "frac_neither": [0.7, 0.7, 0.7, 0.7],
            "null_circ_p": [0.01, 0.2, 0.03, 0.5],
        }
    )
    out = mi_stratum_summary(mi)
    assert len(out) == 4
    f_nosd = out[(out.sex == "F") & (out.condition == "noSD")].iloc[0]
    assert f_nosd["median_mi_mm"] == 0.1


def test_mi_stratum_tests_runs() -> None:
    rows = []
    for i, (sex, condition) in enumerate(
        [
            ("F", "noSD"),
            ("F", "GHSD"),
            ("F", "RBSD"),
            ("M", "noSD"),
            ("M", "GHSD"),
            ("M", "RBSD"),
        ]
    ):
        rows.append(
            {
                "animal_id": f"a{i}",
                "sex": sex,
                "condition": condition,
                "session": "NOR_TX",
                "mi_mm": 0.1 + 0.05 * i,
                "excess": 0.01 * i,
            }
        )
    mi = pd.DataFrame(rows)
    tests = mi_stratum_tests(mi)
    assert len(tests) == 4
    assert "q_bh" in tests.columns


def test_label_for_row_cluster_map() -> None:
    row = {"raw_syllable_id": 4}
    cluster_map = {4: 13, 8: 47}
    assert label_for_row(row, label_kind="syllable") == 4
    assert label_for_row(row, label_kind="cluster", cluster_map=cluster_map) == 13
    assert label_for_row({"raw_syllable_id": 99}, label_kind="cluster", cluster_map=cluster_map) == -2


def test_cluster_mi_lowers_label_entropy() -> None:
    rows = []
    cluster_map = {0: 10, 1: 10, 2: 20, 3: 20}
    for bout in range(24):
        rows.append(
            {
                "animal_id": "a1",
                "sex": "F",
                "condition": "noSD",
                "session": "NOR_TX",
                "trial": "nvl_obj",
                "trial_key": "t1",
                "bout_index": bout,
                "raw_syllable_id": bout % 4,
                "bout_mean_dist_fam_m": 0.05 if bout % 2 == 0 else 0.20,
                "bout_mean_dist_nvl_m": 0.20 if bout % 2 == 0 else 0.06,
            }
        )
    syll = compute_nearest_prox_mi(rows, n_perm=10, seed=0, label_kind="syllable")
    clus = compute_nearest_prox_mi(
        rows, n_perm=10, seed=0, label_kind="cluster", cluster_map=cluster_map
    )
    assert syll.iloc[0]["H_syll"] > clus.iloc[0]["H_syll"]
    assert clus.iloc[0]["label_kind"] == "cluster"


def test_animal_median_across_models() -> None:
    rows = []
    for model, mi in [("m1", 0.10), ("m2", 0.20)]:
        rows.append(
            {
                "model": model,
                "animal_id": "a1",
                "sex": "F",
                "condition": "noSD",
                "session": "NOR_TX",
                "label_kind": "cluster",
                "r_m": 0.1,
                "mi_mm": mi,
                "excess": mi - 0.05,
                "H_syll": 2.5,
                "H_stim": 1.1,
                "frac_fam": 0.1,
                "frac_nvl": 0.2,
                "frac_neither": 0.7,
                "null_circ_mean": 0.05,
                "n_bouts": 100,
            }
        )
    long = pd.DataFrame(rows)
    cons = animal_median_across_models(long)
    assert len(cons) == 1
    assert cons.iloc[0]["mi_mm"] == pytest.approx(0.15)
    assert cons.iloc[0]["n_models"] == 2


def test_mi_stratum_agreement_by_model() -> None:
    tests = pd.DataFrame(
        {
            "model": ["m1", "m2", "m3"],
            "session": ["NOR_BL"] * 3,
            "sex": ["F"] * 3,
            "metric": ["mi_mm"] * 3,
            "p": [0.01, 0.20, 0.03],
            "hit_p05": [True, False, True],
        }
    )
    agr = mi_stratum_agreement_by_model(tests)
    assert len(agr) == 1
    assert agr.iloc[0]["n_hit_p05"] == 2
    assert abs(float(agr.iloc[0]["frac_hit"]) - 2 / 3) < 1e-12
