from __future__ import annotations

from pathlib import Path
from typing import Any

import h5py
import numpy as np

from .schema import (
    XY_ROW_DTYPE,
    FEEDBACK_ROW_DTYPE,
    FEEDBACK_GROUP,
    FEEDBACK_TABLE_DATASET,
    AMBULATION_GROUP,
    XY_DATASET_NAME,
)


def open_db(db_path: Path | str, mode: str = "a") -> h5py.File:
    """
    Open (and create parent dirs for) an HDF5 database.
    """
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return h5py.File(str(path), mode)


def ensure_trial_group(
    h5: h5py.File,
    animal_id: str,
    session_id: str,
    trial_id: str,
    *,
    video_path: str | None = None,
    sleap_path: str | None = None,
) -> h5py.Group:
    """
    Ensure /animal_id/session_id/trial_id exists with standard subgroups.
    Returns the trial group.
    """
    g_animal = h5.require_group(animal_id)
    g_session = g_animal.require_group(session_id)
    g_trial = g_session.require_group(trial_id)

    if video_path is not None:
        g_trial.attrs["video_path"] = str(video_path)
    if sleap_path is not None:
        g_trial.attrs["sleap_path"] = str(sleap_path)

    g_trial.require_group(AMBULATION_GROUP)
    g_trial.require_group("qc_images")
    return g_trial


def write_xy_table(
    g_trial: h5py.Group,
    point_name: str,
    xy_table: np.ndarray,
    fps: float,
) -> None:
    """
    Write ambulation_metrics/<point_name>/xy with shared XY_ROW_DTYPE and fps attr.
    """
    g_amb = g_trial.require_group(AMBULATION_GROUP)
    g_pt = g_amb.require_group(point_name)
    if XY_DATASET_NAME in g_pt:
        del g_pt[XY_DATASET_NAME]
    ds = g_pt.create_dataset(
        XY_DATASET_NAME,
        data=np.asarray(xy_table, dtype=XY_ROW_DTYPE),
        compression="gzip",
    )
    ds.attrs["fps"] = float(fps)


def write_feedback_table(
    g_trial: h5py.Group,
    fb_table: np.ndarray,
) -> None:
    """
    Write unified feedback/table with shared FEEDBACK_ROW_DTYPE.
    """
    g_fb = g_trial.require_group(FEEDBACK_GROUP)
    if FEEDBACK_TABLE_DATASET in g_fb:
        del g_fb[FEEDBACK_TABLE_DATASET]
    g_fb.create_dataset(
        FEEDBACK_TABLE_DATASET,
        data=np.asarray(fb_table, dtype=FEEDBACK_ROW_DTYPE),
        compression="gzip",
    )


def read_feedback_table(
    g_trial: h5py.Group,
) -> np.ndarray | None:
    """
    Read feedback/table if present; returns np.ndarray with FEEDBACK_ROW_DTYPE or None.
    """
    g_fb = g_trial.get(FEEDBACK_GROUP)
    if g_fb is None or FEEDBACK_TABLE_DATASET not in g_fb:
        return None
    return g_fb[FEEDBACK_TABLE_DATASET][:].astype(FEEDBACK_ROW_DTYPE, copy=False)

