"""REC write-rate stats (SSD path) — independent of browser LIVE fps."""

from __future__ import annotations

from app.capture_stats import (
    new_capture_byte_stats,
    note_capture_bytes,
    snapshot_capture_stats,
)


def test_snapshot_starting_then_ok() -> None:
    t0 = 1000.0
    stats = new_capture_byte_stats(now=t0)
    snap0 = snapshot_capture_stats(stats, soft_fps=30, bitrate_bps=4_000_000, now=t0 + 0.5)
    assert snap0["status"] == "starting"
    assert snap0["bytes"] == 0
    assert snap0["stalled"] is False

    # ~bitrate/8 bytes over 1s → est_fps ≈ soft_fps
    note_capture_bytes(stats, 500_000, now=t0 + 1.0)
    note_capture_bytes(stats, 500_000, now=t0 + 2.0)
    snap = snapshot_capture_stats(stats, soft_fps=30, bitrate_bps=4_000_000, now=t0 + 2.1)
    assert snap["bytes"] == 1_000_000
    assert snap["write_Bps"] is not None
    assert snap["write_Bps"] > 400_000
    assert snap["status"] == "ok"
    assert snap["est_fps"] is not None
    assert 20.0 <= float(snap["est_fps"]) <= 40.0


def test_snapshot_stall_after_silence() -> None:
    t0 = 2000.0
    stats = new_capture_byte_stats(now=t0)
    note_capture_bytes(stats, 100_000, now=t0 + 0.5)
    note_capture_bytes(stats, 100_000, now=t0 + 1.0)
    snap = snapshot_capture_stats(
        stats, soft_fps=30, bitrate_bps=4_000_000, now=t0 + 4.0, stall_s=2.0
    )
    assert snap["status"] == "stall"
    assert snap["stalled"] is True
    assert snap["last_write_age_s"] is not None
    assert float(snap["last_write_age_s"]) >= 2.9


def test_snapshot_slow_when_write_far_below_bitrate() -> None:
    t0 = 3000.0
    stats = new_capture_byte_stats(now=t0)
    # 4 Mbps ask → expect ~500 KB/s; feed ~50 KB/s
    note_capture_bytes(stats, 25_000, now=t0 + 1.0)
    note_capture_bytes(stats, 25_000, now=t0 + 2.0)
    snap = snapshot_capture_stats(stats, soft_fps=30, bitrate_bps=4_000_000, now=t0 + 2.05)
    assert snap["status"] == "slow"
    assert snap["stalled"] is False
