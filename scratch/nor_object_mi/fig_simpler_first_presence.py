"""Publication figures for simpler-first presence steps.

Reads only CSVs listed in INFO_presence_steps.md. Does not read the xlsx
sidecar or upstream bout tables.

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/fig_simpler_first_presence.py
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
    PILOT_MODEL,
    SEX_MARKER,
    SEX_ORDER,
    TX_COLOR,
    TX_ORDER,
    apply_style,
    fig_footnote,
    p_text,
    save_pdf_png,
    text_on_cmap,
)
from nor_object_mi.simpler_first_presence import (  # noqa: E402
    CONTROL_TX,
    TX_STRATUM_ALL,
    TX_STRATUM_CONTROL,
    across_model_dispersion_summary,
    animal_median_across_models,
    consensus_tests,
    restrict_tx_stratum,
)

DEFAULT_RUN = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_presence_steps"
)
METRICS = ("frac_near", "mean_dist_any_m", "richness", "shannon_bits")
METRIC_LAB = {
    "frac_near": "frac_near",
    "mean_dist_any_m": "mean dist (m)",
    "richness": "richness",
    "shannon_bits": "Shannon (bits)",
}
STEPS = (
    ("no_obj->identical", "A  Presence  no_obj → identical"),
    ("identical->novel", "B  Novelty  identical → novel"),
)
STEP_ARROW = {
    "no_obj->identical": "no_obj → identical",
    "identical->novel": "identical → novel",
    "no_obj->novel": "no_obj → novel",
}
STEP_PLAIN = {
    "no_obj->identical": "Presence",
    "identical->novel": "Novelty",
    "no_obj->novel": "Span",
}
STEP_GLOSS = (
    "Presence = no_obj → identical (objects appear). "
    "Novelty = identical → novel (novel replaces identical). "
    "BL/TX/REC3/REC11 are NOR phases, not condition steps."
)
DELTA_COL = {
    "frac_near": "delta_frac_near",
    "mean_dist_any_m": "delta_mean_dist_any_m",
    "richness": "delta_richness",
    "shannon_bits": "delta_shannon_bits",
}
FOOT = (
    "Grain: animal × phase × condition (full session). Hit rule: sex=all Wilcoxon "
    "p < 0.05, txs pooled — not a treatment claim. Near window 0.10 m on spot. "
    "21 kpMS models. Not MI; not DA. On no_obj, dist_any is to historical loci."
)
WILCOXON_POOLED = "pooled"
WILCOXON_NOSD = "nosd"
FOOT_WILCOXON_SEX_POOLED = (
    "Grain: animal × phase × condition (full session). This figure: Wilcoxon signed-rank "
    "on the paired Δ vs 0, within sex, txs pooled — companion, not a treatment claim. "
    "Color: frac of 21 kpMS models with Wilcoxon p < 0.05. sex=all companion: "
    "fig_presence_frac_hit. Evolution I (tx=noSD): --wilcoxon nosd. Near window 0.10 m "
    "on spot. Not MI; not DA. On no_obj, dist_any is to historical loci. "
)
FOOT_WILCOXON_SEX_NOSD = (
    "Grain: animal × phase × condition (full session). This figure: Wilcoxon signed-rank "
    "on the paired Δ vs 0, within sex, tx=noSD only — evolution I primary, not a treatment "
    "claim. Color: frac of 21 kpMS models with Wilcoxon p < 0.05. Pooled-tx companion: "
    "fig_presence_frac_hit (sex=all). Near window 0.10 m on spot. Not MI; not DA. "
    "On no_obj, dist_any is to historical loci. "
)
STEP_SEX_PANELS = (
    (0, 0, "no_obj->identical", "F", "A"),
    (0, 1, "no_obj->identical", "M", "B"),
    (1, 0, "identical->novel", "F", "C"),
    (1, 1, "identical->novel", "M", "D"),
)
SEX_LAB = {"F": "female", "M": "male"}
FOOT_CONSENSUS_WX = (
    "Grain: one animal; each animal's Δ is the median across 21 kpMS models. "
    "This figure is Wilcoxon signed-rank on that median Δ vs 0. Color is −log₁₀(p), "
    "not frac of models that hit. Cell text is the p-value. sex=all panel: txs pooled "
    "(companion). Uncorrected p < 0.05. Near window 0.10 m on spot. Not MI; not DA. "
)
FOOT_CONSENSUS_WX_BY_SEX_POOLED = (
    FOOT_CONSENSUS_WX + " By-sex panel: txs pooled (companion). "
)
FOOT_CONSENSUS_WX_BY_SEX_NOSD = (
    FOOT_CONSENSUS_WX + " By-sex panel: tx=noSD only (evolution I). "
)
FOOT_CONSENSUS_KR = (
    "Grain: one animal; each animal's Δ is the median across 21 kpMS models. "
    "This figure is Kruskal–Wallis by tx within sex on that median Δ — a treatment "
    "claim (groups differ on a scalar). Color is −log₁₀(p), not frac of models that "
    "hit. Cell text is the p-value. Uncorrected. Not the Wilcoxon consensus. Not MI; "
    "not DA; not PERMANOVA. Richness/Shannon Δs are not commensurate across alphabets. "
)
FOOT_CONSENSUS_IQR = (
    "Grain: one animal × 21 kpMS models. Cell = cohort median of each animal's "
    "across-model IQR of Δ (salt), not SEM, not a p-value. Color is scaled 0–1 "
    "independently within each metric column (units differ: frac vs meters vs COUNT). "
    "Richness/Shannon IQR is exploratory across alphabets. Companion to the consensus "
    "p heatmap, not a test. "
)
NLP_VMAX = 4.0
FIGSIZE_CONSENSUS = (7.2, 5.8)
FOOT_KRUSKAL = (
    "Grain: animal × phase × condition (full session). This figure is Kruskal–Wallis "
    "by tx (noSD, GHSD, RBSD) within sex, on the paired Δ — groups differ on a scalar. "
    "That is a treatment claim. Color: frac of 21 kpMS models with Kruskal p < 0.05 "
    "(uncorrected). Not the Wilcoxon hit rule (sex=all, txs pooled; that other test is "
    "not a treatment claim). Near window 0.10 m on spot. Not MI; not DA; not PERMANOVA. "
    "On no_obj, dist_any is to historical loci. "
)


def _as_bool(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s
    return s.astype(str).str.lower().isin(("true", "1"))


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


def _p_mat(sub: pd.DataFrame, *, metric_key: str) -> np.ndarray:
    mat = np.full((len(PHASES), len(METRICS)), np.nan)
    for i, ph in enumerate(PHASES):
        for j, met in enumerate(METRICS):
            key = metric_key.format(met=met)
            cell = sub[(sub["phase_layer"] == ph) & (sub["metric"] == key)]
            if len(cell) == 1:
                mat[i, j] = float(cell["p"].iloc[0])
    return mat


def _imshow_p(ax, pmat: np.ndarray):
    nlp = np.vectorize(_neglog10_p, otypes=[float])(pmat)
    im = ax.imshow(nlp, cmap="viridis", vmin=0.0, vmax=NLP_VMAX, aspect="auto")
    ax.set_xticks(range(len(METRICS)))
    ax.set_xticklabels([METRIC_LAB[m] for m in METRICS], rotation=35, ha="right", fontsize=7)
    ax.set_yticks(range(len(PHASES)))
    ax.set_yticklabels([PHASE_SHORT[p] for p in PHASES])
    for i in range(pmat.shape[0]):
        for j in range(pmat.shape[1]):
            p = pmat[i, j]
            nlp_v = nlp[i, j]
            if np.isfinite(p) and np.isfinite(nlp_v):
                ax.text(
                    j,
                    i,
                    _p_cell_text(p),
                    ha="center",
                    va="center",
                    fontsize=6,
                    color=text_on_cmap(nlp_v, vmin=0.0, vmax=NLP_VMAX),
                )
    return im


def _iqr_mat(sub: pd.DataFrame) -> np.ndarray:
    mat = np.full((len(PHASES), len(METRICS)), np.nan)
    for i, ph in enumerate(PHASES):
        for j, met in enumerate(METRICS):
            row = sub[(sub["phase_layer"] == ph) & (sub["metric"] == DELTA_COL[met])]
            if len(row) == 1:
                mat[i, j] = float(row["median_of_iqr"].iloc[0])
    return mat


def _column_unit_color(mats: list[np.ndarray]) -> list[np.ndarray]:
    """Map each metric column to 0–1 using min/max across all panels (raw IQR in text)."""
    stacked = np.stack(mats, axis=0)
    out: list[np.ndarray] = []
    for mat in mats:
        color = np.full(mat.shape, np.nan)
        for j in range(mat.shape[1]):
            finite = stacked[:, :, j]
            finite = finite[np.isfinite(finite)]
            if finite.size == 0:
                continue
            vmin = float(np.min(finite))
            vmax = float(np.max(finite))
            col = mat[:, j]
            if vmax <= vmin:
                color[:, j] = np.where(np.isfinite(col), 0.5, np.nan)
            else:
                color[:, j] = (col - vmin) / (vmax - vmin)
        out.append(color)
    return out


def _iqr_cell_text(v: float) -> str:
    if not np.isfinite(v):
        return ""
    return f"{v:.3g}"


def _imshow_iqr(ax, mat: np.ndarray, color: np.ndarray):
    im = ax.imshow(color, cmap="viridis", vmin=0.0, vmax=1.0, aspect="auto")
    ax.set_xticks(range(len(METRICS)))
    ax.set_xticklabels([METRIC_LAB[m] for m in METRICS], rotation=35, ha="right", fontsize=7)
    ax.set_yticks(range(len(PHASES)))
    ax.set_yticklabels([PHASE_SHORT[p] for p in PHASES])
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            v = mat[i, j]
            c = color[i, j]
            if np.isfinite(v) and np.isfinite(c):
                ax.text(
                    j,
                    i,
                    _iqr_cell_text(v),
                    ha="center",
                    va="center",
                    fontsize=6,
                    color=text_on_cmap(c, vmin=0.0, vmax=1.0),
                )
    return im


def fig_frac_hit(agr: pd.DataFrame, out: Path) -> None:
    apply_style()
    fig, axes = plt.subplots(1, 2, figsize=FIGSIZE_DOUBLE, constrained_layout=True)
    vmin, vmax = 0.0, 1.0
    im = None
    for ax, (step, title) in zip(axes, STEPS):
        sub = agr[agr["step"] == step]
        mat = np.full((len(PHASES), len(METRICS)), np.nan)
        for i, ph in enumerate(PHASES):
            for j, met in enumerate(METRICS):
                row = sub[(sub["phase_layer"] == ph) & (sub["metric"] == met)]
                if len(row) == 1:
                    mat[i, j] = float(row["frac_hit"].iloc[0])
        im = ax.imshow(mat, cmap="viridis", vmin=vmin, vmax=vmax, aspect="auto")
        ax.set_xticks(range(len(METRICS)))
        ax.set_xticklabels([METRIC_LAB[m] for m in METRICS], rotation=35, ha="right")
        ax.set_yticks(range(len(PHASES)))
        ax.set_yticklabels([PHASE_SHORT[p] for p in PHASES])
        ax.set_title(title, loc="left", fontweight="bold", color=INK)
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
                        fontsize=7,
                        color=text_on_cmap(v),
                    )
    fig.colorbar(im, ax=axes, fraction=0.025, pad=0.02, label="frac of 21 models with Wilcoxon hit")
    fig.suptitle(
        "Cross-model agreement: does the paired step hit (Wilcoxon, sex=all)?",
        fontsize=11,
        fontweight="bold",
        color=INK,
        y=1.04,
    )
    fig_footnote(fig, FOOT, y=-0.08)
    save_pdf_png(fig, out / "fig_presence_frac_hit")


def _wilcoxon_hit_frac(sub: pd.DataFrame, phase: str, metric: str) -> float:
    cell = sub[(sub["phase_layer"] == phase) & (sub["metric"] == metric)]
    if cell.empty:
        return float("nan")
    return float(cell["hit"].mean())


def fig_frac_hit_by_sex(tests: pd.DataFrame, out: Path, *, wilcoxon: str = WILCOXON_POOLED) -> None:
    apply_style()
    wx = restrict_tx_stratum(
        tests[tests["test"] == "wilcoxon_signed_rank"], _wx_stratum(wilcoxon)
    )
    wx = wx[wx["sex"].isin(SEX_ORDER)]
    wx["hit"] = _as_bool(wx["hit_p05"])
    fig, axes = plt.subplots(2, 2, figsize=FIGSIZE_DOUBLE, constrained_layout=True)
    im = None
    for r, c, step, sex, letter in STEP_SEX_PANELS:
        ax = axes[r, c]
        sub = wx[(wx["step"] == step) & (wx["sex"] == sex)]
        mat = np.full((len(PHASES), len(METRICS)), np.nan)
        for i, ph in enumerate(PHASES):
            for j, met in enumerate(METRICS):
                mat[i, j] = _wilcoxon_hit_frac(sub, ph, met)
        im = ax.imshow(mat, cmap="viridis", vmin=0.0, vmax=1.0, aspect="auto")
        ax.set_xticks(range(len(METRICS)))
        ax.set_xticklabels([METRIC_LAB[m] for m in METRICS], rotation=35, ha="right", fontsize=7)
        ax.set_yticks(range(len(PHASES)))
        ax.set_yticklabels([PHASE_SHORT[p] for p in PHASES])
        ax.set_title(
            f"{letter}  {STEP_PLAIN[step]} · {SEX_LAB[sex]}\n{STEP_ARROW[step]}",
            loc="left",
            fontweight="bold",
            color=INK,
            fontsize=8,
        )
        _annotate_heatmap(ax, mat)
    fig.colorbar(im, ax=axes, fraction=0.025, pad=0.02, label="frac of 21 models with Wilcoxon hit")
    fig.suptitle(
        "Cross-model agreement: does the paired step hit (Wilcoxon, within sex)?",
        fontsize=11,
        fontweight="bold",
        color=INK,
        y=1.08,
    )
    fig_footnote(
        fig,
        (FOOT_WILCOXON_SEX_POOLED if wilcoxon == WILCOXON_POOLED else FOOT_WILCOXON_SEX_NOSD)
        + STEP_GLOSS,
        y=-0.10,
    )
    save_pdf_png(fig, out / "fig_presence_frac_hit_by_sex")


def fig_median_delta(agr: pd.DataFrame, out: Path) -> None:
    apply_style()
    fig, axes = plt.subplots(2, 4, figsize=(7.2, 5.4), constrained_layout=True)
    x = np.arange(len(PHASES))
    for r, (step, stitle) in enumerate(STEPS):
        sub = agr[agr["step"] == step]
        for c, met in enumerate(METRICS):
            ax = axes[r, c]
            ys = []
            for ph in PHASES:
                row = sub[(sub["phase_layer"] == ph) & (sub["metric"] == met)]
                ys.append(float(row["median_of_median_delta"].iloc[0]) if len(row) == 1 else np.nan)
            colors = ["#2f5d8a" if (np.isfinite(y) and y >= 0) else "#8a4f3d" for y in ys]
            ax.bar(x, ys, color=colors, width=0.72, edgecolor="none")
            ax.axhline(0.0, color="#bbbbbb", lw=0.7, ls="--", zorder=0)
            ax.set_xticks(x)
            ax.set_xticklabels([PHASE_SHORT[p] for p in PHASES], fontsize=7)
            if c == 0:
                ax.set_ylabel("median of model median Δ")
            if r == 0:
                ax.set_title(METRIC_LAB[met], loc="left", fontweight="bold", color=INK, fontsize=8)
            if c == 0:
                ax.text(
                    -0.35,
                    1.12 if r == 0 else 1.02,
                    stitle.split("  ", 1)[0] + "  " + ("presence" if r == 0 else "novelty"),
                    transform=ax.transAxes,
                    fontsize=8,
                    fontweight="bold",
                    color=INK,
                    va="bottom",
                    ha="left",
                )
    fig.suptitle(
        "Direction of paired change (median across 21 models of each model's median Δ)",
        fontsize=11,
        fontweight="bold",
        color=INK,
        y=1.03,
    )
    fig_footnote(
        fig,
        FOOT + " Descriptive companion to frac_hit; independent y-scales (units differ).",
        y=-0.06,
    )
    save_pdf_png(fig, out / "fig_presence_median_delta")


def fig_paired_pilot(deltas: pd.DataFrame, tests: pd.DataFrame, out: Path, *, model: str) -> None:
    apply_style()
    dsub = deltas[(deltas["model"] == model) & (deltas["phase_layer"] == "NOR_TX")].copy()
    tsub = restrict_tx_stratum(
        tests[
            (tests["model"] == model)
            & (tests["phase_layer"] == "NOR_TX")
            & (tests["sex"] == "all")
            & (tests["test"] == "wilcoxon_signed_rank")
        ],
        TX_STRATUM_ALL,
    )
    rng = np.random.default_rng(0)
    fig, axes = plt.subplots(2, 4, figsize=(7.2, 6.2), constrained_layout=True)
    for r, (step, stitle) in enumerate(STEPS):
        step_d = dsub[dsub["step"] == step]
        for c, met in enumerate(METRICS):
            ax = axes[r, c]
            col = DELTA_COL[met]
            y = step_d[col].to_numpy(dtype=float)
            tx = step_d["tx"].to_numpy()
            sex = step_d["sex"].to_numpy()
            x = rng.normal(0.0, 0.08, size=y.size)
            for t in TX_ORDER:
                for s in SEX_ORDER:
                    m = (tx == t) & (sex == s)
                    ax.scatter(
                        x[m],
                        y[m],
                        s=10,
                        c=TX_COLOR[t],
                        marker=SEX_MARKER[s],
                        alpha=0.75,
                        edgecolors="none",
                        zorder=2,
                    )
            med = float(np.nanmedian(y)) if y.size else float("nan")
            ax.plot([-0.35, 0.35], [med, med], color=INK, lw=1.8, zorder=3)
            ax.axhline(0.0, color="#bbbbbb", lw=0.7, ls="--", zorder=0)
            ax.set_xticks([])
            ax.set_xlim(-0.55, 0.55)
            if c == 0:
                ax.set_ylabel("Δ (right − left)")
            if r == 0:
                ax.set_title(METRIC_LAB[met], loc="left", fontweight="bold", color=INK, fontsize=8)
            row = tsub[(tsub["step"] == step) & (tsub["metric"] == met)]
            if len(row) == 1:
                p = float(row["p"].iloc[0])
                hit = bool(_as_bool(row["hit_p05"]).iloc[0])
                ax.text(
                    0.04,
                    0.96,
                    f"n={int(row['n'].iloc[0])}\n{p_text(p)}\n{'hit' if hit else 'miss'}",
                    transform=ax.transAxes,
                    va="top",
                    ha="left",
                    fontsize=6.5,
                    color=INK,
                    bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="#dddddd", lw=0.6),
                )
            if c == 0:
                ax.text(
                    0.0,
                    1.14,
                    stitle,
                    transform=ax.transAxes,
                    fontsize=8,
                    fontweight="bold",
                    color=INK,
                    va="bottom",
                )
    handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=TX_COLOR[t], markersize=6, label=t)
        for t in TX_ORDER
    ] + [
        Line2D(
            [0],
            [0],
            marker=SEX_MARKER[s],
            color="none",
            markerfacecolor=INK,
            markersize=6,
            label=s,
        )
        for s in SEX_ORDER
    ]
    fig.legend(handles=handles, loc="upper right", frameon=False, fontsize=7, ncol=5, bbox_to_anchor=(1.0, 1.08))
    fig.suptitle(
        f"Pilot {model}  ·  NOR_TX  ·  animal-level paired Δ (color=tx, shape=sex)",
        fontsize=10,
        fontweight="bold",
        color=INK,
        y=1.10,
    )
    fig_footnote(
        fig,
        FOOT + " Wilcoxon box is sex=all from tests_long (not recomputed). Median tick includes zeros.",
        y=-0.05,
    )
    save_pdf_png(fig, out / "fig_presence_paired_pilot")


VIOLIN_STEPS = (
    ("no_obj->identical", "Presence"),
    ("identical->novel", "Novelty"),
)
VIOLIN_STEM = {
    "frac_near": "fig_presence_violin_frac_near",
    "mean_dist_any_m": "fig_presence_violin_mean_dist",
    "richness": "fig_presence_violin_richness",
    "shannon_bits": "fig_presence_violin_shannon",
}
FOOT_VIOLIN_PREFIX = (
    "Grain: animal × phase × condition (full session). Each point is one animal: "
    "the median of that animal's paired Δ across 21 kpMS models. Whiskers = ±½ IQR of "
    "that animal's Δ across models (salt), not SEM. Color=tx, shape=sex; violins are "
    "KDE of those medians by tx (sexes pooled in the KDE). "
)
FOOT_VIOLIN_WX_POOLED = (
    "Wilcoxon p is Δ vs 0, sex=all, txs pooled (companion; not a treatment claim). "
)
FOOT_VIOLIN_WX_NOSD = (
    "Wilcoxon p is Δ vs 0, tx=noSD, within sex (evolution I; not a treatment claim). "
)
FOOT_VIOLIN_TAIL = (
    "Kruskal p is within sex on the same medians (treatment claim). "
    "BL/TX n≈48 per tx arm; REC n≈24. Not MI; not DA. "
)


def _foot_violin(wilcoxon: str) -> str:
    wx = FOOT_VIOLIN_WX_POOLED if wilcoxon == WILCOXON_POOLED else FOOT_VIOLIN_WX_NOSD
    return FOOT_VIOLIN_PREFIX + wx + FOOT_VIOLIN_TAIL


def _wx_stratum(wilcoxon: str) -> str:
    return TX_STRATUM_ALL if wilcoxon == WILCOXON_POOLED else TX_STRATUM_CONTROL


FOOT_VIOLIN_COMPOSITION = (
    "Richness (COUNT) and Shannon (H) Δs are not commensurate across alphabets "
    "(ss-50 vs ss-75 vs ss-100); this median is a location summary, not a portable syllable inventory. "
)


def _draw_tx_violins(
    ax, panel: pd.DataFrame, ycol: str, rng: np.random.Generator, *, iqr_col: str | None = None
) -> list[int]:
    """Strip + violin by tx. Optional ``iqr_col`` → ±½ IQR whiskers (salt)."""
    positions = list(range(len(TX_ORDER)))
    bodies: list[np.ndarray] = []
    body_pos: list[int] = []
    body_color: list[str] = []
    ns: list[int] = []
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
        y = y[finite]
        sex = sex[finite]
        iqr = iqr[finite]
        ns.append(int(y.size))
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
                        elinewidth=0.65,
                        capsize=0,
                        alpha=0.35,
                        zorder=2,
                    )
                ax.scatter(
                    x[m],
                    y[m],
                    s=9,
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
    ax.axhline(0.0, color="#bbbbbb", lw=0.7, ls="--", zorder=0)
    ax.set_xticks(positions)
    ax.set_xticklabels(list(TX_ORDER), fontsize=6, rotation=35, ha="right")
    ax.set_xlim(-0.7, len(TX_ORDER) - 0.3)
    return ns


def _attach_iqr(
    med: pd.DataFrame,
    salt: pd.DataFrame,
    *,
    metric: str,
    on: list[str],
) -> pd.DataFrame:
    s = salt[salt["metric"] == metric][on + ["iqr"]].rename(columns={"iqr": "iqr_across_models"})
    return med.merge(s, on=on, how="left")


def fig_delta_violins(
    deltas: pd.DataFrame,
    cons: pd.DataFrame,
    out: Path,
    *,
    salt: pd.DataFrame | None = None,
    salt_summary: pd.DataFrame | None = None,
    wilcoxon: str = WILCOXON_POOLED,
) -> None:
    apply_style()
    dsub = animal_median_across_models(deltas)
    n_models = int(deltas["model"].nunique())
    wx_rows = cons[cons["test"] == "wilcoxon_signed_rank"]
    if wilcoxon == WILCOXON_POOLED:
        wx_ann = restrict_tx_stratum(wx_rows[wx_rows["sex"] == "all"], TX_STRATUM_ALL)
    else:
        wx_ann = restrict_tx_stratum(wx_rows[wx_rows["sex"].isin(("F", "M"))], TX_STRATUM_CONTROL)
    kr = cons[cons["test"] == "kruskal"]
    salt_on = ["animal_id", "sex", "tx", "step", "phase_layer"]
    for met in METRICS:
        rng = np.random.default_rng(0)
        fig, axes = plt.subplots(2, 4, figsize=(7.2, 6.4), sharey=True, constrained_layout=True)
        col = DELTA_COL[met]
        med = dsub
        iqr_col = None
        if salt is not None and not salt.empty:
            med = _attach_iqr(dsub, salt, metric=col, on=salt_on)
            iqr_col = "iqr_across_models"
        for r, (step, slabel) in enumerate(VIOLIN_STEPS):
            for c, ph in enumerate(PHASES):
                ax = axes[r, c]
                panel = med[(med["step"] == step) & (med["phase_layer"] == ph)]
                ns = _draw_tx_violins(ax, panel, col, rng, iqr_col=iqr_col)
                if c == 0:
                    ax.set_ylabel(f"{slabel}\nΔ (right − left)", fontsize=8)
                if r == 0:
                    ax.set_title(PHASE_SHORT[ph], loc="left", fontweight="bold", color=INK, fontsize=8)
                lines = ["n=" + "/".join(str(n) for n in ns)]
                if salt_summary is not None and not salt_summary.empty and met in ("frac_near", "mean_dist_any_m"):
                    srow = salt_summary[
                        (salt_summary["phase_layer"] == ph)
                        & (salt_summary["step"] == step)
                        & (salt_summary["metric"] == col)
                    ]
                    if len(srow) == 1:
                        lines.append(f"cohort med IQR={float(srow['median_of_iqr'].iloc[0]):.3g}")
                if wilcoxon == WILCOXON_POOLED:
                    w = wx_ann[
                        (wx_ann["step"] == step)
                        & (wx_ann["phase_layer"] == ph)
                        & (wx_ann["metric"] == met)
                    ]
                    if len(w) == 1:
                        lines.append("Wilcoxon pooled " + p_text(float(w["p"].iloc[0])))
                else:
                    for sex in SEX_ORDER:
                        w = wx_ann[
                            (wx_ann["step"] == step)
                            & (wx_ann["phase_layer"] == ph)
                            & (wx_ann["metric"] == met)
                            & (wx_ann["sex"] == sex)
                        ]
                        if len(w) == 1:
                            lines.append(f"Wilcoxon noSD {sex} " + p_text(float(w["p"].iloc[0])))
                for sex, lab in (("F", "Kruskal F "), ("M", "Kruskal M ")):
                    k = kr[
                        (kr["step"] == step)
                        & (kr["phase_layer"] == ph)
                        & (kr["sex"] == sex)
                        & (kr["metric"] == f"delta_{met}")
                    ]
                    if len(k) == 1:
                        lines.append(lab + p_text(float(k["p"].iloc[0])))
                ax.text(
                    0.03,
                    0.97,
                    "\n".join(lines),
                    transform=ax.transAxes,
                    va="top",
                    ha="left",
                    fontsize=5.5,
                    color=INK,
                    bbox=dict(
                        boxstyle="round,pad=0.15",
                        facecolor="white",
                        edgecolor="#dddddd",
                        lw=0.5,
                    ),
                )
        handles = [
            Line2D([0], [0], marker="o", color="none", markerfacecolor=TX_COLOR[t], markersize=6, label=t)
            for t in TX_ORDER
        ] + [
            Line2D(
                [0],
                [0],
                marker=SEX_MARKER[s],
                color="none",
                markerfacecolor=INK,
                markersize=6,
                label=s,
            )
            for s in SEX_ORDER
        ]
        fig.legend(handles=handles, loc="upper right", frameon=False, fontsize=7, ncol=5, bbox_to_anchor=(1.0, 1.10))
        fig.suptitle(
            f"Animal-level paired Δ of {METRIC_LAB[met]}  ·  median across {n_models} kpMS models",
            fontsize=10,
            fontweight="bold",
            color=INK,
            y=1.12,
        )
        note = _foot_violin(wilcoxon) + STEP_GLOSS
        if met in ("richness", "shannon_bits"):
            note = _foot_violin(wilcoxon) + FOOT_VIOLIN_COMPOSITION + STEP_GLOSS
        fig_footnote(fig, note, y=-0.07)
        save_pdf_png(fig, out / VIOLIN_STEM[met])



def _kruskal_hit_frac(sub: pd.DataFrame, phase: str, metric: str) -> float:
    cell = sub[(sub["phase_layer"] == phase) & (sub["metric"] == f"delta_{metric}")]
    if cell.empty:
        cell = sub[(sub["phase_layer"] == phase) & (sub["metric"] == metric)]
    if cell.empty:
        return float("nan")
    return float(cell["hit"].mean())


def _annotate_heatmap(ax, mat: np.ndarray) -> None:
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
                    fontsize=6.5,
                    color=text_on_cmap(v),
                )


def fig_tx_kruskal(tests: pd.DataFrame, out: Path) -> None:
    apply_style()
    kr = tests[tests["test"] == "kruskal"].copy()
    kr["hit"] = _as_bool(kr["hit_p05"])
    fig, axes = plt.subplots(2, 2, figsize=FIGSIZE_DOUBLE, constrained_layout=True)
    im = None
    for r, c, step, sex, letter in STEP_SEX_PANELS:
        ax = axes[r, c]
        sub = kr[(kr["step"] == step) & (kr["sex"] == sex)]
        mat = np.full((len(PHASES), len(METRICS)), np.nan)
        for i, ph in enumerate(PHASES):
            for j, met in enumerate(METRICS):
                mat[i, j] = _kruskal_hit_frac(sub, ph, met)
        im = ax.imshow(mat, cmap="viridis", vmin=0.0, vmax=1.0, aspect="auto")
        ax.set_xticks(range(len(METRICS)))
        ax.set_xticklabels([METRIC_LAB[m] for m in METRICS], rotation=35, ha="right", fontsize=7)
        ax.set_yticks(range(len(PHASES)))
        ax.set_yticklabels([PHASE_SHORT[p] for p in PHASES])
        ax.set_title(
            f"{letter}  {STEP_PLAIN[step]} · {SEX_LAB[sex]}\n{STEP_ARROW[step]}",
            loc="left",
            fontweight="bold",
            color=INK,
            fontsize=8,
        )
        _annotate_heatmap(ax, mat)
    fig.colorbar(im, ax=axes, fraction=0.025, pad=0.02, label="frac of 21 models with Kruskal p < 0.05")
    fig.suptitle(
        "Cross-model agreement: does treatment modulate the paired Δ? (Kruskal by tx, within sex)",
        fontsize=11,
        fontweight="bold",
        color=INK,
        y=1.08,
    )
    fig_footnote(
        fig,
        FOOT_KRUSKAL + STEP_GLOSS + " Kruskal metric names in tests_long are delta_*.",
        y=-0.10,
    )
    save_pdf_png(fig, out / "fig_presence_tx_kruskal")


def fig_consensus_wilcoxon(cons: pd.DataFrame, out: Path) -> None:
    apply_style()
    wx = restrict_tx_stratum(
        cons[(cons["test"] == "wilcoxon_signed_rank") & (cons["sex"] == "all")],
        TX_STRATUM_ALL,
    )
    fig, axes = plt.subplots(1, 2, figsize=FIGSIZE_DOUBLE, constrained_layout=True)
    im = None
    for ax, (step, title) in zip(axes, STEPS):
        im = _imshow_p(ax, _p_mat(wx[wx["step"] == step], metric_key="{met}"))
        ax.set_title(title, loc="left", fontweight="bold", color=INK)
    fig.colorbar(im, ax=axes, fraction=0.025, pad=0.02, label="−log₁₀(p)")
    fig.suptitle(
        "Consensus Δ (median across 21 models): does the paired step hit? (Wilcoxon, sex=all)",
        fontsize=11,
        fontweight="bold",
        color=INK,
        y=1.04,
    )
    fig_footnote(fig, FOOT_CONSENSUS_WX + STEP_GLOSS, y=-0.08)
    save_pdf_png(fig, out / "fig_presence_consensus_wilcoxon")


def fig_consensus_wilcoxon_by_sex(
    cons: pd.DataFrame, out: Path, *, wilcoxon: str = WILCOXON_POOLED
) -> None:
    apply_style()
    wx = restrict_tx_stratum(
        cons[cons["test"] == "wilcoxon_signed_rank"], _wx_stratum(wilcoxon)
    )
    wx = wx[wx["sex"].isin(SEX_ORDER)]
    fig, axes = plt.subplots(2, 2, figsize=FIGSIZE_CONSENSUS, constrained_layout=True)
    im = None
    for r, c, step, sex, letter in STEP_SEX_PANELS:
        ax = axes[r, c]
        sub = wx[(wx["step"] == step) & (wx["sex"] == sex)]
        im = _imshow_p(ax, _p_mat(sub, metric_key="{met}"))
        ax.set_title(
            f"{letter}  {STEP_PLAIN[step]} · {SEX_LAB[sex]}\n{STEP_ARROW[step]}",
            loc="left",
            fontweight="bold",
            color=INK,
            fontsize=8,
        )
    fig.colorbar(im, ax=axes, fraction=0.025, pad=0.02, label="−log₁₀(p)")
    fig.suptitle(
        "Consensus Δ (median across 21 models): does the paired step hit? (Wilcoxon, within sex)",
        fontsize=11,
        fontweight="bold",
        color=INK,
        y=1.08,
    )
    fig_footnote(
        fig,
        (
            FOOT_CONSENSUS_WX_BY_SEX_POOLED
            if wilcoxon == WILCOXON_POOLED
            else FOOT_CONSENSUS_WX_BY_SEX_NOSD
        )
        + STEP_GLOSS,
        y=-0.10,
    )
    save_pdf_png(fig, out / "fig_presence_consensus_wilcoxon_by_sex")


def fig_consensus_kruskal(cons: pd.DataFrame, out: Path) -> None:
    apply_style()
    kr = cons[cons["test"] == "kruskal"]
    fig, axes = plt.subplots(2, 2, figsize=FIGSIZE_CONSENSUS, constrained_layout=True)
    im = None
    for r, c, step, sex, letter in STEP_SEX_PANELS:
        ax = axes[r, c]
        sub = kr[(kr["step"] == step) & (kr["sex"] == sex)]
        im = _imshow_p(ax, _p_mat(sub, metric_key="delta_{met}"))
        ax.set_title(
            f"{letter}  {STEP_PLAIN[step]} · {SEX_LAB[sex]}\n{STEP_ARROW[step]}",
            loc="left",
            fontweight="bold",
            color=INK,
            fontsize=8,
        )
    fig.colorbar(im, ax=axes, fraction=0.025, pad=0.02, label="−log₁₀(p)")
    fig.suptitle(
        "Consensus Δ (median across 21 models): does treatment modulate Δ? (Kruskal by tx, within sex)",
        fontsize=11,
        fontweight="bold",
        color=INK,
        y=1.08,
    )
    fig_footnote(fig, FOOT_CONSENSUS_KR + STEP_GLOSS, y=-0.10)
    save_pdf_png(fig, out / "fig_presence_consensus_kruskal")


def fig_consensus_wilcoxon_iqr(salt_sum: pd.DataFrame, out: Path) -> None:
    apply_style()
    mats = [_iqr_mat(salt_sum[salt_sum["step"] == step]) for step, _title in STEPS]
    colors = _column_unit_color(mats)
    fig, axes = plt.subplots(1, 2, figsize=FIGSIZE_DOUBLE, constrained_layout=True)
    im = None
    for ax, (_step, title), mat, color in zip(axes, STEPS, mats, colors):
        im = _imshow_iqr(ax, mat, color)
        ax.set_title(title, loc="left", fontweight="bold", color=INK)
    fig.colorbar(im, ax=axes, fraction=0.025, pad=0.02, label="IQR (color 0–1 within metric)")
    fig.suptitle(
        "Across-model salt on consensus Δ: cohort median IQR (Wilcoxon grain, sex=all)",
        fontsize=11,
        fontweight="bold",
        color=INK,
        y=1.04,
    )
    fig_footnote(fig, FOOT_CONSENSUS_IQR + STEP_GLOSS, y=-0.08)
    save_pdf_png(fig, out / "fig_presence_consensus_wilcoxon_iqr")


def _fig_iqr_step_sex(
    salt_sum_sex: pd.DataFrame,
    out: Path,
    *,
    stem: str,
    title: str,
    grain_note: str,
) -> None:
    apply_style()
    mats: list[np.ndarray] = []
    for _r, _c, step, sex, _letter in STEP_SEX_PANELS:
        mats.append(
            _iqr_mat(salt_sum_sex[(salt_sum_sex["step"] == step) & (salt_sum_sex["sex"] == sex)])
        )
    colors = _column_unit_color(mats)
    fig, axes = plt.subplots(2, 2, figsize=FIGSIZE_CONSENSUS, constrained_layout=True)
    im = None
    for (r, c, step, sex, letter), mat, color in zip(STEP_SEX_PANELS, mats, colors):
        ax = axes[r, c]
        im = _imshow_iqr(ax, mat, color)
        ax.set_title(
            f"{letter}  {STEP_PLAIN[step]} · {SEX_LAB[sex]}\n{STEP_ARROW[step]}",
            loc="left",
            fontweight="bold",
            color=INK,
            fontsize=8,
        )
    fig.colorbar(im, ax=axes, fraction=0.025, pad=0.02, label="IQR (color 0–1 within metric)")
    fig.suptitle(title, fontsize=11, fontweight="bold", color=INK, y=1.08)
    fig_footnote(fig, FOOT_CONSENSUS_IQR + grain_note + STEP_GLOSS, y=-0.10)
    save_pdf_png(fig, out / stem)


def fig_consensus_wilcoxon_iqr_by_sex(
    salt_sum_sex: pd.DataFrame, out: Path, *, wilcoxon: str = WILCOXON_POOLED
) -> None:
    if wilcoxon == WILCOXON_POOLED:
        grain = (
            " Animals pooled across tx within sex (same salt table as Kruskal IQR when "
            "--wilcoxon pooled). "
        )
        title = (
            "Across-model salt on consensus Δ: cohort median IQR (Wilcoxon grain, within sex)"
        )
    else:
        grain = " Animals with tx=noSD only, within sex (evolution I salt grain). "
        title = (
            "Across-model salt on consensus Δ: cohort median IQR (Wilcoxon noSD, within sex)"
        )
    _fig_iqr_step_sex(
        salt_sum_sex,
        out,
        stem="fig_presence_consensus_wilcoxon_iqr_by_sex",
        title=title,
        grain_note=grain,
    )


def fig_consensus_kruskal_iqr(salt_sum_sex: pd.DataFrame, out: Path) -> None:
    _fig_iqr_step_sex(
        salt_sum_sex,
        out,
        stem="fig_presence_consensus_kruskal_iqr",
        title="Across-model salt on consensus Δ: cohort median IQR (Kruskal grain, within sex)",
        grain_note=" Animals pooled across tx within sex (same grain as Kruskal). ",
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--pilot-model", type=str, default=PILOT_MODEL)
    ap.add_argument(
        "--wilcoxon",
        choices=(WILCOXON_POOLED, WILCOXON_NOSD),
        default=WILCOXON_POOLED,
        help="By-sex/violin Wilcoxon: pooled tx (and sex=all on violins) vs noSD within sex.",
    )
    args = ap.parse_args(argv)
    run = args.run_dir
    out = args.out_dir or (run / "figures")
    agr = pd.read_csv(run / "presence_step_agreement_by_model.csv")
    tests = pd.read_csv(run / "presence_step_tests_long.csv")
    deltas = pd.read_csv(run / "presence_step_deltas_per_animal.csv")
    salt_path = run / "presence_step_across_model_dispersion.csv"
    salt_sum_path = run / "presence_step_across_model_dispersion_summary.csv"
    salt = pd.read_csv(salt_path) if salt_path.is_file() else None
    salt_sum = pd.read_csv(salt_sum_path) if salt_sum_path.is_file() else None
    cons = consensus_tests(animal_median_across_models(deltas))
    cons.to_csv(run / "presence_step_consensus_tests.csv", index=False)
    fig_frac_hit(agr, out)
    fig_frac_hit_by_sex(tests, out, wilcoxon=args.wilcoxon)
    fig_median_delta(agr, out)
    fig_paired_pilot(deltas, tests, out, model=args.pilot_model)
    fig_delta_violins(
        deltas, cons, out, salt=salt, salt_summary=salt_sum, wilcoxon=args.wilcoxon
    )
    fig_tx_kruskal(tests, out)
    fig_consensus_wilcoxon(cons, out)
    fig_consensus_wilcoxon_by_sex(cons, out, wilcoxon=args.wilcoxon)
    fig_consensus_kruskal(cons, out)
    salt_sum_sex = None
    salt_sum_sex_nosd = None
    if salt is not None and not salt.empty:
        salt_sum_sex = across_model_dispersion_summary(
            salt, group_keys=("sex", "phase_layer", "step", "metric")
        )
        salt_sum_sex.to_csv(
            run / "presence_step_across_model_dispersion_summary_by_sex.csv", index=False
        )
        salt_sum_sex_nosd = across_model_dispersion_summary(
            salt.loc[salt["tx"] == CONTROL_TX],
            group_keys=("sex", "phase_layer", "step", "metric"),
        )
        salt_sum_sex_nosd.to_csv(
            run / "presence_step_across_model_dispersion_summary_by_sex_noSD.csv",
            index=False,
        )
        if salt_sum is None:
            salt_sum = across_model_dispersion_summary(salt)
            salt_sum.to_csv(salt_sum_path, index=False)
    if salt_sum is not None and not salt_sum.empty:
        fig_consensus_wilcoxon_iqr(salt_sum, out)
    wx_iqr_sex = salt_sum_sex
    if args.wilcoxon == WILCOXON_NOSD:
        wx_iqr_sex = salt_sum_sex_nosd
    if wx_iqr_sex is not None and not wx_iqr_sex.empty:
        fig_consensus_wilcoxon_iqr_by_sex(wx_iqr_sex, out, wilcoxon=args.wilcoxon)
    if salt_sum_sex is not None and not salt_sum_sex.empty:
        fig_consensus_kruskal_iqr(salt_sum_sex, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
