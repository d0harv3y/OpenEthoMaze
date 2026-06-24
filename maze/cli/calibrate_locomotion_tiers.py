"""CLI: locomotion tier calibration from behavior-token centroids."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from maze.kpms.behavior_ethogram.bout_table_io import read_bout_table_csv
from maze.kpms.behavior_ethogram.locomotion import (
    DEFAULT_LOCOMOTION_RULES,
    BoutTokenRow,
    assign_bout_tiers,
    compute_token_centroids,
    load_locomotion_rules_yaml,
    tier_by_token_from_centroids,
    write_locomotion_rules_yaml,
    write_token_tiers_csv,
)
from maze.kpms.behavior_ethogram.paths import (
    bout_tokens_csv,
    locomotion_rules_yaml,
    stage_iii_dir,
    token_tiers_csv,
)
from maze.kpms.io import write_json


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Calibrate locomotion tiers from behavior-token centroids.")
    ap.add_argument("--kpms-root", type=Path, default=None)
    ap.add_argument("--stage-iii-dir", type=Path, default=None)
    ap.add_argument("--input-csv", type=Path, default=None)
    ap.add_argument("--rules-yaml", type=Path, default=None, help="Optional edited rules YAML")
    args = ap.parse_args(argv)

    if args.stage_iii_dir is not None:
        stage_iii = Path(args.stage_iii_dir)
    elif args.kpms_root is not None:
        stage_iii = stage_iii_dir(args.kpms_root)
    else:
        print("Provide --stage-iii-dir or --kpms-root.", file=sys.stderr)
        return 2

    in_csv = Path(args.input_csv) if args.input_csv else bout_tokens_csv(stage_iii)
    if not in_csv.is_file():
        print(f"Missing bout tokens CSV: {in_csv}", file=sys.stderr)
        return 1

    rules_path = Path(args.rules_yaml) if args.rules_yaml else locomotion_rules_yaml(stage_iii)
    if rules_path.is_file():
        rules_doc = load_locomotion_rules_yaml(rules_path)
    else:
        rules_doc = DEFAULT_LOCOMOTION_RULES
        write_locomotion_rules_yaml(rules_path, rules_doc)

    table = read_bout_table_csv(in_csv)
    token_rows: list[BoutTokenRow] = []
    for row in table:
        token_raw = str(row.get("behavior_token", "")).strip()
        if not token_raw:
            continue
        token_rows.append(
            BoutTokenRow(
                seed=str(row["seed"]),
                trial_key=str(row["trial_key"]),
                bout_index=int(row["bout_index"]),
                behavior_token=int(token_raw),
                bout_mean_speed_mps=float(row["bout_mean_speed_mps"]),
                bout_mean_abs_dheading=float(row["bout_mean_abs_dheading"]),
                ambiguous=bool(int(row.get("ambiguous", "0"))),
                tier="",
            )
        )

    centroids = compute_token_centroids(token_rows)
    tier_by_token = tier_by_token_from_centroids(centroids, rules_doc)
    tiered = assign_bout_tiers(token_rows, tier_by_token)
    out_csv = token_tiers_csv(stage_iii)
    write_token_tiers_csv(out_csv, tiered, centroids)

    summary = {
        "n_bouts": len(tiered),
        "n_tokens": len(centroids),
        "rules_yaml": str(rules_path),
        "output_csv": str(out_csv),
        "tier_by_token": {str(k): v for k, v in tier_by_token.items()},
    }
    write_json(stage_iii / "locomotion_calibration_summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
