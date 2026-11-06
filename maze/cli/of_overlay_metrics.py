"""Paint pose plus running Parks/Whitehead counters onto a background video.

Use this to eye-check the seven open-field frailty scalars. Counters are
cumulative from the start of the file (same definitions as ``maze-of-feature-table``).
Pass ``--quad-csv`` so the rear proxy uses the near-wall (supported-rear) gate.

Example::

    uv run maze-of-overlay-metrics \\
      --h5 "Test 27_....h5" \\
      --video "Test 27.mp4" \\
      --quad-csv floor_quads.csv \\
      --out "Test 27_metrics.mp4" \\
      --max-frames 3000

Paths are arguments. Nothing in this module defaults to a lab drive.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from maze.cli.of_mask_video import vertices_for_video
from maze.pipeline.open_field.dlc_h5 import MOUSE_CENTER, bodypart_xy_likelihood, list_bodyparts, read_pose_table
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
)
from maze.pipeline.open_field.running_metrics import compute_running_metrics

DEFAULT_PCUTOFF = 0.6
DEFAULT_DOTSIZE = 4
HUD_FONT = cv2.FONT_HERSHEY_SIMPLEX


def _bgr_colors(n: int) -> list[tuple[int, int, int]]:
    colors: list[tuple[int, int, int]] = []
    for i in range(n):
        hue = int(180 * i / max(n, 1)) % 180
        hsv = np.uint8([[[hue, 220, 255]]])
        bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)[0, 0]
        colors.append((int(bgr[0]), int(bgr[1]), int(bgr[2])))
    return colors


def _fmt(value: float, digits: int = 1) -> str:
    if not np.isfinite(value):
        return "nan"
    return f"{value:.{digits}f}"


def _draw_hud(
    frame: np.ndarray,
    lines: list[str],
    *,
    alert: bool = False,
    side: str = "left",
) -> None:
    """Semi-opaque metric panel on the left or right edge."""
    pad = 8
    line_h = 18
    width = 0
    for line in lines:
        (tw, th), _ = cv2.getTextSize(line, HUD_FONT, 0.45, 1)
        width = max(width, tw)
    box_w = width + 2 * pad
    box_h = pad + len(lines) * line_h + pad // 2
    x0 = 6 if side == "left" else max(6, frame.shape[1] - box_w - 6)
    overlay = frame.copy()
    bg = (40, 40, 180) if alert else (20, 20, 20)
    cv2.rectangle(overlay, (x0, 6), (x0 + box_w, 6 + box_h), bg, -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)
    y = 6 + pad + 12
    for line in lines:
        cv2.putText(frame, line, (x0 + pad, y), HUD_FONT, 0.45, (240, 240, 240), 1, cv2.LINE_AA)
        y += line_h


def _draw_floor_quad(frame: np.ndarray, vertices_xy: np.ndarray) -> None:
    """Outline the floor quadrilateral used for the supported-rear wall gate."""
    pts = np.asarray(vertices_xy, dtype=np.int32).reshape(-1, 1, 2)
    cv2.polylines(frame, [pts], isClosed=True, color=(80, 220, 220), thickness=2, lineType=cv2.LINE_AA)


def write_metrics_overlay(
    video_path: Path,
    h5_path: Path,
    out_path: Path,
    *,
    pcutoff: float = DEFAULT_PCUTOFF,
    individual: str = "animal0",
    max_frames: int | None = None,
    floor_vertices_xy: np.ndarray | None = None,
    likelihood_min: float = DEFAULT_LIKELIHOOD_MIN,
    move_start_speed_px_s: float = DEFAULT_MOVE_START_SPEED_PX_S,
    move_stop_speed_px_s: float = DEFAULT_MOVE_STOP_SPEED_PX_S,
    move_entry_debounce_frames: int = DEFAULT_MOVE_ENTRY_DEBOUNCE_FRAMES,
    move_exit_debounce_frames: int = DEFAULT_MOVE_EXIT_DEBOUNCE_FRAMES,
    move_speed_median_window: int = DEFAULT_MOVE_SPEED_MEDIAN_WINDOW,
    min_bout_frames: int = DEFAULT_MIN_BOUT_FRAMES,
    inter_bout_gap_frames: int = DEFAULT_INTER_BOUT_GAP_FRAMES,
    immobile_speed_px_s: float | None = None,
    rear_length_frac: float = DEFAULT_REAR_LENGTH_FRAC,
    rear_max_speed_px_s: float = DEFAULT_REAR_MAX_SPEED_PX_S,
    rear_min_angle_deg: float = DEFAULT_REAR_MIN_ANGLE_DEG,
    rear_min_frames: int = DEFAULT_REAR_MIN_FRAMES,
    rear_allow_center: bool = False,
    thigmotaxis_band_px: float = DEFAULT_THIGMOTAXIS_BAND_PX,
    interpolate_gaps: bool = DEFAULT_INTERPOLATE_GAPS,
    max_gap_frames: int = DEFAULT_MAX_GAP_FRAMES,
    trace_smooth: bool = DEFAULT_TRACE_SMOOTH,
    trace_smooth_window: int = DEFAULT_TRACE_SMOOTH_WINDOW,
) -> int:
    df = read_pose_table(h5_path)
    bodyparts = list_bodyparts(df)
    block = df.xs(individual, level="individuals", axis=1)
    xy = np.empty((len(df), len(bodyparts), 2), dtype=np.float64)
    lik = np.empty((len(df), len(bodyparts)), dtype=np.float64)
    for j, name in enumerate(bodyparts):
        part = block.xs(name, level="bodyparts", axis=1)
        xy[:, j, 0] = part.xs("x", level="coords", axis=1).to_numpy(dtype=np.float64).reshape(-1)
        xy[:, j, 1] = part.xs("y", level="coords", axis=1).to_numpy(dtype=np.float64).reshape(-1)
        lik[:, j] = part.xs("likelihood", level="coords", axis=1).to_numpy(dtype=np.float64).reshape(-1)
    colors = _bgr_colors(len(bodyparts))

    center_xy, center_lik = bodypart_xy_likelihood(df, MOUSE_CENTER, individual=individual)
    nose_xy, nose_lik = bodypart_xy_likelihood(df, "nose", individual=individual)
    tail_xy, tail_lik = bodypart_xy_likelihood(df, "tail_base", individual=individual)

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

    rear_require_near_wall = not rear_allow_center
    if rear_require_near_wall and floor_vertices_xy is None:
        print(
            "warning: rear wall gate on but no --quad-csv; near-wall prior inactive "
            "(angle / length / center-speed gates still apply)",
            file=sys.stderr,
        )

    metrics = compute_running_metrics(
        center_xy,
        center_lik,
        fps=fps,
        nose_xy=nose_xy,
        tail_xy=tail_xy,
        nose_likelihood=nose_lik,
        tail_likelihood=tail_lik,
        floor_vertices_xy=floor_vertices_xy,
        likelihood_min=likelihood_min,
        move_start_speed_px_s=move_start_speed_px_s,
        move_stop_speed_px_s=move_stop_speed_px_s,
        move_entry_debounce_frames=move_entry_debounce_frames,
        move_exit_debounce_frames=move_exit_debounce_frames,
        move_speed_median_window=move_speed_median_window,
        min_bout_frames=min_bout_frames,
        inter_bout_gap_frames=inter_bout_gap_frames,
        immobile_speed_px_s=immobile_speed_px_s,
        rear_length_frac=rear_length_frac,
        rear_max_speed_px_s=rear_max_speed_px_s,
        rear_min_angle_deg=rear_min_angle_deg,
        rear_require_near_wall=rear_require_near_wall,
        rear_min_frames=rear_min_frames,
        thigmotaxis_band_px=thigmotaxis_band_px,
        interpolate_gaps=interpolate_gaps,
        max_gap_frames=max_gap_frames,
        trace_smooth=trace_smooth,
        trace_smooth_window=trace_smooth_window,
    )
    wall_mode = (
        "off"
        if rear_allow_center
        else ("on" if floor_vertices_xy is not None else "no_quad")
    )

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
            if floor_vertices_xy is not None:
                _draw_floor_quad(frame, floor_vertices_xy)
            if written < len(df):
                for j in range(len(bodyparts)):
                    if lik[written, j] < pcutoff:
                        continue
                    x, y = xy[written, j]
                    if not (np.isfinite(x) and np.isfinite(y)):
                        continue
                    cv2.circle(
                        frame,
                        (int(round(x)), int(round(y))),
                        DEFAULT_DOTSIZE,
                        colors[j],
                        -1,
                        lineType=cv2.LINE_AA,
                    )
                if metrics.trusted[written] and np.isfinite(metrics.center_xy[written]).all():
                    cx, cy = metrics.center_xy[written]
                    ring = (0, 220, 0) if metrics.moving[written] else (0, 0, 220)
                    if metrics.rear_active[written]:
                        ring = (0, 200, 255)
                    cv2.circle(frame, (int(round(cx)), int(round(cy))), 10, ring, 2, lineType=cv2.LINE_AA)

                t_s = written / fps
                state = "REAR" if metrics.rear_active[written] else ("MOVE" if metrics.moving[written] else "STILL")
                if not metrics.trusted[written]:
                    state = "GAP"
                elif metrics.interpolated[written] and state == "STILL":
                    state = "INTERP"
                left_lines = [
                    f"t={t_s:7.1f}s  [{state}]  rear_wall={wall_mode}",
                    f"1 path_px     {_fmt(metrics.path_length_px[written], 0)}",
                    f"2 max_bout_px {_fmt(metrics.max_move_bout_distance_px[written], 0)}",
                    f"3 move_s      {_fmt(metrics.move_duration_s[written], 1)}",
                    f"4 frac_move   {_fmt(metrics.frac_moving[written], 3)}",
                    f"5 meander/px  {_fmt(metrics.meander_deg_per_px[written], 2)}",
                    f"6 mean_v_px/s {_fmt(metrics.mean_speed_px_s[written], 1)}",
                    f"7 rear_proxy  {_fmt(metrics.rear_proxy_count[written], 0)}",
                ]
                # Live signals vs thresholds (right panel) for dial-in.
                len_now = metrics.body_length_frac[written]
                len_hit = np.isfinite(len_now) and len_now <= rear_length_frac
                ctr_now = metrics.center_speed_px_s[written]
                ang_now = metrics.nose_center_tail_angle_deg[written]
                ang_hit = np.isfinite(ang_now) and ang_now >= rear_min_angle_deg
                right_lines = [
                    "live vs gates",
                    f"center_v  {_fmt(ctr_now, 1)} px/s",
                    f"  move_on>={_fmt(move_start_speed_px_s, 1)}  off<={_fmt(move_stop_speed_px_s, 1)}",
                    f"  rear_ctr<={_fmt(rear_max_speed_px_s, 1)}",
                    f"body_L/med {_fmt(len_now, 2)}{' *' if len_hit else ''}",
                    f"  rear_L  <={_fmt(rear_length_frac, 2)}",
                    f"n-c-t ang {_fmt(ang_now, 0)} deg{' *' if ang_hit else ''}",
                    f"  rear_ang>={_fmt(rear_min_angle_deg, 0)}",
                ]
                _draw_hud(frame, left_lines, alert=metrics.rear_active[written], side="left")
                _draw_hud(frame, right_lines, alert=metrics.rear_active[written], side="right")

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
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--h5", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--quad-csv",
        type=Path,
        default=None,
        help="floor_quads.csv for supported-rear wall gate (drawn on frames)",
    )
    parser.add_argument("--allow-review", action="store_true", help="Accept non-pass floor quads")
    parser.add_argument("--pcutoff", type=float, default=DEFAULT_PCUTOFF)
    parser.add_argument("--individual", type=str, default="animal0")
    parser.add_argument("--max-frames", type=int, default=None, help="Optional short smoke")
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
    parser.add_argument("--immobile-speed-px-s", type=float, default=None)
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
        help="Disable near-wall prior (count rear proxy in arena center too)",
    )
    parser.add_argument(
        "--thigmotaxis-band-px",
        type=float,
        default=DEFAULT_THIGMOTAXIS_BAND_PX,
        help="Near-wall band (px) for supported-rear gate",
    )
    args = parser.parse_args()

    floor = None
    if args.quad_csv is not None:
        floor = vertices_for_video(args.quad_csv, args.video.stem, allow_review=args.allow_review)

    written = write_metrics_overlay(
        args.video,
        args.h5,
        args.out,
        pcutoff=args.pcutoff,
        individual=args.individual,
        max_frames=args.max_frames,
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
        rear_min_frames=args.rear_min_frames,
        rear_allow_center=args.rear_allow_center,
        thigmotaxis_band_px=args.thigmotaxis_band_px,
        interpolate_gaps=DEFAULT_INTERPOLATE_GAPS and not args.no_interpolate_gaps,
        max_gap_frames=args.max_gap_frames,
        trace_smooth=DEFAULT_TRACE_SMOOTH and not args.no_trace_smooth,
        trace_smooth_window=args.trace_smooth_window,
    )
    print(f"frames={written} out={args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
