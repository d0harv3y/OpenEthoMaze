from __future__ import annotations

from typing import Any, Optional, Tuple

import numpy as np

from maze.core.anatomy import is_spot_node_name

from ..vast import VastOverlayInfo, VastPhase, VastTrialState

try:
    import cv2

    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


def count_sleap_keypoints_in_exit(
    pose_xy: Optional[np.ndarray],
    pose_node_valid: Optional[np.ndarray],
    pose_node_names: Optional[list],
    exit_x_px: float,
    exit_y_px: float,
    exit_radius_px: float,
) -> int:
    """Count valid SLEAP keypoints plus synthetic centroid/spot inside the exit."""
    if pose_xy is None or pose_node_valid is None or pose_xy.size == 0:
        return 0
    if pose_xy.ndim != 2 or pose_xy.shape[1] != 2 or pose_node_valid.shape != (pose_xy.shape[0],):
        return 0
    if exit_radius_px <= 0:
        return 0
    pts = pose_xy[pose_node_valid]
    if pts.size > 0 and np.all(np.isfinite(pts)):
        centroid = np.array([[float(np.mean(pts[:, 0])), float(np.mean(pts[:, 1]))]])
        pts = np.vstack([pts, centroid])
    if pose_node_names is not None and len(pose_node_names) >= pose_xy.shape[0]:
        fore_inds = [
            i
            for i in range(pose_xy.shape[0])
            if pose_node_valid[i] and is_spot_node_name(str(pose_node_names[i]))
        ]
        if fore_inds:
            fore_pts = pose_xy[fore_inds]
            if np.all(np.isfinite(fore_pts)):
                spot = np.array([[float(np.mean(fore_pts[:, 0])), float(np.mean(fore_pts[:, 1]))]])
                pts = np.vstack([pts, spot])
    if pts.size == 0:
        return 0
    dx = pts[:, 0] - float(exit_x_px)
    dy = pts[:, 1] - float(exit_y_px)
    in_zone = (dx * dx + dy * dy) <= float(exit_radius_px * exit_radius_px)
    return int(np.count_nonzero(in_zone))


def blob_exit_overlap_fraction(
    blob_mask: Optional[np.ndarray],
    blob_crop_rect: Optional[Tuple[int, int, int, int]],
    exit_x_px: float,
    exit_y_px: float,
    exit_radius_px: float,
) -> float:
    """Return overlap fraction: blob pixels inside exit circle / all blob pixels."""
    if blob_mask is None or blob_mask.ndim != 2 or exit_radius_px <= 0:
        return 0.0
    blob_n = int(np.count_nonzero(blob_mask))
    if blob_n <= 0:
        return 0.0
    h, w = blob_mask.shape
    if blob_crop_rect is not None:
        x0, y0, _, _ = blob_crop_rect
        cx = int(round(exit_x_px - x0))
        cy = int(round(exit_y_px - y0))
    else:
        cx = int(round(exit_x_px))
        cy = int(round(exit_y_px))
    yy, xx = np.ogrid[:h, :w]
    rr2 = float(exit_radius_px * exit_radius_px)
    exit_mask = ((xx - cx) ** 2 + (yy - cy) ** 2) <= rr2
    overlap = np.count_nonzero((blob_mask > 0) & exit_mask)
    return float(overlap) / float(blob_n)


def resolve_exit_success_override(
    *,
    pose_xy: Optional[np.ndarray],
    pose_node_valid: Optional[np.ndarray],
    pose_node_names: Optional[list],
    blob_mask: Optional[np.ndarray],
    blob_crop_rect: Optional[Tuple[int, int, int, int]],
    track_xy: Optional[Tuple[float, float]],
    track_source: str,
    exit_x_px: float,
    exit_y_px: float,
    exit_radius_px: float,
    required_keypoints: int,
    min_blob_overlap_fraction: float,
    allow_either_success: bool,
) -> Optional[bool]:
    """Resolve source-specific exit success for the run loop."""

    def sleap_exit_success() -> bool:
        if pose_xy is None or pose_xy.size == 0:
            return False
        n_in_exit = count_sleap_keypoints_in_exit(
            pose_xy=pose_xy,
            pose_node_valid=pose_node_valid,
            pose_node_names=pose_node_names,
            exit_x_px=exit_x_px,
            exit_y_px=exit_y_px,
            exit_radius_px=exit_radius_px,
        )
        return n_in_exit >= max(1, int(required_keypoints))

    def fallback_exit_success() -> bool:
        if blob_mask is not None:
            frac = blob_exit_overlap_fraction(
                blob_mask=blob_mask,
                blob_crop_rect=blob_crop_rect,
                exit_x_px=exit_x_px,
                exit_y_px=exit_y_px,
                exit_radius_px=exit_radius_px,
            )
            return frac >= float(min_blob_overlap_fraction)
        if track_xy is not None:
            dx = float(track_xy[0]) - float(exit_x_px)
            dy = float(track_xy[1]) - float(exit_y_px)
            return (dx * dx + dy * dy) <= float(exit_radius_px * exit_radius_px)
        return False

    if allow_either_success:
        return sleap_exit_success() or fallback_exit_success()
    if track_source == "sleap":
        return sleap_exit_success()
    if track_source == "fallback":
        return fallback_exit_success()
    return None


def blend_blob_mask_into_overlay(
    overlay: np.ndarray,
    blob_mask: Optional[np.ndarray],
    blob_crop_rect: Optional[Tuple[int, int, int, int]],
) -> None:
    """Semi-transparent green tint where ``blob_mask`` is nonzero."""
    if not HAS_CV2 or blob_mask is None or blob_mask.ndim != 2:
        return
    blob_alpha = 0.35
    green_bgr = (0, 255, 0)
    if blob_crop_rect is not None:
        x0, y0, x1, y1 = blob_crop_rect
        if x1 > x0 and y1 > y0 and blob_mask.shape == (y1 - y0, x1 - x0):
            overlay_slice = overlay[y0:y1, x0:x1]
            green_slice = np.empty_like(overlay_slice)
            green_slice[:] = green_bgr
            blended = cv2.addWeighted(green_slice, blob_alpha, overlay_slice, 1.0 - blob_alpha, 0)
            cv2.copyTo(blended, blob_mask, overlay_slice)
    elif blob_mask.shape[:2] == overlay.shape[:2]:
        green_layer = np.empty_like(overlay)
        green_layer[:] = green_bgr
        blended = cv2.addWeighted(green_layer, blob_alpha, overlay, 1.0 - blob_alpha, 0)
        cv2.copyTo(blended, blob_mask, overlay)


def draw_ram_template_polylines(
    overlay: np.ndarray,
    polys: dict[str, Any],
    exit_xyr: Optional[Tuple[float, float, float]],
    *,
    all_holes_xyr: Optional[list[Tuple[float, float, float]]] = None,
    escape_arm_index: int = 0,
) -> None:
    """Draw RAM projected regions on ``overlay`` (BGR) and optional hole circle(s)."""
    if not HAS_CV2:
        return
    center_color = (0, 220, 255)
    hole_color = (180, 180, 255)
    arm_color = (0, 200, 200)
    for name, poly in polys.items():
        arr = np.asarray(poly, dtype=np.float64)
        if arr.ndim != 2 or arr.shape[0] < 3 or arr.shape[1] < 2:
            continue
        pts = np.round(arr).astype(np.int32)
        if str(name) == "center":
            c = center_color
        elif str(name) == "hole":
            if all_holes_xyr:
                continue
            c = hole_color
        else:
            c = arm_color
        cv2.polylines(overlay, [pts], True, c, 1, cv2.LINE_AA)
    if all_holes_xyr is not None and len(all_holes_xyr) > 0:
        esc = int(max(0, min(7, escape_arm_index)))
        for i, t in enumerate(all_holes_xyr):
            ex, ey, er = t
            if er <= 0 or not np.isfinite(ex) or not np.isfinite(ey):
                continue
            col = (255, 0, 255) if i == esc else (200, 200, 255)
            th = 3 if i == esc else 1
            cv2.circle(
                overlay,
                (int(round(ex)), int(round(ey))),
                int(round(er)),
                col,
                th,
                cv2.LINE_AA,
            )
            # Show stable arm labels in preview using 1-based display numbering.
            label = f"arm{i + 1}"
            tx = int(round(ex + max(8.0, er + 4.0)))
            ty = int(round(ey - max(8.0, er + 4.0)))
            cv2.putText(
                overlay,
                label,
                (tx + 1, ty + 1),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 0, 0),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                overlay,
                label,
                (tx, ty),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                col,
                1,
                cv2.LINE_AA,
            )
    elif exit_xyr is not None:
        ex, ey, er = exit_xyr
        if er > 0 and np.isfinite(ex) and np.isfinite(ey):
            cv2.circle(
                overlay,
                (int(round(ex)), int(round(ey))),
                int(round(er)),
                (255, 0, 255),
                2,
                cv2.LINE_AA,
            )


def draw_roi_and_tracking_overlay(
    img: np.ndarray,
    roi_center_xy: Optional[Tuple[float, float]],
    roi_radius_px: float,
    track_xy: Optional[Tuple[float, float]],
    track_valid: bool,
    overlay_opacity: float,
    overlay_info: Optional[VastOverlayInfo] = None,
    track_source: str = "fallback",
    pose_xy: Optional[np.ndarray] = None,
    pose_scores: Optional[np.ndarray] = None,
    pose_edge_inds: Optional[list] = None,
    pose_node_names: Optional[list] = None,
    pose_node_valid: Optional[np.ndarray] = None,
    blob_mask: Optional[np.ndarray] = None,
    blob_crop_rect: Optional[Tuple[int, int, int, int]] = None,
    ram_polys: Optional[dict[str, Any]] = None,
    ram_exit_xyr: Optional[Tuple[float, float, float]] = None,
    ram_all_holes_xyr: Optional[list] = None,
    ram_escape_arm_index: int = 0,
) -> np.ndarray:
    """Draw ROI, state overlays, SLEAP skeleton, and fallback position marker."""
    if not HAS_CV2:
        return img
    out = np.asarray(img, dtype=np.uint8).copy()
    if out.ndim == 2:
        out = cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)
    elif out.ndim == 3 and out.shape[2] == 1:
        out = cv2.cvtColor(out.squeeze(axis=2), cv2.COLOR_GRAY2BGR)
    overlay = out.copy()
    cx_i = int(roi_center_xy[0]) if roi_center_xy else None
    cy_i = int(roi_center_xy[1]) if roi_center_xy else None
    if ram_polys is not None:
        draw_ram_template_polylines(
            overlay,
            ram_polys,
            ram_exit_xyr,
            all_holes_xyr=ram_all_holes_xyr,
            escape_arm_index=int(ram_escape_arm_index),
        )
    elif roi_center_xy is not None and roi_radius_px > 0:
        cv2.circle(overlay, (cx_i, cy_i), int(roi_radius_px), (0, 255, 255), 1)
    if overlay_info is not None and cx_i is not None and cy_i is not None:
        arena = overlay_info.arena
        state = overlay_info.state
        phase = overlay_info.phase
        show_center_edge = (
            state == VastTrialState.WAIT_NOT_CENTER
            or phase == VastPhase.HABITUATION
            or phase == VastPhase.HABITUATION_TRAINING
        )
        if show_center_edge and arena.center_radius_px > 0 and arena.radius_px > 0:
            cv2.circle(overlay, (cx_i, cy_i), int(arena.center_radius_px), (255, 255, 0), 1)
        if state == VastTrialState.TRIAL_RUNNING and arena.px_per_cm > 0:
            ex_i = int(overlay_info.exit_x_px)
            ey_i = int(overlay_info.exit_y_px)
            exit_r_px = int(arena.exit_radius_cm * arena.px_per_cm)
            if exit_r_px > 0:
                cv2.circle(overlay, (ex_i, ey_i), exit_r_px, (255, 0, 255), 2)
    blend_blob_mask_into_overlay(overlay, blob_mask, blob_crop_rect)
    node_marker_r = 2
    nose_color = (255, 0, 255)
    non_nose_color = (0, 255, 255)
    spot_color = (255, 255, 0)
    if track_source == "sleap" and pose_xy is not None and pose_edge_inds:
        n_nodes = pose_xy.shape[0]
        node_valid = (
            pose_node_valid
            if pose_node_valid is not None and pose_node_valid.shape == (n_nodes,)
            else np.ones(n_nodes, dtype=bool)
        )
        for a, b in pose_edge_inds:
            if a >= n_nodes or b >= n_nodes or not node_valid[a] or not node_valid[b]:
                continue
            xa, ya = float(pose_xy[a, 0]), float(pose_xy[a, 1])
            xb, yb = float(pose_xy[b, 0]), float(pose_xy[b, 1])
            if np.isfinite(xa) and np.isfinite(ya) and np.isfinite(xb) and np.isfinite(yb):
                cv2.line(
                    overlay,
                    (int(round(xa)), int(round(ya))),
                    (int(round(xb)), int(round(yb))),
                    non_nose_color,
                    1,
                    cv2.LINE_AA,
                )
        for i in range(n_nodes):
            if not node_valid[i]:
                continue
            x, y = float(pose_xy[i, 0]), float(pose_xy[i, 1])
            if np.isfinite(x) and np.isfinite(y):
                color = nose_color if i == 0 else non_nose_color
                cv2.circle(
                    overlay,
                    (int(round(x)), int(round(y))),
                    node_marker_r,
                    color,
                    1,
                    cv2.LINE_AA,
                )
        if pose_node_names is not None and len(pose_node_names) >= n_nodes:
            fore_inds = [
                i
                for i in range(n_nodes)
                if node_valid[i] and is_spot_node_name(pose_node_names[i])
            ]
            if fore_inds:
                pts = pose_xy[fore_inds]
                if np.all(np.isfinite(pts)):
                    sx = float(np.mean(pts[:, 0]))
                    sy = float(np.mean(pts[:, 1]))
                    cv2.circle(
                        overlay,
                        (int(round(sx)), int(round(sy))),
                        node_marker_r,
                        spot_color,
                        1,
                        cv2.LINE_AA,
                    )
    if track_xy is not None:
        tx, ty = int(track_xy[0]), int(track_xy[1])
        color = (0, 255, 0) if track_valid else (128, 128, 128)
        cv2.circle(overlay, (tx, ty), node_marker_r, color, 1, cv2.LINE_AA)
    alpha = max(0.0, min(1.0, overlay_opacity))
    cv2.addWeighted(overlay, alpha, out, 1.0 - alpha, 0, out)
    return out
