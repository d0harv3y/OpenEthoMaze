"""Presence-step Δ P(move) on the hysteresis segmenter.

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/fig_simpler_first_locomotor_presence.py --dest slides
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
from nor_object_mi.locomotor_presence import PRIMARY_STEP  # noqa: E402
from nor_object_mi.simpler_first_protocol_prologue import PHASES  # noqa: E402
from nor_object_mi.simpler_first_q1 import SEX_ORDER  # noqa: E402

DEFAULT_RUN = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_locomotor_presence"
)
PHASE_SHORT = {
    "NOR_BL": "BL",
    "NOR_TX": "TX",
    "NOR_REC3hr": "REC3",
    "NOR_REC11hr": "REC11",
}
FOOT = (
    "Hysteresis move|still (not kpMS). Y = identical − no_obj frame P(move). "
    "One-sample t within sex; star = BH FDR within sex × phase (5-metric family). "
    "Color = tx. Not syllable DA; not investigation."
)


def _as_bool(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s
    return s.astype(str).str.lower().isin(("true", "1"))


def fig_delta_p_move(
    paired: pd.DataFrame,
    tests: pd.DataFrame,
    stem: Path,
    *,
    dest: str,
) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    p = paired[paired["step"] == PRIMARY_STEP].copy()
    t = tests.copy()
    if not t.empty:
        t["hit_fdr05"] = _as_bool(t["hit_fdr05"]) if "hit_fdr05" in t.columns else False
    fig, axes = plt.subplots(2, 4, figsize=(12.4, 6.2), constrained_layout=True)
    rng = np.random.default_rng(2)
    for r, sex in enumerate(SEX_ORDER):
        for c, ph in enumerate(PHASES):
            ax = axes[r][c]
            cell = p[(p["sex"] == sex) & (p["phase_layer"] == ph)]
            for i, tx in enumerate(TX_ORDER):
                y = pd.to_numeric(cell.loc[cell["tx"] == tx, "delta_p_move"], errors="coerce")
                y = y.to_numpy(dtype=np.float64)
                y = y[np.isfinite(y)]
                x = np.full(y.size, i, dtype=np.float64) + rng.uniform(-0.12, 0.12, size=y.size)
                ax.scatter(x, y, s=20, color=TX_COLOR.get(tx, INK), alpha=0.75, zorder=2)
                if y.size:
                    ax.hlines(float(np.mean(y)), i - 0.28, i + 0.28, color=INK, lw=1.2, zorder=3)
            ax.axhline(0.0, color="#cccccc", lw=0.8)
            hit = False
            if not t.empty:
                rec = t[
                    (t["family"] == "primary")
                    & (t["metric"] == "p_move")
                    & (t["sex"] == sex)
                    & (t["phase_layer"] == ph)
                ]
                hit = len(rec) == 1 and bool(rec["hit_fdr05"].iloc[0])
            title = PHASE_SHORT.get(ph, ph)
            if hit:
                title = title + " ★"
            ax.set_title(title, fontsize=ts["annotation"], color="#b00020" if hit else INK)
            ax.set_xticks(range(len(TX_ORDER)))
            ax.set_xticklabels(list(TX_ORDER), fontsize=ts["cell"])
            if c == 0:
                ax.set_ylabel(f"{sex}  Δ P(move)", fontsize=ts["annotation"])
    fig.suptitle("Presence on the original segmenter — Δ P(move)", fontsize=ts["suptitle"], color=INK)
    fig_footnote(fig, FOOT)
    save_pdf_svg(fig, stem)
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    args = ap.parse_args(argv)
    paired = pd.read_csv(args.run_dir / "paired_step_deltas.csv")
    tests = pd.read_csv(args.run_dir / "locomotor_presence_tests.csv")
    fig_delta_p_move(paired, tests, args.run_dir / "fig_locomotor_presence_delta_p_move", dest=args.dest)
    print(f"Wrote {args.run_dir / 'fig_locomotor_presence_delta_p_move.pdf'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
