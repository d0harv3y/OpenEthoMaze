"""CLI: evaluate Behavior producer artifacts against is_moving anchor."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from maze.kpms.behavior_ethogram.evaluate import (
    cross_seed_reproducibility,
    evaluate_behavior_producers,
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Evaluate Behavior producers vs is_moving anchor.")
    ap.add_argument("--anchor-dir", type=Path, required=True)
    ap.add_argument("--producer-dir", type=Path, action="append", required=True, dest="producer_dirs")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    reports = evaluate_behavior_producers(args.producer_dirs, args.anchor_dir)
    cross = cross_seed_reproducibility(reports)
    payload = {
        "reports": [r.to_dict() for r in reports],
        "cross_seed": {
            "n_producers": cross.n_producers,
            "shared_trial_keys": list(cross.shared_trial_keys),
            "mean_moving_fraction_std": cross.mean_moving_fraction_std,
            "per_producer_moving_fraction": cross.per_producer_moving_fraction,
        },
    }
    text = json.dumps(payload, indent=2)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
