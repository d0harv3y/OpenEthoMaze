"""INFO runner: object-prox DR vs cluster-13 pause syllable Y.

Regen (OpenEthoMaze repo root):

    uv run python scratch/nor_object_mi/simpler_first_info_dr_pause.py
    uv run python scratch/nor_object_mi/simpler_first_info_dr_pause.py --y-metric presence_novel

Requires upstream artifacts:

- ``simpler_first_object_prox_0p10/object_prox_metrics_per_animal.csv``
- ``simpler_first_da/da_syllable_deltas_per_animal.csv``
- ``simpler_first_da/duration_band_vs_da.csv`` (from ``fig_duration_band.py``)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.info_dr_pause_delta import (  # noqa: E402
    DEFAULT_N_BINS,
    DEFAULT_N_PERM,
    DEFAULT_Y_METRIC,
    default_out_dir,
    get_y_metric_spec,
    write_run,
    y_metric_choices,
)

ROOT = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017")
DEFAULT_OBJECT_PROX = ROOT / "_nor_object_mi" / "simpler_first_object_prox_0p10"
DEFAULT_DA = ROOT / "_nor_object_mi" / "simpler_first_da"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--object-prox-dir", type=Path, default=DEFAULT_OBJECT_PROX)
    ap.add_argument("--da-dir", type=Path, default=DEFAULT_DA)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument(
        "--y-metric",
        choices=y_metric_choices(),
        default=DEFAULT_Y_METRIC,
        help="pause syllable Y for INFO (default: novelty-step delta_p)",
    )
    ap.add_argument("--n-bins", type=int, default=DEFAULT_N_BINS)
    ap.add_argument("--n-perm", type=int, default=DEFAULT_N_PERM)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)

    spec = get_y_metric_spec(args.y_metric)
    out = args.out_dir or default_out_dir(ROOT, spec.token)
    print(f"INFO: object-prox DR vs {spec.token} ...", flush=True)
    summary = write_run(
        object_prox_dir=args.object_prox_dir,
        da_dir=args.da_dir,
        out_dir=out,
        y_metric=spec.token,
        n_bins=int(args.n_bins),
        n_perm=int(args.n_perm),
        seed=int(args.seed),
    )
    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
