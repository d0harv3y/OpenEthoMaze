"""Write one open-field video with the four corner triangles zeroed.

The quadrilateral comes from ``floor_quads.csv`` (``maze-of-floor-quad``). Frame
size is unchanged, so pose stays in the original camera frame. Pixels outside
the floor polygon are 0.

Example::

    uv run maze-of-mask-video --quad-csv floor_quads.csv --video "Test 1.mp4" --out masked.mp4

Paths are arguments. Nothing in this module defaults to a lab drive.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from maze.pipeline.open_field.floor_quad import mask_outside_quad


def vertices_for_video(csv_path: Path, video_stem: str, *, allow_review: bool = False) -> np.ndarray:
    """Load the four floor vertices for ``video_stem`` from a quadrilateral table."""
    if not csv_path.is_file():
        raise FileNotFoundError(csv_path)
    with csv_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("video_stem") != video_stem:
                continue
            status = row.get("status") or ""
            if status != "pass" and not allow_review:
                flags = row.get("flags") or "review"
                raise ValueError(f"{video_stem} is {status} ({flags}); pass --allow-review to mask it anyway")
            coords = [row.get(key, "") for key in ("x0", "y0", "x1", "y1", "x2", "y2", "x3", "y3")]
            if any(value == "" for value in coords):
                raise ValueError(f"{video_stem} has no quadrilateral in {csv_path}")
            return np.array([float(value) for value in coords], dtype=np.float64).reshape(4, 2)
    raise KeyError(f"{video_stem} is not in {csv_path}")


def write_masked_video(video_path: Path, out_path: Path, vertices_xy: np.ndarray) -> int:
    """Stream ``video_path`` to ``out_path`` with pixels outside the quadrilateral set to 0."""
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise FileNotFoundError(f"could not open {video_path}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if width < 1 or height < 1:
        capture.release()
        raise ValueError(f"{video_path} has no frames")
    if not (1.0 < fps < 240.0):
        capture.release()
        raise ValueError(f"{video_path} reports fps={fps}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        capture.release()
        raise RuntimeError(f"could not open {out_path} for writing")
    written = 0
    started = time.monotonic()
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            writer.write(mask_outside_quad(frame, vertices_xy))
            written += 1
            if written == 1 or written % 1000 == 0 or (total > 0 and written == total):
                elapsed = time.monotonic() - started
                print(
                    f"progress {written}/{total or '?'} elapsed_s={elapsed:.0f}",
                    file=sys.stderr,
                    flush=True,
                )
    finally:
        capture.release()
        writer.release()
    if written < 1:
        raise RuntimeError(f"{video_path} produced no frames")
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quad-csv", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--allow-review", action="store_true", help="Mask a video whose quadrilateral was flagged")
    args = parser.parse_args()
    vertices = vertices_for_video(args.quad_csv, args.video.stem, allow_review=args.allow_review)
    written = write_masked_video(args.video, args.out, vertices)
    print(f"frames={written} out={args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
