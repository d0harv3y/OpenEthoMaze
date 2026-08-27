"""Forest / tally figure for presence Δ across paramscan models.

Reads presence_grid_summary.csv written by run_presence_grid.py.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def _load(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _f(row: dict[str, str], key: str) -> float | None:
    v = row.get(key, "")
    if v is None or v == "":
        return None
    return float(v)


def make_figure(rows: list[dict[str, str]], *, out_stem: Path, dpi: int = 300) -> None:
    ok = [r for r in rows if r.get("status") == "ok"]
    phases = ["NOR_BL", "NOR_TX"]

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.labelsize": 10,
            "axes.titlesize": 10,
            "axes.linewidth": 0.8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )

    ink = "#1a1a1a"
    mute = "#6b6b6b"
    accent = "#2f5d8a"
    warn = "#8a4b2f"

    fig, axes = plt.subplots(1, 2, figsize=(8.5, 5.2), sharey=True, constrained_layout=True)

    for ax, phase in zip(axes, phases):
        sub = sorted(
            [r for r in ok if r.get("phase_layer") == phase],
            key=lambda r: _f(r, "median_delta") or -1e9,
        )
        if not sub:
            ax.set_title(f"{phase}: no ok rows")
            continue

        y = np.arange(len(sub))
        deltas = np.asarray([_f(r, "median_delta") or 0.0 for r in sub])
        ps = [_f(r, "wilcoxon_p") for r in sub]
        labels = [r["model"].replace("paramscan_", "") for r in sub]
        sig = np.asarray([p is not None and p < 0.05 for p in ps])

        ax.axvline(0.0, color="#bbbbbb", lw=0.8, zorder=0)
        ax.scatter(
            deltas[~sig],
            y[~sig],
            s=36,
            c=mute,
            edgecolors="none",
            zorder=2,
            label="Wilcoxon p ≥ 0.05",
        )
        ax.scatter(
            deltas[sig],
            y[sig],
            s=42,
            c=accent,
            edgecolors="none",
            zorder=3,
            label="Wilcoxon p < 0.05",
        )

        n_sig = int(sig.sum())
        n_pos = int(np.sum(deltas > 0))
        ax.set_title(
            f"{phase}: median Δ > 0 in {n_pos}/{len(sub)}; p < 0.05 in {n_sig}/{len(sub)}"
        )
        ax.set_xlabel("median Δ_presence (excess present − absent)")
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=7)
        ax.tick_params(axis="y", length=0)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color(mute)
        ax.spines["bottom"].set_color(mute)
        ax.legend(frameon=False, loc="lower right", fontsize=8)

        # mark reference model
        for i, r in enumerate(sub):
            if r["model"] == "paramscan_s1-1e8_s2-1e5_ss-50":
                ax.axhline(i, color=warn, lw=0.6, alpha=0.35, zorder=1)
                ax.annotate(
                    "ref",
                    xy=(deltas[i], i),
                    xytext=(4, 0),
                    textcoords="offset points",
                    fontsize=7,
                    color=warn,
                    va="center",
                )

    fig.suptitle(
        "Presence excess-MI across kpMS paramscan fits\n"
        "(frozen dist_any bins from ref pilot; n_perm=100 exploratory)",
        color=ink,
        fontsize=10,
    )
    out_stem.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(f"{out_stem}.pdf")
    fig.savefig(f"{out_stem}.png", dpi=dpi)
    plt.close(fig)
    print(f"wrote {out_stem}.pdf / .png")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--summary-csv",
        type=Path,
        default=Path(
            r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
            r"\_nor_object_mi\presence_grid_summary.csv"
        ),
    )
    ap.add_argument(
        "--out-stem",
        type=Path,
        default=None,
        help="Default: sibling fig_presence_grid_summary next to the CSV",
    )
    args = ap.parse_args()
    if not args.summary_csv.exists():
        raise SystemExit(f"missing {args.summary_csv}")
    out_stem = args.out_stem or (args.summary_csv.parent / "fig_presence_grid_summary")
    rows = _load(args.summary_csv)
    make_figure(rows, out_stem=out_stem)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
