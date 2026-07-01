"""
CLI helpers for :func:`render_unified_overlay_video` (used by ORM and external repos e.g. NOR WIP).

This module is **not** NOR-specific; it only centralizes argparse + config wiring.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from collections.abc import Callable
from pathlib import Path
from typing import Optional

from maze.kpms.apply import KpmsApplyConfig
from maze.kpms.preprocess import KpmsPreprocessConfig
from maze.pipeline.db.trial_key import TrialKey
from maze.pipeline.io.file_discovery import load_manifest_csv

from .overlay_run_config import UnifiedOverlayRunConfig
from .unified_overlay import (
    UnifiedOverlayConfig,
    render_unified_overlay_video,
    resolve_unique_manifest,
)


def is_unified_overlay_available() -> bool:
    """True when OpenCV is installed (required to encode overlay MP4)."""
    try:
        import cv2  # noqa: F401

        return True
    except ImportError:
        return False


def overlay_run_config_to_namespace(cfg: UnifiedOverlayRunConfig) -> argparse.Namespace:
    """Build an argparse namespace with CLI defaults for :func:`run_unified_overlay_from_args`."""
    return argparse.Namespace(
        manifest_csv=cfg.manifest_csv,
        pipeline_h5=cfg.pipeline_h5,
        animal_id=cfg.animal_id,
        session=cfg.session,
        trial=cfg.trial,
        out=cfg.out,
        kpms_h5=cfg.kpms_h5,
        kpms_training_exemplars=cfg.kpms_training_exemplars,
        max_seconds=None,
        contrast=2.0,
        brightness=5.0,
        kpms_px_per_cm=None,
        analysis_only=False,
        history_frames=None,
        no_history_fade=False,
        history_fade_floor=None,
        history_fade_gamma=None,
        no_ethogram=cfg.no_ethogram,
        no_syllable_tray=cfg.no_syllable_tray,
        tray_width=None,
        vertical_exemplar_heading=False,
        bout_center_exemplar_tray=False,
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
        no_skeleton=cfg.no_skeleton,
        no_hud=False,
        no_circular_motor_hud=False,
    )


def run_unified_overlay(cfg: UnifiedOverlayRunConfig) -> Path:
    """Render one unified overlay MP4 from :class:`UnifiedOverlayRunConfig`."""
    return run_unified_overlay_from_args(overlay_run_config_to_namespace(cfg))


def _float_or_none(s: str | None) -> float | None:
    if s is None or str(s).strip() == "":
        return None
    return float(s)


def _apply_layer_opacities(cfg: UnifiedOverlayConfig, args: argparse.Namespace) -> None:
    pairs = (
        ("opacity_trajectory", "trajectory"),
        ("opacity_trail", "trajectory_history"),
        ("opacity_skeleton", "skeleton"),
        ("opacity_arena", "arena_geometry"),
        ("opacity_ethogram", "ethogram"),
        ("opacity_tray", "syllable_tray"),
    )
    for arg_attr, layer_attr in pairs:
        v = getattr(args, arg_attr)
        if v is not None:
            setattr(cfg.layers, layer_attr, float(v))


def build_unified_overlay_parser(
    *,
    manifest_default: Optional[Path] = None,
    pipeline_default: Optional[Path] = None,
    description: str = (
        "Unified overlay: source video + pipeline HDF5 + optional kpMS ethogram and exemplar tray."
    ),
) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=description)

    g_trial = p.add_argument_group("trial", "Which trial to render")
    g_trial.add_argument("--animal-id", required=True, help="Animal id (must match manifest CSV)")
    g_trial.add_argument("--session", required=True, help="Session e.g. S01 (exact CSV match)")
    g_trial.add_argument("--trial", required=True, help="Trial e.g. T01")
    g_trial.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output directory or file path (.mp4); stem gets _unified_overlay suffix",
    )

    g_src = p.add_argument_group("data sources", "Manifest, pipeline DB, optional kpMS outputs")
    g_src.add_argument(
        "--manifest-csv",
        type=Path,
        default=manifest_default,
        required=manifest_default is None,
        help="Trial manifest CSV",
    )
    g_src.add_argument(
        "--pipeline-h5",
        type=Path,
        default=pipeline_default,
        required=pipeline_default is None,
        help="Pipeline results HDF5 (ambulation_metrics / trial attrs)",
    )
    g_src.add_argument(
        "--kpms-h5",
        type=Path,
        default=None,
        help="Per-trial syllable series (e.g. results_apply.h5) for ethogram alignment",
    )
    g_src.add_argument(
        "--kpms-training-exemplars",
        type=Path,
        default=None,
        help=(
            "HDF5 from build_kpms_training_exemplar_table; tray uses these loops "
            "(still pass --kpms-h5 for the ethogram)"
        ),
    )

    g_vid = p.add_argument_group("video", "Frame processing and length")
    g_vid.add_argument("--max-seconds", type=float, default=None, help="Cap output duration")
    g_vid.add_argument("--contrast", type=float, default=2.0, help="cv2.convertScaleAbs alpha")
    g_vid.add_argument("--brightness", type=float, default=5.0, help="cv2.convertScaleAbs beta")
    g_vid.add_argument(
        "--kpms-px-per-cm",
        type=float,
        default=None,
        help="Override KpmsPreprocessConfig.px_per_cm for kpMS alignment",
    )
    g_vid.add_argument(
        "--analysis-only",
        action="store_true",
        help="Start at trial_start_frame (omit pre-trial / iti_wait); default is full clip from frame 0",
    )
    g_vid.add_argument(
        "--history-frames",
        type=int,
        default=None,
        help="Spot trajectory tail length in frames (default 45)",
    )
    g_vid.add_argument(
        "--no-history-fade",
        action="store_true",
        help="Uniform trail brightness (disable age-based fade along the tail)",
    )
    g_vid.add_argument(
        "--history-fade-floor",
        type=float,
        default=None,
        help="Oldest segment brightness scale 0..1 when fading (default ~0.07)",
    )
    g_vid.add_argument(
        "--history-fade-gamma",
        type=float,
        default=None,
        help="Fade curve exponent; >1 keeps more of the tail dim, bright near the head",
    )

    g_kpms = p.add_argument_group(
        "kpMS tray / ethogram",
        "Requires keypoint-moseq (uv sync --extra kpms in ORM env)",
    )
    g_kpms.add_argument("--no-ethogram", action="store_true", help="Disable bottom syllable strip")
    g_kpms.add_argument(
        "--no-syllable-tray",
        action="store_true",
        help="Disable exemplar tray column to the right of the video",
    )
    g_kpms.add_argument(
        "--tray-width",
        type=int,
        default=None,
        help="Pixel width of the right-hand exemplar tray column (default from config)",
    )
    g_kpms.add_argument(
        "--vertical-exemplar-heading",
        action="store_true",
        help="Rotate exemplar so mean nose-to-tail axis points up (kpMS trajectory GIFs do not do this)",
    )
    g_kpms.add_argument(
        "--bout-center-exemplar-tray",
        action="store_true",
        help="Vertically align the exemplar patch with the current syllable bout (default: fixed center)",
    )
    g_kpms.add_argument(
        "--tray-projection",
        type=str,
        default=None,
        choices=("xy", "xz", "yz"),
        help="Projection for 3D kpMS trajectories (default xy)",
    )
    g_kpms.add_argument(
        "--exemplar-min-frequency",
        type=float,
        default=None,
        help="Min global syllable frequency in the recording (0 = keep rare syllables; default 0)",
    )
    g_kpms.add_argument(
        "--exemplar-min-duration",
        type=int,
        default=None,
        help="Min bout length in frames for kpMS instance extraction (default 3)",
    )
    g_kpms.add_argument(
        "--exemplar-neighbors",
        type=int,
        default=None,
        help="kpMS density sampling n_neighbors (only if --exemplar-density-sample)",
    )
    g_kpms.add_argument(
        "--exemplar-density-sample",
        action="store_true",
        help=(
            "Use kpMS density sampling like trajectory GIFs (needs many instances per syllable; "
            "otherwise leave off for single-trial overlays)"
        ),
    )
    g_kpms.add_argument(
        "--exemplar-timesteps",
        type=int,
        default=None,
        help="Rasterized frames per exemplar loop",
    )
    g_kpms.add_argument(
        "--exemplar-arena-coords",
        action="store_true",
        help=(
            "Median exemplar in arena pixels (shows translation; can break pose vs trajectory GIFs)"
        ),
    )

    g_layers = p.add_argument_group(
        "layer opacity",
        "Optional 0..1 blend weights (defaults in UnifiedOverlayConfig.layers)",
    )
    g_layers.add_argument("--opacity-trajectory", type=float, default=None, help="Current dot")
    g_layers.add_argument("--opacity-trail", type=float, default=None, help="Trajectory history")
    g_layers.add_argument("--opacity-skeleton", type=float, default=None)
    g_layers.add_argument("--opacity-arena", type=float, default=None, help="Arena + exit overlay")
    g_layers.add_argument("--opacity-ethogram", type=float, default=None)
    g_layers.add_argument("--opacity-tray", type=float, default=None, help="Exemplar tray patches")

    g_flags = p.add_argument_group("other toggles")
    g_flags.add_argument("--no-skeleton", action="store_true", help="Hide SLEAP skeleton overlay")
    g_flags.add_argument("--no-hud", action="store_true", help="Hide on-frame text HUD")
    g_flags.add_argument(
        "--no-circular-motor-hud",
        action="store_true",
        help="Omit motor feedback on the HUD when ``arena_type`` is circular and no RAM polys",
    )

    return p


def run_unified_overlay_from_args(
    args: argparse.Namespace,
    *,
    extend_cfg: Optional[Callable[[UnifiedOverlayConfig], None]] = None,
    cfg_out: Optional[list[UnifiedOverlayConfig]] = None,
) -> Path:
    """Configure :class:`UnifiedOverlayConfig` from *args* and render; returns output path.

    ``extend_cfg`` can attach e.g. :attr:`UnifiedOverlayConfig.hud_extra_lines_for_frame`
    for downstream wrappers (NOR exploration HUD, etc.).

    When ``cfg_out`` is provided, the configured (and post-render provenance-populated)
  ``UnifiedOverlayConfig`` is appended after rendering.
    """
    manifests = load_manifest_csv(Path(args.manifest_csv))
    manifest = resolve_unique_manifest(manifests, args.animal_id, args.session, args.trial)
    key = TrialKey.from_manifest(manifest)

    pre = KpmsPreprocessConfig()
    if args.kpms_px_per_cm is not None:
        pre = replace(pre, px_per_cm=float(args.kpms_px_per_cm))

    cfg = UnifiedOverlayConfig(
        contrast=float(args.contrast),
        brightness=float(args.brightness),
        max_seconds=_float_or_none(args.max_seconds),
        include_pre_trial_frames=not bool(args.analysis_only),
        kpms_pre=pre,
        kpms_apply=KpmsApplyConfig(),
        kpms_training_exemplar_h5=(
            Path(args.kpms_training_exemplars) if args.kpms_training_exemplars else None
        ),
        show_skeleton=not args.no_skeleton,
        show_ethogram=not args.no_ethogram,
        show_syllable_tray=not args.no_syllable_tray,
        show_hud=not args.no_hud,
        show_circular_motor_hud=not args.no_circular_motor_hud,
        exemplar_vertical_heading=bool(args.vertical_exemplar_heading),
        exemplar_tray_bout_centered=bool(args.bout_center_exemplar_tray),
    )

    _apply_layer_opacities(cfg, args)

    if args.tray_width is not None:
        cfg.syllable_tray_width_px = int(args.tray_width)
    if args.tray_projection is not None:
        cfg.tray_projection_plane = str(args.tray_projection)
    if args.exemplar_min_frequency is not None:
        cfg.exemplar_min_frequency = float(args.exemplar_min_frequency)
    if args.exemplar_min_duration is not None:
        cfg.exemplar_min_duration = int(args.exemplar_min_duration)
    if args.exemplar_neighbors is not None:
        cfg.exemplar_n_neighbors = int(args.exemplar_neighbors)
    if args.exemplar_density_sample:
        cfg.exemplar_density_sample = True
    if args.exemplar_timesteps is not None:
        cfg.exemplar_num_timesteps = int(args.exemplar_timesteps)
    if args.exemplar_arena_coords:
        cfg.exemplar_egocentric = False
    if args.history_frames is not None:
        cfg.trajectory_history_frames = int(args.history_frames)
    if args.no_history_fade:
        cfg.trajectory_history_fade = False
    if args.history_fade_floor is not None:
        cfg.trajectory_history_fade_floor = float(args.history_fade_floor)
    if args.history_fade_gamma is not None:
        cfg.trajectory_history_fade_gamma = float(args.history_fade_gamma)

    if extend_cfg is not None:
        extend_cfg(cfg)

    out = render_unified_overlay_video(
        manifest=manifest,
        pipeline_db=Path(args.pipeline_h5),
        key=key,
        out_path=Path(args.out),
        kpms_results_h5=Path(args.kpms_h5) if args.kpms_h5 else None,
        cfg=cfg,
    )
    if cfg_out is not None:
        cfg_out.append(cfg)
    return out


def main_cli(
    argv: list[str] | None = None,
    *,
    manifest_default: Optional[Path] = None,
    pipeline_default: Optional[Path] = None,
    description: Optional[str] = None,
) -> int:
    """Entry point for ``python -m`` style wrappers."""
    desc = description or (
        "Unified overlay: source video + pipeline HDF5 + optional kpMS ethogram and exemplar tray."
    )
    p = build_unified_overlay_parser(
        manifest_default=manifest_default,
        pipeline_default=pipeline_default,
        description=desc,
    )
    args = p.parse_args(argv)
    try:
        out = run_unified_overlay_from_args(args)
    except Exception as e:
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        return 1
    print(f"Wrote {out}")
    return 0
