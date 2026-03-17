"""
QC image generation for VAST pipeline.

Generates a single composite QC image per trial (ehram parity):
- Dwell-time heatmap with compensation_factor and TURBO colormap
- Arena circle at arena center, exit zone at (exit_x, exit_y) with 12.5 cm radius
- Trajectory overlay
- Dwell time colorbar
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Optional

import numpy as np

# For heatmap from all nodes: list of (xy (n_frames, 2), valid (n_frames,))
XYValidList = list[tuple[np.ndarray, np.ndarray]]

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

from ..config import (
    DWELL_HEATMAP_BLUR_SIGMA,
    MAX_DWELL_TIME_S,
    QC_EXIT_ZONE_RADIUS_CM,
)
from ..storage.h5_db import TrialKey, write_qc_image

# Colormap: TURBO if available (OpenCV 4.1+), else JET
_COLORMAP = getattr(cv2, "COLORMAP_TURBO", cv2.COLORMAP_JET) if HAS_CV2 else None


def generate_trial_qc_images(
    db_path: Path,
    key: TrialKey,
    trajectory_xy: np.ndarray,
    trajectory_valid: np.ndarray,
    exit_pos: tuple[float, float],
    arena_center_x_px: float,
    arena_center_y_px: float,
    arena_radius_px: float,
    px_per_cm: float,
    fps: float = 30.0,
    image_size: int = 512,
    xy_list_heatmap: Optional[XYValidList] = None,
    image_name: str = "composite",
    qc_attrs: Optional[dict[str, Any]] = None,
) -> None:
    """
    Generate and save a single composite QC image for a trial.

    Composite = dwell heatmap (with compensation_factor, TURBO colormap) +
    arena circle at arena center + exit zone at (exit_x, exit_y) with 12.5 cm radius +
    trajectory polyline + colorbar.

    trajectory_xy / trajectory_valid: the (x, y) positions and validity mask drawn
    as the polyline. If xy_list_heatmap is not provided, the same data is used
    for the dwell heatmap; otherwise the heatmap uses all series in xy_list_heatmap.

    qc_attrs: optional dict of string/num attributes stored on the QC image dataset
    (e.g. heatmap_source, trajectory_source, primary_reason) for provenance.
    """
    if not HAS_CV2:
        return

    try:
        if not arena_radius_px or arena_radius_px <= 0:
            return  # Skip: scale would be invalid
        composite = generate_composite_qc_image(
            trajectory_xy=trajectory_xy,
            trajectory_valid=trajectory_valid,
            exit_pos=exit_pos,
            arena_center_x_px=arena_center_x_px,
            arena_center_y_px=arena_center_y_px,
            arena_radius_px=arena_radius_px,
            px_per_cm=px_per_cm,
            fps=fps,
            image_size=image_size,
            xy_list_heatmap=xy_list_heatmap,
        )
        if composite is not None:
            write_qc_image(db_path, key, image_name, composite, attrs=qc_attrs or None)
    except Exception as e:
        import warnings
        warnings.warn(f"QC composite skipped for {key.path()}: {e}", stacklevel=1)


def _render_dwell_heatmap_bgr(
    height: int,
    width: int,
    xy: np.ndarray,
    valid: np.ndarray,
    arena_center_x_px: float,
    arena_center_y_px: float,
    arena_radius_px: float,
    fps: float,
    blur_sigma: float,
    max_dwell_time_s: float,
    scale: float,
    center_x: float,
    center_y: float,
) -> np.ndarray:
    """
    Build dwell-time heatmap in image space. Accumulate in frame counts,
    convert to seconds, blur, apply compensation_factor, normalize, colormap.
    """
    heat = np.zeros((height, width), dtype=np.float32)
    T = min(len(valid), xy.shape[0])
    for i in range(T):
        if not valid[i]:
            continue
        x = float(xy[i, 0])
        y = float(xy[i, 1])
        if not (np.isfinite(x) and np.isfinite(y)):
            continue
        # Video px -> QC image px: place arena center at (center_x, center_y), scale by scale.
        # Assumes (x,y) and (arena_center_x_px, arena_center_y_px) are in the same coordinate
        # system (e.g. both full video frame). If trace appears offset, verify ROI and SLEAP
        # use the same reference (resolution and origin).
        dx = x - arena_center_x_px
        dy = y - arena_center_y_px
        xi = int(round(center_x + dx * scale))
        yi = int(round(center_y + dy * scale))
        if 0 <= xi < width and 0 <= yi < height:
            heat[yi, xi] += 1.0

    dwell_time_s = heat / float(fps) if fps > 0 else heat

    if blur_sigma > 0 and np.nanmax(dwell_time_s) > 0:
        dwell_time_s = cv2.GaussianBlur(
            dwell_time_s, (0, 0),
            sigmaX=float(blur_sigma), sigmaY=float(blur_sigma),
        )
        compensation_factor = 2.0 * math.pi * blur_sigma * blur_sigma
        dwell_time_s = dwell_time_s * compensation_factor

    if max_dwell_time_s > 0:
        heat8 = np.clip(
            (dwell_time_s / float(max_dwell_time_s)) * 255.0, 0, 255
        ).astype(np.uint8)
    else:
        max_val = float(np.nanmax(dwell_time_s))
        heat8 = (
            np.clip((dwell_time_s / max_val) * 255.0, 0, 255).astype(np.uint8)
            if max_val > 0
            else np.zeros((height, width), dtype=np.uint8)
        )

    return cv2.applyColorMap(heat8, _COLORMAP)


def _render_dwell_heatmap_bgr_multi(
    height: int,
    width: int,
    xy_valid_list: XYValidList,
    arena_center_x_px: float,
    arena_center_y_px: float,
    arena_radius_px: float,
    fps: float,
    blur_sigma: float,
    max_dwell_time_s: float,
    scale: float,
    center_x: float,
    center_y: float,
) -> np.ndarray:
    """
    Build dwell-time heatmap from multiple (xy, valid) series (e.g. all nodes).
    Accumulates every valid (x, y) across all nodes and frames into one heat grid.
    """
    heat = np.zeros((height, width), dtype=np.float32)
    for xy, valid in xy_valid_list:
        xy = np.asarray(xy, dtype=np.float64)
        valid = np.asarray(valid, dtype=bool)
        T = min(len(valid), xy.shape[0])
        for i in range(T):
            if not valid[i]:
                continue
            x = float(xy[i, 0])
            y = float(xy[i, 1])
            if not (np.isfinite(x) and np.isfinite(y)):
                continue
            # Same transform: arena center at (center_x, center_y), scale by scale
            dx = x - arena_center_x_px
            dy = y - arena_center_y_px
            xi = int(round(center_x + dx * scale))
            yi = int(round(center_y + dy * scale))
            if 0 <= xi < width and 0 <= yi < height:
                heat[yi, xi] += 1.0

    dwell_time_s = heat / float(fps) if fps > 0 else heat

    if blur_sigma > 0 and np.nanmax(dwell_time_s) > 0:
        dwell_time_s = cv2.GaussianBlur(
            dwell_time_s, (0, 0),
            sigmaX=float(blur_sigma), sigmaY=float(blur_sigma),
        )
        compensation_factor = 2.0 * math.pi * blur_sigma * blur_sigma
        dwell_time_s = dwell_time_s * compensation_factor

    if max_dwell_time_s > 0:
        heat8 = np.clip(
            (dwell_time_s / float(max_dwell_time_s)) * 255.0, 0, 255
        ).astype(np.uint8)
    else:
        max_val = float(np.nanmax(dwell_time_s))
        heat8 = (
            np.clip((dwell_time_s / max_val) * 255.0, 0, 255).astype(np.uint8)
            if max_val > 0
            else np.zeros((height, width), dtype=np.uint8)
        )

    return cv2.applyColorMap(heat8, _COLORMAP)


def _render_colorbar(
    max_dwell_time_s: float,
    height: int = 400,
    width: int = 120,
) -> np.ndarray:
    """Vertical colorbar for dwell time (BGR)."""
    gradient = np.linspace(255, 0, height, dtype=np.uint8).reshape((height, 1))
    gradient = np.repeat(gradient, width, axis=1)
    colorbar = cv2.applyColorMap(gradient, _COLORMAP)
    return colorbar


def generate_composite_qc_image(
    trajectory_xy: np.ndarray,
    trajectory_valid: np.ndarray,
    exit_pos: tuple[float, float],
    arena_center_x_px: float,
    arena_center_y_px: float,
    arena_radius_px: float,
    px_per_cm: float,
    fps: float = 30.0,
    image_size: int = 512,
    margin: int = 20,
    colorbar_width: int = 80,
    xy_list_heatmap: Optional[XYValidList] = None,
) -> Optional[np.ndarray]:
    """
    Generate a single composite QC image: heatmap + arena + exit zone + trajectory + colorbar.

    Arena center is at image center. Exit is drawn at (exit_x, exit_y) with
    radius QC_EXIT_ZONE_RADIUS_CM (12.5 cm). Uses ehram-style dwell heatmap
    (compensation_factor, TURBO colormap).

    trajectory_xy / trajectory_valid: polyline to draw (primary point, e.g. spot or in-range).
    If xy_list_heatmap is provided, the heatmap is built from those series (e.g. all SLEAP nodes);
    otherwise the heatmap uses trajectory_xy / trajectory_valid.
    """
    if not HAS_CV2:
        return None
    if not arena_radius_px or arena_radius_px <= 0:
        return None

    exit_x, exit_y = exit_pos
    scale = (image_size - 2 * margin) / (2.0 * arena_radius_px)
    center_x = image_size / 2.0
    center_y = image_size / 2.0

    # Base: dwell heatmap (all nodes or trajectory)
    if xy_list_heatmap and len(xy_list_heatmap) > 0:
        base = _render_dwell_heatmap_bgr_multi(
            height=image_size,
            width=image_size,
            xy_valid_list=xy_list_heatmap,
            arena_center_x_px=arena_center_x_px,
            arena_center_y_px=arena_center_y_px,
            arena_radius_px=arena_radius_px,
            fps=fps,
            blur_sigma=DWELL_HEATMAP_BLUR_SIGMA,
            max_dwell_time_s=MAX_DWELL_TIME_S,
            scale=scale,
            center_x=center_x,
            center_y=center_y,
        )
    else:
        base = _render_dwell_heatmap_bgr(
            height=image_size,
            width=image_size,
            xy=trajectory_xy,
            valid=trajectory_valid,
            arena_center_x_px=arena_center_x_px,
            arena_center_y_px=arena_center_y_px,
            arena_radius_px=arena_radius_px,
            fps=fps,
            blur_sigma=DWELL_HEATMAP_BLUR_SIGMA,
            max_dwell_time_s=MAX_DWELL_TIME_S,
            scale=scale,
            center_x=center_x,
            center_y=center_y,
        )

    # Arena circle at center
    radius_scaled = int(arena_radius_px * scale)
    cv2.circle(base, (int(center_x), int(center_y)), radius_scaled, (200, 200, 200), 2)

    # Exit zone at (exit_x, exit_y) with 12.5 cm radius
    exit_radius_px = QC_EXIT_ZONE_RADIUS_CM * px_per_cm
    exit_radius_scaled = int(exit_radius_px * scale)
    exit_im_x = int(center_x + (exit_x - arena_center_x_px) * scale)
    exit_im_y = int(center_y + (exit_y - arena_center_y_px) * scale)
    cv2.circle(base, (exit_im_x, exit_im_y), exit_radius_scaled, (0, 255, 0), 1)

    # Trajectory polyline
    pts = []
    first_valid_coord = None
    T = min(len(trajectory_valid), trajectory_xy.shape[0])
    for i in range(T):
        if not trajectory_valid[i]:
            continue
        x, y = float(trajectory_xy[i, 0]), float(trajectory_xy[i, 1])
        if np.isfinite(x) and np.isfinite(y):
            ix = int(center_x + (x - arena_center_x_px) * scale)
            iy = int(center_y + (y - arena_center_y_px) * scale)
            if 0 <= ix < image_size and 0 <= iy < image_size:
                if first_valid_coord is None:
                    first_valid_coord = (ix, iy)
                pts.append((ix, iy))
    if first_valid_coord is not None:
        ix, iy = first_valid_coord
        cv2.line(base, (ix - 3, iy - 3), (ix + 3, iy + 3), (255, 255, 255), 2)
        cv2.line(base, (ix - 3, iy + 3), (ix + 3, iy - 3), (255, 255, 255), 2)
    if len(pts) >= 2:
        cv2.polylines(
            base,
            [np.array(pts, dtype=np.int32).reshape((-1, 1, 2))],
            False,
            (0, 255, 0),
            1,
        )

    # Append colorbar on the right
    cb_h = image_size
    cb_w = colorbar_width
    colorbar = _render_colorbar(MAX_DWELL_TIME_S, height=cb_h, width=cb_w)
    composite = np.zeros((image_size, image_size + cb_w, 3), dtype=np.uint8)
    composite[:, :image_size] = base
    composite[:, image_size:] = colorbar

    return composite
