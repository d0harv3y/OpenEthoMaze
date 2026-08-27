"""Slides figures for simpler_first_syllable_signatures (D only).

Reads only CSVs in that run folder (INFO_syllable_signatures.md).

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/fig_simpler_first_syllable_signatures.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.cm import ScalarMappable
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.lines import Line2D

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi._pub_style import (  # noqa: E402
    FIGSIZE_DOUBLE,
    INK,
    apply_style,
    fig_footnote,
    fig_legend_and_footnote,
    save_pdf_png,
    type_scale,
)
from nor_object_mi.simpler_first_syllable_signatures import (  # noqa: E402
    cluster_feature_matrix,
)
from maze.kpms.behavior_ethogram.cluster import zscore_features  # noqa: E402

DEFAULT_RUN = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_syllable_signatures"
)
HI_COLOR = "#0072B2"
NOISE_COLOR = "#c8c8c8"
OTHER_COLOR = "#9aa0a6"

FEATURE_SHORT = {
    "syllable_sig_mean_speed_mps": "speed",
    "syllable_sig_mean_abs_dheading": "|dheading|",
    "syllable_sig_mean_nose_tail_m": "nose-tail",
    "syllable_mean_iqr_speed_mps": "IQR speed",
    "syllable_mean_iqr_abs_dheading": "IQR |dh|",
    "syllable_mean_iqr_nose_tail_m": "IQR size",
    "syllable_mean_duration_s": "duration",
    "syllable_mean_net_dheading_rad": "net dh",
    "syllable_mean_straightness": "straight",
}


def pca_ordination(z: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """PCA on row-wise z-scored prototype matrix. Returns scores (n×k), loadings (p×k), var frac."""
    x = np.asarray(z, dtype=np.float64)
    x = x - np.nanmean(x, axis=0, keepdims=True)
    x = np.nan_to_num(x, nan=0.0)
    _u, s, vt = np.linalg.svd(x, full_matrices=False)
    scores = x @ vt.T
    loadings = vt.T
    var = (s**2) / max(float(np.sum(s**2)), 1e-12)
    return scores, loadings, var


def prototype_pca_table(
    cl: pd.DataFrame,
) -> tuple[pd.DataFrame, tuple[str, ...], np.ndarray, np.ndarray]:
    mat, names = cluster_feature_matrix(cl)
    z, _mean, _std = zscore_features(mat)
    scores, loadings, var = pca_ordination(z)
    out = cl[["model", "raw_syllable_id", "cluster_id", "n_bouts"]].copy()
    out["pc1"] = scores[:, 0]
    out["pc2"] = scores[:, 1]
    out["pc3"] = scores[:, 2]
    return out, names, loadings, var


def build_cluster_color_lookup(
    summary: pd.DataFrame,
) -> tuple[dict[int, tuple[float, float, float, float]], list[int], ListedColormap]:
    """Stable turbo lookup keyed by cluster_id; noise (−1) is grey."""
    cluster_ids = sorted(int(x) for x in summary["cluster_id"].unique() if int(x) >= 0)
    n = len(cluster_ids)
    base = plt.get_cmap("turbo")
    lookup: dict[int, tuple[float, float, float, float]] = {
        cid: base(i / max(n - 1, 1)) for i, cid in enumerate(cluster_ids)
    }
    lookup[-1] = mcolors.to_rgba(NOISE_COLOR)
    listed = ListedColormap([lookup[cid] for cid in cluster_ids])
    return lookup, cluster_ids, listed


def colors_for_cluster_ids(
    cluster_ids: pd.Series | np.ndarray,
    lookup: dict[int, tuple[float, float, float, float]],
) -> np.ndarray:
    ids = np.asarray(cluster_ids, dtype=np.int64)
    return np.vstack([lookup.get(int(c), lookup[-1]) for c in ids])


def add_cluster_id_colorbar(
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
    cbar.set_label("cluster_id", fontsize=ts["legend"])
    tick_at = np.unique(np.round(np.linspace(0, n - 1, min(9, n))).astype(int))
    cbar.set_ticks(tick_at)
    cbar.set_ticklabels([str(cluster_ids[i]) for i in tick_at])


def _scatter_ordination(
    ax,
    cl: pd.DataFrame,
    xcol: str,
    ycol: str,
    hi: int,
    *,
    dest: str,
    xlabel: str,
    ylabel: str,
    title: str,
) -> None:
    ts = type_scale(dest)
    noise = cl["cluster_id"] < 0
    is_hi = cl["cluster_id"] == hi
    other = ~noise & ~is_hi
    s_noise = 8 if dest == "slides" else 5
    s_hi = 52 if dest == "slides" else 28
    ax.scatter(
        cl.loc[noise, xcol],
        cl.loc[noise, ycol],
        s=s_noise,
        c=NOISE_COLOR,
        alpha=0.35,
        edgecolors="none",
        zorder=1,
    )
    ax.scatter(
        cl.loc[other, xcol],
        cl.loc[other, ycol],
        s=s_noise,
        c=OTHER_COLOR,
        alpha=0.45,
        edgecolors="none",
        zorder=2,
    )
    ax.scatter(
        cl.loc[is_hi, xcol],
        cl.loc[is_hi, ycol],
        s=s_hi,
        c=HI_COLOR,
        marker="o",
        edgecolors=INK,
        linewidths=0.5,
        zorder=3,
    )
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title, loc="left", fontweight="bold", color=INK, fontsize=ts["annotation"])


def fig_prototype_ordination(
    cl: pd.DataFrame,
    hi: int,
    out: Path,
    *,
    dest: str,
) -> pd.DataFrame:
    apply_style(dest=dest)
    ts = type_scale(dest)
    pca_df, names, loadings, var = prototype_pca_table(cl)
    cl_plot = cl.merge(
        pca_df[["model", "raw_syllable_id", "pc1", "pc2", "pc3"]],
        on=["model", "raw_syllable_id"],
        how="left",
    )
    fig, axes = plt.subplots(1, 2, figsize=FIGSIZE_DOUBLE, constrained_layout=True)
    pc1_pct = 100.0 * float(var[0])
    pc2_pct = 100.0 * float(var[1])
    _scatter_ordination(
        axes[0],
        cl_plot,
        "pc1",
        "pc2",
        hi,
        dest=dest,
        xlabel=f"PC1 ({pc1_pct:.1f}% var)",
        ylabel=f"PC2 ({pc2_pct:.1f}% var)",
        title="A  prototype scores (PC1 × PC2)",
    )
    ax = axes[1]
    scale = 0.85 / max(float(np.max(np.abs(loadings[:, :2]))), 1e-12)
    for i, name in enumerate(names):
        lx, ly = loadings[i, 0] * scale, loadings[i, 1] * scale
        ax.arrow(
            0.0,
            0.0,
            lx,
            ly,
            head_width=0.03,
            head_length=0.02,
            fc=INK,
            ec=INK,
            linewidth=0.8,
            zorder=2,
        )
        ax.text(
            lx * 1.08,
            ly * 1.08,
            FEATURE_SHORT.get(name, name),
            fontsize=ts["cell"],
            ha="center",
            va="center",
            color=INK,
        )
    ax.axhline(0, color="#dddddd", linewidth=0.6, zorder=0)
    ax.axvline(0, color="#dddddd", linewidth=0.6, zorder=0)
    ax.set_xlim(-1.05, 1.05)
    ax.set_ylim(-1.05, 1.05)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel(f"PC1 loading ({pc1_pct:.1f}% var)")
    ax.set_ylabel(f"PC2 loading ({pc2_pct:.1f}% var)")
    ax.set_title(
        "B  feature loadings (same z-scored 9-D space as HDBSCAN)",
        loc="left",
        fontweight="bold",
        color=INK,
        fontsize=ts["annotation"],
    )
    fig.suptitle(
        "Syllable prototypes in ordinate space (PCA)",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=NOISE_COLOR, markersize=8, label="noise (−1)"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=OTHER_COLOR, markersize=8, label="other clusters"),
        Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor=HI_COLOR,
            markeredgecolor=INK,
            markersize=9,
            label=f"cluster {hi} (all alphabets, max median n_bouts)",
        ),
    ]
    fig_legend_and_footnote(
        fig,
        handles,
        (
            "PCA on the same 9 z-scored kinematic features used for HDBSCAN (1269 prototypes, n_bouts ≥ 10). "
            f"Blue = cluster {hi}. Ordination is D only; cluster ids are fit-specific."
        ),
        dest=dest,
    )
    save_pdf_png(fig, out / "fig_prototype_ordination")
    return pca_df


def fig_prototype_scores_colormap(
    cl: pd.DataFrame,
    pca_df: pd.DataFrame,
    var: np.ndarray,
    lookup: dict[int, tuple[float, float, float, float]],
    cluster_ids: list[int],
    listed: ListedColormap,
    out: Path,
    *,
    dest: str,
) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    cl_plot = cl.merge(
        pca_df[["model", "raw_syllable_id", "pc1", "pc2"]],
        on=["model", "raw_syllable_id"],
        how="left",
    )
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
    ax.scatter(
        clustered["pc1"],
        clustered["pc2"],
        s=s_pt,
        c=colors_for_cluster_ids(clustered["cluster_id"], lookup),
        alpha=0.88,
        edgecolors=INK,
        linewidths=0.15,
        zorder=2,
    )
    pc1_pct = 100.0 * float(var[0])
    pc2_pct = 100.0 * float(var[1])
    ax.set_xlabel(f"PC1 ({pc1_pct:.1f}% var)")
    ax.set_ylabel(f"PC2 ({pc2_pct:.1f}% var)")
    ax.set_title(
        "Prototype scores (PC1 × PC2)",
        loc="left",
        fontweight="bold",
        color=INK,
        fontsize=ts["annotation"],
    )
    fig.suptitle(
        "Syllable prototypes in ordinate space",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    add_cluster_id_colorbar(fig, ax, cluster_ids, listed, dest=dest)
    fig_footnote(
        fig,
        (
            "PCA on the same 9 z-scored kinematic features used for HDBSCAN (1269 prototypes, n_bouts ≥ 10). "
            "Color = HDBSCAN cluster_id (turbo, fit-specific). Grey = noise (−1). D only."
        ),
        fontsize=ts["footnote"],
    )
    save_pdf_png(fig, out / "fig_prototype_scores_colormap")


def _highlight_cluster(summary: pd.DataFrame) -> int:
    """Full-alphabet blob with the largest median usage (cluster 13 this run)."""
    s = summary.copy()
    s["median_n_bouts"] = pd.to_numeric(s["median_n_bouts"], errors="coerce")
    s["n_models"] = pd.to_numeric(s["n_models"], errors="coerce")
    full = s[s["n_models"] == s["n_models"].max()]
    if full.empty:
        full = s
    return int(full.loc[full["median_n_bouts"].idxmax(), "cluster_id"])


def fig_signature_space(cl: pd.DataFrame, hi: int, out: Path, *, dest: str) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    noise = cl["cluster_id"] < 0
    is_hi = cl["cluster_id"] == hi
    other = ~noise & ~is_hi
    fig, axes = plt.subplots(1, 2, figsize=FIGSIZE_DOUBLE, constrained_layout=True)
    s_noise = 8 if dest == "slides" else 5
    s_hi = 52 if dest == "slides" else 28

    def _scatter(ax, xcol: str, ycol: str, title: str) -> None:
        ax.scatter(
            cl.loc[noise, xcol],
            cl.loc[noise, ycol],
            s=s_noise,
            c=NOISE_COLOR,
            alpha=0.35,
            edgecolors="none",
            zorder=1,
        )
        ax.scatter(
            cl.loc[other, xcol],
            cl.loc[other, ycol],
            s=s_noise,
            c=OTHER_COLOR,
            alpha=0.45,
            edgecolors="none",
            zorder=2,
        )
        ax.scatter(
            cl.loc[is_hi, xcol],
            cl.loc[is_hi, ycol],
            s=s_hi,
            c=HI_COLOR,
            marker="o",
            edgecolors=INK,
            linewidths=0.5,
            zorder=3,
        )
        ax.set_title(title, loc="left", fontweight="bold", color=INK, fontsize=ts["annotation"])

    _scatter(
        axes[0],
        "syllable_mean_duration_s",
        "syllable_sig_mean_speed_mps",
        "A  timing × speed",
    )
    axes[0].set_xlabel("mean bout duration (s)")
    axes[0].set_ylabel("mean speed (m/s)")
    _scatter(
        axes[1],
        "syllable_mean_straightness",
        "syllable_sig_mean_abs_dheading",
        "B  path × heading",
    )
    axes[1].set_xlabel("straightness")
    axes[1].set_ylabel("mean |Δheading| (rad/frame)")
    fig.suptitle(
        "Syllable prototypes in kinematic space (HDBSCAN)",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=NOISE_COLOR, markersize=8, label="noise (−1)"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=OTHER_COLOR, markersize=8, label="other clusters"),
        Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor=HI_COLOR,
            markeredgecolor=INK,
            markersize=9,
            label=f"cluster {hi} (all alphabets, max median n_bouts)",
        ),
    ]
    fig_legend_and_footnote(
        fig,
        handles,
        (
            "One point = model × raw_syllable_id (n_bouts ≥ 10). Grey = HDBSCAN noise. "
            f"Blue = cluster {hi} (every alphabet; largest median_n_bouts among those). D only; no test. "
            "Ids are not portable across alphabets."
        ),
        dest=dest,
    )
    save_pdf_png(fig, out / "fig_signature_space")


def fig_cluster_coverage(
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
    s["median_n_bouts"] = pd.to_numeric(s["median_n_bouts"], errors="coerce")
    s["n_models"] = pd.to_numeric(s["n_models"], errors="coerce")
    s["n_prototypes"] = pd.to_numeric(s["n_prototypes"], errors="coerce")
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
    ax.set_yscale("log")
    ax.set_xlabel("n models in cluster")
    ax.set_ylabel("median n_bouts (log)")
    ax.set_title(
        "Cluster coverage vs usage",
        loc="left",
        fontweight="bold",
        color=INK,
        fontsize=ts["annotation"],
    )
    fig.suptitle(
        "HDBSCAN clusters: how many alphabets, how many bouts",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    add_cluster_id_colorbar(fig, ax, cluster_ids, listed, dest=dest)
    fig_footnote(
        fig,
        (
            "One point = one cluster_id ≥ 0 (55 this run). Marker area ~ n_prototypes. "
            "Same turbo colormap as prototype scores. D only. "
            "n_models = max this run (21) means every alphabet contributed at least one prototype."
        ),
        fontsize=ts["footnote"],
    )
    save_pdf_png(fig, out / "fig_cluster_coverage")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    args = ap.parse_args(argv)

    run = args.run_dir
    out = args.out_dir or (run / "figures")
    out.mkdir(parents=True, exist_ok=True)
    cl = pd.read_csv(run / "syllable_prototypes_clustered.csv")
    summary = pd.read_csv(run / "cluster_summary.csv")
    hi = _highlight_cluster(summary)
    pca_df, _names, _loadings, var = prototype_pca_table(cl)
    lookup, cluster_ids, listed = build_cluster_color_lookup(summary)
    fig_signature_space(cl, hi, out, dest=args.dest)
    fig_cluster_coverage(summary, lookup, cluster_ids, listed, out, dest=args.dest)
    fig_prototype_ordination(cl, hi, out, dest=args.dest)
    fig_prototype_scores_colormap(cl, pca_df, var, lookup, cluster_ids, listed, out, dest=args.dest)
    pca_df.to_csv(run / "prototype_ordination_pca.csv", index=False)
    (out / "FIGURES.md").write_text(_figures_md(), encoding="utf-8")
    print(f"highlight cluster_id={hi} -> {out}", flush=True)
    print(f"wrote {run / 'prototype_ordination_pca.csv'}", flush=True)
    return 0


def _figures_md() -> str:
    return """# Figures — syllable kinematic signatures

Complementary to `INFO_syllable_signatures.md`. Dest: **slides**.

| | |
| --- | --- |
| These files | `_nor_object_mi/simpler_first_syllable_signatures/figures/` |
| Dest | slides |
| How regenerated | `uv run python scratch/nor_object_mi/fig_simpler_first_syllable_signatures.py` |

Source files are only those in this run folder.

## Artifact map

| Stem | Question clause | Source file → columns | Encoding | D / I |
| ---- | --------------- | --------------------- | -------- | ----- |
| `fig_signature_space` | Do clustered prototypes occupy a long/slow, crooked region? | `syllable_prototypes_clustered.csv` → duration, speed, straightness, abs dheading, `cluster_id` | scatter; grey = noise; blue = max-median_n_bouts cluster | D |
| `fig_prototype_ordination` | Where do prototypes sit in the z-scored 9-D feature space? | `syllable_prototypes_clustered.csv` → same 9 features as HDBSCAN; scores in `prototype_ordination_pca.csv` | PCA PC1×PC2 + loadings biplot; blue = cluster 13 | D |
| `fig_prototype_scores_colormap` | Same ordination, all clusters visible? | `prototype_ordination_pca.csv` + `cluster_id` | PC1×PC2; turbo by cluster_id; grey = noise | D |
| `fig_cluster_coverage` | Which blobs span alphabets and usage? | `cluster_summary.csv` → `n_models`, `median_n_bouts`, `n_prototypes` | scatter (log y); size ~ n_prototypes; same turbo colormap | D |

## Notes

- Highlight is the cluster present in the most models with largest `median_n_bouts` among those (id 13 in the 2026-08 fit). Cluster 49 has a higher median bout count but fewer models.
- Not DA; not a treatment test; not portable `raw_syllable_id`.

## Regen

```powershell
uv run python scratch/nor_object_mi/fig_simpler_first_syllable_signatures.py
```
"""


if __name__ == "__main__":
    raise SystemExit(main())
