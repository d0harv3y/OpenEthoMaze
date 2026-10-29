"""Fit a per-video open-field floor quadrilateral and write review images.

Example::

    uv run maze-of-floor-quad --video-dir "D:\\Open Field - mp4" --out-dir "D:\\DeepLabCut\\of_frailty\\floor_quads"

Paths are arguments. Nothing in this module defaults to a lab drive.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

import cv2
import numpy as np

from maze.pipeline.open_field.floor_quad import (
    FloorQuad,
    FloorQuadParams,
    cohort_qc_flags,
    fit_floor_quad,
    quad_review_flags,
    refit_side_outliers,
    render_quad_overlay,
)


def temporal_median_gray(video_path: Path, n_frames: int = 11) -> np.ndarray | None:
    """Median gray frame. The mouse drops out when it does not sit in one place."""
    if n_frames < 1:
        raise ValueError(f"n_frames must be positive, got {n_frames}")
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        return None
    total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if total < 1:
        capture.release()
        return None
    sample_n = min(n_frames, total)
    lo = max(0, int(total * 0.12))
    hi = max(lo + 1, int(total * 0.88))
    indices = np.linspace(lo, min(hi, total - 1), sample_n).astype(int)
    frames: list[np.ndarray] = []
    for index in indices:
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(index))
        ok, frame = capture.read()
        if ok:
            frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
    capture.release()
    if not frames:
        return None
    return np.median(np.stack(frames, axis=0), axis=0).astype(np.uint8)


def _video_sort_key(path: Path) -> tuple[int, str]:
    match = re.search(r"(\d+)", path.stem)
    number = int(match.group(1)) if match else 10**9
    return number, path.name


def iter_videos(video_dir: Path) -> list[Path]:
    return sorted(video_dir.glob("*.mp4"), key=_video_sort_key)


def _write_sheet(images: list[np.ndarray], path: Path, columns: int = 8) -> None:
    if not images:
        return
    thumb_w, thumb_h = 160, 120
    thumbs = [cv2.resize(image, (thumb_w, thumb_h), interpolation=cv2.INTER_AREA) for image in images]
    rows = int(np.ceil(len(thumbs) / columns))
    sheet = np.zeros((rows * thumb_h, columns * thumb_w, 3), dtype=np.uint8)
    for i, thumb in enumerate(thumbs):
        r, c = divmod(i, columns)
        sheet[r * thumb_h : (r + 1) * thumb_h, c * thumb_w : (c + 1) * thumb_w] = thumb
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), sheet)


def fit_directory(
    video_dir: Path,
    out_dir: Path,
    *,
    n_frames: int = 11,
    params: FloorQuadParams | None = None,
) -> Path:
    """Write ``floor_quads.csv``, one review PNG per video, and a sheet of flagged fits."""
    videos = iter_videos(video_dir)
    if not videos:
        raise FileNotFoundError(f"no mp4 files in {video_dir}")
    cfg = params or FloorQuadParams()
    review_dir = out_dir / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "floor_quads.csv"
    flagged_images: list[np.ndarray] = []
    sample_images: list[np.ndarray] = []
    fitted: list[tuple[Path, np.ndarray | None, FloorQuad | None]] = []
    for i, video in enumerate(videos, start=1):
        gray = temporal_median_gray(video, n_frames=n_frames)
        quad = None if gray is None else fit_floor_quad(gray, cfg)
        fitted.append((video, gray, quad))
        if i == 1 or i % 25 == 0 or i == len(videos):
            n_fit = sum(item[2] is not None for item in fitted)
            print(f"progress {i}/{len(videos)} fit={n_fit}", file=sys.stderr, flush=True)

    shape_source = np.full((len(fitted), 4, 2), np.nan, dtype=np.float64)
    for index, (_video, _gray, quad) in enumerate(fitted):
        if quad is not None:
            shape_source[index] = quad.vertices_xy
    quads = refit_side_outliers([gray for _video, gray, _quad in fitted], [quad for _video, _gray, quad in fitted], cfg)
    vertices = np.full((len(quads), 4, 2), np.nan, dtype=np.float64)
    diagonals = np.full(len(quads), np.nan, dtype=np.float64)
    for index, quad in enumerate(quads):
        if quad is None:
            continue
        vertices[index] = quad.vertices_xy
        diagonals[index] = quad.seed_diagonal_px
    extras = cohort_qc_flags(vertices, diagonals, shape_source=shape_source)

    n_pass = 0
    n_review = 0
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "video_id",
                "video_stem",
                "status",
                "flags",
                "area_px",
                "seed_diagonal_px",
                "outward_px",
                "x0",
                "y0",
                "x1",
                "y1",
                "x2",
                "y2",
                "x3",
                "y3",
            ],
        )
        writer.writeheader()
        for i, ((video, gray, _quad), quad, extra) in enumerate(zip(fitted, quads, extras, strict=True), start=1):
            if gray is None:
                flags = ("no_frame",)
            elif quad is None:
                flags = ("fit_failed",)
            else:
                flags = quad_review_flags(quad, gray.shape[:2]) + extra
            status = "pass" if quad is not None and not flags else "review"
            if status == "pass":
                n_pass += 1
            else:
                n_review += 1
            writer.writerow(_csv_row(video, status, flags, quad))
            if gray is None:
                continue
            overlay = render_quad_overlay(gray, quad, flags if status == "review" else ())
            cv2.putText(
                overlay,
                video.stem,
                (8, overlay.shape[0] - 12),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 255),
                1,
                cv2.LINE_AA,
            )
            cv2.imwrite(str(review_dir / f"{video.stem}.png"), overlay)
            if status == "review":
                flagged_images.append(overlay)
            elif len(sample_images) < 12 and (i == 1 or i % max(1, len(videos) // 12) == 0):
                sample_images.append(overlay)

    _write_sheet(flagged_images, out_dir / "flagged_sheet.png")
    _write_sheet(sample_images, out_dir / "sample_sheet.png")
    print(f"pass={n_pass} review={n_review} csv={csv_path}", file=sys.stderr)
    return csv_path


def _csv_row(video: Path, status: str, flags: tuple[str, ...], quad: FloorQuad | None) -> dict[str, str]:
    match = re.search(r"(\d+)", video.stem)
    video_id = match.group(1) if match else ""
    coords = [""] * 8
    area = ""
    seed_diagonal = ""
    outward = ""
    if quad is not None:
        flat = np.round(quad.vertices_xy, 1).reshape(-1)
        coords = [f"{value:.1f}" for value in flat]
        area = f"{quad.area_px:.1f}"
        seed_diagonal = f"{quad.seed_diagonal_px:.1f}"
        outward = f"{quad.outward_px:.1f}"
    return {
        "video_id": video_id,
        "video_stem": video.stem,
        "status": status,
        "flags": ";".join(flags),
        "area_px": area,
        "seed_diagonal_px": seed_diagonal,
        "outward_px": outward,
        "x0": coords[0],
        "y0": coords[1],
        "x1": coords[2],
        "y1": coords[3],
        "x2": coords[4],
        "y2": coords[5],
        "x3": coords[6],
        "y3": coords[7],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--n-frames", type=int, default=11, help="Frames in the temporal median")
    args = parser.parse_args()
    fit_directory(args.video_dir, args.out_dir, n_frames=args.n_frames)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
