"""CLI: export Option D bout AR-HMM tokens to S0 Behavior labeling artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from maze.kpms.apply_summary import resolve_tracking_h5_path
from maze.kpms.behavior_ethogram.paths import bout_tokens_csv, locomotion_rules_yaml, producer_dir, stage_iii_dir
from maze.kpms.behavior_ethogram.producer_option_d import export_option_d_labeling


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Export bout AR-HMM tokens as Behavior labeling (S0).")
    ap.add_argument("--kpms-root", type=Path, required=True)
    ap.add_argument("--seed", type=str, required=True)
    ap.add_argument("--manifest-path", type=Path, required=True)
    ap.add_argument("--tokens-csv", type=Path, default=None)
    ap.add_argument("--tracking-h5", type=Path, default=None)
    ap.add_argument("--fit-id", type=str, default=None)
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument(
        "--locomotion-rules-yaml",
        type=Path,
        default=None,
        help="Token tier rules for behavior_anchor_buckets (default: stage_iii/locomotion_rules.yaml)",
    )
    args = ap.parse_args(argv)

    kpms_root = Path(args.kpms_root)
    fit_id = args.fit_id or f"seed_{args.seed}"
    tokens = args.tokens_csv or bout_tokens_csv(stage_iii_dir(kpms_root, seed=args.seed))
    if not tokens.is_file():
        tokens = bout_tokens_csv(stage_iii_dir(kpms_root))
    if not tokens.is_file():
        print(f"Missing bout tokens CSV: {tokens}", file=sys.stderr)
        return 1

    tracking_h5 = resolve_tracking_h5_path(kpms_root=kpms_root, tracking_h5=args.tracking_h5)
    if tracking_h5 is None:
        print("No tracking H5 found; pass --tracking-h5", file=sys.stderr)
        return 1

    loco_rules = args.locomotion_rules_yaml
    if loco_rules is None:
        candidate = locomotion_rules_yaml(stage_iii_dir(kpms_root, seed=args.seed))
        loco_rules = candidate if candidate.is_file() else None

    try:
        labeling = export_option_d_labeling(
            kpms_root=kpms_root,
            seed=args.seed,
            tokens_csv=tokens,
            manifest_path=args.manifest_path,
            tracking_h5=tracking_h5,
            fit_id=fit_id,
            fps=args.fps,
            locomotion_rules_path=loco_rules,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    out = producer_dir(kpms_root, "bout_arhmm", fit_id)
    print(
        json.dumps(
            {
                "artifact_dir": str(out),
                "producer": labeling.producer,
                "fit_id": labeling.fit_id,
                "n_trials": len(labeling.trials),
                "n_behavior_ids": len(labeling.behavior_names),
                "behavior_anchor_buckets": {
                    int(k): v for k, v in labeling.behavior_anchor_buckets.items()
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
