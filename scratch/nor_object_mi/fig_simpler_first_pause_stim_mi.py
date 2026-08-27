"""Figures: pause-syllable bout MI vs binned object proximity + composition bridge.

Regen:

    uv run python scratch/nor_object_mi/fig_simpler_first_pause_stim_mi.py
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
    PHASE_SHORT,
    PHASES,
    SEX_ORDER,
    TX_COLOR,
    TX_ORDER,
    apply_style,
    fig_footnote,
    panel_stats_box,
    save_pdf_png,
    tx_sex_legend_handles,
)
from nor_object_mi.info_dr_pause_delta import get_y_metric_spec  # noqa: E402
from nor_object_mi.pause_stim_mi import DEFAULT_MODEL, default_out_dir  # noqa: E402

ROOT = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017")
ART_ROOT = ROOT / "_nor_object_mi"


def _fmt_rho(val: float | None) -> str:
    if val is None or not np.isfinite(val):
        return "n/a"
    return f"{val:.2f}"


def fig_pause_vs_full(run_dir: Path, fig_dir: Path) -> None:
    delta = pd.read_csv(run_dir / "pause_stim_delta_excess.csv")
    tx = delta[delta["phase_layer"] == "NOR_TX"].copy()
    pause = tx[tx["mi_label"] == "pause_binary"].set_index("animal_id")
    full = tx[tx["mi_label"] == "full_alphabet"].set_index("animal_id")
    merged = pause[["delta_excess", "sex", "tx"]].join(
        full[["delta_excess"]].rename(columns={"delta_excess": "full_delta_excess"}),
        how="inner",
    )
    apply_style()
    fig, ax = plt.subplots(figsize=(5.2, 4.6))
    for tx_val in TX_ORDER:
        for sex in SEX_ORDER:
            sub = merged[(merged["tx"] == tx_val) & (merged["sex"] == sex)]
            if sub.empty:
                continue
            ax.scatter(
                sub["full_delta_excess"],
                sub["delta_excess"],
                c=TX_COLOR[tx_val],
                marker="o" if sex == "F" else "^",
                s=36,
                edgecolors=INK,
                linewidths=0.35,
                alpha=0.85,
                label=f"{tx_val} {sex}",
            )
    lim = max(
        0.05,
        float(np.nanmax(np.abs(merged[["delta_excess", "full_delta_excess"]].to_numpy()))),
    )
    ax.plot([-lim, lim], [-lim, lim], color=MUTE, lw=0.8, ls="--")
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_xlabel(r"Full-alphabet $\Delta$ excess$_I$ (NOR_TX)")
    ax.set_ylabel(r"Pause-binary $\Delta$ excess$_I$ (NOR_TX)")
    ax.set_title("Pause vs full bout MI novelty contrast", fontweight="bold", color=INK)
    fig_footnote(
        fig,
        "Within-animal bout occupancy MI on novel_obj; pilot model. "
        "Points = animals; shape = sex; color = tx.",
    )
    save_pdf_png(fig, fig_dir / "fig_pause_vs_full_delta_excess_tx")
    plt.close(fig)


def fig_bridge_scatter(run_dir: Path, fig_dir: Path, *, y_token: str, y_label: str) -> None:
    spec = get_y_metric_spec(y_token)
    joined = pd.read_csv(run_dir / f"joined_pause_mi_vs_{y_token}.csv")
    assoc = pd.read_csv(run_dir / "association_tests_long.csv")
    assoc = assoc[
        (assoc["mi_label"] == "pause_binary")
        & (assoc["x_metric"] == "delta_excess")
        & (assoc["y_metric_token"] == y_token)
    ]

    apply_style()
    fig, axes = plt.subplots(2, 4, figsize=(12.5, 5.8), sharex=False, sharey=False)
    for col, phase in enumerate(PHASES):
        for row, sex in enumerate(SEX_ORDER):
            ax = axes[row, col]
            sub = joined[(joined["phase_layer"] == phase) & (joined["sex"] == sex)]
            sub = sub[sub["mi_label"] == "pause_binary"]
            yname = spec.y_col
            for tx_val in TX_ORDER:
                pts = sub[sub["tx"] == tx_val]
                if pts.empty:
                    continue
                ax.scatter(
                    pts["delta_excess"],
                    pts[yname],
                    c=TX_COLOR[tx_val],
                    s=30,
                    edgecolors=INK,
                    linewidths=0.3,
                    alpha=0.9,
                )
            cell = assoc[(assoc["phase_layer"] == phase) & (assoc["sex"] == sex)]
            rho = float(cell["spearman_rho"].iloc[0]) if len(cell) else float("nan")
            pval = float(cell["spearman_p"].iloc[0]) if len(cell) else float("nan")
            panel_stats_box(ax, [f"rho = {_fmt_rho(rho)}", f"p = {pval:.3g}" if np.isfinite(pval) else "p = n/a"])
            if row == 0:
                ax.set_title(PHASE_SHORT.get(phase, phase), fontweight="bold", color=INK)
            if col == 0:
                ax.set_ylabel(f"{sex}\n{y_label}")
            if row == 1:
                ax.set_xlabel(r"Pause $\Delta$ excess$_I$")
    handles = tx_sex_legend_handles()
    fig.legend(handles=handles, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 1.02))
    fig_footnote(
        fig,
        f"Bridge: bout-level pause MI scalar vs composition {y_label} (median 21-model DA). "
        "Spearman by sex x phase; not INFO I(DR;Y).",
    )
    save_pdf_png(fig, fig_dir / f"fig_pause_delta_excess_vs_{y_token}")
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, default=None)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args(argv)

    run_dir = args.run_dir or default_out_dir(ART_ROOT, args.model)
    fig_dir = run_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    fig_pause_vs_full(run_dir, fig_dir)
    fig_bridge_scatter(run_dir, fig_dir, y_token="p_novel", y_label="p_novel (cluster-13)")
    fig_bridge_scatter(run_dir, fig_dir, y_token="delta_p_novelty", y_label="novelty-step delta_p")
    print(json.dumps({"run_dir": str(run_dir), "figures": str(fig_dir)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
