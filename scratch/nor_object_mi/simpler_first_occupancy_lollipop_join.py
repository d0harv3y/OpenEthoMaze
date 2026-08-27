"""Occupancy × DA lollipop join (locked kpMS).

Occupancy is computed in every condition. DA hits are labeled with occupancy
in the step destination (`right`: identical_obj or novel_obj).

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/simpler_first_occupancy_lollipop_join.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.occupancy_lollipop import (  # noqa: E402
    join_da_occupancy,
    occupancy_tests,
    set_overlap_summary,
    signed_overlap_summary,
)
from nor_object_mi.simpler_first_q1 import LOCKED  # noqa: E402
from nor_object_mi.simpler_first_syll_ambulation_overlap import (  # noqa: E402
    AMB_COLS,
    DEFAULT_MOVE,
    DEFAULT_STILL,
    DEFAULT_SYLL,
    build_overlap_tables,
    load_locked_syllable_bouts,
)
from nor_object_mi.syll_ambulation_overlap import occupancy_from_bouts  # noqa: E402

DEFAULT_DA = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_da\da_syllable_tests_long.csv"
)
DEFAULT_OUT = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_occupancy_da_join"
)


def _info_md() -> str:
    return """# INFO — occupancy × DA join

## What this is

For the locked kpMS model, label each syllable by locomotor **occupancy**
(frame P(move | id) − session P(move); one-sample t, BH within phase ×
condition). Join those labels onto DA lollipop FDR hits using occupancy in
the DA step's **destination** condition (`identical_obj` for presence,
`novel_obj` for novelty/span).

## What this is not

Not the same contrast as DA (shares vs locomotor mix). Not tx. Not
investigation. Ids are not portable across models.

## Grain

Occupancy: animal × phase × condition.
DA: animal × phase × step (Wilcoxon on Δp, BH within model × phase × step).
Join key: phase × destination condition × raw_syllable_id.
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--syllable-csv", type=Path, default=DEFAULT_SYLL)
    ap.add_argument("--movement-csv", type=Path, default=DEFAULT_MOVE)
    ap.add_argument("--immobile-csv", type=Path, default=DEFAULT_STILL)
    ap.add_argument("--da-csv", type=Path, default=DEFAULT_DA)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--model", type=str, default=str(LOCKED["model"]))
    args = ap.parse_args(argv)

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    model = str(args.model)
    print(f"Loading locked syllables model={model} (all conditions)", flush=True)
    syll = load_locked_syllable_bouts(args.syllable_csv, model=model, condition=None)
    print(f"syllable bouts={len(syll):,}", flush=True)
    move = pd.read_csv(args.movement_csv, usecols=list(AMB_COLS))
    still = pd.read_csv(args.immobile_csv, usecols=list(AMB_COLS))
    bouts, _sessions = build_overlap_tables(syll, move, still)
    occ = occupancy_from_bouts(bouts)
    occ.to_csv(out / "occupancy_per_animal_syllable.csv", index=False)
    tests = occupancy_tests(occ)
    tests.to_csv(out / "occupancy_tests.csv", index=False)
    da = pd.read_csv(args.da_csv)
    joined = join_da_occupancy(da, tests, model=model)
    joined.to_csv(out / "da_occupancy_join.csv", index=False)
    summary = set_overlap_summary(joined)
    summary.to_csv(out / "da_occupancy_set_summary.csv", index=False)
    signed = signed_overlap_summary(joined)
    signed.to_csv(out / "da_occupancy_signed_summary.csv", index=False)
    blob = {
        "model": model,
        "occupancy_join": "destination_condition",
        "n_occupancy_rows": int(len(occ)),
        "n_occupancy_tests": int(len(tests)),
        "n_join_rows": int(len(joined)),
        "not": ["tx", "investigation", "same_contrast_as_DA"],
    }
    (out / "run_summary.json").write_text(json.dumps(blob, indent=2), encoding="utf-8")
    (out / "INFO_occupancy_da_join.md").write_text(_info_md(), encoding="utf-8")
    print(f"Wrote occupancy n={len(occ):,} tests={len(tests)} join={len(joined)} -> {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
