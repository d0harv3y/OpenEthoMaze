"""Litmus for QuadComp geometry + DR cousins — before cohort Kruskal."""

from __future__ import annotations

import numpy as np

from nor_object_mi.quad_comp import (
    FAMILY_A_SIZE,
    MIN_FRAMES_N,
    NOISE_CLUSTER,
    assert_family_a_size,
    cell_key,
    composition_scalars,
    dr_cousin,
    score_quad_composition,
)


def test_family_a_size_is_four() -> None:
    assert FAMILY_A_SIZE == 4
    assert_family_a_size(4)


def test_cell_key_on_axis_uses_ge() -> None:
    assert cell_key(0.0, 0.0, cx=0.0, cy=0.0) == (1, 1)
    assert cell_key(-1.0, -1.0, cx=0.0, cy=0.0) == (0, 0)
    assert cell_key(1.0, -1.0, cx=0.0, cy=0.0) == (1, 0)


def test_dr_cousin_sign() -> None:
    assert abs(dr_cousin(3.0, 1.0) - 0.5) < 1e-12
    assert abs(dr_cousin(1.0, 3.0) - (-0.5)) < 1e-12
    assert np.isnan(dr_cousin(0.0, 0.0))


def test_composition_scalars_uniform_two() -> None:
    labs = np.array([0, 0, 1, 1], dtype=np.int64)
    out = composition_scalars(labs)
    assert out["n_frames"] == 4.0
    assert out["richness"] == 2.0
    assert abs(out["shannon_bits"] - 1.0) < 1e-12
    # Hill q=2: uniform 2-cat → 1 / (2*(0.5^2)) = 2
    assert abs(out["hill2_eff"] - 2.0) < 1e-12


def test_composition_scalars_hill2_singleton() -> None:
    labs = np.array([3, 3, 3, 3], dtype=np.int64)
    out = composition_scalars(labs)
    assert abs(out["hill2_eff"] - 1.0) < 1e-12
    assert abs(out["shannon_bits"] - 0.0) < 1e-12


def test_diagonal_objects_assign_fam_nvl_other() -> None:
    """Analytical: fam SW, nvl NE; frames in each cell carry one cluster."""
    cx, cy = 100.0, 100.0
    # fam center SW (x<cx, y<cy); nvl NE (x>=cx, y>=cy) — diagonal
    fam_c = np.array([50.0, 50.0])
    nvl_c = np.array([150.0, 150.0])
    # 12 frames: 4 fam, 4 nvl, 4 other (SE); all mapped
    x = np.array(
        [40, 40, 40, 40, 160, 160, 160, 160, 160, 160, 160, 160],
        dtype=np.float64,
    )
    y = np.array(
        [40, 40, 40, 40, 160, 160, 160, 160, 40, 40, 40, 40],
        dtype=np.float64,
    )
    # SE other: x>=cx, y<cy → last 4
    valid = np.ones(12, dtype=bool)
    # fam: cluster 0 only; nvl: clusters 0 and 1 (richer + higher H)
    syll = np.array([0, 0, 0, 0, 0, 0, 1, 1, 2, 2, 2, 2], dtype=np.int64)
    out = score_quad_composition(
        x,
        y,
        valid,
        syll,
        cx=cx,
        cy=cy,
        fam_center_px=fam_c,
        nvl_center_px=nvl_c,
        rotate_180=False,
        min_frames=4,
    )
    assert out["object_cell_collision"] is False
    assert out["n_frames_fam_quad"] == 4.0
    assert out["n_frames_nvl_quad"] == 4.0
    assert out["n_frames_other"] == 4.0
    assert out["n_spot_fam_quad"] == 4.0
    assert out["n_spot_nvl_quad"] == 4.0
    assert out["contrast_eligible"] is True
    assert out["time_contrast_eligible"] is True
    assert out["richness_fam_quad"] == 1.0
    assert out["richness_nvl_quad"] == 2.0
    assert out["fam_richness_quad"] == 1.0
    assert out["nvl_richness_quad"] == 2.0
    assert out["fam_shannon_quad"] == out["shannon_bits_fam_quad"]
    assert out["nvl_shannon_quad"] == out["shannon_bits_nvl_quad"]
    assert out["dr_richness_quad"] > 0.0
    assert out["dr_shannon_quad"] > 0.0
    assert abs(out["dr_time_quad"] - 0.0) < 1e-12  # equal spot counts


def test_min_frames_gates_contrast() -> None:
    cx, cy = 0.0, 0.0
    fam_c = np.array([-1.0, -1.0])
    nvl_c = np.array([1.0, 1.0])
    x = np.array([-1.0, 1.0, 1.0], dtype=np.float64)
    y = np.array([-1.0, 1.0, 1.0], dtype=np.float64)
    valid = np.ones(3, dtype=bool)
    syll = np.array([0, 0, 1], dtype=np.int64)
    out = score_quad_composition(
        x,
        y,
        valid,
        syll,
        cx=cx,
        cy=cy,
        fam_center_px=fam_c,
        nvl_center_px=nvl_c,
        rotate_180=False,
        min_frames=MIN_FRAMES_N,
    )
    assert out["n_frames_fam_quad"] == 1.0
    assert out["n_frames_nvl_quad"] == 2.0
    assert out["contrast_eligible"] is False
    assert np.isnan(out["dr_shannon_quad"])


def test_collision_yields_nan_contrast() -> None:
    cx, cy = 0.0, 0.0
    # both centers in NE cell
    fam_c = np.array([1.0, 1.0])
    nvl_c = np.array([2.0, 2.0])
    x = np.array([1.0, 2.0], dtype=np.float64)
    y = np.array([1.0, 2.0], dtype=np.float64)
    valid = np.ones(2, dtype=bool)
    syll = np.array([0, 1], dtype=np.int64)
    out = score_quad_composition(
        x,
        y,
        valid,
        syll,
        cx=cx,
        cy=cy,
        fam_center_px=fam_c,
        nvl_center_px=nvl_c,
        rotate_180=False,
        min_frames=1,
    )
    assert out["object_cell_collision"] is True
    assert np.isnan(out["dr_shannon_quad"])


def test_noise_cluster_excluded_from_composition() -> None:
    cx, cy = 0.0, 0.0
    fam_c = np.array([-1.0, -1.0])
    nvl_c = np.array([1.0, 1.0])
    x = np.full(20, -1.0)
    y = np.full(20, -1.0)
    # put 10 mapped + 10 noise in fam; 10 mapped in nvl
    x = np.concatenate([np.full(20, -1.0), np.full(10, 1.0)])
    y = np.concatenate([np.full(20, -1.0), np.full(10, 1.0)])
    valid = np.ones(30, dtype=bool)
    syll = np.concatenate(
        [
            np.full(10, 0, dtype=np.int64),
            np.full(10, NOISE_CLUSTER, dtype=np.int64),
            np.full(10, 1, dtype=np.int64),
        ]
    )
    out = score_quad_composition(
        x,
        y,
        valid,
        syll,
        cx=cx,
        cy=cy,
        fam_center_px=fam_c,
        nvl_center_px=nvl_c,
        rotate_180=False,
        min_frames=10,
    )
    assert out["n_frames_fam_quad"] == 10.0
    assert out["n_frames_nvl_quad"] == 10.0
    assert out["contrast_eligible"] is True
