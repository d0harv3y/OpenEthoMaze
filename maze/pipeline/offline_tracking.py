"""
Headless materialization of ``tracking/blob`` from stored video (offline re-track).

Mirrors live acquisition: :class:`~maze.controller.acquisition.tracking.AdaptiveThresholdTracker`
contour detection + :class:`~maze.pipeline.blob_orient.BlobOrientTracker` vertex ordering.
Optional anatomical pose rows supply heading hints when velocity is low.

See ``docs/h5_tracking_contract.md`` § ``tracking/blob`` write path 2 (offline).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from maze.core.anatomy import BLOB_VERTEX_COUNT
from maze.pipeline.blob_orient import BlobOrientTracker, DEFAULT_SPEED_EPSILON_PX
from maze.pipeline.defaults import DEFAULT_FPS
from maze.pipeline.tracking_io import AnatomicalTrackingData, BlobTrackingBuffer


@dataclass(frozen=True)
class OfflineBlobParams:
    """Backup-tracker settings for offline blob re-track (matches ``FallbackTrackingConfig``)."""

    range_low: int = 0
    range_high: int = 255
    min_area: int = 80
    max_area: int = 0
    morph_kernel_size: int = 5
    max_jump_px: float = 0.0
    selection_mode: str = "closest_else_largest"
    min_circularity: float = 0.0
    max_contours: int = 0
    speed_epsilon_px: float = DEFAULT_SPEED_EPSILON_PX


def offline_blob_params_to_backup_json(params: OfflineBlobParams) -> dict[str, object]:
    """JSON-serializable snapshot stored on ``tracking/blob`` attrs."""
    return {
        "range_low": int(params.range_low),
        "range_high": int(params.range_high),
        "min_area": int(params.min_area),
        "max_area": int(params.max_area),
        "morph_kernel_size": int(params.morph_kernel_size),
        "max_jump_px": float(params.max_jump_px),
        "selection_mode": str(params.selection_mode),
        "min_circularity": float(params.min_circularity),
        "max_contours": int(params.max_contours),
    }


def _build_adaptive_threshold_tracker(params: OfflineBlobParams):
    from maze.controller.acquisition.tracking import AdaptiveThresholdTracker

    return AdaptiveThresholdTracker(
        morph_kernel_size=params.morph_kernel_size,
        min_area=params.min_area,
        max_area=params.max_area,
        max_jump_px=params.max_jump_px,
        selection_mode=params.selection_mode,
        min_circularity=params.min_circularity,
        range_low=params.range_low,
        range_high=params.range_high,
        show_blob_overlay=False,
        max_contours=params.max_contours,
    )


def _video_fps(cap, fallback: float) -> float:
    import cv2

    fps = float(cap.get(cv2.CAP_PROP_FPS))
    if fps > 0:
        return fps
    return fallback if fallback > 0 else DEFAULT_FPS


def _frame_to_gray(frame: np.ndarray) -> np.ndarray:
    import cv2

    if frame.ndim == 2:
        return frame
    if frame.shape[2] == 1:
        return frame[:, :, 0]
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def _anatomical_xy_for_frame(
    anatomical: AnatomicalTrackingData | None,
    frame_index: int,
) -> tuple[np.ndarray | None, tuple[str, ...] | None]:
    if anatomical is None:
        return None, None
    idx_arr = np.asarray(anatomical.frame_index, dtype=np.int64)
    matches = np.nonzero(idx_arr == int(frame_index))[0]
    if matches.size == 0:
        return None, tuple(anatomical.node_names)
    row = int(matches[0])
    xy = np.stack(
        [anatomical.x[row], anatomical.y[row]],
        axis=-1,
    ).astype(np.float64, copy=False)
    return xy, tuple(anatomical.node_names)


def materialize_blob_buffer_from_video(
    video_path: Path,
    *,
    fps: float | None = None,
    anatomical: AnatomicalTrackingData | None = None,
    params: OfflineBlobParams | None = None,
) -> tuple[BlobTrackingBuffer, float]:
    """
    Run offline backup tracking on ``video_path`` and return a flush-ready buffer.

    Returns:
        ``(buffer, video_fps)``

    Raises:
        FileNotFoundError: Video missing.
        RuntimeError: OpenCV unavailable or video cannot be opened.
    """
    import cv2

    path = Path(video_path)
    if not path.is_file():
        raise FileNotFoundError(path)

    blob_params = params or OfflineBlobParams()
    tracker = _build_adaptive_threshold_tracker(blob_params)
    orient = BlobOrientTracker(
        min_area_px=float(max(blob_params.min_area, 1)),
        speed_epsilon_px=float(blob_params.speed_epsilon_px),
    )
    buffer = BlobTrackingBuffer(
        backup_params_json=offline_blob_params_to_backup_json(blob_params),
        blob_source="offline_retrack",
    )

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        cap.release()
        raise RuntimeError(f"Failed to open video: {path}")

    resolved_fps = _video_fps(cap, float(fps) if fps is not None else 0.0)
    frame_index = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            gray = _frame_to_gray(np.asarray(frame))
            res = tracker.track(gray)
            pose_xy, node_names = _anatomical_xy_for_frame(anatomical, frame_index)
            if res.blob_contour is None:
                buffer.append_frame(
                    frame_index,
                    np.full((BLOB_VERTEX_COUNT, 2), np.nan, dtype=np.float32),
                    valid=False,
                    heading_rad=float("nan"),
                    score=0.0,
                )
            else:
                oriented = orient.process_contour(
                    res.blob_contour,
                    anatomical_pose_xy=pose_xy,
                    anatomical_node_names=node_names,
                )
                buffer.append_frame(
                    frame_index,
                    np.asarray(oriented.xy, dtype=np.float32),
                    valid=bool(oriented.valid),
                    heading_rad=float(oriented.heading_rad),
                    score=float(oriented.score),
                )
            frame_index += 1
    finally:
        cap.release()

    if buffer.frame_count == 0:
        raise RuntimeError(f"No frames read from video: {path}")

    return buffer, resolved_fps
