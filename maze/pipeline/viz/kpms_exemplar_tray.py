"""
kpMS exemplar trajectory loops as RGBA rasters for the side tray overlay (right of video).

Requires optional dependency ``keypoint-moseq`` (``uv sync --extra kpms``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from maze.core.anatomy import FALLBACK_NODE_INDEX, SKELETON_EDGES, STANDARD_NODE_NAMES

from ...kpms.exemplar_typical import typical_trajectories_for_exemplar_tray
from ...kpms.frame_alignment import kpms_aligned_coordinates_and_indices
from ...kpms.preprocess import KpmsPreprocessConfig
from ..io.file_discovery import TrialManifest

_KPMS_IMPORT_ERROR: Exception | None = None
try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from keypoint_moseq.io import load_hdf5
    from keypoint_moseq.util import get_edges, interpolate_along_axis
    from keypoint_moseq.viz import get_limits

    HAS_KPMS_TRAY = True
except Exception as e:  # pragma: no cover - optional dependency
    HAS_KPMS_TRAY = False
    _KPMS_IMPORT_ERROR = e


def kpms_tray_import_error() -> Exception | None:
    return _KPMS_IMPORT_ERROR


def _orient_xy_vertical_heading(X: np.ndarray) -> np.ndarray:
    """
    Rotate planar keypoints about their centroid so the mean nose→tail vector
    aligns with matplotlib +y (up on screen).
    """
    X = np.asarray(X, dtype=np.float64)
    if X.ndim != 3 or X.shape[-1] != 2 or X.shape[1] < 2:
        return X
    ni = FALLBACK_NODE_INDEX["nose"]
    ti = FALLBACK_NODE_INDEX["tail"]
    nose = X[:, ni, :]
    tail = X[:, ti, :]
    v = nose - tail
    m = np.isfinite(v).all(axis=1)
    if not np.any(m):
        return X
    v_mean = np.mean(v[m], axis=0)
    if not np.all(np.isfinite(v_mean)) or float(np.linalg.norm(v_mean)) < 1e-12:
        return X
    ang = float(np.arctan2(v_mean[1], v_mean[0]))
    rot = 0.5 * np.pi - ang
    c, s = float(np.cos(rot)), float(np.sin(rot))
    R = np.array([[c, -s], [s, c]], dtype=np.float64)
    flat = X.reshape(-1, 2)
    ctr = np.nanmean(flat, axis=0)
    if not np.all(np.isfinite(ctr)):
        ctr = np.zeros(2, dtype=np.float64)
    delta = flat - ctr
    ok = np.isfinite(delta).all(axis=1)
    out_flat = np.full_like(flat, np.nan)
    out_flat[ok] = (R @ delta[ok].T).T + ctr
    return out_flat.reshape(X.shape)


def _postprocess_rgba_key_black(rgba: np.ndarray, lum_thresh: int = 28) -> np.ndarray:
    """Force near-black pixels (matplotlib background) to transparent."""
    out = np.array(rgba, copy=True, dtype=np.uint8)
    rgb = out[..., :3].astype(np.int16)
    lum = rgb.sum(axis=-1)
    out[..., 3] = np.where(lum <= lum_thresh, 0, out[..., 3]).astype(np.uint8)
    return out


def _draw_trajectory_rgba_frames(
    X_time_kp_2: np.ndarray,
    lims: np.ndarray,
    edges: list[list[int]],
    *,
    num_timesteps: int = 14,
    node_size: float = 42.0,
    line_width: float = 2.8,
    keypoint_colormap: str = "autumn",
    dpi: float = 120.0,
    fig_width_inches: float = 3.2,
) -> list[np.ndarray]:
    """
    Rasterize one exemplar trajectory (T, K, 2) into RGBA frames (H, W, 4) uint8.

    Mirrors keypoint_moseq ``plot_trajectories`` drawing without title or backdrop fill.
    """
    assert HAS_KPMS_TRAY
    X = np.asarray(X_time_kp_2, dtype=np.float64)
    if X.ndim != 3 or X.shape[-1] != 2:
        raise ValueError(f"Expected (T, K, 2), got {X.shape}")

    cmap = plt.colormaps[keypoint_colormap]
    colors = cmap(np.linspace(0, 1, X.shape[1]))

    n_steps = int(num_timesteps)
    xp = np.arange(X.shape[0], dtype=np.float64)
    xi = np.linspace(0, X.shape[0] - 1, n_steps)
    Xs = interpolate_along_axis(xi, xp, X[None, ...], axis=1)
    offsets = np.zeros((1, 2), dtype=np.float64)
    Xs = Xs + offsets[:, None, None]

    xmin, ymin = lims[0] + offsets.min(0)
    xmax, ymax = lims[1] + offsets.max(0)
    fw = fig_width_inches
    fh = fw * (ymax - ymin) / max(xmax - xmin, 1e-6)

    fig, ax = plt.subplots(frameon=False)
    fig.patch.set_alpha(0.0)
    ax.patch.set_alpha(0.0)
    ax.set_xlim(float(xmin), float(xmax))
    ax.set_ylim(float(ymin), float(ymax))
    ax.set_aspect("equal")
    ax.axis("off")
    fig.set_size_inches(fw, fh)
    fig.set_dpi(dpi)
    plt.tight_layout(pad=0.0)

    rasters: list[np.ndarray] = []
    for i in range(Xs.shape[1]):
        for X, _offset in zip(Xs, offsets):
            for ii, jj in edges:
                ax.plot(
                    *X[i, (ii, jj)].T,
                    c="k",
                    zorder=i * 4,
                    linewidth=line_width,
                    clip_on=False,
                )
            for ii, jj in edges:
                ax.plot(
                    *X[i, (ii, jj)].T,
                    c=colors[ii],
                    zorder=i * 4 + 1,
                    linewidth=line_width * 0.9,
                    clip_on=False,
                )
            ax.scatter(
                *X[i].T,
                c=colors,
                zorder=i * 4 + 2,
                edgecolor="k",
                linewidth=0.35,
                s=node_size,
                clip_on=False,
            )

        fig.canvas.draw()
        buf = np.asarray(fig.canvas.buffer_rgba())
        rasters.append(_postprocess_rgba_key_black(buf.copy()))
    plt.close(fig)
    return rasters


def exemplar_rgba_loops_from_typical_arrays(
    typical: dict[int, np.ndarray],
    syllable_ids: list[int],
    *,
    projection_plane: str = "xy",
    num_timesteps: int = 14,
    vertical_heading: bool = True,
) -> dict[int, list[np.ndarray]]:
    """
    Turn precomputed ``typical[syllable_id] -> (T, K, D)`` arrays into RGBA frame loops.

    Used with :func:`maze.kpms.training_exemplar_table.load_training_exemplar_typical`.
    """
    if not HAS_KPMS_TRAY:
        raise RuntimeError(
            "keypoint-moseq is required for the exemplar tray. Install with: uv sync --extra kpms"
        ) from _KPMS_IMPORT_ERROR

    edges = get_edges(list(STANDARD_NODE_NAMES), list(SKELETON_EDGES))
    want = {int(s) for s in syllable_ids if int(s) >= 0}
    out: dict[int, list[np.ndarray]] = {}

    for sid in sorted(want):
        if sid not in typical:
            continue
        X = np.asarray(typical[sid], dtype=np.float64)
        if X.ndim != 3:
            continue
        plane = projection_plane.lower().strip()
        if X.shape[-1] == 3:
            dims = {"xy": (0, 1), "xz": (0, 2), "yz": (1, 2)}.get(plane, (0, 1))
            X2 = X[..., dims[0]]
            Y2 = X[..., dims[1]]
            X_vis = np.stack([X2, Y2], axis=-1)
        elif X.shape[-1] == 2:
            X_vis = X * np.array([1.0, -1.0], dtype=np.float64)
        else:
            continue

        if vertical_heading:
            X_vis = _orient_xy_vertical_heading(X_vis)

        lims = get_limits(
            X_vis,
            pctl=1,
            left=0.12,
            right=0.12,
            top=0.18,
            bottom=0.18,
        )
        frames = _draw_trajectory_rgba_frames(
            X_vis,
            lims,
            edges,
            num_timesteps=num_timesteps,
        )
        if frames:
            out[sid] = frames

    return out


def build_exemplar_rgba_loops_for_syllables(
    results_h5: Path,
    manifest: TrialManifest,
    syllable_ids: list[int],
    *,
    pre_cfg: KpmsPreprocessConfig,
    conf_threshold: float,
    min_points_per_frame: int,
    min_fragment_frames: int,
    fps: float,
    pre_seconds: float = 0.167,
    post_seconds: float = 0.5,
    min_frequency: float = 0.003,
    min_duration: int = 3,
    density_sample: bool = True,
    n_neighbors: int = 50,
    projection_plane: str = "xy",
    num_timesteps: int = 14,
    vertical_heading: bool = True,
    egocentric: bool = False,
) -> dict[int, list[np.ndarray]]:
    """
    For each syllable id, build a list of RGBA uint8 frames (H, W, 4) using
    :func:`typical_trajectories_for_exemplar_tray` and local rasterization.

    Missing syllables (filtered by kpMS) are omitted from the returned dict.
    """
    if not HAS_KPMS_TRAY:
        raise RuntimeError(
            "keypoint-moseq is required for the exemplar tray. Install with: uv sync --extra kpms"
        ) from _KPMS_IMPORT_ERROR

    aligned = kpms_aligned_coordinates_and_indices(
        manifest,
        pre_cfg,
        conf_threshold=conf_threshold,
        min_points_per_frame=min_points_per_frame,
        min_fragment_frames=min_fragment_frames,
    )
    if aligned is None:
        return {}

    rk, coordinates_arr, _src_idx = aligned
    results_all: dict[str, Any] = load_hdf5(str(results_h5))
    if rk not in results_all:
        return {}

    results_one = {rk: results_all[rk]}
    coordinates_one = {rk: coordinates_arr}

    pre = max(1, round(float(pre_seconds) * float(fps)))
    post = max(1, round(float(post_seconds) * float(fps)))

    try:
        typical = typical_trajectories_for_exemplar_tray(
            coordinates_one,
            results_one,
            pre=pre,
            post=post,
            min_frequency=min_frequency,
            min_duration=min_duration,
            bodyparts=list(STANDARD_NODE_NAMES),
            use_bodyparts=list(STANDARD_NODE_NAMES),
            density_sample=density_sample,
            sampling_options={"n_neighbors": int(n_neighbors)},
            egocentric=egocentric,
        )
    except ValueError:
        return {}

    typical_i = {int(sid): np.asarray(arr, dtype=np.float64) for sid, arr in typical.items()}
    return exemplar_rgba_loops_from_typical_arrays(
        typical_i,
        syllable_ids,
        projection_plane=projection_plane,
        num_timesteps=num_timesteps,
        vertical_heading=vertical_heading,
    )
