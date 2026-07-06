"""Render per-bout clips for behavior-token grid movies."""

from __future__ import annotations

import argparse
import math
from dataclasses import replace
from pathlib import Path
from typing import Callable

import numpy as np

from maze.core.anatomy import SKELETON_EDGES, STANDARD_NODE_NAMES
from maze.kpms.apply_summary import preprocess_config_for_results_h5
from maze.kpms.behavior_ethogram.grammar_matches import (
    DEFAULT_PREVIEW_PADDING_S,
    PatternMatch,
    clip_frames_for_match,
)
from maze.kpms.frame_alignment import kpms_aligned_coordinates_and_indices
from maze.kpms.preprocess import KpmsPreprocessConfig
from maze.pipeline.db.trial_key import TrialKey
from maze.pipeline.io.file_discovery import TrialManifest
from maze.pipeline.video_paths import resolve_video_path
from maze.pipeline.viz.overlay_cli import run_unified_overlay_from_args
from maze.pipeline.viz.unified_overlay import UnifiedOverlayConfig


def _trial_fps(pipeline_h5: Path, manifest: TrialManifest) -> float:
    from maze.pipeline.db import read_trial_settings

    key = TrialKey.from_manifest(manifest)
    _settings, fps, _timing = read_trial_settings(pipeline_h5, key)
    return float(fps) if fps and fps > 0 else 30.0


def _overlay_namespace(
    *,
    manifest: TrialManifest,
    manifest_path: Path,
    pipeline_h5: Path,
    results_h5: Path,
    out_file: Path,
    pre_cfg: KpmsPreprocessConfig,
    no_ethogram: bool,
    no_syllable_tray: bool,
) -> argparse.Namespace:
    return argparse.Namespace(
        manifest_csv=manifest_path,
        pipeline_h5=pipeline_h5,
        animal_id=str(manifest.animal_id),
        session=str(manifest.session),
        trial=str(manifest.trial),
        out=out_file,
        kpms_h5=results_h5,
        kpms_training_exemplars=None,
        max_seconds=None,
        contrast=2.0,
        brightness=5.0,
        kpms_px_per_cm=pre_cfg.px_per_cm,
        analysis_only=True,
        history_frames=None,
        no_history_fade=False,
        history_fade_floor=None,
        history_fade_gamma=None,
        no_ethogram=bool(no_ethogram),
        no_syllable_tray=bool(no_syllable_tray),
        tray_width=None,
        vertical_exemplar_heading=False,
        bout_center_exemplar_tray=True,
        tray_projection=None,
        exemplar_min_frequency=None,
        exemplar_min_duration=None,
        exemplar_neighbors=None,
        exemplar_density_sample=False,
        exemplar_timesteps=None,
        exemplar_arena_coords=False,
        opacity_trajectory=None,
        opacity_trail=None,
        opacity_skeleton=None,
        opacity_arena=None,
        opacity_ethogram=None,
        opacity_tray=None,
        no_skeleton=False,
        no_hud=False,
        no_circular_motor_hud=False,
    )


def _clip_overlay_cfg(
    cfg: UnifiedOverlayConfig,
    *,
    clip_start: int,
    clip_end: int,
    behavior_token: int,
    trial_key: str,
) -> None:
    cfg.clip_source_start_frame = clip_start
    cfg.clip_source_end_frame = clip_end
    cfg.include_pre_trial_frames = False
    label = f"token {behavior_token} | {trial_key}"

    def _extra_lines(_frame_index: int) -> tuple[str, ...]:
        return (label,)

    cfg.hud_extra_lines_for_frame = _extra_lines


def _sync_kpms_pre_cfg(cfg: UnifiedOverlayConfig, pre_cfg: KpmsPreprocessConfig) -> None:
    """Propagate tracking/preprocess settings into overlay (tray + skeleton read H5 first)."""
    cfg.kpms_pre = replace(
        cfg.kpms_pre,
        min_fragment_frames=pre_cfg.min_fragment_frames,
        jump_filter_cm=pre_cfg.jump_filter_cm,
        jump_filter_lookahead_frames=pre_cfg.jump_filter_lookahead_frames,
        px_per_cm=pre_cfg.px_per_cm,
        retain_all_frames=pre_cfg.retain_all_frames,
        db_path=pre_cfg.db_path,
        pose_stream=pre_cfg.pose_stream,
    )


def manifest_has_video(manifest: TrialManifest) -> bool:
    if not manifest.video_path:
        return False
    resolved = resolve_video_path(manifest.video_path)
    return resolved is not None and Path(resolved).is_file()


def trial_usable_overlay_frame_end_exclusive(
    manifest: TrialManifest,
    pipeline_h5: Path,
) -> int | None:
    """Exclusive upper bound on overlay source frames (matches unified overlay ``n_effective``)."""
    import cv2

    from maze.pipeline.db import open_db
    from maze.pipeline.db.trial_key import TrialKey
    from maze.pipeline.viz.overlay_frame_align import source_frame_exclusive_end, xy_source_frame_indices
    from maze.pipeline.viz.unified_overlay import (
        HYBRID_POINT_NAME,
        _decode_attr,
        _open_pipeline_trial_group,
        resolve_ambulation_metrics_group,
        resolve_trial_key_for_hdf5,
    )

    resolved = resolve_video_path(manifest.video_path)
    if resolved is None or not resolved.is_file():
        return None

    n_vid = manifest.video_n_frames
    if n_vid is None or int(n_vid) <= 0:
        cap = cv2.VideoCapture(str(resolved.resolve()))
        if not cap.isOpened():
            return None
        n_vid = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        cap.release()
    if int(n_vid) <= 0:
        return None

    key = TrialKey.from_manifest(manifest)
    try:
        with open_db(pipeline_h5, "r") as h5:
            key = resolve_trial_key_for_hdf5(h5, key)
            g_trial = _open_pipeline_trial_group(h5, key, manifest)
            primary = _decode_attr(g_trial.attrs.get("primary_trajectory", HYBRID_POINT_NAME)) or HYBRID_POINT_NAME
            g_amb = resolve_ambulation_metrics_group(g_trial)
            if g_amb is None:
                return None
            if primary not in g_amb:
                if "spot" not in g_amb:
                    return None
                primary = "spot"
            xy_full = g_amb[primary]["xy"][:]
    except (OSError, KeyError, ValueError):
        return None

    fi_rows = xy_source_frame_indices(xy_full)
    return int(source_frame_exclusive_end(fi_rows, n_vid=int(n_vid)))


def render_overlay_clip_for_match(
    match: PatternMatch,
    *,
    behavior_token: int,
    manifest: TrialManifest,
    manifest_path: Path,
    pipeline_h5: Path,
    results_h5: Path,
    tracking_h5: Path,
    out_path: Path,
    padding_s: float = DEFAULT_PREVIEW_PADDING_S,
    no_ethogram: bool = False,
    no_syllable_tray: bool = False,
) -> Path:
    """Render one clipped unified-overlay MP4 for a bout exemplar."""
    pre_cfg = preprocess_config_for_results_h5(results_h5) or KpmsPreprocessConfig()
    pre_cfg = replace(pre_cfg, db_path=Path(tracking_h5))
    fps = _trial_fps(pipeline_h5, manifest)
    clip_start, clip_end = clip_frames_for_match(match, fps=fps, padding_s=padding_s)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def _extend(cfg: UnifiedOverlayConfig) -> None:
        _sync_kpms_pre_cfg(cfg, pre_cfg)
        _clip_overlay_cfg(
            cfg,
            clip_start=clip_start,
            clip_end=clip_end,
            behavior_token=behavior_token,
            trial_key=match.trial_key,
        )

    ns = _overlay_namespace(
        manifest=manifest,
        manifest_path=manifest_path,
        pipeline_h5=pipeline_h5,
        results_h5=results_h5,
        out_file=out_path,
        pre_cfg=pre_cfg,
        no_ethogram=no_ethogram,
        no_syllable_tray=no_syllable_tray,
    )
    return run_unified_overlay_from_args(ns, extend_cfg=_extend)


def _row_indices_for_clip(
    source_frame_index: np.ndarray,
    clip_start: int,
    clip_end: int,
) -> np.ndarray:
    src = np.asarray(source_frame_index, dtype=np.int64).ravel()
    mask = (src >= int(clip_start)) & (src <= int(clip_end))
    return np.flatnonzero(mask)


def _pose_canvas_from_coords(
    coords: np.ndarray,
    row_indices: np.ndarray,
    *,
    margin_px: int = 40,
) -> tuple[int, int, Callable[[float, float], tuple[int, int]]]:
    """Return canvas size and a mapper from node pixel coords to canvas coords."""
    pts = coords[row_indices].reshape(-1, 2)
    finite = pts[np.isfinite(pts).all(axis=1)]
    if finite.size == 0:
        return 320, 240, lambda x, y: (float(x), float(y))
    xmin, ymin = np.min(finite, axis=0)
    xmax, ymax = np.max(finite, axis=0)
    width = max(160, int(math.ceil(xmax - xmin)) + 2 * margin_px)
    height = max(120, int(math.ceil(ymax - ymin)) + 2 * margin_px)

    def _map(x: float, y: float) -> tuple[int, int]:
        if not (np.isfinite(x) and np.isfinite(y)):
            return -1, -1
        px = int(round(float(x - xmin) + margin_px))
        py = int(round(float(y - ymin) + margin_px))
        return px, py

    return width, height, _map


def render_pose_only_clip_for_match(
    match: PatternMatch,
    *,
    behavior_token: int,
    manifest: TrialManifest,
    pipeline_h5: Path,
    results_h5: Path,
    tracking_h5: Path,
    out_path: Path,
    padding_s: float = DEFAULT_PREVIEW_PADDING_S,
) -> Path:
    """Render a pose-only MP4 on a black canvas when source video is unavailable."""
    import cv2

    pre_cfg = preprocess_config_for_results_h5(results_h5) or KpmsPreprocessConfig()
    pre_cfg = replace(pre_cfg, db_path=Path(tracking_h5))

    aligned = kpms_aligned_coordinates_and_indices(manifest, pre_cfg)
    if aligned is None:
        raise ValueError(f"no aligned coordinates for trial {match.trial_key}")
    _key, coords, source_frame_index = aligned
    fps = _trial_fps(pipeline_h5, manifest)
    clip_start, clip_end = clip_frames_for_match(match, fps=fps, padding_s=padding_s)
    row_indices = _row_indices_for_clip(source_frame_index, clip_start, clip_end)
    if row_indices.size == 0:
        raise ValueError(f"no aligned rows in clip for trial {match.trial_key}")

    width, height, map_pt = _pose_canvas_from_coords(coords, row_indices)
    name_to_index = {name: idx for idx, name in enumerate(STANDARD_NODE_NAMES)}
    edges = [(name_to_index[a], name_to_index[b]) for a, b in SKELETON_EDGES if a in name_to_index and b in name_to_index]

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_path), fourcc, fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"Failed to open VideoWriter: {out_path}")

    label = f"token {behavior_token} | {match.trial_key}"
    for row in row_indices:
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        pts = coords[int(row)]
        for i, j in edges:
            xa, ya = pts[i]
            xb, yb = pts[j]
            if not (np.isfinite(xa) and np.isfinite(ya) and np.isfinite(xb) and np.isfinite(yb)):
                continue
            p0 = map_pt(float(xa), float(ya))
            p1 = map_pt(float(xb), float(yb))
            if p0[0] < 0 or p1[0] < 0:
                continue
            cv2.line(frame, p0, p1, (0, 200, 255), 2, cv2.LINE_AA)
        cv2.putText(
            frame,
            label,
            (8, 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (220, 220, 220),
            1,
            cv2.LINE_AA,
        )
        writer.write(frame)
    writer.release()
    return out_path
