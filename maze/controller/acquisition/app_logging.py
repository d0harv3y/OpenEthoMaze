"""
Hybrid app logging: file (DEBUG + ERROR, one file per run) and in-memory for the GUI.

- File: one new log file per app instance (timestamped), DEBUG level.
- In-memory: kept in MainWindow for "View error log" dialog.
- Rotates with app instance = new file each time the app starts.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

LOG_NAME = "maze_acquisition"
_current_log_path: Optional[Path] = None

# Log directory: Windows LOCALAPPDATA/Maze Acquisition/logs, else ~/.maze_acquisition/logs
def _log_dir() -> Path:
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        base = Path(os.environ["LOCALAPPDATA"]) / "Maze Acquisition"
    else:
        base = Path.home() / ".maze_acquisition"
    log_dir = base / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def init_app_logging(debug_log: bool = False) -> Optional[Path]:
    """
    Initialize file logging for this app instance. One new log file per run.

    When debug_log is False (default), only INFO and above are written to the file.
    When debug_log is True, DEBUG is also written.
    Returns the path to the log file, or None if setup failed.
    """
    try:
        log_dir = _log_dir()
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
            if isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", "").endswith(".log"):
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
    return _log_dir()


def log_error(message: str) -> None:
    """Log an ERROR to the file logger (and optionally to in-memory via GUI)."""
    logging.getLogger(LOG_NAME).error("%s", message)


def log_debug(message: str) -> None:
    """Log DEBUG to the file logger."""
    logging.getLogger(LOG_NAME).debug("%s", message)
