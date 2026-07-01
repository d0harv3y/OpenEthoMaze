"""CLI: mine bout-level syllable n-grams for Option A grammar discovery."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import h5py
import numpy as np

from maze.kpms.apply_summary import preprocess_config_from_apply_summary, resolve_tracking_h5_path
from maze.kpms.behavior_ethogram.grammar_mine import mine_ngram_candidates, write_candidate_artifacts
from maze.kpms.behavior_ethogram.grammar_enrich import (
    enrich_candidates_with_bout_scalars,
    flag_candidates_for_overlay_review,
)
from maze.kpms.behavior_ethogram.bout_table_io import read_bout_table_csv
from maze.kpms.behavior_ethogram.grammar_matches import attach_example_matches_to_candidates
from maze.kpms.behavior_ethogram.paths import (
    bout_features_csv,
    grammar_candidates_csv,
    grammar_dir,
    stage_ii_dir,
)
from maze.kpms.frame_alignment import kpms_aligned_coordinates_and_indices, kpms_recording_key
from maze.kpms.manifest_subset import SubsetConfig, filter_manifests, load_manifests
from maze.kpms.preprocess import KpmsPreprocessConfig


def _load_syllables(results_h5: h5py.File, recording_key: str) -> np.ndarray | None:
    if recording_key not in results_h5:
        return None
    rec = results_h5[recording_key]
    if "syllable" not in rec:
        return None
    return np.asarray(rec["syllable"], dtype=np.int64)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Mine syllable-bout n-gram candidates (Option A).")
    ap.add_argument("--kpms-root", type=Path, required=True)
    ap.add_argument("--seed", type=str, required=True)
    ap.add_argument("--manifest-path", type=Path, required=True)
    ap.add_argument("--tracking-h5", type=Path, default=None)
    ap.add_argument("--min-count", type=int, default=5)
    ap.add_argument("--max-n", type=int, default=4)
    ap.add_argument("--output-csv", type=Path, default=None)
    ap.add_argument(
        "--bout-features-csv",
        type=Path,
        default=None,
        help="Bout feature table for scalar enrich (default: stage_ii/bout_features.csv)",
    )
    ap.add_argument("--no-enrich", action="store_true", help="Skip bout-scalar enrich and overlay flags")
    args = ap.parse_args(argv)

    kpms_root = Path(args.kpms_root)
    out_dir = grammar_dir(kpms_root, seed=args.seed)
    out_csv = args.output_csv or grammar_candidates_csv(out_dir)
    results_h5 = kpms_root / "anatomical" / f"seed_{args.seed}" / "results_apply.h5"
    if not results_h5.is_file():
        print(f"Missing results_apply.h5: {results_h5}", file=sys.stderr)
        return 1

    tracking_h5 = resolve_tracking_h5_path(kpms_root=kpms_root, tracking_h5=args.tracking_h5)
    if tracking_h5 is None:
        print("No tracking H5 found; pass --tracking-h5", file=sys.stderr)
        return 1

    pre_cfg = preprocess_config_from_apply_summary(results_h5) or KpmsPreprocessConfig()
    pre_cfg = KpmsPreprocessConfig(
        min_fragment_frames=pre_cfg.min_fragment_frames,
        jump_filter_cm=pre_cfg.jump_filter_cm,
        jump_filter_lookahead_frames=pre_cfg.jump_filter_lookahead_frames,
        px_per_cm=pre_cfg.px_per_cm,
        retain_all_frames=pre_cfg.retain_all_frames,
        db_path=Path(tracking_h5),
        pose_stream=pre_cfg.pose_stream,
    )

    cfg = SubsetConfig(manifest_csv=args.manifest_path, require_sleap=False)
    manifests = filter_manifests(load_manifests(cfg), cfg)
    trial_streams: dict[str, np.ndarray] = {}
    trial_source_frames: dict[str, np.ndarray] = {}

    with h5py.File(results_h5, "r") as results_h5_file:
        for manifest in manifests:
            trial_key = kpms_recording_key(manifest)
            z = _load_syllables(results_h5_file, trial_key)
            if z is None or len(z) == 0:
                continue
            aligned = kpms_aligned_coordinates_and_indices(manifest, pre_cfg)
            if aligned is None:
                continue
            _rk, _coord, src = aligned
            if len(z) != len(src):
                continue
            trial_streams[trial_key] = z
            trial_source_frames[trial_key] = np.asarray(src, dtype=np.int64)

    if not trial_streams:
        print("No aligned syllable streams found.", file=sys.stderr)
        return 1

    candidates = mine_ngram_candidates(
        trial_streams,
        min_count=args.min_count,
        max_n=args.max_n,
    )
    enriched = False
    if not args.no_enrich:
        bout_csv = args.bout_features_csv or bout_features_csv(stage_ii_dir(kpms_root))
        if bout_csv.is_file():
            bout_rows = read_bout_table_csv(bout_csv)
            candidates = enrich_candidates_with_bout_scalars(
                candidates, bout_rows, seed=args.seed, trial_keys=trial_streams.keys()
            )
            candidates = flag_candidates_for_overlay_review(candidates, bout_rows, seed=args.seed)
            candidates = attach_example_matches_to_candidates(
                candidates,
                bout_rows,
                trial_source_frames,
                seed=args.seed,
            )
            enriched = True
    fit_id = f"seed_{args.seed}"
    out_csv, exemplars_json = write_candidate_artifacts(out_dir, candidates, fit_id=fit_id)
    print(
        json.dumps(
            {
                "output_csv": str(out_csv),
                "output_exemplars_json": str(exemplars_json),
                "n_trials": len(trial_streams),
                "n_candidates": len(candidates),
                "min_count": args.min_count,
                "max_n": args.max_n,
                "enriched_from_bout_features": enriched,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
