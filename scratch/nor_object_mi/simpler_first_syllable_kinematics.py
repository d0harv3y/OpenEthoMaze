"""Build syllable-bout kinematics across all paramscan kpMS models (scratch).

Spot recomputed from my_NOR_results.h5; heading from each results.h5.
Does not read archived ladder CSVs.

Regen:
  uv run python scratch/nor_object_mi/simpler_first_syllable_kinematics.py
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Sequence

import h5py

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.bout_kinematics import (  # noqa: E402
    KINEMATICS_FIELDS,
    build_kinematics_bout_rows,
    discover_paramscan_models,
)
from nor_object_mi.join_keys import filter_cohort, iter_joined_sessions  # noqa: E402
from nor_object_mi.ngram_decisions import DEFAULT_MIN_BOUT_FRAMES_CLEAN  # noqa: E402

DEFAULT_NOR = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\my_NOR_results.h5")
DEFAULT_ENSEMBLE = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017")


def _write_csv(path: Path, fieldnames: Sequence[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(fieldnames), extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})


def _info_md() -> str:
    return """# INFO — syllable bout kinematics (NOR)

Grain: one row = one kpMS syllable bout × model (full session).

## Inputs

| Source | Role |
|--------|------|
| `my_NOR_results.h5` | SLEAP pose → **spot** = mean(nose, neck, spine); objects / pseudo-loci; `video_fps` |
| `paramscan_*/results.h5` | `syllable`, `heading` (kpMS apply) |

Archived ladder CSVs are **not** inputs.

## Spot vs ethogram

Ethogram compile uses anatomical centroid + blob. This table uses **spot** for speed/path/straightness and kpMS **heading** for |Δheading| / net / sin·cos. Blob is absent on NOR H5; `bout_mean_nose_tail_m` is a NOR-local size proxy (**not** ethogram-commensurate).

## Cross-model rule

`raw_syllable_id` is model-local. Do not equate syllables by id across models (ADR-0005). Use kinematic (+ proximity) features for clustering / signatures.

## Columns (summary)

Ethogram-parity: speed / IQR speed / duration / straightness / abs·IQR·net dheading / heading sin·cos / `ambiguous`.

NOR extras: path length, valid-frame frac, nose–tail mean/IQR, `bout_mean_dist_any_m` (+ fam/nvl on `novel_obj`, obj_a/b when objects present).

## N-grams

Occurrence stimulus in NOR n-gram ladders is bout-mean distance. Join this table on `(model, animal_id, raw_session, bout_index)` or row spans; do not re-mine here.
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
    ap.add_argument("--model", type=str, default=None, help="Single paramscan_* name")
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
    args = ap.parse_args(argv)

    out = args.out_dir or (args.ensemble_root / "_nor_object_mi" / "simpler_first_syllable_kinematics")
    out.mkdir(parents=True, exist_ok=True)

    if args.min_bout_frames is not None:
        min_bout = args.min_bout_frames
    elif args.clean:
        min_bout = DEFAULT_MIN_BOUT_FRAMES_CLEAN
    else:
        min_bout = None

    if args.model:
        models = [args.model]
    else:
        models = discover_paramscan_models(args.ensemble_root)
    if not models:
        print("No paramscan_*/results.h5 found", flush=True)
        return 1

    all_rows: list[dict[str, object]] = []
    per_model: list[dict[str, object]] = []
    n_models = len(models)

    with h5py.File(args.nor_h5, "r") as nor_h5:
        cohort = filter_cohort(nor_h5)
        (out / "cohort_filter.json").write_text(json.dumps(cohort, indent=2), encoding="utf-8")
        kept = set(cohort["kept_ids"])  # type: ignore[arg-type]

        for i, model in enumerate(models, start=1):
            kpms_path = args.ensemble_root / model / "results.h5"
            if not kpms_path.is_file():
                print(f"[{i}/{n_models}] MISSING {model}", flush=True)
                per_model.append({"model": model, "status": "missing_results_h5"})
                continue
            print(f"[{i}/{n_models}] {model}", flush=True)
            with h5py.File(kpms_path, "r") as kpms_h5:
                sessions = list(
                    iter_joined_sessions(nor_h5, kpms_h5, kept_ids=kept, phase_layer=None)
                )
                rows, summary = build_kinematics_bout_rows(
                    nor_h5,
                    kpms_h5,
                    sessions,
                    model=model,
                    min_bout_frames=min_bout,
                )
            all_rows.extend(rows)
            summary["status"] = "ok"
            summary["n_joined_sessions"] = len(sessions)
            per_model.append(summary)
            print(
                f"  sessions_ok={summary['n_sessions_ok']} "
                f"bouts={summary['n_bout_rows']} "
                f"err={summary['n_skip_error']}",
                flush=True,
            )

    _write_csv(out / "syllable_bout_kinematics.csv", KINEMATICS_FIELDS, all_rows)

    run_summary = {
        "nor_h5": str(args.nor_h5),
        "ensemble_root": str(args.ensemble_root),
        "n_models": n_models,
        "n_models_ok": sum(1 for s in per_model if s.get("status") == "ok"),
        "n_bout_rows": len(all_rows),
        "min_bout_frames": min_bout,
        "spot_definition": "mean(nose,neck,spine)/pixels_per_meter",
        "heading_source": "kpms results.h5 heading",
        "archived_ladders_used": False,
        "per_model": per_model,
    }
    (out / "run_summary.json").write_text(json.dumps(run_summary, indent=2), encoding="utf-8")
    (out / "INFO_syllable_kinematics.md").write_text(_info_md(), encoding="utf-8")
    print(
        f"Wrote {len(all_rows)} rows from {run_summary['n_models_ok']}/{n_models} models -> {out}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
