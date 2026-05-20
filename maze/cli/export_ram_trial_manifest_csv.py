"""
Export an ORM :data:`~maze.pipeline.io.file_discovery.MANIFEST_CSV_FIELDNAMES` CSV for
radial-arm (legacy EHRAM) trials.

Uses the same discovery contract as :func:`maze.pipeline.sources.legacy_ehram.discover_legacy_ehram_work_items`:
authoritative ``trial_ns.csv`` (columns ``parent_directory``, ``file_name``, ``id``, …) plus
recursive ``.mp4`` / ``.h5.slp`` pairs under ``--video-base``.

Each row references a shared RAM pipeline HDF5 (``--pipeline-h5``), typically produced by
``maze.pipeline.sources.legacy_ehram_import`` / ``bootstrap_legacy_ram_database``.

Session and trial keys match :func:`maze.pipeline.sources.legacy_ehram_import.legacy_ram_work_item_to_trial_key`:
``session`` = normalized phase (e.g. ``train-1``), ``trial`` = zero-padded ``T01`` style.

From repo root::

    uv run maze-export-ram-trial-manifest ^
      --video-base "D:\\path\\to\\EHRAM Cohort 1 DARPA videos" ^
      --trial-ns inputs/trial_ns.csv ^
      --pipeline-h5 outputs/ram_legacy.db.h5 ^
      --out-csv inputs/ram_trial_manifest.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from maze.pipeline.io.file_discovery import (
    MANIFEST_CSV_FIELDNAMES,
    TrialManifest,
    trial_manifest_csv_row_values,
)
from maze.pipeline.sources.legacy_ehram import discover_legacy_ehram_work_items
from maze.pipeline.work_items import SourceWorkItem


def _is_habituation_phase(phase: str) -> bool:
    p = (phase or "").strip().lower()
    if not p:
        return False
    return p.startswith("h") or p.startswith("hab")


def source_work_item_to_trial_manifest(item: SourceWorkItem, pipeline_h5: Path) -> TrialManifest:
    """Map a legacy RAM work item to :class:`TrialManifest` for overlays / kpMS."""
    md = item.metadata
    phase = (md.get("phase") or item.phase or "").strip()
    return TrialManifest(
        animal_id=item.animal_id,
        session=item.session_key,
        trial=item.trial_key,
        input_h5_path=pipeline_h5.resolve(),
        video_path=item.video_path.resolve() if item.video_path else None,
        sleap_path=item.sleap_path.resolve() if item.sleap_path else None,
        timestamp=item.timestamp,
        original_session=phase or None,
        tx=(md.get("tx") or "").strip() or None,
        sex=(md.get("sex") or "").strip() or None,
        is_habituation=_is_habituation_phase(phase),
        cohort=None,
        researcher=None,
        kpms_recording_key=None,
    )


def main() -> int:
    p = argparse.ArgumentParser(
        description="Build ram_trial_manifest.csv from trial_ns.csv + video/SLEAP discovery."
    )
    p.add_argument(
        "--video-base",
        type=Path,
        required=True,
        help="Root directory scanned for .mp4 + .h5.slp pairs (same as legacy RAM import)",
    )
    p.add_argument(
        "--trial-ns",
        type=Path,
        required=True,
        help="Path to trial_ns.csv (parent_directory, file_name, id, phase, trial, …)",
    )
    p.add_argument(
        "--pipeline-h5",
        type=Path,
        required=True,
        help="ORM RAM pipeline HDF5 shared by these trials (trial groups /animal/session/trial)",
    )
    p.add_argument("--out-csv", type=Path, required=True, help="Output manifest CSV path")
    p.add_argument(
        "--probe-frames",
        action="store_true",
        help="Open pipeline HDF5 and fill h5_n_frames / video_n_frames when possible (slower)",
    )
    args = p.parse_args()

    video_base = args.video_base.expanduser().resolve()
    trial_ns = args.trial_ns.expanduser().resolve()
    pipeline_h5 = args.pipeline_h5.expanduser().resolve()
    out_csv = args.out_csv.expanduser().resolve()

    if not video_base.is_dir():
        print(f"Not a directory: {video_base}", file=sys.stderr)
        return 1
    if not trial_ns.is_file():
        print(f"trial_ns.csv not found: {trial_ns}", file=sys.stderr)
        return 1
    if not pipeline_h5.is_file():
        print(f"pipeline HDF5 not found: {pipeline_h5}", file=sys.stderr)
        return 1

    items = discover_legacy_ehram_work_items(video_base, trial_ns_path=trial_ns)
    if not items:
        print(
            "No work items discovered. Check --video-base, --trial-ns, and that "
            "parent_directory + file_name in CSV match each video folder + filename.",
            file=sys.stderr,
        )
        return 1

    manifests = [source_work_item_to_trial_manifest(it, pipeline_h5) for it in items]

    if args.probe_frames:
        _probe_frame_counts(manifests, pipeline_h5)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(list(MANIFEST_CSV_FIELDNAMES))
        for m in manifests:
            w.writerow(trial_manifest_csv_row_values(m))

    print(f"Wrote {len(manifests)} rows to {out_csv}")
    return 0


def _probe_frame_counts(manifests: list[TrialManifest], pipeline_h5: Path) -> None:
    """Best-effort frame counts for QA columns."""
    try:
        from maze.core.h5_layout import open_db, resolve_ambulation_metrics_group
    except ImportError:
        return

    try:
        with open_db(pipeline_h5, "r") as h5:
            for m in manifests:
                key = f"/{m.animal_id}/{m.session}/{m.trial}"
                g = h5.get(key)
                if g is None:
                    continue
                amb = resolve_ambulation_metrics_group(g)
                if amb is None:
                    continue
                for pt in ("spot", "spot_hybrid"):
                    if pt in amb and "xy" in amb[pt]:
                        m.h5_n_frames = int(len(amb[pt]["xy"]))
                        break
                if m.video_path and m.video_path.is_file():
                    try:
                        import cv2

                        cap = cv2.VideoCapture(str(m.video_path))
                        if cap.isOpened():
                            m.video_n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                        cap.release()
                    except Exception:
                        pass
    except OSError:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
