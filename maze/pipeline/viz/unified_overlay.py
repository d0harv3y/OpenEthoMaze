"""
Unified trial overlay video: manifest-driven source video + pipeline HDF5 + optional kpMS.

ethogram sits at the bottom (full composite width); an optional **exemplar tray** column
sits to the **right** of the video (RGBA kpMS-style trajectories) when ``keypoint-moseq``
is installed (``uv sync --extra kpms``). Tray patch position is vertically centered by
default; set :attr:`UnifiedOverlayConfig.exemplar_tray_bout_centered` to tie it to the
current syllable bout.
Set :attr:`UnifiedOverlayConfig.kpms_training_exemplar_h5` to use a fixed training-derived
table (see ``scripts/build_kpms_training_exemplar_table.py``) instead of per-trial exemplars.

See ``scripts/render_trial_overlay.py`` (or ``scripts/render_ram_trial_overlay.py`` for RAM
manifest defaults). Radial-arm geometry comes from ``task_data/radial_arm`` or from
``ehram_results``-style ``/metadata/global_template`` (:mod:`maze.pipeline.viz.ram_template_draw`,
:mod:`maze.pipeline.viz.ehram_global_template_draw`). That is independent of
``metadata/arena_info`` (see :func:`_read_arena_type`, which defaults to circular when
``arena_info`` is missing). The RAM HUD uses ``ram_polys`` or radial-arm ``arena_type``;
the motor line uses circular ``arena_type`` with no ``ram_polys`` (see HUD loop below).
Layer opacities are configurable via
:class:`UnifiedOverlayConfig`.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
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
from maze.core.h5_layout import resolve_ambulation_metrics_group
from maze.core.trial_settings import TrialSettings

from ..defaults import HYBRID_POINT_NAME, QC_EXIT_ZONE_RADIUS_CM
from ..db import (
    TrialKey,
    complete_trial_timing,
    compute_seek_run_rows,
    open_db,
    ram_sessions_equivalent,
    ram_trials_equivalent,
    read_feedback_series,
    read_spot_frame_index_column,
    read_task_group_attrs,
    read_trial_settings,
    resolve_trial_key_for_hdf5,
)
from ..io.file_discovery import TrialManifest
from ..io.sleap_loader import apply_jump_filter, get_skeleton_edges, load_sleap_file
from ..tracking.trace_processing import TraceProcessingParams, process_trace_data
from .ehram_global_template_draw import load_ehram_global_template_polygons_px
from .ehram_memory_hud import merge_ehram_memory_metrics_into_ram_attrs
from .ram_template_draw import load_ram_region_polygons_px
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


def _trial_states_for_xy_overlay(xy_run: np.ndarray) -> list[str]:
    """
    Per-frame ``trial_state`` for the HUD.

    Full ORM :class:`~maze.core.schema.XY_ROW_DTYPE` tables always include ``trial_state``.
    Older or minimal exports may omit it; we then assume ``run`` for every frame so the
    overlay can render.
    """
    names = getattr(xy_run.dtype, "names", None) or ()
    n = len(xy_run)
    if "trial_state" in names:
        return [_state_str(xy_run["trial_state"][i]) for i in range(n)]
    return ["run"] * n


def _hud_memory_label(v: Any) -> str:
    if v is None or v == "":
        return "--"
    return str(v)


def _slice_series_to_overlay(
    series: Optional[np.ndarray],
    render_start_frame: int,
    max_frames: int,
) -> np.ndarray:
    """Align a per-frame series to overlay indices ``0 .. max_frames-1`` (video frame ``render_start_frame + i``)."""
    out = np.full(max_frames, np.nan, dtype=np.float64)
    if series is None or len(series) == 0:
        return out
    s = np.asarray(series, dtype=np.float64).ravel()
    for i in range(max_frames):
        j = render_start_frame + i
        if j < len(s):
            out[i] = s[j]
    return out


def _hud_scalar_or_dash(v: float) -> str:
    if np.isnan(v):
        return "--"
    return f"{float(v):.3f}"


def _put_text_outlined(
    img: np.ndarray,
    text: str,
    org: tuple[int, int],
    font: int,
    font_scale: float,
    color: tuple[int, int, int],
    thickness: int,
    line_type: int,
    *,
    outline_color: tuple[int, int, int] = (0, 0, 0),
) -> None:
    """Draw text with a 1 px outline (OpenCV has no built-in halo)."""
    x, y = int(org[0]), int(org[1])
    ot = max(1, thickness + 1)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            cv2.putText(
                img,
                text,
                (x + dx, y + dy),
                font,
                font_scale,
                outline_color,
                ot,
                line_type,
            )
    cv2.putText(img, text, (x, y), font, font_scale, color, thickness, line_type)


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
    ethogram: float = 1.0
    syllable_tray: float = 1.0


@dataclass
class UnifiedOverlayConfig:
    contrast: float = 2.0
    brightness: float = 5.0
    max_seconds: Optional[float] = None
    #: If True (default), render from video frame 0 so ``iti_wait`` rows in ``xy`` appear in
    #: the HUD; if False, start at ``trial_start_frame`` (analysis / run window only).
    include_pre_trial_frames: bool = True
    #: When set, render from this source-video frame (overrides ``include_pre_trial_frames`` start).
    clip_source_start_frame: Optional[int] = None
    #: When set with ``clip_source_start_frame``, cap the clip at this source frame (inclusive).
    clip_source_end_frame: Optional[int] = None
    #: How many past frames to include in the trajectory tail (spot history polyline).
    trajectory_history_frames: int = 42
    #: If True, older segments of the tail are drawn dimmer (see fade floor / gamma).
    trajectory_history_fade: bool = True
    #: Minimum brightness scale (0..1) at the oldest end of the tail when fading.
    trajectory_history_fade_floor: float = 0.07
    #: Fade curve: weight uses ``u**gamma`` where ``u`` goes 0 (old) → 1 (recent); ``gamma>1`` keeps the bright part tighter near the head.
    trajectory_history_fade_gamma: float = 1.0
    ethogram_height_px: int = 64
    #: Pixel width of the exemplar tray column to the right of the video.
    syllable_tray_width_px: int = 220
    syllable_tray_margin_px: int = 6
    #: Max width and max height (pixels) when fitting an exemplar patch in the tray column.
    syllable_tray_max_patch_width_px: int = 420
    #: If True, rotate each exemplar in-plane so mean nose→tail points up (+y). Off by default
    #: to match kpMS ``generate_trajectory_plots`` / ``generate_trajectory_gifs.py``.
    exemplar_vertical_heading: bool = False
    #: If True, move the exemplar patch vertically with the syllable bout center; if False,
    #: keep it fixed at mid-height of the video column.
    exemplar_tray_bout_centered: bool = False
    exemplar_pre_seconds: float = 0.167
    exemplar_post_seconds: float = 0.5
    #: Minimum global syllable frequency in the recording (see kpMS ``get_syllable_instances``).
    #: Use ``0`` to include rare syllables in the tray; higher values match publication-style filters.
    exemplar_min_frequency: float = 0.0
    exemplar_min_duration: int = 3
    exemplar_n_neighbors: int = 50
    #: When True, kpMS density sampling requires ~``exemplar_n_neighbors`` instances per syllable,
    #: so most syllables have no median loop and the tray is blank. False matches GIF-style use on
    #: single trials (median over all instances that pass duration/frequency).
    exemplar_density_sample: bool = False
    #: If True (default), median matches kpMS ``get_typical_trajectories`` (body-centered; same as
    #: trajectory GIFs). If False, arena coordinates (can look like a smeared starburst).
    exemplar_egocentric: bool = True
    #: Matches ``plot_trajectories`` default in keypoint_moseq (trajectory GIF frame count).
    exemplar_num_timesteps: int = 10
    tray_projection_plane: str = "xy"
    layers: LayerWeights = field(default_factory=LayerWeights)
    show_skeleton: bool = True
    show_trajectory: bool = True
    show_trajectory_history: bool = True
    show_arena_geometry: bool = True
    show_hud: bool = True
    #: If True, cumulative HUD distance only counts displacement during movement bouts (matches
    #: exported ``total_distance_m``). If False, sum all valid frame-to-frame steps (useful when
    #: ``is_moving`` is sparse, e.g. minimal NOR bootstraps).
    hud_distance_only_when_moving: bool = True
    #: Motor feedback (``feedback`` / ``motor_fb``) when ``arena_type`` is circular and
    #: ``ram_polys`` is unset; see HUD loop in :func:`render_unified_overlay_video`.
    show_circular_motor_hud: bool = True
    show_ethogram: bool = True
    show_syllable_tray: bool = True
    kpms_pre: KpmsPreprocessConfig = field(default_factory=KpmsPreprocessConfig)
    kpms_apply: KpmsApplyConfig = field(default_factory=KpmsApplyConfig)
    #: If set, syllable tray loops come from this HDF5 (training exemplar table)
    #: instead of recomputing from the current trial and ``kpms_results_h5``.
    kpms_training_exemplar_h5: Optional[Path] = None
    #: Extra HUD lines per video frame. Argument is **absolute** frame index (same timeline as
    #: source video / SLEAP), not the overlay loop index after ``render_start_frame``.
    hud_extra_lines_for_frame: Optional[Callable[[int], Sequence[str]]] = None
    #: If set, draw the yellow arena outline as this axis-aligned box ``(x1, y1, x2, y2)`` px
    #: instead of a circle (NOR ``objects/arena/bbox``).
    arena_bbox_px_override: Optional[tuple[float, float, float, float]] = None
    #: If set (and :attr:`arena_bbox_px_override` is unset), override pipeline attrs for the
    #: yellow arena **circle**.
    arena_center_x_px_override: Optional[float] = None
    arena_center_y_px_override: Optional[float] = None
    arena_radius_px_override: Optional[float] = None


def _apply_arena_geometry_overrides(
    settings: TrialSettings,
    cfg: UnifiedOverlayConfig,
) -> TrialSettings:
    if cfg.arena_bbox_px_override is not None:
        return settings
    kw: dict[str, float] = {}
    if cfg.arena_center_x_px_override is not None:
        kw["arena_center_x_px"] = float(cfg.arena_center_x_px_override)
    if cfg.arena_center_y_px_override is not None:
        kw["arena_center_y_px"] = float(cfg.arena_center_y_px_override)
    if cfg.arena_radius_px_override is not None:
        kw["arena_radius_px"] = float(cfg.arena_radius_px_override)
    if not kw:
        return settings
    return replace(settings, **kw)


def resolve_unique_manifest(
    manifests: list[TrialManifest],
    animal_id: str,
    session: str,
    trial: str,
) -> TrialManifest:
    aid = str(animal_id)
    matches = [
        m
        for m in manifests
        if m.animal_id == aid
        and ram_sessions_equivalent(m.session, str(session))
        and ram_trials_equivalent(m.trial, str(trial))
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


def _draw_trajectory_history_tail(
    hist_layer: np.ndarray,
    *,
    hist: int,
    i: int,
    x: np.ndarray,
    y: np.ndarray,
    valid: np.ndarray,
    fade: bool,
    fade_floor: float,
    fade_gamma: float,
    line_type: int,
) -> None:
    """Draw spot history from frame ``hist`` through ``i`` (inclusive) onto ``hist_layer``."""
    pts: list[tuple[int, int]] = []
    idxs: list[int] = []
    for j in range(hist, i + 1):
        if bool(valid[j]) and np.isfinite(x[j]) and np.isfinite(y[j]):
            pts.append((int(round(float(x[j]))), int(round(float(y[j])))))
            idxs.append(j)
    if len(pts) < 2:
        return
    b0, g0, r0 = 80, 200, 255
    span = max(i - hist, 1)
    floor = float(np.clip(fade_floor, 0.0, 1.0))
    gamma = max(float(fade_gamma), 1e-6)
    for k in range(len(pts) - 1):
        p0, p1 = pts[k], pts[k + 1]
        j1 = idxs[k + 1]
        if fade:
            u = float(j1 - hist) / float(span)
            u = min(max(u, 0.0), 1.0)
            w = floor + (1.0 - floor) * (u**gamma)
        else:
            w = 1.0
        col = (int(b0 * w), int(g0 * w), int(r0 * w))
        cv2.line(hist_layer, p0, p1, col, 2, line_type)


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


def _draw_ethogram(
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


def _open_pipeline_trial_group(h5: h5py.File, key: TrialKey, manifest: TrialManifest) -> h5py.Group:
    """Require ORM trial layout ``/animal_id/session/trial`` (ambulation metrics / spot / xy)."""
    path = key.path()
    p = path.lstrip("/")
    try:
        return h5[p]
    except KeyError:
        pass
    aid = str(key.animal_id)
    subs: list[str] = []
    if aid in h5:
        subs = sorted(h5[aid].keys())
    sub_preview = ""
    if subs:
        sub_preview = f" Under /{aid}/: {subs[:50]!r}" + (" ..." if len(subs) > 50 else "")
    nor_hint = ""
    orig = (manifest.original_session or "").strip()
    if orig and orig != key.session:
        nor_hint = (
            f" NOR manifests use phase/condition for session/trial ({key.session!r} / {key.trial!r}); "
            f"the native NOR pipeline HDF5 is usually /{aid}/{orig}/... without that three-level path. "
            "Use --pipeline-h5 pointing to a per-trial ORM bootstrap file "
            "(my_nor_wip/scripts/bootstrap_minimal_pipeline_h5.py) whose groups match "
            f"{path!r}, not the monolithic my_NOR_results.h5. "
            f"kpMS results_apply.h5 groups stay keyed like {manifest.kpms_results_dict_key!r}."
        )
    raise ValueError(f"Pipeline HDF5 has no trial group {path!r}.{sub_preview}{nor_hint}")


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

    Video frames are read from ``manifest.video_path``. By default the clip starts at table row 0;
    set ``include_pre_trial_frames=False`` to start at the resolved run-phase row (post-ITI).
    Metrics come from ``pipeline_db``; optional kpMS ethogram and exemplar tray from
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
        key = resolve_trial_key_for_hdf5(h5, key)
        arena_type = _read_arena_type(h5)
        g_trial = _open_pipeline_trial_group(h5, key, manifest)
        attrs = {k: g_trial.attrs[k] for k in g_trial.attrs.keys()}
        video_path_attr = _decode_attr(attrs.get("video_path", ""))
        if not video_path_attr:
            video_path_attr = video_path
        original_stem = Path(video_path_attr).stem

        fps = float(attrs.get("fps") or attrs.get("h5_fps") or 30.0)
        px_per_cm = float(attrs.get("px_per_cm", 1.0))
        if px_per_cm <= 0:
            px_per_cm = 1.0

        primary = (
            _decode_attr(attrs.get("primary_trajectory", HYBRID_POINT_NAME)) or HYBRID_POINT_NAME
        )
        g_amb = resolve_ambulation_metrics_group(g_trial)
        if g_amb is None:
            raise ValueError(
                f"No ambulation_metrics (or legacy 'ambulation metrics') group (trial {key.path()})"
            )
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

    settings, _h5_fps, timing = read_trial_settings(pipeline_db, key)
    settings = _apply_arena_geometry_overrides(settings, cfg)
    timing = complete_trial_timing(pipeline_db, key, timing)
    fi_xy = read_spot_frame_index_column(pipeline_db, key)
    _seek_row, run_row = compute_seek_run_rows(n_xy, fi_xy, timing)
    trial_start_frame = run_row

    # ORM RAM: task_data/radial_arm. ehram_results.h5: /metadata/global_template + trial escape_arm.
    ram_polys: Optional[dict[str, np.ndarray]] = load_ram_region_polygons_px(
        pipeline_db, key, settings
    )
    if ram_polys is None:
        ram_polys = load_ehram_global_template_polygons_px(pipeline_db, key)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video: {video_path}")
    n_vid = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    cap.release()

    n_table = n_xy
    n_effective = min(n_vid, n_table) if n_vid > 0 else n_table

    render_start_frame = 0 if cfg.include_pre_trial_frames else trial_start_frame
    if cfg.clip_source_start_frame is not None:
        render_start_frame = int(cfg.clip_source_start_frame)
    if render_start_frame >= n_effective:
        raise ValueError(
            f"Overlay start frame {render_start_frame} (trial_start_frame={trial_start_frame}, "
            f"include_pre_trial_frames={cfg.include_pre_trial_frames}) >= usable frames {n_effective}"
        )

    run_len = n_effective - render_start_frame
    if cfg.clip_source_end_frame is not None:
        clip_end = int(cfg.clip_source_end_frame)
        run_len = min(run_len, clip_end - render_start_frame + 1)
    if run_len <= 0:
        raise ValueError(
            f"Overlay clip is empty: render_start_frame={render_start_frame}, "
            f"clip_source_end_frame={cfg.clip_source_end_frame}"
        )
    if cfg.max_seconds is not None and cfg.max_seconds > 0:
        run_len = min(run_len, int(cfg.max_seconds * fps))
    max_frames = run_len

    xy_run = xy_full[render_start_frame : render_start_frame + max_frames]
    trial_states = _trial_states_for_xy_overlay(xy_run)
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
        if cfg.hud_distance_only_when_moving:
            step_m = np.where(step_valid & is_moving[:-1], step_px / (px_per_cm * 100.0), 0.0)
        else:
            step_m = np.where(step_valid, step_px / (px_per_cm * 100.0), 0.0)
        cum_distance_m[1:] = np.cumsum(step_m)
    frame_dur = 1.0 / fps if fps > 0 else 0.0
    still_s = np.where(~is_moving, frame_dur, 0.0)
    cum_time_still_s = np.cumsum(still_s)

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
    if ram_polys is not None or arena_type == ARENA_TYPE_RADIAL_ARM:
        ram_attrs = read_task_group_attrs(pipeline_db, key, ARENA_TYPE_RADIAL_ARM)
        for k in (
            "working_memory_errors",
            "reference_memory_errors",
            "reference_memory_successes",
            "exit_arm",
            "exit_arm_index",
        ):
            if k in attrs:
                ram_attrs[k] = attrs[k]
        merge_ehram_memory_metrics_into_ram_attrs(pipeline_db, key, ram_attrs)

    # Motor HUD only when no RAM template polys: if ``ram_polys`` is set, the RAM HUD path runs
    # even when ``_read_arena_type`` is circular (default or unchanged ``arena_info``).
    m_hud_frames: Optional[np.ndarray] = None
    if arena_type == ARENA_TYPE_CIRCULAR and cfg.show_circular_motor_hud and ram_polys is None:
        fb = read_feedback_series(pipeline_db, key)
        if fb is not None:
            _w_fb, m_fb = fb
            m_hud_frames = _slice_series_to_overlay(m_fb, render_start_frame, max_frames)

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

    hyp_h = cfg.ethogram_height_px if cfg.show_ethogram else 0
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
                hist = max(0, i - int(cfg.trajectory_history_frames))
                _draw_trajectory_history_tail(
                    hist_layer,
                    hist=hist,
                    i=i,
                    x=x,
                    y=y,
                    valid=valid,
                    fade=bool(cfg.trajectory_history_fade),
                    fade_floor=float(cfg.trajectory_history_fade_floor),
                    fade_gamma=float(cfg.trajectory_history_fade_gamma),
                    line_type=line_type,
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
                draw_exit_circle = True
                if cfg.arena_bbox_px_override is not None:
                    bx = cfg.arena_bbox_px_override
                    if len(bx) >= 4:
                        x1, y1, x2, y2 = (
                            float(bx[0]),
                            float(bx[1]),
                            float(bx[2]),
                            float(bx[3]),
                        )
                        cv2.rectangle(
                            geom_layer,
                            (int(round(x1)), int(round(y1))),
                            (int(round(x2)), int(round(y2))),
                            (200, 200, 0),
                            1,
                            line_type,
                        )
                elif ram_polys:
                    for name, poly in sorted(ram_polys.items()):
                        pts = np.asarray(poly, dtype=np.float64)
                        if pts.shape[0] < 2:
                            continue
                        pi = np.round(pts).astype(np.int32).reshape(-1, 1, 2)
                        col = (0, 255, 0) if name == "hole" else (200, 200, 0)
                        th = 2 if name == "hole" else 1
                        cv2.polylines(
                            geom_layer,
                            [pi],
                            isClosed=True,
                            color=col,
                            thickness=th,
                            lineType=line_type,
                        )
                    if "hole" in ram_polys:
                        draw_exit_circle = False
                elif (
                    arena_type == ARENA_TYPE_CIRCULAR
                    and settings.arena_radius_px > 0
                    and not ram_polys
                ):
                    cx, cy = (
                        int(round(settings.arena_center_x_px)),
                        int(round(settings.arena_center_y_px)),
                    )
                    r = int(round(settings.arena_radius_px))
                    cv2.circle(geom_layer, (cx, cy), r, (200, 200, 0), 1, line_type)
                if (
                    draw_exit_circle
                    and exit_x is not None
                    and exit_y is not None
                    and exit_radius_px > 0
                ):
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
                    _put_text_outlined(
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
                put(f"state: {st or '--'}  t: {state_elapsed[i]:.1f}s")
                put(f"dist: {cum_distance_m[i]:.3f}m  still: {cum_time_still_s[i]:.1f}s")
                if cfg.hud_extra_lines_for_frame is not None:
                    abs_frame = int(render_start_frame) + int(i)
                    for extra in cfg.hud_extra_lines_for_frame(abs_frame):
                        put(str(extra))
                # RAM HUD before circular motor: ``ram_polys`` can be present while
                # ``arena_type`` is still ``circular`` (see module docstring).
                if ram_polys is not None or arena_type == ARENA_TYPE_RADIAL_ARM:
                    put(
                        "Working memory errors: "
                        f"{_hud_memory_label(ram_attrs.get('working_memory_errors'))}"
                    )
                    put(
                        "Reference memory errors: "
                        f"{_hud_memory_label(ram_attrs.get('reference_memory_errors'))}"
                    )
                    put(
                        "Reference memory successes: "
                        f"{_hud_memory_label(ram_attrs.get('reference_memory_successes'))}"
                    )
                elif arena_type == ARENA_TYPE_CIRCULAR:
                    # r_cm = settings.arena_radius_cm if settings.px_per_cm > 0 else float("nan")
                    # put(f"arena_r: {r_cm:.1f}cm" if np.isfinite(r_cm) else "arena_r: --")
                    # exn = attrs.get("exit_number", settings.exit_number)
                    # put(f"exit: {int(exn) if exn is not None else '--'}")
                    if m_hud_frames is not None:
                        mv = float(m_hud_frames[i]) if i < len(m_hud_frames) else float("nan")
                        put(f"Motor: {_hud_scalar_or_dash(mv)}")

            if tray_w > 0 and exemplar_loops and cfg.layers.syllable_tray > 0:
                tray_roi = canvas[0:h_vid, w_vid : w_vid + tray_w]
                tray_roi[:] = (24, 24, 30)
                sid = int(syllable_run[i]) if i < len(syllable_run) else -1
                mrg = int(cfg.syllable_tray_margin_px)
                label = f"S {sid}" if sid >= 0 else "S --"
                fs_tray = 0.52
                (tw, th), _ = cv2.getTextSize(label, font, fs_tray, thickness)
                tx = w_vid + max(mrg, (tray_w - tw) // 2)
                ty_label = 4 + th
                cv2.putText(
                    canvas,
                    label,
                    (tx, ty_label),
                    font,
                    fs_tray,
                    (238, 238, 248),
                    thickness,
                    line_type,
                )
                label_reserve = ty_label + 8
                loop = exemplar_loops.get(sid) if sid >= 0 else None
                if loop:
                    if cfg.exemplar_tray_bout_centered:
                        _, _, bc = _bout_bounds_center(syllable_run, i)
                        y_c = _timeline_y_center(bc, max_frames, h_vid) + label_reserve // 2
                    else:
                        y_c = (h_vid + label_reserve) // 2
                    x_c = w_vid + tray_w // 2
                    fr = loop[i % len(loop)]
                    mw = max(2, min(int(cfg.syllable_tray_max_patch_width_px), tray_w - 2 * mrg))
                    v_avail = max(32, h_vid - 2 * mrg - label_reserve)
                    mh = max(2, min(int(cfg.syllable_tray_max_patch_width_px), v_avail))
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

            if hyp_h > 0 and cfg.show_ethogram:
                strip = canvas[hyp_y0 : hyp_y0 + hyp_h, :]
                _draw_ethogram(strip, syllable_run, i, alpha=cfg.layers.ethogram)

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
