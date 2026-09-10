"""Figures: INFO sex vs cluster / composition (within tx, nvl_obj).

    uv run python scratch/nor_object_mi/fig_simpler_first_info_sex_cluster.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi._pub_style import (  # noqa: E402
    INK,
    MUTE,
    SESSION_SHORT,
    SESSIONS,
    SEX_ORDER,
    CONDITION_ORDER,
    apply_style,
    fig_footnote,
    save_pdf_png,
    text_on_cmap,
)
from nor_object_mi.info_sex_cluster import default_out_dir  # noqa: E402

ROOT = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017")


def _neglog10_p(p: float) -> float:
    if not np.isfinite(p) or p <= 0:
        return float("nan")
    return float(min(-np.log10(p), 6.0))


def fig_mi_compare_pooled(run_dir: Path, out: Path) -> None:
    """Bar compare I(sex; dominant) vs I(sex; composition) by tx."""
    dom = pd.read_csv(run_dir / "info_sex_cluster_tests_pooled_phases.csv")
    comp = pd.read_csv(run_dir / "info_sex_composition_tests_pooled_phases.csv")
    apply_style()
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    x = np.arange(len(CONDITION_ORDER))
    w = 0.35
    dom_mi = [float(dom[dom.condition == tx].iloc[0]["mi_mm_bits"]) for condition in CONDITION_ORDER]
    comp_mi = [float(comp[comp.condition == tx].iloc[0]["mi_mm_bits"]) for condition in CONDITION_ORDER]
    dom_p = [float(dom[dom.condition == tx].iloc[0]["perm_p"]) for condition in CONDITION_ORDER]
    comp_p = [float(comp[comp.condition == tx].iloc[0]["perm_p"]) for condition in CONDITION_ORDER]
    ax.bar(x - w / 2, dom_mi, width=w, label="dominant cluster", color="#4C72B0")
    ax.bar(x + w / 2, comp_mi, width=w, label="composition fingerprint", color="#DD8452")
    ax.set_xticks(x)
    ax.set_xticklabels(list(CONDITION_ORDER))
    ax.set_xlabel("Treatment (condition)")
    ax.set_ylabel("I_mm (bits)")
    ax.set_title("I(sex; cluster) — phases pooled", fontweight="bold", color=INK, loc="left")
    for i, tx in enumerate(CONDITION_ORDER):
        ax.text(i - w / 2, dom_mi[i] + 0.01, f"p={dom_p[i]:.3g}", ha="center", fontsize=7, color=MUTE)
        ax.text(i + w / 2, comp_mi[i] + 0.01, f"p={comp_p[i]:.3g}", ha="center", fontsize=7, color=MUTE)
    ax.legend(frameon=False)
    fig_footnote(
        fig,
        "Between-animal INFO within tx; nvl_obj bouts; 21-model median composition.",
        y=-0.02,
        color=MUTE,
    )
    save_pdf_png(fig, out / "fig_info_sex_cluster_mi_compare_pooled")
    fig.savefig(out / "fig_info_sex_cluster_mi_compare_pooled.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def fig_composition_mi_heatmap(tests: pd.DataFrame, out: Path, *, title: str, stem: str) -> None:
    apply_style()
    fig, ax = plt.subplots(figsize=(6.4, 4.8))
    mat = np.full((len(SESSIONS), len(CONDITION_ORDER)), np.nan)
    nlp = np.full_like(mat, np.nan)
    for i, ph in enumerate(SESSIONS):
        for j, tx in enumerate(CONDITION_ORDER):
            row = tests[(tests.session == ph) & (tests.condition == condition)]
            if len(row) == 1:
                mat[i, j] = float(row.iloc[0]["mi_mm_bits"])
                nlp[i, j] = _neglog10_p(float(row.iloc[0]["perm_p"]))
    vmax = max(0.08, np.nanmax(mat) if np.isfinite(mat).any() else 0.08)
    im = ax.imshow(mat, aspect="auto", cmap="viridis", vmin=0.0, vmax=vmax, origin="upper")
    ax.set_xticks(range(len(CONDITION_ORDER)))
    ax.set_xticklabels(list(CONDITION_ORDER))
    ax.set_yticks(range(len(SESSIONS)))
    ax.set_yticklabels([SESSION_SHORT[p] for p in SESSIONS])
    ax.set_xlabel("Treatment (condition)")
    ax.set_ylabel("Phase")
    ax.set_title(title, fontweight="bold", color=INK, loc="left")
    for i in range(len(SESSIONS)):
        for j in range(len(CONDITION_ORDER)):
            v = mat[i, j]
            p = nlp[i, j]
            if not np.isfinite(v):
                continue
            ax.text(
                j,
                i,
                f"{v:.3f}\n-log10p={p:.1f}" if np.isfinite(p) else f"{v:.3f}",
                ha="center",
                va="center",
                fontsize=7,
                linespacing=1.1,
                color=text_on_cmap(v, cmap="viridis", vmin=0.0, vmax=vmax),
            )
    cbar = fig.colorbar(im, ax=ax, shrink=0.9)
    cbar.set_label("I_mm (bits)")
    fig_footnote(fig, "Composition = top-4 cluster fractions, 5 bins; shuffle-sex null.", y=-0.02, color=MUTE)
    save_pdf_png(fig, out / stem)
    fig.savefig(out.with_name(stem + ".png"), dpi=180, bbox_inches="tight")
    plt.close(fig)


def _top_frac_columns(comp: pd.DataFrame, *, top_n: int = 5) -> list[str]:
    frac_cols = [c for c in comp.columns if c.startswith("frac_c")]
    if not frac_cols:
        return []
    means = comp[frac_cols].mean(numeric_only=True).sort_values(ascending=False)
    return list(means.head(top_n).index)


def fig_composition_stack_by_sex(comp: pd.DataFrame, out: Path) -> None:
    """Mean cluster composition by sex × tx (pooled phases)."""
    sub = comp[comp.session == "ALL_SESSIONS"].copy()
    frac_cols = _top_frac_columns(sub, top_n=5)
    if not frac_cols:
        return
    labels = [c.replace("frac_c", "c") for c in frac_cols]
    apply_style()
    fig, axes = plt.subplots(1, len(CONDITION_ORDER), figsize=(9.0, 4.0), sharey=True)
    colors = plt.cm.tab10(np.linspace(0, 1, len(frac_cols)))
    for ax, tx in zip(axes, CONDITION_ORDER, strict=True):
        cell = sub[sub.condition == tx]
        bottoms = np.zeros(len(SEX_ORDER))
        for col, lab, color in zip(frac_cols, labels, colors, strict=True):
            vals = []
            for sex in SEX_ORDER:
                g = cell[cell.sex == sex]
                vals.append(float(g[col].mean()) if len(g) else 0.0)
            ax.bar(SEX_ORDER, vals, bottom=bottoms, label=lab, color=color, width=0.55)
            bottoms += np.asarray(vals)
        ax.set_title(condition, fontweight="bold", color=INK)
        ax.set_xlabel("Sex")
    axes[0].set_ylabel("Mean frame fraction")
    fig.suptitle("Cluster composition by sex × tx (phases pooled)", fontweight="bold", color=INK, y=1.02)
    fig.legend(loc="upper center", ncol=len(labels), bbox_to_anchor=(0.5, 1.08), frameon=False)
    fig_footnote(fig, "Top-5 clusters by cohort mean fraction; 21-model median composition.", y=-0.01, color=MUTE)
    save_pdf_png(fig, out / "fig_info_sex_cluster_composition_stack")
    fig.savefig(out / "fig_info_sex_cluster_composition_stack.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, default=None)
    args = ap.parse_args(argv)

    run = args.run_dir or default_out_dir(ROOT)
    fig_dir = run / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    fig_mi_compare_pooled(run, fig_dir)

    by_phase = pd.read_csv(run / "info_sex_composition_tests_by_phase.csv")
    fig_composition_mi_heatmap(
        by_phase,
        fig_dir,
        title="I(sex; cluster composition) — by phase × tx",
        stem="fig_info_sex_composition_mi_by_phase",
    )

    dom_by = pd.read_csv(run / "info_sex_cluster_tests_by_phase.csv")
    fig_composition_mi_heatmap(
        dom_by,
        fig_dir,
        title="I(sex; dominant cluster) — by phase × tx",
        stem="fig_info_sex_dominant_mi_by_phase",
    )

    comp = pd.read_csv(run / "cluster_composition_consensus.csv")
    fig_composition_stack_by_sex(comp, fig_dir)

    print(f"wrote figures under {fig_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
