"""CLI: scaffold ``behavior_token_labels.csv`` from bout AR-HMM token centroids."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from maze.kpms.behavior_ethogram.anchor_buckets import bout_token_rows_from_table
from maze.kpms.behavior_ethogram.behavior_token_labels import init_behavior_token_labels
from maze.kpms.behavior_ethogram.behavior_token_labels_contract import (
    BEHAVIOR_TOKEN_LABELS_SCHEMA,
)
from maze.kpms.behavior_ethogram.bout_table_io import read_bout_table_csv
from maze.kpms.behavior_ethogram.locomotion import (
    DEFAULT_LOCOMOTION_RULES,
    load_locomotion_rules_yaml,
    write_locomotion_rules_yaml,
)
from maze.kpms.behavior_ethogram.paths import (
    arhmm_fit_summary_json,
    behavior_token_labels_csv,
    bout_tokens_csv,
    locomotion_rules_yaml,
    resolve_stage_iii_dir,
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Scaffold behavior_token_labels.csv (per-token ethology curation table)."
    )
    ap.add_argument("--kpms-root", type=Path, required=True)
    ap.add_argument("--seed", type=str, required=True)
    ap.add_argument("--stage-iii-dir", type=Path, default=None)
    ap.add_argument("--tokens-csv", type=Path, default=None)
    ap.add_argument("--rules-yaml", type=Path, default=None)
    ap.add_argument("--out-csv", type=Path, default=None)
    ap.add_argument(
        "--min-token-bouts",
        type=int,
        default=1,
        help="Omit tokens with fewer bout rows than this (default 1)",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Replace existing curated fields instead of merging reference columns only",
    )
    args = ap.parse_args(argv)

    if args.stage_iii_dir is not None:
        stage_iii = Path(args.stage_iii_dir)
    else:
        stage_iii = resolve_stage_iii_dir(Path(args.kpms_root), seed=args.seed)

    in_csv = Path(args.tokens_csv) if args.tokens_csv else bout_tokens_csv(stage_iii)
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
    token_rows = bout_token_rows_from_table(table, seed=args.seed)
    if not token_rows:
        print(f"No bout token rows for seed {args.seed!r} in {in_csv}", file=sys.stderr)
        return 1

    out_csv = Path(args.out_csv) if args.out_csv else behavior_token_labels_csv(stage_iii)
    had_existing = out_csv.is_file() and not args.force
    written_path, rows = init_behavior_token_labels(
        token_rows=token_rows,
        rules_doc=rules_doc,
        out_csv=out_csv,
        min_token_bouts=int(args.min_token_bouts),
        force=bool(args.force),
    )

    fit_summary = arhmm_fit_summary_json(stage_iii)
    payload = {
        "schema": BEHAVIOR_TOKEN_LABELS_SCHEMA,
        "seed": str(args.seed),
        "output_csv": str(written_path.resolve()),
        "n_tokens": len(rows),
        "min_token_bouts": int(args.min_token_bouts),
        "merged_existing": had_existing,
        "bout_tokens_csv": str(in_csv.resolve()),
        "locomotion_rules_yaml": str(rules_path.resolve()),
        "arhmm_fit_summary_json": str(fit_summary.resolve()) if fit_summary.is_file() else None,
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
