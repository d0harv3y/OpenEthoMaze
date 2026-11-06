"""CapturePort contract — FakeCapture litmus (MULTIHOST Q9=C)."""

from __future__ import annotations

import time
from pathlib import Path

from app.capture_port import CapturePort, FakeCapture, RecordSink, SourceInfo


def test_fake_is_capture_port() -> None:
    assert isinstance(FakeCapture(), CapturePort)


def test_list_sources_stable_ids() -> None:
    cap = FakeCapture()
    srcs = cap.list_sources()
    assert len(srcs) >= 2
    assert all(isinstance(s, SourceInfo) for s in srcs)
    ids = [s.source_id for s in srcs]
    assert len(ids) == len(set(ids))
    assert all(s.source_id.startswith("usb:") for s in srcs)


def test_record_writes_mpegts_shaped_bytes(tmp_path: Path) -> None:
    cap = FakeCapture(hz=50.0)
    src = cap.list_sources()[0]
    cap.open(src.source_id, "desk0")
    ts = tmp_path / "desk0__p000.ts"
    pts = tmp_path / "desk0__p000.pts"
    sink = RecordSink(ts_path=ts, pts_path=pts)
    cap.start_record("desk0", sink)
    time.sleep(0.12)
    cap.stop_record("desk0")
    cap.close("desk0")
    raw = ts.read_bytes()
    assert len(raw) >= 188
    assert raw[0] == 0x47
    assert pts.is_file()
    assert pts.read_text(encoding="utf-8").strip()


def test_snapshot_jpeg_crude_live(tmp_path: Path) -> None:
    _ = tmp_path
    cap = FakeCapture()
    src = cap.list_sources()[0]
    assert cap.snapshot_jpeg("nope") is None
    cap.open(src.source_id, "c1")
    still = cap.snapshot_jpeg("c1")
    assert still is not None and still.startswith(b"\xff\xd8")
    cap.close("c1")


def test_cannot_double_bind_source() -> None:
    cap = FakeCapture()
    a, b = cap.list_sources()[:2]
    cap.open(a.source_id, "c0")
    try:
        cap.open(a.source_id, "c1")
        raise AssertionError("expected RuntimeError")
    except RuntimeError:
        pass
    cap.open(b.source_id, "c1")
    cap.close("c0")
    cap.close("c1")
