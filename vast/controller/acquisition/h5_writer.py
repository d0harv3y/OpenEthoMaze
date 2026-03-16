"""
VAST-compatible HDF5 writer (Option B): trial groups, settings, feedback, xy.

Schema matches vast.pipeline.storage.h5_db so VAST pipeline can read the file.

Per-frame xy table includes trial_state ("iti" | "wait" | "run"). Downstream pipeline
analysis should restrict to frames with trial_state == "run" for now.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import h5py
import numpy as np

from vast.core.schema import (
    XY_ROW_DTYPE,
    FEEDBACK_ROW_DTYPE,
    FEEDBACK_GROUP,
    FEEDBACK_TABLE_DATASET,
)
from vast.core.storage import open_db


def _ensure_group(parent: h5py.Group, name: str) -> h5py.Group:
    return parent[name] if name in parent else parent.create_group(name)


def _safe_str(x: Any) -> str:
    return "" if x is None else str(x)


def init_database(db_path: Path) -> None:
    """Create metadata structure."""
    with open_db(db_path, "a") as h5:
        meta = _ensure_group(h5, "metadata")
        meta.attrs["controller_schema_version"] = "v1"
        arena = _ensure_group(meta, "arena_info")
        arena.attrs["type"] = "circular"


def ensure_trial_group(
    h5: h5py.File,
    animal_id: str,
    session_id: str,
    trial: str,
    video_path: Optional[str] = None,
    sleap_path: Optional[str] = None,
    run_phase: Optional[str] = None,
    run_mode: Optional[str] = None,
) -> h5py.Group:
    """Create or return trial group. Path: /animal_id/session_id/trial.

    The session group stores phase and mode attributes:
    - run_phase: habituation | habituation_training | VAST
    - run_mode: continuous | alternating
    """
    path = f"/{animal_id}/{session_id}/{trial}"
    if path in h5:
        g = h5[path]
        g_session = g.parent
    else:
        g_animal = _ensure_group(h5, animal_id)
        g_session = _ensure_group(g_animal, session_id)
        g = _ensure_group(g_session, trial)
    if run_phase is not None:
        g_session.attrs["run_phase"] = _safe_str(run_phase)
    if run_mode is not None:
        g_session.attrs["run_mode"] = _safe_str(run_mode)
    if video_path is not None:
        g.attrs["video_path"] = _safe_str(video_path)
    if sleap_path is not None:
        g.attrs["sleap_path"] = _safe_str(sleap_path)
    _ensure_group(g, "ambulation_metrics")
    _ensure_group(g, "qc_images")
    return g


def write_trial_settings(
    g_trial: h5py.Group,
    arena_radius_px: float,
    px_per_cm: float,
    arena_center_x_px: float = 0,
    arena_center_y_px: float = 0,
    timestamp: Optional[str] = None,
    phase: str = "habituation",
    run_mode: str = "continuous",
    exit_x: Optional[float] = None,
    exit_y: Optional[float] = None,
    trial_start_frame: int = 0,
) -> None:
    g_trial.attrs["arena_radius_px"] = float(arena_radius_px)
    g_trial.attrs["px_per_cm"] = float(px_per_cm)
    g_trial.attrs["arena_center_x_px"] = float(arena_center_x_px)
    g_trial.attrs["arena_center_y_px"] = float(arena_center_y_px)
    if timestamp:
        g_trial.attrs["timestamp"] = _safe_str(timestamp)
    g_trial.attrs["phase"] = _safe_str(phase)
    g_trial.attrs["run_mode"] = _safe_str(run_mode)
    if exit_x is not None:
        g_trial.attrs["exit_x"] = float(exit_x)
    if exit_y is not None:
        g_trial.attrs["exit_y"] = float(exit_y)
    g_trial.attrs["trial_start_frame"] = int(trial_start_frame)


def write_feedback_table(g_trial: h5py.Group, fb_table: np.ndarray) -> None:
    """Write unified per-frame feedback table under /feedback/table."""
    fb_table = np.asarray(fb_table, dtype=FEEDBACK_ROW_DTYPE)
    g_fb = _ensure_group(g_trial, FEEDBACK_GROUP)
    if FEEDBACK_TABLE_DATASET in g_fb:
        del g_fb[FEEDBACK_TABLE_DATASET]
    g_fb.create_dataset(FEEDBACK_TABLE_DATASET, data=fb_table, compression="gzip")


def write_xy_table(
    g_trial: h5py.Group,
    point_name: str,
    xy_table: np.ndarray,
    fps: float,
) -> None:
    g_amb = _ensure_group(g_trial, "ambulation_metrics")
    g_pt = _ensure_group(g_amb, point_name)
    if "xy" in g_pt:
        del g_pt["xy"]
    g_pt.create_dataset("xy", data=np.asarray(xy_table, dtype=XY_ROW_DTYPE), compression="gzip")
    g_pt["xy"].attrs["fps"] = float(fps)


def write_video_meta(g_trial: h5py.Group, fps: float, n_frames: int, duration_s: float) -> None:
    g_trial.attrs["fps"] = float(fps)
    g_trial.attrs["n_frames"] = int(n_frames)
    g_trial.attrs["duration_s"] = float(duration_s)
