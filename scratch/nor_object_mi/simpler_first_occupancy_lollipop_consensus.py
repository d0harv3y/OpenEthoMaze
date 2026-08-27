"""Cross-model consensus of DA lollipop × dest-matched locomotor occupancy.

Ids are not portable. Consensus is the *pattern*: among DA FDR hits, what
fraction are move- vs still-enriched in the DA step's destination condition,
across 21 kpMS models.

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/simpler_first_occupancy_lollipop_consensus.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.occupancy_lollipop import (  # noqa: E402
    consensus_across_models,
    join_da_occupancy,
    occupancy_tests,
    set_overlap_summary,
)
from nor_object_mi.simpler_first_syll_ambulation_overlap import (  # noqa: E402
    AMB_COLS,
    DEFAULT_MOVE,
    DEFAULT_STILL,
    DEFAULT_SYLL,
)
from nor_object_mi.syll_ambulation_overlap import (  # noqa: E402
    bout_occupancy_on_raster,
    occupancy_from_frame_counts,
    locomotor_raster,
)

DEFAULT_DA = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_da\da_syllable_tests_long.csv"
)
DEFAULT_OUT = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_occupancy_da_consensus"
)

SYLL_USE = (
    "model",
    "animal_id",
    "raw_session",
    "phase_layer",
    "condition_layer",
    "tx",
    "sex",
    "raw_syllable_id",
    "row_start",
    "row_end_exclusive",
)


def _session_n_frames(move: pd.DataFrame, still: pd.DataFrame) -> dict[tuple[str, object], int]:
    out: dict[tuple[str, object], int] = {}
    for df in (move, still):
        if df.empty:
            continue
        ends = pd.to_numeric(df["row_end_exclusive"], errors="coerce")
        tmp = df.assign(_end=ends)
        for (aid, sess), g in tmp.groupby(["animal_id", "raw_session"], sort=False):
            n = int(np.nanmax(g["_end"].to_numpy())) if g["_end"].notna().any() else 0
            key = (str(aid), sess)
            out[key] = max(out.get(key, 0), n)
    return out


def _build_rasters(
    move: pd.DataFrame,
    still: pd.DataFrame,
) -> dict[tuple[str, object], np.ndarray]:
    n_map = _session_n_frames(move, still)
    move_g = move.groupby(["animal_id", "raw_session"], sort=False)
    still_g = still.groupby(["animal_id", "raw_session"], sort=False)
    empty = move.iloc[0:0]
    rasters: dict[tuple[str, object], np.ndarray] = {}
    for (aid, sess), n in n_map.items():
        try:
            mv = move_g.get_group((aid, sess))
        except KeyError:
            try:
                mv = move_g.get_group((str(aid), sess))
            except KeyError:
                mv = empty
        try:
            st = still_g.get_group((aid, sess))
        except KeyError:
            try:
                st = still_g.get_group((str(aid), sess))
            except KeyError:
                st = empty
        rasters[(str(aid), sess)] = locomotor_raster(mv, st, n_frames=max(n, 1))
    return rasters


def _info_md() -> str:
    return """# INFO — occupancy × DA consensus across models

`raw_syllable_id` is not portable. This run does **not** claim that id 11 in
ss-50 is the same syllable in another paramscan.

Consensus is the pattern among DA FDR hits: fraction that are locomotor
move-enriched vs still-enriched in the DA step's destination condition
(occupancy t vs 0, BH within model × phase × condition).

Not tx. Not investigation. Occupancy and DA remain different contrasts.
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--syllable-csv", type=Path, default=DEFAULT_SYLL)
    ap.add_argument("--movement-csv", type=Path, default=DEFAULT_MOVE)
    ap.add_argument("--immobile-csv", type=Path, default=DEFAULT_STILL)
    ap.add_argument("--da-csv", type=Path, default=DEFAULT_DA)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    print("Loading movement/immobile (all conditions)", flush=True)
    move = pd.read_csv(args.movement_csv, usecols=list(AMB_COLS))
    still = pd.read_csv(args.immobile_csv, usecols=list(AMB_COLS))
    move["animal_id"] = move["animal_id"].astype(str)
    still["animal_id"] = still["animal_id"].astype(str)
    rasters = _build_rasters(move, still)
    print(f"rasters={len(rasters)}", flush=True)

    parts: list[pd.DataFrame] = []
    n_kept = 0
    for chunk in pd.read_csv(args.syllable_csv, usecols=list(SYLL_USE), chunksize=400_000):
        sub = chunk.copy().reset_index(drop=True)
        sub["animal_id"] = sub["animal_id"].astype(str)
        n_move = np.zeros(len(sub), dtype=np.int32)
        n_still = np.zeros(len(sub), dtype=np.int32)
        starts = pd.to_numeric(sub["row_start"], errors="coerce").to_numpy()
        ends = pd.to_numeric(sub["row_end_exclusive"], errors="coerce").to_numpy()
        for (aid, sess), g in sub.groupby(["animal_id", "raw_session"], sort=False):
            rast = rasters.get((str(aid), sess))
            if rast is None:
                continue
            ii = g.index.to_numpy()
            ok = np.isfinite(starts[ii]) & np.isfinite(ends[ii])
            if not np.any(ok):
                continue
            use = ii[ok]
            nm, ns = bout_occupancy_on_raster(starts[use].astype(np.int64), ends[use].astype(np.int64), rast)
            n_move[use] = nm
            n_still[use] = ns
        sub["n_move_frames"] = n_move
        sub["n_still_frames"] = n_still
        g = (
            sub.groupby(
                [
                    "model",
                    "animal_id",
                    "raw_session",
                    "phase_layer",
                    "condition_layer",
                    "tx",
                    "sex",
                    "raw_syllable_id",
                ],
                sort=False,
            )[["n_move_frames", "n_still_frames"]]
            .sum()
            .reset_index()
        )
        parts.append(g)
        n_kept += int(len(sub))
        print(f"  syll rows={n_kept:,} groups={len(g):,}", flush=True)
    counts = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    if not counts.empty:
        counts = (
            counts.groupby(
                [
                    "model",
                    "animal_id",
                    "raw_session",
                    "phase_layer",
                    "condition_layer",
                    "tx",
                    "sex",
                    "raw_syllable_id",
                ],
                sort=False,
            )[["n_move_frames", "n_still_frames"]]
            .sum()
            .reset_index()
        )
    occ = occupancy_from_frame_counts(counts)
    print(f"occupancy rows={len(occ):,}", flush=True)
    tests = occupancy_tests(occ)
    tests.to_csv(out / "occupancy_tests_all_models.csv", index=False)
    da = pd.read_csv(args.da_csv)
    summaries: list[pd.DataFrame] = []
    for model, ot in tests.groupby("model", sort=False):
        joined = join_da_occupancy(da, ot, model=str(model))
        if joined.empty:
            continue
        summ = set_overlap_summary(joined)
        summaries.append(summ)
        print(f"  {model} join_rows={len(joined)}", flush=True)
    summary = pd.concat(summaries, ignore_index=True) if summaries else pd.DataFrame()
    summary.to_csv(out / "da_occupancy_set_summary_all_models.csv", index=False)
    cons = consensus_across_models(summary)
    cons.to_csv(out / "da_occupancy_consensus.csv", index=False)
    blob = {
        "n_models": int(tests["model"].nunique()) if not tests.empty else 0,
        "n_occupancy_tests": int(len(tests)),
        "n_summary_rows": int(len(summary)),
        "not": ["portable_ids", "tx", "investigation"],
        "consensus": "pattern_frac_da_hits_move_vs_still",
    }
    (out / "run_summary_consensus.json").write_text(json.dumps(blob, indent=2), encoding="utf-8")
    (out / "INFO_occupancy_da_consensus.md").write_text(_info_md(), encoding="utf-8")
    print(f"Wrote consensus n_models={blob['n_models']} -> {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
