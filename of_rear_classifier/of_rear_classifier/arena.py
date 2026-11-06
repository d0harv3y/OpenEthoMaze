"""Arena membership for P1/P2 (floor-quad vertices)."""

from __future__ import annotations

from pathlib import Path

import numpy as np


def point_in_polygon(xy: np.ndarray, vertices_xy: np.ndarray) -> np.ndarray:
    """Ray-cast point-in-polygon for ``xy`` ``(T, 2)`` and cyclic ``vertices`` ``(N, 2)``."""
    pts = np.asarray(xy, dtype=np.float64)
    verts = np.asarray(vertices_xy, dtype=np.float64)
    if pts.ndim != 2 or pts.shape[1] != 2:
        raise ValueError(f"xy must be (T, 2), got {pts.shape}")
    if verts.ndim != 2 or verts.shape[1] != 2 or verts.shape[0] < 3:
        raise ValueError(f"vertices must be (N≥3, 2), got {verts.shape}")

    x, y = pts[:, 0], pts[:, 1]
    n = verts.shape[0]
    inside = np.zeros(pts.shape[0], dtype=bool)
    j = n - 1
    for i in range(n):
        xi, yi = verts[i, 0], verts[i, 1]
        xj, yj = verts[j, 0], verts[j, 1]
        intersect = ((yi > y) != (yj > y)) & (x < (xj - xi) * (y - yi) / (yj - yi + 1e-15) + xi)
        inside ^= intersect
        j = i
    return inside.astype(np.float64)


def load_floor_quad_vertices(csv_path: Path | str, video_stem: str) -> np.ndarray:
    """Load ``(4, 2)`` vertices for ``video_stem`` from ``floor_quads.csv``."""
    import pandas as pd

    path = Path(csv_path)
    df = pd.read_csv(path)
    if "video_stem" not in df.columns:
        raise KeyError(f"{path}: missing video_stem column")
    rows = df.loc[df["video_stem"].astype(str) == str(video_stem)]
    if rows.empty:
        raise KeyError(f"{path}: no row for video_stem={video_stem!r}")
    row = rows.iloc[0]
    verts = np.array(
        [[row["x0"], row["y0"]], [row["x1"], row["y1"]], [row["x2"], row["y2"]], [row["x3"], row["y3"]]],
        dtype=np.float64,
    )
    return verts
