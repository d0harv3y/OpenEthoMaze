"""Slides packs: HDBSCAN-cluster frame-share violins + per-model Kruskal.

Builds CSVs into `_nor_object_mi/slides_pack/cluster{N}/` from the sibling DA
(differential abundance) run + syllable prototypes, then draws figures from
**only** those pack files. Dest default is slides.

Default clusters: 13, 17, 12, 3.

Figures per cluster:
- level (raw frame share): six-violin combined
- trial_step (prose phase-step): paired Δ across trials within session
- session_step (prose stage-step): paired Δ across sessions within trial
- per-model Kruskal heatmaps: level, phase-step, stage-step

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/fig_slides_pack.py --rebuild
  uv run python scratch/nor_object_mi/fig_slides_pack.py --clusters 13,17
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi._pub_style import (  # noqa: E402
    CONDITION_COLOR,
    CONDITION_ORDER,
    FIGSIZE_SLIDES,
    INK,
    MUTE,
    SESSION_SHORT,
    SESSIONS,
    SEX_MARKER,
    SEX_ORDER,
    apply_style,
    condition_sex_legend_handles,
    fig_footnote,
    fig_legend_and_footnote,
    p_text,
    save_pdf_svg,
    text_on_cmap,
    type_scale,
)
from nor_object_mi.cluster13_frame_share import (  # noqa: E402
    DELTA_USECOLS,
    SESSION_STEP_LAB,
    SESSION_STEP_NAMES,
    TRIAL_LAB,
    TRIAL_STEP_LAB,
    TRIAL_STEP_NAMES,
    build_cluster13_frame_share_pack,
)
from nor_object_mi.cluster_condition_kruskal import cluster_syllable_ids  # noqa: E402
from nor_object_mi.simpler_first_presence import TRIALS  # noqa: E402

DEFAULT_PACK_ROOT = Path(
    r"D:\sack\datas\impress\moseq_251017" r"\_nor_object_mi\slides_pack"
)
DEFAULT_DA = Path(r"D:\sack\datas\impress\moseq_251017" r"\_nor_object_mi\simpler_first_da")
DEFAULT_SIG = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_syllable_signatures"
)
DEFAULT_CLUSTERS = (13, 17, 12, 3)

NLP_VMAX = 4.0
SEX_LAB = {"F": "Female", "M": "Male"}


def _lab(cluster_id: int) -> str:
    return f"cluster{int(cluster_id)}"


def _pack_csv_names(cluster_id: int) -> dict[str, str]:
    p = _lab(cluster_id)
    return {
        "animal": f"{p}_animal_frame_share.csv",
        "kruskal": f"{p}_frame_share_kruskal.csv",
        "map": f"{p}_syllable_map.csv",
        "trial_step": f"{p}_trial_step_delta.csv",
        "trial_step_kr": f"{p}_trial_step_kruskal.csv",
        "session_step": f"{p}_session_step_delta.csv",
        "session_step_kr": f"{p}_session_step_kruskal.csv",
        "model_level_kr": f"{p}_per_model_level_kruskal.csv",
        "model_trial_kr": f"{p}_per_model_trial_step_kruskal.csv",
        "model_session_kr": f"{p}_per_model_session_step_kruskal.csv",
        "model_labels": f"{p}_model_labels.csv",
    }


def _fig_stem(cluster_id: int, suffix: str) -> str:
    return f"fig_{_lab(cluster_id)}_{suffix}"


def _foot_level(cluster_id: int) -> str:
    return (
        f"Grain: animal × session × trial. Point = median frame share of HDBSCAN "
        f"cluster-{cluster_id} syllable(s) across 21 kpMS models (within-model "
        "median if >1 syllable); whiskers = ±½ across-model IQR (salt), not SEM. "
        "Six violins = separate KDE per condition × sex (F then M within each "
        "condition; shared y-axis). Kruskal within sex; panel shows F and M p "
        "(uncorrected); * = BH q < 0.05 in the 24-cell family. Not paired Δ; "
        "not Wilcoxon vs 0."
    )


FOOT_TRIAL_STEP = (
    "Grain: animal × session × trial_step (prose: phase-step). Point = median "
    "paired Δ frame share (right − left trial) across 21 kpMS models; whiskers = "
    "±½ across-model IQR (salt). Six violins = condition × sex. Kruskal on Δ ~ "
    "condition within sex (tx modulation of the move); * = BH q < 0.05 in the "
    "24-cell family. Not Wilcoxon vs 0; not raw level; not DA alphabet FDR."
)
FOOT_SESSION_STEP = (
    "Grain: animal × trial × session_step (prose: stage-step). Point = median "
    "paired Δ frame share (right − left session) across 21 kpMS models; whiskers = "
    "±½ across-model IQR (salt). Six violins = condition × sex. Kruskal on Δ ~ "
    "condition within sex; * = BH q < 0.05 in the 36-cell family. Not Wilcoxon "
    "vs 0; not raw level; not DA alphabet FDR."
)
FOOT_MODEL_LEVEL = (
    "Per-model Kruskal on frame share ~ condition within sex. Panel grid: "
    "rows = trial (phase), cols = sex. Heatmap: y = kpMS model, x = session "
    "(stage). Color = −log₁₀(uncorrected p), clip 4; * = BH q < 0.05 within the "
    "panel (model × session). Not median-across-models consensus; not Wilcoxon vs 0."
)
FOOT_MODEL_TRIAL = (
    "Per-model Kruskal on paired phase-step Δ frame share ~ condition within sex. "
    "Panel grid: rows = trial_step (phase-step), cols = sex. Heatmap: y = kpMS "
    "model, x = session (stage). Color = −log₁₀(uncorrected p), clip 4; "
    "* = BH q < 0.05 within the panel (model × session). Not consensus; "
    "not Wilcoxon vs 0."
)
FOOT_MODEL_SESSION = (
    "Per-model Kruskal on paired stage-step Δ frame share ~ condition within sex. "
    "Panel grid: rows = trial (phase), cols = sex. Heatmap: y = kpMS model, "
    "x = session_step (stage-step). Color = −log₁₀(uncorrected p), clip 4; "
    "* = BH q < 0.05 within the panel (model × session_step). Not consensus "
    "median-across-models; not Wilcoxon vs 0."
)


def _clear_legacy(pack: Path, out: Path, *, cluster_id: int) -> None:
    for name in ("kruskal_classic_dr.csv", "kruskal_object_prox_dr.csv"):
        p = pack / name
        if p.exists():
            p.unlink()
            print(f"removed {p}")
    if out.exists():
        for stem in (
            "fig_dr_kruskal_classic",
            "fig_dr_kruskal_object_prox",
            _fig_stem(cluster_id, "frame_share_female"),
            _fig_stem(cluster_id, "frame_share_male"),
            _fig_stem(cluster_id, "frame_share_kruskal"),
        ):
            for suf in (".pdf", ".svg", ".png"):
                p = out / f"{stem}{suf}"
                if p.exists():
                    p.unlink()
                    print(f"removed {p}")


def rebuild_pack(
    *,
    pack: Path,
    da_dir: Path,
    sig_dir: Path,
    cluster_id: int,
) -> dict[str, pd.DataFrame]:
    """Write level + step + per-model CSVs into the cluster pack folder."""
    pack.mkdir(parents=True, exist_ok=True)
    names = _pack_csv_names(cluster_id)
    print(f"reading prototypes + DA deltas for cluster {cluster_id} ...", flush=True)
    proto = pd.read_csv(sig_dir / "syllable_prototypes_clustered.csv")
    cmap = cluster_syllable_ids(proto, cluster_id=cluster_id)
    deltas = pd.read_csv(da_dir / "da_syllable_deltas_per_animal.csv", usecols=list(DELTA_USECOLS))
    tables = build_cluster13_frame_share_pack(deltas, cmap, cluster_id=cluster_id)
    writes = (
        (names["animal"], tables["animal_frame_share"]),
        (names["kruskal"], tables["kruskal_level"]),
        (names["map"], tables["id_map"]),
        (names["trial_step"], tables["trial_step_delta"]),
        (names["trial_step_kr"], tables["kruskal_trial_step"]),
        (names["session_step"], tables["session_step_delta"]),
        (names["session_step_kr"], tables["kruskal_session_step"]),
        (names["model_level_kr"], tables["kruskal_per_model_level"]),
        (names["model_trial_kr"], tables["kruskal_per_model_trial_step"]),
        (names["model_session_kr"], tables["kruskal_per_model_session_step"]),
        (names["model_labels"], tables["model_labels"]),
    )
    for name, df in writes:
        df.to_csv(pack / name, index=False)
        print(f"wrote {pack / name}  n={len(df)}", flush=True)
    return tables


def _condition_sex_position(condition: str, sex: str) -> float:
    return float(CONDITION_ORDER.index(condition) * len(SEX_ORDER) + SEX_ORDER.index(sex))


def _y_lim_from(df: pd.DataFrame, ycol: str) -> tuple[float, float]:
    y = pd.to_numeric(df[ycol], errors="coerce").to_numpy(dtype=float)
    y = y[np.isfinite(y)]
    if not y.size:
        return (-0.05, 0.05) if ycol == "delta_p" else (0.0, 0.05)
    iqr = pd.to_numeric(df["iqr_across_models"], errors="coerce").to_numpy(dtype=float)
    iqr = iqr[np.isfinite(iqr)]
    pad = 0.5 * float(np.nanmax(iqr)) if iqr.size else 0.0
    lo = float(np.nanmin(y)) - pad
    hi = float(np.nanmax(y)) + pad
    if ycol == "delta_p":
        span = max(0.05, hi - lo)
        mid = 0.5 * (hi + lo)
        return (mid - 0.55 * span, mid + 0.55 * span)
    return (0.0, max(0.05, hi) * 1.05)


def _draw_condition_sex_violins(
    ax,
    panel: pd.DataFrame,
    *,
    dest: str,
    rng: np.random.Generator,
    xlabel: bool,
    ycol: str = "p",
    zero_line: bool = False,
) -> None:
    """Six violins: F then M within each condition (separate KDEs, shared y)."""
    ts = type_scale(dest)
    n_tx = len(CONDITION_ORDER)
    positions = [_condition_sex_position(t, s) for t in CONDITION_ORDER for s in SEX_ORDER]
    bodies: list[np.ndarray] = []
    body_pos: list[float] = []
    body_color: list[str] = []
    for condition in CONDITION_ORDER:
        for sex in SEX_ORDER:
            pos = _condition_sex_position(condition, sex)
            sub = panel[(panel["condition"] == condition) & (panel["sex"] == sex)]
            y = pd.to_numeric(sub[ycol], errors="coerce").to_numpy(dtype=float)
            iqr = pd.to_numeric(sub["iqr_across_models"], errors="coerce").to_numpy(dtype=float)
            finite = np.isfinite(y)
            y, iqr = y[finite], iqr[finite]
            if y.size >= 2 and np.unique(y).size >= 2:
                bodies.append(y)
                body_pos.append(pos)
                body_color.append(CONDITION_COLOR[condition])
            if y.size:
                x = np.full(y.shape, pos) + rng.normal(0.0, 0.04, size=y.size)
                half = np.where(np.isfinite(iqr), 0.5 * iqr, np.nan)
                if np.any(np.isfinite(half)):
                    ax.errorbar(
                        x,
                        y,
                        yerr=np.where(np.isfinite(half), half, 0.0),
                        fmt="none",
                        ecolor=CONDITION_COLOR[condition],
                        elinewidth=0.7,
                        capsize=0,
                        alpha=0.35,
                        zorder=2,
                    )
                ax.scatter(
                    x,
                    y,
                    s=ts["violin_scatter"],
                    c=CONDITION_COLOR[condition],
                    marker=SEX_MARKER[sex],
                    alpha=0.75,
                    edgecolors="none",
                    zorder=3,
                )
                ax.plot(
                    [pos - 0.18, pos + 0.18],
                    [float(np.median(y))] * 2,
                    color=INK,
                    lw=1.5,
                    zorder=4,
                )
    if bodies:
        parts = ax.violinplot(
            bodies,
            positions=body_pos,
            widths=0.62,
            showmeans=False,
            showmedians=False,
            showextrema=False,
        )
        for pc, col in zip(parts["bodies"], body_color):
            pc.set_facecolor(col)
            pc.set_edgecolor("none")
            pc.set_alpha(0.32)
            pc.set_zorder(1)
    if zero_line:
        ax.axhline(0.0, color="#bbbbbb", lw=0.8, ls="--", zorder=0)
    ax.set_xlim(-0.55, n_tx * len(SEX_ORDER) - 0.45)
    if xlabel:
        ax.set_xticks([i * len(SEX_ORDER) + 0.5 for i in range(n_tx)])
        ax.set_xticklabels(list(CONDITION_ORDER), fontsize=ts["annotation"], rotation=35, ha="right")
        for i in range(n_tx):
            for s_idx, sex in enumerate(SEX_ORDER):
                ax.text(
                    i * len(SEX_ORDER) + s_idx,
                    -0.11,
                    sex,
                    transform=ax.get_xaxis_transform(),
                    ha="center",
                    va="top",
                    fontsize=ts["annotation"] * 0.85,
                    color=MUTE,
                )
        ax.tick_params(axis="x", pad=16)
    else:
        ax.set_xticks(positions)
        ax.set_xticklabels([])


def _cell_stats(
    kr: pd.DataFrame,
    *,
    sex: str,
    filters: dict[str, str],
) -> dict[str, object]:
    mask = kr["sex"] == sex
    for col, val in filters.items():
        mask = mask & (kr[col] == val)
    cell = kr[mask]
    if len(cell) != 1:
        return {"p": float("nan"), "hit_fdr05": False, "n": 0}
    row = cell.iloc[0]
    return {"p": float(row["p"]), "hit_fdr05": bool(row["hit_fdr05"]), "n": int(row["n"])}


def _annotate_fm(ax, kr: pd.DataFrame, *, filters: dict[str, str], dest: str) -> None:
    ts = type_scale(dest)
    lines: list[str] = []
    for sex in SEX_ORDER:
        stats = _cell_stats(kr, sex=sex, filters=filters)
        mark = "*" if stats["hit_fdr05"] else ""
        lines.append(f"{sex}: {mark}{p_text(float(stats['p']))}  n={int(stats['n'])}")
    ax.text(
        0.98,
        0.96,
        "\n".join(lines),
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=ts["cell"] * 0.9,
        color=INK,
        linespacing=1.15,
    )


def fig_frame_share_by_condition_sex(
    med: pd.DataFrame,
    kr: pd.DataFrame,
    out: Path,
    *,
    dest: str,
    cluster_id: int,
) -> None:
    """3×4 trial × session; six violins (F|M within each condition)."""
    apply_style(dest=dest)
    ts = type_scale(dest)
    fig_w, fig_h = FIGSIZE_SLIDES if dest == "slides" else (7.2, 8.0)
    fig = plt.figure(figsize=(fig_w * 1.08, fig_h + 0.8))
    gs = fig.add_gridspec(
        len(TRIALS),
        len(SESSIONS),
        left=0.07,
        right=0.98,
        top=0.88,
        bottom=0.22,
        hspace=0.42,
        wspace=0.30,
    )
    rng = np.random.default_rng(0)
    y_lim = _y_lim_from(med, "p")
    violin_axes: list = []
    for i, trial in enumerate(TRIALS):
        for j, session in enumerate(SESSIONS):
            ax = fig.add_subplot(gs[i, j], sharey=violin_axes[0] if violin_axes else None)
            violin_axes.append(ax)
            panel = med[(med["session"] == session) & (med["trial"] == trial)]
            _draw_condition_sex_violins(
                ax,
                panel,
                dest=dest,
                rng=rng,
                xlabel=(i == len(TRIALS) - 1),
            )
            ax.set_ylim(*y_lim)
            _annotate_fm(ax, kr, filters={"session": session, "trial": trial}, dest=dest)
            if i == 0:
                ax.set_title(SESSION_SHORT[session], loc="left", fontweight="bold", color=INK)
            if j == 0:
                ax.set_ylabel(f"{TRIAL_LAB[trial]}\nframe share")
    fig.suptitle(
        f"Cluster {cluster_id} syllable frame share by condition × sex  (six violins)",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_legend_and_footnote(fig, condition_sex_legend_handles(dest=dest), _foot_level(cluster_id), dest=dest)
    save_pdf_svg(fig, out / _fig_stem(cluster_id, "frame_share_by_sex"))


def fig_trial_step_delta_by_sex(
    med: pd.DataFrame,
    kr: pd.DataFrame,
    out: Path,
    *,
    dest: str,
    cluster_id: int,
) -> None:
    """3×4 trial_step × session (phase-step) Δ violins."""
    apply_style(dest=dest)
    ts = type_scale(dest)
    fig_w, fig_h = FIGSIZE_SLIDES if dest == "slides" else (7.2, 8.0)
    fig = plt.figure(figsize=(fig_w * 1.08, fig_h + 0.8))
    gs = fig.add_gridspec(
        len(TRIAL_STEP_NAMES),
        len(SESSIONS),
        left=0.07,
        right=0.98,
        top=0.88,
        bottom=0.22,
        hspace=0.42,
        wspace=0.30,
    )
    rng = np.random.default_rng(0)
    y_lim = _y_lim_from(med, "delta_p")
    violin_axes: list = []
    for i, step in enumerate(TRIAL_STEP_NAMES):
        for j, session in enumerate(SESSIONS):
            ax = fig.add_subplot(gs[i, j], sharey=violin_axes[0] if violin_axes else None)
            violin_axes.append(ax)
            panel = med[(med["session"] == session) & (med["trial_step"] == step)]
            _draw_condition_sex_violins(
                ax,
                panel,
                dest=dest,
                rng=rng,
                xlabel=(i == len(TRIAL_STEP_NAMES) - 1),
                ycol="delta_p",
                zero_line=True,
            )
            ax.set_ylim(*y_lim)
            _annotate_fm(ax, kr, filters={"session": session, "trial_step": step}, dest=dest)
            if i == 0:
                ax.set_title(SESSION_SHORT[session], loc="left", fontweight="bold", color=INK)
            if j == 0:
                ax.set_ylabel(f"{TRIAL_STEP_LAB[step]}\nΔ frame share")
    fig.suptitle(
        f"Cluster {cluster_id} Δ frame share by trial-step × condition × sex",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_legend_and_footnote(fig, condition_sex_legend_handles(dest=dest), FOOT_TRIAL_STEP, dest=dest)
    save_pdf_svg(fig, out / _fig_stem(cluster_id, "trial_step_delta_by_sex"))


def fig_session_step_delta_by_sex(
    med: pd.DataFrame,
    kr: pd.DataFrame,
    out: Path,
    *,
    dest: str,
    cluster_id: int,
) -> None:
    """3×6 trial × session_step (stage-step) Δ violins."""
    apply_style(dest=dest)
    ts = type_scale(dest)
    fig_w = 14.5 if dest == "slides" else 10.0
    fig_h = 7.8 if dest == "slides" else 6.5
    fig = plt.figure(figsize=(fig_w, fig_h))
    gs = fig.add_gridspec(
        len(TRIALS),
        len(SESSION_STEP_NAMES),
        left=0.06,
        right=0.99,
        top=0.88,
        bottom=0.22,
        hspace=0.45,
        wspace=0.28,
    )
    rng = np.random.default_rng(0)
    y_lim = _y_lim_from(med, "delta_p")
    violin_axes: list = []
    for i, trial in enumerate(TRIALS):
        for j, step in enumerate(SESSION_STEP_NAMES):
            ax = fig.add_subplot(gs[i, j], sharey=violin_axes[0] if violin_axes else None)
            violin_axes.append(ax)
            panel = med[(med["trial"] == trial) & (med["session_step"] == step)]
            _draw_condition_sex_violins(
                ax,
                panel,
                dest=dest,
                rng=rng,
                xlabel=(i == len(TRIALS) - 1),
                ycol="delta_p",
                zero_line=True,
            )
            ax.set_ylim(*y_lim)
            _annotate_fm(ax, kr, filters={"trial": trial, "session_step": step}, dest=dest)
            if i == 0:
                ax.set_title(SESSION_STEP_LAB[step], loc="left", fontweight="bold", color=INK)
            if j == 0:
                ax.set_ylabel(f"{TRIAL_LAB[trial]}\nΔ frame share")
    fig.suptitle(
        f"Cluster {cluster_id} Δ frame share by session-step × condition × sex",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_legend_and_footnote(fig, condition_sex_legend_handles(dest=dest), FOOT_SESSION_STEP, dest=dest)
    save_pdf_svg(fig, out / _fig_stem(cluster_id, "session_step_delta_by_sex"))


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


def _model_x_mats(
    kr: pd.DataFrame,
    *,
    models: list[str],
    x_values: list[str],
    x_col: str,
    row_value: str,
    row_col: str,
    sex: str,
) -> tuple[np.ndarray, np.ndarray]:
    pmat = np.full((len(models), len(x_values)), np.nan)
    hits = np.zeros((len(models), len(x_values)), dtype=bool)
    sub = kr[(kr[row_col].astype(str) == row_value) & (kr["sex"] == sex)]
    for i, model in enumerate(models):
        for j, xv in enumerate(x_values):
            cell = sub[(sub["model"].astype(str) == model) & (sub[x_col].astype(str) == xv)]
            if len(cell) == 1:
                pmat[i, j] = float(cell["p"].iloc[0])
                hits[i, j] = bool(cell["hit_fdr05"].iloc[0])
    return pmat, hits


def _imshow_model_x(
    ax,
    pmat: np.ndarray,
    hits: np.ndarray,
    *,
    y_labels: list[str],
    x_labels: list[str],
    title: str,
    ts: dict,
    show_ylabel: bool,
    ylabel: str = "model",
) -> object:
    nlp = np.vectorize(_neglog10_p, otypes=[float])(pmat)
    im = ax.imshow(nlp, cmap="viridis", vmin=0.0, vmax=NLP_VMAX, aspect="auto")
    ax.set_xticks(range(len(x_labels)))
    ax.set_xticklabels(x_labels, fontsize=ts["annotation"], rotation=35, ha="right")
    ax.set_yticks(range(len(y_labels)))
    if show_ylabel:
        ax.set_yticklabels(y_labels, fontsize=ts["cell"] * 0.8)
        if ylabel:
            ax.set_ylabel(ylabel, fontsize=ts["annotation"])
    else:
        ax.set_yticklabels([])
    ax.set_title(title, loc="left", fontweight="bold", color=INK)
    for i in range(pmat.shape[0]):
        for j in range(pmat.shape[1]):
            p = pmat[i, j]
            nlp_v = nlp[i, j]
            if not (np.isfinite(p) and np.isfinite(nlp_v)):
                continue
            mark = "*" if hits[i, j] else ""
            ax.text(
                j,
                i,
                mark + _p_cell_text(p),
                ha="center",
                va="center",
                fontsize=ts["cell"] * 0.7,
                color=text_on_cmap(nlp_v, vmin=0.0, vmax=NLP_VMAX),
            )
    return im


def fig_per_model_kruskal_heatmap(
    kr: pd.DataFrame,
    labels: pd.DataFrame,
    out: Path,
    *,
    dest: str,
    row_col: str,
    row_values: list[str],
    row_lab: dict[str, str],
    x_col: str,
    x_values: list[str],
    x_lab: dict[str, str],
    stem: str,
    title: str,
    footnote: str,
) -> None:
    """Panel grid: rows=row_col × cols=sex; heatmap y=model, x=x_col."""
    apply_style(dest=dest)
    ts = type_scale(dest)
    lab_map = dict(zip(labels["model"].astype(str), labels["label"].astype(str)))
    models = sorted(str(x) for x in kr["model"].unique())
    y_labels = [lab_map.get(m, m.split("_")[-1][:12]) for m in models]
    x_labels = [x_lab.get(x, x) for x in x_values]
    n_row = len(row_values)
    fig_w = 12.0 if dest == "slides" else 9.0
    fig_h = (4.5 * n_row + 0.5) if dest == "slides" else (3.5 * n_row + 0.5)
    fig, axes = plt.subplots(
        n_row,
        len(SEX_ORDER),
        figsize=(fig_w, fig_h),
        constrained_layout=False,
        squeeze=False,
    )
    fig.subplots_adjust(left=0.10, right=0.90, top=0.92, bottom=0.08, hspace=0.35, wspace=0.18)
    im = None
    for i, rv in enumerate(row_values):
        for j, sex in enumerate(SEX_ORDER):
            ax = axes[i, j]
            pmat, hits = _model_x_mats(
                kr,
                models=models,
                x_values=list(x_values),
                x_col=x_col,
                row_value=rv,
                row_col=row_col,
                sex=sex,
            )
            im = _imshow_model_x(
                ax,
                pmat,
                hits,
                y_labels=y_labels,
                x_labels=x_labels,
                title=f"{SEX_LAB[sex]} · {row_lab.get(rv, rv)}",
                ts=ts,
                show_ylabel=(j == 0),
            )
    cax = fig.add_axes([0.92, 0.30, 0.015, 0.40])
    fig.colorbar(im, cax=cax, label="−log₁₀(p)  (clip 4)")
    fig.suptitle(title, fontsize=ts["suptitle"], fontweight="bold", color=INK)
    fig_footnote(fig, footnote, y=0.02, color=MUTE)
    save_pdf_svg(fig, out / stem)


def write_info_md(pack: Path, *, cluster_id: int) -> None:
    names = _pack_csv_names(cluster_id)
    lab = _lab(cluster_id)
    stem_level = _fig_stem(cluster_id, "frame_share_by_sex")
    stem_m_level = _fig_stem(cluster_id, "per_model_level_kruskal")
    stem_m_trial = _fig_stem(cluster_id, "per_model_trial_step_kruskal")
    stem_m_session = _fig_stem(cluster_id, "per_model_session_step_kruskal")
    stem_trial = _fig_stem(cluster_id, "trial_step_delta_by_sex")
    stem_session = _fig_stem(cluster_id, "session_step_delta_by_sex")
    text = f"""# INFO — slides pack: cluster {cluster_id} frame share

Curated PowerPoint figures. The figure script reads **only** the CSVs in this
folder after `--rebuild` (or when those files already exist).

| | |
| --- | --- |
| These files | `sack/datas/impress/moseq_251017/_nor_object_mi/slides_pack/{lab}/` |
| Dest | slides (default) |
| How regenerated | `uv run python scratch/nor_object_mi/fig_slides_pack.py --rebuild --clusters {cluster_id}` |

**kpMS** = keypoint-MoSeq. **DA** = differential abundance. **BH** =
Benjamini–Hochberg. **Kruskal** = Kruskal–Wallis.

## Questions

1. **Level:** Within sex, does **condition** change cluster-{cluster_id} **frame share**
   at each `session × trial`?
2. **Trial-step** (prose *phase-step*): Within sex, does condition modulate the
   paired Δ across trials (presence / novelty / span) inside a session?
3. **Session-step** (prose *stage-step*): Within sex, does condition modulate the
   paired Δ across sessions (BL→TX …) inside a trial?
4. **Per-model level:** Same level question, separately per kpMS model
   (heatmap over models × sessions; panels = trial × sex).
5. **Per-model phase-step:** Same trial-step question, separately per model
   (heatmap over models × sessions; panels = trial_step × sex).
6. **Per-model stage-step:** Same session-step question, separately per model
   (heatmap over models × session_steps; panels = trial × sex).

## Grain

| Family | Point | Value |
| ------ | ----- | ----- |
| level | animal × session × trial | median `p` across 21 models (within-model median over cluster-{cluster_id} syllables) |
| trial_step | animal × session × trial_step | median paired Δp across models (same syllable median rule) |
| session_step | animal × trial × session_step | median paired Δp across models |

Whiskers = ±½ IQR of that animal's values across models (salt), not SEM.

**Association:** independent groups (condition) within sex × facet cell.
Paired Δs are within-animal first differences; Kruskal on Δ is
difference-of-differences / tx modulation of the move.

**Hit rule:** BH `q_bh < 0.05` within each family's cell grid (level & trial_step:
24; session_step: 36).

**What this is not:** not alphabet-wide DA FDR; not Wilcoxon vs 0 as the panel
claim; not spatial dwell maps.

## Protocol gloss (figures only)

| Wire | Prose on figures |
| ---- | ---------------- |
| `session` | stage (BL / TX / REC3 / REC11) |
| `trial` | phase (acclimation / familiarization / recognition) |
| `trial_step` | phase-step (presence / novelty / span) |
| `session_step` | stage-step (BL–TX, …) |
| `condition` | treatment arm (color) |

## Artifacts

| File | Unit |
| ---- | ---- |
| `{names["animal"]}` | animal × session × trial |
| `{names["kruskal"]}` | session × trial × sex |
| `{names["trial_step"]}` | animal × session × trial_step |
| `{names["trial_step_kr"]}` | session × trial_step × sex |
| `{names["session_step"]}` | animal × trial × session_step |
| `{names["session_step_kr"]}` | trial × session_step × sex |
| `{names["map"]}` | model × raw_syllable_id (may be >1 / model) |
| `figures/{stem_level}.{{pdf,svg}}` | six-violin level |
| `figures/{stem_m_level}.{{pdf,svg}}` | per-model level Kruskal |
| `figures/{stem_m_trial}.{{pdf,svg}}` | per-model phase-step Kruskal |
| `figures/{stem_m_session}.{{pdf,svg}}` | per-model stage-step Kruskal |
| `figures/{stem_trial}.{{pdf,svg}}` | phase-step Δ |
| `figures/{stem_session}.{{pdf,svg}}` | stage-step Δ |

## Source (rebuild only)

| Upstream | Use |
| -------- | --- |
| `simpler_first_da/da_syllable_deltas_per_animal.csv` | `p_left` / `p_right` / `delta_p` |
| `simpler_first_syllable_signatures/syllable_prototypes_clustered.csv` | HDBSCAN cluster-{cluster_id} ids (median if >1) |
"""
    (pack / "INFO_slides_pack.md").write_text(text, encoding="utf-8")
    print(f"wrote {pack / 'INFO_slides_pack.md'}")


def write_figures_md(out: Path, *, cluster_id: int) -> None:
    lab = _lab(cluster_id)
    text = f"""# Figures — cluster {cluster_id} frame share (slides pack)

Complementary to `../INFO_slides_pack.md`. Dest = slides.

| | |
| --- | --- |
| These files | `slides_pack/{lab}/figures/` |
| Dest | slides |
| How regenerated | `uv run python scratch/nor_object_mi/fig_slides_pack.py --clusters {cluster_id}` |

## Artifact map

| Stem | Question clause | Encoding | D / I |
| ---- | --------------- | -------- | ----- |
| `{_fig_stem(cluster_id, "frame_share_by_sex")}` | Level: condition × sex on frame share | 3×4 trial × session; six violins | D + Kruskal on level |
| `{_fig_stem(cluster_id, "per_model_level_kruskal")}` | Per-model: does condition change frame share? | 3×2 trial × sex; y=model, x=session | I Kruskal per model |
| `{_fig_stem(cluster_id, "per_model_trial_step_kruskal")}` | Per-model: does condition modulate phase-step Δ? | 3×2 trial_step × sex; y=model, x=session | I Kruskal per model |
| `{_fig_stem(cluster_id, "per_model_session_step_kruskal")}` | Per-model: does condition modulate stage-step Δ? | 3×2 trial × sex; y=model, x=session_step | I Kruskal per model |
| `{_fig_stem(cluster_id, "trial_step_delta_by_sex")}` | Phase-step Δ modulated by condition? | 3×4 trial_step × session; six violins; y = Δp | D + Kruskal on Δ |
| `{_fig_stem(cluster_id, "session_step_delta_by_sex")}` | Stage-step Δ modulated by condition? | 3×6 trial × session_step; six violins; y = Δp | D + Kruskal on Δ |

## Notes

- Level / trial-step grids are **trial (or trial_step) × session** (transpose of the spatial heatmap’s session × trial layout).
- Per-model phase-step panels are **trial_step × sex** with x = session (stage).
- Step figures are complementary paired first differences; Kruskal is tx modulation of the move (not Wilcoxon vs 0).

## Regen

```powershell
uv run python scratch/nor_object_mi/fig_slides_pack.py --rebuild --clusters {cluster_id}
```
"""
    out.mkdir(parents=True, exist_ok=True)
    (out / "FIGURES.md").write_text(text, encoding="utf-8")
    print(f"wrote {out / 'FIGURES.md'}")


def _load_or_rebuild(
    pack: Path,
    da_dir: Path,
    sig_dir: Path,
    *,
    cluster_id: int,
    rebuild: bool,
) -> dict[str, pd.DataFrame]:
    names = _pack_csv_names(cluster_id)
    needed = tuple(names.values())
    if rebuild or any(not (pack / name).exists() for name in needed):
        _clear_legacy(pack, pack / "figures", cluster_id=cluster_id)
        return rebuild_pack(pack=pack, da_dir=da_dir, sig_dir=sig_dir, cluster_id=cluster_id)
    return {
        "animal_frame_share": pd.read_csv(pack / names["animal"]),
        "kruskal_level": pd.read_csv(pack / names["kruskal"]),
        "trial_step_delta": pd.read_csv(pack / names["trial_step"]),
        "kruskal_trial_step": pd.read_csv(pack / names["trial_step_kr"]),
        "session_step_delta": pd.read_csv(pack / names["session_step"]),
        "kruskal_session_step": pd.read_csv(pack / names["session_step_kr"]),
        "kruskal_per_model_level": pd.read_csv(pack / names["model_level_kr"]),
        "kruskal_per_model_trial_step": pd.read_csv(pack / names["model_trial_kr"]),
        "kruskal_per_model_session_step": pd.read_csv(pack / names["model_session_kr"]),
        "model_labels": pd.read_csv(pack / names["model_labels"]),
    }


def _clear_flat_legacy_root(pack_root: Path) -> None:
    """Remove pre-subfolder slides_pack flat files (moved under clusterN/)."""
    if not pack_root.is_dir():
        return
    for p in list(pack_root.iterdir()):
        if p.name.startswith("cluster") and p.is_dir():
            continue
        if p.name in {"INFO_slides_pack.md"} or p.suffix in {".csv", ".md"}:
            p.unlink()
            print(f"removed flat {p}")
        elif p.name == "figures" and p.is_dir():
            shutil.rmtree(p)
            print(f"removed flat {p}")


def run_one_cluster(
    *,
    pack_root: Path,
    da_dir: Path,
    sig_dir: Path,
    cluster_id: int,
    dest: str,
    rebuild: bool,
) -> None:
    pack = pack_root / _lab(cluster_id)
    out = pack / "figures"
    out.mkdir(parents=True, exist_ok=True)
    print(f"=== cluster {cluster_id} -> {pack} ===", flush=True)
    tables = _load_or_rebuild(pack, da_dir, sig_dir, cluster_id=cluster_id, rebuild=rebuild)
    fig_frame_share_by_condition_sex(
        tables["animal_frame_share"], tables["kruskal_level"], out, dest=dest, cluster_id=cluster_id
    )
    fig_trial_step_delta_by_sex(
        tables["trial_step_delta"], tables["kruskal_trial_step"], out, dest=dest, cluster_id=cluster_id
    )
    fig_session_step_delta_by_sex(
        tables["session_step_delta"], tables["kruskal_session_step"], out, dest=dest, cluster_id=cluster_id
    )
    fig_per_model_kruskal_heatmap(
        tables["kruskal_per_model_level"],
        tables["model_labels"],
        out,
        dest=dest,
        row_col="trial",
        row_values=list(TRIALS),
        row_lab=TRIAL_LAB,
        x_col="session",
        x_values=list(SESSIONS),
        x_lab=SESSION_SHORT,
        stem=_fig_stem(cluster_id, "per_model_level_kruskal"),
        title=f"Per-model Kruskal on frame share ~ condition  (cluster {cluster_id})",
        footnote=FOOT_MODEL_LEVEL,
    )
    fig_per_model_kruskal_heatmap(
        tables["kruskal_per_model_trial_step"],
        tables["model_labels"],
        out,
        dest=dest,
        row_col="trial_step",
        row_values=list(TRIAL_STEP_NAMES),
        row_lab=TRIAL_STEP_LAB,
        x_col="session",
        x_values=list(SESSIONS),
        x_lab=SESSION_SHORT,
        stem=_fig_stem(cluster_id, "per_model_trial_step_kruskal"),
        title=f"Per-model Kruskal on phase-step Δ frame share ~ condition  (cluster {cluster_id})",
        footnote=FOOT_MODEL_TRIAL,
    )
    fig_per_model_kruskal_heatmap(
        tables["kruskal_per_model_session_step"],
        tables["model_labels"],
        out,
        dest=dest,
        row_col="trial",
        row_values=list(TRIALS),
        row_lab=TRIAL_LAB,
        x_col="session_step",
        x_values=list(SESSION_STEP_NAMES),
        x_lab=SESSION_STEP_LAB,
        stem=_fig_stem(cluster_id, "per_model_session_step_kruskal"),
        title=f"Per-model Kruskal on stage-step Δ frame share ~ condition  (cluster {cluster_id})",
        footnote=FOOT_MODEL_SESSION,
    )
    write_info_md(pack, cluster_id=cluster_id)
    write_figures_md(out, cluster_id=cluster_id)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pack-root", type=Path, default=DEFAULT_PACK_ROOT)
    ap.add_argument("--da-dir", type=Path, default=DEFAULT_DA)
    ap.add_argument("--sig-dir", type=Path, default=DEFAULT_SIG)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    ap.add_argument(
        "--clusters",
        type=str,
        default=",".join(str(c) for c in DEFAULT_CLUSTERS),
        help="Comma-separated HDBSCAN cluster ids (default: 13,17,12,3)",
    )
    ap.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild pack CSVs from DA + prototypes",
    )
    args = ap.parse_args(argv)
    clusters = [int(x.strip()) for x in args.clusters.split(",") if x.strip()]
    if not clusters:
        raise SystemExit("no clusters specified")
    if args.rebuild:
        _clear_flat_legacy_root(args.pack_root)
    for cid in clusters:
        run_one_cluster(
            pack_root=args.pack_root,
            da_dir=args.da_dir,
            sig_dir=args.sig_dir,
            cluster_id=cid,
            dest=args.dest,
            rebuild=args.rebuild,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
