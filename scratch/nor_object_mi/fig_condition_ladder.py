"""Figure: fam/nvl condition ladders; sex=shape, tx=color; within-sex tx tests."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from scipy import stats

TX_ORDER = ("noSD", "GHSD", "RBSD")
SEX_ORDER = ("F", "M")
# High-contrast, colorblind-friendlier triad (not gray-on-blue-brown)
TX_COLOR = {
    "noSD": "#1b9e77",  # teal
    "GHSD": "#d95f02",  # orange
    "RBSD": "#7570b3",  # purple
}
SEX_MARKER = {"F": "o", "M": "v"}  # inverted triangle for males
Y_LIM = (-0.1, 0.5)


def _load(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _p_text(p: float) -> str:
    if p < 1e-4:
        return "p < 10⁻⁴"
    if p < 0.001:
        return f"p = {p:.1e}"
    return f"p = {p:.3f}"


def _within_sex_tx_kruskal(
    rows: list[dict[str, str]],
    *,
    left_key: str,
    right_key: str,
) -> list[dict[str, object]]:
    """Kruskal–Wallis on paired step Δ = right − left, within each sex across tx."""
    out: list[dict[str, object]] = []
    for sex in SEX_ORDER:
        by_tx: dict[str, list[float]] = defaultdict(list)
        for r in rows:
            if str(r.get("sex", "")) != sex:
                continue
            tx = str(r.get("tx", ""))
            if tx not in TX_ORDER:
                continue
            a = float(r[left_key])
            b = float(r[right_key])
            if np.isfinite(a) and np.isfinite(b):
                by_tx[tx].append(b - a)
        samples = [by_tx[t] for t in TX_ORDER if len(by_tx[t]) >= 1]
        if len(samples) < 2 or any(len(s) < 2 for s in samples):
            out.append(
                {
                    "sex": sex,
                    "n_by_tx": {t: len(by_tx[t]) for t in TX_ORDER},
                    "stat": float("nan"),
                    "p": float("nan"),
                    "test": "kruskal",
                }
            )
            continue
        # require all three tx with n>=2 when possible
        samples = [by_tx[t] for t in TX_ORDER]
        if any(len(s) < 2 for s in samples):
            out.append(
                {
                    "sex": sex,
                    "n_by_tx": {t: len(by_tx[t]) for t in TX_ORDER},
                    "stat": float("nan"),
                    "p": float("nan"),
                    "test": "kruskal",
                }
            )
            continue
        stat, p = stats.kruskal(*samples)
        out.append(
            {
                "sex": sex,
                "n_by_tx": {t: len(by_tx[t]) for t in TX_ORDER},
                "stat": float(stat),
                "p": float(p),
                "test": "kruskal",
                "median_delta_by_tx": {t: float(np.median(by_tx[t])) for t in TX_ORDER},
            }
        )
    return out


def _ladder_panel(
    ax,
    rows: list[dict[str, str]],
    *,
    keys: tuple[str, str, str],
    labels: tuple[str, str, str],
    title: str,
    ink: str,
) -> list[dict[str, object]]:
    n = len(rows)
    rng = np.random.default_rng(0)
    # stable jitter keyed by animal index
    jitter = rng.normal(0.0, 0.045, size=(n, 3))
    ys = [
        np.asarray([float(r[keys[i]]) for r in rows], dtype=np.float64) for i in range(3)
    ]
    xs = [i + jitter[:, i] for i in range(3)]

    # pairing lines (muted)
    for i in range(n):
        ax.plot(
            [xs[0][i], xs[1][i], xs[2][i]],
            [ys[0][i], ys[1][i], ys[2][i]],
            color="#d0d0d0",
            lw=0.35,
            zorder=1,
        )

    # points: color=tx, shape=sex
    for i, r in enumerate(rows):
        sex = str(r.get("sex", ""))
        tx = str(r.get("tx", ""))
        marker = SEX_MARKER.get(sex, "o")
        color = TX_COLOR.get(tx, "#888888")
        for j in range(3):
            ax.scatter(
                xs[j][i],
                ys[j][i],
                s=18 if sex == "F" else 16,
                c=color,
                marker=marker,
                alpha=0.85,
                edgecolors="white",
                linewidths=0.25,
                zorder=2,
            )

    for x, y in ((0.0, ys[0]), (1.0, ys[1]), (2.0, ys[2])):
        ax.plot([x - 0.2, x + 0.2], [np.median(y)] * 2, color=ink, lw=2.0, zorder=3)

    ax.axhline(0.0, color="#bbbbbb", lw=0.7, ls="--", zorder=0)
    ax.set_ylim(*Y_LIM)
    ax.set_xlim(-0.55, 2.55)
    ax.set_xticks([0, 1, 2])
    ax.set_xticklabels(list(labels))
    ax.set_title(title, loc="left", fontweight="bold", color=ink)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    d01 = ys[1] - ys[0]
    d12 = ys[2] - ys[1]
    d02 = ys[2] - ys[0]
    _, p01 = stats.wilcoxon(d01, alternative="two-sided", zero_method="wilcox")
    _, p12 = stats.wilcoxon(d12, alternative="two-sided", zero_method="wilcox")
    _, p02 = stats.wilcoxon(d02, alternative="two-sided", zero_method="wilcox")

    tx_no_id = _within_sex_tx_kruskal(rows, left_key=keys[0], right_key=keys[1])
    tx_id_obj = _within_sex_tx_kruskal(rows, left_key=keys[1], right_key=keys[2])

    def _sex_line(label: str, tests: list[dict[str, object]]) -> str:
        bits = []
        for t in tests:
            sex = str(t["sex"])
            p = t["p"]
            if p != p:  # NaN
                bits.append(f"{sex}: n/a")
            else:
                bits.append(f"{sex}: {_p_text(float(p))}")  # type: ignore[arg-type]
        return f"{label} " + "  ".join(bits)
    side = 'fam' if 'fam' in title.lower() else 'nvl'
    ax.text(
        0.02,
        0.98,
        f"n={n}  pooled steps\n"
        f"no→id Δ̃={np.median(d01):+.3f} {_p_text(float(p01))}\n"
        f"id→{side} Δ̃={np.median(d12):+.3f} {_p_text(float(p12))}\n"
        f"no→{side} Δ̃={np.median(d02):+.3f} {_p_text(float(p02))}\n"
        f"within-sex tx Kruskal\n"
        f"{_sex_line('no→id', tx_no_id)}\n"
        f"{_sex_line(f'id→{side}', tx_id_obj)}",
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=6.8,
        color=ink,
        bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#dddddd", lw=0.6),
    )

    # return rows for CSV export
    export: list[dict[str, object]] = []
    for step_name, tests in (("no_obj->identical", tx_no_id), ("identical->role_nvl", tx_id_obj)):
        for t in tests:
            export.append(
                {
                    "panel_title": title,
                    "step": step_name,
                    "sex": t["sex"],
                    "test": t["test"],
                    "stat": t["stat"],
                    "p": t["p"],
                    "n_noSD": t["n_by_tx"].get("noSD", 0),  # type: ignore[union-attr]
                    "n_GHSD": t["n_by_tx"].get("GHSD", 0),  # type: ignore[union-attr]
                    "n_RBSD": t["n_by_tx"].get("RBSD", 0),  # type: ignore[union-attr]
                }
            )
    return export


def make_figure(rows: list[dict[str, str]], *, out_stem: Path, phase_layer: str, dpi: int = 300) -> None:
    ink, mute = "#1a1a1a", "#6b6b6b"
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
    fig = plt.figure(figsize=(10.6, 5.0), layout="constrained")
    gs = fig.add_gridspec(2, 3, height_ratios=[1.0, 0.18], width_ratios=[1.0, 1.0, 0.32])
    ax0 = fig.add_subplot(gs[0, 0])
    ax1 = fig.add_subplot(gs[0, 1], sharey=ax0)
    ax_leg = fig.add_subplot(gs[0, 2])
    ax_leg.axis("off")
    ax_foot = fig.add_subplot(gs[1, :2])
    ax_foot.axis("off")

    exp0 = _ladder_panel(
        ax0,
        rows,
        keys=("excess_no_obj_fam_side", "excess_identical_fam_side", "excess_fam_obj"),
        labels=("no object", "identical", "fam object"),
        title="A  Fam-side ladder",
        ink=ink,
    )
    ax0.set_ylabel("excess MI (bits)")
    exp1 = _ladder_panel(
        ax1,
        rows,
        keys=("excess_no_obj_nvl_side", "excess_identical_nvl_side", "excess_nvl_obj"),
        labels=("no object", "identical", "nvl object"),
        title="B  Nvl-side ladder",
        ink=ink,
    )

    # Counts for legends (animals in this figure)
    n_sex = {s: sum(1 for r in rows if str(r.get("sex", "")) == s) for s in SEX_ORDER}
    n_tx = {t: sum(1 for r in rows if str(r.get("tx", "")) == t) for t in TX_ORDER}
    n_sex_tx = {
        (s, t): sum(1 for r in rows if str(r.get("sex", "")) == s and str(r.get("tx", "")) == t)
        for s in SEX_ORDER
        for t in TX_ORDER
    }

    sex_handles = [
        Line2D(
            [0],
            [0],
            marker=SEX_MARKER[s],
            color="none",
            markerfacecolor="#555555",
            markeredgecolor="white",
            markersize=7,
            label=f"{s} (n={n_sex[s]})",
        )
        for s in SEX_ORDER
    ]
    tx_handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor=TX_COLOR[t],
            markeredgecolor="white",
            markersize=7,
            label=f"{t} (n={n_tx[t]})",
        )
        for t in TX_ORDER
    ]
    # Legends live in a dedicated column — never overlap scatter
    leg_tx = ax_leg.legend(
        handles=tx_handles,
        title="tx",
        frameon=False,
        loc="upper left",
        fontsize=7,
        title_fontsize=7,
        borderaxespad=0.0,
    )
    ax_leg.add_artist(leg_tx)
    ax_leg.legend(
        handles=sex_handles,
        title="sex",
        frameon=False,
        loc="center left",
        fontsize=7,
        title_fontsize=7,
        borderaxespad=0.0,
    )

    cell_f = "  ".join(f"{t}={n_sex_tx[('F', t)]}" for t in TX_ORDER)
    cell_m = "  ".join(f"{t}={n_sex_tx[('M', t)]}" for t in TX_ORDER)
    fig.suptitle(
        f"Condition ladder by hist-tagged side — {phase_layer}\n"
        "marker shape = sex · marker color = treatment",
        fontsize=11,
        fontweight="bold",
        color=ink,
    )
    footnote = (
        "Hist loci = fixed animal×phase 2-means. "
        f"Side tags from novel session (nvl@hist A={n_a}, B={n_b}).\n"
        f"Gray lines = animals (N={len(rows)}). "
        "Within-sex tx tests = Kruskal–Wallis on step Δ.\n"
        "n_perm=100 exploratory.\n"
        f"sex×tx Ns — F: {cell_f}\n"
        f"sex×tx Ns — M: {cell_m}"
    )
    ax_foot.text(
        0.0,
        1.0,
        footnote,
        transform=ax_foot.transAxes,
        fontsize=6.5,
        color=mute,
        ha="left",
        va="top",
        linespacing=1.4,
        wrap=True,
    )
    out_stem.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_stem.with_suffix(".pdf"), bbox_inches="tight", dpi=dpi)
    fig.savefig(out_stem.with_suffix(".png"), bbox_inches="tight", dpi=dpi)
    plt.close(fig)

    stats_path = out_stem.parent / f"{out_stem.name}_within_sex_tx.csv"
    fields = ["panel_title", "step", "sex", "test", "stat", "p", "n_noSD", "n_GHSD", "n_RBSD"]
    with stats_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in exp0 + exp1:
            w.writerow(row)
    print(f"wrote {out_stem.with_suffix('.pdf')}")
    print(f"wrote {out_stem.with_suffix('.png')}")
    print(f"wrote {stats_path}")


def main() -> int:
    root = Path(
        r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
        r"\_nor_object_mi\paramscan_s1-1e8_s2-1e5_ss-50"
    )
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ladder-csv", type=Path, default=root / "condition_ladder" / "mi_ladder_per_animal.csv")
    ap.add_argument("--out-stem", type=Path, default=None)
    args = ap.parse_args()
    rows = _load(args.ladder_csv)
    phase = str(rows[0]["phase_layer"]) if rows else "NOR_TX"
    out = args.out_stem or (args.ladder_csv.parent / "fig_condition_ladder")
    make_figure(rows, out_stem=out, phase_layer=phase)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
