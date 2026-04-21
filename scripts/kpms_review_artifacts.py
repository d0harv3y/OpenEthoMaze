"""
Generate kpMS taxonomy review artifacts: grid movies, trajectory plots/GIFs, optional similarity CSV.

Uses the same coordinate pipeline as fit/apply (:func:`maze.kpms.preprocess.build_kpms_inputs`).

Example::

    uv run python scripts/kpms_review_artifacts.py ^
      --model-dir "D:/path/to/moseq_project/model_run" ^
      --results-h5 "D:/path/to/results.h5" ^
      --manifest-csv path/to/selected_trials.csv

Requires ``uv sync --extra kpms``.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from maze.kpms.preprocess import KpmsPreprocessConfig
from maze.kpms.review_artifacts import (
    align_coordinates_results,
    build_coordinates_for_review,
    recording_keys_with_syllables,
    run_grid_movies,
    run_similarity_matrix_csv,
    run_trajectory_plots,
    video_paths_for_results,
    write_review_readme,
)
from maze.pipeline.io.file_discovery import load_manifest_csv


def _pre_cfg_from_fit_summary(model_dir: Path) -> KpmsPreprocessConfig | None:
    p = model_dir / "fit_summary.json"
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    raw = data.get("preprocess_config")
    if not isinstance(raw, dict):
        return None
    try:
        return KpmsPreprocessConfig(
            min_fragment_frames=int(raw.get("min_fragment_frames", 4)),
            jump_filter_cm=float(raw.get("jump_filter_cm", 15.0)),
            jump_filter_lookahead_frames=int(raw.get("jump_filter_lookahead_frames", 3)),
            px_per_cm=float(raw.get("px_per_cm", 2.42)),
            retain_all_frames=bool(raw.get("retain_all_frames", False)),
        )
    except (TypeError, ValueError):
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description="kpMS grid movies, trajectory plots, similarity CSV.")
    ap.add_argument("--model-dir", type=Path, required=True, help="kpMS model directory (project)")
    ap.add_argument("--model-name", type=str, default=None, help="Checkpoint folder name (optional)")
    ap.add_argument(
        "--results-h5",
        type=Path,
        required=True,
        help="results.h5 or results_apply.h5 to visualize",
    )
    ap.add_argument(
        "--manifest-csv",
        type=Path,
        default=None,
        help="Trial manifest (default: <model-dir>/selected_trials.csv)",
    )
    ap.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Review output root (default: <model-dir>/review)",
    )
    ap.add_argument("--fps", type=float, default=30.0, help="FPS for time windows")
    ap.add_argument(
        "--retain-all-sleap-frames",
        action="store_true",
        help="KpmsPreprocessConfig(retain_all_frames=True) for native full-length results",
    )
    ap.add_argument(
        "--ignore-fit-summary-preprocess",
        action="store_true",
        help="Do not load KpmsPreprocessConfig from fit_summary.json",
    )
    ap.add_argument("--no-grid", action="store_true", help="Skip grid movies")
    ap.add_argument("--no-trajectory", action="store_true", help="Skip trajectory plots")
    ap.add_argument("--no-similarity", action="store_true", help="Skip syllable similarity CSV")
    ap.add_argument(
        "--keypoints-only",
        action="store_true",
        help="Grid movies without video (pose tiles only); use when video paths missing",
    )
    ap.add_argument("--traj-no-gifs", action="store_true", help="Disable trajectory GIFs (PNG only)")
    ap.add_argument(
        "--density-sample",
        action="store_true",
        help="Use density sampling for typical trajectories (slower)",
    )
    ap.add_argument("--min-frequency", type=float, default=0.005, help="Min syllable frequency")
    ap.add_argument("--min-duration", type=int, default=3, help="Min instance duration (frames)")
    ap.add_argument("--similarity-metric", type=str, default="cosine", help="pdist metric")
    args = ap.parse_args()

    model_dir = Path(args.model_dir).resolve()
    results_h5 = Path(args.results_h5)
    if not results_h5.is_file():
        print(f"Missing results: {results_h5}", file=sys.stderr)
        return 1

    manifest_csv = Path(args.manifest_csv) if args.manifest_csv else model_dir / "selected_trials.csv"
    if not manifest_csv.is_file():
        print(f"Missing manifest: {manifest_csv}", file=sys.stderr)
        return 1

    manifests = load_manifest_csv(manifest_csv)
    pre_cfg = KpmsPreprocessConfig()
    if not args.ignore_fit_summary_preprocess:
        loaded = _pre_cfg_from_fit_summary(model_dir)
        if loaded is not None:
            pre_cfg = loaded
    if args.retain_all_sleap_frames:
        pre_cfg = replace(pre_cfg, retain_all_frames=True)

    import keypoint_moseq as kpms

    results_all = kpms.load_hdf5(str(results_h5))
    coordinates, confidences, skipped = build_coordinates_for_review(manifests, pre_cfg)
    coordinates, _conf, results = align_coordinates_results(coordinates, confidences, results_all)
    if not results:
        print(
            "No overlap between manifest coordinates and results syllable keys. "
            f"Skipped preprocess: {len(skipped)}",
            file=sys.stderr,
        )
        return 1

    keys = recording_keys_with_syllables(results)
    vidmap = video_paths_for_results(manifests, keys)
    use_keypoints_only = bool(args.keypoints_only) or len(vidmap) == 0
    if len(vidmap) == 0 and not use_keypoints_only:
        print("No valid video paths; use --keypoints-only for pose-only grid movies.", file=sys.stderr)
        return 1

    out_root = Path(args.output_dir) if args.output_dir else model_dir / "review"
    out_root.mkdir(parents=True, exist_ok=True)
    grid_dir = out_root / "grid_movies"
    traj_dir = out_root / "trajectory_plots"
    sim_csv = out_root / "syllable_similarity_matrix.csv"

    project_dir = str(model_dir)
    model_name = args.model_name
    sampling = {"n_neighbors": 50}
    if args.density_sample:
        sampling["mode"] = "density"

    if not args.no_grid:
        run_grid_movies(
            coordinates,
            results,
            project_dir=project_dir,
            model_name=model_name,
            output_dir=grid_dir,
            video_paths=None if use_keypoints_only else vidmap,
            keypoints_only=use_keypoints_only,
            fps=float(args.fps),
            min_frequency=float(args.min_frequency),
            min_duration=int(args.min_duration),
            sampling_options=sampling,
        )

    if not args.no_trajectory:
        run_trajectory_plots(
            coordinates,
            results,
            project_dir=project_dir,
            model_name=model_name,
            output_dir=traj_dir,
            fps=float(args.fps),
            min_frequency=float(args.min_frequency),
            min_duration=int(args.min_duration),
            save_gifs=not bool(args.traj_no_gifs),
            save_mp4s=False,
            interactive=False,
            density_sample=bool(args.density_sample),
            sampling_options=sampling,
        )

    sim_path: Path | None = None
    if not args.no_similarity:
        sim_path = run_similarity_matrix_csv(
            coordinates,
            results,
            sim_csv,
            metric=str(args.similarity_metric),
            density_sample=bool(args.density_sample),
            sampling_options=sampling,
        )

    readme = write_review_readme(
        out_root,
        grid_dir=None if args.no_grid else grid_dir,
        traj_dir=None if args.no_trajectory else traj_dir,
        similarity_csv=sim_path,
        results_h5=results_h5,
        n_recordings=len(results),
    )
    print(f"Wrote review index: {readme}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
