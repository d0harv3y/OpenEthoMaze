"""CLI: compute stimulus-conditioned MI per animal and group tests."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from maze.kpms.behavior_ethogram.paths import (
    group_mi_excess_tests_csv,
    group_mi_sliced_tests_csv,
    group_mi_tests_csv,
    group_mi_when_tests_csv,
    mi_per_animal_csv,
    mi_per_trial_csv,
    mi_trial_animal_summaries_csv,
    stimulus_bin_edges_json,
    stimulus_bout_features_csv,
    stimulus_mi_dir,
)
from maze.kpms.behavior_ethogram.stimulus_join import read_stimulus_bout_table_csv
from maze.kpms.behavior_ethogram.stimulus_mi import (
    animal_mi_to_row,
    compute_animal_mi,
    compute_global_bin_edges,
    compute_per_trial_mi,
    compute_trial_animal_summaries,
    load_bin_edges_json,
    run_group_mi_excess_tests,
    run_group_mi_tests,
    run_group_mi_tests_sliced,
    run_group_mi_when_tests,
    trial_animal_summary_to_row,
    write_bin_edges_json,
    write_group_mi_excess_tests_csv,
    write_group_mi_tests_csv,
    write_group_mi_sliced_tests_csv,
    write_group_mi_when_tests_csv,
    write_mi_per_animal_csv,
    write_mi_per_trial_csv,
    write_mi_trial_animal_summaries_csv,
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
    ap.add_argument("--n-perm", type=int, default=1000, help="Circular null permutations (animal + trial)")
    ap.add_argument("--seed", type=int, default=0, help="RNG seed for shuffle nulls")
    ap.add_argument(
        "--bin-edges-json",
        type=Path,
        default=None,
        help="Reuse bin edges sidecar (default: compute from run-phase cohort)",
    )
    ap.add_argument(
        "--per-trial",
        action="store_true",
        help="Emit per-trial MI and animal trajectory summaries (additive to pooled path)",
    )
    ap.add_argument(
        "--trial-nulls",
        action="store_true",
        help="Circular nulls per trial (uses --n-perm); requires --per-trial",
    )
    ap.add_argument(
        "--min-run-bouts",
        type=int,
        default=None,
        help="Optional gate: skip trials with cum_run_bouts below this threshold",
    )
    ap.add_argument(
        "--min-h-stim",
        type=float,
        default=None,
        help="Optional gate: skip trials with H_stim below this threshold (bits)",
    )
    ap.add_argument(
        "--sliced-tests",
        action="store_true",
        help="Emit stratified one/two-hold simple-effect tests with BH-FDR (requires --per-trial)",
    )
    args = ap.parse_args(argv)

    if args.trial_nulls and not args.per_trial:
        print("--trial-nulls requires --per-trial", file=sys.stderr)
        return 2
    if args.sliced_tests and not args.per_trial:
        print("--sliced-tests requires --per-trial", file=sys.stderr)
        return 2

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
    animal_rows = [animal_mi_to_row(r) for r in animal_results]
    group_rows = run_group_mi_tests(animal_rows)
    group_csv = group_mi_tests_csv(out_dir)
    write_group_mi_tests_csv(group_csv, group_rows)
    group_excess_rows = run_group_mi_excess_tests(animal_rows)
    group_excess_csv = group_mi_excess_tests_csv(out_dir)
    write_group_mi_excess_tests_csv(group_excess_csv, group_excess_rows)

    iti_flags = [r for r in animal_results if r.iti_control_flag]
    summary: dict[str, object] = {
        "n_animals": len({r.animal_id for r in animal_results}),
        "n_mi_rows": len(animal_results),
        "n_group_tests": len(group_rows),
        "n_group_excess_tests": len(group_excess_rows),
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
        "group_mi_excess_tests_csv": str(group_excess_csv),
        "per_trial": args.per_trial,
        "confound_note": (
            "Stimulus duty is a deterministic function of distance-to-exit; MI cannot "
            "separate response to signal from response to goal proximity."
        ),
    }

    if args.per_trial:
        trial_rng = np.random.default_rng(args.seed + 1)
        trial_results = compute_per_trial_mi(
            rows,
            edges=edges,
            trial_nulls=args.trial_nulls,
            n_perm=args.n_perm,
            min_run_bouts=args.min_run_bouts,
            min_h_stim=args.min_h_stim,
            rng=trial_rng,
        )
        if not trial_results:
            print("No per-trial MI results.", file=sys.stderr)
            return 1

        trial_csv = mi_per_trial_csv(out_dir)
        write_mi_per_trial_csv(trial_csv, trial_results)
        animal_summaries = compute_trial_animal_summaries(trial_results, trial_nulls=args.trial_nulls)
        summaries_csv = mi_trial_animal_summaries_csv(out_dir)
        write_mi_trial_animal_summaries_csv(summaries_csv, animal_summaries)
        when_rows = run_group_mi_when_tests(
            [trial_animal_summary_to_row(s) for s in animal_summaries],
            trial_nulls=args.trial_nulls,
        )
        when_csv = group_mi_when_tests_csv(out_dir)
        write_group_mi_when_tests_csv(when_csv, when_rows)

        summary["n_trial_mi_rows"] = len(trial_results)
        summary["n_trial_animal_summaries"] = len(animal_summaries)
        summary["n_when_group_tests"] = len(when_rows)
        summary["trial_nulls"] = args.trial_nulls
        summary["mi_per_trial_csv"] = str(trial_csv)
        summary["mi_trial_animal_summaries_csv"] = str(summaries_csv)
        summary["group_mi_when_tests_csv"] = str(when_csv)

        if args.sliced_tests:
            sliced_rows = run_group_mi_tests_sliced(
                [animal_mi_to_row(r) for r in animal_results],
                [trial_animal_summary_to_row(s) for s in animal_summaries],
                trial_nulls=args.trial_nulls,
            )
            sliced_csv = group_mi_sliced_tests_csv(out_dir)
            write_group_mi_sliced_tests_csv(sliced_csv, sliced_rows)
            summary["n_sliced_group_tests"] = len(sliced_rows)
            summary["group_mi_sliced_tests_csv"] = str(sliced_csv)

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
