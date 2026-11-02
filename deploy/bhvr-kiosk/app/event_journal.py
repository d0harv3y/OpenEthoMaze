"""Operator event journal — interaction + consequence breadcrumbs for kiosk debug.

One **page-session** = one browser load (client UUID). Events are JSONL under
``data_root/.kiosk_journals/``. Retention: max sessions + max bytes per file;
oversized sessions mark ``rotate_suggested`` so the UI can soft-reload.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_lock = threading.Lock()

MAX_SESSIONS = 24
MAX_SESSION_BYTES = 400_000  # ~400 KiB → UI may reload to start a fresh page-session
JOURNAL_DIRNAME = ".kiosk_journals"


def journal_root(data_root: Path) -> Path:
    return Path(data_root) / JOURNAL_DIRNAME


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _session_path(root: Path, session_id: str) -> Path:
    safe = "".join(c for c in session_id if c.isalnum() or c in "-_")[:80] or "anon"
    return root / f"{safe}.jsonl"


def _prune(root: Path) -> None:
    if not root.is_dir():
        return
    files = sorted(
        [p for p in root.glob("*.jsonl") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in files[MAX_SESSIONS:]:
        try:
            old.unlink()
        except OSError:
            pass
    meta = root / "index.json"
    try:
        meta.write_text(
            json.dumps(
                {
                    "updated_utc": _utc(),
                    "max_sessions": MAX_SESSIONS,
                    "max_session_bytes": MAX_SESSION_BYTES,
                    "sessions": [
                        {
                            "id": p.stem,
                            "bytes": p.stat().st_size,
                            "mtime": p.stat().st_mtime,
                        }
                        for p in files[:MAX_SESSIONS]
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def append_event(
    data_root: Path,
    *,
    session_id: str,
    kind: str,
    detail: dict[str, Any] | None = None,
    source: str = "server",
) -> dict[str, Any]:
    """Append one event. Returns ``{ok, bytes, rotate_suggested}``."""
    root = journal_root(data_root)
    root.mkdir(parents=True, exist_ok=True)
    path = _session_path(root, session_id)
    row = {
        "ts": _utc(),
        "mono": round(time.monotonic(), 3),
        "source": source,
        "kind": str(kind)[:80],
        "detail": detail or {},
    }
    line = json.dumps(row, ensure_ascii=False, default=str) + "\n"
    with _lock:
        try:
            with path.open("a", encoding="utf-8", newline="\n") as f:
                f.write(line)
            size = path.stat().st_size
        except OSError as exc:
            return {"ok": False, "error": str(exc), "bytes": 0, "rotate_suggested": False}
        _prune(root)
    return {
        "ok": True,
        "bytes": size,
        "rotate_suggested": size >= MAX_SESSION_BYTES,
        "session_id": path.stem,
        "path": str(path),
    }


def recent_events(
    data_root: Path, *, session_id: str | None = None, limit: int = 80
) -> dict[str, Any]:
    root = journal_root(data_root)
    if session_id:
        path = _session_path(root, session_id)
    else:
        files = sorted(
            [p for p in root.glob("*.jsonl") if p.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        path = files[0] if files else None
    if path is None or not path.is_file():
        return {"session_id": session_id, "events": [], "bytes": 0}
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return {"session_id": path.stem, "events": [], "error": str(exc), "bytes": 0}
    events = []
    for ln in lines[-max(1, int(limit)) :]:
        try:
            events.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return {
        "session_id": path.stem,
        "bytes": path.stat().st_size,
        "rotate_suggested": path.stat().st_size >= MAX_SESSION_BYTES,
        "events": events,
    }
