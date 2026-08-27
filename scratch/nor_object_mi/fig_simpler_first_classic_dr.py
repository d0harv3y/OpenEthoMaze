"""Publication figures: classic investigation DR vs object-prox occupancy DR.

Reads only CSVs listed in INFO_classic_dr.md.

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/fig_simpler_first_classic_dr.py
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
    FIGSIZE_SLIDES,
    INK,
    PHASE_SHORT,
    PHASES,
    SEX_MARKER,
    SEX_ORDER,
    TX_COLOR,
    TX_ORDER,
    apply_style,
    fig_footnote,
    fig_legend_and_footnote,
    p_text,
    panel_stats_box,
    save_pdf_png,
    text_on_cmap,
    tx_sex_legend_handles,
    type_scale,
)

DEFAULT_RUN = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017" r"\_nor_object_mi\simpler_first_classic_dr")
CONTRASTS = (
    ("classic_vs_object_prox", "object-prox DR"),
    ("classic_vs_speed", "mean speed"),
    ("classic_vs_immobile", "time immobile"),
)
FOOT_VIOLIN = (
    "Grain: animal × phase × novel_obj. Each point is one animal's classic "
    "investigation DR (nose/forelimb T_nvl vs T_fam). Color=tx, shape=sex. "
    "Wilcoxon p is DR vs 0, txs pooled (preference, not a treatment claim). "
    "Kruskal p is within sex (treatment claim). Not a syllable composition; "
    "not object-prox occupancy; not MI; not DA."
)
FOOT_SCATTER = (
    "Grain: animal × phase × novel_obj. X = classic investigation DR; Y = "
    "object-prox occupancy DR (median across 21 kpMS models). Same formula, "
    "different T. Color=tx, shape=sex. Spearman ρ and p are from "
    "classic_dr_association.csv (not recomputed). Dashed line is y = x. "
    "Not a treatment claim; not speed thresholding; not MI; not DA."
)
FOOT_ASSOC = (
    "Grain: animal × phase × novel_obj. Color is Spearman ρ of classic "
    "investigation DR vs each Y (diverging map, −1 to +1). Cell text is ρ. "
    "This is a within-animal association, not a treatment claim and not "
    "Wilcoxon vs 0. Speed and immobile are ambulation (displacement hysteresis), "
    "not investigation. Uncorrected. Not MI; not DA."
)



FOOT_VIOLIN_S = (
    "Wilcoxon vs 0 is preference (txs pooled). Kruskal by tx is within sex (treatment)."
)
FOOT_SCATTER_S = (
    "Same DR formula, different T: investigation vs object-prox occupancy. Spearman from the association table."
)
FOOT_ASSOC_S = (
    "Spearman ρ of classic DR vs object-prox / speed / immobile. Association, not a treatment test."
)


def _begin(dest: str) -> dict[str, float]:
    apply_style(dest=dest)
    return type_scale(dest)


def _note(dest: str, paper: str, slides: str) -> str:
    return slides if dest == "slides" else paper


def _p_compact(p: float) -> str:
    if not np.isfinite(p):
        return "n/a"
    if p < 1e-4:
        return "<10⁻⁴"
    if p < 0.001:
        return f"{p:.1e}"
    return f"{p:.2f}"


def _as_bool(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s
    return s.astype(str).str.lower().isin(("true", "1"))


def _draw_tx_violins(ax, panel: pd.DataFrame, ycol: str, rng: np.random.Generator, *, dest: str) -> list[int]:
    ts = type_scale(dest)
    positions = list(range(len(TX_ORDER)))
    bodies: list[np.ndarray] = []
    body_pos: list[int] = []
    body_color: list[str] = []
    ns: list[int] = []
    for i, t in enumerate(TX_ORDER):
        sub = panel[panel["tx"] == t]
        y = sub[ycol].to_numpy(dtype=float)
        sex = sub["sex"].to_numpy()
        finite = np.isfinite(y)
        y = y[finite]
        sex = sex[finite]
        ns.append(int(y.size))
        if y.size >= 2 and np.unique(y).size >= 2:
            bodies.append(y)
            body_pos.append(i)
            body_color.append(TX_COLOR[t])
        if y.size:
            x = np.full(y.shape, float(i)) + rng.normal(0.0, 0.055, size=y.size)
            for s in SEX_ORDER:
                m = sex == s
                if not np.any(m):
                    continue
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
    ax.set_xticks(positions)
    if dest == "slides":
        ax.set_xticklabels([])
        ax.tick_params(axis="x", length=3)
    else:
        ax.set_xticklabels(list(TX_ORDER), fontsize=ts["annotation"], rotation=35, ha="right")
    ax.set_xlim(-0.7, len(TX_ORDER) - 0.3)
    return ns


def fig_violin(paired: pd.DataFrame, tests: pd.DataFrame, out: Path, *, dest: str = "slides") -> None:
    ts = _begin(dest)
    wx = tests[(tests["test"] == "wilcoxon_signed_rank") & (tests["metric"] == "dr_classic")]
    kr = tests[(tests["test"] == "kruskal") & (tests["metric"] == "dr_classic")]
    rng = np.random.default_rng(0)
    if dest == "slides":
        fig, axes = plt.subplots(1, 4, figsize=FIGSIZE_SLIDES, sharey=True, layout="constrained")
    else:
        fig, axes = plt.subplots(1, 4, figsize=(7.2, 4.4), sharey=True, layout="constrained")
    ax_list = list(axes)
    for c, ph in enumerate(PHASES):
        ax = ax_list[c]
        panel = paired[paired["phase_layer"] == ph]
        ns = _draw_tx_violins(ax, panel, "dr_classic", rng, dest=dest)
        ax.axhline(0.0, color="#bbbbbb", lw=0.7, ls="--", zorder=0)
        nlab = "n=" + "/".join(str(n) for n in ns)
        w = wx[wx["phase_layer"] == ph]
        pf = pm = float("nan")
        for sex in SEX_ORDER:
            k = kr[(kr["phase_layer"] == ph) & (kr["sex"] == sex)]
            if len(k) == 1:
                if sex == "F":
                    pf = float(k["p"].iloc[0])
                else:
                    pm = float(k["p"].iloc[0])
        p_wx = float(w["p"].iloc[0]) if len(w) == 1 else float("nan")
        panel_stats_box(
            ax,
            [
                nlab,
                "Wilcoxon vs 0  " + _p_compact(p_wx),
                "Kruskal by tx (within sex)",
                f"F {_p_compact(pf)}   M {_p_compact(pm)}",
            ],
            dest=dest,
        )
        if dest == "slides":
            ax.set_xlabel(PHASE_SHORT[ph], fontsize=ts["annotation"], color=INK, fontweight="bold")
        else:
            ax.set_title(PHASE_SHORT[ph], loc="left", fontweight="bold", color=INK, fontsize=ts["annotation"])
        if c == 0:
            ax.set_ylabel("classic investigation DR")
    fig.suptitle(
        "Classic nose/forelimb investigation DR  ·  same formula, investigation T",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
        y=1.02,
    )
    fig_legend_and_footnote(
        fig,
        tx_sex_legend_handles(dest=dest),
        _note(dest, FOOT_VIOLIN, FOOT_VIOLIN_S),
        dest=dest,
    )
    save_pdf_png(fig, out / "fig_classic_dr_violin")


def fig_scatter(paired: pd.DataFrame, assoc: pd.DataFrame, out: Path, *, dest: str = "slides") -> None:
    ts = _begin(dest)
    rng = np.random.default_rng(0)
    if dest == "slides":
        fig, axes = plt.subplots(1, 4, figsize=FIGSIZE_SLIDES, sharex=True, sharey=True, layout="constrained")
    else:
        fig, axes = plt.subplots(1, 4, figsize=(7.2, 4.4), sharex=True, sharey=True, layout="constrained")
    agr = assoc[assoc["contrast"] == "classic_vs_object_prox"]
    for i, ph in enumerate(PHASES):
        ax = axes[i]
        panel = paired[paired["phase_layer"] == ph]
        x = panel["dr_classic"].to_numpy(dtype=float)
        y = panel["dr_object_prox"].to_numpy(dtype=float)
        tx = panel["tx"].to_numpy()
        sex = panel["sex"].to_numpy()
        ok = np.isfinite(x) & np.isfinite(y)
        x, y, tx, sex = x[ok], y[ok], tx[ok], sex[ok]
        jitter = rng.normal(0.0, 0.008, size=x.size)
        for t in TX_ORDER:
            for s in SEX_ORDER:
                m = (tx == t) & (sex == s)
                if not np.any(m):
                    continue
                ax.scatter(
                    x[m] + jitter[m],
                    y[m],
                    s=ts["scatter"],
                    c=TX_COLOR[t],
                    marker=SEX_MARKER[s],
                    alpha=0.75,
                    edgecolors="none",
                    zorder=3,
                )
        ax.plot([-1.05, 1.05], [-1.05, 1.05], color="#bbbbbb", lw=0.8, ls="--", zorder=0)
        ax.set_xlim(-1.08, 1.08)
        ax.set_ylim(-1.08, 1.08)
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlabel(PHASE_SHORT[ph], fontsize=ts["annotation"], color=INK, fontweight="bold")
        if i == 0:
            ax.set_ylabel("object-prox DR")
        row = agr[agr["phase_layer"] == ph]
        if len(row) == 1:
            rho = float(row["spearman_rho"].iloc[0])
            p = float(row["p"].iloc[0])
            hit = "hit" if bool(_as_bool(row["hit_p05"]).iloc[0]) else "miss"
            panel_stats_box(
                ax,
                [
                    f"n={int(row['n'].iloc[0])}",
                    f"Spearman ρ = {rho:.2f}",
                    p_text(p),
                    hit,
                ],
                dest=dest,
            )
    fig.suptitle(
        "Same NOR preference ranks: investigation DR vs object-prox occupancy DR",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
        y=1.04,
    )
    fig_legend_and_footnote(
        fig,
        tx_sex_legend_handles(dest=dest),
        _note(dest, FOOT_SCATTER, FOOT_SCATTER_S),
        dest=dest,
    )
    save_pdf_png(fig, out / "fig_classic_vs_object_prox")


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
    ax.set_xticklabels([lab for _c, lab in CONTRASTS], rotation=20, ha="right")
    ax.set_yticks(range(len(PHASES)))
    ax.set_yticklabels([PHASE_SHORT[p] for p in PHASES])
    ax.set_title("A  Spearman ρ with classic DR", loc="left", fontweight="bold", color=INK)
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
                    fontsize=ts["cell"],
                    color=text_on_cmap(v, cmap="RdBu_r", vmin=-1.0, vmax=1.0),
                )
    fig.colorbar(im, ax=ax, fraction=0.04, pad=0.03, label="Spearman ρ")
    fig.suptitle(
        "Classic investigation DR associates with object-prox DR, not with speed",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
        y=1.04,
    )
    fig_footnote(fig, _note(dest, FOOT_ASSOC, FOOT_ASSOC_S), y=-0.10)
    save_pdf_png(fig, out / "fig_classic_association")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    args = ap.parse_args(argv)
    dest = args.dest
    run = args.run_dir
    out = args.out_dir or (run / "figures")
    paired = pd.read_csv(run / "classic_dr_paired.csv")
    tests = pd.read_csv(run / "classic_dr_tests_long.csv")
    assoc = pd.read_csv(run / "classic_dr_association.csv")
    fig_violin(paired, tests, out, dest=dest)
    fig_scatter(paired, assoc, out, dest=dest)
    fig_association(assoc, out, dest=dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
