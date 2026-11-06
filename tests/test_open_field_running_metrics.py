"""Litmus checks for running open-field metric counters."""

from __future__ import annotations

import numpy as np

from maze.pipeline.open_field.running_metrics import compute_running_metrics


def test_running_path_and_mean_speed_on_a_straight_walk() -> None:
    fps = 10.0
    n = 20
    xy = np.zeros((n, 2), dtype=np.float64)
    xy[:, 0] = np.arange(n)
    lik = np.ones(n)
    series = compute_running_metrics(
        xy,
        lik,
        fps=fps,
        move_start_speed_px_s=8.0,
        move_stop_speed_px_s=4.0,
        move_entry_debounce_frames=1,
        move_exit_debounce_frames=1,
        move_speed_median_window=1,
        min_bout_frames=1,
        inter_bout_gap_frames=0,
        interpolate_gaps=False,
        trace_smooth=False,
    )
    assert abs(series.path_length_px[-1] - 19.0) < 1e-6
    assert abs(series.mean_speed_px_s[-1] - (19.0 / 2.0)) < 1e-6
    assert series.meander_deg_per_px[-1] == 0.0
    assert series.moving[1]
    assert not series.moving[0]
    assert abs(series.center_speed_px_s[1] - 10.0) < 1e-6
    assert np.isnan(series.nose_center_tail_angle_deg[1])
    assert np.isnan(series.body_length_frac[1])


def test_rear_proxy_increments_once_per_bout() -> None:
    n = 30
    # Fixed center so shortening does not create a center-speed spike.
    xy = np.zeros((n, 2))
    xy[:, 0] = 20.0
    lik = np.ones(n)
    nose = np.zeros((n, 2))
    tail = np.zeros((n, 2))
    nose[:, 0] = 0.0
    tail[:, 0] = 40.0
    nose[10:18, 0] = 10.0
    tail[10:18, 0] = 30.0
    series = compute_running_metrics(
        xy,
        lik,
        fps=10.0,
        nose_xy=nose,
        tail_xy=tail,
        nose_likelihood=lik,
        tail_likelihood=lik,
        rear_min_frames=3,
        rear_length_frac=0.75,
        rear_min_angle_deg=160.0,
        rear_require_near_wall=False,
        min_bout_frames=1,
        inter_bout_gap_frames=0,
        move_entry_debounce_frames=1,
        move_exit_debounce_frames=1,
        move_speed_median_window=1,
        interpolate_gaps=False,
        trace_smooth=False,
    )
    assert series.rear_proxy_count[9] == 0.0
    assert series.rear_proxy_count[12] == 1.0
    assert series.rear_proxy_count[-1] == 1.0
    assert series.rear_active[12]
    assert abs(series.body_length_frac[0] - 1.0) < 0.05
    assert abs(series.body_length_frac[12] - 0.5) < 0.05
    assert abs(series.nose_center_tail_angle_deg[12] - 180.0) < 1e-6


def test_rear_proxy_wall_gate_on_overlay_path() -> None:
    """Supported-rear prior: short+still only counts near the floor edge."""
    n = 30
    xy = np.zeros((n, 2))
    xy[:, 0] = 22.0
    xy[:, 1] = 50.0
    lik = np.ones(n)
    nose = np.zeros((n, 2))
    tail = np.zeros((n, 2))
    nose[:, 0] = 2.0
    nose[:, 1] = 50.0
    tail[:, 0] = 42.0
    tail[:, 1] = 50.0
    # Shorten about a fixed center (no center-speed spike).
    nose[10:18, 0] = 12.0
    tail[10:18, 0] = 32.0
    floor = np.array([[0.0, 0.0], [100.0, 0.0], [100.0, 100.0], [0.0, 100.0]])
    near = compute_running_metrics(
        xy,
        lik,
        fps=10.0,
        nose_xy=nose,
        tail_xy=tail,
        nose_likelihood=lik,
        tail_likelihood=lik,
        floor_vertices_xy=floor,
        rear_require_near_wall=True,
        thigmotaxis_band_px=40.0,
        rear_min_frames=3,
        rear_length_frac=0.75,
        rear_min_angle_deg=160.0,
        min_bout_frames=1,
        inter_bout_gap_frames=0,
        move_entry_debounce_frames=1,
        move_exit_debounce_frames=1,
        move_speed_median_window=1,
        interpolate_gaps=False,
        trace_smooth=False,
    )
    assert near.rear_proxy_count[-1] == 1.0

    # Same bout in arena center → rejected when wall required.
    xy_c = xy.copy()
    nose_c = nose.copy()
    tail_c = tail.copy()
    xy_c[:, 0] = 70.0
    nose_c[:, 0] = 50.0
    tail_c[:, 0] = 90.0
    nose_c[10:18, 0] = 60.0
    tail_c[10:18, 0] = 80.0
    mid = compute_running_metrics(
        xy_c,
        lik,
        fps=10.0,
        nose_xy=nose_c,
        tail_xy=tail_c,
        nose_likelihood=lik,
        tail_likelihood=lik,
        floor_vertices_xy=floor,
        rear_require_near_wall=True,
        thigmotaxis_band_px=20.0,
        rear_min_frames=3,
        rear_length_frac=0.75,
        rear_min_angle_deg=160.0,
        min_bout_frames=1,
        inter_bout_gap_frames=0,
        move_entry_debounce_frames=1,
        move_exit_debounce_frames=1,
        move_speed_median_window=1,
        interpolate_gaps=False,
        trace_smooth=False,
    )
    assert mid.rear_proxy_count[-1] == 0.0
