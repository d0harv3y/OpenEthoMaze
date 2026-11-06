"""Per-cam session H5 archive (grill Files & H5 — v0).

One file per cam: ``{subject}__{tag}__{cam}.h5`` with ``video/mpegts_NNN`` (+
optional ``video/pts_NNN``), ``logs/*``, and rich attrs. Pack after each TS
roll / Stop; delete loose ``.ts``/``.pts``/part logs after byte-count verify.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


def _slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", s.strip()).strip("-") or "unknown"

# Soft caps so a runaway remux log cannot balloon the H5.
_MAX_LOG_BYTES = 2 * 1024 * 1024
_MAX_ENV_BYTES = 1 * 1024 * 1024
_MAX_PTS_FULL_BYTES = 8 * 1024 * 1024

# Human-readable ``description`` attr on every dataset (HDF5 viewers / myhdf5).
_DESC = {
    "mpegts": (
        "MPEG-TS bytes for one chunk part (H.264 in MPEG-TS). "
        "Raw uint8 copy of the packed .ts file."
    ),
    "pts": (
        "Per-frame presentation timestamps for this part, milliseconds "
        "relative to the first stamp in the part (see t0_ms_abs for absolute)."
    ),
    "capture": (
        "NVR SSH / rpicam-vid stderr for this part (cam-side capture pipe)."
    ),
    "remux": (
        "NVR ffmpeg stderr while remuxing Annex-B H.264 → MPEG-TS for this part. "
        "Empty when remux is quiet (normal)."
    ),
    "env_jsonl": (
        "Per-cam environment samples (JSONL), e.g. HTU21D temp/humidity windows."
    ),
    "pts_full": (
        "Full-session pts pulled from the cam before final slice "
        "(absolute ms lines; may exceed part bounds)."
    ),
}

try:
    import h5py
except ImportError as exc:  # pragma: no cover
    h5py = None  # type: ignore[assignment]
    _H5PY_ERR = exc
else:
    _H5PY_ERR = None

_COPY_CHUNK = 8 * 1024 * 1024


def require_h5py() -> None:
    if h5py is None:
        raise RuntimeError(
            "h5py is required for session H5 pack — "
            "pip install h5py (see bhvr-kiosk/requirements.txt)"
        ) from _H5PY_ERR


def cam_h5_path(
    folder: Path,
    subject_id: str,
    cam_id: str,
    *,
    recording_tag: str = "ses",
) -> Path:
    """``{subject}__{tag}__{cam}.h5`` — tag always present (default ses)."""
    subj = _slug(subject_id)
    cam = _slug(cam_id)
    tag = _slug(recording_tag) if recording_tag else "ses"
    return folder / f"{subj}__{tag}__{cam}.h5"


def cam_h5_path_slugged(
    folder: Path, subject_slug: str, cam_slug: str, *, tag_slug: str = "ses"
) -> Path:
    tag = tag_slug or "ses"
    return folder / f"{subject_slug}__{tag}__{cam_slug}.h5"


def create_cam_h5(
    path: Path,
    *,
    attrs: dict[str, Any],
) -> Path:
    """Create empty session H5 shell at REC start (grill)."""
    require_h5py()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        path.unlink()
    with h5py.File(path, "w") as f:
        video = f.create_group("video")
        logs = f.create_group("logs")
        video.attrs["description"] = (
            "Chunked MPEG-TS video parts and matching pts datasets."
        )
        logs.attrs["description"] = (
            "Text/binary sidecars: capture/remux logs, env JSONL, full pts."
        )
        f.attrs["bhvr_h5_version"] = "0"
        f.attrs["created_utc"] = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        f.attrs["description"] = (
            "bhvr-kiosk per-cam session archive: video/mpegts_NNN + logs/*."
        )
        for k, v in attrs.items():
            _set_attr(f, k, v)
    return path


def pack_part(
    h5_path: Path,
    *,
    part: int,
    ts_path: Path,
    pts_path: Path | None = None,
    fps_summary: dict[str, Any] | None = None,
    attrs: dict[str, Any] | None = None,
    delete_loose: bool = True,
    folder: Path | str | None = None,
    cam_id: str | None = None,
    subject_id: str | None = None,
    pack_session_sidecars: bool = False,
    skip_if_exists: bool = False,
) -> dict[str, Any]:
    """Append ``video/mpegts_NNN`` (+ pts) and fold part/session sidecars into H5.

    Part sidecars (from ``ts_path.stem``): ``*_capture.log``, ``*_remux.log``,
    ``*_fps.json`` → ``logs/`` (+ fps already on mpegts attrs).

    When ``pack_session_sidecars``: also fold cam ``*_env.jsonl``,
    ``.{cam}_pts_full.pts``, and session ``stop_log.json`` (attr only; leave
    loose stop_log for operators).

    ``skip_if_exists`` (Pack now default): if ``mpegts_NNN`` already present,
    return ok/skipped without deleting loose files (Force clears this flag).
    """
    require_h5py()
    h5_path = Path(h5_path)
    ts_path = Path(ts_path)
    if not ts_path.is_file():
        return {"ok": False, "error": f"missing ts: {ts_path}"}
    ts_size = ts_path.stat().st_size
    if ts_size <= 0:
        return {"ok": False, "error": f"empty ts: {ts_path}"}

    name = f"mpegts_{int(part):03d}"
    pts_name = f"pts_{int(part):03d}"
    packed_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    log: list[str] = []
    stem = ts_path.stem
    folder_p = Path(folder) if folder else ts_path.parent
    to_delete: list[Path] = []

    with h5py.File(h5_path, "a") as f:
        video = f.require_group("video")
        logs = f.require_group("logs")
        if skip_if_exists and name in video:
            log.append(f"skip existing {name}")
            return {
                "ok": True,
                "skipped": True,
                "part": int(part),
                "bytes": int(video[name].shape[0]),
                "h5": str(h5_path),
                "dataset": name,
                "log": log,
            }
        if name in video:
            del video[name]
        ds = video.create_dataset(
            name,
            shape=(ts_size,),
            dtype="uint8",
            chunks=(min(_COPY_CHUNK, ts_size),),
        )
        _copy_file_into_dataset(ds, ts_path)
        ds.attrs["description"] = _DESC["mpegts"]
        ds.attrs["part"] = int(part)
        ds.attrs["packed_utc"] = packed_utc
        ds.attrs["source_ts"] = ts_path.name
        ds.attrs["bytes"] = int(ts_size)
        if attrs:
            for k, v in attrs.items():
                _set_attr(ds, k, v)
        if fps_summary:
            ds.attrs["fps_summary_json"] = json.dumps(fps_summary, separators=(",", ":"))

        pts_n = 0
        if pts_path is not None and Path(pts_path).is_file():
            pts = _load_pts_ms(Path(pts_path))
            pts_n = len(pts)
            if pts_name in video:
                del video[pts_name]
            if pts_n:
                # Relative to first stamp in this part (grill: pts relative).
                rel = pts - pts[0]
                pds = video.create_dataset(pts_name, data=rel.astype(np.float64))
                pds.attrs["description"] = _DESC["pts"]
                pds.attrs["part"] = int(part)
                pds.attrs["unit"] = "ms_relative"
                pds.attrs["n"] = pts_n
                pds.attrs["t0_ms_abs"] = float(pts[0])
            to_delete.append(Path(pts_path))
        log.append(f"packed {name} bytes={ts_size} pts={pts_n}")

        # Verify before delete
        written = int(video[name].shape[0])
        if written != ts_size:
            return {
                "ok": False,
                "error": f"verify fail {name}: h5={written} ts={ts_size}",
                "log": log,
            }
        to_delete.append(ts_path)

        # --- part sidecars ---
        for kind, suffix, max_b in (
            ("capture", "_capture.log", _MAX_LOG_BYTES),
            ("remux", "_remux.log", _MAX_LOG_BYTES),
        ):
            side = folder_p / f"{stem}{suffix}"
            if not side.is_file():
                continue
            # Empty remux/capture is normal (quiet stderr) — do not pack, still
            # delete so the session folder is not littered.
            if side.stat().st_size <= 0:
                to_delete.append(side)
                log.append(f"skip empty {side.name} (delete)")
                continue
            ds_name = f"{kind}_{int(part):03d}"
            n = _pack_bytes_dataset(
                logs, ds_name, side, max_bytes=max_b, part=int(part), kind=kind
            )
            log.append(f"packed logs/{ds_name} bytes={n}")
            to_delete.append(side)

        fps_path = folder_p / f"{stem}_fps.json"
        if fps_path.is_file() and fps_path.stat().st_size > 0:
            try:
                raw = fps_path.read_text(encoding="utf-8", errors="replace")
                parsed = json.loads(raw)
                ds.attrs["fps_file_json"] = json.dumps(parsed, separators=(",", ":"))
                log.append(f"packed fps.json → mpegts attrs ({fps_path.name})")
                to_delete.append(fps_path)
            except (OSError, json.JSONDecodeError) as exc:
                log.append(f"warn fps.json: {exc}")

        if pack_session_sidecars:
            log.extend(
                _pack_session_sidecars(
                    f,
                    folder=folder_p,
                    cam_id=cam_id or str((attrs or {}).get("cam_id") or ""),
                    subject_id=subject_id
                    or str((attrs or {}).get("subject_id") or ""),
                    to_delete=to_delete,
                )
            )

    if delete_loose:
        for path in to_delete:
            try:
                path.unlink(missing_ok=True)
                log.append(f"deleted {path.name}")
            except OSError as exc:
                log.append(f"warn delete {path.name}: {exc}")

    return {
        "ok": True,
        "part": int(part),
        "bytes": ts_size,
        "h5": str(h5_path),
        "dataset": name,
        "log": log,
    }


def _pack_bytes_dataset(
    group: Any,
    name: str,
    path: Path,
    *,
    max_bytes: int,
    part: int | None = None,
    kind: str,
) -> int:
    raw = path.read_bytes()
    truncated = False
    if len(raw) > max_bytes:
        raw = raw[-max_bytes:]
        truncated = True
    if name in group:
        del group[name]
    if not raw:
        return 0
    ds = group.create_dataset(
        name,
        data=np.frombuffer(raw, dtype=np.uint8),
        chunks=(min(_COPY_CHUNK, len(raw)),),
    )
    ds.attrs["description"] = _DESC.get(kind, f"bhvr sidecar ({kind})")
    ds.attrs["kind"] = kind
    ds.attrs["source"] = path.name
    ds.attrs["encoding"] = "utf-8"
    ds.attrs["bytes"] = len(raw)
    ds.attrs["truncated"] = int(truncated)
    if part is not None:
        ds.attrs["part"] = int(part)
    return len(raw)


def _pack_session_sidecars(
    f: Any,
    *,
    folder: Path,
    cam_id: str,
    subject_id: str,
    to_delete: list[Path],
) -> list[str]:
    """Fold cam/session sidecars once (typically on Stop final pack)."""
    log: list[str] = []
    logs = f.require_group("logs")
    cam = _slug(cam_id) if cam_id else ""
    subj = _slug(subject_id) if subject_id else ""

    if subj and cam:
        env = folder / f"{subj}__{cam}_env.jsonl"
        if env.is_file() and env.stat().st_size > 0:
            n = _pack_bytes_dataset(
                logs, "env_jsonl", env, max_bytes=_MAX_ENV_BYTES, kind="env_jsonl"
            )
            log.append(f"packed logs/env_jsonl bytes={n}")
            to_delete.append(env)

    if cam:
        pts_full = folder / f".{cam}_pts_full.pts"
        if pts_full.is_file() and pts_full.stat().st_size > 0:
            n = _pack_bytes_dataset(
                logs,
                "pts_full",
                pts_full,
                max_bytes=_MAX_PTS_FULL_BYTES,
                kind="pts_full",
            )
            log.append(f"packed logs/pts_full bytes={n}")
            to_delete.append(pts_full)

    stop = folder / "stop_log.json"
    if stop.is_file() and stop.stat().st_size > 0:
        try:
            raw = stop.read_text(encoding="utf-8", errors="replace")
            parsed = json.loads(raw)
            f.attrs["stop_log_json"] = json.dumps(parsed, separators=(",", ":"))
            log.append("packed stop_log.json → root attr (loose kept)")
        except (OSError, json.JSONDecodeError) as exc:
            log.append(f"warn stop_log: {exc}")

    return log


def _copy_file_into_dataset(ds: Any, path: Path) -> None:
    off = 0
    with path.open("rb") as f:
        while True:
            buf = f.read(_COPY_CHUNK)
            if not buf:
                break
            n = len(buf)
            ds[off : off + n] = np.frombuffer(buf, dtype=np.uint8)
            off += n


def _load_pts_ms(path: Path) -> np.ndarray:
    vals: list[float] = []
    try:
        raw = path.read_bytes()
    except OSError:
        return np.asarray([], dtype=np.float64)
    if not raw or raw.count(0) > max(8, len(raw) // 4):
        return np.asarray([], dtype=np.float64)
    for line in raw.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "\x00" in line or "\ufffd" in line:
            continue
        try:
            vals.append(float(line))
        except ValueError:
            continue
    return np.asarray(vals, dtype=np.float64)


def _set_attr(obj: Any, key: str, value: Any) -> None:
    if value is None:
        return
    if isinstance(value, (dict, list)):
        obj.attrs[key] = json.dumps(value, separators=(",", ":"))
    elif isinstance(value, bool):
        obj.attrs[key] = int(value)
    elif isinstance(value, (int, float, str, bytes, np.ndarray)):
        obj.attrs[key] = value
    else:
        obj.attrs[key] = str(value)


def slice_pts_file(
    full_pts: Path,
    dest: Path,
    *,
    start_index: int,
) -> tuple[int, int]:
    """Write pts lines ``[start_index:]`` to ``dest``. Returns (n_written, next_index)."""
    pts = _load_pts_ms(full_pts)
    if start_index < 0:
        start_index = 0
    if start_index >= len(pts):
        dest.write_text("", encoding="utf-8")
        return 0, len(pts)
    chunk = pts[start_index:]
    dest.write_text(
        "\n".join(f"{x:.6f}" if x != int(x) else str(int(x)) for x in chunk) + "\n",
        encoding="utf-8",
    )
    return len(chunk), len(pts)
