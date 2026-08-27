"""Fig5 median-duration heatmaps recolored by HDBSCAN cluster_id (turbo cmap).

Same layout as `_syllable_descriptives/regen_descriptives.py` fig5 (model × freq rank),
but cell fill = cluster_id color. Syllables absent from the signature table (n_bouts < 10)
are light grey; HDBSCAN noise (−1) uses the shared noise grey.

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/fig_duration_heatmap_cluster_cmap.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.fig_simpler_first_syllable_signatures import (  # noqa: E402
    NOISE_COLOR,
    add_cluster_id_colorbar,
    build_cluster_color_lookup,
)

DEFAULT_DESC = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017\_syllable_descriptives"
)
DEFAULT_SIG = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_syllable_signatures"
)
UNMAPPED_COLOR = "#e8e8e8"
MIN_BOUT = 3


def _parse_models(model_df: pd.DataFrame) -> tuple[list[str], dict[str, str]]:
    order = model_df["model"].tolist()
    label_map = dict(zip(model_df["model"], model_df["label"]))
    return order, label_map


def cluster_key_map(proto: pd.DataFrame) -> dict[tuple[str, int], int]:
    out: dict[tuple[str, int], int] = {}
    for row in proto.itertuples(index=False):
        out[(str(row.model), int(row.raw_syllable_id))] = int(row.cluster_id)
    return out


def cluster_rgba_grid(
    sub_c: pd.DataFrame,
    order: list[str],
    cluster_by_key: dict[tuple[str, int], int],
    lookup: dict[int, tuple[float, float, float, float]],
) -> tuple[np.ndarray, np.ndarray]:
    n_ranks = int(sub_c["freq_rank"].max()) + 1
    rgba = np.tile(mcolors.to_rgba(UNMAPPED_COLOR), (len(order), n_ranks, 1))
    dur = np.full((len(order), n_ranks), np.nan)
    unmapped = mcolors.to_rgba(UNMAPPED_COLOR)
    for row in sub_c.itertuples(index=False):
        i = order.index(str(row.model))
        j = int(row.freq_rank)
        dur[i, j] = float(row.median_bout_frames)
        key = (str(row.model), int(row.syllable))
        cid = cluster_by_key.get(key)
        if cid is None:
            rgba[i, j] = unmapped
        else:
            rgba[i, j] = lookup.get(int(cid), lookup[-1])
    return rgba, dur


def fig_heatmap_cluster_cmap(
    model_df: pd.DataFrame,
    count_df: pd.DataFrame,
    cluster_by_key: dict[tuple[str, int], int],
    lookup: dict[int, tuple[float, float, float, float]],
    cluster_ids: list[int],
    listed,
    *,
    K: int,
    out: Path,
    annotate_duration: bool = True,
) -> None:
    sub_m = model_df[model_df.K == K].copy()
    if sub_m.empty:
        return
    order, label_map = _parse_models(sub_m)
    sub_c = count_df[count_df["model"].isin(order)]
    rgba, dur = cluster_rgba_grid(sub_c, order, cluster_by_key, lookup)
    n_ranks = rgba.shape[1]
    fig_w = max(8.0, 0.11 * n_ranks + 4.0)
    fig, ax = plt.subplots(figsize=(fig_w, max(3.2, 0.45 * len(order) + 1.8)))
    ax.imshow(rgba, aspect="auto", interpolation="nearest")
    if annotate_duration:
        for i in range(rgba.shape[0]):
            for j in range(rgba.shape[1]):
                v = dur[i, j]
                if not np.isfinite(v):
                    continue
                lum = 0.299 * rgba[i, j, 0] + 0.587 * rgba[i, j, 1] + 0.114 * rgba[i, j, 2]
                ax.text(
                    j,
                    i,
                    f"{v:.0f}",
                    ha="center",
                    va="center",
                    fontsize=5.5,
                    color="white" if lum < 0.55 else "#1a1a1a",
                )
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([label_map[m] for m in order], fontsize=8)
    xt = list(range(0, n_ranks, 5))
    if (n_ranks - 1) not in xt:
        xt.append(n_ranks - 1)
    ax.set_xticks(xt)
    ax.set_xticklabels([str(t) for t in xt])
    ax.set_xlabel("Frequency rank (0 = most used)")
    ax.set_ylabel("Model")
    ax.set_title(
        f"Median bout duration (frames) — cluster colormap · K={K} · absorb <{MIN_BOUT}",
    )
    add_cluster_id_colorbar(fig, ax, cluster_ids, listed, dest="paper")
    fig.text(
        0.01,
        0.005,
        "Fill = HDBSCAN cluster_id (turbo; fit-specific). Light grey = not in signature table "
        "(n_bouts < 10). Cell text = median bout frames. Source: syllable_counts_clean + signatures.",
        fontsize=7,
        color="#555",
    )
    stem = f"fig5_median_duration_heatmap_K{K}_clean_cluster_cmap"
    fig.savefig(out / f"{stem}.png", dpi=300, bbox_inches="tight")
    fig.savefig(out / f"{stem}.pdf", bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {stem}", flush=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--desc-dir", type=Path, default=DEFAULT_DESC)
    ap.add_argument("--sig-dir", type=Path, default=DEFAULT_SIG)
    ap.add_argument("--no-duration-text", action="store_true")
    args = ap.parse_args(argv)

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

    out = args.desc_dir
    model_df = pd.read_csv(out / "model_summary_clean.csv")
    count_df = pd.read_csv(out / "syllable_counts_clean.csv")
    proto = pd.read_csv(args.sig_dir / "syllable_prototypes_clustered.csv")
    summary = pd.read_csv(args.sig_dir / "cluster_summary.csv")
    lookup, cluster_ids, listed = build_cluster_color_lookup(summary)
    cluster_by_key = cluster_key_map(proto)

    for K in (50, 75, 100):
        fig_heatmap_cluster_cmap(
            model_df,
            count_df,
            cluster_by_key,
            lookup,
            cluster_ids,
            listed,
            K=K,
            out=out,
            annotate_duration=not args.no_duration_text,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
