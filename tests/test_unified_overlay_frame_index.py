"""Frame-index alignment for unified overlay trajectory sampling."""

from __future__ import annotations

import numpy as np

from maze.core.schema import XY_ROW_DTYPE
from maze.pipeline.viz.overlay_frame_align import (
    sample_xy_table_rows,
    source_frame_exclusive_end,
    xy_rows_for_source_frames,
    xy_source_frame_indices,
)


def _xy_table(frame_indices: list[int], xs: list[float]) -> np.ndarray:
    rows = np.zeros(len(frame_indices), dtype=XY_ROW_DTYPE)
    for i, (fi, x) in enumerate(zip(frame_indices, xs, strict=True)):
        rows[i]["frame_index"] = fi
        rows[i]["x"] = x
        rows[i]["y"] = float(i)
        rows[i]["valid"] = 1
    return rows


def test_xy_rows_map_source_frame_not_row_index() -> None:
    xy = _xy_table([500, 501, 502], [10.0, 11.0, 12.0])
    fi = xy_source_frame_indices(xy)
    rows = xy_rows_for_source_frames(fi, len(xy), render_start_frame=500, max_frames=2)
    assert list(rows) == [0, 1]
    sampled = sample_xy_table_rows(xy, rows)
    assert sampled["x"][0] == 10.0
    assert sampled["x"][1] == 11.0


def test_dense_frame_index_matches_legacy_slice() -> None:
    xy = _xy_table([0, 1, 2, 3], [1.0, 2.0, 3.0, 4.0])
    fi = xy_source_frame_indices(xy)
    rows = xy_rows_for_source_frames(fi, len(xy), render_start_frame=1, max_frames=2)
    assert list(rows) == [1, 2]
    assert list(sample_xy_table_rows(xy, rows)["x"]) == [2.0, 3.0]


def test_source_frame_exclusive_end_uses_last_frame_index() -> None:
    fi = np.array([100, 101, 102], dtype=np.int64)
    assert source_frame_exclusive_end(fi, n_vid=0) == 103
    assert source_frame_exclusive_end(fi, n_vid=200) == 103
    assert source_frame_exclusive_end(fi, n_vid=102) == 102
