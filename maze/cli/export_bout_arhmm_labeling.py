"""CLI: export Option D bout AR-HMM tokens to S0 Behavior labeling artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from maze.kpms.apply_summary import resolve_tracking_h5_path
from maze.kpms.behavior_ethogram.paths import bout_tokens_csv, producer_dir, stage_iii_dir
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

    try:
        labeling = export_option_d_labeling(
            kpms_root=kpms_root,
            seed=args.seed,
            tokens_csv=tokens,
            manifest_path=args.manifest_path,
            tracking_h5=tracking_h5,
            fit_id=fit_id,
            fps=args.fps,
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
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
