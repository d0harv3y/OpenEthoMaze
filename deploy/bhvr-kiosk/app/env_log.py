"""Append HTU21D window stats to per-cam JSONL while a session is active."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", s.strip()).strip("-") or "unknown"


def _stats_block(raw: Any) -> dict[str, float] | None:
    if not isinstance(raw, dict):
        return None
    try:
        return {
            "min": round(float(raw["min"]), 1),
            "max": round(float(raw["max"]), 1),
            "mean": round(float(raw["mean"]), 1),
        }
    except (KeyError, TypeError, ValueError):
        return None


def append_env_jsonl(
    *,
    active_path: Path,
    cam_id: str,
    ts: str | None,
    env: dict[str, Any] | None = None,
    temp_c: float | None = None,
    rh_pct: float | None = None,
    load_operator_cameras: Callable[[], dict[str, Any]] | None = None,
) -> Path | None:
    """Append one line to ``{subject}__{cam}_env.jsonl`` or return None if idle.

    Prefer ``env`` window stats from the cam announce::

        {"n": 10, "temp_c": {"min","max","mean"}, "rh_pct": {...}? }

    Legacy scalar ``temp_c`` / ``rh_pct`` (means only) still accepted: written as
    min=max=mean for that point.
    """
    if not active_path.is_file():
        return None
    try:
        active = json.loads(active_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    meta = active.get("meta") or {}
    camera_ids = meta.get("camera_ids") or []
    if cam_id not in camera_ids:
        return None
    folder_s = active.get("folder")
    if not folder_s:
        return None
    folder = Path(folder_s)
    cams_meta = meta.get("cameras") or {}
    subject = str((cams_meta.get(cam_id) or {}).get("subject_id") or "").strip()
    if not subject and load_operator_cameras is not None:
        subject = str((load_operator_cameras().get(cam_id) or {}).get("subject_id") or "").strip()
    if not subject:
        subject = str(meta.get("subject_id") or "unknown")

    line: dict[str, Any] = {
        "ts": ts or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if isinstance(env, dict):
        n = env.get("n")
        try:
            line["n"] = int(n) if n is not None else None
        except (TypeError, ValueError):
            line["n"] = None
        t_block = _stats_block(env.get("temp_c"))
        if t_block is None:
            return None
        line["temp_c"] = t_block
        r_block = _stats_block(env.get("rh_pct"))
        if r_block is not None:
            line["rh_pct"] = r_block
    elif temp_c is not None:
        t = round(float(temp_c), 1)
        line["n"] = 1
        line["temp_c"] = {"min": t, "max": t, "mean": t}
        if rh_pct is not None:
            r = round(float(rh_pct), 1)
            line["rh_pct"] = {"min": r, "max": r, "mean": r}
    else:
        return None

    out = folder / f"{slug(subject)}__{slug(cam_id)}_env.jsonl"
    folder.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, separators=(",", ":")) + "\n")
    return out
