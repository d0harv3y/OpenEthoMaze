"""Slides pack: Kruskal-by-tx DR heatmaps (classic vs object-prox).

Reads only CSVs in `_nor_object_mi/slides_pack/` (sliced copies of sibling
run tables). Dest default is slides.

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/fig_slides_pack.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi._pub_style import (  # noqa: E402
    FIGSIZE_DOUBLE,
    INK,
    PHASE_SHORT,
    PHASES,
    SEX_ORDER,
    apply_style,
    fig_footnote,
    save_pdf_svg,
    text_on_cmap,
    type_scale,
)

DEFAULT_PACK = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\slides_pack"
)
NLP_VMAX = 4.0
SEX_LAB = {"F": "Female", "M": "Male"}

FOOT_CLASSIC = (
    "Grain: animal × phase × novel_obj. Kruskal–Wallis on classic investigation "
    "DR by tx, within sex. Color is −log₁₀(p), clipped at 4 for display (not a "
    "new hit rule). Hit is uncorrected p < 0.05. Not Wilcoxon vs 0; not DA; "
    "not FDR across cells. Source slice: kruskal_classic_dr.csv."
)
FOOT_PROX = (
    "Grain: animal × phase × novel_obj. Kruskal–Wallis on exclusive object-prox "
    "DR (spot occupancy, animal median across 21 kpMS models) by tx, within sex. "
    "Color is −log₁₀(p), clipped at 4 for display. Hit is uncorrected p < 0.05. "
    "Not Wilcoxon vs 0; not DA; ids are not portable. Source slice: "
    "kruskal_object_prox_dr.csv."
)


def _neglog10_p(p: float) -> float:
    if not np.isfinite(p) or p < 0:
        return float("nan")
    if p == 0.0:
        return NLP_VMAX
    return float(min(NLP_VMAX, max(0.0, -np.log10(p))))


def _p_cell_text(p: float) -> str:
    if not np.isfinite(p):
        return ""
    if p < 1e-4:
        return "<10⁻⁴"
    if p < 0.001:
        return f"{p:.1e}"
    return f"{p:.3f}"


def _heatmap(
    tests: pd.DataFrame,
    out: Path,
    *,
    dest: str,
    title: str,
    footnote: str,
    stem: str,
) -> None:
    ts = type_scale(dest)
    apply_style(dest=dest)
    fig, axes = plt.subplots(1, 2, figsize=FIGSIZE_DOUBLE, constrained_layout=True)
    im = None
    for ax, sex, letter in zip(axes, SEX_ORDER, ("A", "B")):
        sub = tests[tests["sex"] == sex]
        pmat = np.full((len(PHASES), 1), np.nan)
        nmat = np.full((len(PHASES), 1), np.nan)
        for i, ph in enumerate(PHASES):
            cell = sub[sub["phase_layer"] == ph]
            if len(cell) == 1:
                pmat[i, 0] = float(cell["p"].iloc[0])
                nmat[i, 0] = float(cell["n"].iloc[0])
        nlp = np.vectorize(_neglog10_p, otypes=[float])(pmat)
        im = ax.imshow(nlp, cmap="viridis", vmin=0.0, vmax=NLP_VMAX, aspect="auto")
        ax.set_xticks([0])
        ax.set_xticklabels(["DR"])
        ax.set_yticks(range(len(PHASES)))
        ax.set_yticklabels([PHASE_SHORT[p] for p in PHASES])
        ax.set_title(f"{letter}  {SEX_LAB[sex]}", loc="left", fontweight="bold", color=INK)
        for i in range(pmat.shape[0]):
            p = pmat[i, 0]
            nlp_v = nlp[i, 0]
            n = nmat[i, 0]
            if not (np.isfinite(p) and np.isfinite(nlp_v)):
                continue
            n_txt = f"n={int(n)}" if np.isfinite(n) else ""
            ax.text(
                0,
                i,
                f"{_p_cell_text(p)}\n{n_txt}",
                ha="center",
                va="center",
                fontsize=ts["cell"],
                color=text_on_cmap(nlp_v, vmin=0.0, vmax=NLP_VMAX),
                linespacing=1.15,
            )
    fig.colorbar(im, ax=axes, fraction=0.04, pad=0.03, label="−log₁₀(p)")
    fig.suptitle(title, fontsize=ts["suptitle"], fontweight="bold", color=INK, y=1.06)
    fig_footnote(fig, footnote, y=-0.10)
    save_pdf_svg(fig, out / stem)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pack-dir", type=Path, default=DEFAULT_PACK)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    args = ap.parse_args(argv)
    pack = args.pack_dir
    out = args.out_dir or (pack / "figures")
    classic = pd.read_csv(pack / "kruskal_classic_dr.csv")
    prox = pd.read_csv(pack / "kruskal_object_prox_dr.csv")
    _heatmap(
        classic,
        out,
        dest=args.dest,
        title="Classic investigation DR: Kruskal by tx, within sex",
        footnote=FOOT_CLASSIC,
        stem="fig_dr_kruskal_classic",
    )
    _heatmap(
        prox,
        out,
        dest=args.dest,
        title="Object-prox occupancy DR (kpMS clock): Kruskal by tx, within sex",
        footnote=FOOT_PROX,
        stem="fig_dr_kruskal_object_prox",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
