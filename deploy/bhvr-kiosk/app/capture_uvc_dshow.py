"""Windows DirectShow UVC adapter via ffmpeg (MULTIHOST Win11+UVC spike).

Lists devices with stable PnP ``source_id``, records / idle-LIVE MPEG-TS (libx264),
optional crude JPEG snapshot.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.capture_port import RecordSink, SourceInfo

_ALT_RE = re.compile(
    r'Alternative name\s*\n?\s*"(@device_pnp_[^"]+)"',
    re.IGNORECASE | re.MULTILINE,
)
_NAME_RE = re.compile(r'^\[.*?\]\s*"([^"]+)"\s*\(video\)\s*$', re.IGNORECASE | re.MULTILINE)
# usb#vid_xxxx&pid_yyyy&mi_00#INSTANCE#{guid}\global
_USB_ID_RE = re.compile(
    r"usb#vid_([0-9a-f]+)&pid_([0-9a-f]+)(?:&mi_[0-9a-f]+)?#([^#\\]+)",
    re.IGNORECASE,
)


def _last_jpeg(blob: bytes) -> bytes | None:
    """Return the last SOI…EOI JPEG in ``blob`` (image2pipe mjpeg)."""
    if not blob:
        return None
    soi = blob.rfind(b"\xff\xd8")
    if soi < 0:
        return None
    eoi = blob.find(b"\xff\xd9", soi + 2)
    if eoi < 0:
        return None
    return blob[soi : eoi + 2]


def find_ffmpeg() -> str:
    env = (os.environ.get("MAZE_FFMPEG") or os.environ.get("FFMPEG") or "").strip()
    if env and Path(env).is_file():
        return env
    which = shutil.which("ffmpeg")
    if which:
        return which
    raise FileNotFoundError(
        "ffmpeg not found — install (winget Gyan.FFmpeg) or set MAZE_FFMPEG"
    )


def _dshow_pixel_format(source_id: str) -> str:
    """DirectShow ``-pixel_format`` for this stick.

    Desk ``vid_1871`` sticks are YUYV-only. Vendor Class_FF sticks
    (Vimicro ``vid_0ac8`` ZC0301PL; Pixart ``vid_093a`` Eye 110) speak
    ``bgr24`` / ``yuv420p`` — forcing ``yuyv422`` fails open and LIVE
    hangs on settle with no MPEG-TS bytes.
    """
    sid = (source_id or "").lower()
    if "vid_0ac8" in sid or "vid_093a" in sid:
        return "bgr24"
    return "yuyv422"


def _stable_id_from_alt(alt: str) -> str | None:
    m = _USB_ID_RE.search(alt.replace("/", "\\"))
    if not m:
        return None
    vid, pid, inst = m.group(1).lower(), m.group(2).lower(), m.group(3)
    return f"usb:vid_{vid}&pid_{pid}#{inst}"


def list_dshow_video_sources(*, ffmpeg: str | None = None) -> list[SourceInfo]:
    ff = ffmpeg or find_ffmpeg()
    r = subprocess.run(
        [ff, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    # ffmpeg prints device list to stderr
    blob = (r.stderr or "") + "\n" + (r.stdout or "")
    lines = blob.splitlines()
    out: list[SourceInfo] = []
    i = 0
    while i < len(lines):
        m = re.search(r'"([^"]+)"\s*\(video\)', lines[i])
        if not m:
            i += 1
            continue
        label = m.group(1)
        alt = ""
        # Next lines may be "  Alternative name" then quoted path (possibly wrapped)
        j = i + 1
        while j < len(lines) and j < i + 4:
            if "Alternative name" in lines[j]:
                # same line or next
                am = re.search(r'"(@device_pnp_[^"]+)"', lines[j])
                if am:
                    alt = am.group(1)
                elif j + 1 < len(lines):
                    am2 = re.search(r'"(@device_pnp_[^"]+)"', lines[j + 1])
                    if am2:
                        alt = am2.group(1)
                break
            if re.search(r'"([^"]+)"\s*\(video\)', lines[j]):
                break
            j += 1
        sid = _stable_id_from_alt(alt) if alt else None
        if not sid:
            # Non-USB or unparsed — skip for spike (need stable id)
            i += 1
            continue
        out.append(
            SourceInfo(
                source_id=sid,
                label=label,
                kind="uvc",
                meta={
                    "dshow_name": label,
                    "dshow_alt": alt,
                    "ffmpeg": "dshow",
                },
            )
        )
        i = j + 1 if j > i else i + 1
    # De-dupe by source_id (keep first)
    seen: set[str] = set()
    uniq: list[SourceInfo] = []
    for s in out:
        if s.source_id in seen:
            continue
        seen.add(s.source_id)
        uniq.append(s)
    return uniq


class LocalUvcDshow:
    """CapturePort-shaped adapter: dshow → libx264 MPEG-TS (REC or idle LIVE)."""

    def __init__(
        self,
        *,
        ffmpeg: str | None = None,
        width: int = 640,
        height: int = 480,
        fps: int = 30,
        video_bitrate: str = "1500k",
    ) -> None:
        self._ffmpeg = ffmpeg or find_ffmpeg()
        self._width = width
        self._height = height
        self._fps = fps
        self._bitrate = video_bitrate
        self._bound: dict[str, SourceInfo] = {}
        self._procs: dict[str, subprocess.Popen[bytes]] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._stops: dict[str, threading.Event] = {}
        self._modes: dict[str, str] = {}  # cam_id → "record" | "idle"
        self._lock = threading.Lock()

    def list_sources(self) -> list[SourceInfo]:
        return list_dshow_video_sources(ffmpeg=self._ffmpeg)

    def open(self, source_id: str, cam_id: str) -> None:
        srcs = {s.source_id: s for s in self.list_sources()}
        if source_id not in srcs:
            raise KeyError(f"unknown source_id: {source_id}")
        cam = (cam_id or "").strip()
        if not cam:
            raise ValueError("cam_id required")
        with self._lock:
            if cam in self._bound:
                raise RuntimeError(f"cam_id already open: {cam}")
            if any(s.source_id == source_id for s in self._bound.values()):
                raise RuntimeError(f"source already bound: {source_id}")
            self._bound[cam] = srcs[source_id]

    def close(self, cam_id: str) -> None:
        self.stop_encode(cam_id)
        with self._lock:
            self._bound.pop(cam_id, None)

    def is_encoding(self, cam_id: str) -> bool:
        """True only while ffmpeg is still alive (dead procs are detached)."""
        with self._lock:
            proc = self._procs.get(cam_id)
            if proc is None:
                return False
            if proc.poll() is not None:
                return False
            return True

    def encode_mode(self, cam_id: str) -> str | None:
        with self._lock:
            proc = self._procs.get(cam_id)
            if proc is None or proc.poll() is not None:
                return None
            return self._modes.get(cam_id)

    def _mpegts_cmd(self, *, alt: str, source_id: str) -> list[str]:
        # rtbufsize: dshow drops if encode lags; pixel_format per stick
        # (1871=YUYV; 0ac8 Vimicro=bgr24). Isoch reservation still caps N.
        pix = _dshow_pixel_format(source_id)
        return [
            self._ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "dshow",
            "-rtbufsize",
            "100M",
            "-video_size",
            f"{self._width}x{self._height}",
            "-framerate",
            str(self._fps),
            "-pixel_format",
            pix,
            "-i",
            f"video={alt}",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-tune",
            "zerolatency",
            "-pix_fmt",
            "yuv420p",
            "-b:v",
            self._bitrate,
            "-f",
            "mpegts",
            "pipe:1",
        ]

    def _spawn_mpegts(
        self,
        cam_id: str,
        *,
        mode: str,
        on_chunk: Callable[[bytes], None],
        on_stderr: Callable[[str], None] | None = None,
        pts_every: int = 0,
        on_pts: Callable[[str], None] | None = None,
    ) -> None:
        with self._lock:
            src = self._bound.get(cam_id)
            if src is None:
                raise RuntimeError(f"cam not open: {cam_id}")
            if cam_id in self._procs:
                raise RuntimeError(f"already encoding: {cam_id}")
            alt = src.meta.get("dshow_alt") or ""
            if not alt:
                raise RuntimeError(f"no dshow_alt for {cam_id}")
            stop = threading.Event()
            self._stops[cam_id] = stop
            cmd = self._mpegts_cmd(alt=alt, source_id=src.source_id)
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
            )
            self._procs[cam_id] = proc
            self._modes[cam_id] = mode
            t = threading.Thread(
                target=self._pump,
                args=(cam_id, proc, stop, on_chunk, on_stderr, pts_every, on_pts),
                name=f"uvc-ts-{cam_id}",
                daemon=True,
            )
            self._threads[cam_id] = t
            t.start()

    def start_record(self, cam_id: str, sink: RecordSink) -> None:
        def on_chunk(data: bytes) -> None:
            sink.write_ts(data)

        def on_pts(line: str) -> None:
            sink.write_pts_line(line)

        def on_stderr(msg: str) -> None:
            sink.write_pts_line(f"# ffmpeg_stderr {msg}")

        self._spawn_mpegts(
            cam_id,
            mode="record",
            on_chunk=on_chunk,
            on_stderr=on_stderr,
            pts_every=15,
            on_pts=on_pts,
        )

    def start_idle(
        self,
        cam_id: str,
        on_chunk: Callable[[bytes], None],
        on_stderr: Callable[[str], None] | None = None,
    ) -> None:
        """Idle LIVE: same encode as REC, chunks only (no disk)."""
        self._spawn_mpegts(
            cam_id, mode="idle", on_chunk=on_chunk, on_stderr=on_stderr
        )

    def stop_encode(self, cam_id: str) -> None:
        with self._lock:
            stop = self._stops.pop(cam_id, None)
            proc = self._procs.pop(cam_id, None)
            t = self._threads.pop(cam_id, None)
            self._modes.pop(cam_id, None)
        if stop is not None:
            stop.set()
        if proc is not None:
            try:
                proc.terminate()
            except OSError:
                pass
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        if t is not None:
            t.join(timeout=6.0)

    def stop_record(self, cam_id: str) -> None:
        self.stop_encode(cam_id)

    def snapshot_jpeg(self, cam_id: str) -> bytes | None:
        with self._lock:
            src = self._bound.get(cam_id)
        if src is None:
            return None
        alt = src.meta.get("dshow_alt") or ""
        if not alt:
            return None
        # Cannot grab while same device is encoding.
        with self._lock:
            if cam_id in self._procs:
                return None
        # Grab several frames — first dshow frame is often black/empty.
        pix = _dshow_pixel_format(src.source_id)
        cmd = [
            self._ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "dshow",
            "-rtbufsize",
            "50M",
            "-video_size",
            f"{self._width}x{self._height}",
            "-framerate",
            str(self._fps),
            "-pixel_format",
            pix,
            "-i",
            f"video={alt}",
            "-frames:v",
            "4",
            "-f",
            "image2pipe",
            "-vcodec",
            "mjpeg",
            "pipe:1",
        ]
        try:
            r = subprocess.run(
                cmd, capture_output=True, timeout=12, check=False
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        raw = r.stdout or b""
        # Last SOI…EOI JPEG in the pipe (skip black warm-up frames).
        jpeg = _last_jpeg(raw)
        if jpeg is None or len(jpeg) < 500:
            return None
        return jpeg

    def _pump(
        self,
        cam_id: str,
        proc: subprocess.Popen[bytes],
        stop: threading.Event,
        on_chunk: Callable[[bytes], None],
        on_stderr: Callable[[str], None] | None,
        pts_every: int,
        on_pts: Callable[[str], None] | None,
    ) -> None:
        assert proc.stdout is not None
        t0 = time.monotonic()
        n = 0
        unexpected = False
        try:
            while not stop.is_set():
                chunk = proc.stdout.read(188 * 32)
                if not chunk:
                    unexpected = not stop.is_set()
                    break
                on_chunk(chunk)
                n += 1
                if pts_every > 0 and on_pts is not None and n % pts_every == 0:
                    on_pts(f"{(time.monotonic() - t0) * 1000.0:.3f}")
        finally:
            err = b""
            if proc.stderr is not None:
                try:
                    err = proc.stderr.read() or b""
                except OSError:
                    err = b""
            msg = err[-800:].decode("utf-8", "replace").strip() if err else ""
            if unexpected:
                detail = msg or f"stdout EOF after {n} chunks (rc={proc.poll()})"
                print(f"uvc-ts {cam_id}: ffmpeg died: {detail}", flush=True)
                if on_stderr is not None:
                    on_stderr(detail)
            # Detach so is_encoding/encode_mode do not lie that LIVE is up.
            with self._lock:
                if self._procs.get(cam_id) is proc:
                    self._procs.pop(cam_id, None)
                    self._modes.pop(cam_id, None)
                    self._threads.pop(cam_id, None)
                    self._stops.pop(cam_id, None)


def filter_uvc_only(sources: list[SourceInfo], *, vid: str | None = None) -> list[SourceInfo]:
    """Drop built-in laptop cams; optional VID filter (e.g. ``1871``)."""
    out: list[SourceInfo] = []
    for s in sources:
        if s.kind != "uvc":
            continue
        sid = s.source_id.lower()
        if vid and f"vid_{vid.lower()}" not in sid:
            continue
        # Skip common laptop IR/FHD Chicony if desired — keep unless vid filter set
        out.append(s)
    return out
