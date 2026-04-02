from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import h5py
import numpy as np

from .schema import (
    AMBULATION_GROUP,
    FEEDBACK_GROUP,
    FEEDBACK_ROW_DTYPE,
    FEEDBACK_TABLE_DATASET,
    TASK_DATA_GROUP,
    XY_DATASET_NAME,
    XY_ROW_DTYPE,
)
from .tasks import normalize_arena_type


def open_db(db_path: Path | str, mode: str = "a") -> h5py.File:
    """
    Open (and create parent dirs for) an HDF5 database.
    """
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return h5py.File(str(path), mode)


def ensure_group(parent: h5py.Group, name: str) -> h5py.Group:
    """Return an existing child group or create it."""
    return parent[name] if name in parent else parent.create_group(name)


def safe_str(value: Any) -> str:
    """Convert a value to string safely for HDF5 attrs."""
    return "" if value is None else str(value)


def write_json_attr(group: h5py.Group, key: str, obj: Any) -> None:
    """Write a JSON-serializable object as an attribute."""
    group.attrs[key] = json.dumps(obj, ensure_ascii=False)


def ensure_trial_group(
    h5: h5py.File,
    animal_id: str,
    session_id: str,
    trial_id: str,
    *,
    video_path: str | None = None,
    sleap_path: str | None = None,
    attrs: dict[str, Any] | None = None,
) -> h5py.Group:
    """
    Ensure /animal_id/session_id/trial_id exists with standard subgroups.
    Returns the trial group.
    """
    g_animal = ensure_group(h5, animal_id)
    g_session = ensure_group(g_animal, session_id)
    g_trial = ensure_group(g_session, trial_id)

    if video_path is not None:
        g_trial.attrs["video_path"] = safe_str(video_path)
    if sleap_path is not None:
        g_trial.attrs["sleap_path"] = safe_str(sleap_path)
    if attrs:
        write_group_attrs(g_trial, attrs)

    ensure_group(g_trial, AMBULATION_GROUP)
    ensure_group(g_trial, "qc_images")
    return g_trial


def write_group_attrs(group: h5py.Group, attrs: dict[str, Any]) -> None:
    """Write a neutral set of HDF5 attrs, skipping ``None`` values."""
    for key, value in attrs.items():
        if value is None:
            continue
        group.attrs[key] = str(value) if isinstance(value, Path) else value


def ensure_task_group(g_trial: h5py.Group, task_name: str) -> h5py.Group:
    """Return the task-specific extension group under a shared trial container."""
    g_task_root = ensure_group(g_trial, TASK_DATA_GROUP)
    return ensure_group(g_task_root, normalize_arena_type(task_name))


def init_task_database(
    db_path: Path | str,
    *,
    arena_type: str,
    controller_schema_version: str | None = None,
    arena_description: str | None = None,
) -> None:
    """Initialize shared metadata used by both acquisition and offline pipeline code."""
    with open_db(db_path, "a") as h5:
        meta = ensure_group(h5, "metadata")
        if controller_schema_version is not None:
            meta.attrs["controller_schema_version"] = controller_schema_version
        arena = ensure_group(meta, "arena_info")
        arena.attrs["type"] = normalize_arena_type(arena_type)
        if arena_description is not None:
            arena.attrs["description"] = arena_description


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
