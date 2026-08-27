"""Runner: pause-syllable bout MI vs binned object proximity (original MI design).

Regen (OpenEthoMaze repo root):

    uv run python scratch/nor_object_mi/simpler_first_pause_stim_mi.py

Requires:

- archived ``ladder_bout_features.csv`` per phase under ``_nor_object_mi/archive/<model>/``
- ``simpler_first_da/duration_band_vs_da.csv`` + ``da_syllable_deltas_per_animal.csv``
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.info_dr_pause_delta import y_metric_choices  # noqa: E402
from nor_object_mi.pause_stim_mi import (  # noqa: E402
    DEFAULT_MODEL,
    DEFAULT_N_BINS,
    DEFAULT_N_PERM,
    default_out_dir,
    write_run,
)

ROOT = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017")
ART_ROOT = ROOT / "_nor_object_mi"
DEFAULT_DA = ART_ROOT / "simpler_first_da"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--art-root", type=Path, default=ART_ROOT)
    ap.add_argument("--da-dir", type=Path, default=DEFAULT_DA)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--n-bins", type=int, default=DEFAULT_N_BINS)
    ap.add_argument("--n-perm", type=int, default=DEFAULT_N_PERM)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--y-metrics",
        nargs="+",
        default=["p_novel", "delta_p_novelty"],
        choices=y_metric_choices(),
        help="composition Y metrics to correlate with pause MI scalars",
    )
    args = ap.parse_args(argv)

    out = args.out_dir or default_out_dir(args.art_root, args.model)
    print(f"pause stim MI: model={args.model} -> {out}", flush=True)
    summary = write_run(
        art_root=args.art_root,
        da_dir=args.da_dir,
        out_dir=out,
        model=str(args.model),
        n_bins=int(args.n_bins),
        n_perm=int(args.n_perm),
        seed=int(args.seed),
        y_metrics=tuple(args.y_metrics),
    )
    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
