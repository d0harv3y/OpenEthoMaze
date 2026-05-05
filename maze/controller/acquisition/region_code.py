"""
Per-frame spatial region labels shared by VAST and RAM acquisition and the pipeline.

VAST uses a stateful tracker for overlapping exit disks; RAM uses projected template
polygons with priority exit > back > front > center.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import numpy as np

from maze.core.tasks import ARENA_TYPE_RADIAL_ARM

from .vast.arena import (
    distance_px,
    exit_center_px,
    in_center_region,
)
from .vast.config import ArenaConfig, ExitAngleConfig

REGION_OOB = "oob"
REGION_CENTER = "center"
REGION_ANNULUS = "annulus"


def point_in_polygon_xy(x: float, y: float, poly: np.ndarray) -> bool:
    """Ray-cast test; ``poly`` shape (N, 2)."""
    poly = np.asarray(poly, dtype=float)
    if poly.shape[0] < 3:
        return False
    inside = False
    n = poly.shape[0]
    j = n - 1
    for i in range(n):
        xi, yi = float(poly[i, 0]), float(poly[i, 1])
        xj, yj = float(poly[j, 0]), float(poly[j, 1])
        denom = yj - yi
        if denom == 0.0:
            denom = 1e-30
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / denom + xi:
            inside = not inside
        j = i
    return inside


@dataclass
class VastRegionCodeTracker:
    """Tracks overlapping VAST exit disks (assigned exit wins; else new entry; else sticky)."""

    _prev_inside: set[int] = field(default_factory=set)
    _last_exit_idx: int | None = None

    def reset(self) -> None:
        self._prev_inside = set()
        self._last_exit_idx = None

    def update(
        self,
        x_px: float,
        y_px: float,
        *,
        arena: ArenaConfig,
        exit_angles: ExitAngleConfig,
        assigned_exit_index: int,
    ) -> str:
        cx, cy = arena.arena_center_x_px, arena.arena_center_y_px
        if distance_px(x_px, y_px, cx, cy) > arena.radius_px:
            self._prev_inside = set()
            self._last_exit_idx = None
            return REGION_OOB

        r_exit_px = arena.exit_radius_cm * arena.px_per_cm
        n = int(exit_angles.n_angles)
        inside: set[int] = set()
        for i in range(n):
            ex, ey = exit_center_px(x_px, y_px, i, arena, exit_angles)
            if distance_px(x_px, y_px, ex, ey) <= r_exit_px:
                inside.add(i)

        new_entries = inside - self._prev_inside

        if not inside:
            self._prev_inside = set()
            self._last_exit_idx = None
            if in_center_region(x_px, y_px, arena):
                return REGION_CENTER
            return REGION_ANNULUS

        assigned = int(max(0, min(n - 1, assigned_exit_index)))
        if assigned in inside:
            chosen = assigned
        elif new_entries:
            chosen = min(new_entries)
        elif self._last_exit_idx is not None and self._last_exit_idx in inside:
            chosen = self._last_exit_idx
        else:
            chosen = min(inside)

        self._last_exit_idx = chosen
        self._prev_inside = set(inside)
        return f"exit{chosen + 1}"


def ram_region_code(
    x_px: float,
    y_px: float,
    polys_px: Mapping[str, np.ndarray],
    hole_arm_index_1based: int,
) -> str:
    """Classify RAM position given image-space polygons (``projected_region_polygons_px`` output)."""
    x, y = float(x_px), float(y_px)
    hole = polys_px.get("hole")
    if hole is not None and point_in_polygon_xy(x, y, hole):
        return f"arm{int(hole_arm_index_1based)}_exit"

    for k in range(8):
        key = f"arm{k}_back"
        poly = polys_px.get(key)
        if poly is not None and point_in_polygon_xy(x, y, poly):
            return f"arm{k + 1}_back"

    for k in range(8):
        key = f"arm{k}_front"
        poly = polys_px.get(key)
        if poly is not None and point_in_polygon_xy(x, y, poly):
            return f"arm{k + 1}_front"

    center = polys_px.get("center")
    if center is not None and point_in_polygon_xy(x, y, center):
        return REGION_CENTER

    return REGION_OOB


def encode_region_code_bytes(region_id: str) -> bytes:
    """Pad/truncate to 16 bytes for :data:`~maze.core.schema.XY_ROW_DTYPE` ``region_code``."""
    raw = str(region_id).strip().encode("utf-8")[:16]
    return raw.ljust(16, b"\0")


def arena_config_from_trial_settings(settings: Any) -> ArenaConfig:
    """Rebuild minimal :class:`~maze.controller.acquisition.vast.config.ArenaConfig` from pipeline settings."""
    r_cm = float(settings.arena_radius_cm)
    dia = 2.0 * max(r_cm, 1e-6)
    erc = float(settings.exit_radius_cm or 12.5)
    return ArenaConfig(
        diameter_cm=dia,
        radius_px=float(settings.arena_radius_px),
        center_pct=0.7,
        exit_radius_cm=erc,
        arena_center_x_px=float(settings.arena_center_x_px),
        arena_center_y_px=float(settings.arena_center_y_px),
    )


def projected_ram_polys_from_geometry_payload(
    geometry_payload: dict,
    exit_arm_index: int,
) -> tuple[dict[str, np.ndarray], int]:
    """Project RAM template regions to pixels using stored geometry payload."""
    from .radial_arm.geometry import build_template_from_params, projected_region_polygons_px

    tp = geometry_payload.get("template_params", {}) or {}
    cal = geometry_payload.get("calibration", {}) or {}
    template = build_template_from_params(
        center_midedge_to_midedge_cm=float(tp.get("center_midedge_to_midedge_cm", 80.0)),
        arm_length_cm=float(tp.get("arm_length_cm", 55.0)),
        arm_width_cm=float(tp.get("arm_width_cm", 15.0)),
        arm_split_cm=float(tp.get("arm_split_cm", 27.5)),
        exit_arm_index=int(exit_arm_index),
        hole_radius_cm=float(tp.get("hole_radius_cm", 5.0)),
        hole_inset_from_arm_end_cm=float(tp.get("hole_inset_from_arm_end_cm", 10.0)),
    )
    polys = projected_region_polygons_px(
        template,
        center_x_px=float(cal.get("template_center_x_px", 0.0)),
        center_y_px=float(cal.get("template_center_y_px", 0.0)),
        rotation_deg=float(cal.get("template_rotation_deg", 0.0)),
        px_per_cm=float(cal.get("px_per_cm", 1.0)),
    )
    return polys, int(template.hole_arm_index) + 1


def compute_trace_region_codes(
    xy: np.ndarray,
    *,
    arena_type: str,
    geometry_payload: dict | None,
    exit_arm_index: int,
    arena_config: ArenaConfig,
    exit_angles: ExitAngleConfig,
    assigned_exit_index: int,
) -> list[str]:
    """Per-frame region ids for a full trajectory (pipeline; matches acquisition rules)."""
    n = int(xy.shape[0])
    out: list[str] = []
    if arena_type == ARENA_TYPE_RADIAL_ARM and geometry_payload:
        polys, hole_1b = projected_ram_polys_from_geometry_payload(
            geometry_payload, exit_arm_index
        )
        for i in range(n):
            x, y = float(xy[i, 0]), float(xy[i, 1])
            if not np.isfinite(x) or not np.isfinite(y):
                out.append(REGION_OOB)
            else:
                out.append(ram_region_code(x, y, polys, hole_1b))
        return out

    tracker = VastRegionCodeTracker()
    for i in range(n):
        x, y = float(xy[i, 0]), float(xy[i, 1])
        if not np.isfinite(x) or not np.isfinite(y):
            tracker.reset()
            out.append(REGION_OOB)
            continue
        out.append(
            tracker.update(
                x,
                y,
                arena=arena_config,
                exit_angles=exit_angles,
                assigned_exit_index=int(assigned_exit_index),
            )
        )
    return out
