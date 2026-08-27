"""Patch syllable_bout_kinematics.csv with manifest sex/strain/tx (preserves n/a).

  uv run python scratch/vast_moseq/patch_kinematics_meta.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from vast_moseq.cohort_meta import DEFAULT_MANIFEST, load_animal_meta  # noqa: E402

DEFAULT_CSV = Path(
    r"C:\Users\admin\Documents\work\sack\AZ-SD-VAST-moseq"
    r"\syllable_bout_kinematics\syllable_bout_kinematics.csv"
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--chunksize", type=int, default=250_000)
    args = ap.parse_args(argv)

    meta = load_animal_meta(args.manifest)
    tmp = args.csv.with_suffix(".patched.csv")
    first = True
    n = 0
    for ch in pd.read_csv(args.csv, chunksize=int(args.chunksize), keep_default_na=False):
        ch["animal_id"] = ch["animal_id"].astype(str)
        for col in ("sex", "strain", "tx"):
            if col in ch.columns:
                ch = ch.drop(columns=[col])
        ch = ch.merge(meta, on="animal_id", how="left")
        if "strain" not in ch.columns:
            raise RuntimeError("strain column missing after merge")
        ch.to_csv(tmp, index=False, mode="w" if first else "a", header=first)
        first = False
        n += len(ch)
        print(f"  rows={n:,}", flush=True)
    tmp.replace(args.csv)
    print(f"patched {args.csv} ({n:,} rows)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
