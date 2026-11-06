"""Litmus for Q5 SideMass geometry (Family A) — before cohort Kruskal."""

from __future__ import annotations

import numpy as np

from nor_object_mi.side_mass import (
    FAMILY_A_SIZE,
    assert_family_a_size,
    family_a_cell_keys,
    rotate180_xy,
    side_mass_from_xy,
)


def test_family_a_size_is_sixteen() -> None:
    assert FAMILY_A_SIZE == 16
    assert len(family_a_cell_keys()) == 16
    assert_family_a_size(16)


def test_rotate180_swaps_sides_about_center() -> None:
    cx, cy = 100.0, 50.0
    x = np.array([120.0, 80.0])
    y = np.array([60.0, 40.0])
    xr, yr = rotate180_xy(x, y, cx=cx, cy=cy)
    assert np.allclose(xr, [80.0, 120.0])
    assert np.allclose(yr, [40.0, 60.0])


def test_all_right_of_midline_is_full_nvl_share() -> None:
    """Analytical: every valid frame with x > cx → frac_nvl_side = 1."""
    cx, cy, ppm = 100.0, 50.0, 1000.0
    x = np.array([110.0, 150.0, 200.0])
    y = np.array([50.0, 50.0, 50.0])
    valid = np.array([True, True, True])
    out = side_mass_from_xy(x, y, valid, cx=cx, cy=cy, ppm=ppm, rotate_180=False)
    assert out["frac_nvl_side"] == 1.0
    assert out["frac_fam_side"] == 0.0
    assert out["mean_signed_x_m"] > 0.0


def test_all_left_of_midline_is_zero_nvl_share() -> None:
    cx, cy, ppm = 100.0, 50.0, 1000.0
    x = np.array([10.0, 50.0, 90.0])
    y = np.array([50.0, 50.0, 50.0])
    valid = np.ones(3, dtype=bool)
    out = side_mass_from_xy(x, y, valid, cx=cx, cy=cy, ppm=ppm, rotate_180=False)
    assert out["frac_nvl_side"] == 0.0
    assert out["frac_fam_side"] == 1.0
    assert out["mean_signed_x_m"] < 0.0


def test_rot180_moves_right_mass_to_left() -> None:
    """Points on the right become left after fam-left rot180 — nvl share flips."""
    cx, cy, ppm = 100.0, 50.0, 1000.0
    x = np.array([150.0, 160.0, 170.0])
    y = np.array([50.0, 50.0, 50.0])
    valid = np.ones(3, dtype=bool)
    plain = side_mass_from_xy(x, y, valid, cx=cx, cy=cy, ppm=ppm, rotate_180=False)
    flipped = side_mass_from_xy(x, y, valid, cx=cx, cy=cy, ppm=ppm, rotate_180=True)
    assert plain["frac_nvl_side"] == 1.0
    assert flipped["frac_nvl_side"] == 0.0
    assert flipped["mean_signed_x_m"] == -plain["mean_signed_x_m"]


def test_mean_signed_x_m_known_offset() -> None:
    """Worked example: three frames at +50 px, ppm=1000 → +0.05 m."""
    cx, cy, ppm = 0.0, 0.0, 1000.0
    x = np.array([50.0, 50.0, 50.0])
    y = np.zeros(3)
    valid = np.ones(3, dtype=bool)
    out = side_mass_from_xy(x, y, valid, cx=cx, cy=cy, ppm=ppm, rotate_180=False)
    assert abs(out["mean_signed_x_m"] - 0.05) < 1e-12


def test_invalid_and_nan_frames_dropped() -> None:
    cx, cy, ppm = 100.0, 50.0, 1000.0
    x = np.array([150.0, np.nan, 50.0])
    y = np.array([50.0, 50.0, 50.0])
    valid = np.array([True, True, False])
    out = side_mass_from_xy(x, y, valid, cx=cx, cy=cy, ppm=ppm, rotate_180=False)
    assert out["n_valid"] == 1.0
    assert out["frac_nvl_side"] == 1.0


def test_empty_valid_yields_nan() -> None:
    out = side_mass_from_xy(
        np.array([1.0]),
        np.array([1.0]),
        np.array([False]),
        cx=0.0,
        cy=0.0,
        ppm=1000.0,
        rotate_180=False,
    )
    assert out["n_valid"] == 0.0
    assert np.isnan(out["frac_nvl_side"])
    assert np.isnan(out["mean_signed_x_m"])
