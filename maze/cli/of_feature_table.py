"""Build the Parks/Whitehead open-field frailty feature table for one pose HDF5.

Rows are time bins inside the session. The seven video items are path length,
max move-bout distance, move duration, fraction moving, meander, mean speed,
and a top-view rear proxy. Body weight joins later from metadata. Pixel units
until a floor length in cm is declared.

Example::

    uv run maze-of-feature-table \\
      --h5 "Test 27_....h5" \\
      --video "Test 27.mp4" \\
      --quad-csv floor_quads.csv \\
      --out features.csv \\
      --bin-width-s 600

Paths are arguments. Nothing in this module defaults to a lab drive.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import cv2

from maze.cli.of_mask_video import vertices_for_video
from maze.pipeline.open_field.dlc_h5 import MOUSE_CENTER, bodypart_xy_likelihood, read_pose_table
from maze.pipeline.open_field.features import (
    DEFAULT_INTER_BOUT_GAP_FRAMES,
    DEFAULT_INTERPOLATE_GAPS,
    DEFAULT_LIKELIHOOD_MIN,
    DEFAULT_MAX_GAP_FRAMES,
    DEFAULT_MIN_BOUT_FRAMES,
    DEFAULT_MOVE_ENTRY_DEBOUNCE_FRAMES,
    DEFAULT_MOVE_EXIT_DEBOUNCE_FRAMES,
    DEFAULT_MOVE_SPEED_MEDIAN_WINDOW,
    DEFAULT_MOVE_START_SPEED_PX_S,
    DEFAULT_MOVE_STOP_SPEED_PX_S,
    DEFAULT_REAR_LENGTH_FRAC,
    DEFAULT_REAR_MAX_SPEED_PX_S,
    DEFAULT_REAR_MIN_ANGLE_DEG,
    DEFAULT_REAR_MIN_FRAMES,
    DEFAULT_THIGMOTAXIS_BAND_PX,
    DEFAULT_TRACE_SMOOTH,
    DEFAULT_TRACE_SMOOTH_WINDOW,
    feature_rows_for_video,
)
from maze.pipeline.open_field.time_bins import BIN_WIDTH_10MIN_S


def video_fps_and_duration(video_path: Path, n_pose_frames: int) -> tuple[float, float]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise FileNotFoundError(f"could not open {video_path}")
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        n_video = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:
        capture.release()
    if not (1.0 < fps < 240.0):
        raise ValueError(f"{video_path} reports fps={fps}")
    n = n_pose_frames if n_pose_frames > 0 else max(n_video, 1)
    return fps, n / fps


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--h5", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True, help="Used for fps / duration only")
    parser.add_argument("--out", type=Path, required=True, help="Output CSV")
    parser.add_argument("--quad-csv", type=Path, default=None, help="floor_quads.csv for thigmotaxis / rear wall gate")
    parser.add_argument("--bin-width-s", type=float, default=BIN_WIDTH_10MIN_S)
    parser.add_argument("--likelihood-min", type=float, default=DEFAULT_LIKELIHOOD_MIN)
    parser.add_argument(
        "--no-interpolate-gaps",
        action="store_true",
        help="Disable OEM short-gap linear interpolation on pose tracks",
    )
    parser.add_argument("--max-gap-frames", type=int, default=DEFAULT_MAX_GAP_FRAMES)
    parser.add_argument(
        "--no-trace-smooth",
        action="store_true",
        help="Disable OEM moving-average smoothing after gap fill",
    )
    parser.add_argument("--trace-smooth-window", type=int, default=DEFAULT_TRACE_SMOOTH_WINDOW)
    parser.add_argument("--move-start-speed-px-s", type=float, default=DEFAULT_MOVE_START_SPEED_PX_S)
    parser.add_argument("--move-stop-speed-px-s", type=float, default=DEFAULT_MOVE_STOP_SPEED_PX_S)
    parser.add_argument(
        "--immobile-speed-px-s",
        type=float,
        default=None,
        help="Legacy: sets stop speed and start=2×stop if start left at default",
    )
    parser.add_argument("--move-entry-debounce-frames", type=int, default=DEFAULT_MOVE_ENTRY_DEBOUNCE_FRAMES)
    parser.add_argument("--move-exit-debounce-frames", type=int, default=DEFAULT_MOVE_EXIT_DEBOUNCE_FRAMES)
    parser.add_argument("--move-speed-median-window", type=int, default=DEFAULT_MOVE_SPEED_MEDIAN_WINDOW)
    parser.add_argument("--min-bout-frames", type=int, default=DEFAULT_MIN_BOUT_FRAMES)
    parser.add_argument("--inter-bout-gap-frames", type=int, default=DEFAULT_INTER_BOUT_GAP_FRAMES)
    parser.add_argument("--rear-length-frac", type=float, default=DEFAULT_REAR_LENGTH_FRAC)
    parser.add_argument("--rear-max-speed-px-s", type=float, default=DEFAULT_REAR_MAX_SPEED_PX_S)
    parser.add_argument("--rear-min-angle-deg", type=float, default=DEFAULT_REAR_MIN_ANGLE_DEG)
    parser.add_argument("--rear-min-frames", type=int, default=DEFAULT_REAR_MIN_FRAMES)
    parser.add_argument(
        "--rear-allow-center",
        action="store_true",
        help="Count rear proxy away from walls (default requires near-wall / supported-rear prior)",
    )
    parser.add_argument("--thigmotaxis-band-px", type=float, default=DEFAULT_THIGMOTAXIS_BAND_PX)
    parser.add_argument("--allow-review", action="store_true")
    parser.add_argument("--video-id", type=str, default=None, help="Defaults to the video stem")
    args = parser.parse_args()
    if args.bin_width_s <= 0:
        parser.error("--bin-width-s must be positive")
    if args.min_bout_frames < 1 or args.rear_min_frames < 1:
        parser.error("bout / rear min frames must be >= 1")
    if args.move_start_speed_px_s < args.move_stop_speed_px_s and args.immobile_speed_px_s is None:
        parser.error("--move-start-speed-px-s must be >= --move-stop-speed-px-s")

    df = read_pose_table(args.h5)
    xy, lik = bodypart_xy_likelihood(df, MOUSE_CENTER)
    nose_xy, nose_lik = bodypart_xy_likelihood(df, "nose")
    tail_xy, tail_lik = bodypart_xy_likelihood(df, "tail_base")
    fps, duration_s = video_fps_and_duration(args.video, len(df))
    video_id = args.video_id or args.video.stem

    floor = None
    if args.quad_csv is not None:
        floor = vertices_for_video(args.quad_csv, args.video.stem, allow_review=args.allow_review)

    rows = feature_rows_for_video(
        video_id=video_id,
        xy=xy,
        likelihood=lik,
        fps=fps,
        duration_s=duration_s,
        bin_width_s=args.bin_width_s,
        nose_xy=nose_xy,
        tail_xy=tail_xy,
        nose_likelihood=nose_lik,
        tail_likelihood=tail_lik,
        floor_vertices_xy=floor,
        likelihood_min=args.likelihood_min,
        move_start_speed_px_s=args.move_start_speed_px_s,
        move_stop_speed_px_s=args.move_stop_speed_px_s,
        move_entry_debounce_frames=args.move_entry_debounce_frames,
        move_exit_debounce_frames=args.move_exit_debounce_frames,
        move_speed_median_window=args.move_speed_median_window,
        min_bout_frames=args.min_bout_frames,
        inter_bout_gap_frames=args.inter_bout_gap_frames,
        immobile_speed_px_s=args.immobile_speed_px_s,
        rear_length_frac=args.rear_length_frac,
        rear_max_speed_px_s=args.rear_max_speed_px_s,
        rear_min_angle_deg=args.rear_min_angle_deg,
        rear_require_near_wall=not args.rear_allow_center,
        rear_min_frames=args.rear_min_frames,
        thigmotaxis_band_px=args.thigmotaxis_band_px,
        interpolate_gaps=DEFAULT_INTERPOLATE_GAPS and not args.no_interpolate_gaps,
        max_gap_frames=args.max_gap_frames,
        trace_smooth=DEFAULT_TRACE_SMOOTH and not args.no_trace_smooth,
        trace_smooth_window=args.trace_smooth_window,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = (
        list(rows[0].as_dict().keys())
        if rows
        else [
            "video_id",
            "bin_index",
            "t0_s",
            "t1_s",
            "bin_width_s",
            "n_frames",
            "n_trusted",
            "path_length_px",
            "max_move_bout_distance_px",
            "move_duration_s",
            "frac_moving",
            "meander_deg_per_px",
            "mean_speed_px_s",
            "rear_proxy_count",
            "mean_active_speed_px_s",
            "immobility_frac",
            "thigmotaxis_frac",
            "frac_interpolated",
        ]
    )
    with args.out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.as_dict())
    print(f"rows={len(rows)} fps={fps:.3f} duration_s={duration_s:.1f} out={args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
