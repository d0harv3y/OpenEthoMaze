"""INFO runner: sex vs dominant cluster id (within tx, phases pooled).

    uv run python scratch/nor_object_mi/simpler_first_info_sex_cluster.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.info_sex_cluster import (  # noqa: E402
    DEFAULT_N_PERM,
    default_out_dir,
    write_run,
)

ROOT = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017")
ART_ROOT = ROOT / "_nor_object_mi"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--art-root", type=Path, default=ART_ROOT)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--n-perm", type=int, default=DEFAULT_N_PERM)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument(
        "--skip-frame-build",
        action="store_true",
        help="Reuse cluster_frames_per_model.csv if present (composition INFO only refresh)",
    )
    args = ap.parse_args(argv)

    out = args.out_dir or default_out_dir(ROOT)
    print("INFO: sex vs cluster + composition (within tx, phases pooled) ...", flush=True)
    summary = write_run(
        art_root=args.art_root,
        out_dir=out,
        n_perm=int(args.n_perm),
        seed=int(args.seed),
        skip_frame_build=bool(args.skip_frame_build),
    )
    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
