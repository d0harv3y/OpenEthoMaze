"""Four-phase Pearson block heatmap of two session segmenters.

Litmus: kinematics 2×2 (syllable vs movement frame-weighted mean speed).
Reads CSVs from simpler_first_segmenter_pearson.

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/fig_simpler_first_segmenter_pearson.py --dest slides
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi._pub_style import (  # noqa: E402
    INK,
    apply_style,
    fig_footnote,
    save_pdf_svg,
    text_on_cmap,
    type_scale,
)
from nor_object_mi.segmenter_pearson import (  # noqa: E402
    FEATURES,
    FEATURE_LABELS,
    LITMUS_A,
    LITMUS_B,
    block_edges,
)
from nor_object_mi.simpler_first_protocol_prologue import PHASES  # noqa: E402

DEFAULT_RUN = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_segmenter_pearson"
)
PHASE_SHORT = {
    "NOR_BL": "BL",
    "NOR_TX": "TX",
    "NOR_REC3hr": "REC3",
    "NOR_REC11hr": "REC11",
}
FOOT = (
    "Grain: animal × phase × novel_obj (locked ss-50). Pearson r of session "
    "summaries (not lagged CCF). Blocks: locomotor partition, syllable partition, "
    "interval join, kinematics. Black box = speed litmus (syllable-bout vs "
    "movement-bout frame-weighted mean m/s). Diagonal is self-correlation. "
    "Uncorrected. Heatmap is descriptive. Not n_move vs n_syll as paired events; "
    "not heading; not DA."
)


def _r_matrix(long: pd.DataFrame, phase: str) -> np.ndarray:
    sub = long[long["phase_layer"] == phase]
    k = len(FEATURES)
    mat = np.full((k, k), np.nan)
    idx = {f: i for i, f in enumerate(FEATURES)}
    for rec in sub.itertuples(index=False):
        i = idx[str(rec.feature_i)]
        j = idx[str(rec.feature_j)]
        mat[i, j] = float(rec.pearson_r)
    return mat


def fig_phase_heatmaps(long: pd.DataFrame, stem: Path, *, dest: str) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    fig, axes = plt.subplots(2, 2, figsize=(12.8, 12.2), constrained_layout=True)
    labels = [FEATURE_LABELS[f] for f in FEATURES]
    k = len(FEATURES)
    ia = FEATURES.index(LITMUS_A)
    ib = FEATURES.index(LITMUS_B)
    im = None
    for i, ph in enumerate(PHASES):
        ax = axes[i // 2][i % 2]
        mat = _r_matrix(long, ph)
        im = ax.imshow(mat, cmap="RdBu_r", vmin=-1.0, vmax=1.0, origin="upper")
        ax.set_xticks(range(k))
        ax.set_yticks(range(k))
        ax.set_xticklabels(labels, rotation=70, ha="right", fontsize=ts["cell"])
        ax.set_yticklabels(labels, fontsize=ts["cell"])
        ax.set_title(PHASE_SHORT.get(ph, ph), loc="left", fontweight="bold", color=INK)
        for e in block_edges():
            ax.axhline(e, color=INK, lw=0.8, zorder=4)
            ax.axvline(e, color=INK, lw=0.8, zorder=4)
        lo = min(ia, ib) - 0.5
        side = abs(ia - ib) + 1
        ax.add_patch(
            Rectangle(
                (lo, lo),
                side,
                side,
                fill=False,
                edgecolor=INK,
                lw=1.6,
                zorder=5,
            )
        )
        for yi in range(k):
            for xi in range(k):
                v = mat[yi, xi]
                if not np.isfinite(v):
                    continue
                ax.text(
                    xi,
                    yi,
                    f"{v:.2f}",
                    ha="center",
                    va="center",
                    fontsize=max(5.0, ts["cell"] - 3.5),
                    color=text_on_cmap(v, cmap="RdBu_r", vmin=-1.0, vmax=1.0),
                )
        n = int(long.loc[long["phase_layer"] == ph, "n"].median())
        ax.text(
            0.0,
            1.02,
            f"n={n}",
            transform=ax.transAxes,
            ha="left",
            va="bottom",
            fontsize=ts["annotation"],
            color=INK,
        )
    if im is not None:
        fig.colorbar(im, ax=axes, fraction=0.03, pad=0.02, label="Pearson r")
    fig.suptitle(
        "Two segmenters, one timeline: Pearson of session summaries",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_footnote(fig, FOOT, y=-0.04)
    save_pdf_svg(fig, stem)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    args = ap.parse_args(argv)
    long = pd.read_csv(args.run_dir / "pearson_long.csv")
    fig_phase_heatmaps(
        long,
        args.run_dir / f"fig_segmenter_pearson_{args.dest}",
        dest=args.dest,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
