"""
Build ``selected_trials.csv`` from NOR native keypoint-moSeq ``results.h5`` group names.

Top-level HDF5 keys look like::

    D:-nor vids-standard format-exp1-3115-NOR1 ID OBJ Arena 5 07-03-25 3115 06-07.h5

which map to::

    <base>\\standard format\\exp1\\3115\\NOR1 ID OBJ Arena 5 07-03-25 3115 06-07.h5
    <sleap> = str(h5) + ".slp"

Rows set ``kpms_recording_key`` to the full group name so ORM kpMS code matches native fits.

Example::

    uv run python scripts/generate_selected_trials_from_nor_kpms_results.py ^
      --results-h5 "D:/work sack/.../paramscan_.../results.h5" ^
      --output "D:/work sack/.../paramscan_.../selected_trials.csv"
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import h5py

from maze.kpms.native_nor_results_paths import nor_native_group_to_h5_and_sleap
from maze.pipeline.io.file_discovery import MANIFEST_CSV_FIELDNAMES, trial_manifest_csv_row_values
from maze.pipeline.io.file_discovery import TrialManifest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results-h5", type=Path, required=True)
    ap.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Default: <results_h5 parent>/selected_trials.csv",
    )
    ap.add_argument(
        "--base-dir",
        type=Path,
        default=Path(r"D:\work sack\impress data\NOR video"),
        help="Filesystem root for decoded paths (after D:-nor vids- prefix)",
    )
    ap.add_argument(
        "--prefix-encoded",
        type=str,
        default="D:-nor vids-",
        help="Leading substring in HDF5 group names to strip before path decode",
    )
    ap.add_argument(
        "--path-hyphens",
        type=int,
        default=3,
        help="Number of hyphen-separated path components before the filename segment",
    )
    ap.add_argument(
        "--require-sleap",
        action="store_true",
        help="Skip groups whose decoded .h5.slp path does not exist",
    )
    args = ap.parse_args()

    results_h5 = Path(args.results_h5).resolve()
    out = Path(args.output) if args.output else results_h5.parent / "selected_trials.csv"

    rows_out: list[list[str]] = []
    skipped = 0

    with h5py.File(str(results_h5), "r") as f:
        names = sorted(f.keys())

    for i, group_name in enumerate(names):
        try:
            h5_p, slp_p = nor_native_group_to_h5_and_sleap(
                group_name,
                prefix_encoded=str(args.prefix_encoded),
                base_dir=Path(args.base_dir),
                path_hyphens=int(args.path_hyphens),
            )
        except ValueError:
            skipped += 1
            continue
        if args.require_sleap and not slp_p.is_file():
            skipped += 1
            continue

        m = TrialManifest(
            animal_id="native",
            session=f"{i:04d}",
            trial="r",
            input_h5_path=h5_p,
            video_path=None,
            sleap_path=slp_p,
            is_habituation=False,
            kpms_recording_key=group_name,
        )
        rows_out.append(trial_manifest_csv_row_values(m))

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fp:
        w = csv.writer(fp)
        w.writerow(list(MANIFEST_CSV_FIELDNAMES))
        w.writerows(rows_out)

    print(f"Wrote {out} ({len(rows_out)} rows, skipped {skipped})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
