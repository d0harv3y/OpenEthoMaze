"""Four-mask TX−BL frac by tx (novel_obj); mark tx-specific cells.

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/fig_simpler_first_four_mask.py --dest slides
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
    TX_COLOR,
    TX_ORDER,
    apply_style,
    fig_footnote,
    save_pdf_svg,
    type_scale,
)
from nor_object_mi.four_mask import MASKS  # noqa: E402
from nor_object_mi.simpler_first_q1 import SEX_ORDER  # noqa: E402

DEFAULT_RUN = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_four_mask"
)
FOOT = (
    "Locked ss-50. Y = TX−BL fraction of syllable time in that bout-mask "
    "(majority still|move × bout-mean dist < 0.10 m). Novel_obj only. "
    "Star = tx-specific (novel Welch ANOVA FDR and gates miss on identical/no_obj "
    "and BL level). Not investigation; not DA. Ids not portable."
)


def _as_bool(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s
    return s.astype(str).str.lower().isin(("true", "1"))


def fig_delta_frac(paired: pd.DataFrame, gates: pd.DataFrame, stem: Path, *, dest: str) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    p = paired[paired["condition_layer"] == "novel_obj"].copy()
    g = gates.copy()
    if not g.empty:
        g["tx_specific"] = _as_bool(g["tx_specific"])
    fig, axes = plt.subplots(2, 4, figsize=(12.4, 6.4), constrained_layout=True)
    rng = np.random.default_rng(1)
    for r, sex in enumerate(SEX_ORDER):
        for c, mask in enumerate(MASKS):
            ax = axes[r][c]
            cell = p[(p["sex"] == sex) & (p["mask"] == mask)]
            for i, tx in enumerate(TX_ORDER):
                y = cell.loc[cell["tx"] == tx, "delta_frac_mask"].to_numpy(dtype=np.float64)
                y = y[np.isfinite(y)]
                x = np.full(y.size, i, dtype=np.float64) + rng.uniform(-0.12, 0.12, size=y.size)
                ax.scatter(x, y, s=22, color=TX_COLOR[tx], alpha=0.75, zorder=2)
                if y.size:
                    ax.hlines(float(np.mean(y)), i - 0.28, i + 0.28, color=INK, lw=1.2, zorder=3)
            spec = False
            if not g.empty:
                hit = g[
                    (g["sex"] == sex)
                    & (g["mask"] == mask)
                    & (g["metric"] == "delta_frac_mask")
                    & g["tx_specific"]
                ]
                spec = len(hit) > 0
            title = mask.replace("_", " ")
            if spec:
                title = title + " ★"
            ax.set_title(title, fontsize=ts["annotation"], color="#b00020" if spec else INK)
            ax.axhline(0.0, color="#cccccc", lw=0.8)
            ax.set_xticks(range(len(TX_ORDER)))
            ax.set_xticklabels(list(TX_ORDER), fontsize=ts["cell"])
            if c == 0:
                ax.set_ylabel(f"{sex}  Δ frac", fontsize=ts["annotation"])
            else:
                ax.set_ylabel("")
    fig.suptitle("Four-mask hunt — novel_obj TX−BL frac", fontsize=ts["suptitle"], color=INK)
    fig_footnote(fig, FOOT)
    save_pdf_svg(fig, stem)
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    args = ap.parse_args(argv)
    paired = pd.read_csv(args.run_dir / "paired_tx_minus_bl.csv")
    gates = pd.read_csv(args.run_dir / "gate_hits.csv")
    fig_delta_frac(paired, gates, args.run_dir / "fig_four_mask_delta_frac", dest=args.dest)
    print(f"Wrote {args.run_dir / 'fig_four_mask_delta_frac.pdf'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
