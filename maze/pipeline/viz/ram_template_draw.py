"""Project RAM task template geometry to pixel polylines for unified overlay."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import numpy as np

from maze.controller.acquisition.radial_arm.geometry import (
    build_template_from_params,
    projected_region_polygons_px,
)
from maze.core.trial_settings import TrialSettings
from maze.pipeline.db.trial_key import TrialKey
from maze.pipeline.db.trial_settings_io import read_radial_arm_trial_settings


def _as_float(x: Any, default: float) -> float:
    if x is None:
        return default
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _as_int(x: Any, default: int) -> int:
    if x is None:
        return default
    try:
        return int(x)
    except (TypeError, ValueError):
        return default


def load_ram_region_polygons_px(
    pipeline_db: Path,
    key: TrialKey,
    settings: TrialSettings,
) -> Optional[dict[str, np.ndarray]]:
    """
    Load RAM template regions as closed polylines in image pixels (center octagon, arm rects, hole).

    Reads ``task_data/radial_arm`` geometry (same source as
    :func:`maze.pipeline.db.trial_settings_io.read_radial_arm_trial_settings`).
    Missing ``template_params`` uses the same defaults as the legacy import. Returns
    ``None`` only if there is no ``task_data/radial_arm`` group or ``px_per_cm`` is unusable.

    Note: Drawing uses this task group and :func:`~maze.pipeline.db.read_trial_settings`, not
    ``metadata/arena_info`` (which may be absent, default to circular elsewhere, or not match
    radial-arm geometry written under ``task_data``).
    """
    data = read_radial_arm_trial_settings(pipeline_db, key)
    if not data:
        return None
    gp = data.get("geometry_payload") or {}
    calibration = gp.get("calibration") or {}
    template_params = gp.get("template_params") or {}
    trial_attrs = data.get("trial_attrs") or {}

    tp = template_params
    exit_arm = _as_int(trial_attrs.get("exit_arm_index"), 0)
    template = build_template_from_params(
        center_midedge_to_midedge_cm=_as_float(
            tp.get("center_midedge_to_midedge_cm"),
            80.0,
        ),
        arm_length_cm=_as_float(tp.get("arm_length_cm"), 55.0),
        arm_width_cm=_as_float(tp.get("arm_width_cm"), 15.0),
        arm_split_cm=_as_float(tp.get("arm_split_cm"), 27.5),
        exit_arm_index=_as_int(
            tp.get("exit_arm_index", tp.get("hole_arm_index")),
            exit_arm,
        ),
        hole_radius_cm=_as_float(tp.get("hole_radius_cm"), 5.0),
        hole_inset_from_arm_end_cm=_as_float(
            tp.get("hole_inset_from_arm_end_cm"),
            10.0,
        ),
    )

    rotation_deg = _as_float(
        trial_attrs.get("template_rotation_deg")
        or calibration.get("template_rotation_deg"),
        0.0,
    )

    if settings.px_per_cm <= 0:
        return None

    return projected_region_polygons_px(
        template,
        center_x_px=float(settings.arena_center_x_px),
        center_y_px=float(settings.arena_center_y_px),
        rotation_deg=rotation_deg,
        px_per_cm=float(settings.px_per_cm),
    )
