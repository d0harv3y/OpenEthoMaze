"""Signed DA lollipops colored by dest-matched locomotor occupancy.

X = median Δp (gain right of 0, loss left). Color = occupancy class.
Marker: triangle up = share gain; triangle down = share loss.

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/fig_simpler_first_occupancy_lollipop.py --dest slides
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi._pub_style import (  # noqa: E402
    INK,
    apply_style,
    fig_footnote,
    save_pdf_svg,
    type_scale,
)
from nor_object_mi.occupancy_lollipop import (  # noqa: E402
    STEPS,
    consensus_signed_across_models,
    join_da_occupancy,
    signed_overlap_summary,
)
from nor_object_mi.simpler_first_protocol_prologue import PHASES  # noqa: E402

PHASE_SHORT = {
    "NOR_BL": "BL",
    "NOR_TX": "TX",
    "NOR_REC3hr": "REC3",
    "NOR_REC11hr": "REC11",
}

DEFAULT_RUN = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_occupancy_da_join"
)
DEFAULT_DA = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_da\da_syllable_tests_long.csv"
)
CLASS_COLOR = {"move": "#2f5d8a", "still": "#8a4f3d", "ns": "#9a9a9a", "no_occ": "#cccccc"}
STEP_LAB = {
    "no_obj->identical": "presence",
    "identical->novel": "novelty",
    "no_obj->novel": "span",
}
MAX_N = 28
FOOT = (
    "Locked ss-50. Stem = DA FDR hit; x = median Δp (right = more share on the "
    "destination condition). Color = dest occupancy (identical_obj for presence, "
    "novel_obj for novelty/span). ▲ gain  ▼ loss. Grey = occupancy ns vs 0. "
    "Occupancy and DA are different contrasts. Ids not portable. Not tx."
)
FOOT_CONS = (
    "21 kpMS models. Each pair: median (across models) fraction of DA gainers "
    "vs losers that are move-enriched at the destination. Not portable ids. Not tx."
)


def _as_bool(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s
    return s.astype(str).str.lower().isin(("true", "1"))


def fig_join_lollipops(joined: pd.DataFrame, stem: Path, *, dest: str) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    j = joined.copy()
    j["on_lollipop"] = _as_bool(j["on_lollipop"]) if "on_lollipop" in j.columns else _as_bool(j["hit_da_fdr05"])
    fig, axes = plt.subplots(3, 4, figsize=(12.4, 9.8), constrained_layout=True)
    for r, step in enumerate(STEPS):
        for c, ph in enumerate(PHASES):
            ax = axes[r][c]
            cell = j[(j["step"] == step) & (j["phase_layer"] == ph) & j["on_lollipop"]]
            n_hit = int(len(cell))
            if n_hit == 0:
                ax.text(0.5, 0.5, "0 FDR DA", ha="center", va="center", color="#888888")
                ax.set_xticks([])
                ax.set_yticks([])
                continue
            dlt = pd.to_numeric(cell["median_delta_p"], errors="coerce")
            n_gain = int((dlt > 0).sum())
            n_loss = int((dlt < 0).sum())
            shown = cell.assign(abs_d=dlt.abs(), delta=dlt)
            shown = shown.sort_values("abs_d", ascending=False).head(MAX_N)
            shown = shown.sort_values("delta")
            y = np.arange(len(shown))
            d = shown["delta"].to_numpy(dtype=float)
            cols = [CLASS_COLOR.get(str(x), CLASS_COLOR["ns"]) for x in shown["locomotor_class"]]
            ax.hlines(y, 0.0, d, color="#c8c8c8", lw=0.7)
            for yi, xi, col, di in zip(y, d, cols, d, strict=True):
                mk = "^" if di > 0 else "v"
                ax.scatter(xi, yi, c=[col], s=28, marker=mk, zorder=3, edgecolors="white", linewidths=0.3)
            ax.axvline(0.0, color="#bbbbbb", lw=0.6, ls="--", zorder=1)
            ax.set_yticks(y)
            ax.set_yticklabels([str(int(i)) for i in shown["raw_syllable_id"]], fontsize=ts["cell"] - 2)
            n_m = int((cell["locomotor_class"] == "move").sum())
            n_s = int((cell["locomotor_class"] == "still").sum())
            ax.set_title(
                f"{PHASE_SHORT.get(ph, ph)}  DA={n_hit}  +{n_gain} −{n_loss}  m={n_m} s={n_s}",
                loc="left",
                fontsize=ts["annotation"] - 2,
                color=INK,
            )
            if c == 0:
                ax.set_ylabel(STEP_LAB.get(step, step), fontsize=ts["annotation"])
            if r == 2:
                ax.set_xlabel("median Δp  (gain →)", fontsize=ts["annotation"])
    handles = [
        Line2D([0], [0], marker="^", color="none", markerfacecolor=CLASS_COLOR["move"], markersize=8, label="move gain"),
        Line2D([0], [0], marker="v", color="none", markerfacecolor=CLASS_COLOR["move"], markersize=8, label="move loss"),
        Line2D([0], [0], marker="^", color="none", markerfacecolor=CLASS_COLOR["still"], markersize=8, label="still gain"),
        Line2D([0], [0], marker="v", color="none", markerfacecolor=CLASS_COLOR["still"], markersize=8, label="still loss"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=CLASS_COLOR["ns"], markersize=8, label="occupancy ns"),
    ]
    fig.legend(handles=handles, loc="upper right", frameon=False, fontsize=ts["legend"] - 1, ncol=5)
    fig.suptitle(
        "Signed DA lollipop × dest-matched occupancy",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_footnote(fig, FOOT, y=-0.04)
    save_pdf_svg(fig, stem)


def fig_signed_consensus(cons: pd.DataFrame, stem: Path, *, dest: str) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    fig, axes = plt.subplots(3, 4, figsize=(11.6, 7.6), constrained_layout=True, sharey=True)
    for r, step in enumerate(STEPS):
        for c, ph in enumerate(PHASES):
            ax = axes[r][c]
            rec = cons[(cons["step"] == step) & (cons["phase_layer"] == ph)]
            ax.set_xlim(-0.5, 1.5)
            ax.set_ylim(-0.05, 1.05)
            ax.axhline(0.5, color="#dddddd", lw=0.6, zorder=1)
            if rec.empty:
                ax.set_xticks([0, 1], ["gain", "loss"])
                continue
            row = rec.iloc[0]
            yg = float(row["median_frac_gain_move"])
            yl = float(row["median_frac_loss_move"])
            if np.isfinite(yg):
                ax.scatter([0], [yg], s=36, c="#2f5d8a", zorder=3)
                ax.text(0, yg + 0.04, f"{yg:.2f}", ha="center", fontsize=ts["cell"] - 1, color=INK)
            if np.isfinite(yl):
                ax.scatter([1], [yl], s=36, c="#8a4f3d", zorder=3)
                ax.text(1, yl + 0.04, f"{yl:.2f}", ha="center", fontsize=ts["cell"] - 1, color=INK)
            n_g = int(row["n_models_with_gain"])
            n_l = int(row["n_models_with_loss"])
            ax.set_title(
                f"{PHASE_SHORT.get(ph, ph)}  {n_g}/{n_l} models",
                loc="left",
                fontsize=ts["annotation"] - 1,
                color=INK,
            )
            ax.set_xticks([0, 1], ["gain", "loss"])
            if c == 0:
                ax.set_ylabel(STEP_LAB.get(step, step) + "\nfrac move", fontsize=ts["annotation"] - 1)
    fig.suptitle(
        "Signed DA × occupancy consensus (median frac-move among gainers vs losers)",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_footnote(fig, FOOT_CONS, y=-0.04)
    save_pdf_svg(fig, stem)


def _signed_all_models(da: pd.DataFrame, occ_tests: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    parts: list[pd.DataFrame] = []
    for model, ot in occ_tests.groupby("model", sort=False):
        joined = join_da_occupancy(da, ot, model=str(model))
        if joined.empty:
            continue
        parts.append(signed_overlap_summary(joined))
    per = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    cons = consensus_signed_across_models(per)
    return per, cons


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    ap.add_argument("--da-csv", type=Path, default=DEFAULT_DA)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    args = ap.parse_args(argv)
    joined = pd.read_csv(args.run_dir / "da_occupancy_join.csv")
    signed = signed_overlap_summary(joined)
    signed.to_csv(args.run_dir / "da_occupancy_signed_summary.csv", index=False)
    fig_join_lollipops(joined, args.run_dir / f"fig_occupancy_lollipop_{args.dest}", dest=args.dest)
    occ_all = args.run_dir / "occupancy_tests_all_models.csv"
    if occ_all.is_file() and args.da_csv.is_file():
        da = pd.read_csv(args.da_csv)
        occ = pd.read_csv(occ_all)
        per, cons = _signed_all_models(da, occ)
        per.to_csv(args.run_dir / "da_occupancy_signed_summary_all_models.csv", index=False)
        cons.to_csv(args.run_dir / "da_occupancy_signed_consensus.csv", index=False)
        fig_signed_consensus(cons, args.run_dir / f"fig_occupancy_lollipop_signed_consensus_{args.dest}", dest=args.dest)
        print(f"wrote signed consensus n_models={cons['n_models'].max() if not cons.empty else 0}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
