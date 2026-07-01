"""CLI: preview a grammar candidate pattern match as a clipped overlay MP4."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from maze.kpms.apply_summary import preprocess_config_from_apply_summary, resolve_tracking_h5_path
from maze.kpms.behavior_ethogram.grammar_exemplars import load_pattern_exemplars
from maze.kpms.behavior_ethogram.grammar_matches import (
    DEFAULT_PREVIEW_PADDING_S,
    clip_frames_for_match,
    resolve_manifest_for_trial_key,
)
from maze.kpms.behavior_ethogram.paths import grammar_candidates_csv, grammar_dir
from maze.kpms.frame_alignment import kpms_recording_key
from maze.pipeline.db.trial_key import TrialKey
from maze.pipeline.viz.overlay_cli import is_unified_overlay_available, run_unified_overlay_from_args
from maze.pipeline.viz.unified_overlay import UnifiedOverlayConfig


def _load_candidate_row(candidates_csv: Path, *, row_index: int | None, pattern_json: str | None) -> dict[str, str]:
    with candidates_csv.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError(f"no rows in {candidates_csv}")
    if row_index is not None:
        if row_index < 0 or row_index >= len(rows):
            raise IndexError(f"row_index {row_index} out of range (0..{len(rows) - 1})")
        return rows[row_index]
    if pattern_json is not None:
        target = pattern_json.strip()
        for row in rows:
            if str(row.get("pattern_json", "")).strip() == target:
                return row
        raise KeyError(f"pattern_json not found in {candidates_csv}: {target}")
    raise ValueError("pass --row-index or --pattern-json")


def _trial_fps(pipeline_h5: Path, manifest) -> float:
    from maze.pipeline.db import open_db, read_trial_settings

    key = TrialKey.from_manifest(manifest)
    with open_db(pipeline_h5) as db:
        _settings, fps, _timing = read_trial_settings(db, key)
    return float(fps) if fps and fps > 0 else 30.0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Render a clipped overlay MP4 for one grammar candidate pattern match."
    )
    ap.add_argument("--kpms-root", type=Path, required=True)
    ap.add_argument("--seed", type=str, required=True)
    ap.add_argument("--manifest-path", type=Path, required=True)
    ap.add_argument("--pipeline-h5", type=Path, required=True, help="Legacy / pipeline tracking HDF5")
    ap.add_argument("--tracking-h5", type=Path, default=None)
    ap.add_argument("--candidates-csv", type=Path, default=None)
    ap.add_argument("--row-index", type=int, default=None, help="0-based row in candidate_sequences.csv")
    ap.add_argument("--pattern-json", type=str, default=None, help='Exact pattern_json cell, e.g. "[3, 7, 7]"')
    ap.add_argument("--match-index", type=int, default=0, help="Which example_matches_json entry to preview")
    ap.add_argument("--padding-s", type=float, default=DEFAULT_PREVIEW_PADDING_S)
    ap.add_argument("--out", type=Path, required=True, help="Output MP4 path or directory")
    ap.add_argument("--no-ethogram", action="store_true")
    ap.add_argument("--no-syllable-tray", action="store_true")
    args = ap.parse_args(argv)

    if not is_unified_overlay_available():
        print("OpenCV required; install gui/kpms extras.", file=sys.stderr)
        return 1

    gdir = grammar_dir(args.kpms_root, seed=args.seed)
    candidates_csv = args.candidates_csv or grammar_candidates_csv(gdir)
    if not candidates_csv.is_file():
        print(f"Missing candidates CSV: {candidates_csv}", file=sys.stderr)
        return 1

    try:
        row = _load_candidate_row(
            candidates_csv,
            row_index=args.row_index,
            pattern_json=args.pattern_json,
        )
    except (ValueError, KeyError, IndexError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    pattern_json = str(row.get("pattern_json", "")).strip()
    exemplars = load_pattern_exemplars(gdir, pattern_json, candidates_row=row)
    matches = exemplars.example_matches
    if not matches:
        print(
            "No exemplar matches for this pattern — re-run maze-mine-syllable-grammar-candidates "
            "with bout_features.csv present (writes candidate_exemplars.json).",
            file=sys.stderr,
        )
        return 1
    if args.match_index < 0 or args.match_index >= len(matches):
        print(f"match_index {args.match_index} out of range (0..{len(matches) - 1})", file=sys.stderr)
        return 1
    match = matches[args.match_index]

    try:
        manifest = resolve_manifest_for_trial_key(args.manifest_path, match.trial_key)
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    kpms_root = Path(args.kpms_root)
    results_h5 = kpms_root / "anatomical" / f"seed_{args.seed}" / "results_apply.h5"
    if not results_h5.is_file():
        print(f"Missing results_apply.h5: {results_h5}", file=sys.stderr)
        return 1

    tracking_h5 = resolve_tracking_h5_path(kpms_root=kpms_root, tracking_h5=args.tracking_h5)
    if tracking_h5 is None:
        print("No tracking H5 found; pass --tracking-h5", file=sys.stderr)
        return 1

    from dataclasses import replace

    pre_cfg = preprocess_config_from_apply_summary(results_h5)
    if pre_cfg is None:
        from maze.kpms.preprocess import KpmsPreprocessConfig

        pre_cfg = KpmsPreprocessConfig()
    pre_cfg = replace(pre_cfg, db_path=Path(tracking_h5))

    fps = _trial_fps(Path(args.pipeline_h5), manifest)
    clip_start, clip_end = clip_frames_for_match(match, fps=fps, padding_s=args.padding_s)

    out_path = Path(args.out)
    if out_path.suffix.lower() != ".mp4":
        out_path.mkdir(parents=True, exist_ok=True)
        pat_slug = json.loads(row["pattern_json"])
        slug = "_".join(str(x) for x in pat_slug)
        out_file = out_path / f"grammar_preview_{slug}_m{args.match_index}.mp4"
    else:
        out_file = out_path
        out_file.parent.mkdir(parents=True, exist_ok=True)

    ns = argparse.Namespace(
        manifest_csv=Path(args.manifest_path),
        pipeline_h5=Path(args.pipeline_h5),
        animal_id=str(manifest.animal_id),
        session=str(manifest.session),
        trial=str(manifest.trial),
        out=out_file,
        kpms_h5=results_h5,
        kpms_training_exemplars=None,
        max_seconds=None,
        contrast=2.0,
        brightness=5.0,
        kpms_px_per_cm=pre_cfg.px_per_cm,
        analysis_only=True,
        history_frames=None,
        no_history_fade=False,
        history_fade_floor=None,
        history_fade_gamma=None,
        no_ethogram=bool(args.no_ethogram),
        no_syllable_tray=bool(args.no_syllable_tray),
        tray_width=None,
        vertical_exemplar_heading=False,
        bout_center_exemplar_tray=True,
        tray_projection=None,
        exemplar_min_frequency=None,
        exemplar_min_duration=None,
        exemplar_neighbors=None,
        exemplar_density_sample=False,
        exemplar_timesteps=None,
        exemplar_arena_coords=False,
        opacity_trajectory=None,
        opacity_trail=None,
        opacity_skeleton=None,
        opacity_arena=None,
        opacity_ethogram=None,
        opacity_tray=None,
        no_skeleton=False,
        no_hud=False,
        no_circular_motor_hud=False,
    )

    def _clip_cfg(cfg: UnifiedOverlayConfig) -> None:
        cfg.clip_source_start_frame = clip_start
        cfg.clip_source_end_frame = clip_end
        cfg.include_pre_trial_frames = False

    try:
        written = run_unified_overlay_from_args(ns, extend_cfg=_clip_cfg)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "output_mp4": str(written),
                "pattern_json": row.get("pattern_json"),
                "trial_key": match.trial_key,
                "match_index": args.match_index,
                "clip_source_start_frame": clip_start,
                "clip_source_end_frame": clip_end,
                "kpms_recording_key": kpms_recording_key(manifest),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
