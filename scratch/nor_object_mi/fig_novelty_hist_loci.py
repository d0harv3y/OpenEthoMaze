"""Figure: role Δ vs fixed-hist locus Δ vs nvl-side-tagged hist Δ."""

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
    green = "#5a7a5a"

    fam = np.asarray([float(r["excess_fam"]) for r in rows])
    nvl = np.asarray([float(r["excess_nvl"]) for r in rows])
    la = np.asarray([float(r["excess_locus_a"]) for r in rows])
    lb = np.asarray([float(r["excess_locus_b"]) for r in rows])
    nvl_side = np.asarray([float(r["excess_nvl_side_hist"]) for r in rows])
    other = np.asarray([float(r["excess_other_hist"]) for r in rows])
    d_nov = nvl - fam
    d_spa = lb - la
    d_side = nvl_side - other
    n_a = sum(1 for r in rows if r.get("nvl_nearest_hist_locus") == "a")
    n_b = sum(1 for r in rows if r.get("nvl_nearest_hist_locus") == "b")

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

    fig = plt.figure(figsize=(10.2, 3.8), constrained_layout=True)
    gs = fig.add_gridspec(1, 4, width_ratios=[1.0, 1.0, 1.0, 1.05])
    ax0 = fig.add_subplot(gs[0, 0])
    ax1 = fig.add_subplot(gs[0, 1], sharey=ax0)
    ax2 = fig.add_subplot(gs[0, 2], sharey=ax0)
    ax3 = fig.add_subplot(gs[0, 3])

    _paired(ax0, fam, nvl, labels=("fam", "nvl"), title="A  Role", ink=ink, mute=mute, accent=accent, delta_name="Δ_nov")
    ax0.set_ylabel("excess MI (bits)")
    _paired(
        ax1,
        la,
        lb,
        labels=("hist A", "hist B"),
        title="B  Fixed hist loci",
        ink=ink,
        mute=mute,
        accent=terracotta,
        delta_name="Δ_spa",
    )
    _paired(
        ax2,
        other,
        nvl_side,
        labels=("other hist", "nvl-side\nhist"),
        title="C  Nvl-tagged hist",
        ink=ink,
        mute=mute,
        accent=green,
        delta_name="Δ_side",
    )

    rng = np.random.default_rng(1)
    xs = [rng.normal(i, 0.04, len(rows)) for i in range(3)]
    for x, y, c in zip(xs, (d_nov, d_spa, d_side), (accent, terracotta, green)):
        ax3.scatter(x, y, s=9, c=c, alpha=0.75, edgecolors="none", zorder=2)
        ax3.plot([x.mean() - 0.18, x.mean() + 0.18], [np.median(y)] * 2, color=ink, lw=2.0, zorder=3)
    ax3.axhline(0.0, color="#bbbbbb", lw=0.7, ls="--", zorder=0)
    ax3.set_xlim(-0.5, 2.5)
    ax3.set_xticks([0, 1, 2])
    ax3.set_xticklabels(["Δ_nov", "Δ_spa\n(B−A)", "Δ_side\n(nvl−other)"])
    ax3.set_ylabel("Δ excess MI (bits)")
    ax3.set_title("D  Contrasts", loc="left", fontweight="bold", color=ink)
    for spine in ("top", "right"):
        ax3.spines[spine].set_visible(False)
    rho_ns, p_ns = stats.spearmanr(d_nov, d_side)
    rho_ss, p_ss = stats.spearmanr(d_spa, d_side)
    ax3.text(
        0.98,
        0.98,
        f"nvl@A={n_a} @B={n_b}\n"
        f"ρ(Δ_nov,Δ_side)={rho_ns:.2f} {_p_text(float(p_ns))}\n"
        f"ρ(Δ_spa,Δ_side)={rho_ss:.2f} {_p_text(float(p_ss))}",
        transform=ax3.transAxes,
        va="top",
        ha="right",
        fontsize=7,
        color=ink,
        bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#dddddd", lw=0.6),
    )

    fig.suptitle(
        f"Novelty role vs fixed historical loci — {phase_layer} (novel_obj)",
        fontsize=11,
        fontweight="bold",
        color=ink,
    )
    fig.text(
        0.0,
        -0.02,
        "Hist A/B = animal×phase 2-means (fixed targets). Nvl-side = hist locus nearer the session "
        "novel object. Role channels still use session fam/nvl centers. Frozen shared bins; n_perm=100.",
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
        default=root / "novelty_hist_loci" / "mi_delta_novelty_loci_per_animal.csv",
    )
    ap.add_argument("--out-stem", type=Path, default=None)
    args = ap.parse_args()
    rows = _load(args.delta_csv)
    phase = str(rows[0]["phase_layer"]) if rows else "NOR_TX"
    out = args.out_stem or (args.delta_csv.parent / "fig_novelty_hist_loci")
    make_figure(rows, out_stem=out, phase_layer=phase)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
