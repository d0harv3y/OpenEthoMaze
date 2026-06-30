"""CLI: build is_moving anchor from legacy VAST H5."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from maze.kpms.behavior_ethogram.anchor_build import build_is_moving_anchor
from maze.kpms.behavior_ethogram.paths import anchor_dir
from maze.kpms.manifest_subset import SubsetConfig, filter_manifests, load_manifests


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build is_moving anchor artifact from legacy VAST H5.")
    ap.add_argument("--legacy-db", type=Path, required=True)
    ap.add_argument("--manifest-path", type=Path, required=True)
    ap.add_argument("--kpms-root", type=Path, required=True)
    ap.add_argument("--calibration-id", type=str, default="default")
    ap.add_argument("--out-dir", type=Path, default=None, help="Override anchor artifact dir")
    ap.add_argument("--include-habituation", action="store_true")
    ap.add_argument(
        "--enrich-labels",
        action="store_true",
        help="Fill blank manifest fields from repo inputs/treatment_labels.csv (off by default)",
    )
    args = ap.parse_args(argv)

    cfg = SubsetConfig(
        manifest_csv=args.manifest_path,
        require_sleap=False,
        include_habituation=args.include_habituation,
        enrich_from_treatment_labels=args.enrich_labels,
    )
    manifests = filter_manifests(load_manifests(cfg), cfg)
    if not manifests:
        print("No manifest rows after filter.", file=sys.stderr)
        return 1

    out = args.out_dir or anchor_dir(args.kpms_root, "is_moving", args.calibration_id)
    anchor = build_is_moving_anchor(
        args.legacy_db,
        manifests,
        out,
        calibration_id=args.calibration_id,
    )
    print(json.dumps({"artifact_dir": str(out), "n_trials": len(anchor.trials), "params": dict(anchor.params)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
