from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np

from maze.core.schema import XY_ROW_DTYPE
from maze.core.h5_layout import (
    resolve_ambulation_metrics_group,
    write_xy_table as core_write_xy_table,
)

from ._shared import open_db
from .trial_key import TrialKey


def xy_table_dtype() -> np.dtype:
    """Structured dtype for XY position table (shared maze.core schema)."""
    return XY_ROW_DTYPE


def write_xy_table(
    db_path: Optional[Path],
    key: TrialKey,
    point_name: str,
    xy_table: np.ndarray,
    fps: float,
) -> None:
    """Write one XY position table to database."""
    with open_db(db_path, "a") as h5:
        core_write_xy_table(h5[key.path()], point_name, xy_table, fps)


def read_xy_table(
    db_path: Optional[Path],
    key: TrialKey,
    point_name: str,
) -> Optional[np.ndarray]:
    """Read XY table for a tracking point."""
    try:
        with open_db(db_path, "r") as h5:
            g_trial = h5[key.path()]
            g_amb = resolve_ambulation_metrics_group(g_trial)
            if g_amb is None:
                return None
            return g_amb[point_name]["xy"][:]
    except (KeyError, ValueError):
        return None
