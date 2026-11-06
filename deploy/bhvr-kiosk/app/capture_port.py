"""CapturePort contract — multi-host DAQ adapters (MULTIHOST grill).

Adapters produce MPEG-TS (+ optional pts). See ``docs/capture_port.md``.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol, runtime_checkable


@dataclass(frozen=True)
class SourceInfo:
    """One discoverable capture source."""

    source_id: str
    """Stable hardware/roster id (USB path/serial, MQTT cam id, …)."""

    label: str
    """Human label (may be friendly name; not used as primary key)."""

    kind: str
    """``uvc`` | ``pi_ssh`` | ``fake`` | …"""

    meta: dict[str, str] = field(default_factory=dict)


@dataclass
class RecordSink:
    """Where science MPEG-TS (and optional pts) go during REC."""

    ts_path: Path
    pts_path: Path | None = None
    on_ts_bytes: Callable[[bytes], None] | None = None

    def write_ts(self, data: bytes) -> None:
        if not data:
            return
        self.ts_path.parent.mkdir(parents=True, exist_ok=True)
        with self.ts_path.open("ab") as f:
            f.write(data)
        if self.on_ts_bytes is not None:
            self.on_ts_bytes(data)

    def write_pts_line(self, line: str) -> None:
        if self.pts_path is None:
            return
        self.pts_path.parent.mkdir(parents=True, exist_ok=True)
        with self.pts_path.open("a", encoding="utf-8") as f:
            f.write(line if line.endswith("\n") else line + "\n")


@runtime_checkable
class CapturePort(Protocol):
    """REC-facing capture adapter (grill Q6=A)."""

    def list_sources(self) -> list[SourceInfo]:
        """Discover sources with stable ``source_id`` values."""

    def open(self, source_id: str, cam_id: str) -> None:
        """Bind ``source_id`` → operator ``cam_id`` (filename token)."""

    def close(self, cam_id: str) -> None:
        """Release a binding (idle)."""

    def start_record(self, cam_id: str, sink: RecordSink) -> None:
        """Begin writing MPEG-TS to ``sink``."""

    def stop_record(self, cam_id: str) -> None:
        """Stop recording and flush."""

    def snapshot_jpeg(self, cam_id: str) -> bytes | None:
        """Crude LIVE still (Q7=C); ``None`` if unsupported."""


class FakeCapture:
    """Synthetic MPEG-TS writer for contract tests (no hardware)."""

    def __init__(self, *, packet_bytes: int = 188 * 7, hz: float = 30.0) -> None:
        self._packet_bytes = max(188, packet_bytes)
        self._period = 1.0 / max(hz, 1.0)
        self._sources = [
            SourceInfo(
                source_id="usb:VID_TEST&PID_0001&port_1",
                label="Fake UVC 0",
                kind="fake",
                meta={"vid": "TEST", "pid": "0001"},
            ),
            SourceInfo(
                source_id="usb:VID_TEST&PID_0002&port_2",
                label="Fake UVC 1",
                kind="fake",
                meta={"vid": "TEST", "pid": "0002"},
            ),
        ]
        self._bound: dict[str, str] = {}  # cam_id -> source_id
        self._threads: dict[str, threading.Thread] = {}
        self._stops: dict[str, threading.Event] = {}
        self._sinks: dict[str, RecordSink] = {}
        self._lock = threading.Lock()

    def list_sources(self) -> list[SourceInfo]:
        return list(self._sources)

    def open(self, source_id: str, cam_id: str) -> None:
        ids = {s.source_id for s in self._sources}
        if source_id not in ids:
            raise KeyError(f"unknown source_id: {source_id}")
        cam = (cam_id or "").strip()
        if not cam:
            raise ValueError("cam_id required")
        with self._lock:
            if cam in self._bound:
                raise RuntimeError(f"cam_id already open: {cam}")
            if source_id in self._bound.values():
                raise RuntimeError(f"source already bound: {source_id}")
            self._bound[cam] = source_id

    def close(self, cam_id: str) -> None:
        self.stop_record(cam_id)
        with self._lock:
            self._bound.pop(cam_id, None)

    def start_record(self, cam_id: str, sink: RecordSink) -> None:
        with self._lock:
            if cam_id not in self._bound:
                raise RuntimeError(f"cam not open: {cam_id}")
            if cam_id in self._threads:
                raise RuntimeError(f"already recording: {cam_id}")
            stop = threading.Event()
            self._stops[cam_id] = stop
            self._sinks[cam_id] = sink
            t = threading.Thread(
                target=self._run,
                args=(cam_id, sink, stop),
                name=f"fake-cap-{cam_id}",
                daemon=True,
            )
            self._threads[cam_id] = t
            t.start()

    def stop_record(self, cam_id: str) -> None:
        with self._lock:
            stop = self._stops.pop(cam_id, None)
            t = self._threads.pop(cam_id, None)
            self._sinks.pop(cam_id, None)
        if stop is not None:
            stop.set()
        if t is not None:
            t.join(timeout=5.0)

    def snapshot_jpeg(self, cam_id: str) -> bytes | None:
        with self._lock:
            if cam_id not in self._bound:
                return None
        # Minimal JPEG SOI/EOI stub (not a real image — contract presence only).
        return b"\xff\xd8\xff\xd9"

    def _run(self, cam_id: str, sink: RecordSink, stop: threading.Event) -> None:
        # 0x47 sync MPEG-TS-ish payload; not a valid program — packer only needs bytes.
        pkt = b"\x47" + bytes((cam_id.encode("utf-8") + b"\x00" * 20)[:20])
        pkt = (pkt * ((self._packet_bytes // len(pkt)) + 1))[: self._packet_bytes]
        t0 = time.monotonic()
        n = 0
        while not stop.is_set():
            sink.write_ts(pkt)
            sink.write_pts_line(f"{(time.monotonic() - t0) * 1000.0:.3f}")
            n += 1
            stop.wait(self._period)
        _ = n
