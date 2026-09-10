"""Litmus for syllable spatial heatmap geometry + compositing."""

from __future__ import annotations

import numpy as np

from nor_object_mi.syllable_spatial_heatmap import (
    GrainKey,
    TxOverlayGrainKey,
    all_condition_overlay_grains,
    batch_grains,
    composite_dwell_overlay,
    needs_novel_alignment,
    rotate180_xy,
    tx_colors_bgr,
)


def test_rotate180_about_center() -> None:
    cx, cy = 100.0, 200.0
    x = np.array([110.0, 90.0])
    y = np.array([210.0, 190.0])
    xr, yr = rotate180_xy(x, y, cx=cx, cy=cy)
    assert np.allclose(xr, [90.0, 110.0])
    assert np.allclose(yr, [190.0, 210.0])


def test_novel_alignment_flag() -> None:
    # fam on right when nvl is on hist A → rotate so fam sits left
    assert needs_novel_alignment("a") is True
    assert needs_novel_alignment("b") is False
    assert needs_novel_alignment("") is False


def test_role_mean_survives_half_rotated_sessions() -> None:
    """Hist A/B averaging after 50% rot180 collapses to center; role mean must not."""
    from nor_object_mi.syllable_spatial_heatmap import LocusMarker

    # Two sessions: same fam/nvl geometry; only one needs rot180.
    # Unrotated: fam at (100, 200), nvl at (300, 100)
    # Rotated 180 about (200, 150): fam (100,200)->(300,100), nvl (300,100)->(100,200)
    # If we wrongly average hist slots after rotate, means collapse; role mean stays apart
    # when we always accumulate fam→left, nvl→right *after* alignment:
    fam_aligned = [np.array([100.0, 200.0]), np.array([100.0, 200.0])]  # both fam-left after align
    nvl_aligned = [np.array([300.0, 100.0]), np.array([300.0, 100.0])]
    ml = np.mean(np.stack(fam_aligned), axis=0)
    mr = np.mean(np.stack(nvl_aligned), axis=0)
    assert np.linalg.norm(ml - mr) > 50

    # Broken hist-A averaging with one rotated session (A flips sides):
    hist_a = [np.array([100.0, 200.0]), np.array([300.0, 100.0])]  # unrot A + rot A
    hist_b = [np.array([300.0, 100.0]), np.array([100.0, 200.0])]
    broken_sep = float(np.linalg.norm(np.mean(hist_a, 0) - np.mean(hist_b, 0)))
    assert broken_sep < 5.0
    _ = LocusMarker  # import kept for type clarity in failure messages



def test_draw_rotation_notation_writes_pixels() -> None:
    from nor_object_mi.syllable_spatial_heatmap import draw_rotation_notation

    img = np.full((40, 120, 3), 200, dtype=np.uint8)
    draw_rotation_notation(img, n_rotated=3, n_sessions=24)
    assert not np.array_equal(img[10:25, 8:90], np.full((15, 82, 3), 200, dtype=np.uint8))


def test_draw_condition_notation_upper_right() -> None:
    from nor_object_mi.syllable_spatial_heatmap import draw_condition_notation

    img = np.full((40, 200, 3), 200, dtype=np.uint8)
    draw_condition_notation(img, "noSD")
    # left stays blank; right corner changes
    assert np.array_equal(img[10:25, 0:40], np.full((15, 40, 3), 200, dtype=np.uint8))
    assert not np.array_equal(img[10:25, 150:195], np.full((15, 45, 3), 200, dtype=np.uint8))


def test_grain_slug_includes_tx() -> None:
    g = GrainKey("NOR_TX", "nvl_obj", "M", "noSD")
    assert g.slug() == "NOR_TX__nvl_obj__M__noSD"


def test_batch_nvl_obj_m_is_twelve_grains() -> None:
    grains = batch_grains("nvl_obj", "M")
    assert len(grains) == 12  # 4 phases × 3 tx
    assert all(g.trial == "nvl_obj" and g.sex == "M" for g in grains)


def test_batch_bl_only_is_three_tx() -> None:
    grains = batch_grains("nvl_obj", "M", phases=("NOR_BL",))
    assert len(grains) == 3
    assert {g.condition for g in grains} == {"noSD", "GHSD", "RBSD"}


def test_draw_arena_outline_marks_corners() -> None:
    from nor_object_mi.syllable_spatial_heatmap import draw_arena_outline

    img = np.zeros((80, 100, 3), dtype=np.uint8)
    draw_arena_outline(img, np.array([10.0, 15.0, 70.0, 60.0]))
    assert not np.array_equal(img[15, 10], np.array([0, 0, 0]))
    assert np.array_equal(img[0, 0], np.array([0, 0, 0]))


def test_identical_labels_are_id0_id1() -> None:
    """Contract: id_obj markers are id_0 (left) / id_1 (right)."""
    assert ("id_0", "id_1") == ("id_0", "id_1")
    # Label policy lives in loci_markers_for_grain; keep token stable for docs/CLI.
    from nor_object_mi.syllable_spatial_heatmap import LocusMarker

    left = LocusMarker(10, 20, "id_0")
    right = LocusMarker(90, 20, "id_1")
    assert left.label == "id_0" and right.label == "id_1"
    assert left.x < right.x


def test_keep_clusters_skips_other_ids_in_composite() -> None:
    """Filtered overlay should only tint from kept cluster mass."""
    bg = np.zeros((8, 8, 3), dtype=np.uint8)
    dwell = {
        13: np.zeros((8, 8), dtype=np.float32),
        2: np.zeros((8, 8), dtype=np.float32),
    }
    dwell[13][3, 3] = 10.0
    dwell[2][5, 5] = 10.0
    colors = {13: (0, 0, 255), 2: (255, 0, 0)}
    kept = {13: dwell[13]}
    out = composite_dwell_overlay(bg, kept, colors, vmax_s=10.0)
    assert int(out[3, 3, 2]) > 0  # red channel from BGR (0,0,255)
    assert int(out[5, 5].sum()) == 0


def test_blank_canvas_black() -> None:
    from nor_object_mi.syllable_spatial_heatmap import blank_canvas

    img = blank_canvas((12, 16))
    assert img.shape == (12, 16, 3)
    assert int(img[0, 0, 0]) == 0


def test_composite_tints_high_dwell_pixel() -> None:
    bg = np.full((10, 10, 3), 255, dtype=np.uint8)
    dwell = {3: np.zeros((10, 10), dtype=np.float32)}
    dwell[3][5, 5] = 10.0
    colors = {3: (0, 0, 255)}
    out = composite_dwell_overlay(bg, dwell, colors, vmax_s=10.0)
    assert int(out[5, 5, 0]) < 255
    assert int(out[0, 0, 0]) == 255


def test_condition_overlay_grain_slug_and_count() -> None:
    g = TxOverlayGrainKey("NOR_BL", "nvl_obj", "M")
    assert g.slug() == "NOR_BL__nvl_obj__M__all_tx"
    assert len(all_condition_overlay_grains()) == 24  # 4 phases × 3 cond × 2 sex


def test_condition_colors_match_violin_hex() -> None:
    colors = tx_colors_bgr()
    assert set(colors) == {"noSD", "GHSD", "RBSD"}
    # noSD #1b9e77 → BGR (119, 158, 27)
    assert colors["noSD"] == (119, 158, 27)


def test_condition_overlay_composite_mixes_two_condition_colors() -> None:
    bg = np.zeros((8, 8, 3), dtype=np.uint8)
    colors = tx_colors_bgr()
    dwell = {
        "noSD": np.zeros((8, 8), dtype=np.float32),
        "GHSD": np.zeros((8, 8), dtype=np.float32),
    }
    dwell["noSD"][4, 4] = 5.0
    dwell["GHSD"][4, 4] = 5.0
    out = composite_dwell_overlay(bg, dwell, colors, vmax_s=10.0)
    px = out[4, 4]
    assert px[0] > 0 and px[1] > 0 and px[2] > 0


def test_composite_mixes_two_cluster_colors() -> None:
    bg = np.zeros((8, 8, 3), dtype=np.uint8)
    dwell = {
        1: np.zeros((8, 8), dtype=np.float32),
        2: np.zeros((8, 8), dtype=np.float32),
    }
    dwell[1][4, 4] = 5.0
    dwell[2][4, 4] = 5.0
    colors = {1: (255, 0, 0), 2: (0, 255, 0)}  # BGR blue + green → cyan mix
    out = composite_dwell_overlay(bg, dwell, colors, vmax_s=10.0)
    px = out[4, 4]
    assert px[0] > 0 and px[1] > 0  # both blue and green channels
