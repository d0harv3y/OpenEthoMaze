"""Litmus checks for open-field frailty feature scalars."""

from __future__ import annotations

import numpy as np

from maze.pipeline.open_field.features import (
    distance_to_quad_edge,
    feature_rows_for_video,
    frame_speeds_px_s,
    max_move_bout_distance,
    meander_deg_per_px,
    moving_mask,
    path_and_steps,
    point_to_segment_distance,
    prepare_of_track,
    rear_proxy_count,
)


def test_point_to_segment_distance_at_endpoint_and_midpoint() -> None:
    a = np.array([0.0, 0.0])
    b = np.array([10.0, 0.0])
    assert point_to_segment_distance(np.array([0.0, 0.0]), a, b) == 0.0
    assert point_to_segment_distance(np.array([5.0, 3.0]), a, b) == 3.0
    assert point_to_segment_distance(np.array([12.0, 0.0]), a, b) == 2.0


def test_distance_to_quad_edge_is_zero_on_a_vertex() -> None:
    square = np.array([[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]])
    dist = distance_to_quad_edge(np.array([[0.0, 0.0], [5.0, 5.0]]), square)
    assert dist[0] == 0.0
    assert abs(dist[1] - 5.0) < 1e-9


def test_frame_speeds_skip_gaps_and_do_not_count_as_immobility() -> None:
    xy = np.array([[0.0, 0.0], [1.0, 0.0], [100.0, 0.0], [101.0, 0.0]], dtype=np.float64)
    trusted = np.array([True, True, False, True])
    speed = frame_speeds_px_s(xy, trusted, fps=10.0)
    assert np.isnan(speed[0])
    assert abs(speed[1] - 10.0) < 1e-9
    assert np.isnan(speed[2])
    assert np.isnan(speed[3])


def test_meander_is_zero_on_a_straight_line() -> None:
    xy = np.column_stack([np.arange(10, dtype=np.float64), np.zeros(10)])
    trust = np.ones(10, dtype=bool)
    _, step = path_and_steps(xy, trust)
    assert meander_deg_per_px(xy, trust, step) == 0.0


def test_meander_counts_a_right_angle() -> None:
    xy = np.array([[0.0, 0.0], [10.0, 0.0], [10.0, 10.0]], dtype=np.float64)
    trust = np.ones(3, dtype=bool)
    path, step = path_and_steps(xy, trust)
    assert abs(path - 20.0) < 1e-9
    assert abs(meander_deg_per_px(xy, trust, step) - (90.0 / 20.0)) < 1e-6


def test_max_move_bout_distance_takes_the_longest_run() -> None:
    step = np.array([np.nan, 1.0, 1.0, np.nan, 2.0, 2.0, 2.0], dtype=np.float64)
    moving = np.array([False, True, True, False, True, True, True])
    # Long bout steps 2+2+2 = 6.
    assert abs(max_move_bout_distance(step, moving, min_bout_frames=2) - 6.0) < 1e-9


def test_moving_mask_hysteresis_ignores_brief_spikes_and_dips() -> None:
    fps = 10.0
    n = 40
    step = np.full(n, np.nan)
    trust = np.ones(n, dtype=bool)
    # Steady walk: 1.5 px/frame → 15 px/s (above start=8).
    step[1:15] = 1.5
    # Brief 1-frame spike, then stillness — must not enter moving.
    step[18] = 2.0
    step[19:22] = 0.05
    # Second bout with a one-frame dip below stop (exit debounce keeps moving).
    step[22:36] = 1.5
    step[28] = 0.1  # below stop=0.4 px/frame for one frame only
    moving = moving_mask(
        step,
        trust,
        fps=fps,
        start_speed_px_s=8.0,
        stop_speed_px_s=4.0,
        entry_debounce_frames=3,
        exit_debounce_frames=3,
        speed_median_window_frames=1,
        min_bout_frames=4,
        inter_bout_gap_frames=0,
    )
    assert not moving[0]
    assert moving[5]
    assert not moving[18]  # lone spike washed out by stillness
    assert moving[28]  # single dip inside bout kept moving
    assert moving[32]


def test_rear_proxy_counts_a_short_still_stretch() -> None:
    n = 20
    nose = np.zeros((n, 2))
    center = np.zeros((n, 2))
    tail = np.zeros((n, 2))
    # Colinear along x near left wall; shorten while keeping ~180° angle.
    nose[:, 0] = 0.0
    center[:, 0] = 20.0
    tail[:, 0] = 40.0
    nose[5:11, 0] = 0.0
    center[5:11, 0] = 10.0
    tail[5:11, 0] = 20.0
    ok = np.ones(n, dtype=bool)
    speed = np.zeros(n)
    floor = np.array([[0.0, 0.0], [100.0, 0.0], [100.0, 100.0], [0.0, 100.0]])
    count = rear_proxy_count(
        nose,
        tail,
        center,
        ok,
        speed,
        length_frac=0.75,
        max_speed_px_s=15.0,
        min_frames=3,
        min_angle_deg=160.0,
        floor_vertices_xy=floor,
        near_wall_band_px=40.0,
        require_near_wall=True,
    )
    assert count == 1.0


def test_rear_proxy_rejects_curled_angle_like_grooming() -> None:
    n = 20
    nose = np.zeros((n, 2))
    center = np.zeros((n, 2))
    tail = np.zeros((n, 2))
    # Baseline stretched near wall.
    nose[:, 0] = 2.0
    center[:, 0] = 22.0
    tail[:, 0] = 42.0
    # Frames 5–11: short body but curled (nose and tail on same side of center).
    nose[5:12, 0] = 8.0
    nose[5:12, 1] = 12.0
    center[5:12, 0] = 20.0
    center[5:12, 1] = 0.0
    tail[5:12, 0] = 8.0
    tail[5:12, 1] = -12.0
    ok = np.ones(n, dtype=bool)
    speed = np.zeros(n)
    floor = np.array([[0.0, 0.0], [100.0, 0.0], [100.0, 100.0], [0.0, 100.0]])
    count = rear_proxy_count(
        nose,
        tail,
        center,
        ok,
        speed,
        length_frac=0.75,
        max_speed_px_s=15.0,
        min_frames=3,
        min_angle_deg=160.0,
        floor_vertices_xy=floor,
        near_wall_band_px=40.0,
        require_near_wall=True,
    )
    assert count == 0.0


def test_rear_proxy_rejects_center_field_when_wall_required() -> None:
    n = 20
    nose = np.zeros((n, 2))
    center = np.zeros((n, 2))
    tail = np.zeros((n, 2))
    # Mid-arena (y=50 so not sitting on the floor edge).
    nose[:, :] = (50.0, 50.0)
    center[:, :] = (70.0, 50.0)
    tail[:, :] = (90.0, 50.0)
    nose[5:11, 0] = 50.0
    center[5:11, 0] = 60.0
    tail[5:11, 0] = 70.0
    ok = np.ones(n, dtype=bool)
    speed = np.zeros(n)
    floor = np.array([[0.0, 0.0], [100.0, 0.0], [100.0, 100.0], [0.0, 100.0]])
    count = rear_proxy_count(
        nose,
        tail,
        center,
        ok,
        speed,
        length_frac=0.75,
        max_speed_px_s=15.0,
        min_frames=3,
        min_angle_deg=160.0,
        floor_vertices_xy=floor,
        near_wall_band_px=20.0,
        require_near_wall=True,
    )
    assert count == 0.0


def test_prepare_of_track_fills_short_gaps_not_long() -> None:
    xy = np.column_stack([np.arange(20, dtype=np.float64), np.zeros(20)])
    lik = np.ones(20)
    lik[5:8] = 0.1  # 3-frame gap → fill when max_gap=3
    lik[12:18] = 0.1  # 6-frame gap → keep empty when max_gap=3
    out, trusted, interpolated = prepare_of_track(
        xy,
        lik,
        likelihood_min=0.6,
        interpolate_gaps=True,
        max_gap_frames=3,
        trace_smooth=False,
    )
    assert trusted[5] and trusted[6] and trusted[7]
    assert interpolated[5] and interpolated[7]
    assert abs(out[6, 0] - 6.0) < 1e-6
    assert not trusted[12] and not trusted[17]
    assert not interpolated[12]


def test_feature_rows_parks_scalars_on_a_toy_track() -> None:
    fps = 10.0
    n = 100
    t = np.arange(n) / fps
    xy = np.zeros((n, 2), dtype=np.float64)
    xy[:50, 0] = np.arange(50)
    xy[50:, 0] = 49.0
    xy[:, 1] = 1.0
    lik = np.ones(n, dtype=np.float64)
    nose = xy + np.array([0.0, -20.0])
    tail = xy + np.array([0.0, 20.0])
    floor = np.array([[0.0, 0.0], [200.0, 0.0], [200.0, 100.0], [0.0, 100.0]])
    rows = feature_rows_for_video(
        video_id="toy",
        xy=xy,
        likelihood=lik,
        fps=fps,
        duration_s=float(t[-1]),
        bin_width_s=5.0,
        nose_xy=nose,
        tail_xy=tail,
        nose_likelihood=lik,
        tail_likelihood=lik,
        floor_vertices_xy=floor,
        move_start_speed_px_s=8.0,
        move_stop_speed_px_s=4.0,
        move_entry_debounce_frames=3,
        move_exit_debounce_frames=3,
        move_speed_median_window=1,
        min_bout_frames=4,
        inter_bout_gap_frames=0,
        thigmotaxis_band_px=5.0,
        rear_require_near_wall=True,
        interpolate_gaps=False,
        trace_smooth=False,
    )
    assert len(rows) == 1
    row = rows[0]
    assert row.n_frames == 50
    assert abs(row.path_length_px - 49.0) < 1e-6
    assert row.max_move_bout_distance_px > 40.0
    assert abs(row.mean_speed_px_s - (49.0 / 5.0)) < 1e-6
    assert row.meander_deg_per_px == 0.0
    assert row.frac_moving > 0.7
    assert row.thigmotaxis_frac == 1.0
    assert row.rear_proxy_count == 0.0
    assert row.frac_interpolated == 0.0


def test_low_likelihood_frames_are_excluded_from_path_without_interp() -> None:
    xy = np.array([[0.0, 0.0], [10.0, 0.0], [20.0, 0.0]], dtype=np.float64)
    lik = np.array([1.0, 0.1, 1.0])
    rows = feature_rows_for_video(
        video_id="gap",
        xy=xy,
        likelihood=lik,
        fps=10.0,
        duration_s=1.0,
        bin_width_s=1.0,
        floor_vertices_xy=None,
        likelihood_min=0.6,
        min_bout_frames=1,
        inter_bout_gap_frames=0,
        move_entry_debounce_frames=1,
        move_exit_debounce_frames=1,
        move_speed_median_window=1,
        interpolate_gaps=False,
        trace_smooth=False,
    )
    assert len(rows) == 1
    assert rows[0].path_length_px == 0.0
    assert rows[0].n_trusted == 2
    assert rows[0].frac_interpolated == 0.0


def test_short_gap_interp_reconnects_path() -> None:
    xy = np.array([[0.0, 0.0], [10.0, 0.0], [20.0, 0.0]], dtype=np.float64)
    lik = np.array([1.0, 0.1, 1.0])
    rows = feature_rows_for_video(
        video_id="gap_fill",
        xy=xy,
        likelihood=lik,
        fps=10.0,
        duration_s=1.0,
        bin_width_s=1.0,
        floor_vertices_xy=None,
        likelihood_min=0.6,
        min_bout_frames=1,
        inter_bout_gap_frames=0,
        move_entry_debounce_frames=1,
        move_exit_debounce_frames=1,
        move_speed_median_window=1,
        interpolate_gaps=True,
        max_gap_frames=3,
        trace_smooth=False,
        move_start_speed_px_s=1.0,
        move_stop_speed_px_s=0.5,
    )
    assert len(rows) == 1
    assert abs(rows[0].path_length_px - 20.0) < 1e-6
    assert rows[0].n_trusted == 3
    assert abs(rows[0].frac_interpolated - (1.0 / 3.0)) < 1e-9
