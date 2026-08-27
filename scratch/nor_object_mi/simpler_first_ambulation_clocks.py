"""Movement-bout clock vs syllable-bout clock (session grain).

A movement bout is displacement hysteresis (IMPRESS `fore`). A syllable bout
is a contiguous kpMS label run. They are not the same unit. NOR ladders have
bout duration, not bout speed — this run compares clocks (n, duration) and
movement kinematics, not a made-up syllable speed.

Grain: animal × phase × novel_obj (full session).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.simpler_first_classic_dr import spearman_pair  # noqa: E402
from nor_object_mi.simpler_first_object_prox import PHASES as PHASE_TAGS  # noqa: E402
from nor_object_mi.simpler_first_q1 import LOCKED  # noqa: E402

CONDITION = "novel_obj"
PHASES = ("NOR_BL", "NOR_TX", "NOR_REC3hr", "NOR_REC11hr")
GRAIN = f"animal × {{phase}} × {CONDITION} (full session)"
FPS = 30.0
ASSOC_PAIRS = (
    ("n_move_bouts", "n_syll_bouts", "n_move_vs_n_syll"),
    ("median_move_duration_s", "median_syll_duration_s", "dur_move_vs_dur_syll"),
    ("median_move_speed_mps", "session_mean_speed_mps", "bout_speed_vs_session_speed"),
    ("sum_move_distance_m", "session_distance_m", "bout_dist_vs_session_dist"),
    ("session_mean_speed_mps", "n_syll_bouts", "session_speed_vs_n_syll"),
    ("session_mean_speed_mps", "dr_classic", "session_speed_vs_classic_dr"),
    ("n_move_bouts", "dr_classic", "n_move_vs_classic_dr"),
)

DEFAULT_LONG = Path(r"C:\Users\admin\code\archive\IMPRESS\my_nor_wip\my_NOR_results__ambulation_temporal_long.csv")
DEFAULT_SESS = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017" r"\thresholded-signal-bouts\impress_ambulation.csv")
DEFAULT_DR = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017" r"\_nor_object_mi\simpler_first_classic_dr\classic_dr_paired.csv")
DEFAULT_ART = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017\_nor_object_mi")


def movement_bout_session(long_df: pd.DataFrame, *, condition: str = CONDITION) -> pd.DataFrame:
    """One row per animal × phase: movement-bout counts, duration, speed, distance."""
    df = long_df.copy()
    df.columns = [str(c).strip().replace(" ", "_") for c in df.columns]
    df = df.rename(columns={"ID": "animal_id", "phase_layer": "phase_layer"})
    df["animal_id"] = df["animal_id"].astype(str)
    b = df[(df["level"] == "bout") & (df["condition_layer"] == condition) & (df["phase_layer"].isin(PHASES))].copy()
    if b.empty:
        return b.iloc[0:0].copy()
    speed = b[b["metric"] == "mean_speed_mps"][["animal_id", "phase_layer", "index", "duration_s", "value"]].rename(columns={"value": "mean_speed_mps"})
    dist = b[b["metric"] == "distance_m"][["animal_id", "phase_layer", "index", "value"]].rename(columns={"value": "distance_m"})
    mx = b[b["metric"] == "max_speed_mps"][["animal_id", "phase_layer", "index", "value"]].rename(columns={"value": "max_speed_mps"})
    mb = speed.merge(dist, on=["animal_id", "phase_layer", "index"], how="outer")
    mb = mb.merge(mx, on=["animal_id", "phase_layer", "index"], how="left")
    out = mb.groupby(["animal_id", "phase_layer"], as_index=False).agg(
        n_move_bouts=("index", "nunique"),
        median_move_duration_s=("duration_s", "median"),
        median_move_speed_mps=("mean_speed_mps", "median"),
        median_move_max_speed_mps=("max_speed_mps", "median"),
        sum_move_distance_m=("distance_m", "sum"),
    )
    return out


def syllable_bout_session(bouts: pd.DataFrame, *, fps: float = FPS, condition: str = CONDITION) -> pd.DataFrame:
    """One row per animal × phase: syllable-bout count and duration (no speed on NOR ladders)."""
    sub = bouts[bouts["condition_layer"] == condition].copy()
    if sub.empty:
        return sub.iloc[0:0].copy()
    sub["animal_id"] = sub["animal_id"].astype(str)
    frames = pd.to_numeric(sub["bout_frames"], errors="coerce")
    sub = sub.assign(syll_duration_s=frames / float(fps))
    out = sub.groupby(["animal_id", "phase_layer"], as_index=False).agg(
        n_syll_bouts=("bout_frames", "size"),
        median_syll_duration_s=("syll_duration_s", "median"),
        mean_syll_duration_s=("syll_duration_s", "mean"),
        n_syll_frames=("bout_frames", "sum"),
    )
    return out


def session_ambulation(sess: pd.DataFrame, *, condition: str = CONDITION) -> pd.DataFrame:
    df = sess.copy()
    df.columns = [str(c).strip().replace(" ", "_") for c in df.columns]
    df = df.rename(columns={"ID": "animal_id"})
    df["animal_id"] = df["animal_id"].astype(str)
    sub = df[(df["condition_layer"] == condition) & (df["phase_layer"].isin(PHASES))]
    piv = sub.pivot_table(
        index=["animal_id", "phase_layer", "sex", "treatment_group"],
        columns="metric",
        values="value",
        aggfunc="first",
    ).reset_index()
    piv.columns.name = None
    return piv.rename(
        columns={
            "treatment_group": "tx",
            "distance_m": "session_distance_m",
            "mean_speed_mps": "session_mean_speed_mps",
            "time_immobile_s": "session_time_immobile_s",
        }
    )


def association_table(paired: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for phase, g in paired.groupby("phase_layer", sort=True):
        for xcol, ycol, contrast in ASSOC_PAIRS:
            rec = spearman_pair(g[xcol].to_numpy(), g[ycol].to_numpy())
            p = rec["p"]
            rows.append(
                {
                    "phase_layer": phase,
                    "contrast": contrast,
                    "x": xcol,
                    "y": ycol,
                    "n": int(rec["n"]),
                    "spearman_rho": rec["spearman_rho"],
                    "p": p,
                    "hit_p05": bool(math.isfinite(p) and float(p) < 0.05),
                    "test": "spearman",
                    "grain": GRAIN.format(phase=phase),
                }
            )
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ambulation-long", type=Path, default=DEFAULT_LONG)
    ap.add_argument("--ambulation-session", type=Path, default=DEFAULT_SESS)
    ap.add_argument("--classic-dr", type=Path, default=DEFAULT_DR)
    ap.add_argument("--ensemble-root", type=Path, default=DEFAULT_ART)
    ap.add_argument("--model", type=str, default=str(LOCKED["model"]))
    ap.add_argument("--out-dir", type=Path, default=None)
    args = ap.parse_args(argv)

    out = args.out_dir or (args.ensemble_root / "simpler_first_ambulation_clocks")
    out.mkdir(parents=True, exist_ok=True)

    long_df = pd.read_csv(
        args.ambulation_long,
        usecols=[
            "ID",
            "phase layer",
            "condition layer",
            "level",
            "index",
            "duration_s",
            "metric",
            "value",
        ],
    )
    move = movement_bout_session(long_df)
    sess = session_ambulation(pd.read_csv(args.ambulation_session))
    syll_parts: list[pd.DataFrame] = []
    art = args.ensemble_root / args.model
    for phase, tag in PHASE_TAGS:
        csv = art / tag / "ladder_bout_features.csv"
        if not csv.exists():
            print(f"MISSING {csv}", flush=True)
            continue
        print(f"syllable {phase}", flush=True)
        bouts = pd.read_csv(
            csv,
            usecols=["animal_id", "phase_layer", "condition_layer", "bout_frames"],
        )
        syll_parts.append(syllable_bout_session(bouts))
    syll = pd.concat(syll_parts, ignore_index=True) if syll_parts else pd.DataFrame()

    paired = sess.merge(move, on=["animal_id", "phase_layer"], how="left")
    paired = paired.merge(syll, on=["animal_id", "phase_layer"], how="left")
    if args.classic_dr.exists():
        dr = pd.read_csv(args.classic_dr, usecols=["animal_id", "phase_layer", "dr_classic", "dr_object_prox"])
        dr["animal_id"] = dr["animal_id"].astype(str)
        paired = paired.merge(dr, on=["animal_id", "phase_layer"], how="left")
    else:
        paired["dr_classic"] = np.nan
        paired["dr_object_prox"] = np.nan

    assoc = association_table(paired) if not paired.empty else pd.DataFrame()
    paired.to_csv(out / "clock_metrics_per_animal.csv", index=False)
    if not assoc.empty:
        assoc.to_csv(out / "clock_association.csv", index=False)

    payload = {
        "condition_layer": CONDITION,
        "syllable_model": args.model,
        "fps": FPS,
        "movement_keypoint": "fore",
        "n_paired_rows": int(len(paired)),
        "n_assoc_rows": int(len(assoc)),
        "path": str(out),
        "inputs": {
            "ambulation_long": str(args.ambulation_long),
            "ambulation_session": str(args.ambulation_session),
            "classic_dr": str(args.classic_dr),
            "syllable_model": args.model,
        },
        "note": "NOR ladders have no bout_mean_speed_mps; syllable side is duration/count only.",
    }
    (out / "run_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if not assoc.empty:
        print(assoc[["phase_layer", "contrast", "n", "spearman_rho", "hit_p05"]].to_string(index=False), flush=True)
    print(json.dumps({"path": str(out), "n_paired_rows": int(len(paired))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
