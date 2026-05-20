"""
Video overlay rendering for VAST pipeline.

Renders trial videos with on-screen indicators: W (white), M (motor),
trial timer (post-ITI), cumulative distance, cumulative time still.
Reads all data from the output H5 (trial group, feedback, ambulation_metrics/spot).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

import numpy as np

try:
    import cv2

    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

from ...core.anatomy import STANDARD_NODE_NAMES
from ...core.h5_layout import resolve_ambulation_metrics_group
from ..defaults import QC_EXIT_ZONE_RADIUS_CM
from ..io.sleap_loader import (
    apply_jump_filter,
    get_skeleton_edges,
    load_sleap_file,
)
from ..db import TrialKey, open_db
from ..tracking.trace_processing import TraceProcessingParams, process_trace_data


def _decode_attr(attr: object) -> str:
    if attr is None:
        return ""
    if isinstance(attr, bytes):
        return attr.decode("utf-8", errors="replace")
    return str(attr)


def render_overlay_video(
    db_path: Path,
    key: TrialKey,
    out_path: Path,
    max_seconds: Optional[float] = None,
    contrast: float = 2.0,
    brightness: float = 5.0,
) -> Path:
    """
    Render a trial video with overlay indicators: W, M, trial timer,
    cumulative distance (m), cumulative time still (s).

    Output filename is the original video's name with an '_overlay' suffix,
    written under out_path. If out_path is a directory, output is
    out_path / (original_stem + "_overlay.mp4"). If out_path is a file path,
    output is out_path.parent / (original_stem + "_overlay" + out_path.suffix).

    Reads from output H5: trial attrs (video_path, trial_start_frame, fps, px_per_cm),
    feedback/w, feedback/m, ambulation_metrics/spot/xy. Only renders the analysis
    window (from trial_start_frame). Analysis frame i = video frame trial_start_frame + i.

    Args:
        db_path: Path to output VAST H5 database
        key: Trial key (animal_id, session, trial)
        out_path: Output directory or file path (filename derived from original + _overlay)
        max_seconds: If set, cap output to this many seconds of the analysis window
        contrast: Scale factor for frame intensity (default 2.0).
        brightness: Offset added to frame intensity (default 5.0).
    Returns:
        Path to the written overlay video file (original stem + "_overlay" + ext).
    """
    if not HAS_CV2:
        raise RuntimeError("OpenCV (cv2) is required for video overlay")

    out_path = Path(out_path)

    with open_db(db_path, "r") as h5:
        g_trial = h5[key.path()]
        attrs = g_trial.attrs

        video_path = _decode_attr(attrs.get("video_path", ""))
        if not video_path:
            raise ValueError(f"No video_path for trial {key.path()}")

        # Output filename = original stem + "_overlay" + extension, under out_path
        original_stem = Path(video_path).stem
        if out_path.suffix.lower() in (".mp4", ".avi", ".mov", ".mkv", ".webm"):
            output_file = out_path.parent / f"{original_stem}_overlay{out_path.suffix}"
        else:
            output_file = out_path / f"{original_stem}_overlay.mp4"
        output_file = output_file.resolve()
        output_file.parent.mkdir(parents=True, exist_ok=True)
        # Write OpenCV (mp4v) to temp; re-encode to H.264 for Cursor/browser preview.
        tmp_file = output_file.parent / f"{output_file.stem}.tmp.mp4"

        trial_start_frame = int(attrs.get("trial_start_frame", 0))
        fps = float(attrs.get("fps") or attrs.get("h5_fps") or 30.0)
        px_per_cm = float(attrs.get("px_per_cm", 1.0))
        if px_per_cm <= 0:
            px_per_cm = 1.0

        w_series = None
        m_series = None
        if "feedback" in g_trial:
            g_fb = g_trial["feedback"]
            if "w" in g_fb and "m" in g_fb:
                w_series = np.asarray(g_fb["w"][:], dtype=np.float64)
                m_series = np.asarray(g_fb["m"][:], dtype=np.float64)

        xy_table = None
        g_amb = resolve_ambulation_metrics_group(g_trial)
        if g_amb is not None and "spot" in g_amb:
            try:
                xy_table = g_amb["spot"]["xy"][:]
            except (KeyError, ValueError):
                pass

        sleap_path_str = _decode_attr(attrs.get("sleap_path", ""))

        exit_x = float(attrs["exit_x"]) if "exit_x" in attrs else None
        exit_y = float(attrs["exit_y"]) if "exit_y" in attrs else None
    exit_radius_px = QC_EXIT_ZONE_RADIUS_CM * px_per_cm if px_per_cm > 0 else 0.0

    n_analysis = 0
    if xy_table is not None and len(xy_table) > 0:
        n_analysis = len(xy_table)
    elif w_series is not None:
        n_analysis = len(w_series)
    elif m_series is not None:
        n_analysis = len(m_series)

    if n_analysis == 0:
        raise ValueError(f"No analysis-window data for trial {key.path()}")

    if max_seconds is not None and max_seconds > 0:
        max_frames = min(n_analysis, int(max_seconds * fps))
    else:
        max_frames = n_analysis

    # Build per-frame indicator arrays (length max_frames)
    t_s = np.arange(max_frames, dtype=np.float64) / fps
    w_display = np.full(max_frames, np.nan)
    m_display = np.full(max_frames, np.nan)
    if w_series is not None and len(w_series) >= max_frames:
        w_display = w_series[:max_frames]
    if m_series is not None and len(m_series) >= max_frames:
        m_display = m_series[:max_frames]

    cum_distance_m = np.zeros(max_frames, dtype=np.float64)
    cum_time_still_s = np.zeros(max_frames, dtype=np.float64)
    x = np.array([], dtype=np.float64)
    y = np.array([], dtype=np.float64)
    valid = np.zeros(0, dtype=bool)
    is_moving = np.zeros(0, dtype=bool)
    if xy_table is not None and len(xy_table) >= max_frames:
        x = np.asarray(xy_table["x"][:max_frames], dtype=np.float64)
        y = np.asarray(xy_table["y"][:max_frames], dtype=np.float64)
        valid = np.asarray(xy_table["valid"][:max_frames], dtype=bool)
        is_moving = np.asarray(xy_table["is_moving"][:max_frames], dtype=bool)
        # Step distance in pixels, then to meters: m = px / (px_per_cm * 100)
        dx = np.diff(x)
        dy = np.diff(y)
        step_px = np.sqrt(dx**2 + dy**2)
        step_valid = valid[:-1] & valid[1:]
        # Only count distance when animal is moving (match export total_distance_m)
        step_m = np.where(step_valid & is_moving[:-1], step_px / (px_per_cm * 100.0), 0.0)
        cum_distance_m[1:] = np.cumsum(step_m)
        # Cumulative time still
        frame_duration_s = 1.0 / fps if fps > 0 else 0.0
        still_s = np.where(~is_moving, frame_duration_s, 0.0)
        cum_time_still_s = np.cumsum(still_s)

    # Load SLEAP for skeleton overlay (optional)
    node_xy_sliced = None
    skeleton_edges: list[tuple[int, int]] = []
    if sleap_path_str and Path(sleap_path_str).exists():
        try:
            trace_data = load_sleap_file(Path(sleap_path_str))
            if trace_data is not None and trace_data.n_frames > 0:
                trace_data = apply_jump_filter(trace_data, px_per_cm=px_per_cm)
                processed = process_trace_data(
                    trace_data.traces,
                    trace_data.node_names,
                    TraceProcessingParams(),
                )
                start = trial_start_frame
                end = min(trial_start_frame + max_frames, trace_data.n_frames)
                n_slice = max(0, end - start)
                if n_slice > 0:
                    node_xy_sliced = {}
                    for node_name in STANDARD_NODE_NAMES:
                        if node_name not in processed:
                            continue
                        node = processed[node_name]
                        node_xy_sliced[node_name] = {
                            "x": np.asarray(node["x"][start:end], dtype=np.float64),
                            "y": np.asarray(node["y"][start:end], dtype=np.float64),
                        }
                    skeleton_edges = get_skeleton_edges()
        except Exception:
            node_xy_sliced = None
            skeleton_edges = []
    n_slice = 0
    if node_xy_sliced and STANDARD_NODE_NAMES:
        first_node = next((n for n in STANDARD_NODE_NAMES if n in node_xy_sliced), None)
        if first_node is not None:
            n_slice = len(node_xy_sliced[first_node]["x"])

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video: {video_path}")

    w_vid = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    h_vid = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    if w_vid <= 0 or h_vid <= 0:
        cap.release()
        raise RuntimeError("Failed to read video dimensions")

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(tmp_file), fourcc, fps, (w_vid, h_vid))
    if not writer.isOpened():
        cap.release()
        raise RuntimeError(f"Failed to open writer: {tmp_file}")

    # Seek to first frame of analysis window
    cap.set(cv2.CAP_PROP_POS_FRAMES, trial_start_frame)

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.4
    thickness = 2
    color = (255, 255, 255)
    line_type = cv2.LINE_AA

    try:
        for i in range(max_frames):
            ok, frame = cap.read()
            if not ok or frame is None:
                break

            # Brightness/contrast
            frame = cv2.convertScaleAbs(frame, alpha=contrast, beta=brightness)

            # Exit boundary (circle at exit position, QC radius)
            if exit_x is not None and exit_y is not None and exit_radius_px > 0:
                cv2.circle(
                    frame,
                    (int(round(exit_x)), int(round(exit_y))),
                    int(round(exit_radius_px)),
                    (0, 255, 0),
                    1,
                    line_type,
                )

            # Skeleton overlay (edges between nodes)
            if node_xy_sliced and skeleton_edges and i < n_slice:
                skeleton_color = (0, 200, 255)
                for a, b in skeleton_edges:
                    if a >= len(STANDARD_NODE_NAMES) or b >= len(STANDARD_NODE_NAMES):
                        continue
                    na = STANDARD_NODE_NAMES[a]
                    nb = STANDARD_NODE_NAMES[b]
                    if na not in node_xy_sliced or nb not in node_xy_sliced:
                        continue
                    xa = node_xy_sliced[na]["x"][i]
                    ya = node_xy_sliced[na]["y"][i]
                    xb = node_xy_sliced[nb]["x"][i]
                    yb = node_xy_sliced[nb]["y"][i]
                    if np.isfinite(xa) and np.isfinite(ya) and np.isfinite(xb) and np.isfinite(yb):
                        pt_a = (int(round(xa)), int(round(ya)))
                        pt_b = (int(round(xb)), int(round(yb)))
                        cv2.line(frame, pt_a, pt_b, skeleton_color, 1, line_type)

            # Spot marker (size 3)
            if xy_table is not None and i < len(x) and valid[i]:
                sx, sy = float(x[i]), float(y[i])
                if np.isfinite(sx) and np.isfinite(sy):
                    cv2.circle(
                        frame, (int(round(sx)), int(round(sy))), 3, (0, 255, 0), -1, line_type
                    )

            y_line = 28
            line_height = 16

            def put(line: str) -> None:
                nonlocal y_line
                cv2.putText(
                    frame, line, (12, y_line), font, font_scale, color, thickness, line_type
                )
                y_line += line_height

            put(f"W: {w_display[i]:.2f}" if np.isfinite(w_display[i]) else "W: --")
            put(f"M: {m_display[i]:.2f}" if np.isfinite(m_display[i]) else "M: --")
            put(f"t: {t_s[i]:.1f}s")
            put(f"dist: {cum_distance_m[i]:.3f}m")
            put(f"still: {cum_time_still_s[i]:.1f}s")

            writer.write(frame)
    finally:
        cap.release()
        writer.release()

    # Re-encode to H.264 for Cursor/browser preview (same as ehram_pipeline).
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
        try:
            tmp_file.unlink(missing_ok=True)
        except OSError:
            pass
    except FileNotFoundError:
        tmp_file.replace(output_file)
    except subprocess.CalledProcessError:
        try:
            tmp_file.replace(output_file)
        except OSError:
            pass

    return output_file
