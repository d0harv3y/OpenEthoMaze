"""
Hybrid app logging: file (DEBUG + ERROR, one file per run) and in-memory for the GUI.

Directory selection (in order):

1. ``MAZE_ACQ_LOG_DIR`` — if set, all log files go here (always wins).
2. ``MAZE_ACQ_USE_APPDATA_LOGS=1`` — use the installed-app style directory
   (Windows: ``%LOCALAPPDATA%/Maze Acquisition/logs``, else ``~/.maze_acquisition/logs``).
3. **Dev default**: if the current working directory (or executable directory) is under a
   checkout whose ``pyproject.toml`` declares project name ``maze``, use
   ``<that repo>/logs/acquisition/``.
4. Otherwise fall back to the AppData-style path (safest default for distributed builds).

Before each new run file is created, older ``maze_acquisition_*.log`` files in that directory
are trimmed to keep at most ``MAZE_ACQ_LOG_KEEP`` (default 3).

For production releases, prefer forcing AppData (or an explicit ``MAZE_ACQ_LOG_DIR``) so logs
never land in a source tree on end-user machines.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

LOG_NAME = "maze_acquisition"
_current_log_path: Optional[Path] = None


def _truthy(val: str | None) -> bool:
    if val is None:
        return False
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _is_maze_pyproject(path: Path) -> bool:
    try:
        import tomllib

        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return False
    except Exception:
        return False
    proj = data.get("project")
    if not isinstance(proj, dict):
        return False
    return str(proj.get("name", "")).strip().lower() == "maze"


def _find_maze_repo_root() -> Optional[Path]:
    """Walk parents from cwd and from argv[0] looking for a ``maze`` ``pyproject.toml``."""
    candidates: list[Path] = []
    try:
        candidates.append(Path.cwd())
    except OSError:
        pass
    if getattr(sys, "argv", None):
        try:
            exe = Path(sys.argv[0]).resolve()
            if exe.is_file():
                candidates.append(exe.parent)
            else:
                candidates.append(exe)
        except OSError:
            pass
    seen: set[Path] = set()
    for start in candidates:
        try:
            cur = start.resolve()
        except OSError:
            continue
        for _ in range(28):
            if cur in seen:
                break
            seen.add(cur)
            pp = cur / "pyproject.toml"
            if pp.is_file() and _is_maze_pyproject(pp):
                return cur
            parent = cur.parent
            if parent == cur:
                break
            cur = parent
    return None


def _appdata_log_dir() -> Path:
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        base = Path(os.environ["LOCALAPPDATA"]) / "Maze Acquisition"
    else:
        base = Path.home() / ".maze_acquisition"
    log_dir = base / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _log_dir() -> Path:
    override = (os.environ.get("MAZE_ACQ_LOG_DIR") or "").strip()
    if override:
        log_dir = Path(override)
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir
    if _truthy(os.environ.get("MAZE_ACQ_USE_APPDATA_LOGS")):
        return _appdata_log_dir()
    root = _find_maze_repo_root()
    if root is not None:
        log_dir = root / "logs" / "acquisition"
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir
    return _appdata_log_dir()


def _prune_old_logs(log_dir: Path, keep: int) -> None:
    keep = max(1, int(keep))
    files = sorted(log_dir.glob("maze_acquisition_*.log"), key=lambda p: p.stat().st_mtime)
    while len(files) >= keep:
        oldest = files.pop(0)
        try:
            oldest.unlink(missing_ok=True)
        except OSError:
            break


def init_app_logging(debug_log: bool = False) -> Optional[Path]:
    """
    Initialize file logging for this app instance. One new log file per run.

    When debug_log is False (default), only INFO and above are written to the file.
    When debug_log is True, DEBUG is also written.
    Returns the path to the log file, or None if setup failed.
    """
    try:
        log_dir = _log_dir()
        try:
            keep_n = int(os.environ.get("MAZE_ACQ_LOG_KEEP", "3"))
        except ValueError:
            keep_n = 3
        _prune_old_logs(log_dir, keep_n)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = log_dir / f"maze_acquisition_{timestamp}.log"
        handler = logging.FileHandler(log_path, encoding="utf-8")
        file_level = logging.DEBUG if debug_log else logging.INFO
        handler.setLevel(file_level)
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger = logging.getLogger(LOG_NAME)
        logger.setLevel(file_level)
        # Avoid duplicate handlers if init is called more than once
        for h in logger.handlers[:]:
            if isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", "").endswith(
                ".log"
            ):
                logger.removeHandler(h)
        logger.addHandler(handler)
        global _current_log_path
        _current_log_path = log_path
        if debug_log:
            logger.debug("Log file started for this app instance (debug log enabled): %s", log_path)
        else:
            logger.info("Log file started for this app instance: %s", log_path)
        return log_path
    except Exception:
        return None


def get_current_log_path() -> Optional[Path]:
    """Path to the log file for this app instance, or None if file logging was not initialized."""
    return _current_log_path


def get_log_dir() -> Path:
    """Return the directory used for log files (e.g. for 'Open log folder')."""
    if _current_log_path is not None:
        return _current_log_path.parent
    return _log_dir()


def log_error(message: str) -> None:
    """Log an ERROR to the file logger (and optionally to in-memory via GUI)."""
    logging.getLogger(LOG_NAME).error("%s", message)


def log_debug(message: str) -> None:
    """Log DEBUG to the file logger."""
    logging.getLogger(LOG_NAME).debug("%s", message)
