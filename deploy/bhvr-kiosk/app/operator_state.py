"""Persisted kiosk operator knobs + per-cam metadata (grill 2026-10-22)."""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any

from app.encode_ask import (
    DEFAULT_SCIENCE_FPS,
    DEFAULT_SCIENCE_SIZE,
    bitrate_for,
    encode_ask,
    normalize_science_size,
    normalize_soft_fps,
)

_lock = threading.Lock()
_STATE_NAME = ".kiosk_operator.json"

CHUNK_DEFAULT_LITE_MIN = 20
CHUNK_DEFAULT_STANDARD_MIN = 5


def _state_path(data_root: Path) -> Path:
    return data_root / _STATE_NAME


def default_operator_state() -> dict[str, Any]:
    return {
        "profile": DEFAULT_SCIENCE_SIZE,
        "soft_fps": DEFAULT_SCIENCE_FPS,
        "output_subdir": "",
        # 0 = no limit; else minutes per TS part before roll (Lite default).
        "chunk_minutes": CHUNK_DEFAULT_LITE_MIN,
        "cameras": {},  # cam_id -> {subject_id, cage_id, sex, strain, notes}
    }


def _normalize_cam_meta(raw: dict[str, Any] | None) -> dict[str, str]:
    row = raw if isinstance(raw, dict) else {}
    sex = str(row.get("sex") or "U").strip().upper()[:1]
    if sex not in ("M", "F", "U"):
        sex = "U"
    return {
        "subject_id": str(row.get("subject_id") or "").strip(),
        "cage_id": str(row.get("cage_id") or "").strip(),
        "sex": sex,
        "strain": str(row.get("strain") or "").strip(),
        "notes": str(row.get("notes") or "").strip(),
    }


def load_operator_state(data_root: Path) -> dict[str, Any]:
    path = _state_path(data_root)
    base = default_operator_state()
    if not path.is_file():
        return base
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return base
    if not isinstance(raw, dict):
        return base
    out = default_operator_state()
    out["profile"] = normalize_science_size(raw.get("profile"))
    out["soft_fps"] = normalize_soft_fps(raw.get("soft_fps"))
    sub = str(raw.get("output_subdir") or "").strip().replace("\\", "/")
    sub = re.sub(r"^/+", "", sub)
    if ".." in sub.split("/"):
        sub = ""
    out["output_subdir"] = sub
    try:
        chunk = int(raw.get("chunk_minutes", out["chunk_minutes"]))
    except (TypeError, ValueError):
        chunk = out["chunk_minutes"]
    out["chunk_minutes"] = max(0, min(24 * 60, chunk))
    cams_in = raw.get("cameras") if isinstance(raw.get("cameras"), dict) else {}
    cams: dict[str, dict[str, str]] = {}
    for cam_id, meta in cams_in.items():
        cams[str(cam_id)] = _normalize_cam_meta(meta if isinstance(meta, dict) else {})
    out["cameras"] = cams
    return out


def save_operator_state(data_root: Path, state: dict[str, Any]) -> dict[str, Any]:
    normalized = load_operator_state(data_root)  # start from defaults
    normalized["profile"] = normalize_science_size(state.get("profile"))
    normalized["soft_fps"] = normalize_soft_fps(state.get("soft_fps"))
    sub = str(state.get("output_subdir") or "").strip().replace("\\", "/")
    sub = re.sub(r"^/+", "", sub)
    if ".." in Path(sub).parts:
        raise ValueError("output_subdir must stay under data_root")
    normalized["output_subdir"] = sub
    try:
        chunk = int(state.get("chunk_minutes", normalized["chunk_minutes"]))
    except (TypeError, ValueError) as exc:
        raise ValueError("chunk_minutes must be an integer (0 = no limit)") from exc
    normalized["chunk_minutes"] = max(0, min(24 * 60, chunk))
    cams_in = state.get("cameras") if isinstance(state.get("cameras"), dict) else normalized["cameras"]
    cams: dict[str, dict[str, str]] = {}
    for cam_id, meta in cams_in.items():
        cams[str(cam_id)] = _normalize_cam_meta(meta if isinstance(meta, dict) else {})
    normalized["cameras"] = cams
    path = _state_path(data_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        path.write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")
    return normalized


def patch_cam_meta(
    data_root: Path, cam_id: str, patch: dict[str, Any], *, freeze_subject: bool
) -> dict[str, str]:
    state = load_operator_state(data_root)
    cams = dict(state.get("cameras") or {})
    cur = _normalize_cam_meta(cams.get(cam_id))
    nxt = _normalize_cam_meta({**cur, **patch})
    if freeze_subject:
        nxt["subject_id"] = cur["subject_id"]
    cams[cam_id] = nxt
    state["cameras"] = cams
    save_operator_state(data_root, state)
    return nxt


def chunk_preset_minutes(profile: str) -> int:
    size = normalize_science_size(profile)
    return CHUNK_DEFAULT_LITE_MIN if size == "lite" else CHUNK_DEFAULT_STANDARD_MIN


def storage_health(data_root: Path) -> dict[str, Any]:
    """SSD / data_root mount check for Session settings + Start gate."""
    root = data_root
    exists = root.exists()
    is_dir = root.is_dir() if exists else False
    writable = False
    free_bytes: int | None = None
    if is_dir:
        try:
            probe = root / ".kiosk_write_probe"
            probe.write_text("ok\n", encoding="utf-8")
            probe.unlink(missing_ok=True)
            writable = True
        except OSError:
            writable = False
        try:
            import shutil

            free_bytes = int(shutil.disk_usage(str(root)).free)
        except OSError:
            free_bytes = None
    mounted = exists and is_dir and writable
    return {
        "data_root": str(root),
        "exists": exists,
        "is_dir": is_dir,
        "writable": writable,
        "mounted": mounted,
        "free_bytes": free_bytes,
        "free_gb": round(free_bytes / (1024**3), 2) if free_bytes is not None else None,
    }


def list_output_subdirs(data_root: Path) -> list[str]:
    """Immediate child directories under data_root (for subdir picker)."""
    if not data_root.is_dir():
        return []
    out: list[str] = []
    try:
        for p in sorted(data_root.iterdir()):
            if p.is_dir() and not p.name.startswith("."):
                out.append(p.name)
    except OSError:
        return []
    return out


def estimate_gb_per_hour(profile: str, soft_fps: int, n_cams: int) -> dict[str, Any]:
    ask = encode_ask(profile, soft_fps)
    n = max(0, int(n_cams))
    bytes_per_s = (ask.bitrate_bps / 8.0) * n
    gb_h = (bytes_per_s * 3600.0) / (1024**3)
    return {
        "bitrate_kbps_per_cam": ask.bitrate_kbps,
        "n_cams": n,
        "gb_per_hour": round(gb_h, 2),
        "science_ask": ask.label,
        "table_bitrate": True,
        "note": "pre-start estimate from encode bitrate table; REC uses write_Bps",
    }


def session_folder(data_root: Path, output_subdir: str, start_utc_name: str) -> Path:
    """ses-<utc> under data_root[/subdir] — grill Q14=B."""
    sub = (output_subdir or "").strip().replace("\\", "/")
    sub = re.sub(r"^/+", "", sub)
    base = data_root / sub if sub else data_root
    return base / f"ses-{start_utc_name}"
