"""CLI: cohort HDBSCAN on bout feature table (Stage II step 2)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from maze.kpms.behavior_ethogram.bout_table_io import dict_to_bout_scalar_features, read_bout_table_csv, write_bout_table_csv
from maze.kpms.behavior_ethogram.cluster import cluster_bout_features_hdbscan
from maze.kpms.behavior_ethogram.paths import bout_features_clustered_csv, bout_features_csv, hdbscan_summary_json, stage_ii_dir
from maze.kpms.io import write_json


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="HDBSCAN cluster bout scalar features (cohort QC).")
    ap.add_argument("--stage-ii-dir", type=Path, default=None)
    ap.add_argument("--kpms-root", type=Path, default=None)
    ap.add_argument("--input-csv", type=Path, default=None)
    ap.add_argument("--include-heading-direction", action="store_true")
    ap.add_argument("--min-cluster-size", type=int, default=15)
    ap.add_argument("--min-samples", type=int, default=5)
    args = ap.parse_args(argv)

    if args.stage_ii_dir is not None:
        stage_ii = Path(args.stage_ii_dir)
    elif args.kpms_root is not None:
        stage_ii = stage_ii_dir(args.kpms_root)
    else:
        print("Provide --stage-ii-dir or --kpms-root.", file=sys.stderr)
        return 2

    in_csv = Path(args.input_csv) if args.input_csv else bout_features_csv(stage_ii)
    if not in_csv.is_file():
        print(f"Missing input CSV: {in_csv}", file=sys.stderr)
        return 1

    table = read_bout_table_csv(in_csv)
    feats = [dict_to_bout_scalar_features(row) for row in table]
    if not feats:
        print("Empty bout table.", file=sys.stderr)
        return 1

    result = cluster_bout_features_hdbscan(
        feats,
        include_heading_direction=args.include_heading_direction,
        min_cluster_size=args.min_cluster_size,
        min_samples=args.min_samples,
    )

    out_rows: list[dict] = []
    for row, label in zip(table, result.labels.tolist(), strict=True):
        out = dict(row)
        out["cluster_id"] = int(label)
        out_rows.append(out)

    out_csv = bout_features_clustered_csv(stage_ii)
    write_bout_table_csv(out_csv, out_rows)
    summary = {
        "n_bouts": result.n_bouts,
        "n_clusters": result.n_clusters,
        "n_noise": result.n_noise,
        "feature_names": list(result.feature_names),
        "input_csv": str(in_csv),
        "output_csv": str(out_csv),
    }
    write_json(hdbscan_summary_json(stage_ii), summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
