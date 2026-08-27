"""Litmus checks for paired syllable DA (differential abundance)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from nor_object_mi.simpler_first_da import (
    apply_bh,
    benjamini_hochberg,
    consistency_phase_pairs,
    da_tests_from_deltas,
    da_tests_tx_sex_from_animal_deltas,
    delta_p_and_bc_contrib,
    jaccard,
    paired_da_deltas,
    run_phase_da,
    syllable_persistence,
)
from nor_object_mi.simpler_first_presence import build_animal_condition_table


def test_benjamini_hochberg_worked_examples() -> None:
    assert benjamini_hochberg([]) == []
    assert benjamini_hochberg([0.01]) == [0.01]
    q = benjamini_hochberg([0.01, 1.0])
    assert abs(q[0] - 0.02) < 1e-12
    assert abs(q[1] - 1.0) < 1e-12
    q2 = benjamini_hochberg([0.01, 0.04, 0.03])
    assert abs(q2[0] - 0.03) < 1e-12
    assert abs(q2[1] - 0.04) < 1e-12
    assert abs(q2[2] - 0.04) < 1e-12


def test_delta_p_swap_and_bc_contrib_sums_to_one() -> None:
    left = {1: 80.0, 2: 20.0}
    right = {1: 20.0, 2: 80.0}
    delta, contrib, bc = delta_p_and_bc_contrib(left, right)
    assert abs(delta[1] - (-0.6)) < 1e-12
    assert abs(delta[2] - 0.6) < 1e-12
    assert abs(contrib[1] - 0.5) < 1e-12
    assert abs(contrib[2] - 0.5) < 1e-12
    assert abs(sum(contrib.values()) - 1.0) < 1e-12
    assert abs(bc - 0.6) < 1e-12  # 0.5 * (|−0.6| + |0.6|)


def test_delta_p_identical_compositions() -> None:
    counts = {3: 50.0, 7: 50.0}
    delta, contrib, bc = delta_p_and_bc_contrib(counts, counts)
    assert delta[3] == 0.0 and delta[7] == 0.0
    assert contrib[3] == 0.0 and contrib[7] == 0.0
    assert bc == 0.0


def _bouts_one_animal_swap() -> pd.DataFrame:
    rows = []
    for cond, frames_by_syll in (
        ("no_obj", {1: 80, 2: 20}),
        ("identical_obj", {1: 20, 2: 80}),
        ("novel_obj", {1: 20, 2: 80}),
    ):
        for sid, fr in frames_by_syll.items():
            rows.append(
                {
                    "animal_id": "a1",
                    "sex": "F",
                    "tx": "noSD",
                    "phase_layer": "NOR_TX",
                    "condition_layer": cond,
                    "raw_syllable_id": sid,
                    "bout_frames": fr,
                    "bout_mean_dist_any_m": 0.20,
                }
            )
    return pd.DataFrame(rows)


def test_paired_da_deltas_presence_step() -> None:
    ac = build_animal_condition_table(_bouts_one_animal_swap(), phase_layer="NOR_TX")
    dtab = paired_da_deltas(
        ac,
        step="no_obj->identical",
        left="no_obj",
        right="identical_obj",
        pair_col="condition_layer",
    )
    assert set(dtab["raw_syllable_id"]) == {1, 2}
    d1 = float(dtab.loc[dtab["raw_syllable_id"] == 1, "delta_p"].iloc[0])
    d2 = float(dtab.loc[dtab["raw_syllable_id"] == 2, "delta_p"].iloc[0])
    assert abs(d1 - (-0.6)) < 1e-12
    assert abs(d2 - 0.6) < 1e-12
    assert str(dtab["phase_layer"].iloc[0]) == "NOR_TX"


def test_da_wilcoxon_hits_consistent_share_shift() -> None:
    rows = []
    for i in range(8):
        aid = f"a{i}"
        for cond, frames_by_syll in (
            ("no_obj", {1: 90, 2: 10}),
            ("identical_obj", {1: 10, 2: 90}),
        ):
            for sid, fr in frames_by_syll.items():
                rows.append(
                    {
                        "animal_id": aid,
                        "sex": "F",
                        "tx": "noSD",
                        "phase_layer": "NOR_TX",
                        "condition_layer": cond,
                        "raw_syllable_id": sid,
                        "bout_frames": fr,
                        "bout_mean_dist_any_m": 0.20,
                    }
                )
    ac = build_animal_condition_table(pd.DataFrame(rows), phase_layer="NOR_TX")
    dtab = paired_da_deltas(
        ac,
        step="no_obj->identical",
        left="no_obj",
        right="identical_obj",
        pair_col="condition_layer",
    )
    tests = da_tests_from_deltas(dtab)
    assert len(tests) == 2
    assert bool(tests["hit_p05"].all())
    assert bool(tests["hit_fdr05"].all())
    s1 = tests.loc[tests["raw_syllable_id"] == 1].iloc[0]
    s2 = tests.loc[tests["raw_syllable_id"] == 2].iloc[0]
    assert float(s1["median_delta_p"]) < 0
    assert float(s2["median_delta_p"]) > 0


def test_apply_bh_marks_fdr_hits() -> None:
    df = pd.DataFrame({"raw_syllable_id": [1, 2], "p": [0.01, 1.0]})
    out = apply_bh(df)
    assert abs(float(out.loc[0, "q_bh"]) - 0.02) < 1e-12
    assert bool(out.loc[0, "hit_p05"]) and bool(out.loc[0, "hit_fdr05"])
    assert not bool(out.loc[1, "hit_p05"]) and not bool(out.loc[1, "hit_fdr05"])


def test_jaccard_and_consistency_within_model() -> None:
    assert abs(jaccard({1, 2}, {2, 3}) - 1 / 3) < 1e-12
    tests = pd.DataFrame(
        {
            "model": ["m"] * 6,
            "step": ["no_obj->identical"] * 6,
            "phase_layer": ["NOR_BL", "NOR_BL", "NOR_TX", "NOR_TX", "NOR_TX", "NOR_REC3hr"],
            "raw_syllable_id": [1, 2, 1, 2, 3, 1],
            "median_delta_p": [0.1, -0.1, 0.2, -0.05, 0.01, 0.15],
            "hit_fdr05": [True, True, True, False, True, True],
            "hit_p05": [True, True, True, True, True, True],
        }
    )
    pairs = consistency_phase_pairs(
        tests, facet_col="phase_layer", group_cols=("model", "step")
    )
    bl_tx = pairs[
        (pairs["phase_layer_a"] == "NOR_BL") & (pairs["phase_layer_b"] == "NOR_TX")
    ].iloc[0]
    # BL hits {1,2}, TX hits {1,3} → Jaccard 1/3
    assert int(bl_tx["n_hit_both"]) == 1
    assert abs(float(bl_tx["jaccard"]) - 1 / 3) < 1e-12
    persist = syllable_persistence(
        tests, facet_col="phase_layer", group_cols=("model", "step")
    )
    s1 = persist.loc[persist["raw_syllable_id"] == 1].iloc[0]
    assert int(s1["n_hit_fdr05"]) == 3
    assert int(s1["n_facets"]) == 3


def test_da_tx_sex_stratum_does_not_pool() -> None:
    rows = []
    for i in range(8):
        for cond, frames in (
            ("no_obj", {1: 90, 2: 10}),
            ("identical_obj", {1: 10, 2: 90}),
        ):
            for sid, fr in frames.items():
                rows.append(
                    {
                        "animal_id": f"f{i}",
                        "sex": "F",
                        "tx": "noSD",
                        "phase_layer": "NOR_TX",
                        "condition_layer": cond,
                        "raw_syllable_id": sid,
                        "bout_frames": fr,
                        "bout_mean_dist_any_m": 0.20,
                    }
                )
    for i in range(8):
        for cond, frames in (
            ("no_obj", {1: 50, 2: 50}),
            ("identical_obj", {1: 50, 2: 50}),
        ):
            for sid, fr in frames.items():
                rows.append(
                    {
                        "animal_id": f"m{i}",
                        "sex": "M",
                        "tx": "GHSD",
                        "phase_layer": "NOR_TX",
                        "condition_layer": cond,
                        "raw_syllable_id": sid,
                        "bout_frames": fr,
                        "bout_mean_dist_any_m": 0.20,
                    }
                )
    ac = build_animal_condition_table(pd.DataFrame(rows), phase_layer="NOR_TX")
    dtab = paired_da_deltas(
        ac,
        step="no_obj->identical",
        left="no_obj",
        right="identical_obj",
        pair_col="condition_layer",
    )
    dtab["model"] = "toy"
    tests = da_tests_tx_sex_from_animal_deltas(dtab)
    f = tests[(tests["tx"] == "noSD") & (tests["sex"] == "F")]
    m = tests[(tests["tx"] == "GHSD") & (tests["sex"] == "M")]
    assert bool(f["hit_fdr05"].all())
    assert not bool(m["hit_p05"].any())
    pooled = da_tests_from_deltas(dtab)
    assert str(pooled["sex"].iloc[0]) == "all"


def test_run_phase_da_accepts_bout_count(tmp_path: Path) -> None:
    rows = []
    for aid in ("1", "2"):
        for cond, fr_a, fr_b in (("no_obj", 10, 1), ("identical_obj", 1, 10), ("novel_obj", 2, 8)):
            for syll, fr in ((1, fr_a), (2, fr_b)):
                rows.append(
                    {
                        "animal_id": aid,
                        "sex": "F",
                        "tx": "noSD",
                        "phase_layer": "NOR_TX",
                        "condition_layer": cond,
                        "raw_syllable_id": syll,
                        "bout_frames": fr,
                        "bout_mean_dist_any_m": 0.5,
                    }
                )
    path = tmp_path / "ladder_bout_features.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    tests, _deltas = run_phase_da(path, "NOR_TX", weighting="bout_count")
    assert not tests.empty
    assert (tests["weighting"] == "bout_count").all()
