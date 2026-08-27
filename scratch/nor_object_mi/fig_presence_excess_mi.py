"""Publication-style figure: object presence raises excess I(syll; dist_any).

Outputs PDF + PNG next to the presence pilot artifacts.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy import stats


def _load_delta(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _p_text(p: float) -> str:
    if p < 1e-4:
        return "p < 10⁻⁴"
    if p < 0.001:
        return f"p = {p:.1e}"
    return f"p = {p:.3f}"


def make_figure(
    rows: list[dict[str, str]],
    *,
    out_stem: Path,
    phase_layer: str = "NOR_TX",
    dpi: int = 300,
) -> None:
    present = np.asarray([float(r["excess_present"]) for r in rows], dtype=np.float64)
    absent = np.asarray([float(r["excess_absent"]) for r in rows], dtype=np.float64)
    delta = np.asarray([float(r["delta_excess_present_minus_absent"]) for r in rows], dtype=np.float64)
    sexes = [str(r["sex"]) for r in rows]
    txs = [str(r["tx"]) for r in rows]

    w_stat, w_p = stats.wilcoxon(delta, alternative="two-sided", zero_method="wilcox")
    n = len(delta)
    frac_pos = float(np.mean(delta > 0))

    # Style: journal-like, flat, no chartjunk
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.labelsize": 10,
            "axes.titlesize": 10,
            "axes.linewidth": 0.8,
            "xtick.major.width": 0.8,
            "ytick.major.width": 0.8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )

    fig = plt.figure(figsize=(7.2, 3.4), constrained_layout=True)
    gs = fig.add_gridspec(1, 3, width_ratios=[1.15, 1.0, 1.15])
    ax0 = fig.add_subplot(gs[0, 0])
    ax1 = fig.add_subplot(gs[0, 1])
    ax2 = fig.add_subplot(gs[0, 2])

    ink = "#1a1a1a"
    mute = "#6b6b6b"
    accent = "#2f5d8a"  # steel, not purple

    # --- A: paired absent vs present ---
    rng = np.random.default_rng(0)
    x0 = np.full(n, 0.0) + rng.normal(0, 0.03, n)
    x1 = np.full(n, 1.0) + rng.normal(0, 0.03, n)
    for a, b, xa, xb in zip(absent, present, x0, x1):
        ax0.plot([xa, xb], [a, b], color="#c8c8c8", lw=0.45, zorder=1)
    ax0.scatter(x0, absent, s=10, c=mute, alpha=0.75, edgecolors="none", zorder=2, label="absent")
    ax0.scatter(x1, present, s=10, c=accent, alpha=0.85, edgecolors="none", zorder=2, label="present")

    # median markers
    ax0.plot([-0.18, 0.18], [np.median(absent)] * 2, color=ink, lw=2.0, zorder=3)
    ax0.plot([0.82, 1.18], [np.median(present)] * 2, color=ink, lw=2.0, zorder=3)

    ax0.axhline(0.0, color="#bbbbbb", lw=0.7, ls="--", zorder=0)
    ax0.set_xlim(-0.45, 1.45)
    ax0.set_xticks([0, 1])
    ax0.set_xticklabels(["no object\n(pseudo-loci)", "identical\nobjects"])
    ax0.set_ylabel("excess MI (bits)\nI(syllable; dist_any bin) − null")
    ax0.set_title("A  Object presence vs absence", loc="left", fontweight="bold", color=ink)
    for spine in ("top", "right"):
        ax0.spines[spine].set_visible(False)

    # --- B: Δ histogram ---
    bins = np.linspace(np.min(delta) - 0.02, np.max(delta) + 0.02, 19)
    ax1.hist(delta, bins=bins, color=accent, alpha=0.85, edgecolor="white", linewidth=0.4)
    ax1.axvline(0.0, color=ink, lw=1.0, ls="--")
    ax1.axvline(float(np.median(delta)), color=ink, lw=1.6)
    ax1.set_xlabel("Δ excess MI (bits)\npresent − absent")
    ax1.set_ylabel("animals (n)")
    ax1.set_title("B  Paired contrast", loc="left", fontweight="bold", color=ink)
    for spine in ("top", "right"):
        ax1.spines[spine].set_visible(False)

    note = (
        f"n = {n}\n"
        f"median Δ = {np.median(delta):.3f} bits\n"
        f"{frac_pos * 100:.0f}% Δ > 0\n"
        f"Wilcoxon {_p_text(float(w_p))}"
    )
    ax1.text(
        0.98,
        0.98,
        note,
        transform=ax1.transAxes,
        va="top",
        ha="right",
        fontsize=8,
        color=ink,
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="#dddddd", linewidth=0.6),
    )

    # --- C: sex × tx median Δ ---
    tx_order = ["noSD", "GHSD", "RBSD"]
    sex_order = ["F", "M"]
    cell: dict[tuple[str, str], list[float]] = defaultdict(list)
    for d, s, t in zip(delta, sexes, txs):
        cell[(s, t)].append(float(d))

    x = np.arange(len(tx_order), dtype=float)
    width = 0.36
    for i, sex in enumerate(sex_order):
        meds = [float(np.median(cell[(sex, t)])) if cell[(sex, t)] else np.nan for t in tx_order]
        # bootstrap SE of median (simple)
        errs = []
        for t in tx_order:
            vals = np.asarray(cell[(sex, t)], dtype=np.float64)
            if vals.size < 2:
                errs.append(0.0)
                continue
            boots = [float(np.median(rng.choice(vals, size=vals.size, replace=True))) for _ in range(400)]
            errs.append(float(np.std(boots)))
        offset = (i - 0.5) * width
        color = "#8a4f3d" if sex == "F" else accent
        ax2.bar(
            x + offset,
            meds,
            width=width * 0.92,
            color=color,
            edgecolor="white",
            linewidth=0.5,
            yerr=errs,
            capsize=2.5,
            error_kw={"elinewidth": 0.8, "ecolor": ink},
            label=sex,
        )
        for xi, m, e in zip(x + offset, meds, errs):
            ax2.text(xi, m + e + 0.004, f"{m:.2f}", ha="center", va="bottom", fontsize=6.5, color=mute)

    ax2.axhline(0.0, color="#bbbbbb", lw=0.7, ls="--")
    ax2.set_xticks(x)
    ax2.set_xticklabels(tx_order)
    ax2.set_xlabel("treatment")
    ax2.set_ylabel("median Δ excess MI (bits)")
    ax2.set_title("C  Stratified by sex × tx", loc="left", fontweight="bold", color=ink)
    ax2.legend(frameon=False, loc="upper right", title="sex", fontsize=8, title_fontsize=8)
    for spine in ("top", "right"):
        ax2.spines[spine].set_visible(False)

    fig.suptitle(
        f"Object presence increases syllable↔distance mutual information ({phase_layer})",
        fontsize=11,
        fontweight="bold",
        color=ink,
        y=1.02,
    )

    # Footer caption outside axes
    caption = (
        f"Pilot: NOR kpMS paramscan_s1-1e8_s2-1e5_ss-50 · {phase_layer} · spot keypoint · "
        "5 shared dist_any bins · circular-shift null (n_perm=100) · "
        "no_obj loci = 2-means of animal×phase id+nvl centers. Exploratory pilot."
    )
    fig.text(0.0, -0.02, caption, fontsize=6.5, color=mute, ha="left", va="top", wrap=True)

    out_stem.parent.mkdir(parents=True, exist_ok=True)
    pdf = out_stem.with_suffix(".pdf")
    png = out_stem.with_suffix(".png")
    fig.savefig(pdf, bbox_inches="tight", dpi=dpi)
    fig.savefig(png, bbox_inches="tight", dpi=dpi)
    plt.close(fig)
    print(f"wrote {pdf}")
    print(f"wrote {png}")
    print(f"wilcoxon_stat={w_stat} p={w_p} n={n} median_delta={float(np.median(delta))}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--delta-csv",
        type=Path,
        default=Path(
            r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
            r"\_nor_object_mi\paramscan_s1-1e8_s2-1e5_ss-50\presence"
            r"\mi_delta_presence_per_animal.csv"
        ),
    )
    ap.add_argument(
        "--out-stem",
        type=Path,
        default=None,
        help="Path without extension; default: <delta-csv dir>/fig_presence_excess_mi",
    )
    ap.add_argument(
        "--phase-layer",
        type=str,
        default=None,
        help="Override phase label in title (default: read from CSV phase_layer column)",
    )
    args = ap.parse_args()
    out = args.out_stem or (args.delta_csv.parent / "fig_presence_excess_mi")
    rows = _load_delta(args.delta_csv)
    phase = args.phase_layer or (rows[0].get("phase_layer", "NOR_TX") if rows else "NOR_TX")
    make_figure(rows, out_stem=out, phase_layer=str(phase))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
