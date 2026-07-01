"""CLI: build grammar_rules.json from curated candidate_sequences.csv."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from maze.kpms.behavior_ethogram.grammar_rules import (
    rules_from_auto_candidates,
    rules_from_curated_candidates,
    write_grammar_rules_json,
)
from maze.kpms.behavior_ethogram.paths import grammar_candidates_csv, grammar_dir, grammar_rules_json


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build grammar_rules.json from curated candidates CSV.")
    ap.add_argument("--kpms-root", type=Path, required=True)
    ap.add_argument("--seed", type=str, required=True)
    ap.add_argument("--candidates-csv", type=Path, default=None)
    ap.add_argument("--fit-id", type=str, default=None)
    ap.add_argument("--output-json", type=Path, default=None)
    ap.add_argument(
        "--force",
        action="store_true",
        help="Allow build when must_review_overlay rows lack reviewed_at",
    )
    ap.add_argument(
        "--auto-buckets",
        action="store_true",
        help="Skip curation: synthetic behavior_name from pattern + speed anchor buckets",
    )
    ap.add_argument(
        "--still-max-mps",
        type=float,
        default=0.06,
        help="mean_speed_mps <= this → still (auto-buckets only)",
    )
    ap.add_argument(
        "--moving-min-mps",
        type=float,
        default=0.14,
        help="mean_speed_mps >= this → moving (auto-buckets only)",
    )
    args = ap.parse_args(argv)

    kpms_root = Path(args.kpms_root)
    fit_id = args.fit_id or f"seed_{args.seed}"
    gdir = grammar_dir(kpms_root, seed=args.seed)
    candidates = args.candidates_csv or grammar_candidates_csv(gdir)
    if not candidates.is_file():
        print(f"Missing candidates CSV: {candidates}", file=sys.stderr)
        return 1
    out = args.output_json or grammar_rules_json(gdir)

    try:
        if args.auto_buckets:
            doc = rules_from_auto_candidates(
                candidates,
                fit_id=fit_id,
                still_max_mps=args.still_max_mps,
                moving_min_mps=args.moving_min_mps,
            )
        else:
            doc = rules_from_curated_candidates(candidates, fit_id=fit_id, force=args.force)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    write_grammar_rules_json(out, doc)
    print(
        json.dumps(
            {
                "output_json": str(out),
                "fit_id": doc.fit_id,
                "n_rules": len(doc.rules),
                "behavior_names": list(doc.behavior_names()),
                "behavior_anchor_buckets": dict(doc.behavior_anchor_buckets),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
