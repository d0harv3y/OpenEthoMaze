"""Per-frame kinematics on kpMS-aligned rows."""

from __future__ import annotations

import numpy as np

from maze.pipeline.blob_orient import polygon_area


def centroid_from_coordinates(coordinates: np.ndarray) -> np.ndarray:
    """Mean xy across keypoints per row; ``coordinates`` shape ``(T, K, 2)``."""
    coord = np.asarray(coordinates, dtype=np.float64)
    if coord.ndim != 3 or coord.shape[-1] != 2:
        raise ValueError("coordinates must have shape (T, K, 2)")
    with np.errstate(invalid="ignore"):
        return np.nanmean(coord, axis=1)


def heading_from_anterior_posterior(
    coordinates: np.ndarray,
    *,
    anterior_idx: int,
    posterior_idx: int,
) -> np.ndarray:
    coord = np.asarray(coordinates, dtype=np.float64)
    ant = coord[:, anterior_idx, :]
    post = coord[:, posterior_idx, :]
    vec = ant - post
    return np.arctan2(vec[:, 1], vec[:, 0])


def speed_mps_from_centroid(
    centroid_xy_px: np.ndarray,
    *,
    fps: float,
    px_per_cm: float,
) -> np.ndarray:
    xy = np.asarray(centroid_xy_px, dtype=np.float64)
    n = len(xy)
    out = np.zeros(n, dtype=np.float64)
    if n < 2 or fps <= 0 or px_per_cm <= 0:
        return out
    step_px = np.linalg.norm(np.diff(xy, axis=0), axis=1)
    m_per_px = 1.0 / (px_per_cm * 100.0)
    speeds = step_px * m_per_px * float(fps)
    out[1:] = speeds
    return out


def abs_dheading_per_frame(heading_rad: np.ndarray) -> np.ndarray:
    h = np.asarray(heading_rad, dtype=np.float64).ravel()
    n = len(h)
    out = np.zeros(n, dtype=np.float64)
    if n < 2:
        return out
    unwrapped = np.unwrap(h)
    out[1:] = np.abs(np.diff(unwrapped))
    return out


def blob_area_px2_for_rows(
    blob_xy: np.ndarray,
    blob_valid: np.ndarray,
    source_frame_indices: np.ndarray,
) -> np.ndarray:
    """
    Map blob polygon area onto kpMS rows via ``source_frame_indices``.

    ``blob_xy``: ``(T_video, N, 2)``; ``blob_valid``: ``(T_video,)``.
    """
    blob_xy = np.asarray(blob_xy, dtype=np.float64)
    blob_valid = np.asarray(blob_valid, dtype=bool).ravel()
    src = np.asarray(source_frame_indices, dtype=np.int64).ravel()
    n = len(src)
    out = np.full(n, np.nan, dtype=np.float64)
    in_range = (src >= 0) & (src < len(blob_valid))
    if not np.any(in_range):
        return out
    idx = np.flatnonzero(in_range)
    fi = src[in_range]
    valid = blob_valid[fi]
    if not np.any(valid):
        return out
    idx = idx[valid]
    fi = fi[valid]
    for row_i, frame_i in zip(idx, fi, strict=True):
        poly = blob_xy[int(frame_i)]
        if np.isfinite(poly).all():
            out[int(row_i)] = polygon_area(poly)
    return out


def trial_state_for_rows(
    trial_states: np.ndarray,
    source_frame_indices: np.ndarray,
) -> list[str]:
    states = np.asarray(trial_states)
    src = np.asarray(source_frame_indices, dtype=np.int64).ravel()
    out = [""] * len(src)
    ok = (src >= 0) & (src < len(states))
    if not np.any(ok):
        return out
    for i in np.flatnonzero(ok):
        raw = states[int(src[i])]
        if isinstance(raw, (bytes, np.bytes_)):
            out[int(i)] = raw.decode("utf-8", errors="replace")
        else:
            out[int(i)] = str(raw)
    return out
