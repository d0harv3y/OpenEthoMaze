"""
Materialize controller-style XY tables (spot / in-range / centroid) from decoded video.

Uses the same :class:`~maze.controller.acquisition.tracking.HybridTracker` stack as live
acquisition when SLEAP + backup are enabled in ``config``.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

from maze.controller.acquisition.h5_writer import write_feedback_table, write_xy_table
from maze.controller.acquisition.recording import XYRow
from maze.controller.acquisition.region_code import encode_region_code_bytes
from maze.controller.acquisition.shared_config import AcquisitionConfig
from maze.controller.acquisition.tracking import build_tracker_for_batch_encode
from maze.core.h5_layout import open_db
from maze.core.schema import FEEDBACK_ROW_DTYPE, XY_ROW_DTYPE

from .db import TrialKey

_FORE_NAMES = frozenset({"nose", "neck", "foreL", "foreR"})


def _spot_centroid_from_result(res) -> tuple[
    Optional[Tuple[float, float]],
    Optional[Tuple[float, float]],
]:
    """Mirror main-window recording: fore-node mean for spot, all valid nodes for centroid."""
    spot_xy: Optional[Tuple[float, float]] = None
    centroid_xy: Optional[Tuple[float, float]] = None
    pose_xy = getattr(res, "pose_xy", None)
    pose_node_names = getattr(res, "pose_node_names", None)
    pose_node_valid = getattr(res, "pose_node_valid", None)
    if pose_xy is not None and getattr(res, "source", "") == "sleap":
        if (
            pose_node_names is not None
            and pose_xy.ndim == 2
            and pose_xy.shape[1] == 2
            and len(pose_node_names) >= pose_xy.shape[0]
        ):
            fore_pts: list[tuple[float, float]] = []
            all_pts: list[tuple[float, float]] = []
            for j in range(pose_xy.shape[0]):
                name = str(pose_node_names[j])
                if (
                    pose_node_valid is not None
                    and j < pose_node_valid.shape[0]
                    and not bool(pose_node_valid[j])
                ):
                    continue
                xj = float(pose_xy[j, 0])
                yj = float(pose_xy[j, 1])
                if not (math.isfinite(xj) and math.isfinite(yj)):
                    continue
                if name in _FORE_NAMES:
                    fore_pts.append((xj, yj))
                all_pts.append((xj, yj))
            if fore_pts:
                xs, ys = zip(*fore_pts)
                spot_xy = (float(np.mean(xs)), float(np.mean(ys)))
            if all_pts:
                xs_a, ys_a = zip(*all_pts)
                centroid_xy = (float(np.mean(xs_a)), float(np.mean(ys_a)))
        if spot_xy is None and getattr(res, "valid", False):
            spot_xy = (float(res.x_px), float(res.y_px))
    elif getattr(res, "valid", False):
        spot_xy = (float(res.x_px), float(res.y_px))
    return spot_xy, centroid_xy


def materialize_xy_tables_from_video(
    *,
    db_path: Path,
    key: TrialKey,
    video_path: Path,
    config: AcquisitionConfig,
    model_dir: str,
    fps: Optional[float] = None,
) -> bool:
    """
    Decode ``video_path`` and write spot, in-range, centroid, and zero feedback tables.

    Trial geometry attrs must already exist on the trial group (from discovery or acquisition).
    """
    try:
        import cv2
    except ImportError:
        return False

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return False
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    v_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    use_fps = float(fps) if (fps is not None and fps > 0) else (v_fps if v_fps > 0 else 30.0)

    tracker = build_tracker_for_batch_encode(config, model_dir=model_dir)

    exit_x_px = exit_y_px = 0.0
    with open_db(db_path, "r") as h5:
        g = h5[key.path()]
        exit_x_px = float(g.attrs.get("exit_x", 0.0) or 0.0)
        exit_y_px = float(g.attrs.get("exit_y", 0.0) or 0.0)

    rows: list[XYRow] = []
    fi = 0
    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            break
        res = tracker.track(frame)
        in_range_xy = getattr(res, "in_range_xy", None)
        in_tuple: Optional[Tuple[float, float]] = None
        if (
            in_range_xy is not None
            and len(in_range_xy) == 2
            and math.isfinite(float(in_range_xy[0]))
            and math.isfinite(float(in_range_xy[1]))
        ):
            in_tuple = (float(in_range_xy[0]), float(in_range_xy[1]))
        spot_xy, centroid_xy = _spot_centroid_from_result(res)
        dist_exit = 0.0
        if spot_xy is not None:
            dist_exit = float(
                math.hypot(spot_xy[0] - exit_x_px, spot_xy[1] - exit_y_px)
            )
        valid = bool(getattr(res, "valid", False))
        rows.append(
            XYRow(
                frame_index=fi,
                t_s=float(fi) / use_fps if use_fps > 0 else 0.0,
                x=float(res.x_px),
                y=float(res.y_px),
                spot_x=float(spot_xy[0]) if spot_xy else float("nan"),
                spot_y=float(spot_xy[1]) if spot_xy else float("nan"),
                in_range_x=float(in_tuple[0]) if in_tuple else float("nan"),
                in_range_y=float(in_tuple[1]) if in_tuple else float("nan"),
                centroid_x=float(centroid_xy[0]) if centroid_xy else float("nan"),
                centroid_y=float(centroid_xy[1]) if centroid_xy else float("nan"),
                dist_to_exit_px=dist_exit,
                trial_state="run",
                region_code="",
                valid=valid,
                is_moving=False,
            )
        )
        fi += 1
    cap.release()

    if not rows:
        return False

    n = len(rows)
    arr_spot = np.zeros(n, dtype=XY_ROW_DTYPE)
    arr_in_range = np.zeros(n, dtype=XY_ROW_DTYPE)
    arr_centroid = np.zeros(n, dtype=XY_ROW_DTYPE)
    rc = encode_region_code_bytes("")
    for i, r in enumerate(rows):
        for arr in (arr_spot, arr_in_range, arr_centroid):
            arr[i]["frame_index"] = r.frame_index
            arr[i]["t_s"] = r.t_s
            arr[i]["dist_to_exit_px"] = r.dist_to_exit_px
            arr[i]["trial_state"] = r.trial_state.encode("utf-8")
            arr[i]["region_code"] = rc
            arr[i]["is_moving"] = 0
        arr_spot[i]["x"] = r.spot_x
        arr_spot[i]["y"] = r.spot_y
        arr_spot[i]["valid"] = 1 if (math.isfinite(r.spot_x) and math.isfinite(r.spot_y)) else 0
        arr_in_range[i]["x"] = r.in_range_x
        arr_in_range[i]["y"] = r.in_range_y
        arr_in_range[i]["valid"] = (
            1 if (math.isfinite(r.in_range_x) and math.isfinite(r.in_range_y)) else 0
        )
        arr_centroid[i]["x"] = r.centroid_x
        arr_centroid[i]["y"] = r.centroid_y
        arr_centroid[i]["valid"] = (
            1 if (math.isfinite(r.centroid_x) and math.isfinite(r.centroid_y)) else 0
        )

    fb = np.zeros(n, dtype=FEEDBACK_ROW_DTYPE)
    for i, r in enumerate(rows):
        fb[i]["frame_index"] = r.frame_index
        fb[i]["trial_state"] = r.trial_state.encode("utf-8")
        fb[i]["motor_fb"] = 0.0
        fb[i]["light_fb"] = 0.0
        fb[i]["sound_fb"] = 0.0

    with open_db(db_path, "a") as h5:
        g = h5[key.path()]
        write_xy_table(g, "spot", arr_spot, use_fps)
        write_xy_table(g, "in-range", arr_in_range, use_fps)
        write_xy_table(g, "centroid", arr_centroid, use_fps)
        write_feedback_table(g, fb)
        g.attrs["h5_fps"] = float(use_fps)
        if n_frames > 0:
            g.attrs["h5_n_frames"] = int(n_frames)

    return True
