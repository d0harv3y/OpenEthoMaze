"""Descriptives figures from _ngram_mine grid (max_n=5, raw+clean)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

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


def _coverage_block(df: pd.DataFrame, model: str, tag: str) -> list[dict]:
    rows = []
    for n, sub in df.groupby("pattern_len"):
        sub = sub.sort_values("count", ascending=False)
        c = sub["count"].to_numpy(dtype=float)
        mass = c / c.sum()
        cum = np.cumsum(mass)

        def k_for(p: float) -> int:
            return int(np.searchsorted(cum, p) + 1)

        rows.append(
            {
                "model": model,
                "tag": tag,
                "n": int(n),
                "n_patterns": len(c),
                "total_occ": int(c.sum()),
                "median_occ": float(np.median(c)),
                "median_span": float(sub["mean_span_frames"].median()),
                "K50": k_for(0.5),
                "K80": k_for(0.8),
            }
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--mine-root",
        type=Path,
        default=Path(
            r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017\_ngram_mine"
        ),
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Default: <mine-root>/_descriptives",
    )
    args = p.parse_args(argv)
    mine_root = args.mine_root
    out_dir = args.out_dir or (mine_root / "_descriptives")
    out_dir.mkdir(parents=True, exist_ok=True)

    cov_rows: list[dict] = []
    for model_dir in sorted(mine_root.iterdir()):
        if not model_dir.is_dir() or not model_dir.name.startswith("paramscan_"):
            continue
        for tag in ("raw", "clean"):
            csv_path = model_dir / tag / "ngram_counts.csv"
            if not csv_path.exists():
                continue
            df = pd.read_csv(csv_path)
            cov_rows.extend(_coverage_block(df, model_dir.name, tag))

    if not cov_rows:
        print(json.dumps({"status": "failed", "reason": "no ngram_counts.csv yet"}))
        return 1

    cov = pd.DataFrame(cov_rows)
    cov.to_csv(out_dir / "coverage_by_model_n.csv", index=False)

    # Aggregate across models: median K80 / median_occ by tag × n
    agg = (
        cov.groupby(["tag", "n"], as_index=False)
        .agg(
            median_K80=("K80", "median"),
            median_K50=("K50", "median"),
            median_median_occ=("median_occ", "median"),
            median_n_patterns=("n_patterns", "median"),
            median_span=("median_span", "median"),
            n_models=("model", "nunique"),
        )
        .sort_values(["tag", "n"])
    )
    agg.to_csv(out_dir / "coverage_agg_by_tag_n.csv", index=False)

    colors = {"raw": "#e76f51", "clean": "#2a9d8f"}

    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.8), sharex=True)
    for ax, metric, title in zip(
        axes,
        ["median_K80", "median_median_occ"],
        ["Median K80 across models", "Median of per-model median occ"],
    ):
        for tag, g in agg.groupby("tag"):
            ax.plot(
                g["n"],
                g[metric],
                "o-",
                color=colors[tag],
                lw=1.4,
                ms=5,
                label=tag,
            )
        ax.set_xlabel("n-gram order n")
        ax.set_title(title)
        ax.set_xticks(sorted(agg["n"].unique()))
        if metric.endswith("occ"):
            ax.set_yscale("log")
    axes[0].set_ylabel("Patterns")
    axes[1].set_ylabel("Count")
    axes[0].legend(frameon=False)
    fig.suptitle("Impress n-gram inventory (max_n=5 mine grid)", y=1.02)
    fig.text(
        0.01,
        -0.04,
        "Source: _ngram_mine/*/raw|clean/ngram_counts.csv · knobs: filter use_n / max_span later",
        fontsize=7,
        color="#555",
    )
    fig.tight_layout()
    fig.savefig(out_dir / "fig_ngram_coverage_agg.png")
    fig.savefig(out_dir / "fig_ngram_coverage_agg.pdf")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5.5, 3.8))
    for tag, g in agg.groupby("tag"):
        ax.plot(g["n"], g["median_span"], "o-", color=colors[tag], lw=1.4, ms=5, label=tag)
    ax.set_xlabel("n-gram order n")
    ax.set_ylabel("Median mean_span_frames (across models)")
    ax.set_title("Typical n-gram span vs order")
    ax.set_xticks(sorted(agg["n"].unique()))
    ax.legend(frameon=False)
    fig.text(0.01, -0.02, "Source: pattern mean_span_frames medians", fontsize=7, color="#555")
    fig.savefig(out_dir / "fig_ngram_span_agg.png")
    fig.savefig(out_dir / "fig_ngram_span_agg.pdf")
    plt.close(fig)

    print(json.dumps({"status": "ok", "out_dir": str(out_dir), "n_rows": len(cov)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
