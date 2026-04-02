from __future__ import annotations

from pathlib import Path
from typing import Optional

import h5py

from maze.core.storage import (
    ensure_group as core_ensure_group,
    open_db as core_open_db,
    safe_str as core_safe_str,
    write_json_attr as core_write_json_attr,
)

from ..paths import OUTPUT_H5

ensure_group = core_ensure_group
safe_str = core_safe_str
write_json_attr = core_write_json_attr


def open_db(db_path: Optional[Path] = None, mode: str = "a") -> h5py.File:
    """Open the HDF5 database file using shared ``maze.core.storage.open_db``."""
    path = db_path or OUTPUT_H5
    return core_open_db(Path(path), mode)
