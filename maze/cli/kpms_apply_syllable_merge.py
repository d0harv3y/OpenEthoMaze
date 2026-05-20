"""
Apply user-defined syllable merge groups to a kpMS ``results*.h5`` (keypoint-moseq API).

Merge spec (YAML or JSON)::

    groups:
      - [1, 3, 5]
      - [2, 4]

Example::

    uv run maze-kpms-apply-syllable-merge ^
      --results-h5 results_apply.h5 ^
      --merge-spec syllable_groups.yaml ^
      --output-h5 results_merged.h5

Requires ``uv sync --extra kpms``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from maze.kpms.syllable_merge import (
    apply_merge_to_results,
    load_merge_spec,
    save_merged_results_h5,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Apply syllable merge groups to kpMS results HDF5.")
    ap.add_argument("--results-h5", type=Path, required=True, help="Input results.h5")
    ap.add_argument(
        "--merge-spec",
        type=Path,
        required=True,
        help="YAML or JSON file with key 'groups' (list of lists of syllable ids)",
    )
    ap.add_argument(
        "--output-h5",
        type=Path,
        default=None,
        help="Output path (default: <input-dir>/results_merged.h5)",
    )
    args = ap.parse_args()

    src = Path(args.results_h5)
    if not src.is_file():
        print(f"Missing {src}", file=sys.stderr)
        return 1
    spec = load_merge_spec(Path(args.merge_spec))

    import keypoint_moseq as kpms

    results = kpms.load_hdf5(str(src))
    new_results, mapping = apply_merge_to_results(results, spec)
    out = Path(args.output_h5) if args.output_h5 else src.parent / "results_merged.h5"
    save_merged_results_h5(out, new_results, source_h5=src, spec=spec, mapping=mapping)
    print(f"Wrote {out} (mapping keys: {len(mapping)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
