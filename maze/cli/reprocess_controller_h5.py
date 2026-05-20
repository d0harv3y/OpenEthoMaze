"""
Backfill maze pipeline analysis for trials stored in a controller HDF5 database.

Use when ``Run analysis after each trial`` was off, or to re-run after code changes.

Example (PowerShell, from the ORM repo root)::

    uv run maze-reprocess-controller-h5 path\\to\\controller.h5
    uv run maze-reprocess-controller-h5 path\\to\\controller.h5 --animal-id 1 --session S01 --trial T01 --no-qc
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from maze.controller.acquisition.post_trial_analysis import reprocess_controller_h5


def main() -> int:

    p = argparse.ArgumentParser(
        description=(
            "Run process_trial for trials in a controller H5 (same db_path as acquisition)."
        )
    )
    p.add_argument(
        "db_path",
        type=Path,
        help="Path to the controller .h5 file",
    )
    p.add_argument("--animal-id", default=None, help="Only this animal group")
    p.add_argument("--session", default=None, help="Only this session")
    p.add_argument("--trial", default=None, help="Only this trial key")
    p.add_argument(
        "--no-qc",
        action="store_true",
        help="Skip QC visualizations (faster batch)",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Less console output from the pipeline",
    )
    args = p.parse_args()
    db_path = args.db_path.expanduser().resolve()
    if not db_path.is_file():
        print(f"Not a file: {db_path}", file=sys.stderr)
        return 2
    stats = reprocess_controller_h5(
        db_path,
        animal_id=args.animal_id,
        session=args.session,
        trial=args.trial,
        generate_qc=not args.no_qc,
        quiet=args.quiet,
    )
    print(f"Done: ok={stats['ok']} fail={stats['fail']} skipped={stats['skipped']}")
    return 0 if stats["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
