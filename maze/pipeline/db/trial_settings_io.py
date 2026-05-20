from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np

from maze.core.trial_settings import TrialSettings, parse_timestamp
from maze.core.h5_layout import ensure_task_group, write_group_attrs

from .radial_arm_geometry_io import (
    read_radial_arm_geometry_tree,
    write_radial_arm_geometry_tree,
)
from ...controller.acquisition.radial_arm.geometry import (
    build_template_from_params,
    exit_hole_xyr_px,
    max_template_radius_cm,
)
from ._shared import open_db, safe_str
from .ambulation_xy import read_xy_table
from .trial_key import TrialKey

from ..defaults import (
    FILTER_FRAMES_NO_ANIMAL,
    IN_RANGE_POINT_NAME,
    JUMP_FILTER_LOOKAHEAD_FRAMES,
    MAX_MOVEMENT_PER_FRAME_CM,
    MIN_CONFIDENT_NODES_PER_FRAME,
    MIN_MEAN_CONFIDENCE_PER_FRAME,
    MIN_NODE_CONFIDENCE_THRESHOLD,
    MIN_VALID_FRAME_RUN_LENGTH,
    TRACE_APPLY_SMOOTHING,
    TRACE_CONFIDENCE_THRESHOLD,
    TRACE_INTERPOLATE_LOW_CONF,
    TRACE_INTERPOLATE_NANS,
    TRACE_MAX_GAP_FRAMES,
    TRACE_SMOOTHING_WINDOW,
)


@dataclass(frozen=True)
class TrialTiming:
    """Controller / pipeline timing for splitting trace rows into seek, ITI, and run bands.

    When :attr:`use_absolute_frame_index` is True (controller writes ``seek_to_frame``),
    :attr:`seek_to_frame` and :attr:`run_start_frame` are absolute indices into the source
    video timebase (virtual file frame index or 0-based live encode index). Otherwise
    (legacy trials), only :attr:`run_start_frame` is used and it is a row index into the
    trace; :attr:`seek_to_frame` is ignored and treated as 0.
    """

    seek_to_frame: int
    run_start_frame: int
    use_absolute_frame_index: bool


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


def _radial_arm_shared_attr_fallback(g_trial) -> dict[str, Any]:
    """Synthesize the minimal shared trial attrs from RAM task-local geometry."""
    g_task_root = g_trial.get("task_data")
    if g_task_root is None or "radial_arm" not in g_task_root:
        return {}
    g_task = g_task_root["radial_arm"]
    geometry_payload = read_radial_arm_geometry_tree(g_task)
    calibration = geometry_payload.get("calibration", {}) or {}
    template_regions_cm = geometry_payload.get("template_regions_cm", {}) or {}
    if not template_regions_cm:
        return {}

    px_per_cm = float(g_trial.attrs.get("px_per_cm", calibration.get("px_per_cm", 0.0)) or 0.0)
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

    template_params = geometry_payload.get("template_params", {}) or {}
    template = build_template_from_params(
        center_midedge_to_midedge_cm=float(
            template_params.get("center_midedge_to_midedge_cm", 80.0)
        ),
        arm_length_cm=float(template_params.get("arm_length_cm", 55.0)),
        arm_width_cm=float(template_params.get("arm_width_cm", 15.0)),
        arm_split_cm=float(template_params.get("arm_split_cm", 27.5)),
        exit_arm_index=int(
            template_params.get(
                "exit_arm_index",
                template_params.get("hole_arm_index", exit_arm_index),
            )
        ),
        hole_radius_cm=float(template_params.get("hole_radius_cm", 5.0)),
        hole_inset_from_arm_end_cm=float(template_params.get("hole_inset_from_arm_end_cm", 10.0)),
    )
    exit_x_px, exit_y_px, exit_radius_px = exit_hole_xyr_px(
        template,
        exit_arm_index=exit_arm_index,
        center_x_px=center_x_px,
        center_y_px=center_y_px,
        rotation_deg=rotation_deg,
        px_per_cm=px_per_cm,
    )
    return {
        "arena_center_x_px": center_x_px,
        "arena_center_y_px": center_y_px,
        "arena_radius_px": float(max_template_radius_cm(template) * px_per_cm),
        "px_per_cm": px_per_cm,
        "exit_number": exit_arm_index + 1,
        "exit_x": exit_x_px,
        "exit_y": exit_y_px,
        "exit_radius_px": exit_radius_px,
    }


def radial_arm_exit_hole_from_geometry_payload(
    geometry_payload: dict[str, Any],
    *,
    exit_arm_index: int,
) -> Optional[tuple[float, float, float]]:
    """
    Escape-hole center and radius in pixels from persisted RAM geometry.

    Matches :func:`maze.controller.acquisition.radial_arm.geometry.exit_hole_xyr_px`
    / acquisition recording so QC overlays use the same exit disk as the controller.
    """
    if not isinstance(geometry_payload, dict):
        return None
    calibration = geometry_payload.get("calibration", {}) or {}
    px_per_cm = float(calibration.get("px_per_cm", 0.0) or 0.0)
    if px_per_cm <= 0.0:
        return None
    center_x_px = float(calibration.get("template_center_x_px", 0.0) or 0.0)
    center_y_px = float(calibration.get("template_center_y_px", 0.0) or 0.0)
    rotation_deg = float(calibration.get("template_rotation_deg", 0.0) or 0.0)
    trial_exit = max(0, int(exit_arm_index))
    template_params = geometry_payload.get("template_params", {}) or {}
    template_shape_exit = int(
        template_params.get(
            "exit_arm_index",
            template_params.get("hole_arm_index", trial_exit),
        )
    )
    template = build_template_from_params(
        center_midedge_to_midedge_cm=float(
            template_params.get("center_midedge_to_midedge_cm", 80.0)
        ),
        arm_length_cm=float(template_params.get("arm_length_cm", 55.0)),
        arm_width_cm=float(template_params.get("arm_width_cm", 15.0)),
        arm_split_cm=float(template_params.get("arm_split_cm", 27.5)),
        exit_arm_index=template_shape_exit,
        hole_radius_cm=float(template_params.get("hole_radius_cm", 5.0)),
        hole_inset_from_arm_end_cm=float(template_params.get("hole_inset_from_arm_end_cm", 10.0)),
    )
    ex, ey, er = exit_hole_xyr_px(
        template,
        exit_arm_index=trial_exit,
        center_x_px=center_x_px,
        center_y_px=center_y_px,
        rotation_deg=rotation_deg,
        px_per_cm=px_per_cm,
    )
    return (float(ex), float(ey), float(er))


def infer_first_run_row_from_xy(db_path: Optional[Path], key: TrialKey) -> int:
    """First row index whose ``trial_state`` is ``run`` in controller xy, or ``0``."""
    if db_path is None:
        return 0
    for point_name in (IN_RANGE_POINT_NAME, "spot"):
        xy = read_xy_table(db_path, key, point_name=point_name)
        if xy is None or xy.shape[0] == 0:
            continue
        names = xy.dtype.names or ()
        if "trial_state" not in names:
            continue
        for i in range(xy.shape[0]):
            ts = xy["trial_state"][i]
            if isinstance(ts, bytes):
                ts = ts.decode("utf-8", errors="replace")
            if str(ts).strip().lower() == "run":
                return int(i)
    return 0


def read_spot_frame_index_column(db_path: Optional[Path], key: TrialKey) -> Optional[np.ndarray]:
    """Return ``frame_index`` column from spot xy table if present."""
    if db_path is None:
        return None
    xy = read_xy_table(db_path, key, point_name="spot")
    if xy is None or xy.shape[0] == 0:
        return None
    names = xy.dtype.names or ()
    if "frame_index" not in names:
        return None
    return np.asarray(xy["frame_index"], dtype=np.int64)


def compute_seek_run_rows(
    n_frames: int,
    frame_indices: Optional[np.ndarray],
    timing: TrialTiming,
) -> tuple[int, int]:
    """Map timing to ``(seek_row, run_row)`` row indices into a length-``n_frames`` trace."""
    n_frames = int(n_frames)
    if n_frames <= 0:
        return (0, 0)
    fi = frame_indices
    if fi is None or fi.size != n_frames:
        fi = np.arange(n_frames, dtype=np.int64)
    else:
        fi = np.asarray(fi, dtype=np.int64)
    if not timing.use_absolute_frame_index:
        seek_row = 0
        run_row = int(np.clip(timing.run_start_frame, 0, n_frames))
        return (seek_row, run_row)
    seek_row = int(np.searchsorted(fi, int(timing.seek_to_frame), side="left"))
    run_row = int(np.searchsorted(fi, int(timing.run_start_frame), side="left"))
    seek_row = int(np.clip(seek_row, 0, n_frames))
    run_row = int(np.clip(run_row, seek_row, n_frames))
    return (seek_row, run_row)


def complete_trial_timing(
    db_path: Optional[Path],
    key: TrialKey,
    timing: TrialTiming,
) -> TrialTiming:
    """Fill ``run_start_frame`` when attrs omitted but controller xy labels a ``run`` row."""
    if timing.run_start_frame > 0:
        return timing
    row = infer_first_run_row_from_xy(db_path, key)
    if row <= 0:
        return timing
    if timing.use_absolute_frame_index:
        fi = read_spot_frame_index_column(db_path, key)
        if fi is not None and row < len(fi):
            return TrialTiming(timing.seek_to_frame, int(fi[row]), True)
        return TrialTiming(timing.seek_to_frame, row, True)
    return TrialTiming(0, row, False)


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
    exit_radius_px: Optional[float] = None,
    roi_old: Optional[str] = None,
    h5_fps: Optional[float] = None,
    trial_start_frame: Optional[int] = None,
    seek_to_frame: Optional[int] = None,
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
        if exit_radius_px is not None:
            g_trial.attrs["exit_radius_px"] = float(exit_radius_px)
        if roi_old is not None:
            g_trial.attrs["roi_old"] = safe_str(roi_old)
        if h5_fps is not None:
            g_trial.attrs["h5_fps"] = float(h5_fps)
        if trial_start_frame is not None:
            g_trial.attrs["trial_start_frame"] = int(trial_start_frame)
        if seek_to_frame is not None:
            g_trial.attrs["seek_to_frame"] = int(seek_to_frame)


def read_trial_settings(
    db_path: Optional[Path],
    key: TrialKey,
) -> tuple[TrialSettings, Optional[float], TrialTiming]:
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
                    int(fallback_attrs["exit_number"]) if "exit_number" in fallback_attrs else None
                )
            ),
            exit_x=(
                float(attrs["exit_x"])
                if "exit_x" in attrs
                else (float(fallback_attrs["exit_x"]) if "exit_x" in fallback_attrs else None)
            ),
            exit_y=(
                float(attrs["exit_y"])
                if "exit_y" in attrs
                else (float(fallback_attrs["exit_y"]) if "exit_y" in fallback_attrs else None)
            ),
            exit_radius_px=(
                float(attrs["exit_radius_px"])
                if "exit_radius_px" in attrs
                else (
                    float(fallback_attrs["exit_radius_px"])
                    if "exit_radius_px" in fallback_attrs
                    else None
                )
            ),
            roi_old=roi_old,
            movement_start_threshold_m_per_frame=float(
                attrs.get(
                    "movement_start_threshold_m_per_frame",
                    fallback_attrs.get("movement_start_threshold_m_per_frame", (2**0.5) / 150),
                )
            ),
            movement_stop_threshold_m_per_frame=float(
                attrs.get(
                    "movement_stop_threshold_m_per_frame",
                    fallback_attrs.get("movement_stop_threshold_m_per_frame", (2**0.5) / 300),
                )
            ),
            movement_speed_median_window_frames=max(
                1,
                int(
                    attrs.get(
                        "movement_speed_median_window_frames",
                        fallback_attrs.get("movement_speed_median_window_frames", 3),
                    )
                ),
            ),
            movement_entry_debounce_frames=max(
                1,
                int(
                    attrs.get(
                        "movement_entry_debounce_frames",
                        fallback_attrs.get("movement_entry_debounce_frames", 3),
                    )
                ),
            ),
            movement_exit_debounce_frames=max(
                1,
                int(
                    attrs.get(
                        "movement_exit_debounce_frames",
                        fallback_attrs.get("movement_exit_debounce_frames", 3),
                    )
                ),
            ),
            min_movement_bout_duration_frames=max(
                1,
                int(
                    attrs.get(
                        "min_movement_bout_duration_frames",
                        fallback_attrs.get("min_movement_bout_duration_frames", 4),
                    )
                ),
            ),
            movement_inter_bout_interval_frames=max(
                0,
                int(
                    attrs.get(
                        "movement_inter_bout_interval_frames",
                        fallback_attrs.get("movement_inter_bout_interval_frames", 4),
                    )
                ),
            ),
            max_movement_per_frame_cm=float(
                attrs.get(
                    "max_movement_per_frame_cm",
                    fallback_attrs.get("max_movement_per_frame_cm", MAX_MOVEMENT_PER_FRAME_CM),
                )
            ),
            jump_filter_lookahead_frames=max(
                0,
                int(
                    attrs.get(
                        "jump_filter_lookahead_frames",
                        fallback_attrs.get(
                            "jump_filter_lookahead_frames",
                            JUMP_FILTER_LOOKAHEAD_FRAMES,
                        ),
                    )
                ),
            ),
            filter_frames_no_animal=bool(
                attrs.get("filter_frames_no_animal", FILTER_FRAMES_NO_ANIMAL)
            ),
            min_confident_nodes_per_frame=max(
                0,
                int(
                    attrs.get(
                        "min_confident_nodes_per_frame",
                        MIN_CONFIDENT_NODES_PER_FRAME,
                    )
                ),
            ),
            min_node_confidence_threshold=float(
                attrs.get(
                    "min_node_confidence_threshold",
                    MIN_NODE_CONFIDENCE_THRESHOLD,
                )
            ),
            min_valid_frame_run_length=max(
                0,
                int(
                    attrs.get(
                        "min_valid_frame_run_length",
                        MIN_VALID_FRAME_RUN_LENGTH,
                    )
                ),
            ),
            min_mean_confidence_per_frame=(
                float(attrs["min_mean_confidence_per_frame"])
                if "min_mean_confidence_per_frame" in attrs
                and attrs["min_mean_confidence_per_frame"] is not None
                else MIN_MEAN_CONFIDENCE_PER_FRAME
            ),
            trace_interpolate_nans=bool(
                attrs.get("trace_interpolate_nans", TRACE_INTERPOLATE_NANS)
            ),
            trace_max_gap_frames=max(
                0,
                int(attrs.get("trace_max_gap_frames", TRACE_MAX_GAP_FRAMES)),
            ),
            trace_interpolate_low_conf=bool(
                attrs.get("trace_interpolate_low_conf", TRACE_INTERPOLATE_LOW_CONF)
            ),
            trace_confidence_threshold=float(
                attrs.get("trace_confidence_threshold", TRACE_CONFIDENCE_THRESHOLD)
            ),
            trace_apply_smoothing=bool(attrs.get("trace_apply_smoothing", TRACE_APPLY_SMOOTHING)),
            trace_smoothing_window=max(
                1,
                int(attrs.get("trace_smoothing_window", TRACE_SMOOTHING_WINDOW)),
            ),
        )
        h5_fps = float(attrs["h5_fps"]) if "h5_fps" in attrs else None
        trial_start_frame = int(attrs["trial_start_frame"]) if "trial_start_frame" in attrs else 0
        use_abs = "seek_to_frame" in attrs
        seek_to_frame = int(_decode_attr(attrs["seek_to_frame"])) if use_abs else 0
        timing = TrialTiming(
            seek_to_frame=seek_to_frame,
            run_start_frame=trial_start_frame,
            use_absolute_frame_index=use_abs,
        )
    return settings, h5_fps, timing


def persist_effective_analysis_params(
    db_path: Optional[Path],
    key: TrialKey,
    settings: TrialSettings,
) -> None:
    """Write movement, trace-quality, and completion attrs after a successful ``process_trial`` run."""
    if db_path is None:
        return
    completed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open_db(db_path, "a") as h5:
        g = h5[key.path()]
        g.attrs["movement_start_threshold_m_per_frame"] = float(
            settings.movement_start_threshold_m_per_frame
        )
        g.attrs["movement_stop_threshold_m_per_frame"] = float(
            settings.movement_stop_threshold_m_per_frame
        )
        g.attrs["movement_speed_median_window_frames"] = int(
            settings.movement_speed_median_window_frames
        )
        g.attrs["movement_entry_debounce_frames"] = int(settings.movement_entry_debounce_frames)
        g.attrs["movement_exit_debounce_frames"] = int(settings.movement_exit_debounce_frames)
        g.attrs["min_movement_bout_duration_frames"] = int(
            settings.min_movement_bout_duration_frames
        )
        g.attrs["movement_inter_bout_interval_frames"] = int(
            settings.movement_inter_bout_interval_frames
        )
        g.attrs["max_movement_per_frame_cm"] = float(settings.max_movement_per_frame_cm)
        g.attrs["jump_filter_lookahead_frames"] = int(settings.jump_filter_lookahead_frames)
        g.attrs["filter_frames_no_animal"] = int(bool(settings.filter_frames_no_animal))
        g.attrs["min_confident_nodes_per_frame"] = int(settings.min_confident_nodes_per_frame)
        g.attrs["min_node_confidence_threshold"] = float(settings.min_node_confidence_threshold)
        g.attrs["min_valid_frame_run_length"] = int(settings.min_valid_frame_run_length)
        if settings.min_mean_confidence_per_frame is not None:
            g.attrs["min_mean_confidence_per_frame"] = float(settings.min_mean_confidence_per_frame)
        elif "min_mean_confidence_per_frame" in g.attrs:
            del g.attrs["min_mean_confidence_per_frame"]
        g.attrs["trace_interpolate_nans"] = int(bool(settings.trace_interpolate_nans))
        g.attrs["trace_max_gap_frames"] = int(settings.trace_max_gap_frames)
        g.attrs["trace_interpolate_low_conf"] = int(bool(settings.trace_interpolate_low_conf))
        g.attrs["trace_confidence_threshold"] = float(settings.trace_confidence_threshold)
        g.attrs["trace_apply_smoothing"] = int(bool(settings.trace_apply_smoothing))
        g.attrs["trace_smoothing_window"] = int(settings.trace_smoothing_window)
        g.attrs["analysis_completed_at"] = safe_str(completed)


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
        write_radial_arm_geometry_tree(g_task, geometry_payload)


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
        geometry_payload = read_radial_arm_geometry_tree(g_task)
        return {
            "trial_attrs": {
                name: _decode_attr(g_trial.attrs[name]) for name in g_trial.attrs.keys()
            },
            "task_attrs": {name: _decode_attr(g_task.attrs[name]) for name in g_task.attrs.keys()},
            "geometry_payload": geometry_payload,
        }
