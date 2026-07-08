"""CLI: compute stimulus-conditioned MI per animal and group tests."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from maze.kpms.behavior_ethogram.paths import (
    group_mi_tests_csv,
    mi_per_animal_csv,
    stimulus_bin_edges_json,
    stimulus_bout_features_csv,
    stimulus_mi_dir,
)
from maze.kpms.behavior_ethogram.stimulus_join import read_stimulus_bout_table_csv
from maze.kpms.behavior_ethogram.stimulus_mi import (
    animal_mi_to_row,
    compute_animal_mi,
    compute_global_bin_edges,
    load_bin_edges_json,
    run_group_mi_tests,
    write_bin_edges_json,
    write_group_mi_tests_csv,
    write_mi_per_animal_csv,
)
from maze.kpms.io import write_json


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Compute stimulus-conditioned MI per animal.")
    ap.add_argument("--kpms-root", type=Path, required=True)
    ap.add_argument(
        "--stimulus-bout-csv",
        type=Path,
        default=None,
        help="Joined bout table (default: behavior_ethogram/stimulus_mi/stimulus_bout_features.csv)",
    )
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--n-bins", type=int, default=4)
    ap.add_argument("--n-perm", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=0, help="RNG seed for shuffle nulls")
    ap.add_argument(
        "--bin-edges-json",
        type=Path,
        default=None,
        help="Reuse bin edges sidecar (default: compute from run-phase cohort)",
    )
    args = ap.parse_args(argv)

    kpms_root = Path(args.kpms_root)
    out_dir = Path(args.out_dir) if args.out_dir else stimulus_mi_dir(kpms_root)
    in_csv = args.stimulus_bout_csv or stimulus_bout_features_csv(out_dir)
    if not in_csv.is_file():
        print(f"Missing stimulus bout CSV: {in_csv}", file=sys.stderr)
        return 1

    rows = read_stimulus_bout_table_csv(in_csv)
    if not rows:
        print("Empty stimulus bout table.", file=sys.stderr)
        return 1

    edges_path = args.bin_edges_json or stimulus_bin_edges_json(out_dir)
    if edges_path.is_file():
        edges = load_bin_edges_json(edges_path)
    else:
        edges = compute_global_bin_edges(rows, n_bins=args.n_bins)
        write_bin_edges_json(edges_path, edges)

    rng = np.random.default_rng(args.seed)
    animal_results = compute_animal_mi(rows, edges=edges, n_perm=args.n_perm, rng=rng)
    if not animal_results:
        print("No per-animal MI results.", file=sys.stderr)
        return 1

    mi_csv = mi_per_animal_csv(out_dir)
    write_mi_per_animal_csv(mi_csv, animal_results)
    group_rows = run_group_mi_tests([animal_mi_to_row(r) for r in animal_results])
    group_csv = group_mi_tests_csv(out_dir)
    write_group_mi_tests_csv(group_csv, group_rows)

    iti_flags = [r for r in animal_results if r.iti_control_flag]
    summary = {
        "n_animals": len({r.animal_id for r in animal_results}),
        "n_mi_rows": len(animal_results),
        "n_group_tests": len(group_rows),
        "n_iti_control_flags": len(iti_flags),
        "iti_flagged": [
            {
                "animal_id": r.animal_id,
                "stim_var": r.stim_var,
                "mi_type": r.mi_type,
                "mi_mm": r.mi_mm,
                "null_circ_p": r.null_circ_p,
            }
            for r in iti_flags
        ],
        "bin_edges_json": str(edges_path),
        "mi_per_animal_csv": str(mi_csv),
        "group_mi_tests_csv": str(group_csv),
        "confound_note": (
            "Stimulus duty is a deterministic function of distance-to-exit; MI cannot "
            "separate response to signal from response to goal proximity."
        ),
    }
    write_json(out_dir / "compute_stimulus_mi_summary.json", summary)
    print(json.dumps(summary, indent=2))
    if iti_flags:
        print(
            f"WARNING: {len(iti_flags)} iti negative-control flag(s) — MI exceeds circular null.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
