"""CLI: render one exemplar-grid MP4 per grammar candidate (pattern_len >= N).

For each selected candidate the tool renders every stored exemplar match
(up to ``DEFAULT_MAX_EXAMPLE_MATCHES``) as a clipped overlay, tiles them into a
single grid MP4, and back-fills a relative ``preview_grid_path`` into
``candidate_sequences.csv`` so curators can jump straight to the review movie.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
from dataclasses import replace
from pathlib import Path

from maze.kpms.apply_summary import (
    preprocess_config_for_results_h5,
    resolve_tracking_h5_path,
)
from maze.kpms.behavior_ethogram.grammar_contract import CANDIDATE_SEQUENCE_FIELDS
from maze.kpms.behavior_ethogram.grammar_exemplars import load_pattern_exemplars
from maze.kpms.behavior_ethogram.grammar_matches import (
    DEFAULT_PREVIEW_PADDING_S,
    PatternMatch,
    resolve_manifest_for_trial_key,
)
from maze.kpms.behavior_ethogram.grammar_mine import read_candidate_sequences_csv
from maze.kpms.behavior_ethogram.paths import (
    grammar_candidates_csv,
    grammar_dir,
    grammar_grid_movies_dir,
    resolve_grammar_results_h5,
)
from maze.kpms.behavior_ethogram.token_grid_compose import compose_grid_video
from maze.kpms.behavior_ethogram.token_grid_render import (
    manifest_has_video,
    render_overlay_clip_for_match,
    render_pose_only_clip_for_match,
)
from maze.kpms.preprocess import KpmsPreprocessConfig
from maze.pipeline.video_paths import set_runtime_video_path_prefix_remaps
from maze.pipeline.viz.overlay_cli import is_unified_overlay_available


def _parse_video_prefix_remaps(values: list[str] | None) -> list[tuple[str, str]]:
    if not values:
        return []
    if len(values) % 2 != 0:
        raise ValueError("--video-prefix-remap requires pairs: SOURCE TARGET [SOURCE TARGET ...]")
    return [(values[i], values[i + 1]) for i in range(0, len(values), 2)]


def _pattern_slug(pattern_json: str) -> str:
    return "_".join(str(x) for x in json.loads(pattern_json))


def _select_rows(
    rows: list[dict[str, str]],
    *,
    min_pattern_len: int,
    limit: int,
    pattern_json: str | None,
    row_index: int | None,
) -> list[int]:
    """Return indices into ``rows`` to render, honouring explicit overrides."""
    if row_index is not None:
        if row_index < 0 or row_index >= len(rows):
            raise IndexError(f"row_index {row_index} out of range (0..{len(rows) - 1})")
        return [row_index]
    if pattern_json is not None:
        target = pattern_json.strip()
        matches = [i for i, r in enumerate(rows) if str(r.get("pattern_json", "")).strip() == target]
        if not matches:
            raise KeyError(f"pattern_json not found: {target}")
        return matches
    eligible = [i for i, r in enumerate(rows) if int(r.get("pattern_len") or 0) >= min_pattern_len]
    eligible.sort(key=lambda i: int(rows[i].get("count") or 0), reverse=True)
    if limit > 0:
        eligible = eligible[:limit]
    return eligible


def _render_match_clip(
    match: PatternMatch,
    *,
    label: str,
    manifest_path: Path,
    pipeline_h5: Path,
    results_h5: Path,
    tracking_h5: Path,
    out_path: Path,
    padding_s: float,
    keypoints_only: bool,
    no_ethogram: bool,
    no_syllable_tray: bool,
) -> Path:
    manifest = resolve_manifest_for_trial_key(manifest_path, match.trial_key)
    if keypoints_only or not manifest_has_video(manifest):
        return render_pose_only_clip_for_match(
            match,
            behavior_token=0,
            manifest=manifest,
            pipeline_h5=pipeline_h5,
            results_h5=results_h5,
            tracking_h5=tracking_h5,
            out_path=out_path,
            padding_s=padding_s,
            label=label,
        )
    return render_overlay_clip_for_match(
        match,
        behavior_token=0,
        manifest=manifest,
        manifest_path=manifest_path,
        pipeline_h5=pipeline_h5,
        results_h5=results_h5,
        tracking_h5=tracking_h5,
        out_path=out_path,
        padding_s=padding_s,
        no_ethogram=no_ethogram,
        no_syllable_tray=no_syllable_tray,
        label=label,
    )


def _render_candidate_grid(
    row: dict[str, str],
    *,
    gdir: Path,
    manifest_path: Path,
    pipeline_h5: Path,
    results_h5: Path,
    tracking_h5: Path,
    out_dir: Path,
    max_matches: int,
    padding_s: float,
    keypoints_only: bool,
    no_ethogram: bool,
    no_syllable_tray: bool,
    keep_clips: bool,
) -> tuple[Path, int]:
    """Render + tile exemplar clips for one candidate; return (grid_path, n_clips)."""
    pattern_json = str(row.get("pattern_json", "")).strip()
    slug = _pattern_slug(pattern_json)
    exemplars = load_pattern_exemplars(gdir, pattern_json, candidates_row=row)
    matches = exemplars.example_matches[:max_matches]
    if not matches:
        raise ValueError("no exemplar matches (re-run mine with bout_features.csv present)")

    grid_path = out_dir / f"grammar_grid_{slug}.mp4"
    clip_stage = out_dir / "clips" / slug
    clip_stage.mkdir(parents=True, exist_ok=True)
    clip_paths: list[Path] = []
    labels: list[str] = []
    try:
        for idx, match in enumerate(matches):
            clip_dest = clip_stage / f"exemplar_{idx:02d}.mp4"
            written = _render_match_clip(
                match,
                label=f"{pattern_json} | {match.trial_key}",
                manifest_path=manifest_path,
                pipeline_h5=pipeline_h5,
                results_h5=results_h5,
                tracking_h5=tracking_h5,
                out_path=clip_dest,
                padding_s=padding_s,
                keypoints_only=keypoints_only,
                no_ethogram=no_ethogram,
                no_syllable_tray=no_syllable_tray,
            )
            if not written.is_file():
                raise RuntimeError(f"clip not written: {written}")
            clip_paths.append(written)
            labels.append(match.trial_key)
        compose_grid_video(clip_paths, grid_path, cell_labels=labels)
    finally:
        if not keep_clips and clip_stage.is_dir():
            shutil.rmtree(clip_stage, ignore_errors=True)
    return grid_path, len(clip_paths)


def _write_back_preview_paths(candidates_csv: Path, rows: list[dict[str, str]]) -> None:
    with candidates_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(CANDIDATE_SEQUENCE_FIELDS))
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in CANDIDATE_SEQUENCE_FIELDS})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Render one exemplar-grid MP4 per grammar candidate and back-fill preview_grid_path.")
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
    ap.add_argument("--min-pattern-len", type=int, default=3, help="Only render candidates with pattern_len >= N")
    ap.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Render only the top-N eligible candidates by count (0 = no cap)",
    )
    ap.add_argument("--row-index", type=int, default=None, help="Render a single 0-based CSV row (overrides filters)")
    ap.add_argument("--pattern-json", type=str, default=None, help="Render a single exact pattern_json (overrides filters)")
    ap.add_argument("--max-matches", type=int, default=None, help="Cap exemplar clips per grid (default: all stored)")
    ap.add_argument("--padding-s", type=float, default=DEFAULT_PREVIEW_PADDING_S)
    ap.add_argument("--out", type=Path, default=None, help="Output dir (default: grammar/seed_<seed>/grid_movies)")
    ap.add_argument("--keypoints-only", action="store_true")
    ap.add_argument("--no-ethogram", action="store_true")
    ap.add_argument("--no-syllable-tray", action="store_true")
    ap.add_argument(
        "--keep-clips",
        action="store_true",
        help="Keep per-exemplar clips under grid_movies/clips/ (default: delete after compose)",
    )
    ap.add_argument(
        "--no-write-back",
        action="store_true",
        help="Do not update preview_grid_path in candidate_sequences.csv",
    )
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

    kpms_root = Path(args.kpms_root)
    gdir = grammar_dir(kpms_root, seed=args.seed)
    candidates_csv = args.candidates_csv or grammar_candidates_csv(gdir)
    if not candidates_csv.is_file():
        print(f"Missing candidates CSV: {candidates_csv}", file=sys.stderr)
        return 1

    rows = read_candidate_sequences_csv(candidates_csv)
    if not rows:
        print(f"No rows in {candidates_csv}", file=sys.stderr)
        return 1

    try:
        target_indices = _select_rows(
            rows,
            min_pattern_len=int(args.min_pattern_len),
            limit=int(args.limit),
            pattern_json=args.pattern_json,
            row_index=args.row_index,
        )
    except (ValueError, KeyError, IndexError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if not target_indices:
        print(
            f"No candidates with pattern_len >= {args.min_pattern_len} in {candidates_csv}",
            file=sys.stderr,
        )
        return 1

    try:
        results_h5 = resolve_grammar_results_h5(kpms_root, args.seed, results_h5=Path(args.results_h5) if args.results_h5 else None)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    tracking_h5 = resolve_tracking_h5_path(kpms_root=kpms_root, tracking_h5=args.tracking_h5)
    if tracking_h5 is None:
        print("No tracking H5 found; pass --tracking-h5", file=sys.stderr)
        return 1

    pre_cfg = preprocess_config_for_results_h5(results_h5, kpms_root=kpms_root) or KpmsPreprocessConfig()
    pre_cfg = replace(pre_cfg, db_path=Path(tracking_h5))

    out_dir = Path(args.out) if args.out is not None else grammar_grid_movies_dir(gdir)
    out_dir.mkdir(parents=True, exist_ok=True)
    max_matches = int(args.max_matches) if args.max_matches is not None else 10**9
    csv_parent = candidates_csv.parent

    written: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []
    for i in target_indices:
        row = rows[i]
        try:
            grid_path, n_clips = _render_candidate_grid(
                row,
                gdir=gdir,
                manifest_path=Path(args.manifest_path),
                pipeline_h5=Path(args.pipeline_h5),
                results_h5=results_h5,
                tracking_h5=Path(tracking_h5),
                out_dir=out_dir,
                max_matches=max_matches,
                padding_s=float(args.padding_s),
                keypoints_only=bool(args.keypoints_only),
                no_ethogram=bool(args.no_ethogram),
                no_syllable_tray=bool(args.no_syllable_tray),
                keep_clips=bool(args.keep_clips),
            )
        except Exception as exc:
            skipped.append({"pattern_json": row.get("pattern_json"), "error": str(exc)})
            continue
        rel = os.path.relpath(grid_path.resolve(), csv_parent.resolve())
        row["preview_grid_path"] = rel
        written.append(
            {
                "pattern_json": row.get("pattern_json"),
                "output_mp4": str(grid_path.resolve()),
                "preview_grid_path": rel,
                "n_exemplars": n_clips,
            }
        )

    if written and not args.no_write_back:
        _write_back_preview_paths(candidates_csv, rows)

    print(
        json.dumps(
            {
                "seed": str(args.seed),
                "candidates_csv": str(candidates_csv.resolve()),
                "output_dir": str(out_dir.resolve()),
                "min_pattern_len": int(args.min_pattern_len),
                "n_written": len(written),
                "n_skipped": len(skipped),
                "wrote_back_csv": bool(written and not args.no_write_back),
                "movies": written,
                "skipped": skipped,
            },
            indent=2,
        )
    )
    return 0 if written else 1


if __name__ == "__main__":
    raise SystemExit(main())
