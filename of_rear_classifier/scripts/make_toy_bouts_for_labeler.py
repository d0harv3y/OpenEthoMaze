"""Build a fake bout CSV from fixed-length chunks (smoke-test the labeler pre-MoSeq)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np

from of_rear_classifier.syllable_bouts import bouts_from_syllable_sequence, save_bout_table


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--n-frames", type=int, default=3000)
    p.add_argument("--bout-len", type=int, default=60)
    p.add_argument("--n-syllables", type=int, default=12)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args(argv)

    rng = np.random.default_rng(args.seed)
    n = args.n_frames
    syll = np.empty(n, dtype=np.int32)
    i = 0
    sid = 0
    while i < n:
        L = min(args.bout_len, n - i)
        syll[i : i + L] = sid % args.n_syllables
        sid += 1
        i += L
        if rng.random() < 0.15:
            sid += rng.integers(0, 3)
    df = bouts_from_syllable_sequence(syll)
    save_bout_table(df, args.out)
    print(f"wrote {args.out} ({len(df)} bouts)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
