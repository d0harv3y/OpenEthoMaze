from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np

from maze.core.schema import FEEDBACK_GROUP, FEEDBACK_ROW_DTYPE
from maze.core.h5_layout import (
    read_feedback_table as core_read_feedback_table,
    write_feedback_table as core_write_feedback_table,
)

from ._shared import ensure_group, open_db
from .trial_key import TrialKey


def write_feedback_series(
    db_path: Optional[Path],
    key: TrialKey,
    w: np.ndarray,
    m: np.ndarray,
    trial_start_frame: Optional[int] = None,
) -> None:
    """Write legacy W/M feedback series into the unified feedback table."""
    w = np.asarray(w, dtype=np.float32)
    m = np.asarray(m, dtype=np.float32)
    if len(w) != len(m):
        raise ValueError("write_feedback_series: w and m must have the same length")
    n = len(m)
    if n == 0:
        return
    fb = np.zeros(n, dtype=FEEDBACK_ROW_DTYPE)
    fb["frame_index"] = np.arange(n, dtype=np.uint32)
    if trial_start_frame is not None and 0 < trial_start_frame < n:
        fb["trial_state"][:trial_start_frame] = b"iti_wait"
        fb["trial_state"][trial_start_frame:] = b"run"
    else:
        fb["trial_state"] = b"run"
    fb["motor_fb"] = m
    fb["light_fb"] = w
    fb["sound_fb"] = 0.0
    with open_db(db_path, "a") as h5:
        core_write_feedback_table(h5[key.path()], fb)


def read_feedback_series(
    db_path: Optional[Path],
    key: TrialKey,
) -> Optional[tuple[np.ndarray, np.ndarray]]:
    """Read feedback W and M series for a trial."""
    try:
        with open_db(db_path, "r") as h5:
            g_trial = h5[key.path()]
            g_fb = g_trial.get(FEEDBACK_GROUP)
            if g_fb is None:
                return None
            fb_table = core_read_feedback_table(g_trial)
            if fb_table is not None:
                m = np.asarray(fb_table["motor_fb"], dtype=np.float64)
                if "light_fb" in fb_table.dtype.names:
                    w = np.asarray(fb_table["light_fb"], dtype=np.float64)
                else:
                    w = np.zeros_like(m)
                return (w, m)
            if "w" in g_fb and "m" in g_fb:
                w = np.asarray(g_fb["w"][:], dtype=np.float64)
                m = np.asarray(g_fb["m"][:], dtype=np.float64)
                return (w, m)
            return None
    except (KeyError, ValueError, OSError):
        return None


def write_feedback_error_summary(
    db_path: Optional[Path],
    key: TrialKey,
    n_incongruent_bouts: int,
    incongruent_duration_s: float,
) -> None:
    """Write feedback incongruence summary attrs on the trial feedback group."""
    with open_db(db_path, "a") as h5:
        g_fb = ensure_group(h5[key.path()], FEEDBACK_GROUP)
        g_fb.attrs["n_incongruent_bouts"] = int(n_incongruent_bouts)
        g_fb.attrs["incongruent_duration_s"] = float(incongruent_duration_s)
