"""
Unified trial overlay video: manifest-driven source video + pipeline HDF5 + optional kpMS.

Hypnogram sits at the bottom (full composite width); an optional **exemplar tray** column
sits to the **right** of the video (RGBA kpMS-style trajectories) when ``keypoint-moseq``
is installed (``uv sync --extra kpms``). Tray patch position is vertically centered by
default; set :attr:`UnifiedOverlayConfig.exemplar_tray_bout_centered` to tie it to the
current syllable bout.
Set :attr:`UnifiedOverlayConfig.kpms_training_exemplar_h5` to use a fixed training-derived
table (see ``scripts/build_kpms_training_exemplar_table.py``) instead of per-trial exemplars.

See ``scripts/render_trial_overlay.py`` for CLI. Layer opacities are configurable via
:class:`UnifiedOverlayConfig`.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np

try:
    import cv2

    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

import h5py

from maze.core.anatomy import STANDARD_NODE_NAMES
from maze.core.tasks import ARENA_TYPE_CIRCULAR, ARENA_TYPE_RADIAL_ARM, normalize_arena_type

from ..defaults import HYBRID_POINT_NAME, QC_EXIT_ZONE_RADIUS_CM
from ..db import (
    TrialKey,
    open_db,
    read_feedback_series,
    read_task_group_attrs,
    read_trial_settings,
)
from ..io.file_discovery import TrialManifest
from ..io.sleap_loader import apply_jump_filter, get_skeleton_edges, load_sleap_file
from ..tracking.trace_processing import TraceProcessingParams, process_trace_data
from .video_overlay import _decode_attr

from maze.kpms.apply import KpmsApplyConfig
from maze.kpms.frame_alignment import (
    kpms_aligned_coordinates_and_indices,
    kpms_recording_key,
)
from maze.kpms.preprocess import KpmsPreprocessConfig


def _read_arena_type(h5: h5py.File) -> str:
    meta = h5.get("metadata")
    if meta is None:
        return ARENA_TYPE_CIRCULAR
    ainfo = meta.get("arena_info")
    if ainfo is None:
        return ARENA_TYPE_CIRCULAR
    raw = ainfo.attrs.get("type", ARENA_TYPE_CIRCULAR)
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    return normalize_arena_type(str(raw))


def _state_str(cell: Any) -> str:
    if cell is None:
        return ""
    if isinstance(cell, bytes):
        return cell.decode("utf-8", errors="replace").strip("\x00 \t\n\r")
    return str(cell).strip()


def _feedback_wm_for_overlay(
    w_series: np.ndarray,
    m_series: np.ndarray,
    *,
    render_start_frame: int,
    max_frames: int,
    trial_start_frame: int,
    n_effective: int,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Map stored W/M series onto overlay frame indices.

    Legacy DB stores feedback as ``w[trial_start_frame:]`` (same length as analysis window).
    Some tables span all ``n_effective`` frames (index = absolute video frame).
    """
    w_arr = np.full(max_frames, np.nan)
    m_arr = np.full(max_frames, np.nan)
    lw, lm = len(w_series), len(m_series)
    if lw <= 0 or lm <= 0:
        return w_arr, m_arr
    L = min(lw, lm)
    w_s = np.asarray(w_series[:L], dtype=np.float64)
    m_s = np.asarray(m_series[:L], dtype=np.float64)

    if L >= n_effective:
        rs = min(render_start_frame, L)
        re = min(rs + max_frames, L)
        n = re - rs
        if n > 0:
            w_arr[:n] = w_s[rs:re]
            m_arr[:n] = m_s[rs:re]
        return w_arr, m_arr

    ts = int(trial_start_frame)
    for i in range(max_frames):
        abs_f = render_start_frame + i
        j = abs_f - ts
        if 0 <= j < L:
            w_arr[i] = w_s[j]
            m_arr[i] = m_s[j]
    return w_arr, m_arr


def _syllable_bgr(sid: int) -> tuple[int, int, int]:
    if sid < 0:
        return (40, 40, 40)
    hue = (sid * 37) % 180
    hsv = np.uint8([[[hue, 200, 220]]])
    bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)[0, 0]
    return int(bgr[0]), int(bgr[1]), int(bgr[2])


@dataclass
class LayerWeights:
    """Opacity 0..1 for composited drawing layers (video is always 1)."""

    trajectory: float = 0.85
    trajectory_history: float = 0.6
    skeleton: float = 0.9
    arena_geometry: float = 0.75
    hud: float = 1.0
    hypnogram: float = 1.0
    syllable_tray: float = 1.0


@dataclass
class UnifiedOverlayConfig:
    contrast: float = 2.0
    brightness: float = 5.0
    max_seconds: Optional[float] = None
    #: If True (default), render from video frame 0 so ``iti_wait`` rows in ``xy`` appear in
    #: the HUD; if False, start at ``trial_start_frame`` (analysis / run window only).
    include_pre_trial_frames: bool = True
    trajectory_history_frames: int = 45
    hypnogram_height_px: int = 96
    #: Pixel width of the exemplar tray column to the right of the video.
    syllable_tray_width_px: int = 140
    syllable_tray_margin_px: int = 6
    #: Max width and max height (pixels) when fitting an exemplar patch in the tray column.
    syllable_tray_max_patch_width_px: int = 420
    #: If True, rotate each exemplar in-plane so mean nose→tail points up (+y in the patch).
    exemplar_vertical_heading: bool = True
    #: If True, move the exemplar patch vertically with the syllable bout center; if False,
    #: keep it fixed at mid-height of the video column.
    exemplar_tray_bout_centered: bool = False
    exemplar_pre_seconds: float = 0.167
    exemplar_post_seconds: float = 0.5
    exemplar_min_frequency: float = 0.003
    exemplar_min_duration: int = 3
    exemplar_n_neighbors: int = 50
    exemplar_density_sample: bool = True
    #: If True, median trajectory matches kpMS body-centered ``get_typical_trajectories``.
    #: If False (default), use arena coordinates so the loop shows translation.
    exemplar_egocentric: bool = False
    exemplar_num_timesteps: int = 14
    tray_projection_plane: str = "xy"
    layers: LayerWeights = field(default_factory=LayerWeights)
    show_skeleton: bool = True
    show_trajectory: bool = True
    show_trajectory_history: bool = True
    show_arena_geometry: bool = True
    show_hud: bool = True
    show_hypnogram: bool = True
    show_syllable_tray: bool = True
    kpms_pre: KpmsPreprocessConfig = field(default_factory=KpmsPreprocessConfig)
    kpms_apply: KpmsApplyConfig = field(default_factory=KpmsApplyConfig)
    #: If set, syllable tray loops come from this HDF5 (training exemplar table)
    #: instead of recomputing from the current trial and ``kpms_results_h5``.
    kpms_training_exemplar_h5: Optional[Path] = None


def resolve_unique_manifest(
    manifests: list[TrialManifest],
    animal_id: str,
    session: str,
    trial: str,
) -> TrialManifest:
    matches = [
        m
        for m in manifests
        if m.animal_id == str(animal_id) and m.session == str(session) and m.trial == str(trial)
    ]
    if not matches:
        sessions = sorted({m.session for m in manifests if m.animal_id == str(animal_id)})
        raise ValueError(
            f"No manifest row for animal_id={animal_id!r} session={session!r} trial={trial!r}. "
            f"Sessions for this animal in CSV: {sessions[:20]}"
            + (" ..." if len(sessions) > 20 else "")
        )
    if len(matches) > 1:
        raise ValueError(
            f"Multiple manifest rows for animal_id={animal_id!r} session={session!r} trial={trial!r}"
        )
    return matches[0]


def _blend_layer(base: np.ndarray, layer: np.ndarray, alpha: float) -> None:
    if alpha <= 0:
        return
    mask = np.any(layer > 0, axis=2)
    if not np.any(mask):
        return
    if alpha >= 1.0:
        base[mask] = layer[mask]
        return
    b = base[mask].astype(np.float32)
    ell = layer[mask].astype(np.float32)
    base[mask] = (b * (1.0 - alpha) + ell * alpha).astype(np.uint8)


def _precompute_state_elapsed_s(trial_states: list[str], fps: float) -> np.ndarray:
    n = len(trial_states)
    out = np.zeros(n, dtype=np.float64)
    if n == 0:
        return out
    dt = 1.0 / fps if fps > 0 else 0.0
    cur = trial_states[0]
    acc = dt
    out[0] = dt
    for i in range(1, n):
        if trial_states[i] != cur:
            cur = trial_states[i]
            acc = dt
        else:
            acc += dt
        out[i] = acc
    return out


def _draw_hypnogram(
    strip: np.ndarray,
    syllable_run: np.ndarray,
    frame_idx: int,
    alpha: float = 1.0,
) -> None:
    h, w = strip.shape[:2]
    strip[:] = (28, 28, 32)
    n = len(syllable_run)
    if n <= 0:
        return
    for x in range(w):
        fi = int(x * n / w)
        fi = min(fi, n - 1)
        sid = int(syllable_run[fi])
        c = _syllable_bgr(sid)
        cv2.line(strip, (x, 0), (x, h - 1), c, 1)
    px = int((frame_idx + 0.5) * w / n) if n > 0 else 0
    px = max(0, min(w - 1, px))
    cv2.line(strip, (px, 0), (px, h - 1), (255, 255, 255), 2)


def _bout_bounds_center(syllable_run: np.ndarray, i: int) -> tuple[int, int, int]:
    """Return (bout_start, bout_end, center_index) for the bout containing ``i``."""
    n = len(syllable_run)
    if n <= 0 or i < 0 or i >= n:
        return i, i, i
    sid = int(syllable_run[i])
    if sid < 0:
        return i, i, i
    b0 = i
    while b0 > 0 and int(syllable_run[b0 - 1]) == sid:
        b0 -= 1
    b1 = i
    while b1 < n - 1 and int(syllable_run[b1 + 1]) == sid:
        b1 += 1
    c = (b0 + b1) // 2
    return b0, b1, c


def _timeline_y_center(frame_index: int, n_frames: int, canvas_h: int) -> int:
    if n_frames <= 0:
        return canvas_h // 2
    return int((frame_index + 0.5) * canvas_h / n_frames)


def _alpha_paste_rgba_on_bgr(
    bgr: np.ndarray,
    rgba: np.ndarray,
    x0: int,
    y0: int,
    opacity: float,
) -> None:
    """Composite RGBA patch onto BGR image at top-left (x0, y0), clipping to bounds."""
    h, w = rgba.shape[:2]
    H, W = bgr.shape[:2]
    x0c = max(0, x0)
    y0c = max(0, y0)
    x1c = min(W, x0 + w)
    y1c = min(H, y0 + h)
    if x0c >= x1c or y0c >= y1c:
        return
    sx0 = x0c - x0
    sy0 = y0c - y0
    roi = bgr[y0c:y1c, x0c:x1c]
    sl = rgba[sy0 : sy0 + roi.shape[0], sx0 : sx0 + roi.shape[1]]
    a = sl[..., 3:4].astype(np.float32) / 255.0 * float(opacity)
    rgb = sl[..., :3].astype(np.float32)
    roi_f = roi.astype(np.float32)
    roi[:] = (roi_f * (1.0 - a) + rgb * a).astype(np.uint8)


def _fit_rgba_to_box(rgba: np.ndarray, max_w: int, max_h: int) -> np.ndarray:
    h0, w0 = rgba.shape[:2]
    if w0 <= 0 or h0 <= 0 or max_w < 2 or max_h < 2:
        return rgba
    scale = min(max_w / w0, max_h / h0)
    nw = max(2, int(round(w0 * scale)))
    nh = max(2, int(round(h0 * scale)))
    return cv2.resize(rgba, (nw, nh), interpolation=cv2.INTER_AREA)


def render_unified_overlay_video(
    *,
    manifest: TrialManifest,
    pipeline_db: Path,
    key: TrialKey,
    out_path: Path,
    kpms_results_h5: Optional[Path] = None,
    cfg: Optional[UnifiedOverlayConfig] = None,
) -> Path:
    """
    Render composed overlay MP4 for one trial.

    Video frames are read from ``manifest.video_path``. By default the clip starts at frame 0
    so ``iti_wait`` band labels in ``ambulation_metrics`` are included; set
    ``include_pre_trial_frames=False`` to start at ``trial_start_frame`` only.
    Metrics come from ``pipeline_db``; optional kpMS hypnogram and exemplar tray from
    ``kpms_results_h5`` (and optional training exemplar HDF5 on ``cfg``).
    """
    if not HAS_CV2:
        raise RuntimeError("OpenCV (cv2) is required for unified overlay")

    cfg = cfg or UnifiedOverlayConfig()
    if manifest.video_path is None or not Path(manifest.video_path).is_file():
        raise ValueError("Manifest row has no usable video_path")

    video_path = str(Path(manifest.video_path).resolve())
    out_path = Path(out_path)

    with open_db(pipeline_db, "r") as h5:
        arena_type = _read_arena_type(h5)
        g_trial = h5[key.path()]
        attrs = {k: g_trial.attrs[k] for k in g_trial.attrs.keys()}
        video_path_attr = _decode_attr(attrs.get("video_path", ""))
        if not video_path_attr:
            video_path_attr = video_path
        original_stem = Path(video_path_attr).stem

        trial_start_frame = int(attrs.get("trial_start_frame", 0))
        fps = float(attrs.get("fps") or attrs.get("h5_fps") or 30.0)
        px_per_cm = float(attrs.get("px_per_cm", 1.0))
        if px_per_cm <= 0:
            px_per_cm = 1.0

        primary = (
            _decode_attr(attrs.get("primary_trajectory", HYBRID_POINT_NAME)) or HYBRID_POINT_NAME
        )
        g_amb = g_trial.get("ambulation_metrics")
        if g_amb is None:
            raise ValueError(f"No ambulation_metrics group (trial {key.path()})")
        if primary not in g_amb:
            if "spot" in g_amb:
                primary = "spot"
            else:
                raise ValueError(
                    f"No ambulation_metrics point {primary!r} (trial {key.path()}); "
                    f"available: {list(g_amb.keys())}"
                )

        xy_full = g_amb[primary]["xy"][:]
        n_xy = len(xy_full)

    settings, _h5_fps, tsf_settings = read_trial_settings(pipeline_db, key)
    if tsf_settings != trial_start_frame and tsf_settings > 0:
        trial_start_frame = tsf_settings

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video: {video_path}")
    n_vid = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    cap.release()

    n_table = n_xy
    n_effective = min(n_vid, n_table) if n_vid > 0 else n_table

    render_start_frame = 0 if cfg.include_pre_trial_frames else trial_start_frame
    if render_start_frame >= n_effective:
        raise ValueError(
            f"Overlay start frame {render_start_frame} (trial_start_frame={trial_start_frame}, "
            f"include_pre_trial_frames={cfg.include_pre_trial_frames}) >= usable frames {n_effective}"
        )

    run_len = n_effective - render_start_frame
    if cfg.max_seconds is not None and cfg.max_seconds > 0:
        run_len = min(run_len, int(cfg.max_seconds * fps))
    max_frames = run_len

    xy_run = xy_full[render_start_frame : render_start_frame + max_frames]
    trial_states = [_state_str(xy_run["trial_state"][i]) for i in range(len(xy_run))]
    state_elapsed = _precompute_state_elapsed_s(trial_states, fps)

    x = np.asarray(xy_run["x"], dtype=np.float64)
    y = np.asarray(xy_run["y"], dtype=np.float64)
    valid = np.asarray(xy_run["valid"], dtype=bool)
    is_moving = np.asarray(xy_run["is_moving"], dtype=bool)

    cum_distance_m = np.zeros(max_frames, dtype=np.float64)
    cum_time_still_s = np.zeros(max_frames, dtype=np.float64)
    if max_frames > 1:
        dx = np.diff(x)
        dy = np.diff(y)
        step_px = np.sqrt(dx**2 + dy**2)
        step_valid = valid[:-1] & valid[1:]
        step_m = np.where(step_valid & is_moving[:-1], step_px / (px_per_cm * 100.0), 0.0)
        cum_distance_m[1:] = np.cumsum(step_m)
    frame_dur = 1.0 / fps if fps > 0 else 0.0
    still_s = np.where(~is_moving, frame_dur, 0.0)
    cum_time_still_s = np.cumsum(still_s)

    fb = read_feedback_series(pipeline_db, key)
    if fb is not None:
        w_ser, m_ser = fb
        w_arr, m_arr = _feedback_wm_for_overlay(
            w_ser,
            m_ser,
            render_start_frame=render_start_frame,
            max_frames=max_frames,
            trial_start_frame=trial_start_frame,
            n_effective=n_effective,
        )
    else:
        w_arr = np.full(max_frames, np.nan)
        m_arr = np.full(max_frames, np.nan)

    syllable_run = np.full(max_frames, -1, dtype=np.int32)
    kpms_aligned: tuple[str, np.ndarray, np.ndarray] | None = None
    if kpms_results_h5 is not None and Path(kpms_results_h5).is_file():
        rk = kpms_recording_key(manifest)
        kpms_aligned = kpms_aligned_coordinates_and_indices(
            manifest,
            cfg.kpms_pre,
            conf_threshold=cfg.kpms_apply.conf_threshold,
            min_points_per_frame=cfg.kpms_apply.min_points_per_frame,
            min_fragment_frames=cfg.kpms_apply.min_fragment_frames,
        )
        with h5py.File(str(kpms_results_h5), "r") as kh5:
            if rk in kh5 and "syllable" in kh5[rk] and kpms_aligned is not None:
                _rk, _coord, src_idx = kpms_aligned
                z = np.asarray(kh5[rk]["syllable"][:], dtype=np.int32).ravel()
                n_map = min(len(z), len(src_idx))
                for j in range(n_map):
                    gi = int(src_idx[j])
                    ir = gi - render_start_frame
                    if 0 <= ir < max_frames:
                        syllable_run[ir] = int(z[j])

    ram_attrs: dict[str, Any] = {}
    if arena_type == ARENA_TYPE_RADIAL_ARM:
        ram_attrs = read_task_group_attrs(pipeline_db, key, ARENA_TYPE_RADIAL_ARM)
        for k in (
            "working_memory_errors",
            "reference_memory_errors",
            "reference_memory_successes",
            "exit_arm",
        ):
            if k in attrs:
                ram_attrs[k] = attrs[k]

    sleap_path_str = _decode_attr(attrs.get("sleap_path", ""))
    if not sleap_path_str and manifest.sleap_path:
        sleap_path_str = str(Path(manifest.sleap_path))

    node_xy_sliced: Optional[dict[str, dict[str, np.ndarray]]] = None
    skeleton_edges: list[tuple[int, int]] = []
    if cfg.show_skeleton and sleap_path_str and Path(sleap_path_str).exists():
        try:
            trace_data = load_sleap_file(Path(sleap_path_str))
            if trace_data is not None and trace_data.n_frames > 0:
                trace_data = apply_jump_filter(
                    trace_data,
                    max_jump_cm=cfg.kpms_pre.jump_filter_cm,
                    px_per_cm=px_per_cm,
                    lookahead_frames=cfg.kpms_pre.jump_filter_lookahead_frames,
                )
                processed = process_trace_data(
                    trace_data.traces,
                    trace_data.node_names,
                    TraceProcessingParams(),
                )
                start = render_start_frame
                end = min(render_start_frame + max_frames, trace_data.n_frames)
                if end > start:
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
        except OSError:
            node_xy_sliced = None

    exit_x = float(attrs["exit_x"]) if "exit_x" in attrs else settings.exit_x
    exit_y = float(attrs["exit_y"]) if "exit_y" in attrs else settings.exit_y
    exit_radius_px = QC_EXIT_ZONE_RADIUS_CM * px_per_cm

    exemplar_loops: dict[int, list[np.ndarray]] = {}
    tray_w = 0
    if cfg.show_syllable_tray:
        from .kpms_exemplar_tray import (
            HAS_KPMS_TRAY,
            build_exemplar_rgba_loops_for_syllables,
            exemplar_rgba_loops_from_typical_arrays,
        )

        if HAS_KPMS_TRAY:
            syllable_ids = sorted({int(s) for s in np.unique(syllable_run) if int(s) >= 0})
            if syllable_ids:
                try:
                    tex = cfg.kpms_training_exemplar_h5
                    if tex is not None and Path(tex).is_file():
                        from maze.kpms.training_exemplar_table import load_training_exemplar_typical

                        typical = load_training_exemplar_typical(Path(tex), syllable_ids)
                        exemplar_loops = exemplar_rgba_loops_from_typical_arrays(
                            typical,
                            syllable_ids,
                            projection_plane=cfg.tray_projection_plane,
                            num_timesteps=cfg.exemplar_num_timesteps,
                            vertical_heading=cfg.exemplar_vertical_heading,
                        )
                    elif kpms_results_h5 is not None and Path(kpms_results_h5).is_file():
                        exemplar_loops = build_exemplar_rgba_loops_for_syllables(
                            Path(kpms_results_h5),
                            manifest,
                            syllable_ids,
                            pre_cfg=cfg.kpms_pre,
                            conf_threshold=cfg.kpms_apply.conf_threshold,
                            min_points_per_frame=cfg.kpms_apply.min_points_per_frame,
                            min_fragment_frames=cfg.kpms_apply.min_fragment_frames,
                            fps=fps,
                            pre_seconds=cfg.exemplar_pre_seconds,
                            post_seconds=cfg.exemplar_post_seconds,
                            min_frequency=cfg.exemplar_min_frequency,
                            min_duration=cfg.exemplar_min_duration,
                            density_sample=cfg.exemplar_density_sample,
                            n_neighbors=cfg.exemplar_n_neighbors,
                            projection_plane=cfg.tray_projection_plane,
                            num_timesteps=cfg.exemplar_num_timesteps,
                            vertical_heading=cfg.exemplar_vertical_heading,
                            egocentric=cfg.exemplar_egocentric,
                        )
                except Exception:
                    exemplar_loops = {}
        if exemplar_loops:
            tray_w = int(cfg.syllable_tray_width_px)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video: {video_path}")
    w_vid = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    h_vid = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    if w_vid <= 0 or h_vid <= 0:
        cap.release()
        raise RuntimeError("Failed to read video dimensions")

    hyp_h = cfg.hypnogram_height_px if cfg.show_hypnogram else 0
    hyp_y0 = h_vid
    out_h = h_vid + hyp_h
    out_w = w_vid + tray_w

    if out_path.suffix.lower() in (".mp4", ".avi", ".mov", ".mkv", ".webm"):
        output_file = out_path.parent / f"{original_stem}_unified_overlay{out_path.suffix}"
    else:
        out_path.mkdir(parents=True, exist_ok=True)
        output_file = out_path / f"{original_stem}_unified_overlay.mp4"
    output_file = output_file.resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = output_file.parent / f"{output_file.stem}.tmp.mp4"

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(tmp_file), fourcc, fps, (out_w, out_h))
    if not writer.isOpened():
        cap.release()
        raise RuntimeError(f"Failed to open writer: {tmp_file}")

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.42
    thickness = 1
    line_type = cv2.LINE_AA

    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES, render_start_frame)
        for i in range(max_frames):
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            frame = cv2.convertScaleAbs(frame, alpha=cfg.contrast, beta=cfg.brightness)

            hist_layer = np.zeros_like(frame)
            if cfg.show_trajectory_history and cfg.layers.trajectory_history > 0:
                hist = max(0, i - cfg.trajectory_history_frames)
                pts = []
                for j in range(hist, i + 1):
                    if valid[j] and np.isfinite(x[j]) and np.isfinite(y[j]):
                        pts.append((int(round(x[j])), int(round(y[j]))))
                if len(pts) >= 2:
                    cv2.polylines(
                        hist_layer,
                        [np.array(pts, dtype=np.int32)],
                        False,
                        (80, 200, 255),
                        2,
                        line_type,
                    )
            _blend_layer(frame, hist_layer, cfg.layers.trajectory_history)

            traj_layer = np.zeros_like(frame)
            if cfg.show_trajectory and cfg.layers.trajectory > 0:
                if valid[i] and np.isfinite(x[i]) and np.isfinite(y[i]):
                    cv2.circle(
                        traj_layer,
                        (int(round(x[i])), int(round(y[i]))),
                        4,
                        (0, 255, 100),
                        -1,
                        line_type,
                    )
            _blend_layer(frame, traj_layer, cfg.layers.trajectory)

            skel_layer = np.zeros_like(frame)
            if cfg.show_skeleton and cfg.layers.skeleton > 0 and node_xy_sliced and skeleton_edges:
                col = (0, 200, 255)
                for a, b in skeleton_edges:
                    if a >= len(STANDARD_NODE_NAMES) or b >= len(STANDARD_NODE_NAMES):
                        continue
                    na, nb = STANDARD_NODE_NAMES[a], STANDARD_NODE_NAMES[b]
                    if na not in node_xy_sliced or nb not in node_xy_sliced:
                        continue
                    xa, ya = node_xy_sliced[na]["x"][i], node_xy_sliced[na]["y"][i]
                    xb, yb = node_xy_sliced[nb]["x"][i], node_xy_sliced[nb]["y"][i]
                    if np.isfinite(xa) and np.isfinite(ya) and np.isfinite(xb) and np.isfinite(yb):
                        cv2.line(
                            skel_layer,
                            (int(round(xa)), int(round(ya))),
                            (int(round(xb)), int(round(yb))),
                            col,
                            1,
                            line_type,
                        )
            _blend_layer(frame, skel_layer, cfg.layers.skeleton)

            geom_layer = np.zeros_like(frame)
            if cfg.show_arena_geometry and cfg.layers.arena_geometry > 0:
                if arena_type == ARENA_TYPE_CIRCULAR and settings.arena_radius_px > 0:
                    cx, cy = (
                        int(round(settings.arena_center_x_px)),
                        int(round(settings.arena_center_y_px)),
                    )
                    r = int(round(settings.arena_radius_px))
                    cv2.circle(geom_layer, (cx, cy), r, (200, 200, 0), 1, line_type)
                if exit_x is not None and exit_y is not None and exit_radius_px > 0:
                    cv2.circle(
                        geom_layer,
                        (int(round(exit_x)), int(round(exit_y))),
                        int(round(exit_radius_px)),
                        (0, 255, 0),
                        1,
                        line_type,
                    )
            _blend_layer(frame, geom_layer, cfg.layers.arena_geometry)

            canvas = np.zeros((out_h, out_w, 3), dtype=np.uint8)
            canvas[0:h_vid, 0:w_vid] = frame

            if cfg.show_hud and cfg.layers.hud > 0:
                yl = 24
                lh = 17

                def put(line: str) -> None:
                    nonlocal yl
                    cv2.putText(
                        canvas,
                        line,
                        (10, yl),
                        font,
                        font_scale,
                        (255, 255, 255),
                        thickness,
                        line_type,
                    )
                    yl += lh

                st = trial_states[i] if i < len(trial_states) else ""
                put(f"state: {st or '--'}  t_state: {state_elapsed[i]:.1f}s")
                # put(f"W: {w_arr[i]:.2f}" if np.isfinite(w_arr[i]) else "W: --")
                put(f"Motor: {m_arr[i]:.2f}" if np.isfinite(m_arr[i]) else "Motor: --")
                put(f"dist: {cum_distance_m[i]:.3f}m  still: {cum_time_still_s[i]:.1f}s")
                if arena_type == ARENA_TYPE_CIRCULAR:
                    # r_cm = settings.arena_radius_cm if settings.px_per_cm > 0 else float("nan")
                    # put(f"arena_r: {r_cm:.1f}cm" if np.isfinite(r_cm) else "arena_r: --")
                    # exn = attrs.get("exit_number", settings.exit_number)
                    # put(f"exit: {int(exn) if exn is not None else '--'}")
                    pass
                elif arena_type == ARENA_TYPE_RADIAL_ARM:
                    wme = ram_attrs.get("working_memory_errors", "--")
                    rme = ram_attrs.get("reference_memory_errors", "--")
                    rms = ram_attrs.get("reference_memory_successes", "--")
                    # put(f"RAM WME: {wme}  RME: {rme}  RMS: {rms}")
                    # ex_arm = ram_attrs.get("exit_arm", attrs.get("exit_arm_index", "--"))
                    # put(f"exit_arm: {ex_arm}")

            if tray_w > 0 and exemplar_loops and cfg.layers.syllable_tray > 0:
                tray_roi = canvas[0:h_vid, w_vid : w_vid + tray_w]
                tray_roi[:] = (24, 24, 30)
                sid = int(syllable_run[i]) if i < len(syllable_run) else -1
                loop = exemplar_loops.get(sid) if sid >= 0 else None
                if loop:
                    if cfg.exemplar_tray_bout_centered:
                        _, _, bc = _bout_bounds_center(syllable_run, i)
                        y_c = _timeline_y_center(bc, max_frames, h_vid)
                    else:
                        y_c = h_vid // 2
                    x_c = w_vid + tray_w // 2
                    fr = loop[i % len(loop)]
                    mrg = int(cfg.syllable_tray_margin_px)
                    mw = max(2, min(int(cfg.syllable_tray_max_patch_width_px), tray_w - 2 * mrg))
                    mh = max(2, min(int(cfg.syllable_tray_max_patch_width_px), h_vid - 2 * mrg))
                    fitted = _fit_rgba_to_box(fr, mw, mh)
                    x0 = x_c - fitted.shape[1] // 2
                    y0 = y_c - fitted.shape[0] // 2
                    _alpha_paste_rgba_on_bgr(
                        canvas,
                        fitted,
                        x0,
                        y0,
                        float(cfg.layers.syllable_tray),
                    )

            if hyp_h > 0 and cfg.show_hypnogram:
                strip = canvas[hyp_y0 : hyp_y0 + hyp_h, :]
                _draw_hypnogram(strip, syllable_run, i, alpha=cfg.layers.hypnogram)

            writer.write(canvas)
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
        try:
            tmp_file.unlink(missing_ok=True)
        except OSError:
            pass
    except (FileNotFoundError, subprocess.CalledProcessError):
        try:
            tmp_file.replace(output_file)
        except OSError:
            pass

    return output_file
