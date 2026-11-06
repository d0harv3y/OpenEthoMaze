"""Load Sturman OFT DeepLabCut CSVs → cleaned xy + arena flags for 22-D skeleton."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd

from of_rear_classifier.arena import point_in_polygon
from of_rear_classifier.parts_map import STURMAN_TO_SA_TVM
from of_rear_classifier.skeleton import skeleton_features, zscore_skeleton

STURMAN_ANIMAL_PARTS: tuple[str, ...] = tuple(STURMAN_TO_SA_TVM.keys())
STURMAN_CORNER_PARTS: tuple[str, ...] = ("tl", "tr", "br", "bl")

DEFAULT_FPS = 25.0
DEFAULT_LIKELIHOOD_CUTOFF = 0.95
DEFAULT_CUT_START = 100
DEFAULT_CUT_END = 100


def read_sturman_dlc_csv(path: Path | str) -> pd.DataFrame:
    """DLC multi-index CSV (scorer / bodyparts / coords), frame index."""
    path = Path(path)
    df = pd.read_csv(path, header=[0, 1, 2], index_col=0)
    # Normalize to bodyparts / coords only
    if df.columns.nlevels == 3:
        df.columns = df.columns.droplevel(0)
    df.columns = df.columns.set_names(["bodyparts", "coords"])
    return df


def _part_xy_lik(df: pd.DataFrame, part: str) -> tuple[np.ndarray, np.ndarray]:
    block = df[part]
    x = block["x"].to_numpy(dtype=np.float64).reshape(-1)
    y = block["y"].to_numpy(dtype=np.float64).reshape(-1)
    lik = block["likelihood"].to_numpy(dtype=np.float64).reshape(-1)
    return np.column_stack([x, y]), lik


def _interp_xy(xy: np.ndarray, lik: np.ndarray, cutoff: float) -> np.ndarray:
    out = xy.astype(np.float64, copy=True)
    bad = lik < cutoff
    out[bad] = np.nan
    df = pd.DataFrame(out, columns=["x", "y"])
    df = df.interpolate(method="linear", limit_direction="both")
    return df.to_numpy(dtype=np.float64)


def arena_vertices_from_corners(parts_xy: Mapping[str, np.ndarray]) -> np.ndarray:
    """Median corner positions → (4, 2) polygon tl, tr, br, bl."""
    verts = []
    for name in STURMAN_CORNER_PARTS:
        xy = np.asarray(parts_xy[name], dtype=np.float64)
        verts.append(np.nanmedian(xy, axis=0))
    return np.asarray(verts, dtype=np.float64)


def load_sturman_video_features(
    csv_path: Path | str,
    *,
    likelihood_cutoff: float = DEFAULT_LIKELIHOOD_CUTOFF,
    cut_start: int = DEFAULT_CUT_START,
    cut_end: int = DEFAULT_CUT_END,
) -> tuple[np.ndarray, dict]:
    """Return z-scored ``(T, 22)`` features and meta (paths, T, arena)."""
    path = Path(csv_path)
    df = read_sturman_dlc_csv(path)
    raw: dict[str, np.ndarray] = {}
    for part in (*STURMAN_CORNER_PARTS, *STURMAN_ANIMAL_PARTS):
        xy, lik = _part_xy_lik(df, part)
        raw[part] = _interp_xy(xy, lik, likelihood_cutoff)

    t0 = int(cut_start)
    t1 = len(next(iter(raw.values()))) - int(cut_end)
    if t1 <= t0:
        raise ValueError(f"{path.name}: empty after cut_start/cut_end")
    for k in list(raw):
        raw[k] = raw[k][t0:t1]

    arena = arena_vertices_from_corners(raw)
    sa_parts = {STURMAN_TO_SA_TVM[s]: raw[s] for s in STURMAN_ANIMAL_PARTS}
    in_nose = point_in_polygon(sa_parts["nose"], arena)
    in_head = point_in_polygon(sa_parts["head_midpoint"], arena)
    feat = skeleton_features(sa_parts, in_arena_nose=in_nose, in_arena_head=in_head)
    feat_z = zscore_skeleton(feat)
    meta = {
        "csv_path": str(path),
        "n_frames_raw": int(len(df)),
        "n_frames": int(feat_z.shape[0]),
        "cut_start": t0,
        "cut_end": int(cut_end),
        "arena_vertices": arena,
    }
    return feat_z, meta
