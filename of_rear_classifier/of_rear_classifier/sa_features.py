"""SuperAnimal TVM H5 → z-scored 22-D skeleton features (Davis OF path)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from of_rear_classifier.arena import load_floor_quad_vertices, point_in_polygon
from of_rear_classifier.parts_map import SA_TVM_PARTS
from of_rear_classifier.skeleton import skeleton_features, zscore_skeleton

DEFAULT_SA_LIKELIHOOD_CUTOFF = 0.3


def stem_from_sa_h5(h5: Path | str) -> str:
    name = Path(h5).name
    if "_superanimal" in name:
        return name.split("_superanimal", 1)[0]
    return Path(h5).stem


def _interp_xy(xy: np.ndarray, lik: np.ndarray, cutoff: float) -> np.ndarray:
    out = xy.astype(np.float64, copy=True)
    bad = ~np.isfinite(lik) | (lik < cutoff)
    out[bad] = np.nan
    df = pd.DataFrame(out, columns=["x", "y"])
    df = df.interpolate(method="linear", limit_direction="both")
    return df.to_numpy(dtype=np.float64)


def load_sa_video_features(
    h5_path: Path | str,
    *,
    quad_csv: Path | str,
    video_stem: str | None = None,
    individual: str = "animal0",
    likelihood_cutoff: float = DEFAULT_SA_LIKELIHOOD_CUTOFF,
) -> tuple[np.ndarray, dict]:
    """Return z-scored ``(T, 22)`` features and meta for one SA-TVM recording."""
    from maze.pipeline.open_field.dlc_h5 import bodypart_xy_likelihood, read_pose_table

    h5_path = Path(h5_path)
    stem = video_stem or stem_from_sa_h5(h5_path)
    df = read_pose_table(h5_path)
    parts: dict[str, np.ndarray] = {}
    for name in SA_TVM_PARTS:
        xy, lik = bodypart_xy_likelihood(df, name, individual=individual)
        parts[name] = _interp_xy(xy, lik, likelihood_cutoff)

    verts = load_floor_quad_vertices(quad_csv, stem)
    in_nose = point_in_polygon(parts["nose"], verts)
    in_head = point_in_polygon(parts["head_midpoint"], verts)
    feat = skeleton_features(parts, in_arena_nose=in_nose, in_arena_head=in_head)
    feat_z = zscore_skeleton(feat)
    meta = {
        "h5_path": str(h5_path),
        "video_stem": stem,
        "n_frames": int(feat_z.shape[0]),
        "likelihood_cutoff": float(likelihood_cutoff),
        "arena_vertices": verts,
    }
    return feat_z, meta
