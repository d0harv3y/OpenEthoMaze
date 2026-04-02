from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Optional

import numpy as np

from maze.core.trial_settings import TrialSettings, parse_timestamp
from maze.core.h5_layout import ensure_task_group, write_group_attrs
from ._shared import open_db, safe_str
from .trial_key import TrialKey


def _decode_attr(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return value


def _load_json_attr(group, attr_name: str) -> dict[str, Any]:
    raw = group.attrs.get(attr_name, "{}")
    raw = _decode_attr(raw)
    try:
        loaded = json.loads(str(raw) or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _transform_template_point_to_px(
    point_cm: tuple[float, float],
    *,
    center_x_px: float,
    center_y_px: float,
    rotation_deg: float,
    px_per_cm: float,
) -> tuple[float, float]:
    px, py = point_cm
    theta = math.radians(float(rotation_deg))
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    x_rot = (float(px) * cos_t) - (float(py) * sin_t)
    y_rot = (float(px) * sin_t) + (float(py) * cos_t)
    return (
        float(center_x_px) + (x_rot * float(px_per_cm)),
        float(center_y_px) + (y_rot * float(px_per_cm)),
    )


def _radial_arm_shared_attr_fallback(g_trial) -> dict[str, Any]:
    """Synthesize the minimal shared trial attrs from RAM task-local geometry."""
    g_task_root = g_trial.get("task_data")
    if g_task_root is None or "radial_arm" not in g_task_root:
        return {}
    g_task = g_task_root["radial_arm"]
    geometry_payload = _load_json_attr(g_task, "geometry_payload")
    calibration = geometry_payload.get("calibration", {}) or _load_json_attr(
        g_task, "calibration"
    )
    template_regions_cm = geometry_payload.get(
        "template_regions_cm", {}
    ) or _load_json_attr(g_task, "template_regions_cm")
    if not template_regions_cm:
        return {}

    px_per_cm = float(
        g_trial.attrs.get("px_per_cm", calibration.get("px_per_cm", 0.0)) or 0.0
    )
    center_x_px = float(
        g_trial.attrs.get(
            "arena_center_x_px",
            g_trial.attrs.get(
                "template_center_x_px",
                calibration.get("template_center_x_px", 0.0),
            ),
        )
        or 0.0
    )
    center_y_px = float(
        g_trial.attrs.get(
            "arena_center_y_px",
            g_trial.attrs.get(
                "template_center_y_px",
                calibration.get("template_center_y_px", 0.0),
            ),
        )
        or 0.0
    )
    rotation_deg = float(
        g_trial.attrs.get(
            "template_rotation_deg",
            calibration.get("template_rotation_deg", 0.0),
        )
        or 0.0
    )
    exit_arm_index = int(
        g_trial.attrs.get(
            "exit_arm_index",
            g_task.attrs.get("exit_arm_index", 0),
        )
        or 0
    )

    max_radius_cm = 0.0
    exit_point_cm = (0.0, 0.0)
    for name, poly in template_regions_cm.items():
        arr = np.asarray(poly, dtype=float)
        if arr.size == 0:
            continue
        radii = np.linalg.norm(arr, axis=1)
        if radii.size:
            max_radius_cm = max(max_radius_cm, float(np.max(radii)))
        if name in (f"arm{exit_arm_index}_back", f"arm{exit_arm_index}_front") and arr.shape[0] >= 2:
            farthest = arr[np.argsort(radii)[-2:]]
            exit_point_cm = (
                float(np.mean(farthest[:, 0])),
                float(np.mean(farthest[:, 1])),
            )

    exit_x_px, exit_y_px = _transform_template_point_to_px(
        exit_point_cm,
        center_x_px=center_x_px,
        center_y_px=center_y_px,
        rotation_deg=rotation_deg,
        px_per_cm=px_per_cm,
    )
    return {
        "arena_center_x_px": center_x_px,
        "arena_center_y_px": center_y_px,
        "arena_radius_px": float(max_radius_cm * px_per_cm),
        "px_per_cm": px_per_cm,
        "exit_number": exit_arm_index + 1,
        "exit_x": exit_x_px,
        "exit_y": exit_y_px,
    }


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
        fallback_attrs = _radial_arm_shared_attr_fallback(g_trial)
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
            arena_center_x_px=float(
                attrs.get(
                    "arena_center_x_px",
                    fallback_attrs.get("arena_center_x_px", 0.0),
                )
            ),
            arena_center_y_px=float(
                attrs.get(
                    "arena_center_y_px",
                    fallback_attrs.get("arena_center_y_px", 0.0),
                )
            ),
            arena_radius_px=float(
                attrs.get(
                    "arena_radius_px",
                    fallback_attrs.get("arena_radius_px", 0.0),
                )
            ),
            px_per_cm=float(attrs.get("px_per_cm", fallback_attrs.get("px_per_cm", 0.0))),
            stage=stage,
            color=color,
            timestamp=timestamp,
            exit_number=(
                int(attrs["exit_number"])
                if "exit_number" in attrs
                else (
                    int(fallback_attrs["exit_number"])
                    if "exit_number" in fallback_attrs
                    else None
                )
            ),
            exit_x=(
                float(attrs["exit_x"])
                if "exit_x" in attrs
                else (
                    float(fallback_attrs["exit_x"])
                    if "exit_x" in fallback_attrs
                    else None
                )
            ),
            exit_y=(
                float(attrs["exit_y"])
                if "exit_y" in attrs
                else (
                    float(fallback_attrs["exit_y"])
                    if "exit_y" in fallback_attrs
                    else None
                )
            ),
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
        geometry_payload = _load_json_attr(g_task, "geometry_payload")
        if not geometry_payload:
            geometry_payload = {
                "template_params": _load_json_attr(g_task, "template_params"),
                "calibration": _load_json_attr(g_task, "calibration"),
                "template_regions_cm": _load_json_attr(g_task, "template_regions_cm"),
            }
        return {
            "trial_attrs": {
                name: _decode_attr(g_trial.attrs[name]) for name in g_trial.attrs.keys()
            },
            "task_attrs": {
                name: _decode_attr(g_task.attrs[name]) for name in g_task.attrs.keys()
            },
            "geometry_payload": geometry_payload,
        }
