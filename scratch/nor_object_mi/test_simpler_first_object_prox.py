"""Litmus for per-object 0.10 m proximity windows and discrimination ratio (DR)."""

from __future__ import annotations

import math

import pandas as pd

from nor_object_mi._object_prox_labels import OCC_STEM
from nor_object_mi.simpler_first_object_prox import (
    NEAR_R_M,
    _spacing_audit,
    animal_median_across_models,
    animal_object_prox_metrics,
    across_model_dispersion,
    across_model_dispersion_summary,
    consensus_tests,
    discrimination_ratio,
    tag_object_prox,
)


def test_occupancy_figure_stems_are_split() -> None:
    assert OCC_STEM["frac_near_fam"] == "fig_object_prox_occupancy_fam"
    assert OCC_STEM["frac_near_nvl"] == "fig_object_prox_occupancy_nvl"
    assert len(set(OCC_STEM.values())) == 2


def _bout(
    *,
    frames: int,
    d_fam: float,
    d_nvl: float,
    animal: str = "a",
    cond: str = "novel_obj",
) -> dict:
    return {
        "animal_id": animal,
        "sex": "F",
        "tx": "noSD",
        "phase_layer": "NOR_TX",
        "condition_layer": cond,
        "bout_frames": frames,
        "bout_mean_dist_fam_m": d_fam,
        "bout_mean_dist_nvl_m": d_nvl,
    }


def test_discrimination_ratio_known_toy() -> None:
    # 30 fam-only + 70 nvl-only → DR = (70 − 30) / 100 = 0.4
    dr = discrimination_ratio(n_nvl=70, n_fam=30)
    assert abs(dr - 0.4) < 1e-12


def test_discrimination_ratio_empty_is_nan() -> None:
    assert math.isnan(discrimination_ratio(n_nvl=0, n_fam=0))


def test_tag_marks_fam_nvl_and_both() -> None:
    df = pd.DataFrame(
        [
            _bout(frames=10, d_fam=0.05, d_nvl=0.40),
            _bout(frames=10, d_fam=0.40, d_nvl=0.05),
            _bout(frames=10, d_fam=0.05, d_nvl=0.05),
            _bout(frames=10, d_fam=0.40, d_nvl=0.40),
        ]
    )
    tagged = tag_object_prox(df, r_m=NEAR_R_M)
    assert tagged["near_fam"].tolist() == [True, False, True, False]
    assert tagged["near_nvl"].tolist() == [False, True, True, False]
    assert tagged["near_both"].tolist() == [False, False, True, False]


def test_animal_metrics_disjoint_prox() -> None:
    df = pd.DataFrame(
        [
            _bout(frames=30, d_fam=0.05, d_nvl=0.40),
            _bout(frames=70, d_fam=0.40, d_nvl=0.05),
        ]
    )
    out = animal_object_prox_metrics(df, phase_layer="NOR_TX")
    assert len(out) == 1
    row = out.iloc[0]
    assert int(row["n_fam_frames"]) == 30
    assert int(row["n_nvl_frames"]) == 70
    assert int(row["n_both_frames"]) == 0
    assert abs(float(row["frac_near_fam"]) - 0.30) < 1e-12
    assert abs(float(row["frac_near_nvl"]) - 0.70) < 1e-12
    assert abs(float(row["frac_both"]) - 0.0) < 1e-12
    assert abs(float(row["dr_inclusive"]) - 0.4) < 1e-12
    assert abs(float(row["dr_exclusive"]) - 0.4) < 1e-12


def test_animal_metrics_overlap_splits_inclusive_vs_exclusive() -> None:
    # 20 fam-only, 30 nvl-only, 10 both, 40 far → 100 frames
    df = pd.DataFrame(
        [
            _bout(frames=20, d_fam=0.05, d_nvl=0.40),
            _bout(frames=30, d_fam=0.40, d_nvl=0.05),
            _bout(frames=10, d_fam=0.05, d_nvl=0.05),
            _bout(frames=40, d_fam=0.40, d_nvl=0.40),
        ]
    )
    row = animal_object_prox_metrics(df, phase_layer="NOR_TX").iloc[0]
    assert int(row["n_fam_frames"]) == 30
    assert int(row["n_nvl_frames"]) == 40
    assert int(row["n_both_frames"]) == 10
    assert abs(float(row["frac_both"]) - 0.10) < 1e-12
    # inclusive: overlap in both windows → DR = (40 − 30) / 70
    assert abs(float(row["dr_inclusive"]) - (10 / 70)) < 1e-12
    # exclusive: overlap in neither window → DR = (30 − 20) / 50
    assert abs(float(row["dr_exclusive"]) - 0.2) < 1e-12


def test_ignores_identical_obj() -> None:
    df = pd.DataFrame(
        [
            _bout(frames=50, d_fam=0.05, d_nvl=0.40),
            _bout(frames=999, d_fam=0.01, d_nvl=0.01, cond="identical_obj"),
        ]
    )
    out = animal_object_prox_metrics(df, phase_layer="NOR_TX")
    assert len(out) == 1
    assert int(out.iloc[0]["n_sess_frames"]) == 50


def test_spacing_flags_sum_below_2r() -> None:
    df = pd.DataFrame(
        [
            _bout(frames=1, d_fam=0.05, d_nvl=0.05),  # sum 0.10 < 0.20
            _bout(frames=1, d_fam=0.20, d_nvl=0.20),  # sum 0.40 ≥ 0.20
        ]
    )
    audit = _spacing_audit(df, phase_layer="NOR_TX", condition_layer="novel_obj")
    assert audit["n_bouts_sum_lt_2r"] == 1
    assert abs(float(audit["min_d_fam_plus_d_nvl"]) - 0.10) < 1e-12


def test_animal_median_across_models_identity() -> None:
    rows = []
    for model in ("m0", "m1", "m2"):
        for i, dr in enumerate((0.10, 0.20, 0.15, -0.05)):
            rows.append(
                {
                    "model": model,
                    "animal_id": f"a{i}",
                    "sex": "F",
                    "tx": "noSD",
                    "phase_layer": "NOR_TX",
                    "dr_exclusive": dr,
                    "dr_inclusive": dr,
                    "frac_near_fam": 0.1,
                    "frac_near_nvl": 0.2,
                    "frac_both": 0.0,
                }
            )
    med = animal_median_across_models(pd.DataFrame(rows))
    assert len(med) == 4
    assert med["n_models"].eq(3).all()
    got = med.sort_values("animal_id")["dr_exclusive"].to_numpy()
    assert list(got) == [0.10, 0.20, 0.15, -0.05]


def test_consensus_wilcoxon_hits_positive_dr() -> None:
    rows = []
    for i in range(20):
        rows.append(
            {
                "animal_id": f"a{i}",
                "sex": "F" if i < 10 else "M",
                "tx": "noSD",
                "phase_layer": "NOR_TX",
                "dr_exclusive": 0.40,
                "dr_inclusive": 0.40,
                "frac_near_fam": 0.1,
                "frac_near_nvl": 0.2,
                "frac_both": 0.0,
                "n_models": 21,
            }
        )
    tests = consensus_tests(pd.DataFrame(rows))
    wx = tests[(tests["test"] == "wilcoxon_signed_rank") & (tests["sex"] == "all") & (tests["metric"] == "dr_exclusive")]
    assert len(wx) == 1
    assert float(wx["p"].iloc[0]) < 0.05
    assert bool(wx["hit_p05"].iloc[0])


def test_across_model_dispersion_iqr_on_known_dr() -> None:
    rows = []
    for i, dr in enumerate((0.10, 0.20, 0.30)):
        rows.append(
            {
                "model": f"m{i}",
                "animal_id": "a0",
                "sex": "F",
                "tx": "noSD",
                "phase_layer": "NOR_TX",
                "dr_exclusive": dr,
                "dr_inclusive": dr,
                "frac_near_fam": 0.1,
                "frac_near_nvl": 0.2,
                "frac_both": 0.0,
            }
        )
    disp = across_model_dispersion(pd.DataFrame(rows))
    ex = disp[disp["metric"] == "dr_exclusive"]
    assert len(ex) == 1
    assert abs(float(ex["median"].iloc[0]) - 0.20) < 1e-12
    assert abs(float(ex["iqr"].iloc[0]) - 0.10) < 1e-12
    assert bool(ex["magnitude_commensurate_across_models"].iloc[0])
    summ = across_model_dispersion_summary(disp)
    row = summ[summ["metric"] == "dr_exclusive"]
    assert len(row) == 1
    assert abs(float(row["median_of_iqr"].iloc[0]) - 0.10) < 1e-12
