from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from ...controller.acquisition.radial_arm.geometry import (
    build_template_from_params,
    projected_region_polygons_px,
)
from ...controller.acquisition.radial_arm.legacy_template import (
    LEGACY_RAM_TEMPLATE,
    legacy_escape_hole_xyr,
)


ENTRY_DEBOUNCE_FRAMES = 10


@dataclass(frozen=True)
class RadialArmRegionBounds:
    """Image-space RAM regions used for downstream trajectory interpretation."""

    center_poly_xy: np.ndarray
    arms_poly_xy: dict[tuple[int, int], np.ndarray]
    exit_hole_xyr: np.ndarray
    exit_arm_index: int
    px_per_cm: float


def default_region_code_map() -> dict[str, int]:
    """Stable RAM region-code mapping."""
    mapping: dict[str, int] = {"unknown": 0, "center": 1, "hole": 99}
    for arm in range(8):
        mapping[f"arm{arm}_front"] = 2 + arm * 2
        mapping[f"arm{arm}_back"] = 3 + arm * 2
    return mapping


def decode_arm_from_region_code(code: int) -> Optional[tuple[int, int]]:
    """Decode one region code back into ``(arm_index, half_index)``."""
    if code < 2 or code > 17:
        return None
    k = int(code) - 2
    return int(k // 2), int(k % 2)


def _point_in_polygon(point_xy: np.ndarray, poly_xy: np.ndarray) -> bool:
    x = float(point_xy[0])
    y = float(point_xy[1])
    poly = np.asarray(poly_xy, dtype=float)
    inside = False
    n = int(poly.shape[0])
    j = n - 1
    for i in range(n):
        xi, yi = float(poly[i, 0]), float(poly[i, 1])
        xj, yj = float(poly[j, 0]), float(poly[j, 1])
        intersects = ((yi > y) != (yj > y)) and (
            x
            < ((xj - xi) * (y - yi) / ((yj - yi) if (yj - yi) != 0 else 1e-12)) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def assign_region_code(
    xy: np.ndarray,
    valid: bool,
    bounds: RadialArmRegionBounds,
    code_map: dict[str, int] | None = None,
) -> int:
    """Assign one trajectory sample to a RAM region code."""
    mapping = code_map or default_region_code_map()
    if not bool(valid):
        return int(mapping["unknown"])

    x = float(xy[0])
    y = float(xy[1])
    if not np.isfinite(x) or not np.isfinite(y):
        return int(mapping["unknown"])

    hx, hy, hr = (
        float(bounds.exit_hole_xyr[0]),
        float(bounds.exit_hole_xyr[1]),
        float(bounds.exit_hole_xyr[2]),
    )
    dx = x - hx
    dy = y - hy
    if hr > 0 and (dx * dx + dy * dy) <= (hr * hr):
        return int(mapping["hole"])

    pt = np.asarray([x, y], dtype=float)
    for arm in range(8):
        for half in (0, 1):
            poly = bounds.arms_poly_xy.get((arm, half))
            if poly is not None and _point_in_polygon(pt, poly):
                return int(mapping[f"arm{arm}_{'front' if half == 0 else 'back'}"])
    if _point_in_polygon(pt, bounds.center_poly_xy):
        return int(mapping["center"])
    return int(mapping["unknown"])


def region_codes_from_trajectory(
    xy: np.ndarray,
    valid: np.ndarray,
    bounds: RadialArmRegionBounds,
) -> np.ndarray:
    """Label every frame of one shared trajectory against RAM regions."""
    codes = np.zeros((xy.shape[0],), dtype=np.int16)
    mapping = default_region_code_map()
    for i in range(xy.shape[0]):
        codes[i] = assign_region_code(xy[i], bool(valid[i]), bounds, mapping)
    return codes


def bounds_from_geometry_payload(
    geometry_payload: dict[str, object],
    *,
    exit_arm_index: int,
) -> Optional[RadialArmRegionBounds]:
    """Build RAM bounds from controller-written geometry payload."""
    template_params = geometry_payload.get("template_params", {})
    calibration = geometry_payload.get("calibration", {})
    if not isinstance(template_params, dict) or not isinstance(calibration, dict):
        return None

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
        hole_inset_from_arm_end_cm=float(
            template_params.get("hole_inset_from_arm_end_cm", 10.0)
        ),
    )
    px_per_cm = float(calibration.get("px_per_cm", 0.0) or 0.0)
    projected = projected_region_polygons_px(
        template,
        center_x_px=float(calibration.get("template_center_x_px", 0.0) or 0.0),
        center_y_px=float(calibration.get("template_center_y_px", 0.0) or 0.0),
        rotation_deg=float(calibration.get("template_rotation_deg", 0.0) or 0.0),
        px_per_cm=px_per_cm,
    )
    arms: dict[tuple[int, int], np.ndarray] = {}
    for arm in range(8):
        front = projected.get(f"arm{arm}_front")
        back = projected.get(f"arm{arm}_back")
        if front is not None:
            arms[(arm, 0)] = front.astype(np.float32)
        if back is not None:
            arms[(arm, 1)] = back.astype(np.float32)
    hole = projected.get("hole")
    if hole is not None and hole.size > 0:
        hole_center = np.mean(hole, axis=0)
        hole_radius = float(template.hole_radius_cm * px_per_cm)
        hole_xyr = np.asarray([hole_center[0], hole_center[1], hole_radius], dtype=np.float32)
    else:
        hole_xyr = np.asarray([0.0, 0.0, 0.0], dtype=np.float32)
    return RadialArmRegionBounds(
        center_poly_xy=projected["center"].astype(np.float32),
        arms_poly_xy=arms,
        exit_hole_xyr=hole_xyr,
        exit_arm_index=int(exit_arm_index),
        px_per_cm=px_per_cm,
    )


def legacy_bounds(
    *,
    exit_arm_index: int,
) -> RadialArmRegionBounds:
    """Return the migrated legacy RAM template bounds."""
    arms: dict[tuple[int, int], np.ndarray] = {}
    for row in LEGACY_RAM_TEMPLATE.arms_table:
        arm = int(row["arm_index"])
        half = int(row["half_index"])
        arms[(arm, half)] = np.asarray(
            [
                [row["x0"], row["y0"]],
                [row["x1"], row["y1"]],
                [row["x2"], row["y2"]],
                [row["x3"], row["y3"]],
            ],
            dtype=np.float32,
        )
    return RadialArmRegionBounds(
        center_poly_xy=LEGACY_RAM_TEMPLATE.center_poly_xy.astype(np.float32),
        arms_poly_xy=arms,
        exit_hole_xyr=np.asarray(
            legacy_escape_hole_xyr(exit_arm_index),
            dtype=np.float32,
        ),
        exit_arm_index=int(exit_arm_index),
        px_per_cm=float(LEGACY_RAM_TEMPLATE.px_per_cm),
    )


def compute_arm_memory_metrics(
    region_codes: np.ndarray,
    *,
    exit_arm_index: int,
    debounce_frames: int = ENTRY_DEBOUNCE_FRAMES,
) -> dict[str, int]:
    """Compute RAM working/reference memory metrics from a region-code timeline."""
    codes = np.asarray(region_codes, dtype=int)
    visited_arms = [False] * 8
    wme = 0
    rme = 0
    rms = 0

    current_arm: Optional[int] = None
    current_arm_had_back = False
    current_arm_is_incorrect = False
    current_arm_entered_from_center = False
    pending_front_entry: Optional[tuple[int, int]] = None
    pending_back_entry: Optional[tuple[int, int]] = None

    def end_bout(*, exit_to_center: bool) -> None:
        nonlocal rms, current_arm, current_arm_had_back, current_arm_is_incorrect
        nonlocal current_arm_entered_from_center, pending_front_entry, pending_back_entry
        if current_arm is not None and current_arm_is_incorrect:
            if not current_arm_had_back and current_arm_entered_from_center and exit_to_center:
                rms += 1
        current_arm = None
        current_arm_had_back = False
        current_arm_is_incorrect = False
        current_arm_entered_from_center = False
        pending_front_entry = None
        pending_back_entry = None

    def check_pending_entry(frame_idx: int, arm: int, half: int) -> None:
        nonlocal wme, rme, pending_front_entry, pending_back_entry, current_arm_had_back

        if pending_front_entry is not None:
            pending_arm, pending_start = pending_front_entry
            if arm == pending_arm and half == 0:
                if (frame_idx - pending_start + 1) >= debounce_frames:
                    prev_dec = (
                        decode_arm_from_region_code(int(codes[pending_start - 1]))
                        if pending_start > 0
                        else None
                    )
                    is_entry_from_outside = prev_dec is None or prev_dec[0] != pending_arm
                    if is_entry_from_outside:
                        if visited_arms[pending_arm]:
                            wme += 1
                        else:
                            visited_arms[pending_arm] = True
                    pending_front_entry = None
            else:
                pending_front_entry = None

        if pending_back_entry is not None:
            pending_arm, pending_start = pending_back_entry
            if arm == pending_arm and half == 1:
                if (frame_idx - pending_start + 1) >= debounce_frames:
                    current_arm_had_back = True
                    rme += 1
                    pending_back_entry = None
            else:
                pending_back_entry = None

    for i in range(int(codes.shape[0])):
        dec = decode_arm_from_region_code(int(codes[i]))
        if dec is not None:
            check_pending_entry(i, int(dec[0]), int(dec[1]))

        if dec is None:
            region_code = int(codes[i])
            is_center = region_code == 1
            pending_front_entry = None
            pending_back_entry = None
            if current_arm is not None and is_center:
                end_bout(exit_to_center=True)
            continue

        arm = int(dec[0])
        half = int(dec[1])

        if current_arm is None:
            prev_region_code = int(codes[i - 1]) if i > 0 else 0
            current_arm = arm
            current_arm_had_back = False
            current_arm_is_incorrect = arm != int(exit_arm_index)
            current_arm_entered_from_center = prev_region_code == 1
        elif current_arm != arm:
            end_bout(exit_to_center=False)
            current_arm = arm
            current_arm_had_back = False
            current_arm_is_incorrect = arm != int(exit_arm_index)
            current_arm_entered_from_center = False

        if arm == int(exit_arm_index):
            if half == 1:
                current_arm_had_back = True
            continue

        if half == 0:
            prev = decode_arm_from_region_code(int(codes[i - 1])) if i > 0 else None
            is_entry_from_outside = prev is None or int(prev[0]) != arm
            if is_entry_from_outside and pending_front_entry is None:
                pending_front_entry = (arm, i)
            if pending_front_entry is not None and (i - pending_front_entry[1] + 1) >= debounce_frames:
                check_pending_entry(i, arm, half)
        else:
            prev = decode_arm_from_region_code(int(codes[i - 1])) if i > 0 else None
            prev_same_back = prev is not None and int(prev[0]) == arm and int(prev[1]) == 1
            if not prev_same_back and pending_back_entry is None:
                pending_back_entry = (arm, i)
            if pending_back_entry is not None and (i - pending_back_entry[1] + 1) >= debounce_frames:
                check_pending_entry(i, arm, half)

    if current_arm is not None:
        end_bout(exit_to_center=False)

    return {
        "working_memory_errors": int(wme),
        "reference_memory_errors": int(rme),
        "reference_memory_successes": int(rms),
    }
