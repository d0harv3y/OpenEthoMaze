from __future__ import annotations

from typing import Any

from .shared_config import AcquisitionConfig
from .radial_arm.geometry import build_template_from_params, max_template_radius_cm


def normalize_run_mode_value(
    run_mode: str | None,
    *,
    default: str = "continuous",
) -> str:
    """Normalize controller run-order strings shared by VAST and RAM."""
    value = str(run_mode or default).strip().lower()
    return value or default


def build_run_button_states(
    *,
    state: Any | None,
    run_active: bool,
    can_start_prev_next_states: tuple[Any, ...],
    running_states: tuple[Any, ...],
) -> dict[str, bool]:
    """Return the shared GUI button-state contract for acquisition controllers."""
    out = {
        "start": True,
        "previous": True,
        "next": True,
        "end_trial": False,
        "stop": run_active,
    }
    if state is None:
        return out
    out["start"] = state in can_start_prev_next_states
    out["previous"] = state in can_start_prev_next_states
    out["next"] = state in can_start_prev_next_states
    out["end_trial"] = state in running_states
    return out


def config_center_xy(config: AcquisitionConfig) -> tuple[float, float]:
    """Return the best available task center point for tracking fallbacks."""
    if hasattr(config, "arena"):
        arena = config.arena
        return (float(arena.arena_center_x_px), float(arena.arena_center_y_px))
    if hasattr(config, "radial_arm"):
        calibration = config.radial_arm.calibration
        return (
            float(calibration.template_center_x_px),
            float(calibration.template_center_y_px),
        )
    return (0.0, 0.0)


def config_tracking_roi(config: AcquisitionConfig) -> tuple[float, float, float]:
    """Return task-specific preview ROI center/radius used by shared tracking."""
    if hasattr(config, "arena"):
        arena = config.arena
        return (
            float(arena.arena_center_x_px),
            float(arena.arena_center_y_px),
            float(arena.radius_px),
        )
    if hasattr(config, "radial_arm"):
        calibration = config.radial_arm.calibration
        template = build_template_from_params(
            center_midedge_to_midedge_cm=config.radial_arm.template.center_midedge_to_midedge_cm,
            arm_length_cm=config.radial_arm.template.arm_length_cm,
            arm_width_cm=config.radial_arm.template.arm_width_cm,
            arm_split_cm=config.radial_arm.template.arm_split_cm,
            hole_arm_index=config.radial_arm.template.hole_arm_index,
            hole_radius_cm=config.radial_arm.template.hole_radius_cm,
            hole_inset_from_arm_end_cm=config.radial_arm.template.hole_inset_from_arm_end_cm,
        )
        return (
            float(calibration.template_center_x_px),
            float(calibration.template_center_y_px),
            float(max_template_radius_cm(template) * float(calibration.px_per_cm)),
        )
    return (0.0, 0.0, 0.0)
