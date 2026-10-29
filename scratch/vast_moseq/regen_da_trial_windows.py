"""VAST paired DA: trial-steps and session-steps (PROTOCOL-STRATA wire).

Trial-steps (within session, pair on trial_window):
  mid_early  : mid_t4-6  − early_t1-3
  late_mid   : late_t7-9 − mid_t4-6
  late_early : late_t7-9 − early_t1-3

Session-steps (within trial_window, pair on session):
  S02-S01 … S05-S04 sequential; S05-S01 long span.

Grain: animal × session × trial_window.
Composition: frame_share (sum bout_frames). Pass 1 = run-interval bouts only.

Wire: session · trial_window · trial_step · session_step
(not phase_layer / condition_layer / \"sessions as phases\").

Cohort: 2×2×2 (strain wt|tg × tx RBSF-1|n/a × sex F|M).

Regen:
  uv run python scratch/vast_moseq/regen_da_trial_windows.py \\
    --kinematics-csv D:/az-sd-vast_paramscan2026/_syllable_bout_kinematics/syllable_bout_kinematics.csv \\
    --signatures-csv D:/az-sd-vast_paramscan2026/_syllable_signatures/syllable_prototypes_clustered.csv \\
    --out-dir D:/az-sd-vast_paramscan2026/_da_trial_windows \\
    --meta-h5 D:/az-sd-vast_paramscan2026/vast_results_legacy.h5 \\
    --pause-cluster 40
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.simpler_first_da import (  # noqa: E402
    apply_bh_grouped,
    da_tests_from_deltas,
    paired_da_deltas,
)
from vast_moseq.cohort_meta import (  # noqa: E402
    DEFAULT_MANIFEST,
    attach_animal_meta,
    load_animal_meta,
    load_animal_meta_from_h5,
    norm_tx,
)
from vast_moseq.sliced_group_tests import sliced_mann_whitney_tests  # noqa: E402
from vast_moseq.vast_da_strat import da_tests_cohort_strat_from_deltas  # noqa: E402

DEFAULT_KIN = Path(
    r"D:\sack\AZ-SD-VAST-moseq"
    r"\syllable_bout_kinematics\syllable_bout_kinematics.csv"
)
DEFAULT_SIG = Path(
    r"D:\sack\AZ-SD-VAST-moseq"
    r"\syllable_signatures\syllable_prototypes_clustered.csv"
)
DEFAULT_OUT = Path(r"D:\sack\AZ-SD-VAST-moseq\_da_trial_windows")

TRIAL_RE = re.compile(r"-T(\d+)$")
WINDOWS: dict[str, range] = {
    "early_t1-3": range(1, 4),
    "mid_t4-6": range(4, 7),
    "late_t7-9": range(7, 10),
}
TRIAL_STEPS: tuple[tuple[str, str, str], ...] = (
    ("mid_early", "early_t1-3", "mid_t4-6"),
    ("late_mid", "mid_t4-6", "late_t7-9"),
    ("late_early", "early_t1-3", "late_t7-9"),
)
SESSION_STEPS: tuple[tuple[str, str, str], ...] = (
    ("S02-S01", "S01", "S02"),
    ("S03-S02", "S02", "S03"),
    ("S04-S03", "S03", "S04"),
    ("S05-S04", "S04", "S05"),
    ("S05-S01", "S01", "S05"),
)
SESSIONS = ("S01", "S02", "S03", "S04", "S05")
TRIAL_WINDOWS = ("early_t1-3", "mid_t4-6", "late_t7-9")
PAUSE_CLUSTER_DEFAULT = 13


def trial_from_key(kpms_key: str) -> int | None:
    m = TRIAL_RE.search(str(kpms_key))
    return int(m.group(1)) if m else None


def window_for_trial(trial: int) -> str | None:
    for name, rng in WINDOWS.items():
        if trial in rng:
            return name
    return None


def assign_windows(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "session" not in out.columns and "phase_layer" in out.columns:
        out = out.rename(columns={"phase_layer": "session"})
    trials = out["kpms_key"].map(trial_from_key)
    out["trial"] = trials
    out["trial_window"] = trials.map(lambda t: window_for_trial(int(t)) if t is not None else None)
    return out[out["trial_window"].notna()].copy()


def build_animal_window_table(df: pd.DataFrame) -> pd.DataFrame:
    """One row per animal × session × trial_window with syllable frame counts."""
    rows: list[dict[str, object]] = []
    keys = ["model", "animal_id", "session", "trial_window", "sex", "strain", "tx"]
    for key_vals, g in df.groupby(keys, sort=True):
        key_map = dict(zip(keys, key_vals if isinstance(key_vals, tuple) else (key_vals,)))
        counts: dict[int, float] = {}
        for sid, frames in zip(
            g["raw_syllable_id"].to_numpy(dtype=np.int64),
            g["bout_frames"].to_numpy(dtype=np.float64),
            strict=True,
        ):
            if not np.isfinite(frames) or frames <= 0:
                continue
            counts[int(sid)] = counts.get(int(sid), 0.0) + float(frames)
        rows.append({**key_map, "counts": counts, "n_frames": float(sum(counts.values()))})
    return pd.DataFrame(rows)


def _finalize_step_deltas(
    dtab: pd.DataFrame,
    *,
    step_col: str,
    step: str,
    hold_col: str,
    hold_val: str,
) -> pd.DataFrame:
    out = dtab.copy()
    if "step" in out.columns:
        out = out.rename(columns={"step": step_col})
    out[step_col] = step
    out[hold_col] = hold_val
    return out


def run_model_trial_step_da(
    ac: pd.DataFrame, *, model: str, session: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (tests, animal_deltas) for one model × session (trial-steps)."""
    cell = ac[(ac["model"] == model) & (ac["session"] == session)].copy()
    test_parts: list[pd.DataFrame] = []
    delta_parts: list[pd.DataFrame] = []
    for step, left, right in TRIAL_STEPS:
        dtab = paired_da_deltas(cell, step=step, left=left, right=right, pair_col="trial_window")
        if dtab.empty:
            continue
        dtab = _finalize_step_deltas(
            dtab, step_col="trial_step", step=step, hold_col="session", hold_val=session
        )
        dtab["model"] = model
        delta_parts.append(dtab)
        tests = da_tests_from_deltas(dtab)
        tests["model"] = model
        tests["session"] = session
        tests["trial_step"] = step
        tests["left"] = left
        tests["right"] = right
        test_parts.append(tests)
    tests_out = pd.concat(test_parts, ignore_index=True) if test_parts else pd.DataFrame()
    deltas_out = pd.concat(delta_parts, ignore_index=True) if delta_parts else pd.DataFrame()
    if not tests_out.empty:
        tests_out = apply_bh_grouped(tests_out, ["model", "session", "trial_step"])
    return tests_out, deltas_out


def run_model_session_step_da(
    ac: pd.DataFrame, *, model: str, trial_window: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (tests, animal_deltas) for one model × trial_window (session-steps)."""
    cell = ac[(ac["model"] == model) & (ac["trial_window"] == trial_window)].copy()
    test_parts: list[pd.DataFrame] = []
    delta_parts: list[pd.DataFrame] = []
    for step, left, right in SESSION_STEPS:
        dtab = paired_da_deltas(cell, step=step, left=left, right=right, pair_col="session")
        if dtab.empty:
            continue
        dtab = _finalize_step_deltas(
            dtab,
            step_col="session_step",
            step=step,
            hold_col="trial_window",
            hold_val=trial_window,
        )
        dtab["model"] = model
        delta_parts.append(dtab)
        tests = da_tests_from_deltas(dtab)
        tests["model"] = model
        tests["trial_window"] = trial_window
        tests["session_step"] = step
        tests["left"] = left
        tests["right"] = right
        test_parts.append(tests)
    tests_out = pd.concat(test_parts, ignore_index=True) if test_parts else pd.DataFrame()
    deltas_out = pd.concat(delta_parts, ignore_index=True) if delta_parts else pd.DataFrame()
    if not tests_out.empty:
        tests_out = apply_bh_grouped(tests_out, ["model", "trial_window", "session_step"])
    return tests_out, deltas_out


def animal_median_for_cluster(deltas: pd.DataFrame, id_map: pd.DataFrame) -> pd.DataFrame:
    keys = id_map[["model", "raw_syllable_id"]].drop_duplicates()
    mapped = deltas.merge(keys, on=["model", "raw_syllable_id"], how="inner")
    if mapped.empty:
        return pd.DataFrame()
    gcols = ["animal_id", "sex", "strain", "tx", "session", "trial_step"]
    rows: list[dict[str, object]] = []
    for key_vals, g in mapped.groupby(gcols, sort=True):
        key_map = dict(zip(gcols, key_vals if isinstance(key_vals, tuple) else (key_vals,)))
        v = pd.to_numeric(g["delta_p"], errors="coerce").to_numpy(dtype=np.float64)
        v = v[np.isfinite(v)]
        q75, q25 = (np.percentile(v, [75, 25]) if v.size >= 2 else (np.nan, np.nan))
        rows.append(
            {
                **key_map,
                "delta_p": float(np.median(v)) if v.size else float("nan"),
                "iqr_across_models": float(q75 - q25) if v.size >= 2 else float("nan"),
                "n_models": int(g["model"].nunique()),
                "n_finite": int(v.size),
            }
        )
    out = pd.DataFrame(rows)
    # Legacy aliases for sliced_group_tests / older cluster figs.
    if not out.empty:
        out["phase_layer"] = out["session"]
        out["step"] = out["trial_step"]
    return out


def kruskal_by_sex(med: pd.DataFrame) -> pd.DataFrame:
    """Legacy alias: strain contrast with hold_sex (one-hold slices)."""
    sub = med.copy()
    rows: list[dict[str, object]] = []
    sliced = sliced_mann_whitney_tests(sub)
    if sliced.empty:
        return pd.DataFrame()
    sex_strain = sliced[
        (sliced["contrast_factor"] == "strain")
        & (sliced["hold_strain"] == "")
        & (sliced["hold_tx"] == "")
        & (sliced["hold_sex"].isin(("F", "M")))
    ].copy()
    for _, row in sex_strain.iterrows():
        rows.append(
            {
                "session": row["phase_layer"],
                "phase_layer": row["phase_layer"],
                "trial_step": row["step"],
                "step": row["step"],
                "test": "kruskal_sex",
                "sex": row["hold_sex"],
                "contrast_factor": "strain",
                "level_a": row["level_a"],
                "level_b": row["level_b"],
                "stat": row["stat"],
                "p": row["p"],
                "q_bh": row.get("q_bh", float("nan")),
                "hit_fdr05": row.get("hit_fdr05", False),
                "n_a": row["n_a"],
                "n_b": row["n_b"],
                "median_a": row["median_a"],
                "median_b": row["median_b"],
            }
        )
    return pd.DataFrame(rows)


def _info_md(*, pause_cluster: int) -> str:
    return f"""# INFO — VAST DA trial / session steps

Paired **differential abundance (DA)** of syllable frame-shares.

Wire names follow `docs/vocab/PROTOCOL-STRATA.md`:
`session` · `trial_window` · `trial_step` · `session_step`.

## Trial-steps (within session)

| trial_step | left | right |
|------------|------|-------|
| `mid_early` | `early_t1-3` | `mid_t4-6` |
| `late_mid` | `mid_t4-6` | `late_t7-9` |
| `late_early` | `early_t1-3` | `late_t7-9` |

BH family: `model × session × trial_step`.

## Session-steps (within trial_window)

| session_step | left | right |
|--------------|------|-------|
| `S02-S01` … `S05-S04` | sequential sessions | |
| `S05-S01` | `S01` | `S05` |

BH family: `model × trial_window × session_step`.

Δp_k = p_k(right) − p_k(left); Wilcoxon vs 0 across animals.

## Cohort note

Balanced **2×2×2**: strain (`wt`|`tg`) × tx (`RBSF-1`|`n/a`) × sex (`F`|`M`).
Mann–Whitney slices hold one or two factors (see `cluster*_sliced_tests.csv`).
Pause focus: HDBSCAN `cluster_id={pause_cluster}`.

## Pass 1

Run-interval bouts only (stimulus-on). Wait / whole-trial deferred.

## Paramscan2026 note

For `D:\\az-sd-vast_paramscan2026`, load sex/strain/tx from
`vast_results_legacy.h5` animal attrs (`--meta-h5`). Pause focus defaults to
the slowest *universal* HDBSCAN cluster for that fit (often not integer 13).
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--kinematics-csv", type=Path, default=DEFAULT_KIN)
    ap.add_argument("--signatures-csv", type=Path, default=DEFAULT_SIG)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--pause-cluster", type=int, default=PAUSE_CLUSTER_DEFAULT)
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument(
        "--meta-h5",
        type=Path,
        default=None,
        help="If set, load sex/strain/tx from animal attrs in this cohort H5 "
        "(preferred for az-sd-vast_paramscan2026).",
    )
    ap.add_argument("--chunksize", type=int, default=250_000)
    args = ap.parse_args(argv)

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    peek_ids: set[str] = set()
    for ch in pd.read_csv(
        args.kinematics_csv,
        usecols=["animal_id"],
        dtype=str,
        chunksize=int(args.chunksize),
    ):
        peek_ids.update(ch["animal_id"].astype(str).tolist())

    if args.meta_h5 is not None:
        animal_meta = load_animal_meta_from_h5(args.meta_h5, animal_ids=peek_ids)
        meta_source = f"h5:{args.meta_h5}"
    else:
        animal_meta = load_animal_meta(args.manifest)
        meta_source = f"manifest:{args.manifest}"
    animal_meta.to_csv(out / "animal_meta.csv", index=False)
    print(f"animal_meta n={len(animal_meta)} source={meta_source}", flush=True)

    usecols = [
        "model",
        "animal_id",
        "phase_layer",
        "kpms_key",
        "raw_syllable_id",
        "bout_frames",
        "tx",
        "sex",
    ]
    print(f"Reading {args.kinematics_csv}", flush=True)
    parts: list[pd.DataFrame] = []
    n = 0
    for ch in pd.read_csv(
        args.kinematics_csv,
        usecols=usecols,
        chunksize=int(args.chunksize),
        keep_default_na=False,
    ):
        ch = attach_animal_meta(ch, animal_meta)
        parts.append(assign_windows(ch))
        n += len(ch)
        print(f"  rows={n:,}", flush=True)
    df = pd.concat(parts, ignore_index=True)
    print(f"windowed bouts={len(df):,}", flush=True)

    ac = build_animal_window_table(df)
    ac.to_pickle(out / "animal_window_counts.pkl")
    ac.drop(columns=["counts"]).to_csv(out / "animal_window_meta.csv", index=False)

    # --- Trial-steps ---
    all_tests: list[pd.DataFrame] = []
    all_deltas: list[pd.DataFrame] = []
    models = sorted(ac["model"].unique())
    for mi, model in enumerate(models, start=1):
        print(f"[{mi}/{len(models)}] trial-step DA {model}", flush=True)
        for session in SESSIONS:
            tests, deltas = run_model_trial_step_da(ac, model=model, session=session)
            if not tests.empty:
                all_tests.append(tests)
            if not deltas.empty:
                all_deltas.append(deltas)

    tests = pd.concat(all_tests, ignore_index=True) if all_tests else pd.DataFrame()
    deltas = pd.concat(all_deltas, ignore_index=True) if all_deltas else pd.DataFrame()
    if not deltas.empty:
        deltas = attach_animal_meta(deltas, animal_meta)
        deltas["tx"] = deltas["tx"].map(norm_tx)
    tests.to_csv(out / "da_syllable_tests_long.csv", index=False)
    deltas.to_csv(out / "da_syllable_deltas_per_animal.csv", index=False)

    strat_tests = (
        da_tests_cohort_strat_from_deltas(deltas, progress=True) if not deltas.empty else pd.DataFrame()
    )
    strat_tests.to_csv(out / "da_syllable_tests_strat_long.csv", index=False)

    # --- Session-steps ---
    sess_tests_parts: list[pd.DataFrame] = []
    sess_delta_parts: list[pd.DataFrame] = []
    for mi, model in enumerate(models, start=1):
        print(f"[{mi}/{len(models)}] session-step DA {model}", flush=True)
        for tw in TRIAL_WINDOWS:
            st, sd = run_model_session_step_da(ac, model=model, trial_window=tw)
            if not st.empty:
                sess_tests_parts.append(st)
            if not sd.empty:
                sess_delta_parts.append(sd)

    sess_tests = (
        pd.concat(sess_tests_parts, ignore_index=True) if sess_tests_parts else pd.DataFrame()
    )
    sess_deltas = (
        pd.concat(sess_delta_parts, ignore_index=True) if sess_delta_parts else pd.DataFrame()
    )
    if not sess_deltas.empty:
        sess_deltas = attach_animal_meta(sess_deltas, animal_meta)
        sess_deltas["tx"] = sess_deltas["tx"].map(norm_tx)
    sess_tests.to_csv(out / "da_session_step_tests_long.csv", index=False)
    sess_deltas.to_csv(out / "da_session_step_deltas_per_animal.csv", index=False)
    sess_strat = (
        da_tests_cohort_strat_from_deltas(sess_deltas, progress=True)
        if not sess_deltas.empty
        else pd.DataFrame()
    )
    sess_strat.to_csv(out / "da_session_step_tests_strat_long.csv", index=False)

    # Pause cluster animal medians (trial-steps)
    sig = pd.read_csv(args.signatures_csv)
    id_map = sig[sig["cluster_id"] == int(args.pause_cluster)][
        ["model", "raw_syllable_id", "cluster_id"]
    ].copy()
    id_map.to_csv(out / f"pause_cluster{args.pause_cluster}_id_map.csv", index=False)
    med = animal_median_for_cluster(deltas, id_map)
    med.to_csv(out / f"cluster{args.pause_cluster}_animal_median_delta_p.csv", index=False)
    sliced = sliced_mann_whitney_tests(med) if not med.empty else pd.DataFrame()
    sliced.to_csv(out / f"cluster{args.pause_cluster}_sliced_tests.csv", index=False)
    kruskal = kruskal_by_sex(med) if not med.empty else pd.DataFrame()
    if not kruskal.empty:
        kruskal.to_csv(out / f"cluster{args.pause_cluster}_sex_kruskal.csv", index=False)

    hit_summary = (
        tests.groupby(["model", "session", "trial_step"], sort=True)
        .agg(
            n_syll=("raw_syllable_id", "size"),
            n_hit_fdr05=("hit_fdr05", "sum"),
            n_hit_p05=("hit_p05", "sum"),
        )
        .reset_index()
        if not tests.empty
        else pd.DataFrame()
    )
    hit_summary.to_csv(out / "da_hit_summary.csv", index=False)

    sess_hit = (
        sess_tests.groupby(["model", "trial_window", "session_step"], sort=True)
        .agg(
            n_syll=("raw_syllable_id", "size"),
            n_hit_fdr05=("hit_fdr05", "sum"),
            n_hit_p05=("hit_p05", "sum"),
        )
        .reset_index()
        if not sess_tests.empty
        else pd.DataFrame()
    )
    sess_hit.to_csv(out / "da_session_step_hit_summary.csv", index=False)

    run = {
        "kinematics_csv": str(args.kinematics_csv),
        "meta_source": meta_source,
        "n_animals": int(len(animal_meta)),
        "n_bout_rows_windowed": int(len(df)),
        "n_animal_window_cells": int(len(ac)),
        "n_test_rows": int(len(tests)),
        "n_strat_test_rows": int(len(strat_tests)),
        "n_delta_rows": int(len(deltas)),
        "n_session_step_test_rows": int(len(sess_tests)),
        "n_session_step_strat_rows": int(len(sess_strat)),
        "n_session_step_delta_rows": int(len(sess_deltas)),
        "trial_steps": [s[0] for s in TRIAL_STEPS],
        "session_steps": [s[0] for s in SESSION_STEPS],
        "sessions": list(SESSIONS),
        "trial_windows": list(TRIAL_WINDOWS),
        "pause_cluster": int(args.pause_cluster),
        "n_pause_prototypes": int(len(id_map)),
        "n_pause_animal_medians": int(len(med)),
        "n_sliced_tests": int(len(sliced)),
        "cohort": "2x2x2 strain×tx×sex; Mann–Whitney slices; sex never pooled in contrasts",
        "tx_levels": ["RBSF-1", "n/a"],
        "strain_levels": ["wt", "tg"],
        "wire": "session / trial_window / trial_step / session_step",
    }
    (out / "run_summary.json").write_text(json.dumps(run, indent=2), encoding="utf-8")
    (out / "INFO_da.md").write_text(_info_md(pause_cluster=int(args.pause_cluster)), encoding="utf-8")
    print(json.dumps(run, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
