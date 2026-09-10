"""Phase-paired equivalents of cluster-13 / cluster Kruskal overview figures.

Outputs (under ``simpler_first_phase_paired/``):
  fig_phase_paired_cluster13_tx_delta
  fig_phase_paired_cluster13_tx_delta_by_sex
  fig_phase_paired_cluster13_model_tx_kruskal_overview
  fig_phase_paired_cluster_tx_kruskal_overview

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/fig_cluster_tx_kruskal_phase_paired.py
  uv run python scratch/nor_object_mi/fig_cluster_tx_kruskal_phase_paired.py --by-sex-violin-only
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
    SEX_MARKER,
    SEX_ORDER,
    CONDITION_COLOR,
    CONDITION_ORDER,
    apply_style,
    fig_footnote,
    save_pdf_png,
    text_on_cmap,
    condition_sex_legend_handles,
    type_scale,
)
from nor_object_mi.simpler_first_phase_paired import (  # noqa: E402
    PAIRED_FOOT_LEAD,
    footnote_paired_n,
    paired_n_by_step,
    step_axis_label,
    step_axis_labels,
)
from nor_object_mi.cluster_tx_kruskal import (  # noqa: E402
    clusters_with_any_hit,
    order_cluster_ids,
)
from nor_object_mi.cluster_tx_kruskal_phase_paired import (  # noqa: E402
    COND_LAB,
    TRIALS,
    PHASE_STEPS,
    STEP_LAB,
    animal_delta_p_by_model,
    animal_median_delta_p,
    animal_median_delta_p_by_cluster,
    attach_cluster_ids,
    attach_model_cluster_deltas,
    cluster_syllable_ids,
    filter_mapped_deltas,
    kruskal_by_cluster_trial_session_step_sex,
    kruskal_by_trial_session_step_sex,
    kruskal_by_model_trial_session_step_sex,
    representative_cluster_ids,
)
from nor_object_mi.fig_cluster13_tx_delta import _draw_tx_sex_violins  # noqa: E402
from nor_object_mi.fig_cluster_tx_kruskal_common import (  # noqa: E402
    cluster_y_labels,
    fdr_mark,
    fig_hit_cooccurrence,
    summarize_hit_clusters,
)

DEFAULT_PP = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_phase_paired"
)
DEFAULT_DA = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_da"
)
DEFAULT_SIG = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_syllable_signatures"
)
DELTA_USECOLS = (
    "model",
    "animal_id",
    "sex",
    "condition",
    "session_step",
    "trial",
    "raw_syllable_id",
    "delta_p",
)
NLP_VMAX = 4.0
PANELS = (
    ("F", "no_obj", "Female · no_obj"),
    ("F", "id_obj", "Female · identical"),
    ("F", "nvl_obj", "Female · novel"),
    ("M", "no_obj", "Male · no_obj"),
    ("M", "id_obj", "Male · identical"),
    ("M", "nvl_obj", "Male · novel"),
)


def _p_cell_text(p: float) -> str:
    if not np.isfinite(p):
        return ""
    if p < 1e-4:
        return "<10^-4"
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
    ts = type_scale(dest)
    positions = list(range(len(CONDITION_ORDER)))
    bodies: list[np.ndarray] = []
    body_pos: list[int] = []
    body_color: list[str] = []
    for i, t in enumerate(CONDITION_ORDER):
        sub = panel[panel["condition"] == t]
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
            body_color.append(CONDITION_COLOR[t])
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
                        ecolor=CONDITION_COLOR[t],
                        elinewidth=0.7,
                        capsize=0,
                        alpha=0.35,
                        zorder=2,
                    )
                ax.scatter(
                    x[m],
                    y[m],
                    s=ts["violin_scatter"],
                    c=CONDITION_COLOR[t],
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
    ax.set_xlim(-0.7, len(CONDITION_ORDER) - 0.3)
    if xlabel:
        ax.set_xticklabels(list(CONDITION_ORDER), fontsize=ts["annotation"], rotation=35, ha="right")
    else:
        ax.set_xticklabels([])


def _p_mat_sex(kr: pd.DataFrame, sex: str) -> np.ndarray:
    mat = np.full((len(TRIALS), len(PHASE_STEPS)), np.nan)
    sub = kr[kr["sex"] == sex]
    for i, cond in enumerate(TRIALS):
        for j, step in enumerate(PHASE_STEPS):
            cell = sub[(sub["trial"] == cond) & (sub["session_step"] == step)]
            if len(cell) == 1:
                mat[i, j] = float(cell["p"].iloc[0])
    return mat


def _q_hit_mat(kr: pd.DataFrame, sex: str) -> np.ndarray:
    mat = np.zeros((len(TRIALS), len(PHASE_STEPS)), dtype=bool)
    sub = kr[kr["sex"] == sex]
    for i, cond in enumerate(TRIALS):
        for j, step in enumerate(PHASE_STEPS):
            cell = sub[(sub["trial"] == cond) & (sub["session_step"] == step)]
            if len(cell) == 1:
                mat[i, j] = bool(cell["hit_fdr05"].iloc[0])
    return mat


def _imshow_kruskal(
    ax,
    pmat: np.ndarray,
    hits: np.ndarray,
    *,
    title: str,
    ts: dict,
    n_map: dict[str, int],
) -> object:
    nlp = np.vectorize(_neglog10_p, otypes=[float])(pmat)
    im = ax.imshow(nlp, cmap="viridis", vmin=0.0, vmax=NLP_VMAX, aspect="auto")
    ax.set_xticks(range(len(PHASE_STEPS)))
    ax.set_xticklabels(step_axis_labels(n_map), fontsize=ts["annotation"])
    ax.set_yticks(range(len(TRIALS)))
    ax.set_yticklabels([COND_LAB[c] for c in TRIALS], fontsize=ts["annotation"])
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


def fig_cluster13_tx_delta(
    med: pd.DataFrame,
    kr: pd.DataFrame,
    out: Path,
    *,
    dest: str,
    n_map: dict[str, int],
    by_sex: bool = False,
) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    n_conds = len(TRIALS)
    n_steps = len(PHASE_STEPS)
    half = n_steps // 2
    fig_w, fig_h = FIGSIZE_SLIDES if dest == "slides" else (7.2, 6.8)
    fig_w *= max(1.0, n_steps / 4.0)
    if by_sex:
        fig_w *= 1.12
    fig_h += 1.15 * (n_conds - 2)
    fig = plt.figure(figsize=(fig_w, fig_h + (1.8 if dest == "slides" else 1.4)))
    gs = fig.add_gridspec(
        n_conds + 1,
        n_steps,
        left=0.08,
        right=0.98,
        top=0.90,
        bottom=0.16 if by_sex else 0.14,
        height_ratios=[1.15] * n_conds + [0.95],
        hspace=0.42,
        wspace=0.34 if by_sex else 0.28,
    )
    rng = np.random.default_rng(0)
    draw_violins = _draw_tx_sex_violins if by_sex else _draw_tx_violins
    violin_axes = []
    for i, cond in enumerate(TRIALS):
        for j, step in enumerate(PHASE_STEPS):
            ax = fig.add_subplot(gs[i, j], sharey=violin_axes[0] if violin_axes else None)
            violin_axes.append(ax)
            panel = med[(med["trial"] == cond) & (med["session_step"] == step)]
            draw_violins(
                ax,
                panel,
                "delta_p",
                rng,
                dest=dest,
                iqr_col="iqr_across_models",
                xlabel=(i == n_conds - 1),
            )
            if i == 0:
                ax.set_title(step_axis_label(step, n_map), loc="left", fontweight="bold", color=INK)
            if j == 0:
                ax.set_ylabel(f"{COND_LAB[cond]}\nΔp_k")
    ax_f = fig.add_subplot(gs[n_conds, 0:half])
    ax_m = fig.add_subplot(gs[n_conds, half:n_steps])
    im = None
    for ax, sex in ((ax_f, "F"), (ax_m, "M")):
        im = _imshow_kruskal(
            ax,
            _p_mat_sex(kr, sex),
            _q_hit_mat(kr, sex),
            title=f"Kruskal · {sex}",
            ts=ts,
            n_map=n_map,
        )
    cax = fig.add_axes([0.08, 0.105, 0.22, 0.012])
    fig.colorbar(im, cax=cax, orientation="horizontal", label="−log10(p)  (clip 4)")
    fig.legend(
        handles=condition_sex_legend_handles(dest=dest),
        loc="upper center",
        bbox_to_anchor=(0.62, 0.125),
        bbox_transform=fig.transFigure,
        frameon=False,
        fontsize=ts["legend"],
        ncol=5,
    )
    n_line = footnote_paired_n(n_map) if n_map else PAIRED_FOOT_LEAD.rstrip()
    family_n = n_conds * n_steps * 2
    if by_sex:
        suptitle = (
            "Within-animal paired pause syllable Δp_k by tx × sex  "
            "(cluster 13; six violins per panel; Kruskal within sex)"
        )
        violin_note = (
            "Six violins = separate KDE per tx × sex (F then M within each tx; shared y-axis). "
        )
        stem = "fig_phase_paired_cluster13_tx_delta_by_sex"
    else:
        suptitle = (
            "Within-animal paired pause syllable Δp_k by tx  (cluster 13; Kruskal within sex)"
        )
        violin_note = "Violin = KDE by tx (sexes in the same KDE). "
        stem = "fig_phase_paired_cluster13_tx_delta"
    fig.suptitle(
        suptitle,
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_footnote(
        fig,
        (
            n_line
            + " Point = animal median Δp_k across 21 mapped alphabets. Whiskers = ±½ IQR of that "
            "animal's Δp across models (salt), not SEM. "
            + violin_note
            + "Heatmaps: Kruskal Δp ~ tx within sex; cell = uncorrected p; * = BH q < 0.05 "
            f"in the {family_n}-cell family "
            f"({n_conds} conditions × {n_steps} phase steps × 2 sexes). Color = −log10(p). "
            "Not Wilcoxon vs 0; not alphabet-wide DA FDR."
        ),
        y=0.01,
        color=MUTE,
    )
    save_pdf_png(fig, out / stem)


def _row_step_mats(
    kr: pd.DataFrame,
    row_ids: list,
    row_col: str,
    *,
    sex: str,
    condition: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    pmat = np.full((len(row_ids), len(PHASE_STEPS)), np.nan)
    hits = np.zeros((len(row_ids), len(PHASE_STEPS)), dtype=bool)
    hits_col = np.zeros((len(row_ids), len(PHASE_STEPS)), dtype=bool)
    sub = kr[(kr["sex"] == sex) & (kr["trial"] == condition)]
    id_to_i = {rid: i for i, rid in enumerate(row_ids)}
    has_col = "hit_fdr05_col" in sub.columns
    for row in sub.itertuples(index=False):
        key = getattr(row, row_col)
        i = id_to_i.get(key)
        if i is None:
            continue
        try:
            j = PHASE_STEPS.index(str(row.session_step))
        except ValueError:
            continue
        pmat[i, j] = float(row.p)
        hits[i, j] = bool(row.hit_fdr05)
        if has_col:
            hits_col[i, j] = bool(row.hit_fdr05_col)
    return pmat, hits, hits_col


def _imshow_row_step(
    ax,
    pmat: np.ndarray,
    hits: np.ndarray,
    hits_col: np.ndarray,
    y_labels: list[str],
    *,
    title: str,
    ts: dict,
    ylabel: str,
    show_ylabel: bool,
    annotate_all_p: bool = False,
    ytick_fontsize: float | None = None,
    n_map: dict[str, int] | None = None,
) -> object:
    n_map = n_map or {}
    nlp = np.vectorize(_neglog10_p, otypes=[float])(pmat)
    im = ax.imshow(nlp, cmap="viridis", vmin=0.0, vmax=NLP_VMAX, aspect="auto")
    ax.set_xticks(range(len(PHASE_STEPS)))
    ax.set_xticklabels(step_axis_labels(n_map), fontsize=ts["annotation"])
    ax.set_yticks(range(len(y_labels)))
    yfs = float(ytick_fontsize if ytick_fontsize is not None else ts["cell"])
    if show_ylabel:
        ax.set_yticklabels(y_labels, fontsize=yfs, ha="right")
        ax.set_ylabel(ylabel)
        ax.tick_params(axis="y", pad=2)
    else:
        ax.set_yticklabels([])
    ax.set_title(title, loc="left", fontweight="bold", color=INK, fontsize=ts["annotation"])
    for i in range(pmat.shape[0]):
        for j in range(pmat.shape[1]):
            p = pmat[i, j]
            nlp_v = nlp[i, j]
            if not np.isfinite(p) or not np.isfinite(nlp_v):
                continue
            mark = fdr_mark(bool(hits[i, j]), bool(hits_col[i, j]))
            if not annotate_all_p and not mark:
                continue
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


def fig_cluster_overview(
    kr: pd.DataFrame,
    out: Path,
    *,
    dest: str,
    n_map: dict[str, int],
    stem: str = "fig_phase_paired_cluster_tx_kruskal_overview",
    suptitle: str | None = None,
    footnote_extra: str | None = None,
) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    cluster_ids = order_cluster_ids(kr["cluster_id"])
    y_labels = cluster_y_labels(cluster_ids)
    n_row = len(cluster_ids)
    fig_h = 16.0 if dest == "slides" else 12.0
    fig_w = 20.0 if dest == "slides" else 14.0
    fig, axes = plt.subplots(2, 3, figsize=(fig_w, fig_h), constrained_layout=False)
    fig.subplots_adjust(left=0.06, right=0.93, top=0.93, bottom=0.08, hspace=0.28, wspace=0.12)
    im = None
    for k, (ax, (sex, cond, title)) in enumerate(zip(axes.ravel(), PANELS)):
        pmat, hits, hits_col = _row_step_mats(
            kr, cluster_ids, "cluster_id", sex=sex, condition=cond
        )
        im = _imshow_row_step(
            ax,
            pmat,
            hits,
            hits_col,
            y_labels,
            title=title,
            ts=ts,
            ylabel="cluster_id",
            show_ylabel=(k in (0, 3)),
            n_map=n_map,
        )
    cax = fig.add_axes([0.94, 0.35, 0.012, 0.35])
    fig.colorbar(im, cax=cax, label="−log10(p)  (clip 4)")
    fig.suptitle(
        suptitle
        or (
            "Within-animal paired Kruskal Δp_k (frame_share) ~ tx by cluster × phase step  "
            "(within sex; * = panel BH; † = column BH)"
        ),
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    n_line = footnote_paired_n(n_map) if n_map else PAIRED_FOOT_LEAD.rstrip()
    foot = footnote_extra or (
        n_line
        + f" Row = HDBSCAN cluster_id incl. noise ({n_row} rows; "
        "representative syllable per model = max n_bouts). "
        "Column = phase step. Cell = Kruskal on animal median Δp_k across 21 alphabets. "
        "Color = −log10(uncorrected p); text on FDR marks. "
        f"* = panel BH ({n_row} × {len(PHASE_STEPS)} within sex × condition). "
        "† = column BH (clusters within sex × condition × phase step). "
        "Not Wilcoxon vs 0; not alphabet-wide DA FDR."
    )
    fig_footnote(fig, foot, fontsize=ts["footnote"], y=0.01, color=MUTE)
    save_pdf_png(fig, out / stem)


def fig_cluster_model_overview(
    kr: pd.DataFrame,
    out: Path,
    *,
    dest: str,
    n_map: dict[str, int],
    cluster_id: int,
) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    models = sorted(str(x) for x in kr["model"].unique())
    lab = "noise" if cluster_id < 0 else str(cluster_id)
    fig_h = 13.5 if dest == "slides" else 10.0
    fig_w = 26.0 if dest == "slides" else 18.0
    fig, axes = plt.subplots(2, 3, figsize=(fig_w, fig_h), constrained_layout=False)
    fig.subplots_adjust(left=0.28, right=0.92, top=0.93, bottom=0.08, hspace=0.32, wspace=0.14)
    im = None
    for k, (ax, (sex, cond, title)) in enumerate(zip(axes.ravel(), PANELS)):
        pmat, hits, _hits_col = _row_step_mats(kr, models, "model", sex=sex, condition=cond)
        hits_col = np.zeros_like(hits)
        im = _imshow_row_step(
            ax,
            pmat,
            hits,
            hits_col,
            models,
            title=title,
            ts=ts,
            ylabel="model",
            show_ylabel=(k in (0, 3)),
            annotate_all_p=True,
            ytick_fontsize=ts["cell"] * 0.85,
            n_map=n_map,
        )
    cax = fig.add_axes([0.93, 0.35, 0.01, 0.35])
    fig.colorbar(im, cax=cax, label="−log10(p)  (clip 4)")
    fig.suptitle(
        "Within-animal paired Kruskal Δp_k (frame_share) ~ tx by model × phase step  "
        f"(cluster {lab}; within sex; * = BH q < 0.05)",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    n_line = footnote_paired_n(n_map) if n_map else PAIRED_FOOT_LEAD.rstrip()
    fig_footnote(
        fig,
        (
            n_line
            + f" Row = kpMS model (cluster {lab} syllable; multi-id models merged by median Δp). "
            f"Cell text = uncorrected Kruskal p; * = BH q < 0.05 within the "
            f"{len(models) * len(PHASE_STEPS)}-cell panel. Color = −log10(p)."
        ),
        fontsize=ts["footnote"],
        y=0.01,
        color=MUTE,
    )
    stem = (
        "fig_phase_paired_cluster13_model_tx_kruskal_overview"
        if cluster_id == 13
        else f"fig_phase_paired_cluster{lab}_model_tx_kruskal_overview"
    )
    save_pdf_png(fig, out / stem)


def fig_cluster13_model_overview(kr: pd.DataFrame, out: Path, *, dest: str, n_map: dict[str, int]) -> None:
    fig_cluster_model_overview(kr, out, dest=dest, n_map=n_map, cluster_id=13)

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pp-dir", type=Path, default=DEFAULT_PP)
    ap.add_argument("--da-dir", type=Path, default=DEFAULT_DA)
    ap.add_argument("--sig-dir", type=Path, default=DEFAULT_SIG)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    ap.add_argument(
        "--by-sex-violin-only",
        action="store_true",
        help="Emit only fig_phase_paired_cluster13_tx_delta_by_sex (default: both violin variants)",
    )
    ap.add_argument(
        "--skip-drilldowns",
        action="store_true",
        help="Skip per-hit-cluster model overview figures",
    )
    args = ap.parse_args(argv)

    out = args.out_dir or (args.pp_dir / "figures")
    out.mkdir(parents=True, exist_ok=True)

    print("cluster 13 violin strip ...", flush=True)
    ids = pd.read_csv(args.da_dir / "duration_band_vs_da.csv", usecols=["model", "raw_syllable_id"])
    deltas = pd.read_csv(
        args.pp_dir / "phase_paired_da_deltas_per_animal.csv", usecols=list(DELTA_USECOLS)
    )
    n_map = paired_n_by_step(deltas)
    mapped13 = filter_mapped_deltas(deltas, ids)
    med13 = animal_median_delta_p(mapped13)
    kr13 = kruskal_by_trial_session_step_sex(med13)
    med13.to_csv(args.pp_dir / "phase_paired_cluster13_animal_median_delta_p.csv", index=False)
    kr13.to_csv(args.pp_dir / "phase_paired_cluster13_tx_kruskal.csv", index=False)
    if not args.by_sex_violin_only:
        fig_cluster13_tx_delta(med13, kr13, out, dest=args.dest, n_map=n_map, by_sex=False)
    fig_cluster13_tx_delta(med13, kr13, out, dest=args.dest, n_map=n_map, by_sex=True)
    if args.by_sex_violin_only:
        print("by-sex violin only; skipping cluster overviews.", flush=True)
        return 0

    print("cluster overview (incl. noise) ...", flush=True)
    proto = pd.read_csv(args.sig_dir / "syllable_prototypes_clustered.csv")
    rep = representative_cluster_ids(proto, include_noise=True)
    mapped = attach_cluster_ids(deltas, rep)
    med = animal_median_delta_p_by_cluster(mapped)
    kr = kruskal_by_cluster_trial_session_step_sex(med)
    med.to_csv(args.pp_dir / "phase_paired_cluster_animal_median_delta_p.csv", index=False)
    kr.to_csv(args.pp_dir / "phase_paired_cluster_tx_kruskal.csv", index=False)
    rep.to_csv(args.pp_dir / "phase_paired_cluster_representative_ids.csv", index=False)
    fig_cluster_overview(kr, out, dest=args.dest, n_map=n_map)

    hit_sum = summarize_hit_clusters(kr)
    print("hit co-occurrence ...", flush=True)
    hit_mat, jac = fig_hit_cooccurrence(
        kr,
        out,
        stem="fig_phase_paired_cluster_tx_kruskal_hit_cooccurrence",
        dest=args.dest,
        panel_cols=("sex", "trial"),
        locus_col="session_step",
        locus_order=PHASE_STEPS,
        title="Phase-paired cluster FDR hit co-occurrence (panel BH)",
        footnote=(
            "Left: binary panel FDR hits (hit_fdr05) across sex × condition × phase step. "
            "Right: Jaccard of those hit sets between clusters (incl. noise). "
            "Column-wise FDR († on overview) is exploratory and not used here."
        ),
        hit_col="hit_fdr05",
    )
    hit_mat.to_csv(args.pp_dir / "phase_paired_cluster_tx_kruskal_hit_loci.csv")
    jac.to_csv(args.pp_dir / "phase_paired_cluster_tx_kruskal_hit_jaccard.csv")
    hit_mat_col, jac_col = fig_hit_cooccurrence(
        kr,
        out,
        stem="fig_phase_paired_cluster_tx_kruskal_hit_cooccurrence_col",
        dest=args.dest,
        panel_cols=("sex", "trial"),
        locus_col="session_step",
        locus_order=PHASE_STEPS,
        title="Phase-paired cluster FDR hit co-occurrence (column BH)",
        footnote=(
            "Left: binary column FDR hits (hit_fdr05_col) across sex × condition × phase step. "
            "Right: Jaccard of those hit sets. Exploratory vs panel BH (*)."
        ),
        hit_col="hit_fdr05_col",
    )
    hit_mat_col.to_csv(args.pp_dir / "phase_paired_cluster_tx_kruskal_hit_loci_col.csv")
    jac_col.to_csv(args.pp_dir / "phase_paired_cluster_tx_kruskal_hit_jaccard_col.csv")

    print("cluster 13 model overview ...", flush=True)
    cmap13 = cluster_syllable_ids(proto, cluster_id=13)
    mapped_m = attach_model_cluster_deltas(deltas, cmap13)
    med_m = animal_delta_p_by_model(mapped_m)
    kr_m = kruskal_by_model_trial_session_step_sex(med_m)
    med_m.to_csv(args.pp_dir / "phase_paired_cluster13_model_animal_delta_p.csv", index=False)
    kr_m.to_csv(args.pp_dir / "phase_paired_cluster13_model_tx_kruskal.csv", index=False)
    cmap13.to_csv(args.pp_dir / "phase_paired_cluster13_syllable_map.csv", index=False)
    fig_cluster13_model_overview(kr_m, out, dest=args.dest, n_map=n_map)

    drill_ids = [c for c in clusters_with_any_hit(kr) if c != 13]
    if not args.skip_drilldowns and drill_ids:
        drill_dir = out / "cluster_model_drilldowns"
        drill_dir.mkdir(parents=True, exist_ok=True)
        for cid in drill_ids:
            print(f"model drilldown cluster {cid} ...", flush=True)
            cmap = cluster_syllable_ids(proto, cluster_id=cid)
            mapped_d = attach_model_cluster_deltas(deltas, cmap)
            med_d = animal_delta_p_by_model(mapped_d)
            kr_d = kruskal_by_model_trial_session_step_sex(med_d)
            lab = "noise" if cid < 0 else str(cid)
            med_d.to_csv(drill_dir / f"cluster{lab}_model_animal_delta_p.csv", index=False)
            kr_d.to_csv(drill_dir / f"cluster{lab}_model_tx_kruskal.csv", index=False)
            cmap.to_csv(drill_dir / f"cluster{lab}_syllable_map.csv", index=False)
            fig_cluster_model_overview(
                kr_d, drill_dir, dest=args.dest, n_map=n_map, cluster_id=cid
            )

    summary = {
        "n_cluster13_animal_cells": int(len(med13)),
        "n_cluster_animal_cells": int(len(med)),
        "n_clusters": int(rep["cluster_id"].nunique()),
        "include_noise": True,
        "n_models_cluster13": int(cmap13["model"].nunique()),
        "kruskal_fdr_cluster13_violin": int(kr13["hit_fdr05"].sum()),
        "kruskal_fdr_cluster_overview": {
            f"{sex}_{COND_LAB[cond]}": int(
                kr[(kr["sex"] == sex) & (kr["trial"] == cond)]["hit_fdr05"].sum()
            )
            for sex in ("F", "M")
            for cond in TRIALS
        },
        "kruskal_fdr_col_cluster_overview": {
            f"{sex}_{COND_LAB[cond]}": int(
                kr[(kr["sex"] == sex) & (kr["trial"] == cond)]["hit_fdr05_col"].sum()
            )
            for sex in ("F", "M")
            for cond in TRIALS
        },
        "n_hit_fdr05_panel": hit_sum["n_hit_fdr05_panel"],
        "n_hit_fdr05_col": hit_sum["n_hit_fdr05_col"],
        "clusters_panel_hit": hit_sum["clusters_panel_hit"],
        "clusters_col_only_hit": hit_sum["clusters_col_only_hit"],
        "clusters_any_hit": hit_sum["clusters_any_hit"],
        "model_drilldown_clusters": drill_ids,
    }
    (args.pp_dir / "phase_paired_cluster_tx_kruskal_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
