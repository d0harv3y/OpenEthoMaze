"""Rotatable MPEG-TS sink for science capture (chunk roll without restarting SSH)."""

from __future__ import annotations

import threading
from pathlib import Path


class CaptureSink:
    """Thread-safe write target; ``rotate`` swaps the open file under lock."""

    def __init__(self, path: Path) -> None:
        self._lock = threading.Lock()
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._f = self.path.open("wb")
        self._closed = False

    def write(self, data: bytes) -> int:
        with self._lock:
            if self._closed:
                return 0
            n = self._f.write(data)
            return int(n)

    def flush(self) -> None:
        with self._lock:
            if not self._closed:
                self._f.flush()

    def rotate(self, new_path: Path) -> Path:
        """Close current file, open ``new_path``. Returns the closed path."""
        new_path = Path(new_path)
        new_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            if self._closed:
                raise RuntimeError("sink already closed")
            old = self.path
            self._f.flush()
            self._f.close()
            self.path = new_path
            self._f = new_path.open("wb")
            return old

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            try:
                self._f.flush()
                self._f.close()
            finally:
                self._closed = True
