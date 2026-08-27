"""INFO runner: object-prox DR vs pause bout mi_mm_nvl.

Regen:

    uv run python scratch/nor_object_mi/simpler_first_info_dr_pause_mi.py

Requires:

- ``simpler_first_object_prox_0p10/object_prox_metrics_per_animal.csv``
- ``simpler_first_pause_stim_mi__<model>/pause_stim_delta_excess.csv``
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.info_dr_pause_bout_mi import (  # noqa: E402
    DEFAULT_N_BINS,
    DEFAULT_N_PERM,
    default_out_dir,
    default_pause_mi_dir,
    write_run,
)
from nor_object_mi.pause_stim_mi import DEFAULT_MODEL  # noqa: E402

ROOT = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017")
ART_ROOT = ROOT / "_nor_object_mi"
DEFAULT_OBJECT_PROX = ART_ROOT / "simpler_first_object_prox_0p10"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--object-prox-dir", type=Path, default=DEFAULT_OBJECT_PROX)
    ap.add_argument("--pause-mi-dir", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--model", default=DEFAULT_MODEL, help="kpMS model used for pause bout MI")
    ap.add_argument("--n-bins", type=int, default=DEFAULT_N_BINS)
    ap.add_argument("--n-perm", type=int, default=DEFAULT_N_PERM)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)

    pause_mi_dir = args.pause_mi_dir or default_pause_mi_dir(ART_ROOT, args.model)
    out = args.out_dir or default_out_dir(ROOT)
    print(f"INFO: object-prox DR vs pause mi_mm_nvl (model={args.model}) ...", flush=True)
    summary = write_run(
        object_prox_dir=args.object_prox_dir,
        pause_mi_dir=pause_mi_dir,
        out_dir=out,
        model=str(args.model),
        n_bins=int(args.n_bins),
        n_perm=int(args.n_perm),
        seed=int(args.seed),
    )
    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
