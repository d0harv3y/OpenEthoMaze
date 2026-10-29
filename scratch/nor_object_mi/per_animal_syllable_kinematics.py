"""Bout kinematics for per-animal NOR kpMS paramscan (144 animals × 9 models).

Grain-agnostic feature table for alphabet equating later. Model names are
``{animal}_paramscan_…`` under ``{cohort}/{animal}/anatomical/``.

Regen (OpenEthoMaze repo root, PowerShell):

  uv run python scratch/nor_object_mi/per_animal_syllable_kinematics.py --clean
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Sequence

import h5py

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.bout_kinematics import (  # noqa: E402
    KINEMATICS_FIELDS,
    build_kinematics_bout_rows,
    discover_per_animal_paramscan_models,
)
from nor_object_mi.join_keys import filter_cohort, iter_joined_sessions  # noqa: E402
from nor_object_mi.ngram_decisions import DEFAULT_MIN_BOUT_FRAMES_CLEAN  # noqa: E402

DEFAULT_NOR = Path(r"D:\sack\datas\impress\my_NOR_results.h5")
DEFAULT_ENSEMBLE = Path(
    r"D:\sack\datas\impress\nor_per_animal_paramscan"
)


def _write_header(path: Path, fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=list(fieldnames), extrasaction="ignore").writeheader()


def _append_rows(path: Path, fieldnames: Sequence[str], rows: list[dict[str, object]]) -> None:
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(fieldnames), extrasaction="ignore")
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})


def _info_md() -> str:
    return """# INFO — syllable bout kinematics (per-animal NOR paramscan)

Grain: one row = one kpMS syllable bout × animal-local model (full session).

## Inputs

| Source | Role |
|--------|------|
| `my_NOR_results.h5` | SLEAP pose → **spot** = mean(nose, neck, spine); objects / pseudo-loci; `video_fps`; sex / condition |
| `{cohort}/{animal}/anatomical/{animal}_paramscan_*/results.h5` | `syllable`, `heading` |

## Fit grain

One kpMS alphabet per animal × hyperparam cell (144 × 9). Same NOR IMPRESS
animals as pooled `moseq_251017` / `moseq_recog_260915`; segmentation is animal-local.

## Cross-model / cross-animal rule

`raw_syllable_id` is **animal×model-local** (ADR-0005 extreme). Do not equate
by integer id. Use kinematic (+ proximity) signatures for clustering.

## Columns

See `KINEMATICS_FIELDS` in `scratch/nor_object_mi/bout_kinematics.py` (speed,
heading, nose–tail, object distances, …).
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--nor-h5", type=Path, default=DEFAULT_NOR)
    ap.add_argument("--ensemble-root", type=Path, default=DEFAULT_ENSEMBLE)
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Default: <ensemble>/_nor_object_mi/simpler_first_syllable_kinematics",
    )
    ap.add_argument(
        "--clean",
        action="store_true",
        help=f"Absorb short syllable bouts (<{DEFAULT_MIN_BOUT_FRAMES_CLEAN} frames)",
    )
    ap.add_argument(
        "--min-bout-frames",
        type=int,
        default=None,
        help="Override absorb threshold; implies cleanup when >1",
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N models (smoke test)",
    )
    args = ap.parse_args(argv)

    out = args.out_dir or (
        args.ensemble_root / "_nor_object_mi" / "simpler_first_syllable_kinematics"
    )
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / "syllable_bout_kinematics.csv"

    if args.min_bout_frames is not None:
        min_bout = args.min_bout_frames
    elif args.clean:
        min_bout = DEFAULT_MIN_BOUT_FRAMES_CLEAN
    else:
        min_bout = None

    models = discover_per_animal_paramscan_models(args.ensemble_root)
    if args.limit is not None:
        models = models[: max(0, int(args.limit))]
    if not models:
        print("No per-animal *_paramscan_*/results.h5 found", flush=True)
        return 1

    _write_header(csv_path, KINEMATICS_FIELDS)
    per_model: list[dict[str, object]] = []
    n_models = len(models)
    n_rows = 0
    t0 = time.perf_counter()

    with h5py.File(args.nor_h5, "r") as nor_h5:
        cohort = filter_cohort(nor_h5)
        (out / "cohort_filter.json").write_text(json.dumps(cohort, indent=2), encoding="utf-8")
        kept = set(cohort["kept_ids"])  # type: ignore[arg-type]

        for i, (model, kpms_path) in enumerate(models, start=1):
            print(f"[{i}/{n_models}] {model}", flush=True)
            with h5py.File(kpms_path, "r") as kpms_h5:
                sessions = list(
                    iter_joined_sessions(nor_h5, kpms_h5, kept_ids=kept, session=None)
                )
                rows, summary = build_kinematics_bout_rows(
                    nor_h5,
                    kpms_h5,
                    sessions,
                    model=model,
                    min_bout_frames=min_bout,
                )
            _append_rows(csv_path, KINEMATICS_FIELDS, rows)
            n_rows += len(rows)
            summary["status"] = "ok"
            summary["n_joined_sessions"] = len(sessions)
            summary["results_h5"] = str(kpms_path)
            per_model.append(summary)
            elapsed = time.perf_counter() - t0
            rate = i / elapsed if elapsed > 0 else 0.0
            eta = (n_models - i) / rate if rate > 0 else float("nan")
            print(
                f"  sessions_ok={summary['n_sessions_ok']} "
                f"bouts={summary['n_bout_rows']} "
                f"err={summary['n_skip_error']} "
                f"rows_tot={n_rows} "
                f"eta_min={eta / 60:.1f}",
                flush=True,
            )

    run_summary = {
        "nor_h5": str(args.nor_h5),
        "ensemble_root": str(args.ensemble_root),
        "layout": "per_animal_nested",
        "n_models": n_models,
        "n_models_ok": sum(1 for s in per_model if s.get("status") == "ok"),
        "n_bout_rows": n_rows,
        "min_bout_frames": min_bout,
        "spot_definition": "mean(nose,neck,spine)/pixels_per_meter",
        "heading_source": "kpms results.h5 heading",
        "elapsed_s": time.perf_counter() - t0,
        "per_model": per_model,
    }
    (out / "run_summary.json").write_text(json.dumps(run_summary, indent=2), encoding="utf-8")
    (out / "INFO_syllable_kinematics.md").write_text(_info_md(), encoding="utf-8")
    print(
        f"Wrote {n_rows} rows from {run_summary['n_models_ok']}/{n_models} models -> {out}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
