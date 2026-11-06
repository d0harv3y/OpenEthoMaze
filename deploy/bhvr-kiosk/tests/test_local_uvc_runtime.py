"""local_uvc binding helpers + LIVE tee hooks (no hardware)."""

from __future__ import annotations

import queue
from pathlib import Path

from app.capture_port import FakeCapture, RecordSink
from app.capture_uvc_dshow import _dshow_pixel_format
from app import local_uvc_runtime
from app.local_uvc_runtime import (
    _queue_put_drop_oldest,
    normalize_bindings,
    uvc_settings,
)


def test_normalize_bindings_caps_and_dedupes() -> None:
    raw = {
        "desk0": "usb:a",
        "desk1": "usb:b",
        "desk2": "usb:c",
        "desk3": "usb:d",
        "dup": "usb:a",
        "": "usb:e",
        "empty": "",
    }
    out = normalize_bindings(raw, max_n=3)
    assert list(out.keys()) == ["desk0", "desk1", "desk2"]
    assert out["desk0"] == "usb:a"
    assert "dup" not in out


def test_uvc_settings_allows_four() -> None:
    s = uvc_settings({"local_uvc": {"max_concurrent": 4}})
    assert s["max_concurrent"] == 4
    out = normalize_bindings(
        {"a": "usb:1", "b": "usb:2", "c": "usb:3", "d": "usb:4", "e": "usb:5"},
        max_n=s["max_concurrent"],
    )
    assert list(out.keys()) == ["a", "b", "c", "d"]


def test_dshow_pixel_format_by_vid() -> None:
    assert _dshow_pixel_format("usb:vid_1871&pid_0306#x") == "yuyv422"
    assert _dshow_pixel_format("usb:vid_0ac8&pid_301b#8&6a25437&0&4") == "bgr24"
    assert _dshow_pixel_format("usb:vid_093a&pid_2468#8&6a25437&0&1") == "bgr24"


def test_record_sink_on_ts_bytes_tee(tmp_path: Path) -> None:
    got: list[bytes] = []
    sink = RecordSink(
        ts_path=tmp_path / "cam.ts",
        pts_path=tmp_path / "cam.pts",
        on_ts_bytes=got.append,
    )
    sink.write_ts(b"\x47" * 188)
    sink.write_ts(b"")
    assert got == [b"\x47" * 188]
    assert (tmp_path / "cam.ts").read_bytes() == b"\x47" * 188


def test_queue_put_drop_oldest() -> None:
    q: queue.Queue[bytes | None] = queue.Queue(maxsize=2)
    _queue_put_drop_oldest(q, b"a")
    _queue_put_drop_oldest(q, b"b")
    _queue_put_drop_oldest(q, b"c")  # drops "a"
    assert q.get_nowait() == b"b"
    assert q.get_nowait() == b"c"


def test_other_pixart_busy_reads_idle_table(monkeypatch) -> None:
    class _Cap:
        def is_encoding(self, cam_id: str) -> bool:
            return cam_id == "desk0"

    monkeypatch.setattr(
        local_uvc_runtime,
        "_idle",
        {
            "desk0": {
                "source_id": "usb:vid_093a&pid_2468#a",
                "q": queue.Queue(),
            }
        },
    )
    monkeypatch.setattr(local_uvc_runtime, "get_adapter", lambda _cfg: _Cap())
    assert local_uvc_runtime._other_pixart_busy({}, "desk1") == "desk0"
    assert local_uvc_runtime._other_pixart_busy({}, "desk0") is None


def test_fake_capture_invokes_on_ts_bytes(tmp_path: Path) -> None:
    got: list[bytes] = []
    cap = FakeCapture(hz=200.0)
    src = cap.list_sources()[0]
    cap.open(src.source_id, "desk0")
    sink = RecordSink(
        ts_path=tmp_path / "f.ts",
        pts_path=tmp_path / "f.pts",
        on_ts_bytes=got.append,
    )
    cap.start_record("desk0", sink)
    # Wait for a few synthetic packets
    for _ in range(50):
        if len(got) >= 2:
            break
        import time

        time.sleep(0.02)
    cap.stop_record("desk0")
    cap.close("desk0")
    assert len(got) >= 2
    assert all(isinstance(x, (bytes, bytearray)) and len(x) > 0 for x in got)
