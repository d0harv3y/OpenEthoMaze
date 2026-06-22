"""
Arena-normalized block dwell averages for legacy VAST cohort plots.

Builds per-trial RUN-phase dwell grids from H5 ``spot_hybrid`` XY (cm space),
averages per animal then per stratum, and renders PNG composites.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import h5py
import numpy as np

from ..defaults import (
    DWELL_HEATMAP_BLUR_SIGMA,
    MAX_DWELL_TIME_S,
    QC_EXIT_ZONE_RADIUS_CM,
)

try:
    import cv2

    HAS_CV2 = True
    _COLORMAP = getattr(cv2, "COLORMAP_TURBO", cv2.COLORMAP_JET)
except ImportError:
    HAS_CV2 = False
    _COLORMAP = None

DISPLAY_ARENA_RADIUS_CM = 62.0
IMAGE_SIZE = 512
IMAGE_MARGIN = 20
COLORBAR_WIDTH = 50
EXIT_OVERLAY_ALPHA = 0.05

TRIAL_BLOCKS: dict[str, tuple[str, ...]] = {
    "1-3": ("T01", "T02", "T03"),
    "4-6": ("T04", "T05", "T06"),
    "7-9": ("T07", "T08", "T09"),
}

FULL_SESSION_BLOCK = "1-9"
FULL_SESSION_TRIALS: tuple[str, ...] = tuple(f"T{i:02d}" for i in range(1, 10))
POOLED_SESSION_LABEL = "ALL"

ALL_TRIAL_BLOCKS: dict[str, tuple[str, ...]] = {
    **TRIAL_BLOCKS,
    FULL_SESSION_BLOCK: FULL_SESSION_TRIALS,
}


@dataclass(frozen=True)
class TrialRunSample:
    animal_id: int
    session: str
    trial: str
    dwell_grid_s: np.ndarray
    exit_x_cm: float
    exit_y_cm: float
    exit_radius_cm: float


@dataclass(frozen=True)
class BlockAverageResult:
    session: str
    tx: str
    sex: str
    strain: str
    block: str
    dwell_grid_s: np.ndarray
    exits_cm: tuple[tuple[float, float, float], ...]
    n_animals: int
    n_trials: int


def _decode_state(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode()
    return str(value)


def _cm_scale(image_size: int, margin: int, arena_radius_cm: float) -> float:
    return (image_size - 2 * margin) / (2.0 * arena_radius_cm)


def accumulate_run_dwell_grid_cm(
    xy_px: np.ndarray,
    valid: np.ndarray,
    *,
    arena_center_x_px: float,
    arena_center_y_px: float,
    px_per_cm: float,
    fps: float,
    image_size: int = IMAGE_SIZE,
    margin: int = IMAGE_MARGIN,
    display_arena_radius_cm: float = DISPLAY_ARENA_RADIUS_CM,
    blur_sigma: float = DWELL_HEATMAP_BLUR_SIGMA,
) -> np.ndarray:
    """Return dwell seconds grid (float32) on a fixed arena-centered cm canvas."""
    if px_per_cm <= 0 or fps <= 0:
        return np.zeros((image_size, image_size), dtype=np.float32)

    scale = _cm_scale(image_size, margin, display_arena_radius_cm)
    center_x = image_size / 2.0
    center_y = image_size / 2.0
    heat = np.zeros((image_size, image_size), dtype=np.float32)
    n = min(len(valid), xy_px.shape[0])
    for i in range(n):
        if not valid[i]:
            continue
        x_px = float(xy_px[i, 0])
        y_px = float(xy_px[i, 1])
        if not (np.isfinite(x_px) and np.isfinite(y_px)):
            continue
        x_cm = (x_px - arena_center_x_px) / px_per_cm
        y_cm = (y_px - arena_center_y_px) / px_per_cm
        xi = int(round(center_x + x_cm * scale))
        yi = int(round(center_y + y_cm * scale))
        if 0 <= xi < image_size and 0 <= yi < image_size:
            heat[yi, xi] += 1.0

    dwell_time_s = heat / float(fps)
    if blur_sigma > 0 and np.nanmax(dwell_time_s) > 0:
        if not HAS_CV2:
            return dwell_time_s
        dwell_time_s = cv2.GaussianBlur(
            dwell_time_s,
            (0, 0),
            sigmaX=float(blur_sigma),
            sigmaY=float(blur_sigma),
        )
        compensation_factor = 2.0 * math.pi * blur_sigma * blur_sigma
        dwell_time_s = dwell_time_s * compensation_factor
    return dwell_time_s


def load_trial_run_sample(
    h5: h5py.File,
    *,
    animal_id: int,
    session: str,
    trial: str,
) -> TrialRunSample | None:
    path = f"{animal_id}/{session}/{trial}"
    if path not in h5:
        return None
    g_trial = h5[path]
    xy_path = f"{path}/ambulation_metrics/spot_hybrid/xy"
    if xy_path not in h5:
        return None

    attrs = dict(g_trial.attrs)
    arena_center_x_px = float(attrs.get("arena_center_x_px", 0.0))
    arena_center_y_px = float(attrs.get("arena_center_y_px", 0.0))
    px_per_cm = float(attrs.get("px_per_cm", 0.0))
    fps = float(attrs.get("fps", 0.0))
    exit_x_px = float(attrs.get("exit_x", 0.0))
    exit_y_px = float(attrs.get("exit_y", 0.0))
    if px_per_cm <= 0 or fps <= 0:
        return None

    rec = h5[xy_path][:]
    states = [_decode_state(s) for s in rec["trial_state"]]
    run_mask = np.array([s == "run" for s in states], dtype=bool)
    if not np.any(run_mask):
        return None

    run = rec[run_mask]
    xy_px = np.column_stack((run["x"].astype(np.float64), run["y"].astype(np.float64)))
    valid = run["valid"].astype(bool) & np.isfinite(xy_px).all(axis=1)
    if not np.any(valid):
        return None

    dwell_grid_s = accumulate_run_dwell_grid_cm(
        xy_px,
        valid,
        arena_center_x_px=arena_center_x_px,
        arena_center_y_px=arena_center_y_px,
        px_per_cm=px_per_cm,
        fps=fps,
    )
    exit_x_cm = (exit_x_px - arena_center_x_px) / px_per_cm
    exit_y_cm = (exit_y_px - arena_center_y_px) / px_per_cm
    return TrialRunSample(
        animal_id=animal_id,
        session=session,
        trial=trial,
        dwell_grid_s=dwell_grid_s,
        exit_x_cm=exit_x_cm,
        exit_y_cm=exit_y_cm,
        exit_radius_cm=float(QC_EXIT_ZONE_RADIUS_CM),
    )


def _mean_grids(grids: Sequence[np.ndarray]) -> np.ndarray:
    if not grids:
        return np.zeros((IMAGE_SIZE, IMAGE_SIZE), dtype=np.float32)
    stack = np.stack(grids, axis=0)
    return stack.mean(axis=0).astype(np.float32)


def average_block_dwell(
    samples: Iterable[TrialRunSample],
) -> tuple[np.ndarray, tuple[tuple[float, float, float], ...], int, int, int]:
    """Per animal×session block mean, then mean across units.

    Returns grid, exits, n_units, n_unique_animals, n_trials.
    Each (animal_id, session) pair is one equal-weight contributor.
    """
    by_unit: dict[tuple[int, str], list[TrialRunSample]] = {}
    for sample in samples:
        by_unit.setdefault((sample.animal_id, sample.session), []).append(sample)

    unit_grids: list[np.ndarray] = []
    exits: list[tuple[float, float, float]] = []
    n_trials = 0
    for unit_samples in by_unit.values():
        grids = [s.dwell_grid_s for s in unit_samples]
        unit_grids.append(_mean_grids(grids))
        n_trials += len(unit_samples)
        for s in unit_samples:
            exits.append((s.exit_x_cm, s.exit_y_cm, s.exit_radius_cm))

    if not unit_grids:
        return (
            np.zeros((IMAGE_SIZE, IMAGE_SIZE), dtype=np.float32),
            tuple(),
            0,
            0,
            0,
        )
    n_unique_animals = len({animal_id for animal_id, _ in by_unit})
    return _mean_grids(unit_grids), tuple(exits), len(unit_grids), n_unique_animals, n_trials


def _render_colorbar(max_dwell_time_s: float, height: int, width: int) -> np.ndarray:
    gradient = np.linspace(255, 0, height, dtype=np.uint8).reshape((height, 1))
    gradient = np.repeat(gradient, width, axis=1)
    return cv2.applyColorMap(gradient, _COLORMAP)


def render_block_dwell_image(
    dwell_grid_s: np.ndarray,
    exits_cm: Sequence[tuple[float, float, float]],
    *,
    max_dwell_time_s: float = MAX_DWELL_TIME_S,
    image_size: int = IMAGE_SIZE,
    margin: int = IMAGE_MARGIN,
    display_arena_radius_cm: float = DISPLAY_ARENA_RADIUS_CM,
    exit_overlay_alpha: float = EXIT_OVERLAY_ALPHA,
) -> np.ndarray:
    """Render heatmap + arena + translucent exit ensemble + colorbar (BGR uint8)."""
    if not HAS_CV2:
        raise RuntimeError("opencv is required to render block dwell plots")

    scale = _cm_scale(image_size, margin, display_arena_radius_cm)
    center_x = image_size / 2.0
    center_y = image_size / 2.0

    if max_dwell_time_s > 0:
        heat8 = np.clip((dwell_grid_s / max_dwell_time_s) * 255.0, 0, 255).astype(np.uint8)
    else:
        max_val = float(np.nanmax(dwell_grid_s))
        heat8 = (
            np.clip((dwell_grid_s / max_val) * 255.0, 0, 255).astype(np.uint8)
            if max_val > 0
            else np.zeros((image_size, image_size), dtype=np.uint8)
        )
    base = cv2.applyColorMap(heat8, _COLORMAP)

    arena_radius_px = int(round(display_arena_radius_cm * scale))
    cv2.circle(
        base,
        (int(center_x), int(center_y)),
        arena_radius_px,
        (200, 200, 200),
        2,
        cv2.LINE_AA,
    )

    for exit_x_cm, exit_y_cm, exit_radius_cm in exits_cm:
        ix = int(round(center_x + exit_x_cm * scale))
        iy = int(round(center_y + exit_y_cm * scale))
        ir = max(1, int(round(exit_radius_cm * scale)))
        overlay = base.copy()
        cv2.circle(overlay, (ix, iy), ir, (0, 255, 0), -1, cv2.LINE_AA)
        cv2.addWeighted(overlay, exit_overlay_alpha, base, 1.0 - exit_overlay_alpha, 0, base)

    colorbar = _render_colorbar(max_dwell_time_s, height=image_size, width=COLORBAR_WIDTH)
    composite = np.zeros((image_size, image_size + COLORBAR_WIDTH, 3), dtype=np.uint8)
    composite[:, :image_size] = base
    composite[:, image_size:] = colorbar
    return composite


def tx_path_token(tx: str) -> str:
    """Filesystem-safe treatment token (manifest ``n/a`` is not a valid path segment)."""
    return tx.replace("/", "_").replace("\\", "_")


def export_filename(session: str, tx: str, strain: str, sex: str, block: str) -> str:
    lo, hi = block.split("-", 1)
    tx_tok = tx_path_token(tx)
    return f"{session}_{tx_tok}_{strain}_{sex}_trial{lo}-{hi}.png"


def export_relpath(session: str, tx: str, strain: str, sex: str, block: str) -> Path:
    return Path(session) / tx_path_token(tx) / export_filename(session, tx, strain, sex, block)


def export_filename_pooled(tx: str, strain: str, sex: str, block: str) -> str:
    return export_filename(POOLED_SESSION_LABEL, tx, strain, sex, block)


def export_relpath_pooled(tx: str, strain: str, sex: str, block: str) -> Path:
    return Path(tx_path_token(tx)) / export_filename_pooled(tx, strain, sex, block)
