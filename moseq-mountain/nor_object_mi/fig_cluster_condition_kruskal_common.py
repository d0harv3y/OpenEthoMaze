"""Shared cluster Kruskal overview helpers (dual FDR marks, co-occurrence)."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from nor_object_mi._pub_style import INK, MUTE, apply_style, fig_footnote, save_pdf_png, type_scale
from nor_object_mi.cluster_condition_kruskal import (
    cluster_axis_label,
    clusters_with_any_hit,
    hit_locus_matrix,
    order_cluster_ids,
    pairwise_row_jaccard,
)


def fdr_mark(panel_hit: bool, col_hit: bool) -> str:
    """* = panel FDR; † = column-only FDR; *† when both."""
    if panel_hit and col_hit:
        return "*†"
    if panel_hit:
        return "*"
    if col_hit:
        return "†"
    return ""


def cluster_y_labels(cluster_ids: list[int]) -> list[str]:
    return [cluster_axis_label(c) for c in order_cluster_ids(cluster_ids)]


def fig_hit_cooccurrence(
    kr: pd.DataFrame,
    out: Path,
    *,
    stem: str,
    dest: str,
    panel_cols: tuple[str, ...],
    locus_col: str,
    locus_order: tuple[str, ...] | None,
    title: str,
    footnote: str,
    hit_col: str = "hit_fdr05",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Hit locus heatmap + pairwise Jaccard of cluster hit patterns."""
    apply_style(dest=dest)
    ts = type_scale(dest)
    hit_mat = hit_locus_matrix(
        kr,
        row_col="cluster_id",
        hit_col=hit_col,
        panel_cols=panel_cols,
        locus_col=locus_col,
        locus_order=locus_order,
    )
    jac = pairwise_row_jaccard(hit_mat)
    fig_w = 22.0 if dest == "slides" else 16.0
    fig_h = 10.0 if dest == "slides" else 8.0
    fig, axes = plt.subplots(1, 2, figsize=(fig_w, fig_h), constrained_layout=False)
    fig.subplots_adjust(left=0.08, right=0.96, top=0.90, bottom=0.18, wspace=0.28)

    ax0 = axes[0]
    if hit_mat.empty:
        ax0.text(0.5, 0.5, "no hits", ha="center", va="center", transform=ax0.transAxes)
    else:
        z = hit_mat.to_numpy(dtype=float)
        ax0.imshow(z, cmap="Greys", vmin=0.0, vmax=1.0, aspect="auto")
        ax0.set_yticks(range(len(hit_mat.index)))
        ax0.set_yticklabels(
            [cluster_axis_label(int(i)) for i in hit_mat.index], fontsize=ts["cell"]
        )
        ax0.set_xticks(range(len(hit_mat.columns)))
        ax0.set_xticklabels(
            list(hit_mat.columns), rotation=90, fontsize=max(5.0, ts["cell"] * 0.7)
        )
        ax0.set_title("FDR hit loci (1 = hit)", loc="left", fontweight="bold", color=INK)
        ax0.set_ylabel("cluster_id")

    ax1 = axes[1]
    n_hits = int(hit_mat.to_numpy().sum()) if not hit_mat.empty else 0
    if jac.empty or n_hits == 0:
        msg = "no panel FDR hits\n(Jaccard not shown)"
        ax1.text(0.5, 0.5, msg, ha="center", va="center", transform=ax1.transAxes, color=MUTE)
        ax1.set_axis_off()
    else:
        im = ax1.imshow(jac.to_numpy(dtype=float), cmap="viridis", vmin=0.0, vmax=1.0, aspect="auto")
        labs = [cluster_axis_label(int(i)) for i in jac.index]
        ax1.set_yticks(range(len(labs)))
        ax1.set_yticklabels(labs, fontsize=ts["cell"])
        ax1.set_xticks(range(len(labs)))
        ax1.set_xticklabels(labs, rotation=90, fontsize=ts["cell"])
        ax1.set_title(
            "Cluster × cluster Jaccard of hit sets", loc="left", fontweight="bold", color=INK
        )
        cax = fig.add_axes([0.93, 0.25, 0.012, 0.5])
        fig.colorbar(im, cax=cax, label="Jaccard")

    fig.suptitle(title, fontsize=ts["suptitle"], fontweight="bold", color=INK)
    fig_footnote(fig, footnote, fontsize=ts["footnote"], y=0.02, color=MUTE)
    save_pdf_png(fig, out / stem)
    return hit_mat, jac


def summarize_hit_clusters(kr: pd.DataFrame) -> dict[str, object]:
    panel = clusters_with_any_hit(kr, hit_cols=("hit_fdr05",))
    either = clusters_with_any_hit(kr, hit_cols=("hit_fdr05", "hit_fdr05_col"))
    col_only = [c for c in either if c not in set(panel)]
    return {
        "n_clusters": int(kr["cluster_id"].nunique()) if not kr.empty else 0,
        "n_hit_fdr05_panel": int(kr["hit_fdr05"].sum()) if "hit_fdr05" in kr.columns else 0,
        "n_hit_fdr05_col": int(kr["hit_fdr05_col"].sum()) if "hit_fdr05_col" in kr.columns else 0,
        "clusters_panel_hit": panel,
        "clusters_col_only_hit": col_only,
        "clusters_any_hit": either,
    }
