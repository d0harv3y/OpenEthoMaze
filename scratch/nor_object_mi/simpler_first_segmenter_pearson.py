"""Grain-1 Pearson block heatmap of two session segmenters.

Not lagged CCF. Not Pearson n_move vs n_syll as a clock identity.
Locked kpMS × novel_obj. Frame-weighted mean speed is the kinematics litmus.

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/simpler_first_segmenter_pearson.py
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

from nor_object_mi.segmenter_pearson import (  # noqa: E402
    FEATURES,
    join_session_features,
    pearson_long,
)
from nor_object_mi.simpler_first_protocol_prologue import PHASES  # noqa: E402
from nor_object_mi.simpler_first_q1 import LOCKED  # noqa: E402

CONDITION = "novel_obj"
DEFAULT_SYLL = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_syllable_kinematics\syllable_bout_kinematics.csv"
)
DEFAULT_MOVE = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_movement_kinematics\movement_bout_kinematics.csv"
)
DEFAULT_STILL = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_movement_kinematics\immobile_bout_kinematics.csv"
)
DEFAULT_OVERLAP = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_syll_ambulation_overlap\syll_locomotor_session.csv"
)
DEFAULT_OUT = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_segmenter_pearson"
)

SYLL_COLS = (
    "model",
    "animal_id",
    "raw_session",
    "phase_layer",
    "condition_layer",
    "tx",
    "sex",
    "raw_syllable_id",
    "bout_frames",
    "bout_duration_s",
    "bout_mean_speed_mps",
)
AMB_COLS = (
    "animal_id",
    "raw_session",
    "phase_layer",
    "condition_layer",
    "bout_frames",
    "bout_duration_s",
    "bout_mean_speed_mps",
)


def load_locked_syll(path: Path, *, model: str, condition: str) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    kept = 0
    for chunk in pd.read_csv(path, usecols=list(SYLL_COLS), chunksize=250_000):
        sub = chunk[(chunk["model"] == model) & (chunk["condition_layer"] == condition)]
        if not sub.empty:
            parts.append(sub)
            kept += len(sub)
        print(f"  syll kept={kept:,}", flush=True)
    if not parts:
        return pd.DataFrame(columns=list(SYLL_COLS))
    out = pd.concat(parts, ignore_index=True)
    out["animal_id"] = out["animal_id"].astype(str)
    return out


def _info_md() -> str:
    return """# INFO — segmenter Pearson (grain 1)

## Grain

animal × phase × `novel_obj` (locked kpMS). Between-session Pearson of
**session summaries**, not within-session lagged cross-correlation.

## Segmenters

Same frames, two partitions: hysteresis movement|immobile vs kpMS syllable RLE.
Not two clocks; they do not have independent time bases.

## Blocks

1. locomotor — occupancy, bout counts, median durations
2. syllable — bout count, id richness, median duration, Shannon of ids
3. join — I(syllable; locomotor), Cramér V, unweighted enrich, majority-duration Δ
4. kinematics — frame-weighted mean speed from syllable bouts vs movement bouts

**Litmus:** Pearson(speed_syll, speed_move). Both reconstruct ambulation from
the same pose; r should sit near 1. Diagonal cells are self-correlation.

Heatmap is descriptive. Uncorrected p is in `pearson_long.csv`. Not DA.
Not heading. Do not read n_move vs n_syll as paired events.
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--syllable-csv", type=Path, default=DEFAULT_SYLL)
    ap.add_argument("--movement-csv", type=Path, default=DEFAULT_MOVE)
    ap.add_argument("--immobile-csv", type=Path, default=DEFAULT_STILL)
    ap.add_argument("--overlap-csv", type=Path, default=DEFAULT_OVERLAP)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--model", type=str, default=str(LOCKED["model"]))
    args = ap.parse_args(argv)

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    model = str(args.model)
    print(f"Loading locked syllables model={model}", flush=True)
    syll = load_locked_syll(args.syllable_csv, model=model, condition=CONDITION)
    print(f"syllable bouts={len(syll):,}", flush=True)
    move = pd.read_csv(args.movement_csv, usecols=list(AMB_COLS))
    still = pd.read_csv(args.immobile_csv, usecols=list(AMB_COLS))
    move = move[move["condition_layer"] == CONDITION].copy()
    still = still[still["condition_layer"] == CONDITION].copy()
    move["animal_id"] = move["animal_id"].astype(str)
    still["animal_id"] = still["animal_id"].astype(str)
    overlap = pd.read_csv(args.overlap_csv)
    overlap["animal_id"] = overlap["animal_id"].astype(str)
    print(f"move={len(move):,} still={len(still):,} overlap sessions={len(overlap):,}", flush=True)

    sessions = join_session_features(overlap, syll, move, still)
    missing = [c for c in FEATURES if c not in sessions.columns]
    if missing:
        raise KeyError(f"session table missing {missing}")
    sessions.to_csv(out / "segmenter_session_features.csv", index=False)

    longs: list[pd.DataFrame] = []
    for phase in PHASES:
        g = sessions[sessions["phase_layer"] == phase]
        print(f"  {phase} n={len(g)}", flush=True)
        longs.append(pearson_long(g, phase=str(phase)))
    long = pd.concat(longs, ignore_index=True)
    long.to_csv(out / "pearson_long.csv", index=False)
    summary = {
        "model": model,
        "condition_layer": CONDITION,
        "grain": "animal × phase × novel_obj",
        "n_sessions": int(len(sessions)),
        "features": list(FEATURES),
        "litmus": "pearson(speed_syll_mps, speed_move_mps)",
        "not": ["lagged_ccf", "pearson_n_move_vs_n_syll_as_identity"],
    }
    (out / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out / "INFO_segmenter_pearson.md").write_text(_info_md(), encoding="utf-8")
    print(f"Wrote {len(sessions)} sessions {len(long)} pairs -> {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
