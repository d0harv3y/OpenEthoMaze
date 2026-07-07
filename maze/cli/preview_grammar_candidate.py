"""CLI: preview a grammar candidate pattern match as a clipped overlay MP4."""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path
from typing import Sequence

from maze.kpms.apply_summary import preprocess_config_for_results_h5, resolve_tracking_h5_path
from maze.kpms.behavior_ethogram.grammar_exemplars import load_pattern_exemplars
from maze.kpms.behavior_ethogram.grammar_matches import (
    DEFAULT_PREVIEW_PADDING_S,
    PatternMatch,
    clip_frames_for_match,
    resolve_manifest_for_trial_key,
)
from maze.kpms.behavior_ethogram.paths import (
    grammar_candidates_csv,
    grammar_dir,
    resolve_grammar_results_h5,
)
from maze.kpms.frame_alignment import kpms_recording_key
from maze.pipeline.db.trial_key import TrialKey
from maze.pipeline.io.file_discovery import TrialManifest
from maze.pipeline.video_paths import set_runtime_video_path_prefix_remaps
from maze.pipeline.viz.overlay_cli import is_unified_overlay_available, run_unified_overlay_from_args
from maze.pipeline.viz.unified_overlay import UnifiedOverlayConfig
from maze.kpms.preprocess import KpmsPreprocessConfig


def _parse_video_prefix_remaps(values: list[str] | None) -> list[tuple[str, str]]:
    if not values:
        return []
    if len(values) % 2 != 0:
        raise ValueError("--video-prefix-remap requires pairs: SOURCE TARGET [SOURCE TARGET ...]")
    return [(values[i], values[i + 1]) for i in range(0, len(values), 2)]


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


def _parse_int_list(raw: str) -> list[int]:
    out: list[int] = []
    for part in str(raw).split(","):
        text = part.strip()
        if text:
            out.append(int(text))
    return out


def resolve_match_indices(
    *,
    match_index: str | None,
    random_matches: int | None,
    n_available: int,
    rng: random.Random,
) -> list[int]:
    """Choose which example_matches entries to render."""
    if n_available <= 0:
        raise ValueError("no exemplar matches available")
    if random_matches is not None:
        if random_matches < 1:
            raise ValueError("--random-matches must be >= 1")
        if match_index is not None and str(match_index).strip():
            raise ValueError("pass --match-index or --random-matches, not both")
        k = min(int(random_matches), n_available)
        return sorted(rng.sample(range(n_available), k=k))
    if match_index is not None and str(match_index).strip():
        indices = _parse_int_list(str(match_index))
        if not indices:
            raise ValueError("--match-index must list at least one integer")
        return indices
    return [0]


def _validate_match_indices(indices: Sequence[int], n_available: int) -> None:
    for idx in indices:
        if idx < 0 or idx >= n_available:
            raise IndexError(f"match_index {idx} out of range (0..{n_available - 1})")


def _trial_fps(pipeline_h5: Path, manifest: TrialManifest) -> float:
    from maze.pipeline.db import read_trial_settings

    key = TrialKey.from_manifest(manifest)
    _settings, fps, _timing = read_trial_settings(pipeline_h5, key)
    return float(fps) if fps and fps > 0 else 30.0


def _output_mp4_path(
    out_path: Path,
    *,
    row: dict[str, str],
    match_index: int,
    multi: bool,
) -> Path:
    if out_path.suffix.lower() == ".mp4":
        if multi:
            raise ValueError("multiple matches require --out to be a directory, not a .mp4 path")
        out_file = out_path
        out_file.parent.mkdir(parents=True, exist_ok=True)
        return out_file
    out_path.mkdir(parents=True, exist_ok=True)
    pat_slug = json.loads(row["pattern_json"])
    slug = "_".join(str(x) for x in pat_slug)
    return out_path / f"grammar_preview_{slug}_m{match_index}.mp4"


def _render_match_preview(
    *,
    match: PatternMatch,
    match_index: int,
    row: dict[str, str],
    manifest: TrialManifest,
    out_file: Path,
    args: argparse.Namespace,
    pipeline_h5: Path,
    results_h5: Path,
    tracking_h5: Path,
    pre_cfg: KpmsPreprocessConfig,
) -> dict:
    fps = _trial_fps(pipeline_h5, manifest)
    clip_start, clip_end = clip_frames_for_match(match, fps=fps, padding_s=args.padding_s)

    ns = argparse.Namespace(
        manifest_csv=Path(args.manifest_path),
        pipeline_h5=pipeline_h5,
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

    cfg_holder: list[UnifiedOverlayConfig] = []

    def _clip_cfg(cfg: UnifiedOverlayConfig) -> None:
        cfg.clip_source_start_frame = clip_start
        cfg.clip_source_end_frame = clip_end
        cfg.include_pre_trial_frames = False

    written = run_unified_overlay_from_args(ns, extend_cfg=_clip_cfg, cfg_out=cfg_holder)
    provenance = cfg_holder[0].data_provenance if cfg_holder else None
    payload: dict = {
        "output_mp4": str(written),
        "pattern_json": row.get("pattern_json"),
        "trial_key": match.trial_key,
        "match_index": match_index,
        "clip_source_start_frame": clip_start,
        "clip_source_end_frame": clip_end,
        "kpms_recording_key": kpms_recording_key(manifest),
        "pipeline_h5": str(pipeline_h5.resolve()),
        "tracking_h5": str(Path(tracking_h5).resolve()),
    }
    if provenance is not None:
        payload["data_sources"] = provenance.to_dict()
    return payload


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Render clipped overlay MP4(s) for grammar candidate pattern match(es).")
    ap.add_argument("--kpms-root", type=Path, required=True)
    ap.add_argument("--seed", type=str, required=True)
    ap.add_argument("--manifest-path", type=Path, required=True)
    ap.add_argument("--pipeline-h5", type=Path, required=True, help="Legacy / pipeline tracking HDF5")
    ap.add_argument("--tracking-h5", type=Path, default=None)
    ap.add_argument(
        "--results-h5",
        type=Path,
        default=None,
        help="kpMS syllable results H5 (default: anatomical/seed_*/results_apply.h5 or <kpms-root>/results.h5)",
    )
    ap.add_argument("--candidates-csv", type=Path, default=None)
    ap.add_argument("--row-index", type=int, default=None, help="0-based row in candidate_sequences.csv")
    ap.add_argument("--pattern-json", type=str, default=None, help='Exact pattern_json cell, e.g. "[3, 7, 7]"')
    ap.add_argument(
        "--match-index",
        type=str,
        default=None,
        help="example_matches index or comma-separated list (default: 0)",
    )
    ap.add_argument(
        "--random-matches",
        type=int,
        default=None,
        metavar="N",
        help="Preview N randomly chosen distinct match indices (use --match-seed to reproduce)",
    )
    ap.add_argument(
        "--match-seed",
        type=int,
        default=None,
        help="RNG seed for --random-matches only",
    )
    ap.add_argument("--padding-s", type=float, default=DEFAULT_PREVIEW_PADDING_S)
    ap.add_argument("--out", type=Path, required=True, help="Output MP4 path or directory")
    ap.add_argument("--no-ethogram", action="store_true")
    ap.add_argument("--no-syllable-tray", action="store_true")
    ap.add_argument(
        "--video-prefix-remap",
        dest="video_prefix_remaps",
        nargs="+",
        default=None,
        metavar="SOURCE TARGET",
        help="Prefix remap pairs for stored video_path (e.g. C:\\...\\vibration maze E:\\videos\\vibration maze).",
    )
    args = ap.parse_args(argv)

    if not is_unified_overlay_available():
        print("OpenCV required; install gui/kpms extras.", file=sys.stderr)
        return 1

    try:
        remaps = _parse_video_prefix_remaps(args.video_prefix_remaps)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if remaps:
        set_runtime_video_path_prefix_remaps(remaps)
        print("Video path prefix remaps:", file=sys.stderr)
        for source, target in remaps:
            print(f"  {source} -> {target}", file=sys.stderr)

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
            "No exemplar matches for this pattern — re-run maze-mine-syllable-grammar-candidates " "with bout_features.csv present (writes candidate_exemplars.json).",
            file=sys.stderr,
        )
        return 1

    rng = random.Random(args.match_seed)
    try:
        match_indices = resolve_match_indices(
            match_index=args.match_index,
            random_matches=args.random_matches,
            n_available=len(matches),
            rng=rng,
        )
        _validate_match_indices(match_indices, len(matches))
    except (ValueError, IndexError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    kpms_root = Path(args.kpms_root)
    results_h5_arg = Path(args.results_h5) if args.results_h5 else None
    try:
        results_h5 = resolve_grammar_results_h5(kpms_root, args.seed, results_h5=results_h5_arg)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    tracking_h5 = resolve_tracking_h5_path(kpms_root=kpms_root, tracking_h5=args.tracking_h5)
    if tracking_h5 is None:
        print("No tracking H5 found; pass --tracking-h5", file=sys.stderr)
        return 1

    from dataclasses import replace

    pre_cfg = preprocess_config_for_results_h5(results_h5, kpms_root=kpms_root)
    if pre_cfg is None:
        pre_cfg = KpmsPreprocessConfig()
    pre_cfg = replace(pre_cfg, db_path=Path(tracking_h5))

    pipeline_h5 = Path(args.pipeline_h5)
    multi = len(match_indices) > 1
    renders: list[dict] = []

    for match_index in match_indices:
        match = matches[match_index]
        try:
            manifest = resolve_manifest_for_trial_key(args.manifest_path, match.trial_key)
        except KeyError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        try:
            out_file = _output_mp4_path(
                Path(args.out),
                row=row,
                match_index=match_index,
                multi=multi,
            )
            payload = _render_match_preview(
                match=match,
                match_index=match_index,
                row=row,
                manifest=manifest,
                out_file=out_file,
                args=args,
                pipeline_h5=pipeline_h5,
                results_h5=results_h5,
                tracking_h5=tracking_h5,
                pre_cfg=pre_cfg,
            )
        except Exception as exc:
            print(str(exc), file=sys.stderr)
            return 1
        renders.append(payload)

    if len(renders) == 1:
        print(json.dumps(renders[0], indent=2))
    else:
        print(
            json.dumps(
                {
                    "pattern_json": row.get("pattern_json"),
                    "match_indices": match_indices,
                    "n_renders": len(renders),
                    "renders": renders,
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
