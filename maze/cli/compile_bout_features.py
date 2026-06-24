"""CLI: compile scalar bout feature table (Stage II step 1)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from maze.kpms.behavior_ethogram.compile import CompileBoutFeaturesConfig, compile_cohort_bout_features
from maze.kpms.behavior_ethogram.paths import bout_features_csv, discover_anatomical_seeds, stage_ii_dir
from maze.kpms.behavior_ethogram.bout_table_io import write_bout_table_csv
from maze.kpms.io import write_json
from maze.kpms.manifest_subset import SubsetConfig, filter_manifests, load_manifests
from maze.kpms.preprocess import KpmsPreprocessConfig


def _parse_seeds(raw: str | None, kpms_root: Path) -> tuple[str, ...]:
    if raw:
        return tuple(s.strip() for s in raw.split(",") if s.strip())
    return discover_anatomical_seeds(kpms_root)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Compile anatomical bout scalar feature table.")
    ap.add_argument("--kpms-root", type=Path, required=True)
    ap.add_argument("--manifest-path", type=Path, required=True)
    ap.add_argument("--legacy-db", type=Path, default=None, help="Optional legacy H5 for trial_state")
    ap.add_argument("--out-dir", type=Path, default=None, help="Default: <kpms-root>/behavior_ethogram/stage_ii")
    ap.add_argument("--seeds", type=str, default=None, help="Comma-separated seed ids (default: all on disk)")
    ap.add_argument("--include-heading-direction", action="store_true")
    ap.add_argument("--fps", type=float, default=30.0)
    args = ap.parse_args(argv)

    kpms_root = Path(args.kpms_root)
    out_dir = Path(args.out_dir) if args.out_dir else stage_ii_dir(kpms_root)
    seeds = _parse_seeds(args.seeds, kpms_root)
    if not seeds:
        print("No anatomical seeds with results_apply.h5 found.", file=sys.stderr)
        return 1

    cfg = SubsetConfig(manifest_csv=args.manifest_path, require_sleap=True)
    manifests = filter_manifests(load_manifests(cfg), cfg)
    compile_cfg = CompileBoutFeaturesConfig(include_heading_direction=args.include_heading_direction, fps=args.fps)
    pre_cfg = KpmsPreprocessConfig()

    all_rows: list[dict] = []
    for seed in seeds:
        all_rows.extend(
            compile_cohort_bout_features(
                manifests,
                kpms_root=kpms_root,
                seed=seed,
                cfg=compile_cfg,
                pre_cfg=pre_cfg,
                legacy_db=args.legacy_db,
            )
        )

    out_csv = bout_features_csv(out_dir)
    write_bout_table_csv(out_csv, all_rows)
    summary = {
        "n_rows": len(all_rows),
        "seeds": list(seeds),
        "include_heading_direction": compile_cfg.include_heading_direction,
        "manifest_path": str(args.manifest_path),
        "output_csv": str(out_csv),
    }
    write_json(out_dir / "compile_bout_features_summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
