"""
Average RUN-phase block dwell plots from a legacy VAST H5 + manifest.

Default cohort: experimental ``S01``–``S05``, ``researcher == Emma|Hayden``.

Outputs PNGs at ``{out}/S##/{tx}/S##_tx_strain_sex_trial{lo}-{hi}.png`` and ``summary.csv``.
Also writes full-session (T01–T09) plots under ``{out}/trial1-9/`` and cross-session pooled
plots under ``{out}/all-sessions/`` (each with its own ``summary.csv``).
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path
from typing import Sequence

import cv2
import h5py
import pandas as pd

from maze.pipeline.db import open_db
from maze.pipeline.defaults import MAX_DWELL_TIME_S
from maze.pipeline.viz.block_dwell_average import (
    ALL_TRIAL_BLOCKS,
    FULL_SESSION_BLOCK,
    POOLED_SESSION_LABEL,
    TRIAL_BLOCKS,
    average_block_dwell,
    export_relpath,
    export_relpath_pooled,
    load_trial_run_sample,
    render_block_dwell_image,
)

SUMMARY_FIELDS = (
    "session",
    "tx",
    "sex",
    "strain",
    "block",
    "block_trials",
    "n_animal_sessions",
    "n_unique_animals",
    "n_trials",
    "output_path",
    "colorbar_max_s",
)


def _parse_sessions(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ("S01", "S02", "S03", "S04", "S05")
    return tuple(s.strip() for s in raw.split(",") if s.strip())


def _load_manifest_rows(
    manifest_path: Path,
    *,
    phase: str,
    researcher: str,
    sessions: Sequence[str],
) -> pd.DataFrame:
    # keep_default_na=False: manifest uses literal "n/a" for treatment (not pandas NA).
    df = pd.read_csv(manifest_path, keep_default_na=False)
    mask = (
        (df["phase"].astype(str) == phase)
        & (df["session"].isin(sessions))
        & (df["researcher"].astype(str) == researcher)
    )
    sub = df.loc[mask].copy()
    for col in ("sex", "strain", "tx"):
        sub = sub[sub[col].notna()]
        sub = sub[sub[col].astype(str).str.strip() != ""]
        sub = sub[sub[col].astype(str) != "?"]
    return sub


def _parse_blocks(raw: str | None, *, valid: dict[str, tuple[str, ...]]) -> tuple[str, ...]:
    if not raw:
        return tuple(valid.keys())
    blocks = tuple(b.strip() for b in raw.split(",") if b.strip())
    unknown = [b for b in blocks if b not in valid]
    if unknown:
        raise ValueError(f"Unknown block(s): {', '.join(unknown)}")
    return blocks


def run_average_block_dwell_plots(
    *,
    db_path: Path,
    manifest_path: Path,
    out_dir: Path,
    phase: str = "experimental",
    researcher: str = "Emma|Hayden",
    sessions: Sequence[str] = ("S01", "S02", "S03", "S04", "S05"),
    max_dwell_time_s: float = MAX_DWELL_TIME_S,
    blocks: Sequence[str] = tuple(TRIAL_BLOCKS.keys()),
    group_by_session: bool = True,
) -> list[dict[str, object]]:
    manifest = _load_manifest_rows(
        manifest_path,
        phase=phase,
        researcher=researcher,
        sessions=sessions,
    )
    if manifest.empty:
        raise ValueError("No manifest rows matched phase/session/researcher/strata filters")

    out_dir.mkdir(parents=True, exist_ok=True)
    summary_rows: list[dict[str, object]] = []
    block_set = set(blocks)

    groups: dict[tuple[str, ...], list[tuple[int, str, str]]] = defaultdict(list)
    for row in manifest.itertuples(index=False):
        trial = str(row.trial)
        for block, trials in ALL_TRIAL_BLOCKS.items():
            if block not in block_set:
                continue
            if trial in trials:
                if group_by_session:
                    key = (str(row.session), str(row.tx), str(row.sex), str(row.strain), block)
                else:
                    key = (str(row.tx), str(row.sex), str(row.strain), block)
                groups[key].append((int(row.animal_id), str(row.session), trial))

    with open_db(db_path, "r") as h5_file:
        h5 = h5_file
        assert isinstance(h5, h5py.File)
        for key, members in sorted(groups.items()):
            if group_by_session:
                session, tx, sex, strain, block = key
            else:
                tx, sex, strain, block = key
                session = POOLED_SESSION_LABEL
            samples = []
            for animal_id, member_session, trial in members:
                sample = load_trial_run_sample(
                    h5,
                    animal_id=animal_id,
                    session=member_session,
                    trial=trial,
                )
                if sample is not None:
                    samples.append(sample)

            dwell_grid_s, exits_cm, n_units, n_unique_animals, n_trials = average_block_dwell(samples)
            if n_units == 0:
                continue

            rel = (
                export_relpath(session, tx, strain, sex, block)
                if group_by_session
                else export_relpath_pooled(tx, strain, sex, block)
            )
            out_path = out_dir / rel
            out_path.parent.mkdir(parents=True, exist_ok=True)
            image = render_block_dwell_image(
                dwell_grid_s,
                exits_cm,
                max_dwell_time_s=max_dwell_time_s,
            )

            if not cv2.imwrite(str(out_path), image):
                raise RuntimeError(f"Failed to write {out_path}")

            block_trials = ",".join(ALL_TRIAL_BLOCKS[block])
            summary_rows.append(
                {
                    "session": session,
                    "tx": tx,
                    "sex": sex,
                    "strain": strain,
                    "block": block,
                    "block_trials": block_trials,
                    "n_animal_sessions": n_units,
                    "n_unique_animals": n_unique_animals,
                    "n_trials": n_trials,
                    "output_path": str(out_path.resolve()),
                    "colorbar_max_s": float(max_dwell_time_s),
                }
            )

    summary_path = out_dir / "summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(summary_rows)

    return summary_rows


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Average legacy RUN-phase block dwell plots (H5 spot_hybrid, arena-normalized cm)."
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        required=True,
        help="Path to vast_results_legacy.h5",
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        required=True,
        help="Path to trial_manifest_legacy.csv",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="Output directory for PNG tree and summary.csv",
    )
    parser.add_argument(
        "--phase",
        default="experimental",
        help="Manifest phase filter (default: experimental)",
    )
    parser.add_argument(
        "--researcher",
        default="Emma|Hayden",
        help="Manifest researcher filter (default: Emma|Hayden)",
    )
    parser.add_argument(
        "--sessions",
        default=None,
        help="Comma-separated sessions (default: S01,S02,S03,S04,S05)",
    )
    parser.add_argument(
        "--max-dwell-s",
        type=float,
        default=MAX_DWELL_TIME_S,
        help=f"Fixed colorbar max dwell seconds (default: {MAX_DWELL_TIME_S})",
    )
    parser.add_argument(
        "--blocks",
        default=None,
        help="Comma-separated trial blocks for --out-dir (default: 1-3,4-6,7-9)",
    )
    parser.add_argument(
        "--no-full-session",
        action="store_true",
        help=f"Skip full-session {FULL_SESSION_BLOCK} export to {{out-dir}}/trial1-9/",
    )
    parser.add_argument(
        "--full-session-out-dir",
        type=Path,
        default=None,
        help=f"Override output dir for {FULL_SESSION_BLOCK} plots (default: {{out-dir}}/trial1-9)",
    )
    parser.add_argument(
        "--no-all-sessions",
        action="store_true",
        help="Skip cross-session pooled export to {out-dir}/all-sessions/",
    )
    parser.add_argument(
        "--all-sessions-out-dir",
        type=Path,
        default=None,
        help="Override output dir for cross-session pooled plots (default: {out-dir}/all-sessions)",
    )
    args = parser.parse_args()

    out_dir = args.out_dir.expanduser().resolve()
    db_path = args.db_path.expanduser().resolve()
    manifest_path = args.manifest_path.expanduser().resolve()

    try:
        block_rows = run_average_block_dwell_plots(
            db_path=db_path,
            manifest_path=manifest_path,
            out_dir=out_dir,
            phase=args.phase,
            researcher=args.researcher,
            sessions=_parse_sessions(args.sessions),
            max_dwell_time_s=float(args.max_dwell_s),
            blocks=_parse_blocks(args.blocks, valid=TRIAL_BLOCKS),
        )
        full_rows: list[dict[str, object]] = []
        if not args.no_full_session:
            full_out = (
                args.full_session_out_dir.expanduser().resolve()
                if args.full_session_out_dir is not None
                else out_dir / "trial1-9"
            )
            full_rows = run_average_block_dwell_plots(
                db_path=db_path,
                manifest_path=manifest_path,
                out_dir=full_out,
                phase=args.phase,
                researcher=args.researcher,
                sessions=_parse_sessions(args.sessions),
                max_dwell_time_s=float(args.max_dwell_s),
                blocks=(FULL_SESSION_BLOCK,),
            )
        pooled_rows: list[dict[str, object]] = []
        if not args.no_all_sessions:
            pooled_root = (
                args.all_sessions_out_dir.expanduser().resolve()
                if args.all_sessions_out_dir is not None
                else out_dir / "all-sessions"
            )
            pooled_rows.extend(
                run_average_block_dwell_plots(
                    db_path=db_path,
                    manifest_path=manifest_path,
                    out_dir=pooled_root,
                    phase=args.phase,
                    researcher=args.researcher,
                    sessions=_parse_sessions(args.sessions),
                    max_dwell_time_s=float(args.max_dwell_s),
                    blocks=_parse_blocks(args.blocks, valid=TRIAL_BLOCKS),
                    group_by_session=False,
                )
            )
            if not args.no_full_session:
                pooled_rows.extend(
                    run_average_block_dwell_plots(
                        db_path=db_path,
                        manifest_path=manifest_path,
                        out_dir=pooled_root / "trial1-9",
                        phase=args.phase,
                        researcher=args.researcher,
                        sessions=_parse_sessions(args.sessions),
                        max_dwell_time_s=float(args.max_dwell_s),
                        blocks=(FULL_SESSION_BLOCK,),
                        group_by_session=False,
                    )
                )
    except (RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {len(block_rows)} block PNGs and {out_dir / 'summary.csv'}")
    if full_rows:
        full_out = (
            args.full_session_out_dir.expanduser().resolve()
            if args.full_session_out_dir is not None
            else out_dir / "trial1-9"
        )
        print(f"Wrote {len(full_rows)} full-session PNGs and {full_out / 'summary.csv'}")
    if pooled_rows:
        pooled_root = (
            args.all_sessions_out_dir.expanduser().resolve()
            if args.all_sessions_out_dir is not None
            else out_dir / "all-sessions"
        )
        print(f"Wrote {len(pooled_rows)} cross-session PNGs under {pooled_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
