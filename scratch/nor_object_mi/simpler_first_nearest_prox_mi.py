"""Runner: I(label; nearest object prox) on nvl_obj across phases.

Regen:

    uv run python scratch/nor_object_mi/simpler_first_nearest_prox_mi.py
    uv run python scratch/nor_object_mi/simpler_first_nearest_prox_mi.py --label cluster
    uv run python scratch/nor_object_mi/simpler_first_nearest_prox_mi.py --all-models --label cluster
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.nearest_prox_mi import (  # noqa: E402
    DEFAULT_N_PERM,
    LabelKind,
    default_ensemble_out_dir,
    default_out_dir,
    default_sig_dir,
    write_ensemble_run,
    write_run,
)
from nor_object_mi.pause_stim_mi import DEFAULT_MODEL  # noqa: E402
from nor_object_mi.simpler_first_object_prox import NEAR_R_M  # noqa: E402

ROOT = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017")
ART_ROOT = ROOT / "_nor_object_mi"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--art-root", type=Path, default=ART_ROOT)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument(
        "--all-models",
        action="store_true",
        help="21-model ensemble; median consensus per animal (cluster label only)",
    )
    ap.add_argument(
        "--label",
        choices=("syllable", "cluster"),
        default="syllable",
        help="X variable: raw syllable id or HDBSCAN cluster_id",
    )
    ap.add_argument("--sig-dir", type=Path, default=None, help="syllable_prototypes_clustered.csv dir")
    ap.add_argument("--r-m", type=float, default=NEAR_R_M)
    ap.add_argument("--n-perm", type=int, default=DEFAULT_N_PERM)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args(argv)

    label_kind: LabelKind = args.label  # type: ignore[assignment]
    sig_dir = args.sig_dir or default_sig_dir(args.art_root)

    if args.all_models:
        if label_kind != "cluster":
            raise SystemExit("--all-models requires --label cluster")
        out = args.out_dir or default_ensemble_out_dir(args.art_root, label_kind=label_kind)
        print(
            f"nearest-prox MI ensemble: label={label_kind} r={args.r_m}m n_perm={args.n_perm} ...",
            flush=True,
        )
        summary = write_ensemble_run(
            art_root=args.art_root,
            out_dir=out,
            r_m=float(args.r_m),
            n_perm=int(args.n_perm),
            seed=int(args.seed),
            label_kind=label_kind,
            sig_dir=sig_dir,
        )
    else:
        out = args.out_dir or default_out_dir(args.art_root, args.model, label_kind=label_kind)
        print(
            f"nearest-prox MI: model={args.model} label={label_kind} r={args.r_m}m ...",
            flush=True,
        )
        summary = write_run(
            art_root=args.art_root,
            out_dir=out,
            model=str(args.model),
            r_m=float(args.r_m),
            n_perm=int(args.n_perm),
            seed=int(args.seed),
            label_kind=label_kind,
            sig_dir=sig_dir if label_kind == "cluster" else None,
        )

    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
