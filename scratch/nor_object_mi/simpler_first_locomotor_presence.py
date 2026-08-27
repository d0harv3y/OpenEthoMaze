"""Presence steps on hysteresis move|still (no kpMS).

Primary: no_obj → identical_obj. Protocol t of Δ vs 0 within sex.

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/simpler_first_locomotor_presence.py
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

from nor_object_mi.locomotor_presence import (  # noqa: E402
    PRIMARY_METRICS,
    PRIMARY_STEP,
    hunt_tests,
    paired_step_deltas,
    session_locomotor_table,
)
from nor_object_mi.simpler_first_presence import NEAR_R_M  # noqa: E402
from nor_object_mi.simpler_first_syll_ambulation_overlap import (  # noqa: E402
    DEFAULT_MOVE,
    DEFAULT_STILL,
)

USECOLS = (
    "animal_id",
    "raw_session",
    "phase_layer",
    "condition_layer",
    "tx",
    "sex",
    "bout_frames",
    "bout_duration_s",
    "bout_mean_speed_mps",
    "bout_mean_dist_any_m",
)
DEFAULT_OUT = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_locomotor_presence"
)


def _info_md() -> str:
    return """# INFO — locomotor presence (hysteresis segmenter)

## What this is

Paired **presence** (`no_obj → identical_obj`) on the original movement|immobile
clock (spot-node hysteresis), not kpMS syllables. Two categories tile labeled
frames: movement bouts vs immobile complement.

Grain: animal × phase × condition. Scalars include frame P(move), bout counts,
median durations, frame-weighted movement speed, and bout-mean near rate
(< 0.10 m).

**Inferential (protocol):** one-sample t of (identical − no_obj) vs 0 within
sex (treatments pooled). BH family = 5 metrics within sex × phase. Novelty and
span steps are companions (uncorrected). Tx coda: Welch ANOVA of Δ P(move) by
tx (not in the BH family).

## What this is not

Not syllable DA. Not investigation (near is bout-mean). Not a 21-model grid —
there is one locomotor segmenter.
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--movement-csv", type=Path, default=DEFAULT_MOVE)
    ap.add_argument("--immobile-csv", type=Path, default=DEFAULT_STILL)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--near-m", type=float, default=NEAR_R_M)
    args = ap.parse_args(argv)

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    print("Loading movement / immobile kinematics", flush=True)
    move = pd.read_csv(args.movement_csv, usecols=list(USECOLS))
    still = pd.read_csv(args.immobile_csv, usecols=list(USECOLS))
    sessions = session_locomotor_table(move, still, r_m=float(args.near_m))
    sessions.to_csv(out / "session_locomotor_scalars.csv", index=False)
    paired = paired_step_deltas(sessions)
    paired.to_csv(out / "paired_step_deltas.csv", index=False)
    tests = hunt_tests(paired)
    tests.to_csv(out / "locomotor_presence_tests.csv", index=False)
    prim = tests[tests["family"] == "primary"] if not tests.empty else tests
    n_fdr = int(prim["hit_fdr05"].sum()) if not prim.empty else 0
    blob = {
        "segmenter": "hysteresis_move_still",
        "primary_step": PRIMARY_STEP,
        "primary_metrics": list(PRIMARY_METRICS),
        "near_m": float(args.near_m),
        "n_sessions": int(len(sessions)),
        "n_paired": int(len(paired)),
        "n_primary_fdr": n_fdr,
        "not": ["kpMS", "syllable_DA", "investigation"],
    }
    (out / "run_summary.json").write_text(json.dumps(blob, indent=2), encoding="utf-8")
    (out / "INFO_locomotor_presence.md").write_text(_info_md(), encoding="utf-8")
    print(f"primary FDR hits={n_fdr} sessions={len(sessions)} -> {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
