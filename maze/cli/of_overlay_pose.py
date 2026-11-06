"""Paint SuperAnimal pose from an HDF5 onto a background video.

The background can be the raw open-field mp4 or a wide mask. Pose coordinates
are camera pixels, so the frame size must match the video that was inferred.

Example::

    uv run maze-of-overlay-pose \\
      --h5 "Test 27_....h5" \\
      --video "Test 27.mp4" \\
      --out "Test 27_overlay.mp4"

Paths are arguments. Nothing in this module defaults to a lab drive.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from maze.pipeline.open_field.dlc_h5 import list_bodyparts, read_pose_table

DEFAULT_PCUTOFF = 0.6
DEFAULT_DOTSIZE = 4


def _bgr_colors(n: int) -> list[tuple[int, int, int]]:
    """Distinct BGR colors for bodyparts (OpenCV order)."""
    colors: list[tuple[int, int, int]] = []
    for i in range(n):
        hue = int(180 * i / max(n, 1)) % 180
        hsv = np.uint8([[[hue, 220, 255]]])
        bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)[0, 0]
        colors.append((int(bgr[0]), int(bgr[1]), int(bgr[2])))
    return colors


def write_pose_overlay(
    video_path: Path,
    h5_path: Path,
    out_path: Path,
    *,
    pcutoff: float = DEFAULT_PCUTOFF,
    individual: str = "animal0",
    max_frames: int | None = None,
) -> int:
    """Stream ``video_path`` with keypoints from ``h5_path`` drawn on each frame."""
    df = read_pose_table(h5_path)
    bodyparts = list_bodyparts(df)
    try:
        block = df.xs(individual, level="individuals", axis=1)
    except KeyError as exc:
        raise KeyError(f"individual {individual!r} not in {h5_path}") from exc

    xy = np.empty((len(df), len(bodyparts), 2), dtype=np.float64)
    lik = np.empty((len(df), len(bodyparts)), dtype=np.float64)
    for j, name in enumerate(bodyparts):
        part = block.xs(name, level="bodyparts", axis=1)
        xy[:, j, 0] = part.xs("x", level="coords", axis=1).to_numpy(dtype=np.float64).reshape(-1)
        xy[:, j, 1] = part.xs("y", level="coords", axis=1).to_numpy(dtype=np.float64).reshape(-1)
        lik[:, j] = part.xs("likelihood", level="coords", axis=1).to_numpy(dtype=np.float64).reshape(-1)

    colors = _bgr_colors(len(bodyparts))
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
            if max_frames is not None and written >= max_frames:
                break
            ok, frame = capture.read()
            if not ok:
                break
            if written < len(df):
                for j, name in enumerate(bodyparts):
                    if lik[written, j] < pcutoff:
                        continue
                    x, y = xy[written, j]
                    if not (np.isfinite(x) and np.isfinite(y)):
                        continue
                    cv2.circle(frame, (int(round(x)), int(round(y))), DEFAULT_DOTSIZE, colors[j], -1, lineType=cv2.LINE_AA)
            writer.write(frame)
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
    if written != len(df) and max_frames is None:
        print(
            f"warning: video frames={written} pose rows={len(df)}",
            file=sys.stderr,
            flush=True,
        )
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--h5", type=Path, required=True, help="SuperAnimal pose HDF5")
    parser.add_argument("--video", type=Path, required=True, help="Background mp4 (raw or wide mask)")
    parser.add_argument("--out", type=Path, required=True, help="Output labeled mp4")
    parser.add_argument("--pcutoff", type=float, default=DEFAULT_PCUTOFF)
    parser.add_argument("--individual", type=str, default="animal0")
    parser.add_argument("--max-frames", type=int, default=None, help="Optional cap for a short smoke")
    args = parser.parse_args()
    if not (args.pcutoff >= 0):
        parser.error("--pcutoff must be non-negative")
    written = write_pose_overlay(
        args.video,
        args.h5,
        args.out,
        pcutoff=args.pcutoff,
        individual=args.individual,
        max_frames=args.max_frames,
    )
    print(f"frames={written} out={args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
