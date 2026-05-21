from __future__ import annotations

import argparse
import csv
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import h5py
import numpy as np

try:
    import cv2
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("OpenCV (cv2) is required for rendering overlays.") from exc

from maze.core.anatomy import STANDARD_NODE_NAMES
from maze.pipeline.defaults import (
    DEFAULT_PX_PER_CM,
    MIN_MOVEMENT_BOUT_DURATION_S,
    MOVEMENT_ENTRY_DEBOUNCE_FRAMES,
    MOVEMENT_EXIT_DEBOUNCE_FRAMES,
    MOVEMENT_INTER_BOUT_INTERVAL_S,
    MOVEMENT_SPEED_MEDIAN_WINDOW_FRAMES,
    MOVEMENT_START_THRESHOLD_M_PER_FRAME,
    MOVEMENT_STOP_THRESHOLD_M_PER_FRAME,
)
from maze.pipeline.io.sleap_loader import (
    apply_jump_filter,
    get_skeleton_edges,
    load_sleap_file,
)
from maze.pipeline.metrics.ambulation import _detect_movement_bouts
from maze.pipeline.tracking.trace_processing import (
    TraceProcessingParams,
    process_trace_data,
)


VIDEO_EXTS = (".mp4", ".avi", ".mov", ".mkv")


@dataclass
class Pair:
    video_path: Path
    slp_path: Path


@dataclass
class PairSummary:
    video_path: str
    slp_path: str
    overlay_path: str
    fps: float
    n_frames: int
    n_bouts: int
    total_distance_px: float
    time_still_s: float
    time_moving_s: float


def _discover_pairs(root: Path) -> list[Pair]:
    pairs: list[Pair] = []
    for video_path in sorted(
        (p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTS),
        key=lambda p: str(p).lower(),
    ):
        stem = video_path.stem
        candidates = [
            video_path.with_suffix(".predictions.slp"),
            video_path.with_suffix(".slp"),
            video_path.with_suffix(".h5.slp"),
            video_path.parent / f"{stem}.predictions.slp",
            video_path.parent / f"{stem}.slp",
            video_path.parent / f"{stem}.h5.slp",
        ]
        slp_path = next((c for c in candidates if c.exists()), None)
        if slp_path is None:
            continue
        pairs.append(Pair(video_path=video_path, slp_path=slp_path))
    return pairs


def _video_fps(video_path: Path) -> float:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    finally:
        cap.release()
    if fps <= 0:
        fps = 30.0
    return fps


def _load_slp_frame_indices(slp_path: Path, n_frames_fallback: int) -> np.ndarray:
    """Return video-frame indices for each SLP frame row."""
    try:
        with h5py.File(slp_path, "r") as f:
            if "frames" not in f:
                return np.arange(n_frames_fallback, dtype=np.int32)
            frames = f["frames"][:]
            if getattr(frames.dtype, "names", None) and "frame_idx" in frames.dtype.names:
                idx = np.asarray(frames["frame_idx"], dtype=np.int32)
                if len(idx):
                    return idx
    except Exception:
        pass
    return np.arange(n_frames_fallback, dtype=np.int32)


def _align_series_to_video(
    values: np.ndarray,
    frame_indices: np.ndarray,
    n_video_frames: int,
) -> np.ndarray:
    out = np.full(n_video_frames, np.nan, dtype=np.float64)
    n = min(len(values), len(frame_indices))
    if n <= 0 or n_video_frames <= 0:
        return out
    values = np.asarray(values[:n], dtype=np.float64)
    idx = np.asarray(frame_indices[:n], dtype=np.int64)
    valid = (
        np.isfinite(values)
        & (idx >= 0)
        & (idx < n_video_frames)
    )
    out[idx[valid]] = values[valid]
    return out


def _build_centroid(processed: dict[str, dict[str, np.ndarray]]) -> np.ndarray:
    x_list: list[np.ndarray] = []
    y_list: list[np.ndarray] = []
    for node_name in STANDARD_NODE_NAMES:
        if node_name not in processed:
            continue
        x_list.append(np.asarray(processed[node_name]["x"], dtype=np.float64))
        y_list.append(np.asarray(processed[node_name]["y"], dtype=np.float64))
    if not x_list:
        return np.empty((0, 2), dtype=np.float64)
    x_stack = np.column_stack(x_list)
    y_stack = np.column_stack(y_list)
    x_counts = np.sum(np.isfinite(x_stack), axis=1)
    y_counts = np.sum(np.isfinite(y_stack), axis=1)
    x_sum = np.nansum(x_stack, axis=1)
    y_sum = np.nansum(y_stack, axis=1)
    x_centroid = np.divide(
        x_sum,
        x_counts,
        out=np.full(len(x_sum), np.nan, dtype=np.float64),
        where=(x_counts > 0),
    )
    y_centroid = np.divide(
        y_sum,
        y_counts,
        out=np.full(len(y_sum), np.nan, dtype=np.float64),
        where=(y_counts > 0),
    )
    return np.column_stack([x_centroid, y_centroid])


def _movement_arrays(
    centroid_xy: np.ndarray,
    fps: float,
    px_per_cm_for_bouts: float,
) -> tuple[np.ndarray, np.ndarray, list[dict[str, float]], float, float]:
    if len(centroid_xy) == 0:
        return (
            np.zeros(0, dtype=bool),
            np.zeros(0, dtype=np.float64),
            [],
            0.0,
            0.0,
        )

    valid = np.isfinite(centroid_xy[:, 0]) & np.isfinite(centroid_xy[:, 1])
    dx = np.diff(centroid_xy[:, 0])
    dy = np.diff(centroid_xy[:, 1])
    step_px = np.sqrt(dx**2 + dy**2)
    step_px = np.nan_to_num(step_px, nan=0.0)

    px_per_m = max(px_per_cm_for_bouts, 1e-6) * 100.0
    distances_m = step_px / px_per_m
    bouts, is_moving = _detect_movement_bouts(
        distances_m=distances_m,
        valid=valid,
        fps=fps,
        start_threshold_m=MOVEMENT_START_THRESHOLD_M_PER_FRAME,
        stop_threshold_m=MOVEMENT_STOP_THRESHOLD_M_PER_FRAME,
        speed_median_window_frames=MOVEMENT_SPEED_MEDIAN_WINDOW_FRAMES,
        entry_debounce_frames=MOVEMENT_ENTRY_DEBOUNCE_FRAMES,
        exit_debounce_frames=MOVEMENT_EXIT_DEBOUNCE_FRAMES,
        min_bout_duration_s=MIN_MOVEMENT_BOUT_DURATION_S,
        inter_bout_interval_s=MOVEMENT_INTER_BOUT_INTERVAL_S,
    )

    valid_steps = valid[:-1] & valid[1:]
    moving_steps = is_moving[:-1] if len(is_moving) > 1 else np.zeros(0, dtype=bool)
    step_px_for_distance = np.where(valid_steps & moving_steps, step_px, 0.0)

    cum_distance_px = np.zeros(len(centroid_xy), dtype=np.float64)
    if len(cum_distance_px) > 1:
        cum_distance_px[1:] = np.cumsum(step_px_for_distance)

    frame_dt = 1.0 / fps if fps > 0 else 0.0
    still_time_s = np.cumsum(np.where(~is_moving, frame_dt, 0.0))
    total_distance_px = float(cum_distance_px[-1]) if len(cum_distance_px) else 0.0
    total_still_s = float(still_time_s[-1]) if len(still_time_s) else 0.0
    return is_moving, cum_distance_px, bouts, total_distance_px, total_still_s


def _bouts_seen_by_frame(n_frames: int, bouts: list[dict[str, float]]) -> np.ndarray:
    seen = np.zeros(n_frames, dtype=np.int32)
    if n_frames == 0:
        return seen
    for bout_idx, bout in enumerate(bouts, start=1):
        start = int(bout["start_frame"])
        if 0 <= start < n_frames:
            seen[start:] += 1
        elif start <= 0:
            seen[:] += 1
    return seen


def _iter_recent_points(xy: np.ndarray, frame_idx: int, trail_len: int) -> Iterable[tuple[int, int]]:
    start = max(0, frame_idx - trail_len + 1)
    for i in range(start, frame_idx + 1):
        x, y = xy[i]
        if np.isfinite(x) and np.isfinite(y):
            yield (int(round(x)), int(round(y)))


def _render_pair(
    pair: Pair,
    out_dir: Path,
    max_seconds: float | None,
    trail_len: int,
    contrast: float,
    brightness: float,
    px_per_cm_for_bouts: float,
) -> PairSummary:
    trace_data = load_sleap_file(pair.slp_path)
    if trace_data is None:
        raise RuntimeError(f"Failed to load SLP: {pair.slp_path}")

    trace_data = apply_jump_filter(trace_data, px_per_cm=px_per_cm_for_bouts)
    processed_raw = process_trace_data(
        trace_data.traces,
        trace_data.node_names,
        TraceProcessingParams(),
    )

    cap = cv2.VideoCapture(str(pair.video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video for rendering: {pair.video_path}")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    if fps <= 0:
        fps = 30.0
    video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if video_frames <= 0:
        video_frames = trace_data.n_frames

    slp_frame_idx = _load_slp_frame_indices(pair.slp_path, trace_data.n_frames)
    aligned_processed: dict[str, dict[str, np.ndarray]] = {}
    for node_name in STANDARD_NODE_NAMES:
        if node_name not in processed_raw:
            continue
        aligned_processed[node_name] = {
            "x": _align_series_to_video(
                processed_raw[node_name]["x"],
                slp_frame_idx,
                video_frames,
            ),
            "y": _align_series_to_video(
                processed_raw[node_name]["y"],
                slp_frame_idx,
                video_frames,
            ),
        }

    centroid_xy = _build_centroid(aligned_processed)
    if len(centroid_xy) == 0:
        cap.release()
        raise RuntimeError(f"No usable keypoints found in {pair.slp_path}")

    max_frames = min(len(centroid_xy), video_frames)
    if max_seconds is not None and max_seconds > 0:
        max_frames = min(max_frames, int(max_seconds * fps))
    centroid_xy = centroid_xy[:max_frames]

    is_moving, cum_distance_px, bouts, total_distance_px, total_still_s = _movement_arrays(
        centroid_xy=centroid_xy,
        fps=fps,
        px_per_cm_for_bouts=px_per_cm_for_bouts,
    )
    bouts_seen = _bouts_seen_by_frame(len(centroid_xy), bouts)
    frame_dt = 1.0 / fps if fps > 0 else 0.0
    time_still_s = np.cumsum(np.where(~is_moving, frame_dt, 0.0))
    time_moving_s = np.cumsum(np.where(is_moving, frame_dt, 0.0))

    skeleton_edges = get_skeleton_edges()
    node_xy = {}
    for node_name in STANDARD_NODE_NAMES:
        if node_name not in aligned_processed:
            continue
        node_xy[node_name] = {
            "x": np.asarray(aligned_processed[node_name]["x"][:max_frames], dtype=np.float64),
            "y": np.asarray(aligned_processed[node_name]["y"][:max_frames], dtype=np.float64),
        }

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    if width <= 0 or height <= 0:
        cap.release()
        raise RuntimeError(f"Invalid video dimensions: {pair.video_path}")

    out_dir.mkdir(parents=True, exist_ok=True)
    output_file = out_dir / f"{pair.video_path.stem}_overlay.mp4"
    tmp_file = out_dir / f"{pair.video_path.stem}_overlay.tmp.mp4"

    writer = cv2.VideoWriter(
        str(tmp_file),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        cap.release()
        raise RuntimeError(f"Could not open output writer: {tmp_file}")

    font = cv2.FONT_HERSHEY_SIMPLEX
    line_type = cv2.LINE_AA
    text_color = (255, 255, 255)

    try:
        for i in range(max_frames):
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            frame = cv2.convertScaleAbs(frame, alpha=contrast, beta=brightness)

            if skeleton_edges:
                for a, b in skeleton_edges:
                    if a >= len(STANDARD_NODE_NAMES) or b >= len(STANDARD_NODE_NAMES):
                        continue
                    na = STANDARD_NODE_NAMES[a]
                    nb = STANDARD_NODE_NAMES[b]
                    if na not in node_xy or nb not in node_xy:
                        continue
                    xa = node_xy[na]["x"][i]
                    ya = node_xy[na]["y"][i]
                    xb = node_xy[nb]["x"][i]
                    yb = node_xy[nb]["y"][i]
                    if np.isfinite(xa) and np.isfinite(ya) and np.isfinite(xb) and np.isfinite(yb):
                        cv2.line(
                            frame,
                            (int(round(xa)), int(round(ya))),
                            (int(round(xb)), int(round(yb))),
                            (0, 200, 255),
                            1,
                            line_type,
                        )

            for node_name in STANDARD_NODE_NAMES:
                if node_name not in node_xy:
                    continue
                x = node_xy[node_name]["x"][i]
                y = node_xy[node_name]["y"][i]
                if np.isfinite(x) and np.isfinite(y):
                    cv2.circle(
                        frame,
                        (int(round(x)), int(round(y))),
                        2,
                        (255, 60, 60),
                        -1,
                        line_type,
                    )

            pts = list(_iter_recent_points(centroid_xy, i, trail_len=trail_len))
            for j in range(1, len(pts)):
                cv2.line(frame, pts[j - 1], pts[j], (0, 255, 0), 2, line_type)

            if np.isfinite(centroid_xy[i, 0]) and np.isfinite(centroid_xy[i, 1]):
                cv2.circle(
                    frame,
                    (int(round(centroid_xy[i, 0])), int(round(centroid_xy[i, 1]))),
                    4,
                    (0, 255, 0),
                    -1,
                    line_type,
                )

            y_line = 26

            def put(line: str) -> None:
                nonlocal y_line
                cv2.putText(frame, line, (12, y_line), font, 0.55, text_color, 2, line_type)
                y_line += 18

            put(f"t: {i / fps:.1f}s")
            put(f"distance(px): {cum_distance_px[i]:.1f}")
            put(f"time_still(s): {time_still_s[i]:.1f}")
            put("state: MOVING" if bool(is_moving[i]) else "state: STILL")
            put(f"bouts: {int(bouts_seen[i])}")

            writer.write(frame)
    finally:
        cap.release()
        writer.release()

    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(tmp_file),
            "-an",
            "-vf",
            "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-c:v",
            "libx264",
            "-profile:v",
            "baseline",
            "-level",
            "3.0",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output_file),
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        tmp_file.unlink(missing_ok=True)
    except FileNotFoundError:
        tmp_file.replace(output_file)
    except subprocess.CalledProcessError:
        tmp_file.replace(output_file)

    return PairSummary(
        video_path=str(pair.video_path),
        slp_path=str(pair.slp_path),
        overlay_path=str(output_file),
        fps=fps,
        n_frames=int(max_frames),
        n_bouts=len(bouts),
        total_distance_px=total_distance_px,
        time_still_s=total_still_s,
        time_moving_s=float(time_moving_s[-1]) if len(time_moving_s) else 0.0,
    )


def _write_summary_csv(rows: list[PairSummary], csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "video_path",
                "slp_path",
                "overlay_path",
                "fps",
                "n_frames",
                "n_bouts",
                "total_distance_px",
                "time_still_s",
                "time_moving_s",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "video_path": row.video_path,
                    "slp_path": row.slp_path,
                    "overlay_path": row.overlay_path,
                    "fps": f"{row.fps:.4f}",
                    "n_frames": row.n_frames,
                    "n_bouts": row.n_bouts,
                    "total_distance_px": f"{row.total_distance_px:.3f}",
                    "time_still_s": f"{row.time_still_s:.3f}",
                    "time_moving_s": f"{row.time_moving_s:.3f}",
                }
            )


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Render one-shot overlays from video/.slp pairs and export one combined "
            "bout summary CSV (pixel-space metrics)."
        )
    )
    ap.add_argument(
        "--root",
        required=True,
        help="Root directory containing videos and basename-matched .slp files.",
    )
    ap.add_argument(
        "--out-dir",
        default=None,
        help="Overlay output directory (default: <root>\\overlay_outputs).",
    )
    ap.add_argument(
        "--summary-csv",
        default=None,
        help="Summary CSV path (default: <out-dir>\\bout_summary_all_videos.csv).",
    )
    ap.add_argument("--max-seconds", type=float, default=None, help="Optional cap on rendered seconds per video.")
    ap.add_argument("--trail-len", type=int, default=45, help="Centroid trail length in frames.")
    ap.add_argument("--contrast", type=float, default=2.0, help="Overlay contrast multiplier.")
    ap.add_argument("--brightness", type=float, default=5.0, help="Overlay brightness offset.")
    ap.add_argument(
        "--px-per-cm-for-bouts",
        type=float,
        default=DEFAULT_PX_PER_CM,
        help=(
            "Calibration used only to apply ORM bout thresholds. "
            "Reported output metrics remain in pixels/seconds."
        ),
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="List discovered pairs and output locations without rendering.",
    )
    args = ap.parse_args()

    root = Path(args.root)
    if not root.exists():
        print(f"Root path not found: {root}")
        return 1

    out_dir = Path(args.out_dir) if args.out_dir else (root / "overlay_outputs")
    summary_csv = Path(args.summary_csv) if args.summary_csv else (out_dir / "bout_summary_all_videos.csv")

    pairs = _discover_pairs(root)
    if not pairs:
        print("No video/.slp pairs found. Expected basename-matched files in the same folder.")
        return 1

    print(f"Found {len(pairs)} pair(s) under: {root}")
    if args.dry_run:
        for i, pair in enumerate(pairs, start=1):
            out_file = out_dir / f"{pair.video_path.stem}_overlay.mp4"
            print(f"[{i}] {pair.video_path} -> {pair.slp_path} -> {out_file}")
        print(f"Summary CSV would be: {summary_csv}")
        return 0

    summaries: list[PairSummary] = []
    for i, pair in enumerate(pairs, start=1):
        print(f"[{i}/{len(pairs)}] Rendering {pair.video_path.name}")
        try:
            result = _render_pair(
                pair=pair,
                out_dir=out_dir,
                max_seconds=args.max_seconds,
                trail_len=max(1, int(args.trail_len)),
                contrast=float(args.contrast),
                brightness=float(args.brightness),
                px_per_cm_for_bouts=float(args.px_per_cm_for_bouts),
            )
            summaries.append(result)
            print(
                "  -> wrote overlay | "
                f"distance(px)={result.total_distance_px:.1f}, "
                f"time_still(s)={result.time_still_s:.1f}, "
                f"bouts={result.n_bouts}"
            )
        except Exception as exc:
            print(f"  -> failed: {exc}")

    if not summaries:
        print("No overlays were generated successfully.")
        return 1

    _write_summary_csv(summaries, summary_csv)
    print(f"Wrote summary CSV: {summary_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
