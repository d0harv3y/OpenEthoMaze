"""Cross-model consensus: DA lollipop hits × locomotor occupancy class.

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/fig_simpler_first_occupancy_lollipop_consensus.py --dest slides
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
    INK,
    apply_style,
    fig_footnote,
    save_pdf_svg,
    type_scale,
)
from nor_object_mi.occupancy_lollipop import STEPS  # noqa: E402
from nor_object_mi.simpler_first_protocol_prologue import PHASES  # noqa: E402

DEFAULT_RUN = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_occupancy_da_consensus"
)
PHASE_SHORT = {
    "NOR_BL": "BL",
    "NOR_TX": "TX",
    "NOR_REC3hr": "REC3",
    "NOR_REC11hr": "REC11",
}
STEP_LAB = {
    "no_obj->identical": "presence",
    "identical->novel": "novelty",
    "no_obj->novel": "span",
}
FOOT = (
    "21 kpMS models. Each point = one model: fraction of DA FDR-hit ids that "
    "are move-enriched in the DA destination condition (t vs 0, BH within "
    "model × phase × condition). Presence uses identical_obj occupancy; "
    "novelty/span use novel_obj. Ids are not portable — pattern consensus, "
    "not a shared syllable. Tick = median across models with ≥1 DA hit. "
    "Not tx. Not investigation."
)


def fig_consensus(summary: pd.DataFrame, cons: pd.DataFrame, stem: Path, *, dest: str) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    fig, axes = plt.subplots(3, 4, figsize=(11.6, 8.4), constrained_layout=True, sharey=True)
    rng = np.random.default_rng(0)
    for r, step in enumerate(STEPS):
        for c, ph in enumerate(PHASES):
            ax = axes[r][c]
            cell = summary[(summary["step"] == step) & (summary["phase_layer"] == ph)]
            y = pd.to_numeric(cell["frac_da_move"], errors="coerce").to_numpy(dtype=float)
            n_da = pd.to_numeric(cell["n_da_fdr"], errors="coerce").to_numpy(dtype=float)
            ok = np.isfinite(y) & (n_da > 0)
            y = y[ok]
            x = np.zeros(y.size) + rng.normal(0, 0.06, size=y.size)
            ax.scatter(x, y, s=18, c="#2f5d8a", alpha=0.75, edgecolors="white", linewidths=0.3, zorder=3)
            rec = cons[(cons["step"] == step) & (cons["phase_layer"] == ph)]
            if len(rec) == 1 and np.isfinite(float(rec["median_frac_da_move"].iloc[0])):
                med = float(rec["median_frac_da_move"].iloc[0])
                ax.plot([-0.35, 0.35], [med, med], color=INK, lw=1.6, zorder=4)
                n_m = int(rec["n_models_with_da"].iloc[0])
                n_maj = int(rec["n_models_move_majority"].iloc[0])
                ax.set_title(
                    f"{PHASE_SHORT.get(ph, ph)}  {n_maj}/{n_m} move>½",
                    loc="left",
                    fontsize=ts["annotation"] - 1,
                    color=INK,
                )
            else:
                ax.set_title(PHASE_SHORT.get(ph, ph), loc="left", fontsize=ts["annotation"] - 1, color=INK)
            ax.set_xticks([])
            ax.set_ylim(-0.05, 1.05)
            if c == 0:
                ax.set_ylabel(STEP_LAB.get(step, step) + "\nfrac DA ∩ move", fontsize=ts["annotation"])
    fig.suptitle(
        "Across models: DA hits lean move, not a shared id",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_footnote(fig, FOOT, y=-0.04)
    save_pdf_svg(fig, stem)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    args = ap.parse_args(argv)
    summary = pd.read_csv(args.run_dir / "da_occupancy_set_summary_all_models.csv")
    cons = pd.read_csv(args.run_dir / "da_occupancy_consensus.csv")
    fig_consensus(summary, cons, args.run_dir / f"fig_occupancy_lollipop_consensus_{args.dest}", dest=args.dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
