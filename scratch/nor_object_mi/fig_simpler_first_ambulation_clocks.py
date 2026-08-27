"""Publication figures: movement-bout clock vs syllable-bout clock.

Reads only CSVs listed in INFO_ambulation_clocks.md.

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/fig_simpler_first_ambulation_clocks.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi._pub_style import (  # noqa: E402
    FIGSIZE_DOUBLE,
    INK,
    PHASE_SHORT,
    PHASES,
    SEX_MARKER,
    SEX_ORDER,
    TX_COLOR,
    TX_ORDER,
    apply_style,
    fig_footnote,
    p_text,
    save_pdf_png,
    text_on_cmap,
    type_scale,
)

DEFAULT_RUN = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017" r"\_nor_object_mi\simpler_first_ambulation_clocks")
CONTRASTS = (
    ("n_move_vs_n_syll", "n clocks"),
    ("dur_move_vs_dur_syll", "duration clocks"),
    ("bout_speed_vs_session_speed", "speed litmus"),
    ("bout_dist_vs_session_dist", "distance litmus"),
    ("session_speed_vs_n_syll", "speed vs n_syll"),
    ("session_speed_vs_classic_dr", "speed vs DR"),
    ("n_move_vs_classic_dr", "n_move vs DR"),
)
FOOT_N = (
    "Grain: animal × phase × novel_obj. X = IMPRESS movement-bout count "
    "(fore hysteresis). Y = kpMS syllable-bout count (locked ss-50 model). "
    "These are different clocks, not paired events. Color=tx, shape=sex. "
    "Spearman from clock_association.csv. Not DR; not syllable speed; not MI; not DA."
)
FOOT_DUR = (
    "Grain: animal × phase × novel_obj. X = median movement-bout duration (s). "
    "Y = median syllable-bout duration (bout_frames / 30). Different debounce "
    "rules and typical scales. Color=tx, shape=sex. Spearman from the association "
    "table. Not a speed comparison (NOR ladders have no bout_mean_speed_mps)."
)
FOOT_ASSOC = (
    "Grain: animal × phase × novel_obj. Color is Spearman ρ (−1 to +1). Litmus "
    "columns (speed, distance) check that movement bouts reconstruct session "
    "ambulation. Clock columns compare n / duration across segmenters. DR columns "
    "are the negative control (kinematics ≠ preference). Uncorrected. Not MI; not DA."
)



FOOT_N_S = (
    "Movement-bout n vs syllable-bout n (locked ss-50). Different clocks, not paired events."
)
FOOT_DUR_S = (
    "Median bout duration: movement vs syllable. Different debounce; not a speed comparison."
)
FOOT_ASSOC_S = (
    "Spearman ρ among clocks, litmus kinematics, and NOR DR (negative control)."
)


def _begin(dest: str) -> dict[str, float]:
    apply_style(dest=dest)
    return type_scale(dest)


def _note(dest: str, paper: str, slides: str) -> str:
    return slides if dest == "slides" else paper


def _as_bool(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s
    return s.astype(str).str.lower().isin(("true", "1"))


def _legend_tx_sex(fig, *, dest: str, bbox=(1.0, 1.04)) -> None:
    ts = type_scale(dest)
    ms = 8 if dest == "slides" else 6
    handles = [Line2D([0], [0], marker="o", color="none", markerfacecolor=TX_COLOR[t], markersize=ms, label=t) for t in TX_ORDER] + [
        Line2D(
            [0],
            [0],
            marker=SEX_MARKER[s],
            color="none",
            markerfacecolor=INK,
            markersize=ms,
            label=s,
        )
        for s in SEX_ORDER
    ]
    fig.legend(handles=handles, loc="upper right", frameon=False, fontsize=ts["legend"], ncol=5, bbox_to_anchor=bbox)


def _scatter_grid(
    paired: pd.DataFrame,
    assoc: pd.DataFrame,
    *,
    xcol: str,
    ycol: str,
    contrast: str,
    xlabel: str,
    ylabel: str,
    title: str,
    footnote: str,
    stem: str,
    out: Path,
    dest: str = "slides",
) -> None:
    ts = _begin(dest)
    agr = assoc[assoc["contrast"] == contrast]
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 7.0), constrained_layout=True)
    for i, ph in enumerate(PHASES):
        ax = axes[i // 2][i % 2]
        panel = paired[paired["phase_layer"] == ph]
        x = panel[xcol].to_numpy(dtype=float)
        y = panel[ycol].to_numpy(dtype=float)
        tx = panel["tx"].to_numpy()
        sex = panel["sex"].to_numpy()
        ok = np.isfinite(x) & np.isfinite(y)
        x, y, tx, sex = x[ok], y[ok], tx[ok], sex[ok]
        for t in TX_ORDER:
            for s in SEX_ORDER:
                m = (tx == t) & (sex == s)
                if not np.any(m):
                    continue
                ax.scatter(
                    x[m],
                    y[m],
                    s=ts["scatter"],
                    c=TX_COLOR[t],
                    marker=SEX_MARKER[s],
                    alpha=0.75,
                    edgecolors="none",
                    zorder=3,
                )
        ax.set_title(PHASE_SHORT[ph], loc="left", fontweight="bold", color=INK, fontsize=ts["annotation"])
        if i // 2 == 1:
            ax.set_xlabel(xlabel)
        if i % 2 == 0:
            ax.set_ylabel(ylabel)
        row = agr[agr["phase_layer"] == ph]
        if len(row) == 1:
            rho = float(row["spearman_rho"].iloc[0])
            p = float(row["p"].iloc[0])
            hit = bool(_as_bool(row["hit_p05"]).iloc[0])
            ax.text(
                0.04,
                0.96,
                f"n={int(row['n'].iloc[0])}\nρ = {rho:.2f}\n{p_text(p)}\n{'hit' if hit else 'miss'}",
                transform=ax.transAxes,
                va="top",
                ha="left",
                fontsize=ts["annotation"],
                color=INK,
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="#dddddd", lw=0.6),
            )
    _legend_tx_sex(fig, dest=dest)
    fig.suptitle(title, fontsize=ts["suptitle"], fontweight="bold", color=INK, y=1.04)
    fig_footnote(fig, footnote, y=-0.06)
    save_pdf_png(fig, out / stem)


def fig_association(assoc: pd.DataFrame, out: Path, *, dest: str = "slides") -> None:
    ts = _begin(dest)
    fig, ax = plt.subplots(figsize=FIGSIZE_DOUBLE, constrained_layout=True)
    mat = np.full((len(PHASES), len(CONTRASTS)), np.nan)
    for i, ph in enumerate(PHASES):
        for j, (contrast, _lab) in enumerate(CONTRASTS):
            row = assoc[(assoc["phase_layer"] == ph) & (assoc["contrast"] == contrast)]
            if len(row) == 1:
                mat[i, j] = float(row["spearman_rho"].iloc[0])
    im = ax.imshow(mat, cmap="RdBu_r", vmin=-1.0, vmax=1.0, aspect="auto")
    ax.set_xticks(range(len(CONTRASTS)))
    ax.set_xticklabels([lab for _c, lab in CONTRASTS], rotation=28, ha="right", fontsize=ts["annotation"])
    ax.set_yticks(range(len(PHASES)))
    ax.set_yticklabels([PHASE_SHORT[p] for p in PHASES])
    ax.set_title("A  Spearman ρ", loc="left", fontweight="bold", color=INK)
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            v = mat[i, j]
            if np.isfinite(v):
                ax.text(
                    j,
                    i,
                    f"{v:.2f}",
                    ha="center",
                    va="center",
                    fontsize=ts["annotation"],
                    color=text_on_cmap(v, cmap="RdBu_r", vmin=-1.0, vmax=1.0),
                )
    fig.colorbar(im, ax=ax, fraction=0.04, pad=0.03, label="Spearman ρ")
    fig.suptitle(
        "Movement and syllable clocks associate moderately; neither is NOR DR",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
        y=1.06,
    )
    fig_footnote(fig, _note(dest, FOOT_ASSOC, FOOT_ASSOC_S), y=-0.14)
    save_pdf_png(fig, out / "fig_clock_association")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    args = ap.parse_args(argv)
    dest = args.dest
    run = args.run_dir
    out = args.out_dir or (run / "figures")
    paired = pd.read_csv(run / "clock_metrics_per_animal.csv")
    assoc = pd.read_csv(run / "clock_association.csv")
    _scatter_grid(
        paired,
        assoc,
        xcol="n_move_bouts",
        ycol="n_syll_bouts",
        contrast="n_move_vs_n_syll",
        xlabel="movement bouts (n)",
        ylabel="syllable bouts (n)",
        title="Two clocks: movement-bout count vs syllable-bout count",
        footnote=_note(dest, FOOT_N, FOOT_N_S),
        stem="fig_clock_n_bouts",
        out=out,
        dest=dest,
    )
    _scatter_grid(
        paired,
        assoc,
        xcol="median_move_duration_s",
        ycol="median_syll_duration_s",
        contrast="dur_move_vs_dur_syll",
        xlabel="median movement-bout duration (s)",
        ylabel="median syllable-bout duration (s)",
        title="Two clocks: median bout duration (movement vs syllable)",
        footnote=_note(dest, FOOT_DUR, FOOT_DUR_S),
        stem="fig_clock_duration",
        out=out,
        dest=dest,
    )
    fig_association(assoc, out, dest=dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
