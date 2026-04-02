from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from maze.core.trial_settings import TrialSettings, parse_timestamp
from maze.core.storage import ensure_task_group, write_group_attrs
from ._shared import open_db, safe_str
from .trial_key import TrialKey


def write_trial_settings(
    db_path: Optional[Path],
    key: TrialKey,
    arena_radius_px: float,
    px_per_cm: float,
    arena_center_x_px: Optional[float] = None,
    arena_center_y_px: Optional[float] = None,
    timestamp: Optional[str] = None,
    stage: Optional[str] = None,
    color: Optional[str] = None,
    exit_number: Optional[int] = None,
    exit_x: Optional[float] = None,
    exit_y: Optional[float] = None,
    roi_old: Optional[str] = None,
    h5_fps: Optional[float] = None,
    trial_start_frame: Optional[int] = None,
) -> None:
    """Write trial settings (exit position and arena geometry) to database."""
    with open_db(db_path, "a") as h5:
        g_trial = h5[key.path()]
        g_trial.attrs["arena_radius_px"] = float(arena_radius_px)
        g_trial.attrs["px_per_cm"] = float(px_per_cm)
        if arena_center_x_px is not None:
            g_trial.attrs["arena_center_x_px"] = float(arena_center_x_px)
        if arena_center_y_px is not None:
            g_trial.attrs["arena_center_y_px"] = float(arena_center_y_px)
        if timestamp is not None:
            g_trial.attrs["timestamp"] = safe_str(timestamp)
        if stage is not None:
            g_trial.attrs["stage"] = safe_str(stage)
        if color is not None:
            g_trial.attrs["color"] = safe_str(color)
        if exit_number is not None:
            g_trial.attrs["exit_number"] = int(exit_number)
        if exit_x is not None:
            g_trial.attrs["exit_x"] = float(exit_x)
        if exit_y is not None:
            g_trial.attrs["exit_y"] = float(exit_y)
        if roi_old is not None:
            g_trial.attrs["roi_old"] = safe_str(roi_old)
        if h5_fps is not None:
            g_trial.attrs["h5_fps"] = float(h5_fps)
        if trial_start_frame is not None:
            g_trial.attrs["trial_start_frame"] = int(trial_start_frame)


def read_trial_settings(
    db_path: Optional[Path],
    key: TrialKey,
) -> tuple:
    """Read trial settings from the output database."""
    with open_db(db_path, "r") as h5:
        g_trial = h5[key.path()]
        attrs = g_trial.attrs
        timestamp_str = attrs.get("timestamp", None)
        if isinstance(timestamp_str, bytes):
            timestamp_str = timestamp_str.decode("utf-8")
        timestamp = parse_timestamp(timestamp_str) if timestamp_str else None

        stage = attrs.get("stage", attrs.get("phase", ""))
        if isinstance(stage, bytes):
            stage = stage.decode("utf-8")
        color = attrs.get("color", "")
        if isinstance(color, bytes):
            color = color.decode("utf-8")
        roi_old = attrs.get("roi_old", None)
        if isinstance(roi_old, bytes):
            roi_old = roi_old.decode("utf-8")

        settings = TrialSettings(
            arena_center_x_px=float(attrs.get("arena_center_x_px", 0.0)),
            arena_center_y_px=float(attrs.get("arena_center_y_px", 0.0)),
            arena_radius_px=float(attrs["arena_radius_px"]),
            px_per_cm=float(attrs["px_per_cm"]),
            stage=stage,
            color=color,
            timestamp=timestamp,
            exit_number=int(attrs["exit_number"]) if "exit_number" in attrs else None,
            exit_x=float(attrs["exit_x"]) if "exit_x" in attrs else None,
            exit_y=float(attrs["exit_y"]) if "exit_y" in attrs else None,
            roi_old=roi_old,
        )
        h5_fps = float(attrs["h5_fps"]) if "h5_fps" in attrs else None
        trial_start_frame = (
            int(attrs["trial_start_frame"]) if "trial_start_frame" in attrs else 0
        )
    return settings, h5_fps, trial_start_frame


def write_radial_arm_trial_settings(
    db_path: Optional[Path],
    key: TrialKey,
    *,
    trial_attrs: dict[str, Any],
    task_attrs: dict[str, Any],
    geometry_payload: dict[str, Any],
) -> None:
    """Persist RAM trial settings under the shared trial group and task-local subtree."""
    if db_path is None:
        return
    with open_db(db_path, "a") as h5:
        g_trial = h5[key.path()]
        write_group_attrs(g_trial, trial_attrs)
        g_task = ensure_task_group(g_trial, "radial_arm")
        write_group_attrs(g_task, task_attrs)
        g_task.attrs["geometry_payload"] = json.dumps(
            geometry_payload, ensure_ascii=False
        )


def read_radial_arm_trial_settings(
    db_path: Optional[Path],
    key: TrialKey,
) -> dict[str, Any]:
    """Read RAM task-local settings and geometry payload for a trial."""
    if db_path is None:
        return {}
    with open_db(db_path, "r") as h5:
        g_trial = h5[key.path()]
        g_task_root = g_trial.get("task_data")
        if g_task_root is None or "radial_arm" not in g_task_root:
            return {}
        g_task = g_task_root["radial_arm"]
        geometry_payload = g_task.attrs.get("geometry_payload", "{}")
        if isinstance(geometry_payload, bytes):
            geometry_payload = geometry_payload.decode("utf-8")
        return {
            "trial_attrs": {name: g_trial.attrs[name] for name in g_trial.attrs.keys()},
            "task_attrs": {name: g_task.attrs[name] for name in g_task.attrs.keys()},
            "geometry_payload": json.loads(str(geometry_payload) or "{}"),
        }
