"""CLI: align feedback/table to ambulation xy timeline in a cohort H5."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from maze.pipeline.db.feedback_align import align_feedback_h5


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="One-time/batch rewrite of feedback/table to match xy frame_index timeline.",
    )
    ap.add_argument("db_path", type=Path, help="Pipeline or legacy results H5")
    ap.add_argument("--dry-run", action="store_true", help="Report counts only (no writes)")
    args = ap.parse_args(argv)

    db_path = Path(args.db_path)
    if not db_path.is_file():
        print(f"Not a file: {db_path}", file=sys.stderr)
        return 2

    if args.dry_run:
        # align_feedback_h5 always writes; for dry-run scan with read-only open
        import h5py

        from maze.core.h5_layout import read_feedback_table
        from maze.pipeline.db.feedback_align import feedback_table_matches_xy, read_primary_xy_table
        from maze.pipeline.db.trial_groups import list_trials

        stats = {"seen": 0, "would_align": 0, "already_aligned": 0, "missing_xy": 0, "missing_feedback": 0}
        with h5py.File(db_path, "r") as h5:
            for key in list_trials(db_path):
                stats["seen"] += 1
                path = key.path().lstrip("/")
                if path not in h5:
                    continue
                g = h5[path]
                xy = read_primary_xy_table(g)
                if xy is None:
                    stats["missing_xy"] += 1
                    continue
                fb = read_feedback_table(g)
                if fb is None:
                    stats["missing_feedback"] += 1
                    continue
                if feedback_table_matches_xy(fb, xy):
                    stats["already_aligned"] += 1
                else:
                    stats["would_align"] += 1
        print(json.dumps(stats, indent=2))
        return 0

    stats = align_feedback_h5(db_path)
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
