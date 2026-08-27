"""Build movement-bout kinematics with the same columns as syllable bouts.

Spot and proximity match the syllable table. Heading is SLEAP nose−spine
(no kpMS). Spans come from NOR ``ambulation_metrics/{node}/movement_bouts``.

Regen:
  uv run python scratch/nor_object_mi/simpler_first_movement_kinematics.py
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
    build_ambulation_kinematics_bout_rows,
)
from nor_object_mi.join_keys import filter_cohort, iter_nor_sessions  # noqa: E402

DEFAULT_NOR = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\my_NOR_results.h5")
DEFAULT_ENSEMBLE = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017")


def _write_csv(path: Path, fieldnames: Sequence[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(fieldnames), extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})


def _info_md(*, node: str) -> str:
    return f"""# INFO — movement bout kinematics (NOR)

Grain: one row = one ambulation movement bout (full session). Same columns as
``syllable_bout_kinematics.csv``.

## Inputs

| Source | Role |
|--------|------|
| `my_NOR_results.h5` | SLEAP pose → **spot**; objects / pseudo-loci; `video_fps` |
| `ambulation_metrics/{node}/movement_bouts` | bout spans (`start_frame`, exclusive `end_frame`) |

No kpMS `results.h5`. Archived ladder CSVs are **not** inputs.

## Same columns, different identity

| Column | Movement | Immobile (complement) |
|--------|----------|------------------------|
| `model` | `movement_{node}` | `immobile_{node}` |
| `ss` | NaN | NaN |
| `kpms_key` | empty | empty |
| `raw_syllable_id` | -1 | -2 |

Immobile spans are the gaps on ``[0, n_frames)`` around merged movement bouts
(pre-first, between, post-last). Not a stored H5 ``immobile_bouts`` table.

## Spot vs heading

Speed / path / straightness / proximity use **spot**, same recipe as syllable bouts.
Heading is SLEAP **nose − spine**, not kpMS apply heading — so heading columns are
**not** commensurate with the syllable table. Speed/path/proximity are.

Default node is **spot** (same geometry as speed). `--node fore` uses forelimb
hysteresis spans (clocks runner) on the same spot scalars.

## Cross-model rule

Does not apply. Movement bouts are model-free.
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--nor-h5", type=Path, default=DEFAULT_NOR)
    ap.add_argument("--ensemble-root", type=Path, default=DEFAULT_ENSEMBLE)
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Default: <ensemble>/_nor_object_mi/simpler_first_movement_kinematics",
    )
    ap.add_argument(
        "--node",
        type=str,
        default="spot",
        help="ambulation_metrics node holding movement_bouts (spot or fore)",
    )
    args = ap.parse_args(argv)

    out = args.out_dir or (
        args.ensemble_root / "_nor_object_mi" / "simpler_first_movement_kinematics"
    )
    out.mkdir(parents=True, exist_ok=True)

    with h5py.File(args.nor_h5, "r") as nor_h5:
        cohort = filter_cohort(nor_h5)
        (out / "cohort_filter.json").write_text(json.dumps(cohort, indent=2), encoding="utf-8")
        kept = set(cohort["kept_ids"])  # type: ignore[arg-type]
        sessions = list(iter_nor_sessions(nor_h5, kept_ids=kept, phase_layer=None))
        print(f"sessions={len(sessions)} node={args.node}", flush=True)
        move_rows, still_rows, summary = build_ambulation_kinematics_bout_rows(
            nor_h5,
            sessions,
            node=str(args.node),
        )

    _write_csv(out / "movement_bout_kinematics.csv", KINEMATICS_FIELDS, move_rows)
    _write_csv(out / "immobile_bout_kinematics.csv", KINEMATICS_FIELDS, still_rows)
    run_summary = {
        "nor_h5": str(args.nor_h5),
        "n_sessions": len(sessions),
        "n_movement_rows": len(move_rows),
        "n_immobile_rows": len(still_rows),
        "n_bout_rows": len(move_rows),
        "node": args.node,
        "columns": list(KINEMATICS_FIELDS),
        "spot_definition": "mean(nose,neck,spine)/pixels_per_meter",
        "heading_source": "sleap_nose_minus_spine",
        "immobile_definition": "complement of merged movement_bouts on [0, n_frames)",
        "archived_ladders_used": False,
        "summary": summary,
    }
    (out / "run_summary.json").write_text(json.dumps(run_summary, indent=2), encoding="utf-8")
    (out / "INFO_movement_kinematics.md").write_text(_info_md(node=str(args.node)), encoding="utf-8")
    print(
        f"Wrote movement={len(move_rows)} immobile={len(still_rows)} "
        f"sessions_ok={summary['n_sessions_ok']} "
        f"err={summary['n_skip_error']} -> {out}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
