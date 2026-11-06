"""Parks / Whitehead open-field frailty scalars (descriptive, bin grain).

The published performance-based eight-item FI is seven open-field trackers plus
body weight ([Parks et al., 2012](https://doi.org/10.1093/gerona/glr193);
[Whitehead et al., 2014](https://doi.org/10.1093/gerona/glt136)). This module
emits the seven video items. ``body_weight_g`` joins later from metadata.

Units stay in pixels until a floor length in cm is declared. Likelihood gates
QC; unfilled pose gaps are not immobility. Short gaps are filled with the OEM
trace helper (``process_xy_trace``) before kinematics. Rearing is a **top-view
proxy**, not EthoVision rearing. Thigmotaxis is kept as an extra column (not
one of the Parks eight). A collapsed FI score waits on reference means / SDs.

Provisional thresholds (must be locked before claiming an FI)::

    likelihood_min                 mouse_center (and rear parts) QC gate
    interpolate_gaps               OEM short-gap linear fill on / off
    max_gap_frames                 max NaN run to interpolate (OEM TRACE_MAX_GAP)
    trace_smooth                   OEM moving-average after interp
    trace_smooth_window            smooth window (frames; odd ≥ 3)
    move_start_speed_px_s          enter-moving hysteresis (OEM-style)
    move_stop_speed_px_s           exit-moving hysteresis (start > stop)
    move_entry_debounce_frames     consecutive above-start frames to enter
    move_exit_debounce_frames      consecutive below-stop frames to exit
    move_speed_median_window       median filter on inbound step before state
    min_bout_frames                drop move bouts shorter than this
    inter_bout_gap_frames          merge move bouts separated by shorter gaps
    rear_length_frac               nose–tail_base ≤ this × median length
    rear_max_speed_px_s            max center translation during rear proxy
    rear_min_angle_deg             min nose–center–tail_base angle (rejects curled grooming)
    rear_require_near_wall         supported-rear prior (EthoVision Wall-zone analogue)
    rear_min_frames                min contiguous frames for one rear bout
    thigmotaxis_band_px            near-wall band (extra column + rear gate)
    px_per_cm                      not a threshold — scale join, still missing
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from maze.pipeline.defaults import (
    TRACE_APPLY_SMOOTHING,
    TRACE_MAX_GAP_FRAMES,
    TRACE_SMOOTHING_WINDOW,
)
from maze.pipeline.open_field.time_bins import TimeBin, equal_width_bins
from maze.pipeline.tracking.trace_processing import TraceProcessingParams, process_xy_trace

DEFAULT_LIKELIHOOD_MIN = 0.6
DEFAULT_INTERPOLATE_GAPS = True
DEFAULT_MAX_GAP_FRAMES = TRACE_MAX_GAP_FRAMES
DEFAULT_TRACE_SMOOTH = TRACE_APPLY_SMOOTHING
DEFAULT_TRACE_SMOOTH_WINDOW = TRACE_SMOOTHING_WINDOW
# Movement hysteresis mirrors maze.pipeline.defaults (start ~2× stop) in px/s.
DEFAULT_MOVE_START_SPEED_PX_S = 8.0
DEFAULT_MOVE_STOP_SPEED_PX_S = 4.0
DEFAULT_MOVE_ENTRY_DEBOUNCE_FRAMES = 3
DEFAULT_MOVE_EXIT_DEBOUNCE_FRAMES = 3
DEFAULT_MOVE_SPEED_MEDIAN_WINDOW = 3
DEFAULT_MIN_BOUT_FRAMES = 4
DEFAULT_INTER_BOUT_GAP_FRAMES = 4
# Backward-compatible alias: old single gate ≈ stop threshold.
DEFAULT_IMMOBILE_SPEED_PX_S = DEFAULT_MOVE_STOP_SPEED_PX_S
DEFAULT_REAR_LENGTH_FRAC = 0.75
DEFAULT_REAR_MAX_SPEED_PX_S = 15.0
DEFAULT_REAR_MIN_ANGLE_DEG = 160.0
DEFAULT_REAR_REQUIRE_NEAR_WALL = True
DEFAULT_REAR_MIN_FRAMES = 3
DEFAULT_THIGMOTAXIS_BAND_PX = 40.0


@dataclass(frozen=True)
class BinFeatures:
    """One session-bin row. Parks OF items first; weight omitted; thigmotaxis extra."""

    video_id: str
    bin_index: int
    t0_s: float
    t1_s: float
    bin_width_s: float
    n_frames: int
    n_trusted: int
    # Parks / Whitehead #1–7 (px until scale; rearing = proxy)
    path_length_px: float
    max_move_bout_distance_px: float
    move_duration_s: float
    frac_moving: float
    meander_deg_per_px: float
    mean_speed_px_s: float
    rear_proxy_count: float
    # Convenience / QC cousins (not Parks #8)
    mean_active_speed_px_s: float
    immobility_frac: float
    thigmotaxis_frac: float
    frac_interpolated: float

    def as_dict(self) -> dict:
        return asdict(self)


def _nan_row(
    *,
    video_id: str,
    bin_: TimeBin,
    bin_width_s: float,
    n_frames: int = 0,
    n_trusted: int = 0,
) -> BinFeatures:
    nan = float("nan")
    return BinFeatures(
        video_id=video_id,
        bin_index=bin_.bin_index,
        t0_s=bin_.t0_s,
        t1_s=bin_.t1_s,
        bin_width_s=bin_width_s,
        n_frames=n_frames,
        n_trusted=n_trusted,
        path_length_px=nan,
        max_move_bout_distance_px=nan,
        move_duration_s=nan,
        frac_moving=nan,
        meander_deg_per_px=nan,
        mean_speed_px_s=nan,
        rear_proxy_count=nan,
        mean_active_speed_px_s=nan,
        immobility_frac=nan,
        thigmotaxis_frac=nan,
        frac_interpolated=nan,
    )


def prepare_of_track(
    xy: np.ndarray,
    likelihood: np.ndarray,
    *,
    likelihood_min: float = DEFAULT_LIKELIHOOD_MIN,
    interpolate_gaps: bool = DEFAULT_INTERPOLATE_GAPS,
    max_gap_frames: int = DEFAULT_MAX_GAP_FRAMES,
    trace_smooth: bool = DEFAULT_TRACE_SMOOTH,
    trace_smooth_window: int = DEFAULT_TRACE_SMOOTH_WINDOW,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Likelihood-gate then OEM ``process_xy_trace`` (short-gap fill ± smooth).

    Returns ``(xy_out, trusted_out, interpolated)`` where ``interpolated`` marks
    frames that were below ``likelihood_min`` (or non-finite) before fill and
    became trusted after. Unfilled long gaps stay untrusted and are not
    immobility.
    """
    points = np.asarray(xy, dtype=np.float64)
    raw_ok = trusted_mask(likelihood, likelihood_min)
    if points.shape != (len(raw_ok), 2):
        raise ValueError(f"xy must be (T, 2) aligned with likelihood, got {points.shape}")

    if not interpolate_gaps and not trace_smooth:
        return points.copy(), raw_ok.copy(), np.zeros(len(raw_ok), dtype=bool)

    params = TraceProcessingParams(
        interpolate_nans=bool(interpolate_gaps),
        max_gap_frames=max(0, int(max_gap_frames)),
        interpolate_low_conf=False,
        apply_smoothing=bool(trace_smooth),
        smoothing_window=max(1, int(trace_smooth_window)),
    )
    xy_out, trusted_out = process_xy_trace(points, raw_ok, score=None, params=params)
    interpolated = trusted_out & ~raw_ok
    return xy_out, trusted_out, interpolated


def point_to_segment_distance(point: np.ndarray, a: np.ndarray, b: np.ndarray) -> float:
    """Shortest distance from ``point`` to the closed segment ``a``–``b``."""
    ab = b - a
    denom = float(np.dot(ab, ab))
    if denom <= 0:
        return float(np.linalg.norm(point - a))
    t = float(np.clip(np.dot(point - a, ab) / denom, 0.0, 1.0))
    return float(np.linalg.norm(point - (a + t * ab)))


def distance_to_quad_edge(xy: np.ndarray, vertices_xy: np.ndarray) -> np.ndarray:
    """Per-row distance from each point to the nearest edge of a closed quadrilateral."""
    vertices = np.asarray(vertices_xy, dtype=np.float64)
    if vertices.shape != (4, 2):
        raise ValueError(f"vertices_xy must have shape (4, 2), got {vertices.shape}")
    points = np.asarray(xy, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError(f"xy must have shape (T, 2), got {points.shape}")
    edges = [(vertices[i], vertices[(i + 1) % 4]) for i in range(4)]
    out = np.empty(len(points), dtype=np.float64)
    for i, point in enumerate(points):
        if not np.isfinite(point).all():
            out[i] = np.nan
            continue
        out[i] = min(point_to_segment_distance(point, a, b) for a, b in edges)
    return out


def trusted_mask(likelihood: np.ndarray, likelihood_min: float) -> np.ndarray:
    lik = np.asarray(likelihood, dtype=np.float64)
    return np.isfinite(lik) & (lik >= likelihood_min)


def frame_speeds_px_s(xy: np.ndarray, trusted: np.ndarray, fps: float) -> np.ndarray:
    """Per-frame speed onto this frame from the previous frame (px/s).

    Only consecutive trusted frames contribute. Gaps stay NaN (not immobility).
    """
    if fps <= 0:
        raise ValueError(f"fps must be positive, got {fps}")
    points = np.asarray(xy, dtype=np.float64)
    mask = np.asarray(trusted, dtype=bool)
    n = len(points)
    if len(mask) != n:
        raise ValueError("xy and trusted must have the same length")
    speed = np.full(n, np.nan, dtype=np.float64)
    for i in range(1, n):
        if not (mask[i] and mask[i - 1]):
            continue
        speed[i] = float(np.linalg.norm(points[i] - points[i - 1]) * fps)
    return speed


def _median_filter_1d(values: np.ndarray, window: int) -> np.ndarray:
    """Odd-window median filter with edge padding (NaNs stay NaN)."""
    window = max(1, int(window))
    if window <= 1 or len(values) == 0:
        return values.copy()
    if window % 2 == 0:
        window += 1
    pad = window // 2
    padded = np.pad(values.astype(np.float64), (pad, pad), mode="edge")
    out = np.empty_like(values, dtype=np.float64)
    for i in range(len(values)):
        chunk = padded[i : i + window]
        finite = chunk[np.isfinite(chunk)]
        out[i] = float(np.median(finite)) if finite.size else np.nan
    return out


def moving_mask(
    step_px: np.ndarray,
    trusted: np.ndarray,
    *,
    fps: float,
    start_speed_px_s: float = DEFAULT_MOVE_START_SPEED_PX_S,
    stop_speed_px_s: float = DEFAULT_MOVE_STOP_SPEED_PX_S,
    entry_debounce_frames: int = DEFAULT_MOVE_ENTRY_DEBOUNCE_FRAMES,
    exit_debounce_frames: int = DEFAULT_MOVE_EXIT_DEBOUNCE_FRAMES,
    speed_median_window_frames: int = DEFAULT_MOVE_SPEED_MEDIAN_WINDOW,
    min_bout_frames: int = DEFAULT_MIN_BOUT_FRAMES,
    inter_bout_gap_frames: int = DEFAULT_INTER_BOUT_GAP_FRAMES,
    immobile_speed_px_s: float | None = None,
) -> np.ndarray:
    """Per-frame moving state with OEM-style start/stop hysteresis + debounce.

    Frame 0 never has an inbound step, so it is never marked moving. A bout's
    path is the sum of inbound steps on moving frames (Parks #2).

    If ``immobile_speed_px_s`` is passed (legacy), it sets ``stop_speed_px_s``
    and ``start_speed_px_s = 2 * stop`` when start was left at the default.
    """
    if fps <= 0:
        raise ValueError(f"fps must be positive, got {fps}")
    step = np.asarray(step_px, dtype=np.float64)
    trust = np.asarray(trusted, dtype=bool)
    n = len(step)
    if len(trust) != n:
        raise ValueError("step_px and trusted must have the same length")

    stop = float(stop_speed_px_s)
    start = float(start_speed_px_s)
    if immobile_speed_px_s is not None:
        stop = float(immobile_speed_px_s)
        if abs(start - DEFAULT_MOVE_START_SPEED_PX_S) < 1e-12:
            start = 2.0 * stop
    if start < stop:
        raise ValueError(f"start_speed_px_s ({start}) must be >= stop_speed_px_s ({stop})")

    start_step = start / fps
    stop_step = stop / fps
    filtered = _median_filter_1d(step, speed_median_window_frames)

    entry_n = max(1, int(entry_debounce_frames))
    exit_n = max(1, int(exit_debounce_frames))

    # State machine on inbound steps (indices 1..n-1); frame 0 stays False.
    raw = np.zeros(n, dtype=bool)
    currently_moving = False
    above_start = 0
    below_stop = 0
    pending_start: int | None = None

    for i in range(1, n):
        if not (trust[i] and trust[i - 1] and np.isfinite(filtered[i])):
            raw[i] = False
            currently_moving = False
            above_start = 0
            below_stop = 0
            pending_start = None
            continue

        dist = float(filtered[i])
        if not currently_moving:
            if dist >= start_step:
                above_start += 1
                if pending_start is None:
                    pending_start = i
                if above_start >= entry_n:
                    currently_moving = True
                    start_idx = pending_start if pending_start is not None else i
                    raw[start_idx : i + 1] = True
                    above_start = 0
                    pending_start = None
            else:
                above_start = 0
                pending_start = None
        else:
            raw[i] = True
            if dist <= stop_step:
                below_stop += 1
                if below_stop >= exit_n:
                    stop_run_start = i - exit_n + 1
                    raw[stop_run_start : i + 1] = False
                    currently_moving = False
                    below_stop = 0
            else:
                below_stop = 0

    # Contiguous raw bouts → min duration → merge short gaps.
    bouts: list[tuple[int, int]] = []
    in_bout = False
    bout_start = 0
    for i, moving in enumerate(raw):
        if moving and not in_bout:
            in_bout = True
            bout_start = i
        elif not moving and in_bout:
            bouts.append((bout_start, i))
            in_bout = False
    if in_bout:
        bouts.append((bout_start, n))

    min_frames = max(1, int(min_bout_frames))
    bouts = [(a, b) for a, b in bouts if (b - a) >= min_frames]

    gap_n = max(0, int(inter_bout_gap_frames))
    if len(bouts) > 1 and gap_n > 0:
        merged = [bouts[0]]
        for a, b in bouts[1:]:
            prev_a, prev_b = merged[-1]
            if a - prev_b < gap_n:
                merged[-1] = (prev_a, b)
            else:
                merged.append((a, b))
        bouts = merged

    out = np.zeros(n, dtype=bool)
    for a, b in bouts:
        out[a:b] = True
    return out


def path_and_steps(xy: np.ndarray, trusted: np.ndarray) -> tuple[float, np.ndarray]:
    """Adjacent-trusted step lengths (px) and their sum."""
    points = np.asarray(xy, dtype=np.float64)
    trust = np.asarray(trusted, dtype=bool)
    step = np.full(len(points), np.nan, dtype=np.float64)
    for i in range(1, len(points)):
        if trust[i] and trust[i - 1]:
            step[i] = float(np.linalg.norm(points[i] - points[i - 1]))
    finite = step[np.isfinite(step)]
    if trust.any() and finite.size == 0:
        return 0.0, step
    if finite.size == 0:
        return float("nan"), step
    return float(np.sum(finite)), step


def max_move_bout_distance(step_px: np.ndarray, moving: np.ndarray, *, min_bout_frames: int) -> float:
    """Longest path length inside a contiguous run of moving frames (Parks #2)."""
    move = np.asarray(moving, dtype=bool)
    step = np.asarray(step_px, dtype=np.float64)
    if move.size == 0:
        return float("nan")
    best = 0.0
    found = False
    i = 0
    n = len(move)
    while i < n:
        if not move[i]:
            i += 1
            continue
        j = i
        while j < n and move[j]:
            j += 1
        if (j - i) >= min_bout_frames:
            bout = step[i:j]
            bout = bout[np.isfinite(bout)]
            found = True
            best = max(best, float(np.sum(bout)) if bout.size else 0.0)
        i = j
    return best if found else 0.0


def meander_deg_per_px(xy: np.ndarray, trusted: np.ndarray, step_px: np.ndarray) -> float:
    """Sum of absolute heading changes (deg) divided by path length (px). Parks #5."""
    points = np.asarray(xy, dtype=np.float64)
    trust = np.asarray(trusted, dtype=bool)
    step = np.asarray(step_px, dtype=np.float64)
    headings: list[float] = []
    path = 0.0
    for i in range(1, len(points)):
        if not (trust[i] and trust[i - 1] and np.isfinite(step[i]) and step[i] > 0):
            continue
        delta = points[i] - points[i - 1]
        headings.append(float(np.degrees(np.arctan2(delta[1], delta[0]))))
        path += float(step[i])
    if path <= 0 or len(headings) < 2:
        return 0.0 if path == 0 and trust.any() else float("nan")
    turn = 0.0
    for a, b in zip(headings[:-1], headings[1:]):
        d = b - a
        while d > 180.0:
            d -= 360.0
        while d < -180.0:
            d += 360.0
        turn += abs(d)
    return float(turn / path)


def nose_center_tail_angle_deg(
    nose_xy: np.ndarray,
    center_xy: np.ndarray,
    tail_xy: np.ndarray,
    trusted: np.ndarray,
) -> np.ndarray:
    """Interior angle at ``mouse_center`` between nose and ``tail_base`` (degrees).

    ~180° = colinear head–body–tail (stretched). Curled grooming poses drop well
    below that. Returns NaN when any point is untrusted or a leg is degenerate.
    """
    nose = np.asarray(nose_xy, dtype=np.float64)
    center = np.asarray(center_xy, dtype=np.float64)
    tail = np.asarray(tail_xy, dtype=np.float64)
    ok = np.asarray(trusted, dtype=bool)
    n = len(center)
    if not (len(nose) == n and len(tail) == n and len(ok) == n):
        raise ValueError("nose, center, tail, and trust masks must align")
    out = np.full(n, np.nan, dtype=np.float64)
    eps = 1e-9
    for i in range(n):
        if not ok[i]:
            continue
        if not (
            np.isfinite(nose[i]).all()
            and np.isfinite(center[i]).all()
            and np.isfinite(tail[i]).all()
        ):
            continue
        vn = nose[i] - center[i]
        vt = tail[i] - center[i]
        ln = float(np.linalg.norm(vn))
        lt = float(np.linalg.norm(vt))
        if ln < eps or lt < eps:
            continue
        cos = float(np.dot(vn, vt) / (ln * lt))
        cos = float(np.clip(cos, -1.0, 1.0))
        out[i] = float(np.degrees(np.arccos(cos)))
    return out


def rear_proxy_frame_mask(
    nose_xy: np.ndarray,
    tail_xy: np.ndarray,
    center_xy: np.ndarray,
    part_trusted: np.ndarray,
    speed_px_s: np.ndarray,
    *,
    length_frac: float,
    max_speed_px_s: float,
    min_angle_deg: float = DEFAULT_REAR_MIN_ANGLE_DEG,
    floor_vertices_xy: np.ndarray | None = None,
    near_wall_band_px: float = DEFAULT_THIGMOTAXIS_BAND_PX,
    require_near_wall: bool = DEFAULT_REAR_REQUIRE_NEAR_WALL,
) -> tuple[np.ndarray, float]:
    """Per-frame rear-proxy candidates plus session median nose–tail length.

    Gates (all required when enabled)::

        short body          nose–tail_base ≤ length_frac × median
        slow center         mouse_center speed ≤ max_speed_px_s
        open angle          nose–center–tail_base ≥ min_angle_deg
                            (rejects curled grooming; default 160°)
        near wall           optional; EthoVision-style supported-rear prior

    EthoVision Behavior Recognition separates **Grooming**, **Rearing
    supported**, and **Rearing unsupported** as distinct learned classes — not
    via elongation alone. This proxy is still not BR.
    """
    nose = np.asarray(nose_xy, dtype=np.float64)
    tail = np.asarray(tail_xy, dtype=np.float64)
    center = np.asarray(center_xy, dtype=np.float64)
    ok = np.asarray(part_trusted, dtype=bool)
    speed = np.asarray(speed_px_s, dtype=np.float64)
    if len(nose) != len(tail) or len(nose) != len(ok) or len(center) != len(ok):
        raise ValueError("nose, tail, center, and trust masks must align")
    n = len(nose)
    length = np.full(n, np.nan, dtype=np.float64)
    for i in range(n):
        if not ok[i]:
            continue
        if not (np.isfinite(nose[i]).all() and np.isfinite(tail[i]).all()):
            continue
        length[i] = float(np.linalg.norm(nose[i] - tail[i]))
    finite = length[np.isfinite(length)]
    if finite.size == 0:
        return np.zeros(n, dtype=bool), float("nan")
    median = float(np.median(finite))
    if median <= 0:
        return np.zeros(n, dtype=bool), float("nan")

    short = np.isfinite(length) & (length <= length_frac * median)
    slow = ~np.isfinite(speed) | (speed <= max_speed_px_s)
    angle = nose_center_tail_angle_deg(nose, center, tail, ok)
    open_angle = np.isfinite(angle) & (angle >= min_angle_deg)

    near_wall = np.ones(n, dtype=bool)
    if require_near_wall:
        if floor_vertices_xy is None:
            near_wall[:] = False
        else:
            dist = distance_to_quad_edge(nose, floor_vertices_xy)
            # Prefer nose near wall (supported rear); fall back to midpoint.
            mid = 0.5 * (nose + tail)
            dist_mid = distance_to_quad_edge(mid, floor_vertices_xy)
            near = np.isfinite(dist) & (dist <= near_wall_band_px)
            near |= np.isfinite(dist_mid) & (dist_mid <= near_wall_band_px)
            near_wall = near

    candidate = short & slow & open_angle & near_wall & ok
    return candidate, median


def rear_proxy_count(
    nose_xy: np.ndarray,
    tail_xy: np.ndarray,
    center_xy: np.ndarray,
    part_trusted: np.ndarray,
    speed_px_s: np.ndarray,
    *,
    length_frac: float,
    max_speed_px_s: float,
    min_frames: int,
    min_angle_deg: float = DEFAULT_REAR_MIN_ANGLE_DEG,
    floor_vertices_xy: np.ndarray | None = None,
    near_wall_band_px: float = DEFAULT_THIGMOTAXIS_BAND_PX,
    require_near_wall: bool = DEFAULT_REAR_REQUIRE_NEAR_WALL,
) -> float:
    """Count top-view rear-like bouts (provisional; see ``rear_proxy_frame_mask``)."""
    ok = np.asarray(part_trusted, dtype=bool)
    candidate, median = rear_proxy_frame_mask(
        nose_xy,
        tail_xy,
        center_xy,
        part_trusted,
        speed_px_s,
        length_frac=length_frac,
        max_speed_px_s=max_speed_px_s,
        min_angle_deg=min_angle_deg,
        floor_vertices_xy=floor_vertices_xy,
        near_wall_band_px=near_wall_band_px,
        require_near_wall=require_near_wall,
    )
    if not np.isfinite(median):
        return 0.0 if ok.any() else float("nan")
    count = 0
    i = 0
    n = len(candidate)
    while i < n:
        if not candidate[i]:
            i += 1
            continue
        j = i
        while j < n and candidate[j]:
            j += 1
        if (j - i) >= min_frames:
            count += 1
        i = j
    return float(count)


def frames_in_bin(n_total: int, fps: float, bin_: TimeBin, duration_s: float) -> np.ndarray:
    t = np.arange(n_total, dtype=np.float64) / fps
    in_bin = (t >= bin_.t0_s) & (t < bin_.t1_s)
    if abs(bin_.t1_s - duration_s) <= 1e-9:
        in_bin = (t >= bin_.t0_s) & (t <= bin_.t1_s + 1e-9)
    return np.flatnonzero(in_bin)


def summarize_bin(
    *,
    video_id: str,
    bin_: TimeBin,
    bin_width_s: float,
    xy: np.ndarray,
    likelihood: np.ndarray,
    fps: float,
    duration_s: float,
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
) -> BinFeatures:
    """Parks OF scalars on frames in the bin; session-end bin includes the last frame."""
    n_total = len(xy)
    if len(likelihood) != n_total:
        raise ValueError("xy and likelihood length mismatch")
    idx = frames_in_bin(n_total, fps, bin_, duration_s)
    if idx.size == 0:
        return _nan_row(video_id=video_id, bin_=bin_, bin_width_s=bin_width_s)

    # Full-session prep so short gaps can use flanks outside this bin.
    xy_p, trusted_full, interp_full = prepare_of_track(
        xy,
        likelihood,
        likelihood_min=likelihood_min,
        interpolate_gaps=interpolate_gaps,
        max_gap_frames=max_gap_frames,
        trace_smooth=trace_smooth,
        trace_smooth_window=trace_smooth_window,
    )
    xy_b = xy_p[idx]
    trusted = trusted_full[idx]
    interpolated = interp_full[idx]
    speed_full = frame_speeds_px_s(xy_p, trusted_full, fps)
    speed_b = speed_full[idx]

    path, step = path_and_steps(xy_b, trusted)
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
    bin_dur = max(bin_.t1_s - bin_.t0_s, 0.0)
    move_frames = int(moving.sum())
    move_duration = move_frames / fps
    frac_moving = float(move_duration / bin_dur) if bin_dur > 0 else float("nan")
    # Immobility among frames with a defined inbound step.
    scored = trusted & np.isfinite(step)
    if scored.any():
        immobile = float(np.mean(~moving[scored]))
    else:
        immobile = float("nan")

    finite_speed = speed_b[moving & np.isfinite(speed_b)]
    mean_active = float(np.mean(finite_speed)) if finite_speed.size else float("nan")
    # Parks #6 "average velocity … over" the trial ≈ path / wall-clock duration.
    mean_speed = float(path / bin_dur) if bin_dur > 0 and np.isfinite(path) else float("nan")

    # Bout length already enforced inside moving_mask; keep min_bout_frames=1 here.
    max_bout = max_move_bout_distance(step, moving, min_bout_frames=1)
    meander = meander_deg_per_px(xy_b, trusted, step)
    frac_interp = float(np.mean(interpolated)) if interpolated.size else float("nan")

    if nose_xy is None or tail_xy is None or nose_likelihood is None or tail_likelihood is None:
        rear = float("nan")
    else:
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
        part_ok = nose_ok[idx] & tail_ok[idx] & trusted
        rear = rear_proxy_count(
            nose_p[idx],
            tail_p[idx],
            xy_b,
            part_ok,
            speed_b,
            length_frac=rear_length_frac,
            max_speed_px_s=rear_max_speed_px_s,
            min_frames=rear_min_frames,
            min_angle_deg=rear_min_angle_deg,
            floor_vertices_xy=floor_vertices_xy,
            near_wall_band_px=thigmotaxis_band_px,
            require_near_wall=rear_require_near_wall,
        )

    if floor_vertices_xy is None or not trusted.any():
        thigmo = float("nan")
    else:
        dist = distance_to_quad_edge(xy_b[trusted], floor_vertices_xy)
        thigmo = float(np.mean(dist <= thigmotaxis_band_px)) if dist.size else float("nan")

    return BinFeatures(
        video_id=video_id,
        bin_index=bin_.bin_index,
        t0_s=bin_.t0_s,
        t1_s=bin_.t1_s,
        bin_width_s=bin_width_s,
        n_frames=int(idx.size),
        n_trusted=int(trusted.sum()),
        path_length_px=path,
        max_move_bout_distance_px=max_bout,
        move_duration_s=move_duration,
        frac_moving=frac_moving,
        meander_deg_per_px=meander,
        mean_speed_px_s=mean_speed,
        rear_proxy_count=rear,
        mean_active_speed_px_s=mean_active,
        immobility_frac=immobile,
        thigmotaxis_frac=thigmo,
        frac_interpolated=frac_interp,
    )


def feature_rows_for_video(
    *,
    video_id: str,
    xy: np.ndarray,
    likelihood: np.ndarray,
    fps: float,
    duration_s: float,
    bin_width_s: float,
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
) -> list[BinFeatures]:
    bins = equal_width_bins(duration_s, bin_width_s)
    # Prep once per video (full-session flanks); summarize_bin would redo per bin.
    xy_p, trusted_p, interp_p = prepare_of_track(
        xy,
        likelihood,
        likelihood_min=likelihood_min,
        interpolate_gaps=interpolate_gaps,
        max_gap_frames=max_gap_frames,
        trace_smooth=trace_smooth,
        trace_smooth_window=trace_smooth_window,
    )
    # Encode trust in likelihood so summarize_bin can skip a second prep when
    # interpolate_gaps/trace_smooth are both False on already-prepared tracks.
    lik_p = np.where(trusted_p, 1.0, 0.0)
    nose_p = nose_xy
    nose_lik_p = nose_likelihood
    tail_p = tail_xy
    tail_lik_p = tail_likelihood
    if nose_xy is not None and nose_likelihood is not None:
        nose_p, nose_ok, _ = prepare_of_track(
            nose_xy,
            nose_likelihood,
            likelihood_min=likelihood_min,
            interpolate_gaps=interpolate_gaps,
            max_gap_frames=max_gap_frames,
            trace_smooth=trace_smooth,
            trace_smooth_window=trace_smooth_window,
        )
        nose_lik_p = np.where(nose_ok, 1.0, 0.0)
    if tail_xy is not None and tail_likelihood is not None:
        tail_p, tail_ok, _ = prepare_of_track(
            tail_xy,
            tail_likelihood,
            likelihood_min=likelihood_min,
            interpolate_gaps=interpolate_gaps,
            max_gap_frames=max_gap_frames,
            trace_smooth=trace_smooth,
            trace_smooth_window=trace_smooth_window,
        )
        tail_lik_p = np.where(tail_ok, 1.0, 0.0)

    rows: list[BinFeatures] = []
    for bin_ in bins:
        row = summarize_bin(
            video_id=video_id,
            bin_=bin_,
            bin_width_s=bin_width_s,
            xy=xy_p,
            likelihood=lik_p,
            fps=fps,
            duration_s=duration_s,
            nose_xy=nose_p,
            tail_xy=tail_p,
            nose_likelihood=nose_lik_p,
            tail_likelihood=tail_lik_p,
            floor_vertices_xy=floor_vertices_xy,
            likelihood_min=likelihood_min,
            move_start_speed_px_s=move_start_speed_px_s,
            move_stop_speed_px_s=move_stop_speed_px_s,
            move_entry_debounce_frames=move_entry_debounce_frames,
            move_exit_debounce_frames=move_exit_debounce_frames,
            move_speed_median_window=move_speed_median_window,
            min_bout_frames=min_bout_frames,
            inter_bout_gap_frames=inter_bout_gap_frames,
            immobile_speed_px_s=immobile_speed_px_s,
            rear_length_frac=rear_length_frac,
            rear_max_speed_px_s=rear_max_speed_px_s,
            rear_min_angle_deg=rear_min_angle_deg,
            rear_require_near_wall=rear_require_near_wall,
            rear_min_frames=rear_min_frames,
            thigmotaxis_band_px=thigmotaxis_band_px,
            # Already prepared — avoid double-smoothing / re-interp.
            interpolate_gaps=False,
            max_gap_frames=max_gap_frames,
            trace_smooth=False,
            trace_smooth_window=trace_smooth_window,
        )
        # Restore true gap-fill fraction from the pre-prep mask (bin slice).
        idx = frames_in_bin(len(xy_p), fps, bin_, duration_s)
        if idx.size:
            frac = float(np.mean(interp_p[idx]))
            rows.append(
                BinFeatures(
                    **{**row.as_dict(), "frac_interpolated": frac, "n_trusted": int(trusted_p[idx].sum())}
                )
            )
        else:
            rows.append(row)
    return rows
