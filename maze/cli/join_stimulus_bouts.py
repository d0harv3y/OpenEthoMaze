"""CLI: join per-frame VAST stimulus onto kpMS syllable bouts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from maze.kpms.apply_summary import resolve_tracking_h5_path
from maze.kpms.behavior_ethogram.bout_table_io import read_bout_table_csv
from maze.kpms.behavior_ethogram.paths import (
    bout_features_csv,
    stage_ii_dir,
    stimulus_bout_features_csv,
    stimulus_mi_dir,
)
from maze.kpms.behavior_ethogram.stimulus_join import (
    StimulusJoinFilterConfig,
    filter_bout_rows,
    join_stimulus_to_bouts,
    verify_trial_stimulus_h5,
    write_stimulus_bout_table_csv,
)
from maze.kpms.frame_alignment import KpmsAlignmentCache, kpms_recording_key
from maze.kpms.io import write_json
from maze.kpms.manifest_subset import SubsetConfig, filter_manifests, load_manifests
from maze.kpms.preprocess import KpmsPreprocessConfig
from maze.pipeline.db.trial_key import TrialKey
from maze.pipeline.io.file_discovery import TrialManifest


def _pre_cfg(kpms_root: Path, tracking_h5: Path) -> KpmsPreprocessConfig:
    pre_cfg = KpmsPreprocessConfig(db_path=tracking_h5)
    return pre_cfg


def _parse_csv_list(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    return tuple(s.strip() for s in raw.split(",") if s.strip())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Join VAST stimulus scalars onto bout feature rows.")
    ap.add_argument("--kpms-root", type=Path, required=True)
    ap.add_argument("--manifest-path", type=Path, required=True)
    ap.add_argument(
        "--bout-features-csv",
        type=Path,
        default=None,
        help="Input bout table (default: stage_ii/bout_features.csv)",
    )
    ap.add_argument(
        "--tracking-h5",
        type=Path,
        default=None,
        help="Cohort trial H5 with feedback/xy (default: <kpms-root>/kpms_tracking.h5)",
    )
    ap.add_argument(
        "--stimulus-h5",
        type=Path,
        default=None,
        help="Override H5 for stimulus read (default: per-trial canonical resolution)",
    )
    ap.add_argument("--out-dir", type=Path, default=None, help="Default: behavior_ethogram/stimulus_mi")
    ap.add_argument(
        "--experiment",
        type=str,
        default="VASTcont,VASTalt",
        help="Comma-separated experiment filter (default: VASTcont,VASTalt)",
    )
    ap.add_argument(
        "--drop-strain",
        type=str,
        default="?,",
        help="Comma-separated strain values to drop (default: ? and blank)",
    )
    ap.add_argument("--drop-blank-sex", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--tx", type=str, default=None, help="Optional comma-separated tx filter")
    ap.add_argument(
        "--verify-h5",
        action="store_true",
        help="Verify stimulus H5 paths for one trial per experiment then exit",
    )
    args = ap.parse_args(argv)

    kpms_root = Path(args.kpms_root)
    out_dir = Path(args.out_dir) if args.out_dir else stimulus_mi_dir(kpms_root)
    tracking_h5 = resolve_tracking_h5_path(kpms_root=kpms_root, tracking_h5=args.tracking_h5)
    if tracking_h5 is None:
        print("No tracking H5 found. Pass --tracking-h5.", file=sys.stderr)
        return 1

    cfg = SubsetConfig(
        manifest_csv=args.manifest_path,
        require_sleap=False,
        db_path=tracking_h5,
    )
    manifests = filter_manifests(load_manifests(cfg), cfg)
    if not manifests:
        print("No manifest rows after filtering.", file=sys.stderr)
        return 1

    if args.verify_h5:
        by_experiment: dict[str, TrialManifest] = {}
        for manifest in manifests:
            exp = str(manifest.experiment or "").strip()
            if exp and exp not in by_experiment:
                by_experiment[exp] = manifest
        reports = []
        for exp in sorted(by_experiment):
            manifest = by_experiment[exp]
            trial_key = TrialKey.from_manifest(manifest)
            report = verify_trial_stimulus_h5(tracking_h5, trial_key)
            reports.append(
                {
                    "experiment": exp,
                    "trial_key": kpms_recording_key(manifest),
                    "ok": report.ok,
                    "h5_path": report.h5_path,
                    "has_feedback_table": report.has_feedback_table,
                    "has_motor_fb": report.has_motor_fb,
                    "has_xy_dist": report.has_xy_dist,
                    "n_feedback_frames": report.n_feedback_frames,
                    "n_xy_frames": report.n_xy_frames,
                    "motor_fb_finite_frac": report.motor_fb_finite_frac,
                    "dist_finite_frac": report.dist_finite_frac,
                }
            )
        print(json.dumps(reports, indent=2))
        return 0 if all(r["ok"] for r in reports) else 1

    bout_csv = args.bout_features_csv or bout_features_csv(stage_ii_dir(kpms_root))
    if not bout_csv.is_file():
        print(f"Missing bout features CSV: {bout_csv}", file=sys.stderr)
        return 1

    join_filter = StimulusJoinFilterConfig(
        experiments=_parse_csv_list(args.experiment) or ("VASTcont", "VASTalt"),
        drop_strains=_parse_csv_list(args.drop_strain) or ("?", ""),
        drop_blank_sex=bool(args.drop_blank_sex),
        tx_values=_parse_csv_list(args.tx) if args.tx else None,
    )
    bout_rows = filter_bout_rows(read_bout_table_csv(bout_csv), join_filter)
    if not bout_rows:
        print("No bout rows after stimulus cohort filters.", file=sys.stderr)
        return 1

    pre_cfg = _pre_cfg(kpms_root, tracking_h5)
    alignment_cache = KpmsAlignmentCache()
    alignment_cache.preload(manifests, pre_cfg)

    enriched, join_stats = join_stimulus_to_bouts(
        bout_rows,
        manifests,
        pre_cfg=pre_cfg,
        alignment_cache=alignment_cache,
        stimulus_h5=args.stimulus_h5,
    )
    if not enriched:
        print("No bout rows enriched with stimulus (check H5 paths / alignment).", file=sys.stderr)
        return 1

    out_csv = stimulus_bout_features_csv(out_dir)
    write_stimulus_bout_table_csv(out_csv, enriched)
    summary = {
        "n_input_rows": join_stats.n_input_rows,
        "n_output_rows": join_stats.n_output_rows,
        "n_trials_seen": join_stats.n_trials_seen,
        "n_trials_joined": join_stats.n_trials_joined,
        "n_trials_skipped_no_manifest": join_stats.n_trials_skipped_no_manifest,
        "n_trials_skipped_no_alignment": join_stats.n_trials_skipped_no_alignment,
        "n_trials_skipped_no_stimulus": join_stats.n_trials_skipped_no_stimulus,
        "experiments": list(join_filter.experiments),
        "tracking_h5": str(tracking_h5),
        "bout_features_csv": str(bout_csv),
        "output_csv": str(out_csv),
        "confound_note": (
            "Stimulus duty is a deterministic function of distance-to-exit; MI cannot "
            "separate response to signal from response to goal proximity."
        ),
    }
    write_json(out_dir / "join_stimulus_bouts_summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
