"""CLI: block-stratified tier-colored ethogram exports."""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import h5py
import pandas as pd

import numpy as np

from maze.kpms.behavior_ethogram.paths import token_tiers_csv
from maze.kpms.frame_alignment import kpms_recording_key
from maze.kpms.preprocess import KpmsPreprocessConfig
from maze.pipeline.db.trial_key import TrialKey
from maze.pipeline.io.file_discovery import TrialManifest, load_manifest_csv
from maze.pipeline.viz.block_dwell_average import (
    ALL_TRIAL_BLOCKS,
    TRIAL_BLOCKS,
    export_relpath,
)
from maze.pipeline.viz.block_ethogram_average import (
    BoutTierSpan,
    aggregate_mode_tier_per_second,
    expand_bout_tiers_to_rows,
    render_tier_ethogram_strip,
    render_tier_legend_bgr,
    rows_to_phase_seconds,
)
from maze.cli.average_block_dwell_plots import _load_manifest_rows


def _merge_tier_spans_with_bout_table(
    token_csv: Path,
    bout_csv: Path,
) -> dict[str, list[BoutTierSpan]]:
    bout_rows: dict[tuple[str, int], dict[str, str]] = {}
    with bout_csv.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            bout_rows[(str(row["trial_key"]), int(row["bout_index"]))] = row

    by_trial: dict[str, list[BoutTierSpan]] = defaultdict(list)
    with token_csv.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            bout = bout_rows.get((str(row["trial_key"]), int(row["bout_index"])))
            if bout is None:
                continue
            key = str(row["trial_key"])
            by_trial[key].append(
                BoutTierSpan(
                    trial_key=key,
                    row_start=int(bout["row_start"]),
                    row_end_exclusive=int(bout["row_end_exclusive"]),
                    tier=str(row.get("tier", "unknown")),
                    behavior_token=int(row.get("behavior_token", 0) or 0),
                )
            )
    return dict(by_trial)


def _trial_states_legacy(legacy_db: Path, manifest: TrialManifest) -> list[str] | None:
    key = TrialKey.from_manifest(manifest)
    with h5py.File(legacy_db, "r") as h5:
        group_path = key.path().lstrip("/")
        if group_path not in h5:
            return None
        g = h5[group_path]
        for point in ("spot_hybrid", "center"):
            xy_path = f"ambulation_metrics/{point}/xy"
            if xy_path not in g:
                continue
            rec = g[xy_path]
            if "trial_state" not in rec.dtype.names:
                continue
            raw = rec["trial_state"]
            return [
                x.decode("utf-8") if isinstance(x, (bytes, bytearray)) else str(x)
                for x in raw
            ]
    return None


def _trial_seconds_for_manifest(
    manifest: TrialManifest,
    *,
    tier_spans: dict[str, list[BoutTierSpan]],
    legacy_db: Path,
    fps: float,
    phase: str,
    pre_cfg: KpmsPreprocessConfig,
) -> tuple[np.ndarray, np.ndarray] | None:
    from maze.kpms.frame_alignment import kpms_aligned_coordinates_and_indices

    key = kpms_recording_key(manifest)
    spans = tier_spans.get(key)
    if not spans:
        return None
    aligned = kpms_aligned_coordinates_and_indices(manifest, pre_cfg)
    if aligned is None:
        return None
    n_rows = aligned[1].shape[0]
    tiers = expand_bout_tiers_to_rows(spans, n_rows)
    states = _trial_states_legacy(legacy_db, manifest)
    if states is None:
        states = ["run"] * n_rows
    if len(states) != n_rows:
        # Legacy state vector may be full video length; subsample is not attempted here.
        states = (states + ["run"] * n_rows)[:n_rows]
    return rows_to_phase_seconds(tiers, states, fps=fps, phase=phase)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Block ethogram exports with locomotion tier colors.")
    ap.add_argument("--kpms-root", type=Path, required=True)
    ap.add_argument("--legacy-db", type=Path, required=True)
    ap.add_argument("--manifest-path", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--token-tiers-csv", type=Path, default=None)
    ap.add_argument("--bout-csv", type=Path, default=None)
    ap.add_argument("--phase", choices=("run", "iti"), default="run")
    ap.add_argument("--blocks", type=str, default="1-3,4-6,7-9")
    ap.add_argument("--fps", type=float, default=30.0)
    args = ap.parse_args(argv)

    stage_iii = Path(args.kpms_root) / "behavior_ethogram" / "stage_iii"
    token_csv = Path(args.token_tiers_csv) if args.token_tiers_csv else token_tiers_csv(stage_iii)
    bout_csv = Path(args.bout_csv) if args.bout_csv else stage_iii / "bout_behavior_tokens.csv"
    if not token_csv.is_file():
        print(f"Missing token tiers CSV: {token_csv}", file=sys.stderr)
        return 1
    if not bout_csv.is_file():
        print(f"Missing bout CSV for row spans: {bout_csv}", file=sys.stderr)
        return 1

    tier_spans = _merge_tier_spans_with_bout_table(token_csv, bout_csv)
    manifests = load_manifest_csv(args.manifest_path)
    manifest_by_trial = {kpms_recording_key(m): m for m in manifests}
    pre_cfg = KpmsPreprocessConfig()

    block_keys = [b.strip() for b in args.blocks.split(",") if b.strip()]
    out_root = Path(args.out_dir)
    summary_rows: list[dict[str, str]] = []

    df = _load_manifest_rows(args.manifest_path, phase="experimental", researcher="Emma", sessions=("S01", "S02", "S03", "S04", "S05"))
    if df.empty:
        df = pd.read_csv(args.manifest_path, keep_default_na=False)

    for block in block_keys:
        trials = ALL_TRIAL_BLOCKS.get(block, TRIAL_BLOCKS.get(block, ()))
        if not trials:
            continue
        sub = df[df["trial"].isin(trials)] if "trial" in df.columns else df
        if sub.empty:
            continue

        for (session, tx, sex, strain), group in sub.groupby(["session", "tx", "sex", "strain"], dropna=False):
            trial_seconds: list[tuple[np.ndarray, np.ndarray]] = []
            for _, row in group.iterrows():
                key = f"{row['animal_id']}_{row['session']}_{row['trial']}"
                manifest = manifest_by_trial.get(key)
                if manifest is None:
                    continue
                sec = _trial_seconds_for_manifest(
                    manifest,
                    tier_spans=tier_spans,
                    legacy_db=args.legacy_db,
                    fps=args.fps,
                    phase=args.phase,
                    pre_cfg=pre_cfg,
                )
                if sec is not None:
                    trial_seconds.append(sec)

            if not trial_seconds:
                continue
            max_sec = max(len(t[0]) for t in trial_seconds)
            mode, n_trials = aggregate_mode_tier_per_second(trial_seconds, max_sec)
            strip = render_tier_ethogram_strip(mode)
            rel = export_relpath(
                session=str(session),
                tx=str(tx),
                strain=str(strain),
                sex=str(sex),
                block=block,
            )
            out_path = out_root / rel.with_name(rel.stem + f"_{args.phase}" + rel.suffix)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(out_path), strip)
            summary_rows.append(
                {
                    "session": str(session),
                    "tx": str(tx),
                    "sex": str(sex),
                    "strain": str(strain),
                    "block": block,
                    "phase": args.phase,
                    "n_trials": str(int(np.max(n_trials)) if len(n_trials) else 0),
                    "max_seconds": str(max_sec),
                    "output_path": str(out_path),
                }
            )

    legend_path = out_root / "tier_legend.png"
    cv2.imwrite(str(legend_path), render_tier_legend_bgr())
    summary_path = out_root / "summary.csv"
    if summary_rows:
        with summary_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
            writer.writeheader()
            writer.writerows(summary_rows)
    print(f"Wrote {len(summary_rows)} ethogram PNGs under {out_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
