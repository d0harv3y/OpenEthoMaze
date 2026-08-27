"""Figure: presence Δ for nearest vs independent spatial loci A/B."""

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


def make_figure(rows: list[dict[str, str]], *, out_stem: Path, phase_layer: str, dpi: int = 300) -> None:
    ink, mute, accent = "#1a1a1a", "#6b6b6b", "#2f5d8a"
    locus_order = [("any", "nearest"), ("a", "locus A"), ("b", "locus B")]

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

    fig, axes = plt.subplots(1, 3, figsize=(8.8, 3.6), sharey=True, constrained_layout=True)
    rng = np.random.default_rng(0)

    for ax, (locus, title) in zip(axes, locus_order):
        sub = [r for r in rows if r.get("locus") == locus]
        if not sub:
            ax.set_title(f"{title}: empty")
            continue
        present = np.asarray([float(r["excess_present"]) for r in sub])
        absent = np.asarray([float(r["excess_absent"]) for r in sub])
        delta = present - absent
        n = len(delta)
        x0 = rng.normal(0, 0.03, n)
        x1 = 1.0 + rng.normal(0, 0.03, n)
        for a, b, xa, xb in zip(absent, present, x0, x1):
            ax.plot([xa, xb], [a, b], color="#c8c8c8", lw=0.35, zorder=1)
        ax.scatter(x0, absent, s=8, c=mute, alpha=0.75, edgecolors="none", zorder=2)
        ax.scatter(x1, present, s=8, c=accent, alpha=0.85, edgecolors="none", zorder=2)
        ax.plot([-0.18, 0.18], [np.median(absent)] * 2, color=ink, lw=2.0, zorder=3)
        ax.plot([0.82, 1.18], [np.median(present)] * 2, color=ink, lw=2.0, zorder=3)
        ax.axhline(0.0, color="#bbbbbb", lw=0.7, ls="--", zorder=0)
        ax.set_xlim(-0.45, 1.45)
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["no object", "identical\nobjects"])
        ax.set_title(title, loc="left", fontweight="bold", color=ink)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
        _, wp = stats.wilcoxon(delta, alternative="two-sided", zero_method="wilcox")
        ax.text(
            0.02,
            0.98,
            f"n={n}\nmedian Δ={np.median(delta):.3f}\n"
            f"%Δ>0={100 * np.mean(delta > 0):.0f}\nWilcoxon {_p_text(float(wp))}",
            transform=ax.transAxes,
            va="top",
            ha="left",
            fontsize=7.5,
            color=ink,
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#dddddd", lw=0.6),
        )

    axes[0].set_ylabel("excess MI (bits)")
    fig.suptitle(
        f"Presence boost: nearest vs independent loci — {phase_layer}",
        fontsize=11,
        fontweight="bold",
        color=ink,
    )
    fig.text(
        0.0,
        -0.02,
        "Locus A/B = animal×phase 2-means (lower-x = A). Identical: real centers matched to A/B. "
        "no_obj: pseudo-loci. Same animals; gray lines = animal pairs. Frozen dist_any bins; "
        "n_perm=100 exploratory.",
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
        default=root / "presence_loci" / "mi_delta_presence_per_animal_loci.csv",
    )
    ap.add_argument("--out-stem", type=Path, default=None)
    ap.add_argument("--phase-layer", type=str, default="NOR_TX")
    args = ap.parse_args()
    out = args.out_stem or (args.delta_csv.parent / "fig_presence_loci_independent")
    rows = _load(args.delta_csv)
    phase = args.phase_layer
    if rows:
        phase = str(rows[0].get("phase_layer") or phase)
    make_figure(rows, out_stem=out, phase_layer=phase)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
