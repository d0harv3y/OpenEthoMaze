"""CLI: export Option A syllable grammar to S0 Behavior labeling artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from maze.kpms.apply_summary import resolve_tracking_h5_path
from maze.kpms.behavior_ethogram.paths import grammar_dir, grammar_rules_json, producer_dir
from maze.kpms.behavior_ethogram.producer_option_a import export_option_a_labeling


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Export syllable grammar as Behavior labeling (S0).")
    ap.add_argument("--kpms-root", type=Path, required=True)
    ap.add_argument("--seed", type=str, required=True)
    ap.add_argument("--manifest-path", type=Path, required=True)
    ap.add_argument("--rules-json", type=Path, default=None)
    ap.add_argument("--tracking-h5", type=Path, default=None)
    ap.add_argument("--fit-id", type=str, default=None)
    ap.add_argument("--fps", type=float, default=30.0)
    args = ap.parse_args(argv)

    kpms_root = Path(args.kpms_root)
    fit_id = args.fit_id or f"seed_{args.seed}"
    rules = args.rules_json or grammar_rules_json(grammar_dir(kpms_root, seed=args.seed))
    if not rules.is_file():
        print(f"Missing grammar rules JSON: {rules}", file=sys.stderr)
        return 1

    tracking_h5 = resolve_tracking_h5_path(kpms_root=kpms_root, tracking_h5=args.tracking_h5)
    if tracking_h5 is None:
        print("No tracking H5 found; pass --tracking-h5", file=sys.stderr)
        return 1

    try:
        labeling = export_option_a_labeling(
            kpms_root=kpms_root,
            seed=args.seed,
            rules_json=rules,
            manifest_path=args.manifest_path,
            tracking_h5=tracking_h5,
            fit_id=fit_id,
            fps=args.fps,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    out = producer_dir(kpms_root, "syllable_grammar", fit_id)
    print(
        json.dumps(
            {
                "artifact_dir": str(out),
                "producer": labeling.producer,
                "fit_id": labeling.fit_id,
                "n_trials": len(labeling.trials),
                "n_behavior_ids": len(labeling.behavior_names),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
