"""Figures: INFO object-prox DR vs pause bout mi_mm_nvl.

Regen:

    uv run python scratch/nor_object_mi/fig_simpler_first_info_dr_pause_mi.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.fig_simpler_first_info_dr_pause import fig_heatmaps, fig_scatter  # noqa: E402
from nor_object_mi.info_dr_pause_bout_mi import SPEC, default_out_dir  # noqa: E402

ROOT = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    args = ap.parse_args(argv)

    run = args.run_dir or default_out_dir(ROOT)
    out = args.out_dir or (run / "figures")
    out.mkdir(parents=True, exist_ok=True)

    joined = pd.read_csv(run / "info_dr_pause_mi_joined_per_animal.csv")
    tests = pd.read_csv(run / "info_dr_pause_mi_tests_long.csv")

    fig_scatter(joined, tests, out, spec=SPEC, dest=args.dest)
    fig_heatmaps(tests, out, spec=SPEC, dest=args.dest)
    print(f"wrote figures under {out} ({SPEC.token})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
