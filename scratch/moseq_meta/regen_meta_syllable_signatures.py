"""Cross-experiment syllable meta-clustering (NOR + VAST).

Pools bout kinematics from each experiment into model-local prototypes (ADR-0005),
tags rows with ``experiment``, concatenates, and runs one HDBSCAN fit on the shared
9-D z-scored signature matrix. Within-cohort ``cluster_id`` values are **not**
portable; this fit defines a new ``meta_cluster_id``.

Regen (OpenEthoMaze repo root):
  uv run python scratch/moseq_meta/regen_meta_syllable_signatures.py
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

from nor_object_mi.simpler_first_syllable_signatures import (  # noqa: E402
    CLUSTER_POOL_COLS,
    READ_COLS,
    SIG_OUT_COLS,
    accumulate_chunk_sums,
    cluster_prototypes_hdbscan,
    prototypes_from_accumulators,
)

DEFAULT_NOR_KIN = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_syllable_kinematics\syllable_bout_kinematics.csv"
)
DEFAULT_VAST_KIN = Path(
    r"C:\Users\admin\Documents\work\sack\AZ-SD-VAST-moseq"
    r"\syllable_bout_kinematics\syllable_bout_kinematics.csv"
)
DEFAULT_NOR_CL = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_syllable_signatures\syllable_prototypes_clustered.csv"
)
DEFAULT_VAST_CL = Path(
    r"C:\Users\admin\Documents\work\sack\AZ-SD-VAST-moseq"
    r"\syllable_signatures\syllable_prototypes_clustered.csv"
)
DEFAULT_OUT = Path(r"C:\Users\admin\Documents\work\sack\moseq_meta_syllable_signatures_k100_gerstner")
DEFAULT_NOR_SS = 100
DEFAULT_VAST_MODELS = ("gerstner_vast_fit",)


def _pool_experiment(
    kin: Path,
    experiment: str,
    *,
    chunksize: int,
    model_allow: set[str] | None = None,
    nor_ss: int | None = None,
) -> tuple[pd.DataFrame, int]:
    sums: dict[tuple, np.ndarray] = {}
    counts: dict[tuple, np.ndarray] = {}
    n_bouts: dict[tuple, int] = {}
    n_rows = 0
    filt = ""
    if model_allow is not None:
        filt += f" models={sorted(model_allow)}"
    if nor_ss is not None:
        filt += f" ss={nor_ss}"
    print(f"Pooling {experiment} from {kin}{filt} (chunksize={chunksize})", flush=True)
    usecols = list(READ_COLS)
    for chunk in pd.read_csv(kin, usecols=usecols, chunksize=int(chunksize)):
        if nor_ss is not None:
            chunk = chunk[chunk["ss"] == int(nor_ss)]
        if model_allow is not None:
            chunk = chunk[chunk["model"].astype(str).isin(model_allow)]
        if chunk.empty:
            continue
        accumulate_chunk_sums(chunk, sums, counts, n_bouts, CLUSTER_POOL_COLS)
        n_rows += len(chunk)
        print(f"  {experiment} rows={n_rows:,} prototypes={len(sums):,}", flush=True)
    proto = prototypes_from_accumulators(sums, counts, n_bouts, CLUSTER_POOL_COLS)
    proto.insert(0, "experiment", experiment)
    return proto, n_rows


def _cluster_summary(clustered: pd.DataFrame) -> pd.DataFrame:
    pos = clustered[clustered["meta_cluster_id"] >= 0]
    if pos.empty:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for cid, sub in pos.groupby("meta_cluster_id", sort=True):
        nor = sub[sub["experiment"] == "nor"]
        vast = sub[sub["experiment"] == "vast"]
        rows.append(
            {
                "meta_cluster_id": int(cid),
                "n_prototypes": int(len(sub)),
                "n_models": int(sub["model"].nunique()),
                "n_experiments": int(sub["experiment"].nunique()),
                "n_nor_prototypes": int(len(nor)),
                "n_vast_prototypes": int(len(vast)),
                "n_nor_models": int(nor["model"].nunique()) if not nor.empty else 0,
                "n_vast_models": int(vast["model"].nunique()) if not vast.empty else 0,
                "median_n_bouts": float(sub["n_bouts"].median()),
                "mean_sig_speed": float(sub["syllable_sig_mean_speed_mps"].mean()),
                "mean_sig_dheading": float(sub["syllable_sig_mean_abs_dheading"].mean()),
                "mean_sig_nose_tail": float(sub["syllable_sig_mean_nose_tail_m"].mean()),
                "mean_duration_s": float(sub["syllable_mean_duration_s"].mean()),
                "mean_straightness": float(sub["syllable_mean_straightness"].mean()),
            }
        )
    return pd.DataFrame(rows)


def _attach_within_cohort_clusters(
    meta: pd.DataFrame,
    nor_cl: Path | None,
    vast_cl: Path | None,
) -> pd.DataFrame:
    out = meta.copy()
    out["nor_cluster_id"] = np.nan
    out["vast_cluster_id"] = np.nan
    if nor_cl and nor_cl.is_file():
        nor = pd.read_csv(nor_cl, usecols=["model", "raw_syllable_id", "cluster_id"])
        nor = nor.rename(columns={"cluster_id": "nor_cluster_id"})
        nor_keys = out["experiment"] == "nor"
        out.loc[nor_keys, "nor_cluster_id"] = (
            out.loc[nor_keys, ["model", "raw_syllable_id"]]
            .merge(nor, on=["model", "raw_syllable_id"], how="left")["nor_cluster_id"]
            .to_numpy()
        )
    if vast_cl and vast_cl.is_file():
        vast = pd.read_csv(vast_cl, usecols=["model", "raw_syllable_id", "cluster_id"])
        vast = vast.rename(columns={"cluster_id": "vast_cluster_id"})
        vast_keys = out["experiment"] == "vast"
        out.loc[vast_keys, "vast_cluster_id"] = (
            out.loc[vast_keys, ["model", "raw_syllable_id"]]
            .merge(vast, on=["model", "raw_syllable_id"], how="left")["vast_cluster_id"]
            .to_numpy()
        )
    return out


def _pause_hint(summary: pd.DataFrame) -> dict[str, object]:
    if summary.empty:
        return {}
    cand = summary[(summary["n_experiments"] >= 2) & (summary["n_models"] >= 3)].copy()
    if cand.empty:
        cand = summary[summary["n_models"] >= 2].copy()
    if cand.empty:
        return {}
    cand = cand.sort_values(
        ["mean_sig_speed", "mean_duration_s", "mean_straightness"],
        ascending=[True, False, True],
    )
    top = cand.head(5)
    return {
        "rule": "cross-experiment clusters preferred; rank by low speed, high duration, low straightness",
        "top_meta_cluster_ids": [int(x) for x in top["meta_cluster_id"].tolist()],
        "top_rows": top.to_dict(orient="records"),
    }


def _info_md(nor_ss: int | None, vast_models: tuple[str, ...]) -> str:
    nor_note = f"NOR alphabets with ss={nor_ss} (K={nor_ss})" if nor_ss is not None else "all NOR alphabets"
    vast_note = ", ".join(vast_models) if vast_models else "all VAST alphabets"
    return f"""# INFO — cross-experiment syllable meta-signatures (NOR + VAST)

Grain: one row = ``experiment × model × raw_syllable_id`` prototype.

## Model filter (this run)

| experiment | subset |
|------------|--------|
| `nor` | {nor_note} |
| `vast` | `{vast_note}` |

## Purpose

ADR-0005 still applies: ``raw_syllable_id`` is model-local. This pass pools bout
kinematics within each experiment, concatenates prototypes, and HDBSCAN-clusters in
the shared 9-D signature space. ``meta_cluster_id`` is a **new** physics label —
not equal to NOR or VAST within-cohort ``cluster_id``.

## Inputs

| experiment | Bout CSV | Bout filter |
|------------|----------|-------------|
| `nor` | NOR ``syllable_bout_kinematics.csv`` | full session (all phases) |
| `vast` | VAST ``syllable_bout_kinematics.csv`` | run-phase only (stimulus-on) |

**Validation caveat:** VAST prototypes reflect run-window bouts; NOR prototypes pool
all phases. Compare occupancy or re-pool NOR on run-only before inferring experiment
effects on meta-cluster membership.

## Feature matrix

Same 9 z-scored columns as within-cohort signatures (speed, |dheading|, nose-tail,
IQR trio, duration, net dheading, straightness).

## Lineage columns

| Column | Meaning |
|--------|---------|
| `meta_cluster_id` | This fit (≥0 cluster, −1 noise) |
| `nor_cluster_id` | NOR-only HDBSCAN label (NaN for vast rows) |
| `vast_cluster_id` | VAST-only HDBSCAN label (NaN for nor rows) |
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--nor-kinematics-csv", type=Path, default=DEFAULT_NOR_KIN)
    ap.add_argument("--vast-kinematics-csv", type=Path, default=DEFAULT_VAST_KIN)
    ap.add_argument("--nor-clustered-csv", type=Path, default=DEFAULT_NOR_CL)
    ap.add_argument("--vast-clustered-csv", type=Path, default=DEFAULT_VAST_CL)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--chunksize", type=int, default=250_000)
    ap.add_argument("--min-cluster-size", type=int, default=5)
    ap.add_argument("--min-samples", type=int, default=3)
    ap.add_argument("--min-bouts", type=int, default=10)
    ap.add_argument(
        "--nor-ss",
        type=int,
        default=DEFAULT_NOR_SS,
        help="Keep NOR bout rows with this ss (K). Use 0 to disable ss filter.",
    )
    ap.add_argument(
        "--vast-models",
        nargs="*",
        default=list(DEFAULT_VAST_MODELS),
        help="VAST model ids to include (default: gerstner_vast_fit only).",
    )
    ap.add_argument(
        "--all-models",
        action="store_true",
        help="Disable model/ss filters (full 21 NOR + 6 VAST alphabets).",
    )
    args = ap.parse_args(argv)

    nor_ss = None if args.all_models or int(args.nor_ss) <= 0 else int(args.nor_ss)
    vast_models: tuple[str, ...] = () if args.all_models else tuple(str(m) for m in args.vast_models)
    vast_allow = set(vast_models) if vast_models else None

    out = args.out_dir
    if args.all_models and args.out_dir == DEFAULT_OUT:
        out = Path(r"C:\Users\admin\Documents\work\sack\moseq_meta_syllable_signatures")
    out.mkdir(parents=True, exist_ok=True)

    nor_proto, nor_rows = _pool_experiment(
        args.nor_kinematics_csv,
        "nor",
        chunksize=int(args.chunksize),
        nor_ss=nor_ss,
    )
    vast_proto, vast_rows = _pool_experiment(
        args.vast_kinematics_csv,
        "vast",
        chunksize=int(args.chunksize),
        model_allow=vast_allow,
    )
    proto = pd.concat([nor_proto, vast_proto], ignore_index=True)
    proto.to_csv(out / "syllable_kinematic_signatures.csv", index=False)

    fit = proto[proto["n_bouts"] >= int(args.min_bouts)].copy()
    clustered, cl_summary = cluster_prototypes_hdbscan(
        fit,
        min_cluster_size=int(args.min_cluster_size),
        min_samples=int(args.min_samples),
    )
    clustered = clustered.rename(columns={"cluster_id": "meta_cluster_id"})
    clustered = _attach_within_cohort_clusters(
        clustered,
        args.nor_clustered_csv if args.nor_clustered_csv else None,
        args.vast_clustered_csv if args.vast_clustered_csv else None,
    )
    clustered.to_csv(out / "syllable_prototypes_meta_clustered.csv", index=False)

    summary = _cluster_summary(clustered)
    summary.to_csv(out / "meta_cluster_summary.csv", index=False)

    cross_exp = summary[summary["n_experiments"] >= 2] if not summary.empty else summary
    pause_hint = _pause_hint(summary)

    run = {
        "nor_kinematics_csv": str(args.nor_kinematics_csv),
        "vast_kinematics_csv": str(args.vast_kinematics_csv),
        "nor_clustered_csv": str(args.nor_clustered_csv),
        "vast_clustered_csv": str(args.vast_clustered_csv),
        "model_filter": {
            "nor_ss": nor_ss,
            "vast_models": list(vast_models),
            "all_models": bool(args.all_models),
        },
        "nor_models_in_fit": sorted(nor_proto["model"].astype(str).unique().tolist()),
        "vast_models_in_fit": sorted(vast_proto["model"].astype(str).unique().tolist()),
        "n_bout_rows_nor": nor_rows,
        "n_bout_rows_vast": vast_rows,
        "n_prototypes_total": int(len(proto)),
        "n_prototypes_fit": int(len(fit)),
        "n_prototypes_nor_fit": int((fit["experiment"] == "nor").sum()),
        "n_prototypes_vast_fit": int((fit["experiment"] == "vast").sum()),
        "min_bouts": int(args.min_bouts),
        "signature_cols": list(SIG_OUT_COLS),
        "cluster": cl_summary,
        "n_meta_clusters": int(cl_summary["n_clusters"]),
        "n_cross_experiment_clusters": int(len(cross_exp)),
        "pause_hint": pause_hint,
    }
    (out / "run_summary.json").write_text(json.dumps(run, indent=2), encoding="utf-8")
    (out / "INFO_meta_syllable_signatures.md").write_text(
        _info_md(nor_ss, vast_models), encoding="utf-8"
    )

    print(
        f"Meta HDBSCAN: n_clusters={cl_summary['n_clusters']} "
        f"noise_frac={cl_summary['noise_frac']:.3f} "
        f"cross_experiment={run['n_cross_experiment_clusters']} -> {out}",
        flush=True,
    )
    if pause_hint.get("top_meta_cluster_ids"):
        print(f"pause-like meta candidates: {pause_hint['top_meta_cluster_ids']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
