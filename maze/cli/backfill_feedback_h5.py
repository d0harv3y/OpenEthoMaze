"""CLI: backfill feedback/table from source input H5 W/M arrays."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from maze.pipeline.db.feedback_align import backfill_feedback_h5


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Rewrite feedback/table from source input_h5_path W/M when aligned rows "
            "contain NaN (e.g. after run-only expand). Applies VIDEO_PATH_PREFIX_REMAPS."
        ),
    )
    ap.add_argument("db_path", type=Path, help="Pipeline or legacy results H5")
    ap.add_argument(
        "--overwrite",
        action="store_true",
        help="Rewrite from source even when feedback has no NaN",
    )
    ap.add_argument("--dry-run", action="store_true", help="Report counts only (no writes)")
    args = ap.parse_args(argv)

    db_path = Path(args.db_path)
    if not db_path.is_file():
        print(f"Not a file: {db_path}", file=sys.stderr)
        return 2

    if args.dry_run:
        import h5py

        from maze.core.h5_layout import read_feedback_table
        from maze.pipeline.db.feedback_align import (
            feedback_has_missing_source_values,
            read_primary_xy_table,
        )
        from maze.pipeline.db.trial_groups import list_trials
        from maze.pipeline.video_paths import resolve_input_h5_path

        stats = {
            "seen": 0,
            "would_backfill": 0,
            "no_nan": 0,
            "missing_xy": 0,
            "missing_feedback": 0,
            "missing_source": 0,
        }
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
                if not args.overwrite and not feedback_has_missing_source_values(fb):
                    stats["no_nan"] += 1
                    continue
                raw = g.attrs.get("input_h5_path")
                if raw is None:
                    stats["missing_source"] += 1
                    continue
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", errors="replace")
                resolved = resolve_input_h5_path(str(raw))
                if resolved is None or not resolved.is_file():
                    stats["missing_source"] += 1
                else:
                    stats["would_backfill"] += 1
        print(json.dumps(stats, indent=2))
        return 0

    stats = backfill_feedback_h5(db_path, overwrite=args.overwrite)
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
