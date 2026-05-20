"""
Emit a tab-separated data dictionary for ``trial_summary.csv`` (Excel-friendly).

Example::

    uv run maze-trial-summary-dictionary --db path/to/vast_results.h5

Writes ``exports/trial_summary_data_dictionary.tsv`` next to the HDF5 by default.

Task-specific rows: implement ``maze/pipeline/exports/trial_summary_dictionary_plugins.py``
(or ``trial_summary_dictionary_tasks.py``) and call
``register_trial_summary_dictionary_extension`` there; those modules are imported
automatically when present.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from maze.pipeline.exports.trial_summary_dictionary import write_trial_summary_dictionary_tsv
from maze.pipeline.paths import OUTPUT_H5


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, default=None, help="Results HDF5 path")
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output .tsv (default: <db parent>/exports/trial_summary_data_dictionary.tsv)",
    )
    p.add_argument(
        "--utf8-bom",
        action="store_true",
        help="UTF-8 BOM for opening directly in Excel on Windows",
    )
    args = p.parse_args()
    db_path = args.db or OUTPUT_H5
    if args.output is None:
        out = Path(db_path).parent / "exports" / "trial_summary_data_dictionary.tsv"
    else:
        out = args.output
    if not Path(db_path).exists():
        print(f"Warning: {db_path} not found; analysis column will use code defaults.", file=sys.stderr)
    path = write_trial_summary_dictionary_tsv(out, db_path=db_path, utf8_bom=args.utf8_bom)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
