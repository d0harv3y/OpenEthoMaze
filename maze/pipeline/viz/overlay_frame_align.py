"""Map pipeline / pose tables to unified-overlay source video frames."""

from __future__ import annotations

import numpy as np


def xy_source_frame_indices(xy_full: np.ndarray) -> np.ndarray:
    """Per-row source video frame numbers from an ambulation ``xy`` table."""
    n_xy = len(xy_full)
    if n_xy == 0:
        return np.zeros(0, dtype=np.int64)
    names = xy_full.dtype.names or ()
    if "frame_index" in names:
        return np.asarray(xy_full["frame_index"], dtype=np.int64).ravel()
    return np.arange(n_xy, dtype=np.int64)


def source_frame_exclusive_end(fi_rows: np.ndarray, *, n_vid: int) -> int:
    """Exclusive upper bound on addressable source video frames."""
    if fi_rows.size == 0:
        return 0
    end = int(fi_rows[-1]) + 1
    if n_vid > 0:
        return min(int(n_vid), end)
    return end


def xy_rows_for_source_frames(
    fi_rows: np.ndarray,
    n_xy: int,
    render_start_frame: int,
    max_frames: int,
) -> np.ndarray:
    """Map each overlay frame to a table row for source video frame ``render_start_frame + i``."""
    rows = np.full(max_frames, -1, dtype=np.int64)
    for i in range(max_frames):
        vf = int(render_start_frame + i)
        pos = int(np.searchsorted(fi_rows, vf, side="left"))
        if pos < n_xy and int(fi_rows[pos]) == vf:
            rows[i] = pos
        elif pos > 0 and int(fi_rows[pos - 1]) == vf:
            rows[i] = pos - 1
    return rows


def sample_xy_table_rows(xy_full: np.ndarray, rows: np.ndarray) -> np.ndarray:
    """Build per-overlay-frame ``xy`` rows; unmapped frames are invalid."""
    n = len(rows)
    out = np.zeros(n, dtype=xy_full.dtype)
    names = xy_full.dtype.names or ()
    if "valid" in names:
        out["valid"][:] = 0
    if "is_moving" in names:
        out["is_moving"][:] = 0
    if "x" in names:
        out["x"][:] = np.nan
    if "y" in names:
        out["y"][:] = np.nan
    ok = rows >= 0
    if np.any(ok):
        out[ok] = xy_full[rows[ok]]
    return out
