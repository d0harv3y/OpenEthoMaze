"""Strip B: cluster-13 pause syllable Δp by tx, one panel per phase × step.

Violins + salt (across-model IQR whiskers). Companion heatmaps: Kruskal within sex.
BH family = 24 cells (3 steps × 4 phases × 2 sexes: presence / novelty / span).

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/fig_cluster13_tx_delta.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi._pub_style import (  # noqa: E402
    FIGSIZE_SLIDES,
    INK,
    MUTE,
    PHASE_SHORT,
    PHASES,
    SEX_MARKER,
    SEX_ORDER,
    TX_COLOR,
    TX_ORDER,
    apply_style,
    fig_footnote,
    save_pdf_png,
    text_on_cmap,
    tx_sex_legend_handles,
    type_scale,
)
from nor_object_mi.cluster13_tx_delta import (  # noqa: E402
    STEPS,
    STEP_LAB,
    animal_median_delta_p,
    filter_mapped_deltas,
    kruskal_by_phase_step_sex,
)

DEFAULT_DA = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_da"
)
DELTA_USECOLS = (
    "model",
    "animal_id",
    "sex",
    "tx",
    "step",
    "phase_layer",
    "raw_syllable_id",
    "delta_p",
)
NLP_VMAX = 4.0


def _info_md() -> str:
    return """# INFO — cluster-13 Δp by tx × phase

Strip B: treatment contrast on paired share change of the pause syllable
(duration-band / `cluster_id` 13; ids mapped per model).

## Grain

One point = one **animal** × phase × step. Value = **median** `delta_p` across
kpMS models, each using that model's mapped `raw_syllable_id`. Whiskers =
±½ **IQR of that animal's Δp across models** (salt), not SEM.

Kruskal–Wallis: those animal values ~ tx, **within sex**. BH family = 24 cells
(3 steps × 4 phases × 2 sexes: presence / novelty / span). Pre-specified syllable — not BH over the alphabet.

## Inputs

| File | Role |
|------|------|
| `duration_band_vs_da.csv` | mapped id per model |
| `da_syllable_deltas_per_animal.csv` | animal Δp |

## Not

Not Wilcoxon vs 0 (pooled DA). Not kinematics. Not occupancy clocks (strip A).
"""


def _p_cell_text(p: float) -> str:
    if not np.isfinite(p):
        return ""
    if p < 1e-4:
        return "<10⁻⁴"
    if p < 0.001:
        return f"{p:.1e}"
    return f"{p:.3f}"


def _neglog10_p(p: float) -> float:
    if not np.isfinite(p) or p <= 0:
        return float("nan")
    return float(min(NLP_VMAX, max(0.0, -np.log10(p))))


def _draw_tx_violins(
    ax,
    panel: pd.DataFrame,
    ycol: str,
    rng: np.random.Generator,
    *,
    dest: str,
    iqr_col: str | None = None,
    xlabel: bool = False,
) -> None:
    """Violin KDE by tx + salt whiskers (±½ across-model IQR)."""
    ts = type_scale(dest)
    positions = list(range(len(TX_ORDER)))
    bodies: list[np.ndarray] = []
    body_pos: list[int] = []
    body_color: list[str] = []
    for i, t in enumerate(TX_ORDER):
        sub = panel[panel["tx"] == t]
        y = sub[ycol].to_numpy(dtype=float)
        sex = sub["sex"].to_numpy()
        iqr = (
            sub[iqr_col].to_numpy(dtype=float)
            if iqr_col is not None and iqr_col in sub.columns
            else np.full(y.shape, np.nan)
        )
        finite = np.isfinite(y)
        y, sex, iqr = y[finite], sex[finite], iqr[finite]
        if y.size >= 2 and np.unique(y).size >= 2:
            bodies.append(y)
            body_pos.append(i)
            body_color.append(TX_COLOR[t])
        if y.size:
            x = np.full(y.shape, float(i)) + rng.normal(0.0, 0.055, size=y.size)
            half = np.where(np.isfinite(iqr), 0.5 * iqr, np.nan)
            for s in SEX_ORDER:
                m = sex == s
                if not np.any(m):
                    continue
                if np.any(np.isfinite(half[m])):
                    ax.errorbar(
                        x[m],
                        y[m],
                        yerr=np.where(np.isfinite(half[m]), half[m], 0.0),
                        fmt="none",
                        ecolor=TX_COLOR[t],
                        elinewidth=0.7,
                        capsize=0,
                        alpha=0.35,
                        zorder=2,
                    )
                ax.scatter(
                    x[m],
                    y[m],
                    s=ts["violin_scatter"],
                    c=TX_COLOR[t],
                    marker=SEX_MARKER[s],
                    alpha=0.75,
                    edgecolors="none",
                    zorder=3,
                )
            ax.plot(
                [i - 0.22, i + 0.22],
                [float(np.median(y))] * 2,
                color=INK,
                lw=1.5,
                zorder=4,
            )
    if bodies:
        parts = ax.violinplot(
            bodies,
            positions=body_pos,
            widths=0.78,
            showmeans=False,
            showmedians=False,
            showextrema=False,
        )
        for pc, col in zip(parts["bodies"], body_color):
            pc.set_facecolor(col)
            pc.set_edgecolor("none")
            pc.set_alpha(0.32)
            pc.set_zorder(1)
    ax.axhline(0.0, color="#bbbbbb", lw=0.8, ls="--", zorder=0)
    ax.set_xticks(positions)
    ax.set_xlim(-0.7, len(TX_ORDER) - 0.3)
    if xlabel:
        ax.set_xticklabels(list(TX_ORDER), fontsize=ts["annotation"], rotation=35, ha="right")
    else:
        ax.set_xticklabels([])


def _p_mat_sex(kr: pd.DataFrame, sex: str) -> np.ndarray:
    """Rows = steps, cols = phases."""
    mat = np.full((len(STEPS), len(PHASES)), np.nan)
    sub = kr[kr["sex"] == sex]
    for i, step in enumerate(STEPS):
        for j, ph in enumerate(PHASES):
            cell = sub[(sub["step"] == step) & (sub["phase_layer"] == ph)]
            if len(cell) == 1:
                mat[i, j] = float(cell["p"].iloc[0])
    return mat


def _q_hit_mat(kr: pd.DataFrame, sex: str) -> np.ndarray:
    mat = np.zeros((len(STEPS), len(PHASES)), dtype=bool)
    sub = kr[kr["sex"] == sex]
    for i, step in enumerate(STEPS):
        for j, ph in enumerate(PHASES):
            cell = sub[(sub["step"] == step) & (sub["phase_layer"] == ph)]
            if len(cell) == 1:
                mat[i, j] = bool(cell["hit_fdr05"].iloc[0])
    return mat


def _imshow_kruskal(ax, pmat: np.ndarray, hits: np.ndarray, *, title: str, ts: dict) -> object:
    nlp = np.vectorize(_neglog10_p, otypes=[float])(pmat)
    im = ax.imshow(nlp, cmap="viridis", vmin=0.0, vmax=NLP_VMAX, aspect="auto")
    ax.set_xticks(range(len(PHASES)))
    ax.set_xticklabels([PHASE_SHORT[p] for p in PHASES], fontsize=ts["annotation"])
    ax.set_yticks(range(len(STEPS)))
    ax.set_yticklabels([STEP_LAB[s] for s in STEPS], fontsize=ts["annotation"])
    ax.set_title(title, loc="left", fontweight="bold", color=INK)
    for i in range(pmat.shape[0]):
        for j in range(pmat.shape[1]):
            p = pmat[i, j]
            nlp_v = nlp[i, j]
            if not np.isfinite(p) or not np.isfinite(nlp_v):
                continue
            mark = "*" if hits[i, j] else ""
            ax.text(
                j,
                i,
                mark + _p_cell_text(p),
                ha="center",
                va="center",
                fontsize=ts["cell"],
                color=text_on_cmap(nlp_v, vmin=0.0, vmax=NLP_VMAX),
            )
    return im


def fig_strip_b(med: pd.DataFrame, kr: pd.DataFrame, out: Path, *, dest: str) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    n_steps = len(STEPS)
    fig_w, fig_h = FIGSIZE_SLIDES if dest == "slides" else (7.2, 6.8)
    fig_h += 1.15 * (n_steps - 2)  # taller when span row added
    fig = plt.figure(figsize=(fig_w, fig_h + (1.8 if dest == "slides" else 1.4)))
    gs = fig.add_gridspec(
        n_steps + 1,
        4,
        left=0.08,
        right=0.98,
        top=0.90,
        bottom=0.14,
        height_ratios=[1.15] * n_steps + [0.95],
        hspace=0.42,
        wspace=0.28,
    )
    rng = np.random.default_rng(0)
    violin_axes = []
    for i, step in enumerate(STEPS):
        for j, phase in enumerate(PHASES):
            ax = fig.add_subplot(gs[i, j], sharey=violin_axes[0] if violin_axes else None)
            violin_axes.append(ax)
            panel = med[(med["phase_layer"] == phase) & (med["step"] == step)]
            _draw_tx_violins(
                ax,
                panel,
                "delta_p",
                rng,
                dest=dest,
                iqr_col="iqr_across_models",
                xlabel=(i == n_steps - 1),
            )
            if i == 0:
                ax.set_title(PHASE_SHORT[phase], loc="left", fontweight="bold", color=INK)
            if j == 0:
                ax.set_ylabel(f"{STEP_LAB[step]}\nΔp")
    ax_f = fig.add_subplot(gs[n_steps, 0:2])
    ax_m = fig.add_subplot(gs[n_steps, 2:4])
    im = None
    for ax, sex in ((ax_f, "F"), (ax_m, "M")):
        im = _imshow_kruskal(
            ax,
            _p_mat_sex(kr, sex),
            _q_hit_mat(kr, sex),
            title=f"Kruskal · {sex}",
            ts=ts,
        )
    cax = fig.add_axes([0.08, 0.105, 0.22, 0.012])
    fig.colorbar(im, cax=cax, orientation="horizontal", label="−log₁₀(p)  (clip 4)")
    fig.legend(
        handles=tx_sex_legend_handles(dest=dest),
        loc="upper center",
        bbox_to_anchor=(0.62, 0.125),
        bbox_transform=fig.transFigure,
        frameon=False,
        fontsize=ts["legend"],
        ncol=5,
    )
    fig.suptitle(
        "Pause syllable Δp by tx  (cluster_id 13; violin + salt; Kruskal within sex)",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_footnote(
        fig,
        (
            "Point = animal median Δp across 21 mapped alphabets. Whiskers = ±½ IQR of that "
            "animal's Δp across models (salt), not SEM. Violin = KDE by tx (sexes in the same "
            "KDE). Heatmaps: Kruskal Δp ~ tx within sex; cell = uncorrected p; * = BH q < 0.05 "
            "in the 24-cell family (presence / novelty / span). Color = −log₁₀(p). "
            "Not Wilcoxon vs 0; not alphabet-wide DA FDR."
        ),
        y=0.01,
        color=MUTE,
    )
    save_pdf_png(fig, out / "fig_cluster13_tx_delta")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--da-dir", type=Path, default=DEFAULT_DA)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    args = ap.parse_args(argv)

    out = args.out_dir or args.da_dir
    print("reading mapped ids + animal deltas ...", flush=True)
    ids = pd.read_csv(args.da_dir / "duration_band_vs_da.csv", usecols=["model", "raw_syllable_id"])
    deltas = pd.read_csv(args.da_dir / "da_syllable_deltas_per_animal.csv", usecols=list(DELTA_USECOLS))
    mapped = filter_mapped_deltas(deltas, ids)
    print(f"mapped rows {len(mapped)}", flush=True)
    med = animal_median_delta_p(mapped)
    kr = kruskal_by_phase_step_sex(med)
    med.to_csv(out / "cluster13_animal_median_delta_p.csv", index=False)
    kr.to_csv(out / "cluster13_tx_kruskal.csv", index=False)
    (out / "INFO_cluster13_tx_delta.md").write_text(_info_md(), encoding="utf-8")
    fig_strip_b(med, kr, out, dest=args.dest)
    summary = {
        "n_animal_cells": int(len(med)),
        "n_models_min": int(med["n_models"].min()) if len(med) else 0,
        "n_models_max": int(med["n_models"].max()) if len(med) else 0,
        "n_kruskal_cells": int(len(kr)),
        "n_kruskal_fdr": int(kr["hit_fdr05"].sum()) if "hit_fdr05" in kr.columns else 0,
        "family": "phase x step x sex",
    }
    (out / "cluster13_tx_delta_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    print(
        kr[["phase_layer", "step", "sex", "n", "p", "q_bh", "hit_fdr05"]].to_string(index=False),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
