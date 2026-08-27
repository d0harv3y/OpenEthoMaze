"""Composite figure: presence boost is real in BL & TX; tx does not emerge at TX.

Panels
  A  NOR_BL paired excess (absent vs present)
  B  NOR_TX paired excess (absent vs present)
  C  Per-animal presence Δ by phase (BL vs TX medians + paired)
  D  Change Δ_TX − Δ_BL by sex × treatment (the 'emerges at TX' test)
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
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


def _paired_panel(ax, rows: list[dict[str, str]], *, title: str, ink: str, mute: str, accent: str) -> None:
    present = np.asarray([float(r["excess_present"]) for r in rows])
    absent = np.asarray([float(r["excess_absent"]) for r in rows])
    delta = present - absent
    n = len(delta)
    rng = np.random.default_rng(0)
    x0 = rng.normal(0, 0.03, n)
    x1 = 1.0 + rng.normal(0, 0.03, n)
    for a, b, xa, xb in zip(absent, present, x0, x1):
        ax.plot([xa, xb], [a, b], color="#c8c8c8", lw=0.4, zorder=1)
    ax.scatter(x0, absent, s=8, c=mute, alpha=0.75, edgecolors="none", zorder=2)
    ax.scatter(x1, present, s=8, c=accent, alpha=0.85, edgecolors="none", zorder=2)
    ax.plot([-0.18, 0.18], [np.median(absent)] * 2, color=ink, lw=2.0, zorder=3)
    ax.plot([0.82, 1.18], [np.median(present)] * 2, color=ink, lw=2.0, zorder=3)
    ax.axhline(0.0, color="#bbbbbb", lw=0.7, ls="--", zorder=0)
    ax.set_xlim(-0.45, 1.45)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["no object", "identical\nobjects"])
    ax.set_ylabel("excess MI (bits)")
    ax.set_title(title, loc="left", fontweight="bold", color=ink)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    _, wp = stats.wilcoxon(delta, alternative="two-sided", zero_method="wilcox")
    ax.text(
        0.02,
        0.98,
        f"n={n}\nmedian Δ={np.median(delta):.3f}\nWilcoxon {_p_text(float(wp))}",
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=7.5,
        color=ink,
        bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#dddddd", lw=0.6),
    )


def make_figure(
    rows_bl: list[dict[str, str]],
    rows_tx: list[dict[str, str]],
    *,
    out_stem: Path,
    dpi: int = 300,
) -> None:
    bl = {r["animal_id"]: r for r in rows_bl}
    tx = {r["animal_id"]: r for r in rows_tx}
    shared = sorted(set(bl) & set(tx))

    d_bl = np.asarray([float(bl[a]["delta_excess_present_minus_absent"]) for a in shared])
    d_tx = np.asarray([float(tx[a]["delta_excess_present_minus_absent"]) for a in shared])
    d_change = d_tx - d_bl
    sex = [str(tx[a]["sex"]) for a in shared]
    treat = [str(tx[a]["tx"]) for a in shared]

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
    ink, mute, accent = "#1a1a1a", "#6b6b6b", "#2f5d8a"
    terracotta = "#8a4f3d"

    fig = plt.figure(figsize=(7.4, 6.2), constrained_layout=True)
    gs = fig.add_gridspec(2, 2, height_ratios=[1.05, 1.0])
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1], sharey=ax_a)
    ax_c = fig.add_subplot(gs[1, 0])
    ax_d = fig.add_subplot(gs[1, 1])

    _paired_panel(
        ax_a,
        [bl[a] for a in shared],
        title="A  Presence boost — NOR_BL",
        ink=ink,
        mute=mute,
        accent=accent,
    )
    _paired_panel(
        ax_b,
        [tx[a] for a in shared],
        title="B  Presence boost — NOR_TX",
        ink=ink,
        mute=mute,
        accent=accent,
    )
    ax_b.set_ylabel("")

    # C: BL vs TX presence Δ (paired)
    rng = np.random.default_rng(1)
    n = len(shared)
    x0 = rng.normal(0, 0.03, n)
    x1 = 1.0 + rng.normal(0, 0.03, n)
    for a, b, xa, xb in zip(d_bl, d_tx, x0, x1):
        ax_c.plot([xa, xb], [a, b], color="#c8c8c8", lw=0.4, zorder=1)
    ax_c.scatter(x0, d_bl, s=8, c="#5a7a5a", alpha=0.8, edgecolors="none", zorder=2)
    ax_c.scatter(x1, d_tx, s=8, c=accent, alpha=0.85, edgecolors="none", zorder=2)
    ax_c.plot([-0.18, 0.18], [np.median(d_bl)] * 2, color=ink, lw=2.0, zorder=3)
    ax_c.plot([0.82, 1.18], [np.median(d_tx)] * 2, color=ink, lw=2.0, zorder=3)
    ax_c.axhline(0.0, color="#bbbbbb", lw=0.7, ls="--", zorder=0)
    ax_c.set_xlim(-0.45, 1.45)
    ax_c.set_xticks([0, 1])
    ax_c.set_xticklabels(["NOR_BL\npresence Δ", "NOR_TX\npresence Δ"])
    ax_c.set_ylabel("presence Δ excess MI (bits)\npresent − absent")
    ax_c.set_title("C  Same animals across phases", loc="left", fontweight="bold", color=ink)
    for spine in ("top", "right"):
        ax_c.spines[spine].set_visible(False)
    _, p_change = stats.wilcoxon(d_change, alternative="two-sided", zero_method="wilcox")
    ax_c.text(
        0.98,
        0.98,
        f"Δ_TX − Δ_BL\nmedian = {np.median(d_change):+.3f}\nWilcoxon {_p_text(float(p_change))}\n(no systematic rise at TX)",
        transform=ax_c.transAxes,
        va="top",
        ha="right",
        fontsize=7.5,
        color=ink,
        bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#dddddd", lw=0.6),
    )

    # D: d_change by sex × tx
    tx_order = ["noSD", "GHSD", "RBSD"]
    sex_order = ["F", "M"]
    cell: dict[tuple[str, str], list[float]] = defaultdict(list)
    for dc, s, t in zip(d_change, sex, treat):
        cell[(s, t)].append(float(dc))

    x = np.arange(len(tx_order), dtype=float)
    width = 0.36
    for i, s in enumerate(sex_order):
        meds = [float(np.median(cell[(s, t)])) for t in tx_order]
        errs = []
        for t in tx_order:
            vals = np.asarray(cell[(s, t)], dtype=np.float64)
            boots = [
                float(np.median(rng.choice(vals, size=vals.size, replace=True))) for _ in range(400)
            ]
            errs.append(float(np.std(boots)))
        offset = (i - 0.5) * width
        color = terracotta if s == "F" else accent
        ax_d.bar(
            x + offset,
            meds,
            width=width * 0.92,
            color=color,
            edgecolor="white",
            linewidth=0.5,
            yerr=errs,
            capsize=2.2,
            error_kw={"elinewidth": 0.8, "ecolor": ink},
            label=s,
        )

    ax_d.axhline(0.0, color="#bbbbbb", lw=0.7, ls="--")
    ax_d.set_xticks(x)
    ax_d.set_xticklabels(tx_order)
    ax_d.set_xlabel("treatment")
    ax_d.set_ylabel("median (Δ_TX − Δ_BL) (bits)")
    ax_d.set_title("D  Tx effect does not emerge at TX", loc="left", fontweight="bold", color=ink)
    ax_d.legend(frameon=False, loc="upper right", title="sex", fontsize=8, title_fontsize=8)
    for spine in ("top", "right"):
        ax_d.spines[spine].set_visible(False)

    # Kruskal p annotations for d_change within sex
    note_lines = ["sex-stratified tx Kruskal"]
    for s in sex_order:
        by_tx = [cell[(s, t)] for t in tx_order]
        _, pk = stats.kruskal(*by_tx)
        note_lines.append(f"{s}: {_p_text(float(pk))}")
    ax_d.text(
        0.02,
        0.98,
        "\n".join(note_lines),
        transform=ax_d.transAxes,
        va="top",
        ha="left",
        fontsize=7.5,
        color=ink,
        bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#dddddd", lw=0.6),
    )

    fig.suptitle(
        "Object presence raises syllable↔distance MI in BL and TX;\ntreatment does not selectively amplify that boost at TX",
        fontsize=11,
        fontweight="bold",
        color=ink,
        y=1.03,
    )
    fig.text(
        0.0,
        -0.01,
        "Pilot: NOR kpMS paramscan_s1-1e8_s2-1e5_ss-50 · spot · 5 dist_any bins · circular null "
        "(n_perm=100) · presence Δ = excess_I(identical) − excess_I(no_obj pseudo-loci). "
        "Phases kept separate (not averaged). Exploratory pilot.",
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
    print(
        f"n={n} median_d_bl={float(np.median(d_bl)):.4f} median_d_tx={float(np.median(d_tx)):.4f} "
        f"median_d_change={float(np.median(d_change)):.4f} wilcoxon_change_p={float(p_change):.4g}"
    )


def main() -> int:
    root = Path(
        r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
        r"\_nor_object_mi\paramscan_s1-1e8_s2-1e5_ss-50"
    )
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bl-csv", type=Path, default=root / "presence_NOR_BL" / "mi_delta_presence_per_animal.csv")
    ap.add_argument("--tx-csv", type=Path, default=root / "presence" / "mi_delta_presence_per_animal.csv")
    ap.add_argument(
        "--out-stem",
        type=Path,
        default=root / "presence_phase_contrast" / "fig_presence_bl_tx_summary",
    )
    args = ap.parse_args()
    make_figure(_load(args.bl_csv), _load(args.tx_csv), out_stem=args.out_stem)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
