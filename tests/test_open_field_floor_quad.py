"""Litmus checks for the open-field floor quadrilateral."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from maze.cli.of_mask_video import vertices_for_video

from maze.pipeline.open_field.floor_quad import (
    FloorQuad,
    FloorQuadParams,
    _four_inner_lines,
    _intersect_line_pairs,
    _place_on_pose,
    _relock_lines,
    cohort_qc_flags,
    fit_floor_quad,
    POSE_MASK_SCALE,
    mask_outside_quad,
    mean_diagonal_px,
    scale_quad_about_center,
    quad_review_flags,
    rectified_side_ratio,
    snap_quad_to_dark_edge,
)


def _diamond(center: tuple[float, float], radius: float) -> np.ndarray:
    cx, cy = center
    return np.array(
        [[cx, cy - radius], [cx + radius, cy], [cx, cy + radius], [cx - radius, cy]],
        dtype=np.float32,
    )


def _max_vertex_error(got: np.ndarray, expected: np.ndarray) -> float:
    used: set[int] = set()
    errors: list[float] = []
    for point in expected:
        distances = np.linalg.norm(got - point, axis=1)
        for index in np.argsort(distances):
            index = int(index)
            if index not in used:
                used.add(index)
                errors.append(float(distances[index]))
                break
    return max(errors)


def test_known_diamond_recovers_on_the_dark_side_of_the_step() -> None:
    expected = _diamond((319.5, 239.5), 180.0)
    image = np.full((480, 640), 40, np.uint8)
    cv2.fillPoly(image, [expected.astype(np.int32)], 170)
    image = cv2.GaussianBlur(image, (5, 5), 0)

    quad = fit_floor_quad(image)
    assert quad is not None
    # The shared shift sits on the dark side of the blurred step, a few pixels outside the fill.
    assert _max_vertex_error(quad.vertices_xy, expected) <= 18.0
    assert quad_review_flags(quad, image.shape) == ()
    sides = _side_lengths(quad.vertices_xy)
    assert abs(sides[0] - sides[2]) < 0.5
    assert abs(sides[1] - sides[3]) < 0.5
    assert quad.seed_diagonal_px > 0.0
    assert mean_diagonal_px(quad.vertices_xy) + 1.0 >= quad.seed_diagonal_px


def test_outer_rim_does_not_replace_the_floor() -> None:
    inner = _diamond((319.5, 239.5), 180.0)
    outer = _diamond((319.5, 239.5), 300.0)
    image = np.full((480, 640), 30, np.uint8)
    cv2.fillPoly(image, [np.round(outer).astype(np.int32)], 80)
    cv2.fillPoly(image, [inner.astype(np.int32)], 170)
    image = cv2.GaussianBlur(image, (5, 5), 0)

    quad = fit_floor_quad(image)
    assert quad is not None
    assert _max_vertex_error(quad.vertices_xy, inner) <= 18.0
    assert _max_vertex_error(quad.vertices_xy, outer) > 50.0


def test_dark_crease_on_bright_walls() -> None:
    """A wall as bright as the floor still stops the fit on the crease line."""
    floor = _diamond((319.5, 239.5), 180.0)
    image = np.full((480, 640), 160, np.uint8)
    cv2.polylines(image, [floor.astype(np.int32)], True, 30, 3)
    image = cv2.GaussianBlur(image, (3, 3), 0)

    quad = fit_floor_quad(image)
    assert quad is not None
    # The innermost line sits on the inner side of the stroked crease, so the
    # tolerance is wider than the filled-diamond case. It is still the floor,
    # not the image border.
    assert _max_vertex_error(quad.vertices_xy, floor) <= 24.0


def test_snap_locks_to_dark_crease_not_corner_posts() -> None:
    """An inset seed moves to the dark crease. Posts past the corners do not pull the sides."""
    crease = _diamond((319.5, 239.5), 180.0)
    seed = _diamond((319.5, 239.5), 166.0)
    image = np.full((480, 640), 110, np.uint8)
    cv2.fillPoly(image, [crease.astype(np.int32)], 180)
    cv2.polylines(image, [crease.astype(np.int32)], True, 25, 3)
    center = np.array([319.5, 239.5])
    for vertex in crease:
        direction = vertex - center
        direction = direction / np.linalg.norm(direction)
        post = vertex + 18.0 * direction
        cv2.circle(image, (int(round(post[0])), int(round(post[1]))), 8, 20, -1)

    snapped = snap_quad_to_dark_edge(image, seed)
    assert snapped is not None
    assert _max_vertex_error(snapped, crease) <= 8.0
    assert _max_vertex_error(snapped, crease) < _max_vertex_error(seed, crease)


def _side_lengths(vertices: np.ndarray) -> np.ndarray:
    edge = np.roll(vertices, -1, axis=0) - vertices
    return np.hypot(edge[:, 0], edge[:, 1])


def _hough_line(degrees: float, offset: float) -> tuple[float, float, float]:
    return (float(np.deg2rad(degrees)), 0.0, float(offset))


def _square(center: tuple[float, float], half: float) -> np.ndarray:
    cx, cy = center
    return np.array(
        [[cx - half, cy - half], [cx + half, cy - half], [cx + half, cy + half], [cx - half, cy + half]],
        dtype=np.float64,
    )


def test_faint_opposite_matches_partner_distance_not_the_far_wall() -> None:
    """Test 96 / 135: one crease is missing from the strong edges and must not be replaced by the far wall."""
    cfg = FloorQuadParams()
    strong = [
        _hough_line(36, 116),
        _hough_line(38, 116),
        _hough_line(40, 118),
        _hough_line(36, -140),
        _hough_line(38, -142),
        _hough_line(40, -144),
        _hough_line(130, -136),
        _hough_line(132, -136),
        _hough_line(134, -138),
    ]
    assert _four_inner_lines(strong, cfg) is None
    faint = strong + [_hough_line(129, 126), _hough_line(129, 105), _hough_line(115, 172)]
    found = _four_inner_lines(strong, cfg, fill_from=faint)
    assert found is not None
    chosen, _modes = found
    offsets = [line[2] for line in chosen]
    assert any(abs(offset - 126) < 1 for offset in offsets)
    assert all(abs(offset) < 160 for offset in offsets)


def test_locked_angles_make_opposite_sides_equal() -> None:
    """Lines tilted inside the member window become one parallelogram."""
    center = (320.0, 240.0)
    cx, cy = center

    def line(degrees: float, offset: float) -> tuple[float, float, float]:
        theta = float(np.deg2rad(degrees))
        rho = offset + cx * np.cos(theta) + cy * np.sin(theta)
        return theta, rho, offset

    lines = [line(28, 110), line(44, -110), line(118, 130), line(138, -130)]
    modes = (float(np.deg2rad(36)), float(np.deg2rad(128)))
    vertices = _intersect_line_pairs(_relock_lines(lines, modes, center))
    assert vertices is not None
    sides = _side_lengths(vertices)
    assert abs(sides[0] - sides[2]) < 1e-3
    assert abs(sides[1] - sides[3]) < 1e-3
    assert abs(sides[0] - sides[1]) > 5.0


def test_corner_span_uses_a_5_percent_band() -> None:
    square = _square((320.0, 240.0), 80.0)
    vertices = np.stack([square, square, square, square])
    flags = cohort_qc_flags(vertices, np.array([100.0, 100.0, 100.0, 105.0]), pose_bin_px=500.0)
    assert flags == [(), (), (), ()]
    flags = cohort_qc_flags(vertices, np.array([100.0, 100.0, 100.0, 106.0]), pose_bin_px=500.0)
    assert flags[3] == ("corner_span",)
    assert flags[0] == ()


def test_side_mismatch_is_measured_in_the_pose_plane() -> None:
    square = _square((320.0, 240.0), 80.0)
    stretched = square.copy()
    stretched[1, 0] += 40.0
    vertices = np.stack([square, square, square, square, stretched])
    flags = cohort_qc_flags(vertices, np.full(5, 200.0), pose_bin_px=500.0)
    assert flags[0] == ()
    assert "side_mismatch" in flags[4]
    assert "corner_span" not in flags[4]


def test_side_check_uses_the_pose_from_before_the_refit() -> None:
    square = _square((320.0, 240.0), 80.0)
    stretched = square.copy()
    stretched[1, 0] += 40.0
    own = cohort_qc_flags(np.stack([stretched] * 4), np.full(4, 200.0), pose_bin_px=500.0)
    frozen = cohort_qc_flags(
        np.stack([stretched] * 4),
        np.full(4, 200.0),
        shape_source=np.stack([square] * 4),
        pose_bin_px=500.0,
    )
    assert own == [(), (), (), ()]
    assert all("side_mismatch" in flags for flags in frozen)


def test_pose_placement_clears_side_mismatch_without_changing_the_ruler() -> None:
    square = _square((320.0, 240.0), 80.0)
    stretched = square.copy()
    stretched[1, 0] += 40.0
    quad = FloorQuad(vertices_xy=stretched, area_px=1.0, seed_diagonal_px=200.0, outward_px=4.0)
    placed = _place_on_pose(quad, square)
    assert placed.seed_diagonal_px == 200.0
    assert placed.outward_px == 4.0
    assert rectified_side_ratio(placed.vertices_xy, square) <= 1.03


def test_vertices_for_video_skips_a_flagged_quad(tmp_path: Path) -> None:
    table = tmp_path / "floor_quads.csv"
    table.write_text(
        "video_stem,status,flags,x0,y0,x1,y1,x2,y2,x3,y3\n" "Test 1,pass,,0,0,1,0,1,1,0,1\n" "Test 68,review,area_out_of_band,0,0,1,0,1,1,0,1\n",
        encoding="utf-8",
    )
    assert vertices_for_video(table, "Test 1").shape == (4, 2)
    with pytest.raises(ValueError, match="area_out_of_band"):
        vertices_for_video(table, "Test 68")


def test_pose_mask_keeps_the_wall_band_and_zeros_beyond_the_blue_roi() -> None:
    image = np.full((120, 160), 200, np.uint8)
    quad = _diamond((79.5, 59.5), 30.0)
    pose = scale_quad_about_center(quad, POSE_MASK_SCALE)
    assert POSE_MASK_SCALE == 1.8
    assert np.allclose(pose.mean(axis=0), quad.mean(axis=0))
    masked = mask_outside_quad(image, pose)
    # 40 px right of center: outside the green floor (radius 30), inside the 1.8x zone (radius 54).
    assert masked[60, 120] == 200
    # 80 px right of center: outside the blue zone.
    assert masked[60, 159] == 0
    assert masked[60, 80] == 200
    assert not np.shares_memory(masked, image)


def test_blank_frame_returns_none() -> None:
    assert fit_floor_quad(np.full((480, 640), 40, np.uint8)) is None


def test_area_out_of_band_is_flagged() -> None:
    expected = _diamond((319.5, 239.5), 180.0)
    image = np.full((480, 640), 40, np.uint8)
    cv2.fillPoly(image, [expected.astype(np.int32)], 170)
    image = cv2.GaussianBlur(image, (5, 5), 0)
    quad = fit_floor_quad(image)
    assert quad is not None
    flags = quad_review_flags(quad, image.shape, area_min_px=80_000, area_max_px=90_000)
    assert flags == ("area_out_of_band",)
