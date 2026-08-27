"""Figure: novelty Δ (nvl−fam) vs spatial-locus Δ (B−A) on novel_obj."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy import stats


def _load(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _p_text(p: float) -> str:
    if p < 1e-4:
        return "p < 10⁻⁴"
    if p < 0.001:
        return f"p = {p:.1e}"
    return f"p = {p:.3f}"


def _paired(
    ax,
    left: np.ndarray,
    right: np.ndarray,
    *,
    labels: tuple[str, str],
    title: str,
    ink: str,
    mute: str,
    accent: str,
    delta_name: str,
) -> None:
    delta = right - left
    n = len(delta)
    rng = np.random.default_rng(0)
    x0 = rng.normal(0, 0.03, n)
    x1 = 1.0 + rng.normal(0, 0.03, n)
    for a, b, xa, xb in zip(left, right, x0, x1):
        ax.plot([xa, xb], [a, b], color="#c8c8c8", lw=0.35, zorder=1)
    ax.scatter(x0, left, s=8, c=mute, alpha=0.75, edgecolors="none", zorder=2)
    ax.scatter(x1, right, s=8, c=accent, alpha=0.85, edgecolors="none", zorder=2)
    ax.plot([-0.18, 0.18], [np.median(left)] * 2, color=ink, lw=2.0, zorder=3)
    ax.plot([0.82, 1.18], [np.median(right)] * 2, color=ink, lw=2.0, zorder=3)
    ax.axhline(0.0, color="#bbbbbb", lw=0.7, ls="--", zorder=0)
    ax.set_xlim(-0.45, 1.45)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(list(labels))
    ax.set_title(title, loc="left", fontweight="bold", color=ink)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    _, wp = stats.wilcoxon(delta, alternative="two-sided", zero_method="wilcox")
    ax.text(
        0.02,
        0.98,
        f"n={n}\nmedian {delta_name}={np.median(delta):+.3f}\n"
        f"%{delta_name}>0={100 * np.mean(delta > 0):.0f}\nWilcoxon {_p_text(float(wp))}",
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=7.5,
        color=ink,
        bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#dddddd", lw=0.6),
    )


def make_figure(rows: list[dict[str, str]], *, out_stem: Path, phase_layer: str, dpi: int = 300) -> None:
    ink, mute, accent = "#1a1a1a", "#6b6b6b", "#2f5d8a"
    terracotta = "#8a4f3d"

    fam = np.asarray([float(r["excess_fam"]) for r in rows])
    nvl = np.asarray([float(r["excess_nvl"]) for r in rows])
    la = np.asarray([float(r["excess_locus_a"]) for r in rows])
    lb = np.asarray([float(r["excess_locus_b"]) for r in rows])
    d_nov = nvl - fam
    d_spa = lb - la

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.labelsize": 9,
            "axes.titlesize": 9.5,
            "axes.linewidth": 0.8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )

    fig = plt.figure(figsize=(8.6, 3.8), constrained_layout=True)
    gs = fig.add_gridspec(1, 3, width_ratios=[1.0, 1.0, 1.05])
    ax0 = fig.add_subplot(gs[0, 0])
    ax1 = fig.add_subplot(gs[0, 1], sharey=ax0)
    ax2 = fig.add_subplot(gs[0, 2])

    _paired(
        ax0,
        fam,
        nvl,
        labels=("fam", "nvl"),
        title="A  Role contrast",
        ink=ink,
        mute=mute,
        accent=accent,
        delta_name="Δ_nov",
    )
    ax0.set_ylabel("excess MI (bits)")
    _paired(
        ax1,
        la,
        lb,
        labels=("locus A", "locus B"),
        title="B  Spatial contrast",
        ink=ink,
        mute=mute,
        accent=terracotta,
        delta_name="Δ_spa",
    )

    # C: both deltas as jittered points
    rng = np.random.default_rng(1)
    x0 = rng.normal(0, 0.04, len(d_nov))
    x1 = 1.0 + rng.normal(0, 0.04, len(d_spa))
    ax2.axhline(0.0, color="#bbbbbb", lw=0.7, ls="--", zorder=0)
    ax2.scatter(x0, d_nov, s=10, c=accent, alpha=0.75, edgecolors="none", zorder=2)
    ax2.scatter(x1, d_spa, s=10, c=terracotta, alpha=0.75, edgecolors="none", zorder=2)
    ax2.plot([-0.18, 0.18], [np.median(d_nov)] * 2, color=ink, lw=2.0, zorder=3)
    ax2.plot([0.82, 1.18], [np.median(d_spa)] * 2, color=ink, lw=2.0, zorder=3)
    ax2.set_xlim(-0.45, 1.45)
    ax2.set_xticks([0, 1])
    ax2.set_xticklabels(["Δ_nov\n(nvl−fam)", "Δ_spa\n(B−A)"])
    ax2.set_ylabel("Δ excess MI (bits)")
    ax2.set_title("C  Contrast magnitudes", loc="left", fontweight="bold", color=ink)
    for spine in ("top", "right"):
        ax2.spines[spine].set_visible(False)
    # paired comparison of |Δ|? report Spearman of the two deltas
    rho, rp = stats.spearmanr(d_nov, d_spa)
    ax2.text(
        0.98,
        0.98,
        f"Spearman(Δ_nov, Δ_spa)\nρ={rho:.2f}  {_p_text(float(rp))}",
        transform=ax2.transAxes,
        va="top",
        ha="right",
        fontsize=7.5,
        color=ink,
        bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#dddddd", lw=0.6),
    )

    fig.suptitle(
        f"Novelty role Δ vs spatial-locus Δ — {phase_layer} (novel_obj)",
        fontsize=11,
        fontweight="bold",
        color=ink,
    )
    fig.text(
        0.0,
        -0.02,
        "Same bouts / animals. Role = fam vs nvl object distance. Spatial = loci A/B "
        "(animal×phase 2-means; centers matched). Frozen shared dist bins; n_perm=100 exploratory.",
        fontsize=6.5,
        color=mute,
        ha="left",
        va="top",
    )
    out_stem.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_stem.with_suffix(".pdf"), bbox_inches="tight", dpi=dpi)
    fig.savefig(out_stem.with_suffix(".png"), bbox_inches="tight", dpi=dpi)
    plt.close(fig)
    print(f"wrote {out_stem.with_suffix('.pdf')}")
    print(f"wrote {out_stem.with_suffix('.png')}")


def main() -> int:
    root = Path(
        r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
        r"\_nor_object_mi\paramscan_s1-1e8_s2-1e5_ss-50"
    )
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--delta-csv",
        type=Path,
        default=root / "novelty_loci" / "mi_delta_novelty_loci_per_animal.csv",
    )
    ap.add_argument("--out-stem", type=Path, default=None)
    args = ap.parse_args()
    rows = _load(args.delta_csv)
    phase = str(rows[0]["phase_layer"]) if rows else "NOR_TX"
    out = args.out_stem or (args.delta_csv.parent / "fig_novelty_loci_contrast")
    make_figure(rows, out_stem=out, phase_layer=phase)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
