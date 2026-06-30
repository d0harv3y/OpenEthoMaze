"""CLI: evaluate Behavior producer artifacts against is_moving anchor."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from maze.kpms.behavior_ethogram.anchor_store import missing_is_moving_anchor_files
from maze.kpms.behavior_ethogram.evaluate import (
    cross_seed_reproducibility,
    evaluate_behavior_producers,
)
from maze.kpms.behavior_ethogram.labeling import missing_behavior_labeling_files

_EXAMPLE = """
Example (after a producer emits S0 artifacts in S2–S4):

  uv run maze-evaluate-behavior-producers \\
    --anchor-dir "C:/.../test2/behavior_ethogram/anchors/is_moving/ele_v1" \\
    --producer-dir "C:/.../test2/behavior_ethogram/producers/bout_arhmm/seed_042"

Producer dirs must contain behavior_frames.h5 + provenance.json (not anatomical/seed_*).
"""


def _validate_dirs(anchor_dir: Path, producer_dirs: list[Path]) -> int:
    missing_anchor = missing_is_moving_anchor_files(anchor_dir)
    if missing_anchor:
        print(
            f"Anchor dir missing required files: {anchor_dir}\n"
            f"  missing: {', '.join(missing_anchor)}\n"
            "Build anchor first: uv run maze-build-is-moving-anchor ...",
            file=sys.stderr,
        )
        return 1
    for p in producer_dirs:
        missing = missing_behavior_labeling_files(p)
        if missing:
            print(
                f"Producer dir missing required files: {p}\n"
                f"  missing: {', '.join(missing)}\n"
                "Expected: <kpms_root>/behavior_ethogram/producers/<producer>/<fit_id>/\n"
                "  (kpMS anatomical/seed_* and stage_iii CSVs are not Behavior producers yet.)",
                file=sys.stderr,
            )
            return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Evaluate Behavior producers vs is_moving anchor.",
        epilog=_EXAMPLE,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--anchor-dir", type=Path, required=True)
    ap.add_argument("--producer-dir", type=Path, action="append", required=True, dest="producer_dirs")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    if _validate_dirs(args.anchor_dir, args.producer_dirs):
        return 1
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
