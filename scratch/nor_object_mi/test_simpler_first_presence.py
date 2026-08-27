"""Paired presence-step litmus."""

from __future__ import annotations

import numpy as np
import pandas as pd

from nor_object_mi.simpler_first_presence import (
    TX_STRATUM_ALL,
    TX_STRATUM_CONTROL,
    _paired_delta_table,
    across_model_dispersion,
    across_model_dispersion_by_ss,
    across_model_dispersion_summary,
    animal_median_across_models,
    agreement_table,
    build_animal_condition_table,
    consensus_tests,
    model_num_states,
    wilcoxon_paired,
)


def test_model_num_states_parse() -> None:
    assert model_num_states("paramscan_s1-1e8_s2-1e5_ss-50") == 50
    assert model_num_states("paramscan_s1-1e8_s2-1e5_ss-100") == 100


def test_across_model_dispersion_iqr_and_commensurate_flag() -> None:
    rows = []
    # Δ frac_near = 0.10, 0.20, 0.30 → median 0.20, IQR 0.10
    for i, d in enumerate((0.10, 0.20, 0.30)):
        rows.append(
            {
                "model": f"paramscan_s1-1e8_s2-1e5_ss-50_r{i}",
                "animal_id": "a0",
                "sex": "F",
                "tx": "noSD",
                "step": "no_obj->identical",
                "phase_layer": "NOR_TX",
                "delta_frac_near": d,
                "delta_mean_dist_any_m": 0.0,
                "delta_richness": float(i),
                "delta_shannon_bits": 0.0,
            }
        )
    disp = across_model_dispersion(pd.DataFrame(rows))
    fr = disp[disp["metric"] == "delta_frac_near"].iloc[0]
    assert abs(float(fr["median"]) - 0.20) < 1e-12
    assert abs(float(fr["iqr"]) - 0.10) < 1e-12
    assert bool(fr["magnitude_commensurate_across_models"]) is True
    sh = disp[disp["metric"] == "delta_shannon_bits"].iloc[0]
    assert bool(sh["magnitude_commensurate_across_models"]) is False
    summary = across_model_dispersion_summary(disp)
    assert len(summary) == 4
    by_sex = across_model_dispersion_summary(
        disp, group_keys=("sex", "phase_layer", "step", "metric")
    )
    assert set(by_sex["sex"]) == {"F"}
    assert int(by_sex["n_animals"].iloc[0]) == 1


def test_dispersion_summary_by_sex_splits_n_animals() -> None:
    rows = []
    for sex, animal in (("F", "a0"), ("M", "a1")):
        for i, d in enumerate((0.10, 0.20, 0.30)):
            rows.append(
                {
                    "model": f"m{i}",
                    "animal_id": animal,
                    "sex": sex,
                    "tx": "noSD",
                    "step": "no_obj->identical",
                    "phase_layer": "NOR_TX",
                    "delta_frac_near": d,
                    "delta_mean_dist_any_m": 0.0,
                    "delta_richness": 0.0,
                    "delta_shannon_bits": 0.0,
                }
            )
    disp = across_model_dispersion(pd.DataFrame(rows))
    by_sex = across_model_dispersion_summary(
        disp, group_keys=("sex", "phase_layer", "step", "metric")
    )
    fr = by_sex[by_sex["metric"] == "delta_frac_near"]
    assert set(fr["sex"]) == {"F", "M"}
    assert fr["n_animals"].eq(1).all()
    pooled = across_model_dispersion_summary(disp)
    assert int(pooled[pooled["metric"] == "delta_frac_near"]["n_animals"].iloc[0]) == 2


def test_across_model_dispersion_accepts_phase_paired_keys() -> None:
    rows = []
    for i, d in enumerate((0.10, 0.20, 0.30)):
        rows.append(
            {
                "model": f"m{i}",
                "animal_id": "a0",
                "sex": "F",
                "tx": "noSD",
                "phase_step": "BL->TX",
                "condition_layer": "novel_obj",
                "delta_frac_near": d,
                "delta_mean_dist_any_m": 0.0,
                "delta_richness": 0.0,
                "delta_shannon_bits": 0.0,
            }
        )
    disp = across_model_dispersion(
        pd.DataFrame(rows),
        keys=("animal_id", "sex", "tx", "phase_step", "condition_layer"),
    )
    fr = disp[disp["metric"] == "delta_frac_near"].iloc[0]
    assert abs(float(fr["iqr"]) - 0.10) < 1e-12
    summ = across_model_dispersion_summary(
        disp, group_keys=("condition_layer", "phase_step", "metric")
    )
    assert len(summ) == 4
    assert "median_of_iqr" in summ.columns


def test_across_model_dispersion_by_ss_marks_within_ss() -> None:
    rows = []
    for ss in (50, 100):
        for i, d in enumerate((0.1, 0.2, 0.3)):
            rows.append(
                {
                    "model": f"paramscan_s1-1e8_s2-1e5_ss-{ss}_r{i}",
                    "animal_id": "a0",
                    "sex": "F",
                    "tx": "noSD",
                    "step": "no_obj->identical",
                    "phase_layer": "NOR_TX",
                    "delta_frac_near": d,
                    "delta_mean_dist_any_m": 0.0,
                    "delta_richness": 1.0,
                    "delta_shannon_bits": 0.05 * i,
                }
            )
    by_ss = across_model_dispersion_by_ss(pd.DataFrame(rows))
    assert set(by_ss["ss"]) == {50, 100}
    assert by_ss["salt_role"].eq("within_ss_primary").all()


def test_animal_median_across_models_identity() -> None:
    rows = []
    for model in ("m0", "m1", "m2"):
        for i, d in enumerate((0.10, 0.20, 0.15, -0.05)):
            rows.append(
                {
                    "model": model,
                    "animal_id": f"a{i}",
                    "sex": "F",
                    "tx": "noSD",
                    "step": "no_obj->identical",
                    "phase_layer": "NOR_TX",
                    "delta_frac_near": d,
                    "delta_mean_dist_any_m": 0.0,
                    "delta_richness": 0.0,
                    "delta_shannon_bits": 0.0,
                }
            )
    med = animal_median_across_models(pd.DataFrame(rows))
    assert len(med) == 4
    assert med["n_models"].eq(3).all()
    got = med.sort_values("animal_id")["delta_frac_near"].to_numpy()
    assert np.allclose(got, [0.10, 0.20, 0.15, -0.05])


def test_consensus_wilcoxon_on_median_hits_positive_shift() -> None:
    rows = []
    for i in range(20):
        rows.append(
            {
                "animal_id": f"a{i}",
                "sex": "F" if i < 10 else "M",
                "tx": "noSD",
                "step": "no_obj->identical",
                "phase_layer": "NOR_TX",
                "delta_frac_near": 0.12,
                "delta_mean_dist_any_m": 0.0,
                "delta_richness": 0.0,
                "delta_shannon_bits": 0.0,
                "n_models": 21,
            }
        )
    tests = consensus_tests(pd.DataFrame(rows))
    wx = tests[
        (tests["test"] == "wilcoxon_signed_rank")
        & (tests["sex"] == "all")
        & (tests["metric"] == "frac_near")
        & (tests["tx_stratum"] == TX_STRATUM_ALL)
    ]
    assert len(wx) == 1
    assert float(wx["p"].iloc[0]) < 0.05
    assert bool(wx["hit_p05"].iloc[0])


def test_consensus_kruskal_metric_is_delta_star() -> None:
    rows = []
    for i in range(18):
        tx = ("noSD", "GHSD", "RBSD")[i % 3]
        rows.append(
            {
                "animal_id": f"a{i}",
                "sex": "F" if i < 9 else "M",
                "tx": tx,
                "step": "no_obj->identical",
                "phase_layer": "NOR_TX",
                "delta_frac_near": 0.10 if tx == "noSD" else 0.0,
                "delta_mean_dist_any_m": 0.0,
                "delta_richness": 0.0,
                "delta_shannon_bits": 0.0,
                "n_models": 21,
            }
        )
    tests = consensus_tests(pd.DataFrame(rows))
    kr = tests[(tests["test"] == "kruskal") & (tests["metric"] == "delta_frac_near")]
    assert set(kr["sex"]) == {"F", "M"}
    assert kr["p"].notna().all()


def test_noSD_wilcoxon_within_sex_not_pooled() -> None:
    """Control-arm n is noSD only; pooled F includes treated animals."""
    rows = []
    for i in range(12):
        tx = "noSD" if i < 6 else "GHSD"
        rows.append(
            {
                "animal_id": f"a{i}",
                "sex": "F",
                "tx": tx,
                "step": "no_obj->identical",
                "phase_layer": "NOR_TX",
                "delta_frac_near": 0.20 if tx == "noSD" else -0.20,
                "delta_mean_dist_any_m": 0.0,
                "delta_richness": 0.0,
                "delta_shannon_bits": 0.0,
                "n_models": 21,
            }
        )
    tests = consensus_tests(pd.DataFrame(rows))
    pooled = tests[
        (tests["test"] == "wilcoxon_signed_rank")
        & (tests["sex"] == "F")
        & (tests["metric"] == "frac_near")
        & (tests["tx_stratum"] == TX_STRATUM_ALL)
    ]
    ctrl = tests[
        (tests["test"] == "wilcoxon_signed_rank")
        & (tests["sex"] == "F")
        & (tests["metric"] == "frac_near")
        & (tests["tx_stratum"] == TX_STRATUM_CONTROL)
    ]
    assert len(pooled) == 1 and len(ctrl) == 1
    assert int(pooled["n"].iloc[0]) == 12
    assert int(ctrl["n"].iloc[0]) == 6
    assert float(ctrl["p"].iloc[0]) != float(pooled["p"].iloc[0])


def test_agreement_table_stays_sex_all_pooled() -> None:
    rows = [
        {
            "phase_layer": "NOR_TX",
            "step": "no_obj->identical",
            "sex": "all",
            "metric": "frac_near",
            "test": "wilcoxon_signed_rank",
            "hit_p05": True,
            "median_delta": 0.1,
            "tx_stratum": TX_STRATUM_ALL,
        },
        {
            "phase_layer": "NOR_TX",
            "step": "no_obj->identical",
            "sex": "F",
            "metric": "frac_near",
            "test": "wilcoxon_signed_rank",
            "hit_p05": True,
            "median_delta": 0.2,
            "tx_stratum": TX_STRATUM_CONTROL,
        },
    ]
    agr = agreement_table(pd.DataFrame(rows))
    assert len(agr) == 1
    assert int(agr["n_models"].iloc[0]) == 1


def test_wilcoxon_prefers_positive_shift() -> None:
    d = wilcoxon_paired([0.1, 0.2, 0.15, 0.12, 0.18, 0.11])
    assert d["median_delta"] > 0
    assert d["p"] < 0.05


def test_paired_delta_and_bc() -> None:
    rows = []
    for cond, frames_by_syll, dist in (
        ("no_obj", {1: 80, 2: 20}, 0.20),
        ("identical_obj", {1: 20, 2: 80}, 0.05),
        ("novel_obj", {1: 20, 2: 80}, 0.05),
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
                    "bout_mean_dist_any_m": dist,
                }
            )
    ac = build_animal_condition_table(pd.DataFrame(rows), phase_layer="NOR_TX", r_m=0.10)
    assert set(ac["condition_layer"]) == {"no_obj", "identical_obj", "novel_obj"}
    dtab = _paired_delta_table(
        ac,
        step="no_obj->identical",
        left="no_obj",
        right="identical_obj",
        metrics=("frac_near", "shannon_bits", "richness", "mean_dist_any_m"),
    )
    assert len(dtab) == 1
    assert float(dtab.loc[0, "delta_frac_near"]) > 0  # 0% near → 100% near
    assert float(dtab.loc[0, "braycurtis"]) > 0.5
