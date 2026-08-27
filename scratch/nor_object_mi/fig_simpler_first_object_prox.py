"""Publication figures for per-object 0.10 m object-prox discrimination ratio.

Reads only CSVs listed in INFO_object_prox.md. Does not read upstream bout
tables.

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/fig_simpler_first_object_prox.py
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

from nor_object_mi._object_prox_labels import (  # noqa: E402
    OCC_LAB,
    OCC_METRICS,
    OCC_STEM,
    p_compact,
)
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
from nor_object_mi.simpler_first_object_prox import (  # noqa: E402
    animal_median_across_models,
)

DEFAULT_RUN = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017" r"\_nor_object_mi\simpler_first_object_prox_0p10")
NLP_VMAX = 4.0
SEX_LAB = {"F": "female", "M": "male"}
R2_M = 0.20

FOOT_OVERLAP = (
    "Grain: animal × phase × novel_obj (full session); geometry is bout-mean "
    "spot→object distance. Color in A is n animals with dual-gated frames; "
    "in B is min(d_fam + d_nvl) in meters (floor of the map is 2r = 0.20 m). "
    "21 kpMS models. This figure is a geometry audit, not a preference test "
    "and not a treatment claim. Not MI; not DA."
)
FOOT_WX_HIT = (
    "Grain: animal × phase × novel_obj. This figure: Wilcoxon signed-rank on "
    "DR vs 0, sex=all, txs pooled — a preference claim, not a treatment claim. "
    "Color: frac of 21 kpMS models with p < 0.05. Inclusive equals exclusive "
    "because overlap is zero. Uncorrected. Not MI; not DA."
)
FOOT_KR_DR = (
    "Grain: animal × phase × novel_obj. This figure is Kruskal–Wallis by tx "
    "(noSD, GHSD, RBSD) within sex, on DR — groups differ on a scalar. That is "
    "a treatment claim. Color: frac of 21 kpMS models with Kruskal p < 0.05 "
    "(uncorrected). Not the Wilcoxon hit rule (sex=all, txs pooled). Not MI; "
    "not DA; not PERMANOVA."
)
FOOT_KR_OCC = (
    "Grain: animal × phase × novel_obj. This figure is Kruskal–Wallis by tx "
    "within sex on occupancy in one prox window (frac_near_fam or frac_near_nvl) — a "
    "treatment claim on that scalar, not on DR. Color: frac of 21 kpMS models "
    "with Kruskal p < 0.05 (uncorrected). Occupancy can hit while DR misses. "
    "Not Wilcoxon; not MI; not DA."
)
FOOT_CONS_WX = (
    "Grain: one animal; each animal's DR is the median across 21 kpMS models. "
    "This figure is Wilcoxon signed-rank on that median DR vs 0. Color is "
    "−log₁₀(p), not frac of models that hit. Cell text is the p-value. txs "
    "pooled — not a treatment claim. Uncorrected p < 0.05. Inclusive = exclusive "
    "here. Not MI; not DA."
)
FOOT_CONS_KR = (
    "Grain: one animal; each animal's DR is the median across 21 kpMS models. "
    "This figure is Kruskal–Wallis by tx within sex on that median DR — a "
    "treatment claim (groups differ on a scalar). Color is −log₁₀(p), not frac "
    "of models that hit. Cell text is the p-value. Uncorrected. Not the Wilcoxon "
    "consensus. Not MI; not DA; not PERMANOVA."
)
FOOT_VIOLIN = (
    "Grain: animal × phase × novel_obj. Each point is one animal: the median of "
    "that animal's exclusive DR across 21 kpMS models. Thin whiskers = ±½ IQR of "
    "that animal's DR across models (across-model dispersion / salt), not SEM. "
    "Not 21 independent replicates of the same animal. Color=tx, shape=sex; "
    "violins are KDE of those medians by tx (sexes pooled in the KDE). Wilcoxon p "
    "is DR vs 0, txs pooled (not a treatment claim). Kruskal p is within sex on "
    "the same medians (treatment claim). Stats box also shows cohort median IQR. "
    "BL/TX n≈48 per tx arm; REC n≈24. Not MI; not DA."
)
FOOT_OCC = (
    "Grain: animal × phase × novel_obj. Each point is one animal: the median "
    "across 21 kpMS models of that prox window's occupancy (frames with bout-mean "
    "spot distance < 0.10 m / session frames). Color=tx, shape=sex. Kruskal p "
    "is within sex on those medians — a treatment claim on occupancy, not on DR. "
    "Y-scales are independent. Not Wilcoxon vs 0; not MI; not DA."
)



FOOT_OVERLAP_S = (
    "Object-prox geometry: dual-gated n and min(d_fam+d_nvl). Not preference, not treatment."
)
FOOT_WX_HIT_S = (
    "Agreement: Wilcoxon DR vs 0 (sex=all, txs pooled). Preference, not treatment. Color = frac of 21 models with p < 0.05."
)
FOOT_KR_DR_S = (
    "Agreement: Kruskal on DR by tx within sex. Treatment claim. Color = frac of 21 models with p < 0.05."
)
FOOT_KR_OCC_S = (
    "Agreement: Kruskal on fam/nvl occupancy by tx within sex. Treatment on occupancy, not DR."
)
FOOT_CONS_WX_S = (
    "Consensus Wilcoxon on median-across-models DR vs 0. Preference, not treatment. Color = −log₁₀(p)."
)
FOOT_CONS_KR_S = (
    "Consensus Kruskal on median DR by tx within sex. Treatment claim. Color = −log₁₀(p)."
)
FOOT_VIOLIN_S = (
    "Point = animal median exclusive DR across 21 models; whiskers = ±½ across-model IQR (salt). "
    "Wilcoxon vs 0 is preference (txs pooled). Kruskal by tx is within sex (treatment)."
)
FOOT_OCC_S = (
    "Each point is median occupancy in one object's 0.10 m prox window. "
    "Kruskal by tx is within sex (treatment on occupancy, not DR)."
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


def _model_short(name: str) -> str:
    return str(name).removeprefix("paramscan_")


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


def _annotate_frac(ax, mat: np.ndarray, *, dest: str, vmin: float = 0.0, vmax: float = 1.0) -> None:
    ts = type_scale(dest)
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
                    color=text_on_cmap(v, vmin=vmin, vmax=vmax),
                )


def _draw_tx_violins(
    ax,
    panel: pd.DataFrame,
    ycol: str,
    rng: np.random.Generator,
    *,
    dest: str,
    iqr_col: str | None = None,
) -> list[int]:
    """Strip + violin by tx. Optional ``iqr_col`` → ±½ IQR whiskers (salt)."""
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
    ax.set_xticks(positions)
    if dest == "slides":
        ax.set_xticklabels([])
        ax.tick_params(axis="x", length=3)
    else:
        ax.set_xticklabels(list(TX_ORDER), fontsize=ts["annotation"], rotation=35, ha="right")
    ax.set_xlim(-0.7, len(TX_ORDER) - 0.3)
    return ns


def fig_overlap(ov: pd.DataFrame, out: Path, *, dest: str = "slides") -> None:
    ts = _begin(dest)
    models = sorted(ov["model"].unique())
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 9.4 if dest == "slides" else 7.6), constrained_layout=True)
    overlap = np.full((len(models), len(PHASES)), np.nan)
    spacing = np.full((len(models), len(PHASES)), np.nan)
    for i, m in enumerate(models):
        for j, ph in enumerate(PHASES):
            row = ov[(ov["model"] == m) & (ov["phase_layer"] == ph)]
            if len(row) == 1:
                overlap[i, j] = float(row["n_animals_with_overlap"].iloc[0])
                spacing[i, j] = float(row["min_d_fam_plus_d_nvl"].iloc[0])
    ax = axes[0]
    im0 = ax.imshow(overlap, cmap="viridis", vmin=0.0, vmax=1.0, aspect="auto")
    ax.set_xticks(range(len(PHASES)))
    ax.set_xticklabels([PHASE_SHORT[p] for p in PHASES])
    ax.set_yticks(range(len(models)))
    ax.set_yticklabels([_model_short(m) for m in models], fontsize=ts["cell"])
    ax.set_title("A  Dual-gated animals", loc="left", fontweight="bold", color=INK, fontsize=ts["annotation"])
    for i in range(overlap.shape[0]):
        for j in range(overlap.shape[1]):
            v = overlap[i, j]
            if np.isfinite(v):
                ax.text(
                    j,
                    i,
                    f"{int(v)}",
                    ha="center",
                    va="center",
                    fontsize=ts["cell"],
                    color=text_on_cmap(v, vmin=0.0, vmax=1.0),
                )
    fig.colorbar(im0, ax=ax, fraction=0.035, pad=0.03, label="n animals with overlap")
    ax = axes[1]
    im1 = ax.imshow(spacing, cmap="viridis", vmin=R2_M, vmax=0.35, aspect="auto")
    ax.set_xticks(range(len(PHASES)))
    ax.set_xticklabels([PHASE_SHORT[p] for p in PHASES])
    ax.set_yticks(range(len(models)))
    ax.set_yticklabels([_model_short(m) for m in models], fontsize=ts["cell"])
    ax.set_title("B  Min d_fam + d_nvl (m)", loc="left", fontweight="bold", color=INK, fontsize=ts["annotation"])
    for i in range(spacing.shape[0]):
        for j in range(spacing.shape[1]):
            v = spacing[i, j]
            if np.isfinite(v):
                ax.text(
                    j,
                    i,
                    f"{v:.2f}",
                    ha="center",
                    va="center",
                    fontsize=ts["cell"],
                    color=text_on_cmap(v, cmap="viridis", vmin=R2_M, vmax=0.35),
                )
    fig.colorbar(im1, ax=ax, fraction=0.035, pad=0.03, label="min(d_fam + d_nvl) (m)")
    fig.suptitle(
        "Object-prox overlap audit: dual membership is zero; sums stay above 2r",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
        y=1.02,
    )
    fig_footnote(fig, _note(dest, FOOT_OVERLAP, FOOT_OVERLAP_S), y=-0.04)
    save_pdf_png(fig, out / "fig_object_prox_overlap")


def fig_frac_hit(agr: pd.DataFrame, out: Path, *, dest: str = "slides") -> None:
    ts = _begin(dest)
    metrics = ("dr_exclusive", "dr_inclusive")
    labels = ("exclusive DR", "inclusive DR")
    fig, ax = plt.subplots(figsize=FIGSIZE_DOUBLE, constrained_layout=True)
    mat = np.full((len(PHASES), len(metrics)), np.nan)
    for i, ph in enumerate(PHASES):
        for j, met in enumerate(metrics):
            row = agr[(agr["phase_layer"] == ph) & (agr["metric"] == met)]
            if len(row) == 1:
                mat[i, j] = float(row["frac_hit"].iloc[0])
    im = ax.imshow(mat, cmap="viridis", vmin=0.0, vmax=1.0, aspect="auto")
    ax.set_xticks(range(len(metrics)))
    ax.set_xticklabels(list(labels))
    ax.set_yticks(range(len(PHASES)))
    ax.set_yticklabels([PHASE_SHORT[p] for p in PHASES])
    ax.set_title("A  Wilcoxon DR vs 0", loc="left", fontweight="bold", color=INK)
    _annotate_frac(ax, mat, dest=dest)
    fig.colorbar(im, ax=ax, fraction=0.04, pad=0.03, label="frac of 21 models with Wilcoxon hit")
    fig.suptitle(
        "Cross-model agreement: does novel-prox preference hit (Wilcoxon, sex=all)?",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
        y=1.04,
    )
    fig_footnote(fig, _note(dest, FOOT_WX_HIT, FOOT_WX_HIT_S), y=-0.08)
    save_pdf_png(fig, out / "fig_object_prox_frac_hit")


def fig_tx_kruskal(tests: pd.DataFrame, out: Path, *, dest: str = "slides") -> None:
    ts = _begin(dest)
    kr = tests[(tests["test"] == "kruskal") & (tests["metric"] == "dr_exclusive")].copy()
    kr["hit"] = _as_bool(kr["hit_p05"])
    fig, axes = plt.subplots(1, 2, figsize=FIGSIZE_DOUBLE, constrained_layout=True)
    im = None
    for ax, sex, letter in zip(axes, SEX_ORDER, ("A", "B")):
        sub = kr[kr["sex"] == sex]
        mat = np.full((len(PHASES), 1), np.nan)
        for i, ph in enumerate(PHASES):
            cell = sub[sub["phase_layer"] == ph]
            if not cell.empty:
                mat[i, 0] = float(cell["hit"].mean())
        im = ax.imshow(mat, cmap="viridis", vmin=0.0, vmax=1.0, aspect="auto")
        ax.set_xticks([0])
        ax.set_xticklabels(["exclusive DR"])
        ax.set_yticks(range(len(PHASES)))
        ax.set_yticklabels([PHASE_SHORT[p] for p in PHASES])
        ax.set_title(f"{letter}  {SEX_LAB[sex]}", loc="left", fontweight="bold", color=INK)
        _annotate_frac(ax, mat, dest=dest)
    fig.colorbar(im, ax=axes, fraction=0.03, pad=0.02, label="frac of 21 models with Kruskal hit")
    fig.suptitle(
        "Cross-model agreement: does treatment modulate DR? (Kruskal by tx, within sex)",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
        y=1.06,
    )
    fig_footnote(fig, _note(dest, FOOT_KR_DR, FOOT_KR_DR_S), y=-0.10)
    save_pdf_png(fig, out / "fig_object_prox_tx_kruskal")


def fig_occupancy_kruskal(tests: pd.DataFrame, out: Path, *, dest: str = "slides") -> None:
    ts = _begin(dest)
    kr = tests[(tests["test"] == "kruskal") & (tests["metric"].isin(OCC_METRICS))].copy()
    kr["hit"] = _as_bool(kr["hit_p05"])
    fig, axes = plt.subplots(1, 2, figsize=FIGSIZE_DOUBLE, constrained_layout=True)
    im = None
    for ax, sex, letter in zip(axes, SEX_ORDER, ("A", "B")):
        sub = kr[kr["sex"] == sex]
        mat = np.full((len(PHASES), len(OCC_METRICS)), np.nan)
        for i, ph in enumerate(PHASES):
            for j, met in enumerate(OCC_METRICS):
                cell = sub[(sub["phase_layer"] == ph) & (sub["metric"] == met)]
                if not cell.empty:
                    mat[i, j] = float(cell["hit"].mean())
        im = ax.imshow(mat, cmap="viridis", vmin=0.0, vmax=1.0, aspect="auto")
        ax.set_xticks(range(len(OCC_METRICS)))
        ax.set_xticklabels([OCC_LAB[m] for m in OCC_METRICS])
        ax.set_yticks(range(len(PHASES)))
        ax.set_yticklabels([PHASE_SHORT[p] for p in PHASES])
        ax.set_title(f"{letter}  {SEX_LAB[sex]}", loc="left", fontweight="bold", color=INK)
        _annotate_frac(ax, mat, dest=dest)
    fig.colorbar(im, ax=axes, fraction=0.03, pad=0.02, label="frac of 21 models with Kruskal hit")
    fig.suptitle(
        "Cross-model agreement: does treatment change time in one prox window? (Kruskal)",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
        y=1.06,
    )
    fig_footnote(fig, _note(dest, FOOT_KR_OCC, FOOT_KR_OCC_S), y=-0.10)
    save_pdf_png(fig, out / "fig_object_prox_occupancy_kruskal")


def fig_consensus_wilcoxon(cons: pd.DataFrame, out: Path, *, dest: str = "slides") -> None:
    ts = _begin(dest)
    wx = cons[(cons["test"] == "wilcoxon_signed_rank") & (cons["sex"] == "all")]
    metrics = ("dr_exclusive", "dr_inclusive")
    labels = ("exclusive DR", "inclusive DR")
    fig, ax = plt.subplots(figsize=FIGSIZE_DOUBLE, constrained_layout=True)
    pmat = np.full((len(PHASES), len(metrics)), np.nan)
    for i, ph in enumerate(PHASES):
        for j, met in enumerate(metrics):
            cell = wx[(wx["phase_layer"] == ph) & (wx["metric"] == met)]
            if len(cell) == 1:
                pmat[i, j] = float(cell["p"].iloc[0])
    nlp = np.vectorize(_neglog10_p, otypes=[float])(pmat)
    im = ax.imshow(nlp, cmap="viridis", vmin=0.0, vmax=NLP_VMAX, aspect="auto")
    ax.set_xticks(range(len(metrics)))
    ax.set_xticklabels(list(labels))
    ax.set_yticks(range(len(PHASES)))
    ax.set_yticklabels([PHASE_SHORT[p] for p in PHASES])
    ax.set_title("A  Consensus Wilcoxon", loc="left", fontweight="bold", color=INK)
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
                    fontsize=ts["cell"],
                    color=text_on_cmap(nlp_v, vmin=0.0, vmax=NLP_VMAX),
                )
    fig.colorbar(im, ax=ax, fraction=0.04, pad=0.03, label="−log₁₀(p)")
    fig.suptitle(
        "Consensus DR (median across 21 models): does novel-prox preference hit?",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
        y=1.04,
    )
    fig_footnote(fig, _note(dest, FOOT_CONS_WX, FOOT_CONS_WX_S), y=-0.08)
    save_pdf_png(fig, out / "fig_object_prox_consensus_wilcoxon")


def fig_consensus_kruskal(cons: pd.DataFrame, out: Path, *, dest: str = "slides") -> None:
    ts = _begin(dest)
    kr = cons[(cons["test"] == "kruskal") & (cons["metric"] == "dr_exclusive")]
    fig, axes = plt.subplots(1, 2, figsize=FIGSIZE_DOUBLE, constrained_layout=True)
    im = None
    for ax, sex, letter in zip(axes, SEX_ORDER, ("A", "B")):
        sub = kr[kr["sex"] == sex]
        pmat = np.full((len(PHASES), 1), np.nan)
        for i, ph in enumerate(PHASES):
            cell = sub[sub["phase_layer"] == ph]
            if len(cell) == 1:
                pmat[i, 0] = float(cell["p"].iloc[0])
        nlp = np.vectorize(_neglog10_p, otypes=[float])(pmat)
        im = ax.imshow(nlp, cmap="viridis", vmin=0.0, vmax=NLP_VMAX, aspect="auto")
        ax.set_xticks([0])
        ax.set_xticklabels(["exclusive DR"])
        ax.set_yticks(range(len(PHASES)))
        ax.set_yticklabels([PHASE_SHORT[p] for p in PHASES])
        ax.set_title(f"{letter}  {SEX_LAB[sex]}", loc="left", fontweight="bold", color=INK)
        for i in range(pmat.shape[0]):
            p = pmat[i, 0]
            nlp_v = nlp[i, 0]
            if np.isfinite(p) and np.isfinite(nlp_v):
                ax.text(
                    0,
                    i,
                    _p_cell_text(p),
                    ha="center",
                    va="center",
                    fontsize=ts["cell"],
                    color=text_on_cmap(nlp_v, vmin=0.0, vmax=NLP_VMAX),
                )
    fig.colorbar(im, ax=axes, fraction=0.03, pad=0.02, label="−log₁₀(p)")
    fig.suptitle(
        "Consensus DR (median across 21 models): does treatment modulate DR?",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
        y=1.06,
    )
    fig_footnote(fig, _note(dest, FOOT_CONS_KR, FOOT_CONS_KR_S), y=-0.10)
    save_pdf_png(fig, out / "fig_object_prox_consensus_kruskal")


def fig_violin_dr(
    animals: pd.DataFrame,
    cons: pd.DataFrame,
    out: Path,
    *,
    dest: str = "slides",
    salt: pd.DataFrame | None = None,
    salt_summary: pd.DataFrame | None = None,
) -> None:
    ts = _begin(dest)
    med = animal_median_across_models(animals)
    iqr_col: str | None = None
    if salt is not None and not salt.empty:
        salt_ex = salt[salt["metric"] == "dr_exclusive"][
            ["animal_id", "sex", "tx", "phase_layer", "iqr"]
        ].rename(columns={"iqr": "iqr_across_models"})
        med = med.merge(salt_ex, on=["animal_id", "sex", "tx", "phase_layer"], how="left")
        iqr_col = "iqr_across_models"
    n_models = int(med["n_models"].iloc[0]) if len(med) else 0
    wx_all = cons[(cons["test"] == "wilcoxon_signed_rank") & (cons["sex"] == "all") & (cons["metric"] == "dr_exclusive")]
    kr = cons[(cons["test"] == "kruskal") & (cons["metric"] == "dr_exclusive")]
    rng = np.random.default_rng(0)
    if dest == "slides":
        fig, axes = plt.subplots(1, 4, figsize=FIGSIZE_SLIDES, sharey=True, layout="constrained")
    else:
        fig, axes = plt.subplots(1, 4, figsize=(7.2, 4.4), sharey=True, layout="constrained")
    ax_list = list(axes)
    for c, ph in enumerate(PHASES):
        ax = ax_list[c]
        panel = med[med["phase_layer"] == ph]
        ns = _draw_tx_violins(ax, panel, "dr_exclusive", rng, dest=dest, iqr_col=iqr_col)
        ax.axhline(0.0, color="#bbbbbb", lw=0.7, ls="--", zorder=0)
        nlab = "n=" + "/".join(str(n) for n in ns)
        w = wx_all[wx_all["phase_layer"] == ph]
        pf = pm = float("nan")
        for sex in SEX_ORDER:
            k = kr[(kr["phase_layer"] == ph) & (kr["sex"] == sex)]
            if len(k) == 1:
                if sex == "F":
                    pf = float(k["p"].iloc[0])
                else:
                    pm = float(k["p"].iloc[0])
        p_wx = float(w["p"].iloc[0]) if len(w) == 1 else float("nan")
        box = [
            nlab,
            "Wilcoxon vs 0  " + p_compact(p_wx),
            "Kruskal by tx (within sex)",
            f"F {p_compact(pf)}   M {p_compact(pm)}",
        ]
        if salt_summary is not None and not salt_summary.empty:
            srow = salt_summary[
                (salt_summary["phase_layer"] == ph) & (salt_summary["metric"] == "dr_exclusive")
            ]
            if len(srow) == 1:
                box.append(f"cohort med IQR={float(srow['median_of_iqr'].iloc[0]):.3g}")
        panel_stats_box(ax, box, dest=dest)
        if dest == "slides":
            ax.set_xlabel(PHASE_SHORT[ph], fontsize=ts["annotation"], color=INK, fontweight="bold")
        else:
            ax.set_title(PHASE_SHORT[ph], loc="left", fontweight="bold", color=INK, fontsize=ts["annotation"])
        if c == 0:
            ax.set_ylabel("exclusive DR")
    fig.suptitle(
        f"Animal-level exclusive DR  ·  median across {n_models} kpMS models",
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
    save_pdf_png(fig, out / "fig_object_prox_violin_dr")


def fig_occupancy(animals: pd.DataFrame, cons: pd.DataFrame, out: Path, *, dest: str = "slides") -> None:
    ts = _begin(dest)
    med = animal_median_across_models(animals)
    n_models = int(med["n_models"].iloc[0]) if len(med) else 0
    kr = cons[(cons["test"] == "kruskal") & (cons["metric"].isin(OCC_METRICS))]
    rng = np.random.default_rng(0)
    for met, stem in OCC_STEM.items():
        if dest == "slides":
            fig, axes = plt.subplots(1, 4, figsize=FIGSIZE_SLIDES, sharey=True, layout="constrained")
        else:
            fig, axes = plt.subplots(1, 4, figsize=(7.2, 4.4), sharey=True, layout="constrained")
        for c, ph in enumerate(PHASES):
            ax = axes[c]
            panel = med[med["phase_layer"] == ph]
            ns = _draw_tx_violins(ax, panel, met, rng, dest=dest)
            if c == 0:
                ax.set_ylabel(OCC_LAB[met], fontsize=ts["annotation"])
            nlab = "n=" + "/".join(str(n) for n in ns)
            pf = pm = float("nan")
            for sex in SEX_ORDER:
                k = kr[(kr["phase_layer"] == ph) & (kr["sex"] == sex) & (kr["metric"] == met)]
                if len(k) == 1:
                    if sex == "F":
                        pf = float(k["p"].iloc[0])
                    else:
                        pm = float(k["p"].iloc[0])
            panel_stats_box(
                ax,
                [nlab, "Kruskal by tx (within sex)", f"F {p_compact(pf)}   M {p_compact(pm)}"],
                dest=dest,
            )
            if dest == "slides":
                ax.set_xlabel(PHASE_SHORT[ph], fontsize=ts["annotation"], color=INK, fontweight="bold")
            else:
                ax.set_title(PHASE_SHORT[ph], loc="center", fontweight="bold", color=INK, fontsize=ts["annotation"])
        fig.suptitle(
            f"{OCC_LAB[met]} occupancy  ·  median across {n_models} kpMS models",
            fontsize=ts["suptitle"],
            fontweight="bold",
            color=INK,
            y=1.02,
        )
        fig_legend_and_footnote(
            fig,
            tx_sex_legend_handles(dest=dest),
            _note(dest, FOOT_OCC, FOOT_OCC_S),
            dest=dest,
        )
        save_pdf_png(fig, out / stem)
    for old in out.glob("fig_object_prox_occupancy.*"):
        if old.stem == "fig_object_prox_occupancy":
            old.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    args = ap.parse_args(argv)
    dest = args.dest
    run = args.run_dir
    out = args.out_dir or (run / "figures")
    animals = pd.read_csv(run / "object_prox_metrics_per_animal.csv")
    tests = pd.read_csv(run / "object_prox_tests_long.csv")
    ov = pd.read_csv(run / "object_prox_overlap_by_model.csv")
    agr = pd.read_csv(run / "object_prox_agreement_by_model.csv")
    cons = pd.read_csv(run / "object_prox_consensus_tests.csv")
    fig_overlap(ov, out, dest=dest)
    fig_frac_hit(agr, out, dest=dest)
    fig_tx_kruskal(tests, out, dest=dest)
    fig_occupancy_kruskal(tests, out, dest=dest)
    fig_consensus_wilcoxon(cons, out, dest=dest)
    fig_consensus_kruskal(cons, out, dest=dest)
    salt_path = run / "object_prox_across_model_dispersion.csv"
    salt_sum_path = run / "object_prox_across_model_dispersion_summary.csv"
    salt = pd.read_csv(salt_path) if salt_path.is_file() else None
    salt_sum = pd.read_csv(salt_sum_path) if salt_sum_path.is_file() else None
    fig_violin_dr(animals, cons, out, dest=dest, salt=salt, salt_summary=salt_sum)
    fig_occupancy(animals, cons, out, dest=dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
