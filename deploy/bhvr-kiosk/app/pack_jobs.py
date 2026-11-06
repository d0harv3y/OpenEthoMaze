"""Final-session H5 pack queue (Round A Stop S2+).

Stop clears the science session quickly; packs run in background.
Start is gated while any job is pending/running.
"""

from __future__ import annotations

import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

_lock = threading.Lock()
# job_id -> row
_jobs: dict[str, dict[str, Any]] = {}


def pending() -> bool:
    with _lock:
        return any(j.get("status") in ("pending", "running") for j in _jobs.values())


def snapshot() -> dict[str, Any]:
    with _lock:
        jobs = [dict(j) for j in _jobs.values()]
    # Newest first for UI.
    jobs.sort(key=lambda j: float(j.get("created_at") or 0), reverse=True)
    active = [j for j in jobs if j.get("status") in ("pending", "running")]
    done_ok = sum(1 for j in jobs if j.get("status") == "ok")
    done_fail = sum(1 for j in jobs if j.get("status") == "fail")
    total = len(jobs)
    finished = done_ok + done_fail
    if active:
        label = f"PACK {finished}/{total}"
        state = "packing"
    elif done_fail and total:
        label = f"PACK fail {done_fail}/{total}"
        state = "fail"
    elif total and finished == total:
        label = f"PACK OK {total}/{total}"
        state = "ok"
    else:
        label = ""
        state = "idle"
    return {
        "pending": bool(active),
        "state": state,
        "label": label,
        "total": total,
        "finished": finished,
        "ok": done_ok,
        "fail": done_fail,
        "jobs": jobs[:40],
    }


def clear_finished() -> None:
    """Drop completed jobs (banner idle). Keeps pending/running."""
    with _lock:
        dead = [
            jid
            for jid, j in _jobs.items()
            if j.get("status") not in ("pending", "running")
        ]
        for jid in dead:
            _jobs.pop(jid, None)


def enqueue(
    *,
    cam_id: str,
    folder: str,
    h5_path: Path,
    part: int,
    ts_path: Path,
    pts_path: Path | None,
    fps_summary: dict[str, Any] | None,
    attrs: dict[str, Any],
    pack_fn: Callable[..., dict[str, Any]],
    subject_id: str | None = None,
    pack_session_sidecars: bool = True,
    skip_if_exists: bool = False,
) -> str:
    """Queue one final-part pack. ``pack_fn`` is ``h5_archive.pack_part``."""
    job_id = uuid.uuid4().hex[:12]
    row: dict[str, Any] = {
        "id": job_id,
        "cam_id": cam_id,
        "folder": folder,
        "h5_path": str(h5_path),
        "part": int(part),
        "ts_path": str(ts_path),
        "status": "pending",
        "error": "",
        "bytes": None,
        "skipped": False,
        "created_at": time.time(),
        "finished_at": None,
    }
    with _lock:
        _jobs[job_id] = row

    def _run() -> None:
        with _lock:
            cur = _jobs.get(job_id)
            if cur is not None:
                cur["status"] = "running"
        try:
            result = pack_fn(
                h5_path,
                part=part,
                ts_path=ts_path,
                pts_path=pts_path,
                fps_summary=fps_summary,
                attrs=attrs,
                delete_loose=True,
                folder=folder,
                cam_id=cam_id,
                subject_id=subject_id or str(attrs.get("subject_id") or ""),
                pack_session_sidecars=pack_session_sidecars,
                skip_if_exists=skip_if_exists,
            )
            ok = bool(result.get("ok"))
            with _lock:
                cur = _jobs.get(job_id)
                if cur is None:
                    return
                cur["status"] = "ok" if ok else "fail"
                cur["error"] = "" if ok else str(result.get("error") or "pack failed")
                cur["bytes"] = result.get("bytes")
                cur["skipped"] = bool(result.get("skipped"))
                cur["finished_at"] = time.time()
        except Exception as exc:  # noqa: BLE001
            with _lock:
                cur = _jobs.get(job_id)
                if cur is None:
                    return
                cur["status"] = "fail"
                cur["error"] = repr(exc)
                cur["finished_at"] = time.time()

    threading.Thread(
        target=_run, name=f"bhvr-final-pack-{cam_id}-{job_id}", daemon=True
    ).start()
    return job_id
