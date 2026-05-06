"""
Shared acquisition HDF5 writer for controller-recorded trials.

The layout matches ``maze.pipeline.db`` so the offline pipeline can read
either VAST or RAM trials from the same shared container structure.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import h5py
import numpy as np

from maze.core.schema import (
    XY_ROW_DTYPE,
    FEEDBACK_ROW_DTYPE,
)
from maze.core.h5_layout import (
    ensure_group,
    ensure_task_group,
    ensure_trial_group as core_ensure_trial_group,
    init_task_database,
    open_db,
    safe_str,
    write_feedback_table as core_write_feedback_table,
    write_group_attrs,
    write_xy_table as core_write_xy_table,
)
from maze.core.tasks import ARENA_TYPE_CIRCULAR, ARENA_TYPE_RADIAL_ARM, normalize_arena_type
from maze.pipeline.db.radial_arm_geometry_io import write_radial_arm_geometry_tree
from .radial_arm.config import RadialArmControllerConfig
from .radial_arm.geometry import (
    build_template_from_params,
    exit_hole_xyr_px,
    max_template_radius_cm,
)

__all__ = [
    "open_db",
    "init_database",
    "ensure_trial_group",
    "write_trial_settings",
    "write_feedback_table",
    "write_xy_table",
    "write_video_meta",
    "write_animal_label",
    "compute_radial_arm_settings_payloads",
    "write_radial_arm_trial_settings",
]


def init_database(db_path: Path, arena_type: str = ARENA_TYPE_CIRCULAR) -> None:
    """Compatibility wrapper around the shared database bootstrap path."""
    init_task_database(
        db_path,
        arena_type=normalize_arena_type(arena_type),
        controller_schema_version="v1",
    )


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
    g = core_ensure_trial_group(
        h5,
        animal_id,
        session_id,
        trial,
        video_path=safe_str(video_path) if video_path is not None else None,
        sleap_path=safe_str(sleap_path) if sleap_path is not None else None,
    )
    write_group_attrs(
        g.parent,
        {
            "run_phase": safe_str(run_phase) if run_phase is not None else None,
            "run_mode": safe_str(run_mode) if run_mode is not None else None,
        },
    )
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
    exit_radius_px: Optional[float] = None,
    trial_start_frame: int = 0,
    seek_to_frame: int = 0,
) -> None:
    """Persist geometry/session attrs only; analysis parameters are written after ``process_trial``."""
    write_group_attrs(
        g_trial,
        {
            "arena_radius_px": float(arena_radius_px),
            "px_per_cm": float(px_per_cm),
            "arena_center_x_px": float(arena_center_x_px),
            "arena_center_y_px": float(arena_center_y_px),
            "timestamp": safe_str(timestamp) if timestamp else None,
            "phase": safe_str(phase),
            "stage": safe_str(phase),
            "run_mode": safe_str(run_mode),
            "exit_x": float(exit_x) if exit_x is not None else None,
            "exit_y": float(exit_y) if exit_y is not None else None,
            "exit_radius_px": float(exit_radius_px) if exit_radius_px is not None else None,
            "trial_start_frame": int(trial_start_frame),
            "seek_to_frame": int(seek_to_frame),
        },
    )


def compute_radial_arm_settings_payloads(
    config: RadialArmControllerConfig,
    *,
    timestamp: Optional[str] = None,
    phase: str = "radial_arm",
    run_mode: str = "continuous",
    trial_start_frame: int = 0,
    seek_to_frame: int = 0,
    ram_exit_arm_index: Optional[int] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """Build trial/task attrs and geometry JSON for RAM trials (acquisition or pipeline import).

    When ``ram_exit_arm_index`` is set (0..7), use it for this trial's escape hole in attrs and
    ``exit_x``/``exit_y``; otherwise use ``config.radial_arm.exit_arm_index`` (profile default).
    Template geometry still follows the profile (printed maze hole arm).
    """
    ram = config.radial_arm
    calibration = ram.calibration
    template_cfg = ram.template
    template = build_template_from_params(
        center_midedge_to_midedge_cm=template_cfg.center_midedge_to_midedge_cm,
        arm_length_cm=template_cfg.arm_length_cm,
        arm_width_cm=template_cfg.arm_width_cm,
        arm_split_cm=template_cfg.arm_split_cm,
        exit_arm_index=int(ram.exit_arm_index),
        hole_radius_cm=template_cfg.hole_radius_cm,
        hole_inset_from_arm_end_cm=template_cfg.hole_inset_from_arm_end_cm,
    )
    template_regions_cm = {
        name: np.asarray(poly, dtype=float).tolist()
        for name, poly in template.regions_cm.items()
    }
    max_radius_cm = max_template_radius_cm(template)
    trial_exit_arm_index = int(ram.exit_arm_index)
    if ram_exit_arm_index is not None:
        trial_exit_arm_index = int(ram_exit_arm_index)
    trial_exit_arm_index = max(0, min(7, trial_exit_arm_index))
    exit_x_px, exit_y_px, exit_radius_px = exit_hole_xyr_px(
        template,
        exit_arm_index=trial_exit_arm_index,
        center_x_px=calibration.template_center_x_px,
        center_y_px=calibration.template_center_y_px,
        rotation_deg=calibration.template_rotation_deg,
        px_per_cm=calibration.px_per_cm,
    )
    trial_attrs: Dict[str, Any] = {
        "phase": safe_str(phase),
        "stage": safe_str(phase),
        "run_mode": safe_str(run_mode),
        "timestamp": safe_str(timestamp) if timestamp else None,
        "arena_type": ARENA_TYPE_RADIAL_ARM,
        "trial_start_frame": int(trial_start_frame),
        "seek_to_frame": int(seek_to_frame),
        "arena_center_x_px": float(calibration.template_center_x_px),
        "arena_center_y_px": float(calibration.template_center_y_px),
        "arena_radius_px": float(max_radius_cm * float(calibration.px_per_cm)),
        "template_center_x_px": float(calibration.template_center_x_px),
        "template_center_y_px": float(calibration.template_center_y_px),
        "template_rotation_deg": float(calibration.template_rotation_deg),
        "px_per_cm": float(calibration.px_per_cm),
        "exit_number": trial_exit_arm_index + 1,
        "exit_x": float(exit_x_px),
        "exit_y": float(exit_y_px),
        "exit_radius_px": float(exit_radius_px),
        "exit_arm_index": trial_exit_arm_index,
        "speaker_device_name": safe_str(ram.speaker_device_name),
        "speaker_volume_pct": float(ram.speaker_volume_pct),
        "stimulus_frequency_hz": float(ram.stimulus_frequency_hz),
        "stimulus_enabled": int(bool(ram.stimulus_enabled)),
        "active_edit_region": safe_str(calibration.edit_region_name),
    }
    task_attrs: Dict[str, Any] = {
        "task_name": ARENA_TYPE_RADIAL_ARM,
        "exit_arm_index": trial_exit_arm_index,
        "speaker_device_name": safe_str(ram.speaker_device_name),
        "speaker_volume_pct": float(ram.speaker_volume_pct),
        "stimulus_frequency_hz": float(ram.stimulus_frequency_hz),
        "stimulus_enabled": int(bool(ram.stimulus_enabled)),
        "edit_region_name": safe_str(calibration.edit_region_name),
    }
    geometry_payload: Dict[str, Any] = {
        "template_params": {
            "center_midedge_to_midedge_cm": template_cfg.center_midedge_to_midedge_cm,
            "arm_length_cm": template_cfg.arm_length_cm,
            "arm_width_cm": template_cfg.arm_width_cm,
            "arm_split_cm": template_cfg.arm_split_cm,
            "hole_radius_cm": template_cfg.hole_radius_cm,
            "hole_inset_from_arm_end_cm": template_cfg.hole_inset_from_arm_end_cm,
        },
        "calibration": {
            "template_center_x_px": calibration.template_center_x_px,
            "template_center_y_px": calibration.template_center_y_px,
            "template_rotation_deg": calibration.template_rotation_deg,
            "apothem_px": float(calibration.apothem_px),
            "px_per_cm": calibration.px_per_cm,
            "tracking_mask_margin_px": float(calibration.tracking_mask_margin_px),
            "edit_region_name": calibration.edit_region_name,
        },
        "template_regions_cm": template_regions_cm,
    }
    return trial_attrs, task_attrs, geometry_payload


def write_radial_arm_trial_settings(
    g_trial: h5py.Group,
    config: RadialArmControllerConfig,
    *,
    timestamp: Optional[str] = None,
    phase: str = "radial_arm",
    run_mode: str = "continuous",
    trial_start_frame: int = 0,
    seek_to_frame: int = 0,
    ram_exit_arm_index: Optional[int] = None,
) -> None:
    """Persist RAM trial attrs plus a task-local geometry payload."""
    trial_attrs, task_attrs, geometry_payload = compute_radial_arm_settings_payloads(
        config,
        timestamp=timestamp,
        phase=phase,
        run_mode=run_mode,
        trial_start_frame=trial_start_frame,
        seek_to_frame=seek_to_frame,
        ram_exit_arm_index=ram_exit_arm_index,
    )
    write_group_attrs(g_trial, trial_attrs)
    g_task = ensure_task_group(g_trial, ARENA_TYPE_RADIAL_ARM)
    write_group_attrs(g_task, task_attrs)
    write_radial_arm_geometry_tree(g_task, geometry_payload)


def write_feedback_table(g_trial: h5py.Group, fb_table: np.ndarray) -> None:
    """Write unified per-frame feedback table under /feedback/table."""
    fb_table = np.asarray(fb_table, dtype=FEEDBACK_ROW_DTYPE)
    core_write_feedback_table(g_trial, fb_table)


def write_xy_table(
    g_trial: h5py.Group,
    point_name: str,
    xy_table: np.ndarray,
    fps: float,
) -> None:
    core_write_xy_table(
        g_trial,
        point_name,
        np.asarray(xy_table, dtype=XY_ROW_DTYPE),
        fps,
    )


def write_video_meta(g_trial: h5py.Group, fps: float, n_frames: int, duration_s: float) -> None:
    write_group_attrs(
        g_trial,
        {"fps": float(fps), "n_frames": int(n_frames), "duration_s": float(duration_s)},
    )


def write_animal_label(
    h5: h5py.File,
    animal_id: str,
    sex: Optional[str] = None,
    tx: Optional[str] = None,
    strain: Optional[str] = None,
    experiment: Optional[str] = None,
    researcher: Optional[str] = None,
    drug: Optional[str] = None,
    notes: Optional[str] = None,
) -> None:
    """Write per-animal metadata attributes on ``/{animal_id}``."""
    g_animal = ensure_group(h5, animal_id)
    write_group_attrs(
        g_animal,
        {
            "sex": safe_str(sex) if sex is not None else None,
            "tx": safe_str(tx) if tx is not None else None,
            "strain": safe_str(strain) if strain is not None else None,
            "experiment": safe_str(experiment) if experiment is not None else None,
            "researcher": safe_str(researcher) if researcher is not None else None,
            "drug": safe_str(drug) if drug is not None else None,
            "notes": safe_str(notes) if notes is not None else None,
        },
    )
