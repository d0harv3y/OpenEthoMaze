"""Compose multiple clip MP4s into one grid movie."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Sequence

import numpy as np

try:
    import cv2
except ImportError:  # pragma: no cover - guarded by CLI availability check
    cv2 = None  # type: ignore[assignment]


def grid_layout(n_cells: int, *, cols: int | None = None) -> tuple[int, int]:
    """Return ``(n_rows, n_cols)`` for ``n_cells`` tiles."""
    n = max(0, int(n_cells))
    if n == 0:
        return 0, 0
    n_cols = max(1, int(cols) if cols is not None else int(math.ceil(math.sqrt(n))))
    n_rows = int(math.ceil(n / n_cols))
    return n_rows, n_cols


def _read_clip_frames(path: Path) -> tuple[list[np.ndarray], float]:
    if cv2 is None:
        raise RuntimeError("OpenCV (cv2) is required for grid composition")
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open clip: {path}")
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    if not math.isfinite(fps) or fps <= 0:
        fps = 30.0
    frames: list[np.ndarray] = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(frame)
    cap.release()
    if not frames:
        raise RuntimeError(f"Clip has no frames: {path}")
    return frames, fps


def _resize_cell(frame: np.ndarray, cell_w: int, cell_h: int) -> np.ndarray:
    return cv2.resize(frame, (cell_w, cell_h), interpolation=cv2.INTER_AREA)


def _label_cell(frame: np.ndarray, label: str) -> np.ndarray:
    out = frame.copy()
    cv2.putText(
        out,
        label,
        (8, 22),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        out,
        label,
        (8, 22),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (20, 20, 20),
        1,
        cv2.LINE_AA,
    )
    return out


def compose_grid_video(
    clip_paths: Sequence[Path | str],
    output_path: Path | str,
    *,
    cell_labels: Sequence[str] | None = None,
    cols: int | None = None,
    fps: float | None = None,
) -> Path:
    """Write one MP4 tiling ``clip_paths`` in row-major order."""
    if cv2 is None:
        raise RuntimeError("OpenCV (cv2) is required for grid composition")
    paths = [Path(p) for p in clip_paths]
    if not paths:
        raise ValueError("compose_grid_video requires at least one clip")

    clip_frames: list[list[np.ndarray]] = []
    clip_fps: list[float] = []
    for path in paths:
        frames, clip_rate = _read_clip_frames(path)
        clip_frames.append(frames)
        clip_fps.append(clip_rate)

    out_fps = float(fps) if fps is not None and fps > 0 else max(clip_fps)
    n_frames = max(len(frames) for frames in clip_frames)
    cell_h = max(frames[0].shape[0] for frames in clip_frames)
    cell_w = max(frames[0].shape[1] for frames in clip_frames)

    n_rows, n_cols = grid_layout(len(paths), cols=cols)
    out_h = n_rows * cell_h
    out_w = n_cols * cell_w

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_path), fourcc, out_fps, (out_w, out_h))
    if not writer.isOpened():
        raise RuntimeError(f"Failed to open VideoWriter: {out_path}")

    labels = list(cell_labels) if cell_labels is not None else [""] * len(paths)
    if len(labels) < len(paths):
        labels.extend([""] * (len(paths) - len(labels)))

    for frame_idx in range(n_frames):
        canvas = np.zeros((out_h, out_w, 3), dtype=np.uint8)
        for tile_idx, frames in enumerate(clip_frames):
            frame = frames[min(frame_idx, len(frames) - 1)]
            cell = _resize_cell(frame, cell_w, cell_h)
            label = labels[tile_idx].strip()
            if label:
                cell = _label_cell(cell, label)
            row = tile_idx // n_cols
            col = tile_idx % n_cols
            y0 = row * cell_h
            x0 = col * cell_w
            canvas[y0 : y0 + cell_h, x0 : x0 + cell_w] = cell
        writer.write(canvas)
    writer.release()
    return out_path
