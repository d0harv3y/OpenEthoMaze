"""Per-frame running Parks/Whitehead open-field counters (for overlay HUD).

Uses the same definitions as ``features.py``. Values at frame ``i`` are computed
from frames ``0..i`` inclusive. Pixel units until a floor length in cm exists.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from maze.pipeline.open_field.features import (
    DEFAULT_INTER_BOUT_GAP_FRAMES,
    DEFAULT_INTERPOLATE_GAPS,
    DEFAULT_LIKELIHOOD_MIN,
    DEFAULT_MAX_GAP_FRAMES,
    DEFAULT_MIN_BOUT_FRAMES,
    DEFAULT_MOVE_ENTRY_DEBOUNCE_FRAMES,
    DEFAULT_MOVE_EXIT_DEBOUNCE_FRAMES,
    DEFAULT_MOVE_SPEED_MEDIAN_WINDOW,
    DEFAULT_MOVE_START_SPEED_PX_S,
    DEFAULT_MOVE_STOP_SPEED_PX_S,
    DEFAULT_REAR_LENGTH_FRAC,
    DEFAULT_REAR_MAX_SPEED_PX_S,
    DEFAULT_REAR_MIN_ANGLE_DEG,
    DEFAULT_REAR_MIN_FRAMES,
    DEFAULT_REAR_REQUIRE_NEAR_WALL,
    DEFAULT_THIGMOTAXIS_BAND_PX,
    DEFAULT_TRACE_SMOOTH,
    DEFAULT_TRACE_SMOOTH_WINDOW,
    frame_speeds_px_s,
    moving_mask,
    nose_center_tail_angle_deg,
    path_and_steps,
    prepare_of_track,
    rear_proxy_frame_mask,
)


@dataclass(frozen=True)
class RunningMetricSeries:
    """Parallel arrays, one value per frame."""

    path_length_px: np.ndarray
    max_move_bout_distance_px: np.ndarray
    move_duration_s: np.ndarray
    frac_moving: np.ndarray
    meander_deg_per_px: np.ndarray
    mean_speed_px_s: np.ndarray
    rear_proxy_count: np.ndarray
    moving: np.ndarray
    rear_active: np.ndarray
    trusted: np.ndarray
    interpolated: np.ndarray
    # Instantaneous dial-in signals (after OEM prep)
    center_xy: np.ndarray
    center_speed_px_s: np.ndarray
    body_length_frac: np.ndarray
    nose_center_tail_angle_deg: np.ndarray


def compute_running_metrics(
    xy: np.ndarray,
    likelihood: np.ndarray,
    *,
    fps: float,
    nose_xy: np.ndarray | None = None,
    tail_xy: np.ndarray | None = None,
    nose_likelihood: np.ndarray | None = None,
    tail_likelihood: np.ndarray | None = None,
    floor_vertices_xy: np.ndarray | None = None,
    likelihood_min: float = DEFAULT_LIKELIHOOD_MIN,
    move_start_speed_px_s: float = DEFAULT_MOVE_START_SPEED_PX_S,
    move_stop_speed_px_s: float = DEFAULT_MOVE_STOP_SPEED_PX_S,
    move_entry_debounce_frames: int = DEFAULT_MOVE_ENTRY_DEBOUNCE_FRAMES,
    move_exit_debounce_frames: int = DEFAULT_MOVE_EXIT_DEBOUNCE_FRAMES,
    move_speed_median_window: int = DEFAULT_MOVE_SPEED_MEDIAN_WINDOW,
    min_bout_frames: int = DEFAULT_MIN_BOUT_FRAMES,
    inter_bout_gap_frames: int = DEFAULT_INTER_BOUT_GAP_FRAMES,
    immobile_speed_px_s: float | None = None,
    rear_length_frac: float = DEFAULT_REAR_LENGTH_FRAC,
    rear_max_speed_px_s: float = DEFAULT_REAR_MAX_SPEED_PX_S,
    rear_min_angle_deg: float = DEFAULT_REAR_MIN_ANGLE_DEG,
    rear_require_near_wall: bool = DEFAULT_REAR_REQUIRE_NEAR_WALL,
    rear_min_frames: int = DEFAULT_REAR_MIN_FRAMES,
    thigmotaxis_band_px: float = DEFAULT_THIGMOTAXIS_BAND_PX,
    interpolate_gaps: bool = DEFAULT_INTERPOLATE_GAPS,
    max_gap_frames: int = DEFAULT_MAX_GAP_FRAMES,
    trace_smooth: bool = DEFAULT_TRACE_SMOOTH,
    trace_smooth_window: int = DEFAULT_TRACE_SMOOTH_WINDOW,
) -> RunningMetricSeries:
    """Return running counters aligned to the pose frame index."""
    n = len(xy)
    if len(likelihood) != n:
        raise ValueError("xy and likelihood length mismatch")
    if fps <= 0:
        raise ValueError(f"fps must be positive, got {fps}")

    xy_p, trusted, interpolated = prepare_of_track(
        xy,
        likelihood,
        likelihood_min=likelihood_min,
        interpolate_gaps=interpolate_gaps,
        max_gap_frames=max_gap_frames,
        trace_smooth=trace_smooth,
        trace_smooth_window=trace_smooth_window,
    )
    speed = frame_speeds_px_s(xy_p, trusted, fps)
    _, step = path_and_steps(xy_p, trusted)
    moving = moving_mask(
        step,
        trusted,
        fps=fps,
        start_speed_px_s=move_start_speed_px_s,
        stop_speed_px_s=move_stop_speed_px_s,
        entry_debounce_frames=move_entry_debounce_frames,
        exit_debounce_frames=move_exit_debounce_frames,
        speed_median_window_frames=move_speed_median_window,
        min_bout_frames=min_bout_frames,
        inter_bout_gap_frames=inter_bout_gap_frames,
        immobile_speed_px_s=immobile_speed_px_s,
    )

    path_run = np.full(n, np.nan, dtype=np.float64)
    max_bout_run = np.full(n, np.nan, dtype=np.float64)
    move_dur = np.full(n, np.nan, dtype=np.float64)
    frac_move = np.full(n, np.nan, dtype=np.float64)
    meander_run = np.full(n, np.nan, dtype=np.float64)
    mean_speed = np.full(n, np.nan, dtype=np.float64)
    rear_count = np.full(n, np.nan, dtype=np.float64)
    rear_active = np.zeros(n, dtype=bool)
    body_length_frac = np.full(n, np.nan, dtype=np.float64)
    nct_angle = np.full(n, np.nan, dtype=np.float64)

    cum_path = 0.0
    best_bout = 0.0
    bout_len = 0.0
    bout_frames = 0
    move_frames = 0
    turn_deg = 0.0
    meander_path = 0.0
    prev_heading: float | None = None

    for i in range(n):
        if np.isfinite(step[i]):
            cum_path += float(step[i])
        if moving[i]:
            move_frames += 1
            if np.isfinite(step[i]):
                bout_len += float(step[i])
            bout_frames += 1
            best_bout = max(best_bout, bout_len)
        else:
            bout_len = 0.0
            bout_frames = 0

        if trusted[i] and i > 0 and trusted[i - 1] and np.isfinite(step[i]) and step[i] > 0:
            delta = xy_p[i] - xy_p[i - 1]
            heading = float(np.degrees(np.arctan2(delta[1], delta[0])))
            meander_path += float(step[i])
            if prev_heading is not None:
                d = heading - prev_heading
                while d > 180.0:
                    d -= 360.0
                while d < -180.0:
                    d += 360.0
                turn_deg += abs(d)
            prev_heading = heading
        elif not (trusted[i] and np.isfinite(step[i]) and step[i] > 0):
            if not trusted[i]:
                prev_heading = None

        elapsed = (i + 1) / fps
        path_run[i] = cum_path
        max_bout_run[i] = best_bout
        move_dur[i] = move_frames / fps
        frac_move[i] = move_frames / (i + 1)
        mean_speed[i] = cum_path / elapsed if elapsed > 0 else float("nan")
        if meander_path > 0:
            meander_run[i] = turn_deg / meander_path
        elif trusted[: i + 1].any():
            meander_run[i] = 0.0

    if nose_xy is not None and tail_xy is not None and nose_likelihood is not None and tail_likelihood is not None:
        nose_p, nose_ok, _ = prepare_of_track(
            nose_xy,
            nose_likelihood,
            likelihood_min=likelihood_min,
            interpolate_gaps=interpolate_gaps,
            max_gap_frames=max_gap_frames,
            trace_smooth=trace_smooth,
            trace_smooth_window=trace_smooth_window,
        )
        tail_p, tail_ok, _ = prepare_of_track(
            tail_xy,
            tail_likelihood,
            likelihood_min=likelihood_min,
            interpolate_gaps=interpolate_gaps,
            max_gap_frames=max_gap_frames,
            trace_smooth=trace_smooth,
            trace_smooth_window=trace_smooth_window,
        )
        part_ok = nose_ok & tail_ok & trusted
        length = np.full(n, np.nan, dtype=np.float64)
        for i in range(n):
            if not part_ok[i]:
                continue
            if not (np.isfinite(nose_p[i]).all() and np.isfinite(tail_p[i]).all()):
                continue
            length[i] = float(np.linalg.norm(nose_p[i] - tail_p[i]))
        finite = length[np.isfinite(length)]
        median = float(np.median(finite)) if finite.size else float("nan")
        if np.isfinite(median) and median > 0:
            body_length_frac = length / median
        nct_angle = nose_center_tail_angle_deg(nose_p, xy_p, tail_p, part_ok)

        wall_gate = rear_require_near_wall and floor_vertices_xy is not None
        candidate, med = rear_proxy_frame_mask(
            nose_p,
            tail_p,
            xy_p,
            part_ok,
            speed,
            length_frac=rear_length_frac,
            max_speed_px_s=rear_max_speed_px_s,
            min_angle_deg=rear_min_angle_deg,
            floor_vertices_xy=floor_vertices_xy,
            near_wall_band_px=thigmotaxis_band_px,
            require_near_wall=wall_gate,
        )
        if not np.isfinite(med):
            rear_count[:] = 0.0
        else:
            rear_active[:] = candidate
            completed = 0
            run = 0
            counted_this_run = False
            for i in range(n):
                if candidate[i]:
                    run += 1
                    if run >= rear_min_frames and not counted_this_run:
                        completed += 1
                        counted_this_run = True
                else:
                    run = 0
                    counted_this_run = False
                rear_count[i] = float(completed)

    return RunningMetricSeries(
        path_length_px=path_run,
        max_move_bout_distance_px=max_bout_run,
        move_duration_s=move_dur,
        frac_moving=frac_move,
        meander_deg_per_px=meander_run,
        mean_speed_px_s=mean_speed,
        rear_proxy_count=rear_count,
        moving=moving,
        rear_active=rear_active,
        trusted=trusted,
        interpolated=interpolated,
        center_xy=xy_p,
        center_speed_px_s=speed,
        body_length_frac=body_length_frac,
        nose_center_tail_angle_deg=nct_angle,
    )
