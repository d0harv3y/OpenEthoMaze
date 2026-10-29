"""Litmus for ProxComp exclusive circular gates."""

from __future__ import annotations

import numpy as np

from nor_object_mi.prox_comp import (
    FAMILY_A_SIZE,
    MIN_FRAMES_N,
    NEAR_R_M,
    PER_SCALAR_FAMILY_METRICS,
    PER_SCALAR_FAMILY_SIZE,
    TIME_FAMILY_A_SIZE,
    assert_family_a_size,
    assert_per_scalar_family_sizes,
    assert_time_family_a_size,
    score_prox_composition,
)


def test_family_sizes() -> None:
    assert FAMILY_A_SIZE == 4
    assert TIME_FAMILY_A_SIZE == 2
    assert PER_SCALAR_FAMILY_SIZE == 2
    assert PER_SCALAR_FAMILY_METRICS == (
        "dr_shannon_prox",
        "dr_richness_prox",
        "dr_hill2_prox",
    )
    assert_family_a_size(4)
    assert_time_family_a_size(2)
    assert_per_scalar_family_sizes({m: 2 for m in PER_SCALAR_FAMILY_METRICS})


def test_exclusive_drops_both() -> None:
    # fam near only, nvl near only, both (dropped), far
    d_fam = np.array([0.05, 0.20, 0.05, 0.50], dtype=np.float64)
    d_nvl = np.array([0.20, 0.05, 0.05, 0.50], dtype=np.float64)
    valid = np.ones(4, dtype=bool)
    syll = np.array([0, 1, 2, 3], dtype=np.int64)
    out = score_prox_composition(
        d_fam, d_nvl, valid, syll, r_m=NEAR_R_M, min_frames=1
    )
    assert out["n_spot_fam_prox"] == 1.0
    assert out["n_spot_nvl_prox"] == 1.0
    assert out["n_spot_both_prox"] == 1.0
    assert out["n_frames_fam_prox"] == 1.0
    assert out["n_frames_nvl_prox"] == 1.0


def test_time_dr_positive_when_more_nvl() -> None:
    d_fam = np.full(20, 0.05)
    d_nvl = np.full(20, 0.50)
    # first 5 fam-only, next 15: swap so nvl-only
    d_fam = np.concatenate([np.full(5, 0.05), np.full(15, 0.50)])
    d_nvl = np.concatenate([np.full(5, 0.50), np.full(15, 0.05)])
    valid = np.ones(20, dtype=bool)
    syll = np.zeros(20, dtype=np.int64)
    out = score_prox_composition(
        d_fam, d_nvl, valid, syll, r_m=NEAR_R_M, min_frames=MIN_FRAMES_N
    )
    assert out["time_contrast_eligible"] is False  # fam only 5 < 10
    out2 = score_prox_composition(
        d_fam, d_nvl, valid, syll, r_m=NEAR_R_M, min_frames=5
    )
    assert out2["dr_time_prox"] > 0.0
