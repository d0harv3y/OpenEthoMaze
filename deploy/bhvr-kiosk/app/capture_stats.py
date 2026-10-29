"""SSD write-rate stats for kiosk REC badge (independent of browser LIVE fps)."""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any

_capture_stats_lock = threading.Lock()
CAPTURE_STALL_S = 2.0


def new_capture_byte_stats(*, now: float | None = None) -> dict[str, Any]:
    """Per-cam write counters for kiosk REC badge (not browser LIVE fps)."""
    t = time.monotonic() if now is None else float(now)
    return {
        "bytes": 0,
        "started_mono": t,
        "samples": deque(maxlen=48),  # (mono, cum_bytes)
        "last_write_mono": None,
    }


def note_capture_bytes(
    stats: dict[str, Any], n: int, *, now: float | None = None
) -> None:
    """Record ``n`` bytes just written to ``*_video.ts`` (single writer thread)."""
    t = time.monotonic() if now is None else float(now)
    with _capture_stats_lock:
        stats["bytes"] = int(stats.get("bytes") or 0) + int(n)
        stats["last_write_mono"] = t
        samples = stats.get("samples")
        if not isinstance(samples, deque):
            samples = deque(samples or (), maxlen=48)
            stats["samples"] = samples
        samples.append((t, int(stats["bytes"])))


def snapshot_capture_stats(
    stats: dict[str, Any],
    *,
    soft_fps: int | None = None,
    bitrate_bps: int | None = None,
    now: float | None = None,
    stall_s: float = CAPTURE_STALL_S,
) -> dict[str, Any]:
    """Derive write_Bps / stall / rough est_fps for UI (SSD path, not tile decode)."""
    t = time.monotonic() if now is None else float(now)
    with _capture_stats_lock:
        bytes_total = int(stats.get("bytes") or 0)
        last = stats.get("last_write_mono")
        started = float(stats.get("started_mono") or t)
        samples = list(stats.get("samples") or ())
    age = (t - float(last)) if last is not None else None
    write_bps: float | None = None
    if len(samples) >= 2:
        t0, b0 = samples[0]
        t1, b1 = samples[-1]
        dt = float(t1) - float(t0)
        if dt >= 0.2:
            write_bps = (int(b1) - int(b0)) / dt
    est_fps: float | None = None
    if (
        write_bps is not None
        and bitrate_bps
        and int(bitrate_bps) > 0
        and soft_fps
        and int(soft_fps) > 0
    ):
        expected = float(bitrate_bps) / 8.0
        if expected > 0:
            raw = float(soft_fps) * (write_bps / expected)
            est_fps = round(max(0.0, min(float(soft_fps) * 1.5, raw)), 1)
    age_start = t - started
    if bytes_total == 0 and age_start < 5.0:
        status = "starting"
    elif age is None or age > float(stall_s):
        status = "stall"
    elif (
        write_bps is not None
        and bitrate_bps
        and int(bitrate_bps) > 0
        and write_bps < (float(bitrate_bps) / 8.0) * 0.25
    ):
        status = "slow"
    else:
        status = "ok"
    return {
        "bytes": bytes_total,
        "write_Bps": round(write_bps, 1) if write_bps is not None else None,
        "last_write_age_s": round(age, 2) if age is not None else None,
        "est_fps": est_fps,
        "stalled": status == "stall",
        "status": status,
    }
