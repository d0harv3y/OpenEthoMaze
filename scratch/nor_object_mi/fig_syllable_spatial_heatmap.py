"""Render spatial time-in-syllable heatmaps (QC-style) per phase × condition × sex × tx.

Regen (OpenEthoMaze repo root; needs opencv + videos on disk):

  uv run python scratch/nor_object_mi/fig_syllable_spatial_heatmap.py --batch nvl_obj M --phases NOR_BL
  uv run python scratch/nor_object_mi/fig_syllable_spatial_heatmap.py --grain NOR_BL nvl_obj M noSD
  uv run python scratch/nor_object_mi/fig_syllable_spatial_heatmap.py --all --cluster-id 13
  uv run python scratch/nor_object_mi/fig_syllable_spatial_heatmap.py --all --cluster-id 13 --overlay-tx
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.syllable_spatial_heatmap import (  # noqa: E402
    DEFAULT_BLUR_SIGMA,
    DEFAULT_FRAME_STRIDE,
    GrainKey,
    TxOverlayGrainKey,
    all_grains,
    all_tx_overlay_grains,
    batch_grains,
    batch_tx_overlay_grains,
    run_grain,
    run_tx_overlay_grain,
    write_shared_cluster_legend,
    write_tx_legend,
)

DEFAULT_NOR = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\my_NOR_results.h5")
DEFAULT_ENSEMBLE = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017")
DEFAULT_SIG = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_syllable_signatures\syllable_prototypes_clustered.csv"
)
DEFAULT_VIDEO = Path(r"C:\Users\admin\Documents\work\sack\datas\impress")
DEFAULT_OUT = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\syllable_spatial_heatmaps"
)
DEFAULT_OUT_CLUSTER13 = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\syllable_spatial_heatmaps_cluster13"
)
DEFAULT_OUT_CLUSTER13_TX = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\syllable_spatial_heatmaps_cluster13_tx_overlay"
)
LEGEND_STEM = "fig_syllable_spatial_cluster_legend"
TX_LEGEND_STEM = "fig_syllable_spatial_tx_legend"


def _info_md(*, keep_clusters: list[int] | None, overlay_tx: bool) -> str:
    dwell_extra = ""
    if keep_clusters is not None:
        dwell_extra = (
            f"\n\n**Filter:** only HDBSCAN `cluster_id` in {keep_clusters} "
            "(other syllables omitted, not remapped to noise)."
        )
    tx_extra = ""
    if overlay_tx:
        tx_extra = (
            "\n\n**Tx overlay:** all three treatments pooled per grain; color = tx "
            "(`noSD` green, `GHSD` orange, `RBSD` purple — same as violin plots)."
        )
    grain_line = (
        "animal sessions pooled within **session × trial × sex** "
        "(all tx overlaid)."
        if overlay_tx
        else "animal sessions pooled within **session × trial × sex × tx**."
    )
    legend_line = (
        f"Single shared ``{TX_LEGEND_STEM}.png`` (tx swatches)."
        if overlay_tx
        else f"Single shared ``{LEGEND_STEM}.png`` (cluster_id swatches)."
    )
    return f"""# INFO — syllable spatial heatmaps (time-in-syllable)

**D (descriptive)** arena maps of where syllable time accumulates, QC trial-heatmap style.

## Grain

{grain_line}

## Background

Blank black canvas (no median video). Arena AABB outline from mean
``objects/arena/bbox`` (scaled to canvas). Novel-object trials with fam on the
right (``nvl_nearest_hist_locus=a``) are rotated 180° so **fam is always on the
left**. Upper-left notation: ``rot180: n/N`` (sessions flipped / grain n).

## Dwell overlay

Per pixel: **weighted mean color** from blurred dwell seconds (layers mix
instead of sequential alpha wash-out). Opacity ∝ total dwell. All kpMS models overlaid.
{dwell_extra}{tx_extra}

## Loci

Circles at mean aligned locus positions; labels by condition: **fam/nvl**,
**id_0/id_1**, **no_0/no_1** (hist locus 0 = lower-x left, 1 = right; no rot180
except novel fam-left).

## Legend

{legend_line}

## Not

Not portable ``raw_syllable_id``. Not DA / MI. Models overlaid — mass scales with model count.
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--nor-h5", type=Path, default=DEFAULT_NOR)
    ap.add_argument("--ensemble-root", type=Path, default=DEFAULT_ENSEMBLE)
    ap.add_argument("--prototypes-csv", type=Path, default=DEFAULT_SIG)
    ap.add_argument("--video-root", type=Path, default=DEFAULT_VIDEO)
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output folder (defaults depend on --cluster-id / --overlay-condition)",
    )
    ap.add_argument("--model", action="append", default=None, help="Limit to model(s)")
    ap.add_argument(
        "--grain",
        nargs=4,
        metavar=("PHASE", "COND", "SEX", "TX"),
        default=None,
        help="Single per-tx grain (ignored when --overlay-condition)",
    )
    ap.add_argument(
        "--batch",
        nargs=2,
        metavar=("COND", "SEX"),
        default=None,
        help="All phases × all tx for one condition × sex (use --phases to restrict)",
    )
    ap.add_argument(
        "--phases",
        nargs="+",
        default=None,
        help="Restrict batch to phase(s), e.g. NOR_BL",
    )
    ap.add_argument("--all", action="store_true", help="Full phase × condition × sex × tx grid")
    ap.add_argument(
        "--cluster-id",
        type=int,
        nargs="+",
        default=None,
        help="Keep only these HDBSCAN cluster_id(s) in the dwell overlay",
    )
    ap.add_argument(
        "--overlay-tx",
        action="store_true",
        help="Pool all tx in one image; color by treatment (requires --cluster-id)",
    )
    ap.add_argument("--frame-stride", type=int, default=DEFAULT_FRAME_STRIDE)
    ap.add_argument("--bg-frame-stride", type=int, default=None)
    ap.add_argument("--blur-sigma", type=float, default=DEFAULT_BLUR_SIGMA)
    ap.add_argument("--vmax-s", type=float, default=None)
    ap.add_argument("--max-sessions", type=int, default=None, help="Debug cap per grain")
    args = ap.parse_args(argv)

    if args.overlay_tx and not args.cluster_id:
        ap.error("--overlay-tx requires --cluster-id")

    keep = frozenset(int(c) for c in args.cluster_id) if args.cluster_id else None
    if args.out_dir is not None:
        out = Path(args.out_dir)
    elif args.overlay_tx and keep == frozenset({13}):
        out = DEFAULT_OUT_CLUSTER13_TX
    elif keep == frozenset({13}):
        out = DEFAULT_OUT_CLUSTER13
    else:
        out = DEFAULT_OUT

    out.mkdir(parents=True, exist_ok=True)
    keep_list = sorted(keep) if keep is not None else None
    (out / "INFO_syllable_spatial_heatmaps.md").write_text(
        _info_md(keep_clusters=keep_list, overlay_tx=args.overlay_tx), encoding="utf-8"
    )

    phase_filter = tuple(args.phases) if args.phases else None
    if args.overlay_tx:
        if args.all:
            grains: list[TxOverlayGrainKey] = all_tx_overlay_grains()
        elif args.batch:
            grains = batch_tx_overlay_grains(args.batch[0], args.batch[1], phases=phase_filter)
        elif args.grain:
            grains = [
                TxOverlayGrainKey(args.grain[0], args.grain[1], args.grain[2])
            ]
        else:
            ap.error("pass --grain PHASE COND SEX, --batch COND SEX, or --all with --overlay-tx")
    elif args.all:
        grains = all_grains()
    elif args.batch:
        grains = batch_grains(args.batch[0], args.batch[1], phases=phase_filter)
    elif args.grain:
        grains = [GrainKey(args.grain[0], args.grain[1], args.grain[2], args.grain[3])]
    else:
        ap.error("pass --grain PHASE COND SEX TX, --batch COND SEX, or --all")

    models = args.model
    summaries = []
    legend_ids: list[int] | list[str] = []
    legend_colors: dict[object, tuple[int, int, int]] = {}
    for i, g in enumerate(grains, 1):
        print(f"[{i}/{len(grains)}] {g.slug()}", flush=True)
        if args.overlay_tx:
            summary, cids, colors = run_tx_overlay_grain(
                g,
                nor_h5_path=args.nor_h5,
                ensemble_root=args.ensemble_root,
                prototypes_csv=args.prototypes_csv,
                video_root=args.video_root,
                out_dir=out,
                models=models,
                frame_stride=int(args.frame_stride),
                bg_frame_stride=args.bg_frame_stride,
                blur_sigma=float(args.blur_sigma),
                vmax_s=args.vmax_s,
                max_sessions=args.max_sessions,
                keep_clusters=keep,
            )
        else:
            summary, cids, colors = run_grain(
                g,
                nor_h5_path=args.nor_h5,
                ensemble_root=args.ensemble_root,
                prototypes_csv=args.prototypes_csv,
                video_root=args.video_root,
                out_dir=out,
                models=models,
                frame_stride=int(args.frame_stride),
                bg_frame_stride=args.bg_frame_stride,
                blur_sigma=float(args.blur_sigma),
                vmax_s=args.vmax_s,
                max_sessions=args.max_sessions,
                keep_clusters=keep,
            )
        summaries.append(summary)
        if cids and not legend_ids:
            legend_ids = cids
            legend_colors = colors

    if legend_ids:
        if args.overlay_tx:
            legend_path = out / f"{TX_LEGEND_STEM}.png"
            write_tx_legend(legend_path)
        else:
            legend_path = out / f"{LEGEND_STEM}.png"
            write_shared_cluster_legend(
                legend_path,
                legend_ids,  # type: ignore[arg-type]
                legend_colors,  # type: ignore[arg-type]
                include_noise=keep is None,
            )
        print(f"wrote shared legend {legend_path}", flush=True)

    print(f"done {len(summaries)} grains -> {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
