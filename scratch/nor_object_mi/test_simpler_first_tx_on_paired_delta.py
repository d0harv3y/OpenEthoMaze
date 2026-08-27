"""Litmus checks for tx-on-paired-Δ lattice (Q1–Q4 helpers)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from nor_object_mi.simpler_first_presence import build_animal_condition_table
from nor_object_mi.simpler_first_tx_on_paired_delta import (
    agreement_da,
    agreement_shannon,
    da_cell_consensus_hit,
    da_consensus_min_hits,
    da_tx_kruskal_from_deltas,
    model_alphabet_k,
    run_condition_axis,
)


def test_alphabet_k_and_consensus_threshold() -> None:
    assert model_alphabet_k("paramscan_s1-1e8_s2-1e5_ss-50") == 50
    assert model_alphabet_k("paramscan_s1-1e8_s2-1e5_ss-100") == 100
    assert da_consensus_min_hits(50) == 2
    assert da_consensus_min_hits(75) == 3
    assert da_consensus_min_hits(100) == 4
    assert da_cell_consensus_hit(2, 50) is True
    assert da_cell_consensus_hit(1, 50) is False
    assert da_cell_consensus_hit(4, 100) is True
    assert da_cell_consensus_hit(3, 100) is False


def _bouts_tx_sex_shift() -> pd.DataFrame:
    """F: noSD moves syllable 1→2 on presence; GHSD/RBSD flat. M flat."""
    rows: list[dict[str, object]] = []
    for i in range(9):
        sex = "F"
        tx = ("noSD", "GHSD", "RBSD")[i % 3]
        aid = f"f{i}"
        if tx == "noSD":
            left, right = {1: 90, 2: 10}, {1: 10, 2: 90}
        else:
            left = right = {1: 50, 2: 50}
        for cond, frames in (("no_obj", left), ("identical_obj", right), ("novel_obj", right)):
            for sid, fr in frames.items():
                rows.append(
                    {
                        "animal_id": aid,
                        "sex": sex,
                        "tx": tx,
                        "phase_layer": "NOR_TX",
                        "condition_layer": cond,
                        "raw_syllable_id": sid,
                        "bout_frames": fr,
                        "bout_mean_dist_any_m": 0.20,
                    }
                )
    for i in range(9):
        tx = ("noSD", "GHSD", "RBSD")[i % 3]
        aid = f"m{i}"
        frames = {1: 50, 2: 50}
        for cond in ("no_obj", "identical_obj", "novel_obj"):
            for sid, fr in frames.items():
                rows.append(
                    {
                        "animal_id": aid,
                        "sex": "M",
                        "tx": tx,
                        "phase_layer": "NOR_TX",
                        "condition_layer": cond,
                        "raw_syllable_id": sid,
                        "bout_frames": fr,
                        "bout_mean_dist_any_m": 0.20,
                    }
                )
    return pd.DataFrame(rows)


def test_da_tx_kruskal_detects_sex_specific_tx_effect() -> None:
    from nor_object_mi.simpler_first_da import paired_da_deltas

    ac = build_animal_condition_table(_bouts_tx_sex_shift(), phase_layer="NOR_TX")
    dtab = paired_da_deltas(
        ac,
        step="no_obj->identical",
        left="no_obj",
        right="identical_obj",
        pair_col="condition_layer",
    )
    tests = da_tx_kruskal_from_deltas(dtab, question="Q1")
    # apply BH within sex
    from nor_object_mi.simpler_first_da import apply_bh_grouped

    tests = apply_bh_grouped(tests, ("sex",))
    f1 = tests[(tests["sex"] == "F") & (tests["raw_syllable_id"] == 1)]
    m1 = tests[(tests["sex"] == "M") & (tests["raw_syllable_id"] == 1)]
    assert len(f1) == 1 and len(m1) == 1
    assert float(f1["p"].iloc[0]) < 0.05
    assert bool(f1["hit_p05"].iloc[0])
    # males are flat → should not reject
    assert not (np.isfinite(m1["p"].iloc[0]) and float(m1["p"].iloc[0]) < 0.05)


def test_da_tx_anova_detects_sex_specific_tx_effect() -> None:
    """Mean-scale twin of the Kruskal litmus (same synthetic shift + tiny noise).

    Alexander–Govern needs positive within-arm variance; add ε so AG is defined.
    """
    from nor_object_mi.simpler_first_da import apply_bh_grouped, paired_da_deltas
    from nor_object_mi.simpler_first_tx_on_paired_delta import da_tx_stage_b_from_deltas

    ac = build_animal_condition_table(_bouts_tx_sex_shift(), phase_layer="NOR_TX")
    dtab = paired_da_deltas(
        ac,
        step="no_obj->identical",
        left="no_obj",
        right="identical_obj",
        pair_col="condition_layer",
    )
    rng = np.random.default_rng(0)
    dtab = dtab.copy()
    dtab["delta_p"] = pd.to_numeric(dtab["delta_p"], errors="coerce") + rng.normal(
        0.0, 1e-4, size=len(dtab)
    )
    tests = da_tx_stage_b_from_deltas(dtab, question="Q1", stage_b="anova")
    tests = apply_bh_grouped(tests, ("sex",))
    f1 = tests[(tests["sex"] == "F") & (tests["raw_syllable_id"] == 1)]
    m1 = tests[(tests["sex"] == "M") & (tests["raw_syllable_id"] == 1)]
    assert len(f1) == 1 and len(m1) == 1
    assert str(f1["test"].iloc[0]) == "welch_anova"
    assert float(f1["p"].iloc[0]) < 0.05
    assert bool(f1["hit_p05"].iloc[0])
    assert "mean_noSD" in f1.columns
    assert not (np.isfinite(m1["p"].iloc[0]) and float(m1["p"].iloc[0]) < 0.05)


def test_near_grain_empty_when_all_far() -> None:
    bouts = _bouts_tx_sex_shift()
    ac_near = build_animal_condition_table(
        bouts, phase_layer="NOR_TX", grain="near_0p10"
    )
    assert (ac_near["n_near_frames"] == 0).all()
    assert ac_near["shannon_bits"].isna().all()
    assert all((not c) for c in ac_near["counts"])


def test_near_grain_uses_near_bouts_only() -> None:
    rows = []
    for cond, d_any, frames_by_syll in (
        ("no_obj", 0.05, {1: 100}),
        ("identical_obj", 0.05, {2: 100}),
        ("novel_obj", 0.20, {1: 100}),  # far — excluded from near composition
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
                    "bout_mean_dist_any_m": d_any,
                }
            )
    ac = build_animal_condition_table(
        pd.DataFrame(rows), phase_layer="NOR_TX", grain="near_0p10"
    )
    no_obj = ac[ac["condition_layer"] == "no_obj"].iloc[0]
    novel = ac[ac["condition_layer"] == "novel_obj"].iloc[0]
    counts = {int(k): float(v) for k, v in dict(no_obj["counts"]).items()}
    assert counts == {1: 100.0}
    assert not novel["counts"]
    assert np.isnan(novel["shannon_bits"])


def test_shannon_bh_family_size_three_within_phase() -> None:
    """Q2: BH groups three steps; with one tiny p, q is inflated by m=3."""
    from nor_object_mi.simpler_first_da import apply_bh_grouped

    rows = []
    for step, p in (
        ("no_obj->identical", 0.01),
        ("identical->novel", 0.80),
        ("no_obj->novel", 0.90),
    ):
        rows.append(
            {
                "phase_layer": "NOR_TX",
                "step": step,
                "sex": "F",
                "p": p,
            }
        )
    out = apply_bh_grouped(pd.DataFrame(rows), ("sex", "phase_layer"))
    q_hit = float(out.loc[out["step"] == "no_obj->identical", "q_bh"].iloc[0])
    assert abs(q_hit - 0.03) < 1e-12  # 0.01 * 3 / 1
    assert bool(out.loc[out["step"] == "no_obj->identical", "hit_fdr05"].iloc[0])


def test_agreement_da_uses_alphabet_frac() -> None:
    rows = []
    # 21 models would be heavy; three models, K=50 → need ≥2 hits
    for model, n_hit in (
        ("paramscan_x_ss-50", 2),
        ("paramscan_y_ss-50", 0),
        ("paramscan_z_ss-50", 5),
    ):
        for sid in range(n_hit):
            rows.append(
                {
                    "model": model,
                    "grain": "full_session",
                    "sex": "F",
                    "phase_layer": "NOR_TX",
                    "step": "no_obj->identical",
                    "raw_syllable_id": sid,
                    "hit_fdr05": True,
                }
            )
        # pad a non-hit row so model appears
        if n_hit == 0:
            rows.append(
                {
                    "model": model,
                    "grain": "full_session",
                    "sex": "F",
                    "phase_layer": "NOR_TX",
                    "step": "no_obj->identical",
                    "raw_syllable_id": 99,
                    "hit_fdr05": False,
                }
            )
    agree = agreement_da(pd.DataFrame(rows), hold_col="phase_layer", step_col="step")
    assert len(agree) == 1
    assert int(agree["n_model_consensus_hit"].iloc[0]) == 2
    assert abs(float(agree["frac_model_consensus_hit"].iloc[0]) - 2 / 3) < 1e-12


def test_run_condition_axis_smoke() -> None:
    ac = build_animal_condition_table(_bouts_tx_sex_shift(), phase_layer="NOR_TX")
    da, sc, da_d, sc_d = run_condition_axis(ac, grain="full_session")
    assert not da.empty
    assert set(da["sex"]) <= {"F", "M"}
    assert "hit_fdr05" in da.columns
    assert not sc.empty
    assert "hit_fdr05" in sc.columns
    assert "delta_shannon_bits" in set(sc["metric"])
    assert "delta_richness" in set(sc["metric"])
    assert "braycurtis" in set(sc["metric"])
    assert not da_d.empty
    assert {"animal_id", "delta_p", "raw_syllable_id", "tx", "sex"} <= set(da_d.columns)
    assert not sc_d.empty
    assert "delta_shannon_bits" in sc_d.columns


def test_bout_count_weighting_differs_from_frame_share() -> None:
    rows = []
    # one long bout of syll 1, many short bouts of syll 2
    rows.append(
        {
            "animal_id": "a1",
            "sex": "F",
            "tx": "noSD",
            "phase_layer": "NOR_TX",
            "condition_layer": "no_obj",
            "raw_syllable_id": 1,
            "bout_frames": 90,
            "bout_mean_dist_any_m": 0.2,
        }
    )
    for _ in range(9):
        rows.append(
            {
                "animal_id": "a1",
                "sex": "F",
                "tx": "noSD",
                "phase_layer": "NOR_TX",
                "condition_layer": "no_obj",
                "raw_syllable_id": 2,
                "bout_frames": 1,
                "bout_mean_dist_any_m": 0.2,
            }
        )
    bouts = pd.DataFrame(rows)
    # pad other conditions
    for cond in ("identical_obj", "novel_obj"):
        for sid, fr in ((1, 50), (2, 50)):
            bouts = pd.concat(
                [
                    bouts,
                    pd.DataFrame(
                        [
                            {
                                "animal_id": "a1",
                                "sex": "F",
                                "tx": "noSD",
                                "phase_layer": "NOR_TX",
                                "condition_layer": cond,
                                "raw_syllable_id": sid,
                                "bout_frames": fr,
                                "bout_mean_dist_any_m": 0.2,
                            }
                        ]
                    ),
                ],
                ignore_index=True,
            )
    frame = build_animal_condition_table(bouts, phase_layer="NOR_TX", weighting="frame_share")
    bout = build_animal_condition_table(bouts, phase_layer="NOR_TX", weighting="bout_count")
    cf = frame[frame["condition_layer"] == "no_obj"].iloc[0]["counts"]
    cb = bout[bout["condition_layer"] == "no_obj"].iloc[0]["counts"]
    assert float(cf[1]) == 90.0 and float(cf[2]) == 9.0
    assert float(cb[1]) == 1.0 and float(cb[2]) == 9.0
