"""Syllable-bout ∩ movement/immobile association (locked kpMS model).

Does **not** Pearson n_move vs n_syll (two clocks). Joins intervals.

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/simpler_first_syll_ambulation_overlap.py
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.simpler_first_protocol_prologue import (  # noqa: E402
    PHASES,
    pearson_pair,
    ttest_one_sample,
    ttest_paired,
)
from nor_object_mi.simpler_first_q1 import LOCKED, SEX_ORDER  # noqa: E402
from nor_object_mi.syll_ambulation_overlap import (  # noqa: E402
    annotate_syllable_bouts,
    session_association,
)

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
DEFAULT_OUT = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_syll_ambulation_overlap"
)

SYLL_COLS = (
    "model",
    "animal_id",
    "raw_session",
    "phase_layer",
    "condition_layer",
    "tx",
    "sex",
    "bout_index",
    "raw_syllable_id",
    "row_start",
    "row_end_exclusive",
    "bout_frames",
    "bout_duration_s",
    "bout_mean_speed_mps",
)
AMB_COLS = (
    "animal_id",
    "raw_session",
    "phase_layer",
    "condition_layer",
    "row_start",
    "row_end_exclusive",
)


def _hit(p: float) -> bool:
    return math.isfinite(p) and p < 0.05


def load_locked_syllable_bouts(
    path: Path,
    *,
    model: str,
    condition: str | None = CONDITION,
) -> pd.DataFrame:
    chunks: list[pd.DataFrame] = []
    kept = 0
    for chunk in pd.read_csv(path, usecols=list(SYLL_COLS), chunksize=250_000):
        sub = chunk[chunk["model"] == model]
        if condition is not None:
            sub = sub[sub["condition_layer"] == condition]
        if not sub.empty:
            chunks.append(sub)
            kept += len(sub)
        print(f"  syll chunk kept={kept:,}", flush=True)
    if not chunks:
        return pd.DataFrame(columns=list(SYLL_COLS))
    out = pd.concat(chunks, ignore_index=True)
    out["animal_id"] = out["animal_id"].astype(str)
    return out


def _sex_slices(g: pd.DataFrame):
    yield "pooled", g
    for sex in SEX_ORDER:
        yield sex, g[g["sex"] == sex]


def build_overlap_tables(
    syll: pd.DataFrame,
    move: pd.DataFrame,
    still: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    move = move.copy()
    still = still.copy()
    syll = syll.copy()
    for df in (move, still, syll):
        df["animal_id"] = df["animal_id"].astype(str)
    move_g = move.groupby(["animal_id", "raw_session"], sort=False)
    still_g = still.groupby(["animal_id", "raw_session"], sort=False)
    empty_amb = move.iloc[0:0]
    session_rows: list[dict[str, object]] = []
    bout_parts: list[pd.DataFrame] = []
    groups = list(syll.groupby(["animal_id", "raw_session", "phase_layer"], sort=False))
    n_jobs = len(groups)
    for i, ((aid, sess, phase), sy) in enumerate(groups, start=1):
        if i == 1 or i % 50 == 0 or i == n_jobs:
            print(f"  sessions {i}/{n_jobs}", flush=True)
        try:
            mv = move_g.get_group((aid, sess))
        except KeyError:
            mv = empty_amb
        try:
            st = still_g.get_group((aid, sess))
        except KeyError:
            st = empty_amb
        ann = annotate_syllable_bouts(sy, mv, st)
        bout_parts.append(ann)
        meta = ann.iloc[0]
        assoc = session_association(ann)
        session_rows.append(
            {
                "animal_id": aid,
                "raw_session": sess,
                "phase_layer": phase,
                "condition_layer": str(sy["condition_layer"].iloc[0])
                if "condition_layer" in sy.columns
                else CONDITION,
                "tx": meta["tx"],
                "sex": meta["sex"],
                "model": meta["model"],
                **assoc,
            }
        )
    bouts = pd.concat(bout_parts, ignore_index=True) if bout_parts else pd.DataFrame()
    sessions = pd.DataFrame(session_rows)
    if not sessions.empty:
        sessions["phase_layer"] = pd.Categorical(
            sessions["phase_layer"], categories=list(PHASES), ordered=True
        )
        sessions = sessions.sort_values(["phase_layer", "animal_id"]).reset_index(drop=True)
    return bouts, sessions


def association_tests(sessions: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    if sessions.empty:
        return pd.DataFrame()
    for phase, g in sessions.groupby("phase_layer", observed=True):
        for sex, gs in _sex_slices(g):
            rec_i = ttest_one_sample(gs["i_syllable_locomotor_bits"].to_numpy())
            rec_e = ttest_one_sample(gs["enrich_unweighted_move"].to_numpy())
            rec_d = ttest_paired(
                gs["median_duration_s_majority_move"].to_numpy(),
                gs["median_duration_s_majority_still"].to_numpy(),
            )
            rec_p = pearson_pair(
                gs["p_session_move"].to_numpy(),
                gs["mean_bout_move_frac"].to_numpy(),
            )
            specs = (
                (
                    rec_i,
                    "i_syllable_locomotor_vs_0",
                    rec_i["test"],
                    "one-sample t on I(syllable; locomotor); I≥0 so this is a magnitude check, not a signed association",
                ),
                (
                    rec_e,
                    "unweighted_bout_move_enrich_vs_0",
                    rec_e["test"],
                    "mean bout P(move) minus session P(move); nonzero iff bout durations differ by locomotor mix",
                ),
                (
                    rec_d,
                    "median_duration_majority_move_vs_still",
                    rec_d["test"],
                    "paired t of median syllable-bout duration (majority-move minus majority-still)",
                ),
            )
            for rec, contrast, test_name, note in specs:
                rows.append(
                    {
                        "phase_layer": str(phase),
                        "sex": sex,
                        "contrast": contrast,
                        "n": rec["n"],
                        "mean_delta": rec["mean_delta"],
                        "median_delta": rec["median_delta"],
                        "stat": rec["stat"],
                        "p": rec["p"],
                        "hit_p05": _hit(float(rec["p"])),
                        "test": test_name,
                        "note": note,
                    }
                )
            rows.append(
                {
                    "phase_layer": str(phase),
                    "sex": sex,
                    "contrast": "session_p_move_vs_unweighted_bout_frac",
                    "n": int(rec_p["n"]),
                    "mean_delta": float("nan"),
                    "median_delta": float("nan"),
                    "stat": float(rec_p["pearson_r"]),
                    "p": float(rec_p["p"]),
                    "hit_p05": _hit(float(rec_p["p"])),
                    "test": "pearson",
                    "note": "litmus: frame-weighted identity would be r=1; unweighted can leave the diagonal",
                }
            )
    return pd.DataFrame(rows)


def _info_md() -> str:
    return """# INFO — syllable ∩ locomotor overlap

## Why not Pearson n_move vs n_syll?

Those are **two clocks** (hysteresis vs kpMS RLE). Session counts can correlate
because both scale with time, without any shared boundaries.

Syllable labels **tile** the session, so “are syllables happening during
movement?” is tautological. The join is **which** syllable and **how long**
the bout is, given locomotor state.

## Join

For each locked-model syllable bout `[row_start, row_end_exclusive)` count
overlapping frames in movement vs immobile bout tables (spot node). Exclusive ends.

## Session scalars

| Column | Meaning |
|--------|---------|
| `p_session_move` | frame P(movement) among labeled frames |
| `mean_bout_move_frac` | **unweighted** mean over bouts of P(move\\|bout) |
| `enrich_unweighted_move` | unweighted mean − session P(move) |
| `i_syllable_locomotor_bits` | I(raw_syllable_id ; {move, still}) |
| `cramers_v` | k×2 Cramér V on the same table |
| `delta_median_duration_s_move_minus_still` | majority-move vs majority-still bout duration |

## Inferential (mean/interval)

Within sex (and pooled): one-sample t on I and on enrich; paired t on median
durations; Pearson of session P(move) vs unweighted bout-mean P(move).

Locked model: `paramscan_s1-1e8_s2-1e5_ss-50`. Condition: `novel_obj`.
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--syllable-csv", type=Path, default=DEFAULT_SYLL)
    ap.add_argument("--movement-csv", type=Path, default=DEFAULT_MOVE)
    ap.add_argument("--immobile-csv", type=Path, default=DEFAULT_STILL)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--model", type=str, default=str(LOCKED["model"]))
    ap.add_argument("--write-bout-csv", action="store_true", help="Write per-bout overlap (large)")
    args = ap.parse_args(argv)

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    model = str(args.model)
    print(f"Loading locked syllables model={model}", flush=True)
    syll = load_locked_syllable_bouts(args.syllable_csv, model=model, condition=CONDITION)
    print(f"syllable bouts={len(syll):,}", flush=True)
    move = pd.read_csv(args.movement_csv, usecols=list(AMB_COLS))
    still = pd.read_csv(args.immobile_csv, usecols=list(AMB_COLS))
    move = move[move["condition_layer"] == CONDITION]
    still = still[still["condition_layer"] == CONDITION]
    print(f"move bouts={len(move):,} still bouts={len(still):,}", flush=True)

    bouts, sessions = build_overlap_tables(syll, move, still)
    tests = association_tests(sessions)
    if args.write_bout_csv:
        bouts.to_csv(out / "syll_locomotor_bout_overlap.csv", index=False)
    sessions.to_csv(out / "syll_locomotor_session.csv", index=False)
    tests.to_csv(out / "syll_locomotor_association.csv", index=False)
    summary = {
        "model": model,
        "condition_layer": CONDITION,
        "n_syll_bouts": int(len(bouts)),
        "n_sessions": int(len(sessions)),
        "join": "interval_overlap_exclusive_end",
        "not": "pearson_n_move_vs_n_syll",
    }
    (out / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out / "INFO_syll_ambulation_overlap.md").write_text(_info_md(), encoding="utf-8")
    print(f"Wrote {len(sessions)} sessions {len(tests)} assoc rows -> {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
