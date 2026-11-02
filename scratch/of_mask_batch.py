"""Mask every open-field mp4 in one folder, one process per video.

Run from the OpenEthoMaze repo with the uv environment::

    uv run python scratch/of_mask_batch.py ^
      --quad-csv "H:\\Open Field - masked\\floor_quads\\floor_quads.csv" ^
      --videos-dir "H:\\Open Field - mp4" ^
      --out-dir "H:\\Open Field - masked-tight" ^
      --scale 1.2 ^
      --workers 6

Paths are arguments. Nothing in this file defaults to a lab drive.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from maze.cli.of_mask_video import vertices_for_video, write_masked_video
from maze.pipeline.open_field.floor_quad import POSE_MASK_SCALE


def test_sort_key(path: Path) -> tuple:
    match = re.search(r"(\d+)", path.stem)
    if match:
        return (0, int(match.group(1)), path.name.lower())
    return (1, path.name.lower())


def mask_one(job: tuple[str, str, str, float, bool]) -> tuple[str, str, int | None, str]:
    """Worker entry. Returns (stem, status, frames_or_none, detail)."""
    video_s, out_s, csv_s, scale, allow_review = job
    video = Path(video_s)
    out = Path(out_s)
    try:
        vertices = vertices_for_video(Path(csv_s), video.stem, allow_review=allow_review)
    except (ValueError, KeyError, FileNotFoundError) as exc:
        return (video.stem, "skip", None, str(exc))
    try:
        frames = write_masked_video(video, out, vertices, scale=scale)
    except Exception as exc:  # noqa: BLE001 — report and continue the batch
        return (video.stem, "fail", None, str(exc))
    return (video.stem, "ok", frames, str(out))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quad-csv", type=Path, required=True)
    parser.add_argument("--videos-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--scale", type=float, default=POSE_MASK_SCALE)
    parser.add_argument("--workers", type=int, default=4, help="Concurrent mask processes. Default 4.")
    parser.add_argument("--allow-review", action="store_true")
    parser.add_argument("--overwrite", action="store_true", help="Rewrite existing outputs. Default skips them.")
    args = parser.parse_args(argv)
    if not (args.scale > 0):
        parser.error("--scale must be positive")
    if args.workers < 1:
        parser.error("--workers must be >= 1")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.videos_dir.is_dir():
        print(f"videos folder missing: {args.videos_dir}", file=sys.stderr)
        return 2
    if not args.quad_csv.is_file():
        print(f"quad csv missing: {args.quad_csv}", file=sys.stderr)
        return 2

    videos = sorted(
        (path for path in args.videos_dir.iterdir() if path.is_file() and path.suffix.lower() == ".mp4"),
        key=test_sort_key,
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)

    jobs: list[tuple[str, str, str, float, bool]] = []
    skipped_existing = 0
    for video in videos:
        out = args.out_dir / video.name
        if out.is_file() and not args.overwrite:
            skipped_existing += 1
            print(f"skip existing {video.name}", flush=True)
            continue
        jobs.append((str(video), str(out), str(args.quad_csv), args.scale, args.allow_review))

    print(
        f"videos={len(videos)} jobs={len(jobs)} already={skipped_existing} "
        f"workers={args.workers} scale={args.scale}",
        flush=True,
    )
    if not jobs:
        return 0

    ok = fail = skip = 0
    started = time.monotonic()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(mask_one, job): job[0] for job in jobs}
        for index, future in enumerate(as_completed(futures), start=1):
            stem, status, frames, detail = future.result()
            if status == "ok":
                ok += 1
            elif status == "skip":
                skip += 1
            else:
                fail += 1
            elapsed = time.monotonic() - started
            print(
                f"[{index}/{len(jobs)}] {status} {stem}"
                + (f" frames={frames}" if frames is not None else f" {detail}")
                + f" elapsed_s={elapsed:.0f}",
                flush=True,
            )

    print(f"done ok={ok} skip={skip} fail={fail}", flush=True)
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
