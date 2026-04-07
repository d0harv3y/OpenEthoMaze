"""
Render unified trial overlay video (manifest + pipeline H5 + optional kpMS).

Session strings must match the manifest CSV exactly (e.g. ``S01`` not ``1``).

Example::

    uv run python scripts/render_trial_overlay.py ^
      --manifest-csv outputs/legacy/trial_manifest_legacy.csv ^
      --pipeline-h5 outputs/legacy/vast_results_legacy.h5 ^
      --animal-id 1 --session S01 --trial T01 ^
      --out outputs/overlays ^
      --kpms-h5 "D:/work sack/.../results_apply.h5"

Requires ``uv sync --extra kpms`` for the hypnogram and exemplar tray.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

# Repo root (parent of scripts/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from maze.kpms.apply import KpmsApplyConfig
from maze.kpms.preprocess import KpmsPreprocessConfig
from maze.pipeline.db.trial_key import TrialKey
from maze.pipeline.io.file_discovery import load_manifest_csv
from maze.pipeline.viz.unified_overlay import (
    UnifiedOverlayConfig,
    render_unified_overlay_video,
    resolve_unique_manifest,
)

_DEFAULT_MANIFEST = _PROJECT_ROOT / "outputs" / "legacy" / "trial_manifest_legacy.csv"
_DEFAULT_PIPELINE = _PROJECT_ROOT / "outputs" / "legacy" / "vast_results_legacy.h5"


def _float_or_none(s: str | None) -> float | None:
    if s is None or str(s).strip() == "":
        return None
    return float(s)


def _apply_layer_opacities(cfg: UnifiedOverlayConfig, args: argparse.Namespace) -> None:
    """Apply optional 0..1 opacity overrides from CLI onto ``cfg.layers``."""
    pairs = (
        ("opacity_trajectory", "trajectory"),
        ("opacity_trail", "trajectory_history"),
        ("opacity_skeleton", "skeleton"),
        ("opacity_arena", "arena_geometry"),
        ("opacity_hypnogram", "hypnogram"),
        ("opacity_tray", "syllable_tray"),
    )
    for arg_attr, layer_attr in pairs:
        v = getattr(args, arg_attr)
        if v is not None:
            setattr(cfg.layers, layer_attr, float(v))


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Unified ORM overlay: source video + pipeline HDF5 + optional kpMS hypnogram "
            "and exemplar tray."
        ),
    )

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
        default=_DEFAULT_MANIFEST,
        help=f"Trial manifest CSV (default: {_DEFAULT_MANIFEST})",
    )
    g_src.add_argument(
        "--pipeline-h5",
        type=Path,
        default=_DEFAULT_PIPELINE,
        help=f"Pipeline results HDF5 (default: {_DEFAULT_PIPELINE})",
    )
    g_src.add_argument(
        "--kpms-h5",
        type=Path,
        default=None,
        help="Per-trial syllable series (e.g. results_apply.h5) for hypnogram alignment",
    )
    g_src.add_argument(
        "--kpms-training-exemplars",
        type=Path,
        default=None,
        help=(
            "HDF5 from scripts/build_kpms_training_exemplar_table.py; tray uses these loops "
            "for every trial (still pass --kpms-h5 for the hypnogram)"
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

    g_kpms = p.add_argument_group(
        "kpMS tray / hypnogram",
        "Requires keypoint-moseq (uv sync --extra kpms)",
    )
    g_kpms.add_argument(
        "--no-hypnogram",
        action="store_true",
        help="Disable bottom syllable strip",
    )
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
        "--no-vertical-exemplar-heading",
        action="store_true",
        help="Do not rotate exemplars so nose→tail points up (use raw projection orientation)",
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
        help="get_typical_trajectories min_frequency when building per-trial tray",
    )
    g_kpms.add_argument(
        "--exemplar-neighbors",
        type=int,
        default=None,
        help="kpMS density sampling n_neighbors",
    )
    g_kpms.add_argument(
        "--exemplar-timesteps",
        type=int,
        default=None,
        help="Rasterized frames per exemplar loop",
    )
    g_kpms.add_argument(
        "--exemplar-egocentric",
        action="store_true",
        help=(
            "Use kpMS body-centered typical trajectories (pulses in place); default is arena coords"
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
    g_layers.add_argument("--opacity-hypnogram", type=float, default=None)
    g_layers.add_argument("--opacity-tray", type=float, default=None, help="Exemplar tray patches")

    g_flags = p.add_argument_group("other toggles")
    g_flags.add_argument("--no-skeleton", action="store_true", help="Hide SLEAP skeleton overlay")
    g_flags.add_argument("--no-hud", action="store_true", help="Hide on-frame text HUD")

    return p


def main() -> int:
    args = _build_parser().parse_args()

    manifests = load_manifest_csv(Path(args.manifest_csv))
    manifest = resolve_unique_manifest(manifests, args.animal_id, args.session, args.trial)
    key = TrialKey(
        animal_id=str(args.animal_id),
        session=str(args.session),
        trial=str(args.trial),
    )

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
        show_hypnogram=not args.no_hypnogram,
        show_syllable_tray=not args.no_syllable_tray,
        show_hud=not args.no_hud,
        exemplar_vertical_heading=not args.no_vertical_exemplar_heading,
        exemplar_tray_bout_centered=bool(args.bout_center_exemplar_tray),
    )

    _apply_layer_opacities(cfg, args)

    if args.tray_width is not None:
        cfg.syllable_tray_width_px = int(args.tray_width)
    if args.tray_projection is not None:
        cfg.tray_projection_plane = str(args.tray_projection)
    if args.exemplar_min_frequency is not None:
        cfg.exemplar_min_frequency = float(args.exemplar_min_frequency)
    if args.exemplar_neighbors is not None:
        cfg.exemplar_n_neighbors = int(args.exemplar_neighbors)
    if args.exemplar_timesteps is not None:
        cfg.exemplar_num_timesteps = int(args.exemplar_timesteps)
    if args.exemplar_egocentric:
        cfg.exemplar_egocentric = True

    written = render_unified_overlay_video(
        manifest=manifest,
        pipeline_db=Path(args.pipeline_h5),
        key=key,
        out_path=Path(args.out),
        kpms_results_h5=Path(args.kpms_h5) if args.kpms_h5 else None,
        cfg=cfg,
    )
    print(f"Wrote {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
