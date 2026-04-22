"""RAM template: walkable tracking mask (union minus exit hole) and crop bbox."""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

from .radial_arm.config import RadialArmControllerConfig, ram_derived_px_per_cm
from .radial_arm.geometry import (
    build_template_from_params,
    exit_hole_xyr_px,
    projected_region_polygons_px,
)


def ram_uncalibrated(config: RadialArmControllerConfig) -> bool:
    ram = config.radial_arm
    return ram_derived_px_per_cm(ram.template, ram.calibration) <= 0.0


def ram_walkable_mask_crop(
    config: RadialArmControllerConfig,
    frame_h: int,
    frame_w: int,
) -> Optional[Tuple[np.ndarray, int, int, int, int]]:
    """
    Build a uint8 mask (255 = trackable) on the crop bbox, with exit hole subtracted.

    Returns ``(mask, x0, y0, x1, y1)`` in full-frame coordinates, or ``None`` if scale
    is not set or OpenCV polygons are empty.
    """
    try:
        import cv2
    except ImportError:
        return None

    ram = config.radial_arm
    tcfg = ram.template
    cal = ram.calibration
    ppc = ram_derived_px_per_cm(tcfg, cal)
    if ppc <= 0.0 or frame_h <= 0 or frame_w <= 0:
        return None

    template = build_template_from_params(
        center_midedge_to_midedge_cm=tcfg.center_midedge_to_midedge_cm,
        arm_length_cm=tcfg.arm_length_cm,
        arm_width_cm=tcfg.arm_width_cm,
        arm_split_cm=tcfg.arm_split_cm,
        hole_arm_index=tcfg.hole_arm_index,
        hole_radius_cm=tcfg.hole_radius_cm,
        hole_inset_from_arm_end_cm=tcfg.hole_inset_from_arm_end_cm,
    )
    polys = projected_region_polygons_px(
        template,
        center_x_px=cal.template_center_x_px,
        center_y_px=cal.template_center_y_px,
        rotation_deg=cal.template_rotation_deg,
        px_per_cm=ppc,
    )
    if not polys:
        return None

    walk_keys = [k for k in polys if k != "hole"]
    pts_list = [np.asarray(polys[k], dtype=np.float64) for k in walk_keys if k in polys]
    if "hole" in polys:
        pts_list.append(np.asarray(polys["hole"], dtype=np.float64))
    if not pts_list:
        return None
    all_pts = np.vstack(pts_list)
    minx = float(np.min(all_pts[:, 0]))
    maxx = float(np.max(all_pts[:, 0]))
    miny = float(np.min(all_pts[:, 1]))
    maxy = float(np.max(all_pts[:, 1]))
    half_w = max((maxx - minx) / 2.0, 1.0)
    half_h = max((maxy - miny) / 2.0, 1.0)
    margin = float(cal.tracking_mask_margin_px)
    if margin <= 0.0:
        margin = 0.2 * max(half_w, half_h)
    margin_i = int(max(2.0, round(margin)))

    x0 = int(np.clip(np.floor(minx - margin_i), 0, frame_w - 1))
    y0 = int(np.clip(np.floor(miny - margin_i), 0, frame_h - 1))
    x1 = int(np.clip(np.ceil(maxx + margin_i), 0, frame_w))
    y1 = int(np.clip(np.ceil(maxy + margin_i), 0, frame_h))
    if x1 <= x0 + 1 or y1 <= y0 + 1:
        return None

    cw, ch = x1 - x0, y1 - y0
    mask = np.zeros((ch, cw), dtype=np.uint8)
    for k in walk_keys:
        poly = np.asarray(polys[k], dtype=np.float64)
        if poly.size < 6:
            continue
        cnt = (poly - np.array([[x0, y0]], dtype=np.float64)).astype(np.int32)
        cv2.fillPoly(mask, [cnt], 255)

    if "hole" in polys:
        hp = (np.asarray(polys["hole"], dtype=np.float64) - np.array([[x0, y0]], dtype=np.float64)).astype(
            np.int32
        )
        if hp.shape[0] >= 3:
            cv2.fillPoly(mask, [hp], 0)

    if int(np.max(mask)) == 0:
        return None
    return (mask, x0, y0, x1, y1)


def ram_exit_hole_xyr_px(
    config: RadialArmControllerConfig,
) -> Optional[tuple[float, float, float]]:
    """Exit hole center and radius in image pixels, or None if uncalibrated."""
    ram = config.radial_arm
    tcfg = ram.template
    cal = ram.calibration
    ppc = ram_derived_px_per_cm(tcfg, cal)
    if ppc <= 0.0:
        return None
    template = build_template_from_params(
        center_midedge_to_midedge_cm=tcfg.center_midedge_to_midedge_cm,
        arm_length_cm=tcfg.arm_length_cm,
        arm_width_cm=tcfg.arm_width_cm,
        arm_split_cm=tcfg.arm_split_cm,
        hole_arm_index=tcfg.hole_arm_index,
        hole_radius_cm=tcfg.hole_radius_cm,
        hole_inset_from_arm_end_cm=tcfg.hole_inset_from_arm_end_cm,
    )
    return exit_hole_xyr_px(
        template,
        exit_arm_index=int(ram.exit_arm_index),
        center_x_px=cal.template_center_x_px,
        center_y_px=cal.template_center_y_px,
        rotation_deg=cal.template_rotation_deg,
        px_per_cm=ppc,
    )


def ram_template_polylines_image(
    config: RadialArmControllerConfig,
) -> Optional[dict[str, np.ndarray]]:
    """Projected region polylines in full image px, or None if uncalibrated."""
    ram = config.radial_arm
    tcfg = ram.template
    cal = ram.calibration
    ppc = ram_derived_px_per_cm(tcfg, cal)
    if ppc <= 0.0:
        return None
    template = build_template_from_params(
        center_midedge_to_midedge_cm=tcfg.center_midedge_to_midedge_cm,
        arm_length_cm=tcfg.arm_length_cm,
        arm_width_cm=tcfg.arm_width_cm,
        arm_split_cm=tcfg.arm_split_cm,
        hole_arm_index=tcfg.hole_arm_index,
        hole_radius_cm=tcfg.hole_radius_cm,
        hole_inset_from_arm_end_cm=tcfg.hole_inset_from_arm_end_cm,
    )
    return projected_region_polygons_px(
        template,
        center_x_px=cal.template_center_x_px,
        center_y_px=cal.template_center_y_px,
        rotation_deg=cal.template_rotation_deg,
        px_per_cm=ppc,
    )
