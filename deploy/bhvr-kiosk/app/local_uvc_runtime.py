"""Process-local LocalUvcDshow singleton for kiosk capture_backend=local_uvc."""

from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.capture_port import RecordSink, SourceInfo
from app.capture_uvc_dshow import LocalUvcDshow, filter_uvc_only

# Soft ceiling for operator bindings. Desk litmus: 3-up PASS / 4-up often
# fails isoch on one uplink — allow 4 so operators can retry / split hubs.
MAX_CONCURRENT = 4
DEFAULT_IDLE_QUEUE_MAX = 512

_lock = threading.Lock()
_snap_lock = threading.Lock()  # one dshow graph at a time (USB isoch)
_snap_block = threading.Event()  # set during science promote/REC
_adapter: LocalUvcDshow | None = None
# cam_id → idle LIVE publisher state
_idle: dict[str, dict[str, Any]] = {}
_idle_lock = threading.Lock()


def set_snapshot_blocked(blocked: bool) -> None:
    """Stop idle still grabs so they cannot hold a stick during science open."""
    if blocked:
        _snap_block.set()
        # Wait out any in-flight ffmpeg snap (holds _snap_lock).
        acquired = _snap_lock.acquire(timeout=20.0)
        if acquired:
            _snap_lock.release()
    else:
        _snap_block.clear()


def snapshots_blocked() -> bool:
    return _snap_block.is_set()


def capture_backend(cfg: dict[str, Any]) -> str:
    return str(cfg.get("capture_backend") or "pi_ssh").strip().lower()


def is_local_uvc(cfg: dict[str, Any]) -> bool:
    return capture_backend(cfg) == "local_uvc"


def uvc_settings(cfg: dict[str, Any]) -> dict[str, Any]:
    raw = cfg.get("local_uvc") if isinstance(cfg.get("local_uvc"), dict) else {}
    max_n = int(raw.get("max_concurrent") or MAX_CONCURRENT)
    max_n = max(1, min(MAX_CONCURRENT, max_n))
    return {
        "max_concurrent": max_n,
        "width": int(raw.get("width") or 320),
        "height": int(raw.get("height") or 240),
        "fps": int(raw.get("fps") or 30),
        "video_bitrate": str(raw.get("video_bitrate") or "1500k"),
        "vid_filter": str(raw.get("vid_filter") or "").strip() or None,
    }


def get_adapter(cfg: dict[str, Any]) -> LocalUvcDshow:
    global _adapter
    s = uvc_settings(cfg)
    with _lock:
        if _adapter is None:
            _adapter = LocalUvcDshow(
                width=s["width"],
                height=s["height"],
                fps=s["fps"],
                video_bitrate=s["video_bitrate"],
            )
        return _adapter


def normalize_bindings(raw: Any, *, max_n: int = MAX_CONCURRENT) -> dict[str, str]:
    """cam_id → source_id; at most max_n; drop empties; first wins on dup source."""
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    seen_src: set[str] = set()
    for cam_id, source_id in raw.items():
        cid = str(cam_id or "").strip()
        sid = str(source_id or "").strip()
        if not cid or not sid:
            continue
        if sid in seen_src:
            continue
        if len(out) >= max_n:
            break
        seen_src.add(sid)
        out[cid] = sid
    return out


def list_sources(cfg: dict[str, Any]) -> list[SourceInfo]:
    s = uvc_settings(cfg)
    try:
        srcs = get_adapter(cfg).list_sources()
    except FileNotFoundError:
        return []
    return filter_uvc_only(srcs, vid=s.get("vid_filter"))


def roster_cameras(cfg: dict[str, Any], op: dict[str, Any]) -> list[dict[str, Any]]:
    """Synthetic MQTT-like rows for bound local UVC cams."""
    s = uvc_settings(cfg)
    bindings = normalize_bindings(op.get("uvc_bindings"), max_n=s["max_concurrent"])
    present = {src.source_id: src for src in list_sources(cfg)}
    now = time.time()
    out: list[dict[str, Any]] = []
    cap = None
    try:
        cap = get_adapter(cfg)
    except FileNotFoundError:
        cap = None
    for cam_id, source_id in sorted(bindings.items()):
        src = present.get(source_id)
        # list_devices while a stick is encoding often misses it — keep online
        # if we already hold an idle/REC graph for this cam_id.
        holding = idle_preview_active(cam_id) or (
            cap is not None and cap.is_encoding(cam_id)
        )
        online = src is not None or holding
        label = src.label if src else source_id
        out.append(
            {
                "id": cam_id,
                "ip": "local",
                "ips": {"local": source_id},
                "link": "uvc",
                "online": online,
                "age_s": 0.0 if online else 9999.0,
                "seen_at": now if online else 0.0,
                "source_id": source_id,
                "label": label,
                "kind": "uvc",
                "temp_c": None,
                "rh_pct": None,
            }
        )
    return out


def _other_pixart_busy(cfg: dict[str, Any], cam_id: str) -> str | None:
    """Pixart Eye 110 (vid_093a): second concurrent open kills both on one hub."""
    with _idle_lock:
        for other_id, st in _idle.items():
            if other_id == cam_id:
                continue
            sid = str(st.get("source_id") or "").lower()
            if "vid_093a" not in sid:
                continue
            if get_adapter(cfg).is_encoding(other_id):
                return other_id
    return None


def _queue_put_drop_oldest(q: "queue.Queue[bytes | None]", chunk: bytes) -> None:
    try:
        q.put_nowait(chunk)
    except queue.Full:
        try:
            q.get_nowait()
        except queue.Empty:
            pass
        try:
            q.put_nowait(chunk)
        except queue.Full:
            pass


def start_record_cam(
    *,
    cfg: dict[str, Any],
    cam_id: str,
    source_id: str,
    ts_path: Path,
    pts_path: Path,
    on_ts_bytes: Callable[[bytes], None] | None = None,
) -> None:
    """open + start_record. Caller owns H5 shell / capture bookkeeping."""
    stop_idle_preview(cfg, cam_id)
    cap = get_adapter(cfg)
    # Re-bind cleanly if a prior session left state.
    try:
        cap.close(cam_id)
    except Exception:
        pass
    cap.open(source_id, cam_id)
    sink = RecordSink(
        ts_path=ts_path, pts_path=pts_path, on_ts_bytes=on_ts_bytes
    )
    cap.start_record(cam_id, sink)


def stop_record_cam(cfg: dict[str, Any], cam_id: str) -> None:
    try:
        get_adapter(cfg).stop_record(cam_id)
    except Exception:
        pass
    try:
        get_adapter(cfg).close(cam_id)
    except Exception:
        pass


def stop_idle_preview(cfg: dict[str, Any], cam_id: str) -> None:
    """Stop idle LIVE publisher for ``cam_id`` (no-op if none)."""
    with _idle_lock:
        info = _idle.pop(cam_id, None)
    if info is None:
        return
    q = info.get("q")
    if isinstance(q, queue.Queue):
        try:
            q.put_nowait(None)
        except queue.Full:
            pass
    try:
        get_adapter(cfg).stop_encode(cam_id)
    except Exception:
        pass
    try:
        get_adapter(cfg).close(cam_id)
    except Exception:
        pass


def stop_all_idle_previews(cfg: dict[str, Any]) -> None:
    with _idle_lock:
        ids = list(_idle.keys())
    for cam_id in ids:
        stop_idle_preview(cfg, cam_id)


def idle_preview_active(cam_id: str) -> bool:
    with _idle_lock:
        return cam_id in _idle


def ensure_idle_preview(
    cfg: dict[str, Any],
    cam_id: str,
    source_id: str,
    *,
    queue_max: int = DEFAULT_IDLE_QUEUE_MAX,
) -> "queue.Queue[bytes | None]":
    """Start or reuse idle MPEG-TS publisher; return tee queue for HTTP."""
    cam_id = (cam_id or "").strip()
    source_id = (source_id or "").strip()
    if not cam_id or not source_id:
        raise ValueError("cam_id and source_id required")
    qmax = max(32, min(4096, int(queue_max)))

    with _idle_lock:
        cur = _idle.get(cam_id)
        if (
            cur is not None
            and cur.get("source_id") == source_id
            and isinstance(cur.get("q"), queue.Queue)
            and get_adapter(cfg).encode_mode(cam_id) == "idle"
            and get_adapter(cfg).is_encoding(cam_id)
        ):
            return cur["q"]  # type: ignore[return-value]

    busy = _other_pixart_busy(cfg, cam_id)
    if busy and "vid_093a" in source_id.lower():
        raise RuntimeError(
            f"Pixart Eye 110: only one concurrent open (other LIVE is {busy}; "
            "opening a second stick kills both). Stop the other tile first."
        )

    stop_idle_preview(cfg, cam_id)

    q: queue.Queue[bytes | None] = queue.Queue(maxsize=qmax)

    def on_chunk(data: bytes) -> None:
        _queue_put_drop_oldest(q, data)

    def on_stderr(msg: str) -> None:
        print(f"idle-uvc {cam_id}: encode died: {msg}", flush=True)
        with _idle_lock:
            st = _idle.pop(cam_id, None)
        if st is not None:
            qq = st.get("q")
            if isinstance(qq, queue.Queue):
                try:
                    qq.put_nowait(None)
                except queue.Full:
                    pass

    cap = get_adapter(cfg)
    try:
        cap.close(cam_id)
    except Exception:
        pass
    cap.open(source_id, cam_id)
    cap.start_idle(cam_id, on_chunk, on_stderr=on_stderr)
    with _idle_lock:
        _idle[cam_id] = {"q": q, "source_id": source_id}
    return q


def snapshot_jpeg(cfg: dict[str, Any], cam_id: str, source_id: str) -> bytes | None:
    """Grab one JPEG. Serialized — concurrent dshow opens trip the isoch wall.

    Returns ``None`` immediately if another snap holds the lock (caller → 503/busy)
    so the FastAPI threadpool is not wedged behind multi-second ffmpeg grabs.
    Idle/REC encode on the same cam also returns ``None``.
    """
    if _snap_block.is_set():
        return None
    if idle_preview_active(cam_id):
        return None
    if not _snap_lock.acquire(blocking=False):
        return None
    try:
        if _snap_block.is_set():
            return None
        cap = get_adapter(cfg)
        if cap.is_encoding(cam_id):
            return None
        try:
            cap.open(source_id, cam_id)
        except RuntimeError:
            pass
        except KeyError:
            return None
        try:
            return cap.snapshot_jpeg(cam_id)
        finally:
            try:
                cap.close(cam_id)
            except Exception:
                pass
    finally:
        _snap_lock.release()
