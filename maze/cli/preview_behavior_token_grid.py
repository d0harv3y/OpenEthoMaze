"""CLI: render behavior-token exemplar grid movies."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

from maze.kpms.apply_summary import (
    preprocess_config_for_results_h5,
    resolve_tracking_h5_path,
)
from maze.kpms.behavior_ethogram.bout_table_io import read_bout_table_csv
from maze.kpms.behavior_ethogram.grammar_matches import (
    DEFAULT_PREVIEW_PADDING_S,
    manifest_lookup_by_kpms_key,
    resolve_manifest_for_trial_key,
)
from maze.kpms.behavior_ethogram.paths import (
    bout_tokens_csv,
    resolve_results_h5_path,
    resolve_stage_iii_dir,
    token_grid_clips_dir,
    token_grid_movies_dir,
)
from maze.kpms.behavior_ethogram.token_exemplars import (
    DEFAULT_MAX_TOKEN_EXEMPLARS,
    select_token_bout_exemplars,
    unique_behavior_tokens,
)
from maze.kpms.behavior_ethogram.token_grid_compose import compose_grid_video
from maze.kpms.behavior_ethogram.token_grid_render import (
    manifest_has_video,
    render_overlay_clip_for_match,
    render_pose_only_clip_for_match,
)
from maze.kpms.frame_alignment import kpms_aligned_coordinates_and_indices
from maze.kpms.preprocess import KpmsPreprocessConfig
from maze.pipeline.viz.overlay_cli import is_unified_overlay_available


def _parse_token_list(raw: str | None) -> list[int] | None:
    if raw is None or not str(raw).strip():
        return None
    out: list[int] = []
    for part in str(raw).split(","):
        text = part.strip()
        if text:
            out.append(int(text))
    return out or None


def _build_trial_source_frames(
    trial_keys: set[str],
    *,
    manifest_path: Path,
    pre_cfg: KpmsPreprocessConfig,
) -> dict[str, np.ndarray]:
    by_key = manifest_lookup_by_kpms_key(manifest_path)
    out: dict[str, np.ndarray] = {}
    for trial_key in sorted(trial_keys):
        manifest = by_key.get(trial_key)
        if manifest is None:
            continue
        aligned = kpms_aligned_coordinates_and_indices(manifest, pre_cfg)
        if aligned is None:
            continue
        _rk, _coord, src_idx = aligned
        out[trial_key] = np.asarray(src_idx, dtype=np.int64)
    return out


def _render_exemplar_clip(
    match,
    *,
    behavior_token: int,
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
    use_pose_only = keypoints_only or not manifest_has_video(manifest)
    if use_pose_only:
        return render_pose_only_clip_for_match(
            match,
            behavior_token=behavior_token,
            manifest=manifest,
            pipeline_h5=pipeline_h5,
            results_h5=results_h5,
            tracking_h5=tracking_h5,
            out_path=out_path,
            padding_s=padding_s,
        )
    return render_overlay_clip_for_match(
        match,
        behavior_token=behavior_token,
        manifest=manifest,
        manifest_path=manifest_path,
        pipeline_h5=pipeline_h5,
        results_h5=results_h5,
        tracking_h5=tracking_h5,
        out_path=out_path,
        padding_s=padding_s,
        no_ethogram=no_ethogram,
        no_syllable_tray=no_syllable_tray,
    )


def render_token_grid_movie(
    *,
    behavior_token: int,
    bout_rows: list[dict[str, str]],
    trial_source_frames: dict[str, np.ndarray],
    seed: str,
    manifest_path: Path,
    pipeline_h5: Path,
    results_h5: Path,
    tracking_h5: Path,
    out_path: Path,
    clips_dir: Path,
    max_exemplars: int = DEFAULT_MAX_TOKEN_EXEMPLARS,
    padding_s: float = DEFAULT_PREVIEW_PADDING_S,
    keypoints_only: bool = False,
    no_ethogram: bool = False,
    no_syllable_tray: bool = False,
    keep_clips: bool = False,
) -> tuple[Path, int] | None:
    """Render one grid MP4 for ``behavior_token``; return ``(path, n_exemplars)`` or None."""
    matches = select_token_bout_exemplars(
        bout_rows,
        behavior_token=behavior_token,
        trial_source_frames=trial_source_frames,
        seed=seed,
        max_exemplars=max_exemplars,
    )
    if not matches:
        return None

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    clip_stage = Path(clips_dir)
    clip_stage.mkdir(parents=True, exist_ok=True)
    clip_paths: list[Path] = []
    labels: list[str] = []
    try:
        for idx, match in enumerate(matches):
            clip_dest = clip_stage / f"exemplar_{idx:02d}.mp4"
            written = _render_exemplar_clip(
                match,
                behavior_token=behavior_token,
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
        grid_path = compose_grid_video(
            clip_paths,
            out_path,
            cell_labels=labels,
        )
    finally:
        if not keep_clips and clip_stage.is_dir():
            shutil.rmtree(clip_stage, ignore_errors=True)
    return grid_path, len(matches)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Render grid MP4 review movies per behavior_token (bout exemplars).")
    ap.add_argument("--kpms-root", type=Path, required=True)
    ap.add_argument("--seed", type=str, required=True)
    ap.add_argument("--manifest-path", type=Path, required=True)
    ap.add_argument("--pipeline-h5", type=Path, required=True, help="Legacy / pipeline tracking HDF5")
    ap.add_argument("--tracking-h5", type=Path, default=None)
    ap.add_argument("--tokens-csv", type=Path, default=None)
    ap.add_argument(
        "--results-h5",
        type=Path,
        default=None,
        help="kpMS syllable results H5 (default: anatomical/seed_*/results_apply.h5 or <kpms-root>/results.h5)",
    )
    ap.add_argument(
        "--token",
        type=str,
        default=None,
        help="Comma-separated behavior_token ids (default: all tokens in CSV)",
    )
    ap.add_argument("--max-exemplars", type=int, default=DEFAULT_MAX_TOKEN_EXEMPLARS)
    ap.add_argument("--padding-s", type=float, default=DEFAULT_PREVIEW_PADDING_S)
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output directory (default: stage_iii/seed_<seed>/grid_movies)",
    )
    ap.add_argument("--keypoints-only", action="store_true")
    ap.add_argument("--no-ethogram", action="store_true")
    ap.add_argument("--no-syllable-tray", action="store_true")
    ap.add_argument(
        "--keep-clips",
        action="store_true",
        help="Keep per-exemplar clips under grid_movies/clips/ (default: delete after grid compose)",
    )
    args = ap.parse_args(argv)

    if not is_unified_overlay_available():
        print("OpenCV required; install gui/kpms extras.", file=sys.stderr)
        return 1

    kpms_root = Path(args.kpms_root)
    stage_iii = resolve_stage_iii_dir(kpms_root, seed=args.seed)
    tokens_csv = Path(args.tokens_csv) if args.tokens_csv else bout_tokens_csv(stage_iii)
    if not tokens_csv.is_file():
        print(f"Missing bout tokens CSV: {tokens_csv}", file=sys.stderr)
        return 1

    results_h5 = resolve_results_h5_path(
        kpms_root,
        args.seed,
        results_h5=Path(args.results_h5) if args.results_h5 else None,
    )
    if not results_h5.is_file():
        print(
            f"Missing kpMS results H5: {results_h5} "
            "(expected anatomical/seed_*/results_apply.h5 or <kpms-root>/results.h5; pass --results-h5)",
            file=sys.stderr,
        )
        return 1

    tracking_h5 = resolve_tracking_h5_path(kpms_root=kpms_root, tracking_h5=args.tracking_h5)
    if tracking_h5 is None:
        print("No tracking H5 found; pass --tracking-h5", file=sys.stderr)
        return 1

    bout_rows = read_bout_table_csv(tokens_csv)
    token_filter = _parse_token_list(args.token)
    if token_filter is None:
        tokens = unique_behavior_tokens(bout_rows, seed=args.seed)
    else:
        tokens = tuple(sorted(set(token_filter)))

    pre_cfg = preprocess_config_for_results_h5(results_h5, kpms_root=kpms_root) or KpmsPreprocessConfig()
    pre_cfg = replace(pre_cfg, db_path=Path(tracking_h5))
    trial_keys = {str(row["trial_key"]) for row in bout_rows if str(row.get("seed", "")) == str(args.seed)}
    trial_source_frames = _build_trial_source_frames(
        trial_keys,
        manifest_path=Path(args.manifest_path),
        pre_cfg=pre_cfg,
    )
    if not trial_source_frames:
        print("No aligned trials found for manifest / tracking H5.", file=sys.stderr)
        return 1

    out_dir = Path(args.out) if args.out is not None else token_grid_movies_dir(stage_iii)
    out_dir.mkdir(parents=True, exist_ok=True)

    written: list[dict[str, object]] = []
    skipped: list[int] = []
    for token in tokens:
        out_file = out_dir / f"token_{int(token):02d}.mp4"
        try:
            rendered = render_token_grid_movie(
                behavior_token=int(token),
                bout_rows=bout_rows,
                trial_source_frames=trial_source_frames,
                seed=str(args.seed),
                manifest_path=Path(args.manifest_path),
                pipeline_h5=Path(args.pipeline_h5),
                results_h5=results_h5,
                tracking_h5=Path(tracking_h5),
                out_path=out_file,
                clips_dir=token_grid_clips_dir(stage_iii, int(token)),
                max_exemplars=int(args.max_exemplars),
                padding_s=float(args.padding_s),
                keypoints_only=bool(args.keypoints_only),
                no_ethogram=bool(args.no_ethogram),
                no_syllable_tray=bool(args.no_syllable_tray),
                keep_clips=bool(args.keep_clips),
            )
        except Exception as exc:
            print(f"token {token}: {exc}", file=sys.stderr)
            continue
        if rendered is None:
            skipped.append(int(token))
            continue
        result, n_exemplars = rendered
        written.append(
            {
                "behavior_token": int(token),
                "output_mp4": str(result.resolve()),
                "n_exemplars": n_exemplars,
            }
        )

    payload = {
        "seed": str(args.seed),
        "output_dir": str(out_dir.resolve()),
        "n_written": len(written),
        "n_skipped": len(skipped),
        "skipped_tokens": skipped,
        "movies": written,
        "tokens_csv": str(tokens_csv.resolve()),
        "results_h5": str(results_h5.resolve()),
        "pipeline_h5": str(Path(args.pipeline_h5).resolve()),
        "tracking_h5": str(Path(tracking_h5).resolve()),
    }
    print(json.dumps(payload, indent=2))
    return 0 if written else 1


if __name__ == "__main__":
    raise SystemExit(main())
