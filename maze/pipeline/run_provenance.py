"""
JSON run provenance sidecars for pipeline, discovery sync, and kpMS jobs.

Writes timestamped records under ``<anchor>.parent/provenance/`` (or
``<anchor>/provenance/`` when *anchor* is a directory). Each record includes
git revision (when available), serializable inputs/outputs, and run status.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping

SCHEMA_VERSION = 1


def utc_now_iso(*, timespec: str = "seconds") -> str:
    return datetime.now(timezone.utc).isoformat(timespec=timespec)


def _compact_timestamp(iso: str) -> str:
    """Filesystem-safe fragment from an ISO timestamp."""
    return iso.replace(":", "").replace("+00:00", "Z")


def git_info(*, cwd: Path | None = None) -> dict[str, Any]:
    """
    Resolve HEAD commit and working-tree dirtiness.

    On failure, returns explicit nulls plus an ``error`` string (no silent omit).
    """
    root = cwd or Path(__file__).resolve().parents[2]
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        ).strip()
        dirty_rc = subprocess.run(
            ["git", "diff", "--quiet", "HEAD"],
            cwd=root,
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).returncode
        dirty = dirty_rc != 0
        describe = subprocess.check_output(
            ["git", "describe", "--always", "--dirty"],
            cwd=root,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        ).strip()
        return {
            "commit": commit,
            "dirty": dirty,
            "describe": describe,
            "error": None,
        }
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return {
            "commit": None,
            "dirty": None,
            "describe": None,
            "error": str(exc),
        }


def sha256_file(path: Path | str) -> str | None:
    """SHA-256 hex digest of a file, or ``None`` if missing/unreadable."""
    p = Path(path)
    if not p.is_file():
        return None
    digest = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return str(value)


def provenance_dir(anchor: Path) -> Path:
    """Directory for provenance JSON files associated with *anchor*."""
    anchor = Path(anchor)
    base = anchor.parent if anchor.suffix else anchor
    return base / "provenance"


def provenance_path(anchor: Path, operation: str, started_at: str) -> Path:
    stamp = _compact_timestamp(started_at)
    return provenance_dir(anchor) / f"{operation}_{stamp}.json"


def provenance_envelope(
    *,
    operation: str,
    inputs: Mapping[str, Any] | None = None,
    outputs: Mapping[str, Any] | None = None,
    status: str = "ok",
    error: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
) -> dict[str, Any]:
    """Build a provenance dict suitable for merging into summary JSON (e.g. kpMS)."""
    started = started_at or utc_now_iso()
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "operation": operation,
        "started_at": started,
        "finished_at": finished_at or utc_now_iso(),
        "status": status,
        "git": git_info(),
        "inputs": _json_safe(inputs or {}),
    }
    if outputs:
        record["outputs"] = _json_safe(outputs)
    if error:
        record["error"] = error
    return record


def write_provenance(anchor: Path, record: Mapping[str, Any]) -> Path:
    """Write *record* to a new JSON file; return the path written."""
    anchor = Path(anchor)
    started = str(record.get("started_at") or utc_now_iso())
    operation = str(record.get("operation") or "run")
    out_path = provenance_path(anchor, operation, started)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = _json_safe(dict(record))
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    return out_path


@contextmanager
def provenance_run(
    operation: str,
    anchor: Path,
    inputs: Mapping[str, Any],
) -> Iterator[dict[str, Any]]:
    """
    Context manager: yield a mutable record dict, then write provenance on exit.

    Sets ``status`` to ``failed`` and ``error`` on exception; re-raises afterward.
    """
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "operation": operation,
        "started_at": utc_now_iso(),
        "git": git_info(),
        "inputs": _json_safe(inputs),
        "outputs": {},
    }
    status = "ok"
    error: str | None = None
    try:
        yield record
    except Exception as exc:
        status = "failed"
        error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        record["finished_at"] = utc_now_iso()
        record["status"] = status
        if error:
            record["error"] = error
        write_provenance(anchor, record)


def record_provenance(
    *,
    anchor: Path,
    operation: str,
    inputs: Mapping[str, Any],
    outputs: Mapping[str, Any] | None = None,
    status: str = "ok",
    error: str | None = None,
    started_at: str | None = None,
) -> Path:
    """One-shot provenance write (e.g. GUI workers without a wrapping context)."""
    started = started_at or utc_now_iso()
    record = provenance_envelope(
        operation=operation,
        inputs=inputs,
        outputs=outputs,
        status=status,
        error=error,
        started_at=started,
        finished_at=utc_now_iso(),
    )
    return write_provenance(anchor, record)
