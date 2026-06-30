"""is_moving anchor: pure speed-in → bool-out module (S1, ADR-0002).

Accepts per-frame speed; does not fetch it. Calibration helpers live here too.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class IsMovingParams:
    enter_mps: float
    exit_mps: float
    min_dwell_ms: float


def _min_dwell_frames(fps: float, min_dwell_ms: float) -> int:
    if fps <= 0:
        raise ValueError("fps must be positive")
    if min_dwell_ms < 0:
        raise ValueError("min_dwell_ms must be non-negative")
    return max(1, int(round(float(min_dwell_ms) * float(fps) / 1000.0)))


def speed_mps_from_xy_px(
    xy_px: np.ndarray,
    *,
    fps: float,
    px_per_cm: float,
) -> np.ndarray:
    """Per-frame speed (m/s) from ``(T, 2)`` pixel positions."""
    xy = np.asarray(xy_px, dtype=np.float64)
    if xy.ndim != 2 or xy.shape[1] != 2:
        raise ValueError("xy_px must have shape (T, 2)")
    n = len(xy)
    out = np.zeros(n, dtype=np.float64)
    if n < 2 or fps <= 0 or px_per_cm <= 0:
        return out
    step_px = np.linalg.norm(np.diff(xy, axis=0), axis=1)
    m_per_px = 1.0 / (px_per_cm * 100.0)
    out[1:] = step_px * m_per_px * float(fps)
    return out


def is_moving(
    speed_mps: np.ndarray,
    *,
    fps: float,
    enter_mps: float,
    exit_mps: float,
    min_dwell_ms: float,
    valid: np.ndarray | None = None,
) -> np.ndarray:
    """Binary per-frame anchor from speed with hysteresis and ms-based debounce."""
    speed = np.asarray(speed_mps, dtype=np.float64).ravel()
    n = len(speed)
    if float(enter_mps) <= float(exit_mps):
        raise ValueError("enter_mps must be greater than exit_mps for hysteresis")
    dwell_frames = _min_dwell_frames(fps, min_dwell_ms)

    if valid is None:
        valid_mask = np.ones(n, dtype=bool)
    else:
        valid_mask = np.asarray(valid, dtype=bool).ravel()
        if len(valid_mask) != n:
            raise ValueError("valid must match speed length")

    out = np.zeros(n, dtype=bool)
    moving = False
    above_count = 0
    below_count = 0
    pending_start: int | None = None

    for i, spd in enumerate(speed):
        if not valid_mask[i]:
            out[i] = False
            moving = False
            above_count = 0
            below_count = 0
            pending_start = None
            continue

        if not moving:
            if spd >= enter_mps:
                above_count += 1
                if pending_start is None:
                    pending_start = i
                if above_count >= dwell_frames:
                    moving = True
                    start = pending_start if pending_start is not None else i
                    out[start : i + 1] = True
                    above_count = 0
                    below_count = 0
                    pending_start = None
            else:
                above_count = 0
                pending_start = None
        else:
            out[i] = True
            if spd <= exit_mps:
                below_count += 1
                if below_count >= dwell_frames:
                    stop_start = i - dwell_frames + 1
                    out[stop_start : i + 1] = False
                    moving = False
                    below_count = 0
            else:
                below_count = 0

    return out


def speed_histogram_antimode(
    speed_mps: np.ndarray,
    *,
    valid: np.ndarray | None = None,
    n_bins: int = 64,
) -> tuple[float, float]:
    """Return ``(enter_mps, exit_mps)`` from a speed histogram valley (antimode)."""
    speed = np.asarray(speed_mps, dtype=np.float64).ravel()
    if valid is not None:
        mask = np.asarray(valid, dtype=bool).ravel()
        if len(mask) != len(speed):
            raise ValueError("valid must match speed length")
        speed = speed[mask]
    speed = speed[np.isfinite(speed) & (speed >= 0)]
    if len(speed) < 10:
        raise ValueError("need at least 10 finite speed samples for antimode calibration")

    hi = float(np.percentile(speed, 99))
    if hi <= 0:
        hi = float(speed.max()) or 1.0
    counts, edges = np.histogram(speed, bins=n_bins, range=(0.0, hi))
    smoothed = np.convolve(counts.astype(np.float64), np.ones(3) / 3.0, mode="same")
    peak_lo = int(np.argmax(smoothed[: n_bins // 2]))
    peak_hi = int(n_bins // 2 + np.argmax(smoothed[n_bins // 2 :]))
    if peak_hi <= peak_lo + 1:
        mid = float(np.median(speed))
        return (mid * 1.5, mid * 0.5)

    valley = int(peak_lo + 1 + np.argmin(smoothed[peak_lo + 1 : peak_hi]))
    valley = int(np.clip(valley, 1, n_bins - 2))
    antimode = float(0.5 * (edges[valley] + edges[valley + 1]))
    band = max(antimode * 0.25, 0.01)
    return (antimode + band, max(0.0, antimode - band))


def calibrate_min_dwell_ms(
    speed_mps: np.ndarray,
    params: IsMovingParams,
    *,
    fps: float,
    candidates_ms: tuple[float, ...] | list[float],
) -> float:
    """Pick dwell minimizing state-transition count among candidates."""
    if not candidates_ms:
        raise ValueError("candidates_ms must be non-empty")
    speed = np.asarray(speed_mps, dtype=np.float64).ravel()
    best_ms = float(candidates_ms[0])
    best_score = float("inf")
    raw = speed >= params.enter_mps
    for ms in candidates_ms:
        mask = is_moving(
            speed,
            fps=fps,
            enter_mps=params.enter_mps,
            exit_mps=params.exit_mps,
            min_dwell_ms=float(ms),
        )
        transitions = int(np.sum(mask[1:] != mask[:-1])) if len(mask) > 1 else 0
        # Penalize large drift from raw threshold moving fraction.
        drift = abs(float(mask.mean()) - float(raw.mean()))
        score = transitions + 50.0 * drift
        if score < best_score:
            best_score = score
            best_ms = float(ms)
    return best_ms


def calibrate_is_moving_params(
    speed_mps: np.ndarray,
    *,
    fps: float,
    dwell_candidates_ms: tuple[float, ...] | list[float] = (50.0, 100.0, 150.0, 200.0, 300.0),
    valid: np.ndarray | None = None,
) -> IsMovingParams:
    """Calibrate enter/exit from antimode and dwell via sweep."""
    enter, exit_ = speed_histogram_antimode(speed_mps, valid=valid)
    base = IsMovingParams(enter_mps=enter, exit_mps=exit_, min_dwell_ms=0.0)
    dwell = calibrate_min_dwell_ms(
        speed_mps,
        base,
        fps=fps,
        candidates_ms=dwell_candidates_ms,
    )
    return IsMovingParams(enter_mps=enter, exit_mps=exit_, min_dwell_ms=dwell)
