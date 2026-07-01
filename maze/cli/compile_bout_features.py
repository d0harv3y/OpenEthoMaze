"""CLI: compile scalar bout feature table (Stage II step 1)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from maze.kpms.apply_summary import (
    preprocess_config_for_results_h5,
    resolve_tracking_h5_path,
)
from maze.kpms.frame_alignment import KpmsAlignmentCache
from maze.kpms.behavior_ethogram.bout_table_io import write_bout_table_csv
from maze.kpms.behavior_ethogram.compile import CompileBoutFeaturesConfig, compile_cohort_bout_features
from maze.kpms.behavior_ethogram.paths import (
    bout_features_csv,
    discover_compile_seeds,
    resolve_results_h5_path,
    stage_ii_dir,
)
from maze.kpms.io import write_json
from maze.kpms.manifest_subset import SubsetConfig, filter_manifests, load_manifests
from maze.kpms.preprocess import KpmsPreprocessConfig


def _resolve_seeds(
    *,
    seeds_raw: str | None,
    seed: str | None,
    kpms_root: Path,
    results_h5: Path | None,
) -> tuple[str, ...]:
    if seeds_raw:
        return tuple(s.strip() for s in seeds_raw.split(",") if s.strip())
    if seed:
        return (seed,)
    return discover_compile_seeds(kpms_root, results_h5=results_h5)


def _pre_cfg_for_seed(
    kpms_root: Path,
    seed: str,
    tracking_h5: Path | None,
    *,
    results_h5: Path | None,
) -> KpmsPreprocessConfig:
    resolved_results = resolve_results_h5_path(kpms_root, seed, results_h5=results_h5)
    pre_cfg = preprocess_config_for_results_h5(resolved_results, kpms_root=kpms_root) or KpmsPreprocessConfig()
    db = resolve_tracking_h5_path(
        kpms_root=kpms_root,
        tracking_h5=tracking_h5,
        preprocess_db_path=pre_cfg.db_path,
    )
    if db is None:
        return pre_cfg
    return KpmsPreprocessConfig(
        min_fragment_frames=pre_cfg.min_fragment_frames,
        jump_filter_cm=pre_cfg.jump_filter_cm,
        jump_filter_lookahead_frames=pre_cfg.jump_filter_lookahead_frames,
        px_per_cm=pre_cfg.px_per_cm,
        retain_all_frames=pre_cfg.retain_all_frames,
        db_path=db,
        pose_stream=pre_cfg.pose_stream,
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Compile anatomical bout scalar feature table.")
    ap.add_argument("--kpms-root", type=Path, required=True)
    ap.add_argument("--manifest-path", type=Path, required=True)
    ap.add_argument(
        "--legacy-db",
        type=Path,
        default=None,
        help="Optional legacy H5 for bout_primary_state (trial_state); not used for pose",
    )
    ap.add_argument(
        "--tracking-h5",
        type=Path,
        default=None,
        help=(
            "Cohort H5 with tracking/anatomical for pose (required if not at "
            "<kpms-root>/kpms_tracking.h5). Example: test2/kpms_tracking.h5"
        ),
    )
    ap.add_argument(
        "--results-h5",
        type=Path,
        default=None,
        help="kpMS syllable results H5 (default: anatomical/seed_*/results_apply.h5 or <kpms-root>/results.h5)",
    )
    ap.add_argument(
        "--seed",
        type=str,
        default=None,
        help="Seed id for row labeling when using cohort fit results.h5 (default: fit)",
    )
    ap.add_argument("--out-dir", type=Path, default=None, help="Default: <kpms-root>/behavior_ethogram/stage_ii")
    ap.add_argument("--seeds", type=str, default=None, help="Comma-separated seed ids (default: all on disk)")
    ap.add_argument("--include-heading-direction", action="store_true")
    ap.add_argument("--include-habituation", action="store_true")
    ap.add_argument(
        "--enrich-labels",
        action="store_true",
        help="Fill blank manifest fields from repo inputs/treatment_labels.csv (off by default)",
    )
    ap.add_argument("--fps", type=float, default=30.0)
    args = ap.parse_args(argv)

    kpms_root = Path(args.kpms_root)
    results_h5 = Path(args.results_h5) if args.results_h5 else None
    out_dir = Path(args.out_dir) if args.out_dir else stage_ii_dir(kpms_root)
    seeds = _resolve_seeds(
        seeds_raw=args.seeds,
        seed=args.seed,
        kpms_root=kpms_root,
        results_h5=results_h5,
    )
    if not seeds:
        print(
            "No kpMS results found (anatomical/seed_*/results_apply.h5 or results.h5). "
            "Pass --results-h5 or --seeds.",
            file=sys.stderr,
        )
        return 1

    tracking_h5 = resolve_tracking_h5_path(
        kpms_root=kpms_root,
        tracking_h5=args.tracking_h5,
    )
    if tracking_h5 is None:
        print(
            "No tracking H5 found for pose alignment. Pass --tracking-h5 "
            "(e.g. kpms_tracking.h5 with tracking/anatomical).",
            file=sys.stderr,
        )
        return 1

    cfg = SubsetConfig(
        manifest_csv=args.manifest_path,
        require_sleap=False,
        include_habituation=args.include_habituation,
        enrich_from_treatment_labels=args.enrich_labels,
        db_path=tracking_h5,
    )
    manifests = filter_manifests(load_manifests(cfg), cfg)
    if not manifests:
        print("No manifest rows after filtering.", file=sys.stderr)
        return 1

    compile_cfg = CompileBoutFeaturesConfig(include_heading_direction=args.include_heading_direction, fps=args.fps)

    alignment_cache = KpmsAlignmentCache()
    alignment_cache.preload(
        manifests,
        _pre_cfg_for_seed(kpms_root, seeds[0], tracking_h5, results_h5=results_h5),
    )

    all_rows: list[dict] = []
    for seed in seeds:
        pre_cfg = _pre_cfg_for_seed(kpms_root, seed, tracking_h5, results_h5=results_h5)
        all_rows.extend(
            compile_cohort_bout_features(
                manifests,
                kpms_root=kpms_root,
                seed=seed,
                cfg=compile_cfg,
                pre_cfg=pre_cfg,
                legacy_db=args.legacy_db,
                alignment_cache=alignment_cache,
                results_h5=results_h5,
            )
        )

    out_csv = bout_features_csv(out_dir)
    write_bout_table_csv(out_csv, all_rows)
    summary = {
        "n_rows": len(all_rows),
        "seeds": list(seeds),
        "include_heading_direction": compile_cfg.include_heading_direction,
        "enrich_labels": args.enrich_labels,
        "manifest_path": str(args.manifest_path),
        "tracking_h5": str(tracking_h5),
        "results_h5": str(results_h5) if results_h5 else str(resolve_results_h5_path(kpms_root, seeds[0])),
        "output_csv": str(out_csv),
    }
    write_json(out_dir / "compile_bout_features_summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
