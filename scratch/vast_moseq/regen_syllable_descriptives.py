"""VAST syllable descriptives (fig1/2/4/5) from run-phase kinematics.

Uses absorbed bout rows already in
``AZ-SD-VAST-moseq/syllable_bout_kinematics/syllable_bout_kinematics.csv``.
Models = five ``seed_*`` alphabets + ``gerstner_vast_fit`` (fit-on-full).

Regen:
  uv run python scratch/vast_moseq/regen_syllable_descriptives.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import colormaps
from matplotlib.colors import Normalize

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

DEFAULT_KIN = Path(
    r"C:\Users\admin\Documents\work\sack\AZ-SD-VAST-moseq"
    r"\syllable_bout_kinematics\syllable_bout_kinematics.csv"
)
DEFAULT_SIG = Path(
    r"C:\Users\admin\Documents\work\sack\AZ-SD-VAST-moseq"
    r"\syllable_signatures\syllable_prototypes_clustered.csv"
)
DEFAULT_OUT = Path(r"C:\Users\admin\Documents\work\sack\AZ-SD-VAST-moseq\_syllable_descriptives")

MODEL_ORDER = (
    "seed_005",
    "seed_013",
    "seed_042",
    "seed_067",
    "seed_111",
    "gerstner_vast_fit",
)
MODEL_COLORS = {
    "seed_005": "#a8dadc",
    "seed_013": "#457b9d",
    "seed_042": "#1d3557",
    "seed_067": "#e9c46a",
    "seed_111": "#e76f51",
    "gerstner_vast_fit": "#2a9d8f",
}

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "pdf.fonttype": 42,
    }
)


def _save_figure_formats(fig, stem: Path, *, dpi: int = 300) -> None:
    stem = Path(stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(stem.with_suffix(".png"), bbox_inches="tight", dpi=dpi)
    fig.savefig(stem.with_suffix(".pdf"), bbox_inches="tight", dpi=dpi)
    fig.savefig(stem.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)
    for ext in (".png", ".pdf", ".svg"):
        print(f"wrote {stem.with_suffix(ext)}")


def summarize_from_kinematics(kin: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, np.ndarray]]:
    usecols = ["model", "raw_syllable_id", "bout_frames", "kpms_key"]
    model_rows: list[dict] = []
    count_rows: list[dict] = []
    dur_map: dict[str, np.ndarray] = {}

    chunks: list[pd.DataFrame] = []
    for ch in pd.read_csv(kin, usecols=usecols, chunksize=200_000):
        chunks.append(ch)
    df = pd.concat(chunks, ignore_index=True)

    for model in MODEL_ORDER:
        sub = df[df["model"] == model]
        if sub.empty:
            continue
        n_rec = int(sub["kpms_key"].nunique())
        n_frames = int(sub["bout_frames"].sum())
        durs = sub["bout_frames"].to_numpy(dtype=np.int64)
        used = sorted(sub["raw_syllable_id"].unique().tolist())
        g = (
            sub.groupby("raw_syllable_id", sort=True)
            .agg(n_bouts=("bout_frames", "size"), n_frames=("bout_frames", "sum"))
            .reset_index()
        )
        med = sub.groupby("raw_syllable_id")["bout_frames"].median()
        mean = sub.groupby("raw_syllable_id")["bout_frames"].mean()
        p25 = sub.groupby("raw_syllable_id")["bout_frames"].quantile(0.25)
        p75 = sub.groupby("raw_syllable_id")["bout_frames"].quantile(0.75)
        p90 = sub.groupby("raw_syllable_id")["bout_frames"].quantile(0.90)
        ranked = g.sort_values(["n_bouts", "raw_syllable_id"], ascending=[False, True])
        rank_of = {int(s): r for r, s in enumerate(ranked["raw_syllable_id"].tolist())}
        for _, r in g.iterrows():
            sid = int(r["raw_syllable_id"])
            count_rows.append(
                {
                    "model": model,
                    "label": model,
                    "K": 100,
                    "syllable": sid,
                    "raw_syllable_id": sid,
                    "freq_rank": int(rank_of[sid]),
                    "n_bouts": int(r["n_bouts"]),
                    "n_frames": int(r["n_frames"]),
                    "occupancy": float(r["n_frames"]) / float(n_frames) if n_frames else 0.0,
                    "median_bout_frames": float(med.loc[sid]),
                    "mean_bout_frames": float(mean.loc[sid]),
                    "p25_bout_frames": float(p25.loc[sid]),
                    "p75_bout_frames": float(p75.loc[sid]),
                    "p90_bout_frames": float(p90.loc[sid]),
                }
            )
        model_rows.append(
            {
                "model": model,
                "label": model,
                "K": 100,
                "n_recordings": n_rec,
                "n_frames": n_frames,
                "n_syllables_used": len(used),
                "n_bouts": int(len(sub)),
                "median_bout_frames": float(np.median(durs)) if durs.size else float("nan"),
                "mean_bout_frames": float(np.mean(durs)) if durs.size else float("nan"),
            }
        )
        if durs.size > 200_000:
            rng = np.random.default_rng(0)
            dur_map[model] = rng.choice(durs, size=200_000, replace=False)
        else:
            dur_map[model] = durs

    model_df = pd.DataFrame(model_rows)
    model_df["_ord"] = model_df["model"].map({m: i for i, m in enumerate(MODEL_ORDER)})
    model_df = model_df.sort_values("_ord").drop(columns=["_ord"]).reset_index(drop=True)
    return model_df, pd.DataFrame(count_rows), dur_map


def fig_stacked_counts(model_df: pd.DataFrame, count_df: pd.DataFrame, out: Path) -> None:
    order = model_df["model"].tolist()
    max_rank = int(count_df["freq_rank"].max())
    mat = np.zeros((len(order), max_rank + 1))
    for _, r in count_df.iterrows():
        mat[order.index(r["model"]), int(r["freq_rank"])] += r["n_bouts"]
    y = np.arange(len(order))
    cmap = colormaps["viridis"]
    norm = Normalize(vmin=0, vmax=max_rank)
    fig, ax = plt.subplots(figsize=(8.0, 3.8))
    left = np.zeros(len(order))
    for rank in range(max_rank + 1):
        vals = mat[:, rank]
        if vals.sum() == 0:
            continue
        ax.barh(y, vals, left=left, height=0.72, color=cmap(norm(rank)), edgecolor="none")
        left += vals
    ax.set_yticks(y)
    ax.set_yticklabels(order)
    ax.set_xlabel("Syllable bout count (run-phase, primary cohort)")
    ax.set_ylabel("Model (seed)")
    ax.set_title("Syllable bout inventory by frequency rank (absorb <3 Â· run)")
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("Frequency rank (0 = most used)")
    for i in range(len(order)):
        tot = mat[i].sum()
        ax.text(tot * 1.01, i, f"{tot / 1e3:.0f}k", va="center", ha="left", fontsize=7, color="#444")
    ax.set_xlim(0, mat.sum(1).max() * 1.14)
    fig.text(
        0.01,
        0.005,
        "Source: AZ-SD-VAST-moseq Â· gerstner primary keys Â· run phase Â· 1840 trials/seed",
        fontsize=7,
        color="#555",
    )
    _save_figure_formats(fig, out / "fig1_stacked_bout_counts_clean")


def fig_duration_box(model_df: pd.DataFrame, durs: dict[str, np.ndarray], out: Path) -> None:
    order = model_df["model"].tolist()
    y = np.arange(len(order))
    data = [durs[m] for m in order]
    fig, ax = plt.subplots(figsize=(8.0, 3.8))
    bp = ax.boxplot(
        data,
        vert=False,
        positions=y,
        widths=0.65,
        showfliers=False,
        patch_artist=True,
        medianprops=dict(color="black", lw=1.2),
        whiskerprops=dict(color="#444"),
        capprops=dict(color="#444"),
        boxprops=dict(edgecolor="#444", lw=0.8),
    )
    for i, m in enumerate(order):
        bp["boxes"][i].set_facecolor(MODEL_COLORS.get(m, "#888"))
    ax.set_yticks(y)
    ax.set_yticklabels(order)
    ax.set_xlabel("Bout duration (frames)")
    ax.set_ylabel("Model")
    ax.set_title("Pooled syllable bout duration by seed (absorb <3 Â· run)")
    ax.set_xscale("log")
    fig.text(
        0.01,
        0.005,
        "Source: AZ-SD-VAST-moseq Â· subsampled â‰¤200k bouts/seed Â· outliers hidden Â· log x",
        fontsize=7,
        color="#555",
    )
    _save_figure_formats(fig, out / "fig2_bout_duration_boxplot_clean")


def fig_inventory_scatter(model_df: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(5.2, 4.0))
    for _, row in model_df.iterrows():
        ax.scatter(
            row["n_syllables_used"],
            row["median_bout_frames"],
            s=90,
            color=MODEL_COLORS.get(row["model"], "#888"),
            edgecolors="white",
            lw=0.5,
            zorder=3,
            label=row["model"],
        )
    ax.set_xlabel("Syllables used (of K=100)")
    ax.set_ylabel("Median bout duration (frames)")
    ax.set_title("Segmentation grain vs syllable inventory (run)")
    ax.legend(frameon=False, fontsize=8)
    fig.text(0.01, -0.02, "Source: AZ-SD-VAST-moseq Â· frames", fontsize=7, color="#555")
    _save_figure_formats(fig, out / "fig4_inventory_vs_median_duration_clean")


def fig_median_duration_heatmap(
    model_df: pd.DataFrame,
    count_df: pd.DataFrame,
    out: Path,
    *,
    vmax: float,
    cluster_df: pd.DataFrame | None = None,
) -> None:
    order = model_df["model"].tolist()
    n_ranks = int(count_df["freq_rank"].max()) + 1
    heat = np.full((len(order), n_ranks), np.nan)
    for _, r in count_df.iterrows():
        heat[order.index(r["model"]), int(r["freq_rank"])] = r["median_bout_frames"]

    fig, ax = plt.subplots(figsize=(max(8.0, 0.18 * n_ranks + 3.0), 3.6))
    im = ax.imshow(heat, aspect="auto", cmap="magma", interpolation="nearest", vmin=0, vmax=vmax)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(order, fontsize=8)
    xt = list(range(0, n_ranks, 5))
    if (n_ranks - 1) not in xt:
        xt.append(n_ranks - 1)
    ax.set_xticks(xt)
    ax.set_xlabel("Frequency rank (0 = most used)")
    ax.set_ylabel("Model")
    ax.set_title("Median bout duration (frames) â€” all syllables Â· K=100 Â· absorb <3")
    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label(f"Median bout duration (frames; clipped at {vmax:g})")
    fig.text(
        0.01,
        0.005,
        "Source: AZ-SD-VAST-moseq Â· within-model frequency rank Â· run phase",
        fontsize=7,
        color="#555",
    )
    _save_figure_formats(fig, out / "fig5_median_duration_heatmap_K100_clean")

    if cluster_df is None or cluster_df.empty:
        return
    # Cluster colormap: fill = cluster_id; text = median frames
    merged = count_df.merge(
        cluster_df[["model", "raw_syllable_id", "cluster_id"]],
        on=["model", "raw_syllable_id"],
        how="left",
    )
    cid_mat = np.full((len(order), n_ranks), np.nan)
    text_mat = np.full((len(order), n_ranks), np.nan)
    for _, r in merged.iterrows():
        i = order.index(r["model"])
        j = int(r["freq_rank"])
        text_mat[i, j] = r["median_bout_frames"]
        if pd.notna(r.get("cluster_id")) and int(r["cluster_id"]) >= 0:
            cid_mat[i, j] = int(r["cluster_id"])
    vmax_c = float(np.nanmax(cid_mat)) if np.isfinite(np.nanmax(cid_mat)) else 1.0
    fig, ax = plt.subplots(figsize=(max(8.0, 0.18 * n_ranks + 3.0), 3.6))
    cmap = colormaps["turbo"].copy()
    cmap.set_bad("#d9d9d9")
    im = ax.imshow(cid_mat, aspect="auto", cmap=cmap, interpolation="nearest", vmin=0, vmax=vmax_c)
    for i in range(len(order)):
        for j in range(n_ranks):
            if np.isfinite(text_mat[i, j]):
                ax.text(
                    j,
                    i,
                    f"{text_mat[i, j]:.0f}",
                    ha="center",
                    va="center",
                    fontsize=5.5,
                    color="black",
                )
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(order, fontsize=8)
    ax.set_xticks(xt)
    ax.set_xlabel("Frequency rank (0 = most used)")
    ax.set_ylabel("Model")
    ax.set_title("Median bout duration (frames) â€” cluster colormap Â· K=100 Â· absorb <3")
    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("cluster_id")
    fig.text(
        0.01,
        0.005,
        "Fill = HDBSCAN cluster_id (turbo; fit-specific). Light grey = not in signature table "
        "(n_bouts < 10). Cell text = median bout frames.",
        fontsize=7,
        color="#555",
    )
    _save_figure_formats(fig, out / "fig5_median_duration_heatmap_K100_clean_cluster_cmap")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--kinematics-csv", type=Path, default=DEFAULT_KIN)
    ap.add_argument("--signatures-csv", type=Path, default=DEFAULT_SIG)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    model_df, count_df, dur_map = summarize_from_kinematics(args.kinematics_csv)
    model_df.to_csv(out / "model_summary_clean.csv", index=False)
    count_df.to_csv(out / "syllable_counts_clean.csv", index=False)
    np.savez_compressed(out / "duration_subsamples_clean.npz", **dur_map)

    cluster_df = None
    if args.signatures_csv.is_file():
        cluster_df = pd.read_csv(args.signatures_csv)

    vmax = float(np.percentile(count_df["median_bout_frames"], 95))
    vmax = max(20.0, round(vmax))
    fig_stacked_counts(model_df, count_df, out)
    fig_duration_box(model_df, dur_map, out)
    fig_inventory_scatter(model_df, out)
    fig_median_duration_heatmap(model_df, count_df, out, vmax=vmax, cluster_df=cluster_df)

    summary = {
        "kinematics_csv": str(args.kinematics_csv),
        "n_models": int(len(model_df)),
        "heatmap_vmax": vmax,
        "models": model_df.to_dict(orient="records"),
    }
    (out / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"wrote descriptives -> {out}", flush=True)
    print(model_df[["model", "n_syllables_used", "n_bouts", "median_bout_frames"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
