"""Comparable 2x2 NOR_TX DR violin panels for pooled cluster / consensus.

Matches the per-animal exploratory layout
(``fig_per_animal_consensus_dr_violins``) so boards can be eyeballed side by
side. Reads long tables from ``simpler_first_prox_quad_comp_figs_min0``.

Regen::

    uv run python scratch/nor_object_mi/fig_prox_quad_comparable_dr_panels.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi._pub_style import (  # noqa: E402
    CONDITION_COLOR,
    CONDITION_ORDER,
    FIGSIZE_DOUBLE,
    INK,
    MUTE,
    SEX_ORDER,
    apply_style,
    save_pdf_svg,
)

DEFAULT_ROOT = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_prox_quad_comp_figs_min0"
)

# (metric role name in long, display title, kruskal csv kind tag)
PANELS: tuple[tuple[str, str, str, str], ...] = (
    ("dr_shannon_quad", "Quad Shannon DR", "quad", "shannon"),
    ("dr_shannon_prox", "Prox Shannon DR", "prox", "shannon"),
    ("dr_richness_quad", "Quad Richness DR", "quad", "richness"),
    ("dr_richness_prox", "Prox Richness DR", "prox", "richness"),
)


def _load_dr_tx(root: Path, tag: str, roi: str, kind: str) -> pd.DataFrame:
    path = root / f"long_{tag}_{roi}_{kind}.csv"
    df = pd.read_csv(path)
    out = df[(df.role == "dr") & (df.session == "NOR_TX")].copy()
    out["metric"] = f"dr_{kind}_{roi}"
    return out


def _f_q_hit(root: Path, tag: str, roi: str, kind: str) -> tuple[float, bool]:
    kr = pd.read_csv(root / f"kruskal_{tag}_{roi}_{kind}.csv")
    row = kr[
        (kr.metric.str.startswith("dr_"))
        & (kr.session == "NOR_TX")
        & (kr.sex == "F")
    ]
    if row.empty:
        # some boards use role=='dr' without metric prefix in kruskal
        row = kr[(kr.role == "dr") & (kr.session == "NOR_TX") & (kr.sex == "F")]
    if row.empty:
        return float("nan"), False
    r = row.iloc[0]
    q = float(r.q_bh) if "q_bh" in r.index else float("nan")
    hit = bool(r.hit_fdr05) if "hit_fdr05" in r.index else False
    return q, hit


def fig_comparable_dr_violins(
    root: Path,
    *,
    tag: str,
    alphabet_lab: str,
    stem: str,
) -> Path:
    apply_style()
    rng = np.random.default_rng(0)
    fig, axes = plt.subplots(2, 2, figsize=(10, 8), constrained_layout=True)

    for ax, (metric, title, roi, kind) in zip(axes.ravel(), PANELS):
        long = _load_dr_tx(root, tag, roi, kind)
        positions: list[float] = []
        data: list[np.ndarray] = []
        colors: list[str] = []
        labels: list[str] = []
        pos = 0.0
        for c in CONDITION_ORDER:
            for s in SEX_ORDER:
                vals = long[(long.condition == c) & (long.sex == s)]["value"].dropna().to_numpy()
                data.append(vals)
                positions.append(pos)
                colors.append(CONDITION_COLOR[c])
                labels.append(f"{c}\n{s}")
                if len(vals):
                    ax.scatter(
                        np.full(len(vals), pos) + rng.uniform(-0.12, 0.12, len(vals)),
                        vals,
                        s=12,
                        c=[CONDITION_COLOR[c]],
                        edgecolors=INK,
                        linewidths=0.3,
                        zorder=3,
                        alpha=0.85,
                    )
                pos += 1.0
            pos += 0.4

        parts = ax.violinplot(
            data, positions=positions, widths=0.7, showextrema=False, showmeans=False
        )
        for pc, col in zip(parts["bodies"], colors):
            pc.set_facecolor(col)
            pc.set_alpha(0.35)
            pc.set_edgecolor(INK)

        q, hit = _f_q_hit(root, tag, roi, kind)
        star = " *" if hit else ""
        ax.axhline(0, color=MUTE, lw=0.8, ls="--")
        ax.set_xticks(positions)
        ax.set_xticklabels(labels, fontsize=7)
        ax.set_ylabel("DR")
        ax.set_title(f"{title}{star}\nF q={q:.3f}")

    fig.suptitle(
        f"Pooled {alphabet_lab} DR @ NOR_TX nvl_obj  (comparable 2×2 to per-animal)"
    )
    out = root / "figures" / stem
    save_pdf_svg(fig, out)
    png = Path(str(out) + ".png")
    fig.savefig(png, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {stem}.{{pdf,svg,png}}", flush=True)
    return png


def fig_direction_compare(root: Path, pa_root: Path) -> Path:
    """Bar twin: per-animal ×9 vs pooled cluster vs pooled consensus @ F NOR_TX."""
    apply_style()
    pa = pd.read_csv(pa_root / "consensus_per_animal.csv")
    tests = pd.read_csv(pa_root / "consensus_tests_long.csv")

    def pooled_medians(kind: str, src: str) -> tuple[list[float], bool]:
        df = pd.read_csv(root / f"kruskal_{src}_{kind}.csv")
        row = df[
            (df.metric.str.startswith("dr_"))
            & (df.session == "NOR_TX")
            & (df.sex == "F")
        ]
        if row.empty:
            row = df[(df.role == "dr") & (df.session == "NOR_TX") & (df.sex == "F")]
        r = row.iloc[0]
        meds = [float(getattr(r, f"median_{c}")) for c in CONDITION_ORDER]
        hit = bool(r.hit_fdr05)
        return meds, hit

    metrics = [
        ("dr_shannon_quad", "quad_shannon", "Quad Shannon DR"),
        ("dr_shannon_prox", "prox_shannon", "Prox Shannon DR"),
    ]
    boards = [
        ("per-animal median ×9", None),
        ("pooled cluster_id", "cluster"),
        ("pooled raw median ×21", "consensus"),
    ]
    fig, axes = plt.subplots(1, 2, figsize=FIGSIZE_DOUBLE, constrained_layout=True)
    x = np.arange(3)
    w = 0.25
    board_colors = ["#4C78A8", "#F58518", "#54A24B"]

    for ax, (m, kind, title) in zip(axes, metrics):
        for j, (lab, src) in enumerate(boards):
            if src is None:
                meds = [
                    float(pa[(pa.sex == "F") & (pa.condition == c)][m].median())
                    for c in CONDITION_ORDER
                ]
                hit = bool(
                    tests[(tests.sex == "F") & (tests.metric == m)].hit_fdr05.iloc[0]
                )
            else:
                meds, hit = pooled_medians(kind, src)
            ax.bar(
                x + (j - 1) * w,
                meds,
                width=w,
                label=lab + (" *" if hit else ""),
                color=board_colors[j],
                edgecolor=INK,
                lw=0.6,
            )
        ax.axhline(0, color=MUTE, lw=0.8, ls="--")
        ax.set_xticks(x)
        ax.set_xticklabels(CONDITION_ORDER)
        ax.set_ylabel("median DR")
        ax.set_title(f"F {title}")
        ax.legend(fontsize=7, frameon=False)

    out = root / "figures" / "fig_direction_compare_F_dr_shannon"
    save_pdf_svg(fig, out)
    png = Path(str(out) + ".png")
    fig.savefig(png, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote fig_direction_compare_F_dr_shannon.{pdf,svg,png}", flush=True)
    return png


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    ap.add_argument(
        "--per-animal-root",
        type=Path,
        default=Path(
            r"D:\sack\datas\impress\nor_per_animal_paramscan"
            r"\_nor_object_mi\simpler_first_prox_quad_per_animal"
        ),
    )
    args = ap.parse_args(argv)
    root = args.root
    (root / "figures").mkdir(parents=True, exist_ok=True)

    # Peek kruskal schema once
    sample = pd.read_csv(root / "kruskal_cluster_quad_shannon.csv")
    print("kruskal cols:", list(sample.columns), flush=True)

    p1 = fig_comparable_dr_violins(
        root,
        tag="cluster",
        alphabet_lab="cluster_id",
        stem="fig_comparable_dr_violins_cluster_NOR_TX",
    )
    p2 = fig_comparable_dr_violins(
        root,
        tag="consensus",
        alphabet_lab="raw×21 median",
        stem="fig_comparable_dr_violins_consensus_NOR_TX",
    )
    p3 = fig_direction_compare(root, args.per_animal_root)

    preview = root / "comparable_preview_paths.txt"
    preview.write_text(
        "\n".join(str(p) for p in (p1, p2, p3)) + "\n", encoding="utf-8"
    )
    print(f"done -> {preview}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
