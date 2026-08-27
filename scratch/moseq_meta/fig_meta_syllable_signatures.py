"""Meta-cluster descriptives + ordination (NOR + VAST pooled prototypes).

Regen:
  uv run python scratch/moseq_meta/fig_meta_syllable_signatures.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.cm import ScalarMappable
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.lines import Line2D

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from maze.kpms.behavior_ethogram.cluster import zscore_features  # noqa: E402
from moseq_meta.meta_cluster_style import (  # noqa: E402
    DEFAULT_META,
    EXPERIMENT_COLOR,
    EXPERIMENT_MARKER,
    clustered_for_fig,
    highlight_meta_cluster,
    load_meta_lookup,
    summary_for_fig,
)
from nor_object_mi._pub_style import (  # noqa: E402
    FIGSIZE_DOUBLE,
    INK,
    apply_style,
    fig_footnote,
    fig_legend_and_footnote,
    save_pdf_png,
    type_scale,
)
from nor_object_mi.fig_simpler_first_syllable_signatures import (  # noqa: E402
    FEATURE_SHORT,
    NOISE_COLOR,
    colors_for_cluster_ids,
    pca_ordination,
    prototype_pca_table,
)
from nor_object_mi.simpler_first_syllable_signatures import cluster_feature_matrix  # noqa: E402

HI_COLOR = "#0072B2"


def add_meta_cluster_colorbar(
    fig: plt.Figure,
    ax: plt.Axes,
    cluster_ids: list[int],
    listed: ListedColormap,
    *,
    dest: str,
) -> None:
    ts = type_scale(dest)
    n = len(cluster_ids)
    norm = BoundaryNorm(np.arange(n + 1) - 0.5, n)
    sm = ScalarMappable(cmap=listed, norm=norm)
    sm.set_array(np.arange(n))
    cbar = fig.colorbar(sm, ax=ax, fraction=0.05, pad=0.02)
    cbar.set_label("meta_cluster_id", fontsize=ts["legend"])
    tick_at = np.unique(np.round(np.linspace(0, n - 1, min(9, n))).astype(int))
    cbar.set_ticks(tick_at)
    cbar.set_ticklabels([str(cluster_ids[i]) for i in tick_at])


def fig_meta_cluster_coverage(
    summary: pd.DataFrame,
    lookup: dict[int, tuple[float, float, float, float]],
    cluster_ids: list[int],
    listed: ListedColormap,
    out: Path,
    *,
    dest: str,
) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    s = summary.copy()
    fig, ax = plt.subplots(figsize=FIGSIZE_DOUBLE, constrained_layout=True)
    sizes = 18 + 4 * np.sqrt(s["n_prototypes"].to_numpy(dtype=float))
    ax.scatter(
        s["n_models"],
        s["median_n_bouts"],
        s=sizes,
        c=colors_for_cluster_ids(s["cluster_id"], lookup),
        alpha=0.88,
        edgecolors=INK,
        linewidths=0.35,
        zorder=2,
    )
    cross = s[s["n_experiments"] >= 2]
    if not cross.empty:
        ax.scatter(
            cross["n_models"],
            cross["median_n_bouts"],
            s=80,
            facecolors="none",
            edgecolors="#000000",
            linewidths=1.2,
            zorder=3,
        )
    ax.set_yscale("log")
    ax.set_xlabel("n models in meta cluster")
    ax.set_ylabel("median n_bouts (log)")
    ax.set_title("Meta-cluster coverage vs usage", loc="left", fontweight="bold", color=INK, fontsize=ts["annotation"])
    fig.suptitle("Cross-experiment HDBSCAN: alphabet span × bout usage", fontsize=ts["suptitle"], fontweight="bold", color=INK)
    add_meta_cluster_colorbar(fig, ax, cluster_ids, listed, dest=dest)
    fig_footnote(
        fig,
        "One point = meta_cluster_id ≥ 0 (62 this fit). Black ring = spans NOR + VAST. "
        "Marker area ~ n_prototypes. Turbo colormap shared with DA figures.",
        fontsize=ts["footnote"],
    )
    save_pdf_png(fig, out / "fig_meta_cluster_coverage")


def fig_meta_experiment_composition(summary: pd.DataFrame, lookup: dict, cluster_ids: list[int], listed, out: Path, *, dest: str) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    s = summary.sort_values("cluster_id").copy()
    y = np.arange(len(s))
    fig, ax = plt.subplots(figsize=(FIGSIZE_DOUBLE[0], max(4.0, 0.22 * len(s) + 1.5)), constrained_layout=True)
    nor = s["n_nor_prototypes"].to_numpy(dtype=float)
    vast = s["n_vast_prototypes"].to_numpy(dtype=float)
    ax.barh(y, nor, height=0.72, color="#0072B2", alpha=0.85, label="NOR prototypes")
    ax.barh(y, vast, left=nor, height=0.72, color="#E69F00", alpha=0.85, label="VAST prototypes")
    ax.set_yticks(y)
    ax.set_yticklabels([str(int(c)) for c in s["cluster_id"]], fontsize=7)
    ax.set_ylabel("meta_cluster_id")
    ax.set_xlabel("prototype count")
    ax.set_title("Experiment composition per meta cluster", loc="left", fontweight="bold", color=INK, fontsize=ts["annotation"])
    ax.legend(frameon=False, fontsize=ts["legend"])
    fig_footnote(fig, "Stacked counts from pooled bout signatures. Only 3 meta clusters include both experiments.", fontsize=ts["footnote"])
    save_pdf_png(fig, out / "fig_meta_experiment_composition")


def fig_meta_signature_space(cl: pd.DataFrame, lookup: dict, cluster_ids: list[int], listed, out: Path, *, dest: str) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    noise = cl["cluster_id"] < 0
    fig, axes = plt.subplots(1, 2, figsize=FIGSIZE_DOUBLE, constrained_layout=True)
    s_pt = ts["scatter"] if dest == "slides" else ts["violin_scatter"] * 0.35

    def _panel(ax, xcol: str, ycol: str, title: str) -> None:
        ax.scatter(
            cl.loc[noise, xcol],
            cl.loc[noise, ycol],
            s=s_pt * 0.4,
            c=NOISE_COLOR,
            alpha=0.35,
            edgecolors="none",
            zorder=1,
        )
        clustered = cl.loc[~noise]
        for exp, mk in EXPERIMENT_MARKER.items():
            sub = clustered[clustered["experiment"] == exp]
            if sub.empty:
                continue
            ax.scatter(
                sub[xcol],
                sub[ycol],
                s=s_pt,
                marker=mk,
                c=colors_for_cluster_ids(sub["cluster_id"], lookup),
                alpha=0.88,
                edgecolors=INK,
                linewidths=0.15,
                zorder=2,
            )
        ax.set_title(title, loc="left", fontweight="bold", color=INK, fontsize=ts["annotation"])

    _panel(axes[0], "syllable_mean_duration_s", "syllable_sig_mean_speed_mps", "A  timing × speed")
    axes[0].set_xlabel("mean bout duration (s)")
    axes[0].set_ylabel("mean speed (m/s)")
    _panel(axes[1], "syllable_mean_straightness", "syllable_sig_mean_abs_dheading", "B  path × heading")
    axes[1].set_xlabel("straightness")
    axes[1].set_ylabel("mean |Δheading| (rad/frame)")
    fig.suptitle("Meta-cluster prototypes in kinematic space", fontsize=ts["suptitle"], fontweight="bold", color=INK)
    handles = [
        Line2D([0], [0], marker=EXPERIMENT_MARKER["nor"], color="none", markerfacecolor=EXPERIMENT_COLOR["nor"], markersize=8, label="NOR"),
        Line2D([0], [0], marker=EXPERIMENT_MARKER["vast"], color="none", markerfacecolor=EXPERIMENT_COLOR["vast"], markersize=8, label="VAST"),
        Line2D([0], [0], marker="s", color="none", markerfacecolor=NOISE_COLOR, markersize=8, label="meta noise (−1)"),
    ]
    fig_legend_and_footnote(
        fig,
        handles,
        "Color = meta_cluster_id (turbo). Shape = experiment. Grey = HDBSCAN noise. "
        "NOR = full session bouts; VAST = stimulus-on run bouts only.",
        dest=dest,
    )
    add_meta_cluster_colorbar(fig, axes[1], cluster_ids, listed, dest=dest)
    save_pdf_png(fig, out / "fig_meta_signature_space")


def fig_meta_prototype_scores_colormap(
    cl: pd.DataFrame,
    pca_df: pd.DataFrame,
    var: np.ndarray,
    lookup: dict,
    cluster_ids: list[int],
    listed,
    out: Path,
    *,
    dest: str,
) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    cl_plot = cl.merge(pca_df[["model", "raw_syllable_id", "pc1", "pc2"]], on=["model", "raw_syllable_id"], how="left")
    noise = cl_plot["cluster_id"] < 0
    s_pt = ts["scatter"] if dest == "slides" else ts["violin_scatter"] * 0.35
    fig, ax = plt.subplots(figsize=FIGSIZE_DOUBLE, constrained_layout=True)
    ax.scatter(
        cl_plot.loc[noise, "pc1"],
        cl_plot.loc[noise, "pc2"],
        s=s_pt * 0.45,
        c=NOISE_COLOR,
        alpha=0.35,
        edgecolors="none",
        zorder=1,
    )
    clustered = cl_plot.loc[~noise]
    for exp, mk in EXPERIMENT_MARKER.items():
        sub = clustered[clustered["experiment"] == exp]
        if sub.empty:
            continue
        ax.scatter(
            sub["pc1"],
            sub["pc2"],
            s=s_pt,
            marker=mk,
            c=colors_for_cluster_ids(sub["cluster_id"], lookup),
            alpha=0.88,
            edgecolors=INK,
            linewidths=0.15,
            zorder=2,
        )
    pc1_pct = 100.0 * float(var[0])
    pc2_pct = 100.0 * float(var[1])
    ax.set_xlabel(f"PC1 ({pc1_pct:.1f}% var)")
    ax.set_ylabel(f"PC2 ({pc2_pct:.1f}% var)")
    ax.set_title("Prototype scores (PC1 × PC2)", loc="left", fontweight="bold", color=INK, fontsize=ts["annotation"])
    fig.suptitle("Meta-cluster ordination (PCA on 9-D z-space)", fontsize=ts["suptitle"], fontweight="bold", color=INK)
    add_meta_cluster_colorbar(fig, ax, cluster_ids, listed, dest=dest)
    fig_footnote(
        fig,
        f"PCA on shared 9 z-scored features ({len(cl)} fit prototypes). "
        "Color = meta_cluster_id. ○ NOR · △ VAST.",
        fontsize=ts["footnote"],
    )
    save_pdf_png(fig, out / "fig_meta_prototype_scores_colormap")


def fig_meta_prototype_ordination(cl: pd.DataFrame, pca_df: pd.DataFrame, var: np.ndarray, names: tuple[str, ...], loadings: np.ndarray, out: Path, *, dest: str) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    cl_plot = cl.merge(pca_df[["model", "raw_syllable_id", "pc1", "pc2"]], on=["model", "raw_syllable_id"], how="left")
    fig, axes = plt.subplots(1, 2, figsize=FIGSIZE_DOUBLE, constrained_layout=True)
    pc1_pct = 100.0 * float(var[0])
    pc2_pct = 100.0 * float(var[1])
    ax = axes[0]
    for exp, mk in EXPERIMENT_MARKER.items():
        sub = cl_plot[cl_plot["experiment"] == exp]
        ax.scatter(sub["pc1"], sub["pc2"], s=12 if dest == "slides" else 8, marker=mk, c=EXPERIMENT_COLOR[exp], alpha=0.55, edgecolors="none", label=exp.upper())
    ax.set_xlabel(f"PC1 ({pc1_pct:.1f}% var)")
    ax.set_ylabel(f"PC2 ({pc2_pct:.1f}% var)")
    ax.set_title("A  prototype scores by experiment", loc="left", fontweight="bold", color=INK, fontsize=ts["annotation"])
    ax.legend(frameon=False, fontsize=ts["legend"])
    ax = axes[1]
    scale = 0.85 / max(float(np.max(np.abs(loadings[:, :2]))), 1e-12)
    for i, name in enumerate(names):
        lx, ly = loadings[i, 0] * scale, loadings[i, 1] * scale
        ax.arrow(0.0, 0.0, lx, ly, head_width=0.03, head_length=0.02, fc=INK, ec=INK, linewidth=0.8, zorder=2)
        ax.text(lx * 1.08, ly * 1.08, FEATURE_SHORT.get(name, name), fontsize=ts["cell"], ha="center", va="center", color=INK)
    ax.axhline(0, color="#dddddd", linewidth=0.6, zorder=0)
    ax.axvline(0, color="#dddddd", linewidth=0.6, zorder=0)
    ax.set_xlim(-1.05, 1.05)
    ax.set_ylim(-1.05, 1.05)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel(f"PC1 loading ({pc1_pct:.1f}% var)")
    ax.set_ylabel(f"PC2 loading ({pc2_pct:.1f}% var)")
    ax.set_title("B  feature loadings", loc="left", fontweight="bold", color=INK, fontsize=ts["annotation"])
    fig.suptitle("Meta-cluster prototype ordination", fontsize=ts["suptitle"], fontweight="bold", color=INK)
    fig_footnote(fig, "Same 9-D z-scored space as cross-experiment HDBSCAN. Left: experiment only (not meta color).", fontsize=ts["footnote"])
    save_pdf_png(fig, out / "fig_meta_prototype_ordination")


def fig_meta_descriptives_heatmap(summary: pd.DataFrame, lookup: dict, cluster_ids: list[int], listed, out: Path, *, dest: str) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    s = summary.sort_values("mean_sig_speed").copy()
    cols = ["mean_sig_speed", "mean_sig_dheading", "mean_duration_s", "mean_straightness", "mean_sig_nose_tail"]
    mat = s[cols].to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(FIGSIZE_DOUBLE[0], max(4.5, 0.18 * len(s) + 1.5)), constrained_layout=True)
    im = ax.imshow(mat, aspect="auto", cmap="viridis")
    ax.set_yticks(range(len(s)))
    ax.set_yticklabels([str(int(c)) for c in s["cluster_id"]], fontsize=7)
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels(["speed", "|dheading|", "duration", "straight", "nose-tail"], rotation=30, ha="right", fontsize=ts["cell"])
    ax.set_ylabel("meta_cluster_id (slow→fast sort)")
    ax.set_title("Meta-cluster mean kinematics", loc="left", fontweight="bold", color=INK, fontsize=ts["annotation"])
    fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02, label="raw prototype mean")
    fig_footnote(fig, "Rows sorted by mean speed. Values are un-z-scored prototype means from meta_cluster_summary.csv.", fontsize=ts["footnote"])
    save_pdf_png(fig, out / "fig_meta_descriptives_heatmap")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--meta-dir", type=Path, default=DEFAULT_META)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    args = ap.parse_args(argv)

    meta = args.meta_dir
    out = args.out_dir or (meta / "figures")
    out.mkdir(parents=True, exist_ok=True)

    cl = clustered_for_fig(meta)
    summary = summary_for_fig(meta)
    lookup, cluster_ids, listed = load_meta_lookup(meta)
    hi = highlight_meta_cluster(summary)

    pca_df, names, loadings, var = prototype_pca_table(cl)
    pca_df = pca_df.merge(cl[["model", "raw_syllable_id", "experiment"]], on=["model", "raw_syllable_id"], how="left")
    pca_df.to_csv(meta / "prototype_ordination_pca.csv", index=False)

    fig_meta_signature_space(cl, lookup, cluster_ids, listed, out, dest=args.dest)
    fig_meta_cluster_coverage(summary, lookup, cluster_ids, listed, out, dest=args.dest)
    fig_meta_experiment_composition(summary, lookup, cluster_ids, listed, out, dest=args.dest)
    fig_meta_prototype_scores_colormap(cl, pca_df, var, lookup, cluster_ids, listed, out, dest=args.dest)
    fig_meta_prototype_ordination(cl, pca_df, var, names, loadings, out, dest=args.dest)
    fig_meta_descriptives_heatmap(summary, lookup, cluster_ids, listed, out, dest=args.dest)

    print(f"highlight meta_cluster_id={hi} -> {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
