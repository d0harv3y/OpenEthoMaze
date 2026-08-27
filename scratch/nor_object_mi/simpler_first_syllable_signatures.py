"""Within-model syllable kinematic signatures + across-model HDBSCAN (scratch).

Pools bout rows from ``syllable_bout_kinematics.csv`` by ``(model, raw_syllable_id)``
into ADR-0005-style signatures (nose–tail stands in for missing blob). Then clusters
syllable prototypes across models in z-scored kinematic space so ids are never treated
as portable.

Regen:
  uv run python scratch/nor_object_mi/simpler_first_syllable_signatures.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from maze.kpms.behavior_ethogram.cluster import zscore_features  # noqa: E402

DEFAULT_KIN = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_syllable_kinematics\syllable_bout_kinematics.csv"
)

# ADR-0005 core (blob → nose_tail for NOR).
SIGNATURE_POOL_COLS: tuple[str, ...] = (
    "bout_mean_speed_mps",
    "bout_mean_abs_dheading",
    "bout_mean_nose_tail_m",
)

# Stage-II-like matrix at syllable grain (NOR; no blob).
CLUSTER_POOL_COLS: tuple[str, ...] = (
    "bout_mean_speed_mps",
    "bout_mean_abs_dheading",
    "bout_mean_nose_tail_m",
    "bout_iqr_speed_mps",
    "bout_iqr_abs_dheading",
    "bout_iqr_nose_tail_m",
    "bout_duration_s",
    "bout_net_dheading_rad",
    "bout_straightness",
)

READ_COLS: tuple[str, ...] = (
    "model",
    "ss",
    "raw_syllable_id",
    *CLUSTER_POOL_COLS,
)

SIG_OUT_COLS: tuple[str, ...] = (
    "syllable_sig_mean_speed_mps",
    "syllable_sig_mean_abs_dheading",
    "syllable_sig_mean_nose_tail_m",
)


def pool_syllable_prototypes(df: pd.DataFrame) -> pd.DataFrame:
    """One row per model × raw_syllable_id: nanmean of bout scalars + n_bouts."""
    need = {"model", "raw_syllable_id", *CLUSTER_POOL_COLS}
    missing = need - set(df.columns)
    if missing:
        raise KeyError(f"pool_syllable_prototypes missing: {sorted(missing)}")

    gcols = ["model", "raw_syllable_id"]
    if "ss" in df.columns:
        gcols = ["model", "ss", "raw_syllable_id"]

    out = (
        df.groupby(gcols, dropna=False, sort=True)
        .agg(**{c: (c, "mean") for c in CLUSTER_POOL_COLS}, n_bouts=("raw_syllable_id", "size"))
        .reset_index()
    )
    return out.rename(
        columns={
            "bout_mean_speed_mps": "syllable_sig_mean_speed_mps",
            "bout_mean_abs_dheading": "syllable_sig_mean_abs_dheading",
            "bout_mean_nose_tail_m": "syllable_sig_mean_nose_tail_m",
            "bout_iqr_speed_mps": "syllable_mean_iqr_speed_mps",
            "bout_iqr_abs_dheading": "syllable_mean_iqr_abs_dheading",
            "bout_iqr_nose_tail_m": "syllable_mean_iqr_nose_tail_m",
            "bout_duration_s": "syllable_mean_duration_s",
            "bout_net_dheading_rad": "syllable_mean_net_dheading_rad",
            "bout_straightness": "syllable_mean_straightness",
        }
    )


def accumulate_chunk_sums(
    chunk: pd.DataFrame,
    sums: dict[tuple, np.ndarray],
    counts: dict[tuple, np.ndarray],
    n_bouts: dict[tuple, int],
    feature_cols: Sequence[str],
) -> None:
    """Online sum/count per (model, ss, syllable) for chunked CSV reads."""
    feats = list(feature_cols)
    g = chunk.groupby(["model", "ss", "raw_syllable_id"], dropna=False, sort=False)
    for key, sub in g:
        mat = sub[feats].to_numpy(dtype=np.float64)
        finite = np.isfinite(mat)
        s = np.nansum(np.where(finite, mat, 0.0), axis=0)
        c = finite.sum(axis=0).astype(np.float64)
        n = int(len(sub))
        if key not in sums:
            sums[key] = s.copy()
            counts[key] = c.copy()
            n_bouts[key] = n
        else:
            sums[key] += s
            counts[key] += c
            n_bouts[key] += n


def prototypes_from_accumulators(
    sums: dict[tuple, np.ndarray],
    counts: dict[tuple, np.ndarray],
    n_bouts: dict[tuple, int],
    feature_cols: Sequence[str],
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    rename = {
        "bout_mean_speed_mps": "syllable_sig_mean_speed_mps",
        "bout_mean_abs_dheading": "syllable_sig_mean_abs_dheading",
        "bout_mean_nose_tail_m": "syllable_sig_mean_nose_tail_m",
        "bout_iqr_speed_mps": "syllable_mean_iqr_speed_mps",
        "bout_iqr_abs_dheading": "syllable_mean_iqr_abs_dheading",
        "bout_iqr_nose_tail_m": "syllable_mean_iqr_nose_tail_m",
        "bout_duration_s": "syllable_mean_duration_s",
        "bout_net_dheading_rad": "syllable_mean_net_dheading_rad",
        "bout_straightness": "syllable_mean_straightness",
    }
    for (model, ss, sid), s in sums.items():
        c = counts[(model, ss, sid)]
        with np.errstate(invalid="ignore", divide="ignore"):
            means = np.where(c > 0, s / c, np.nan)
        rec: dict[str, object] = {
            "model": model,
            "ss": ss,
            "raw_syllable_id": int(sid),
            "n_bouts": int(n_bouts[(model, ss, sid)]),
        }
        for j, col in enumerate(feature_cols):
            rec[rename[col]] = float(means[j])
        rows.append(rec)
    return pd.DataFrame(rows).sort_values(["model", "raw_syllable_id"]).reset_index(drop=True)


def cluster_feature_matrix(proto: pd.DataFrame) -> tuple[np.ndarray, tuple[str, ...]]:
    names = (
        "syllable_sig_mean_speed_mps",
        "syllable_sig_mean_abs_dheading",
        "syllable_sig_mean_nose_tail_m",
        "syllable_mean_iqr_speed_mps",
        "syllable_mean_iqr_abs_dheading",
        "syllable_mean_iqr_nose_tail_m",
        "syllable_mean_duration_s",
        "syllable_mean_net_dheading_rad",
        "syllable_mean_straightness",
    )
    mat = proto[list(names)].to_numpy(dtype=np.float64)
    return mat, names


def cluster_prototypes_hdbscan(
    proto: pd.DataFrame,
    *,
    min_cluster_size: int = 5,
    min_samples: int = 3,
) -> tuple[pd.DataFrame, dict[str, object]]:
    import hdbscan

    mat, names = cluster_feature_matrix(proto)
    z, mean, std = zscore_features(mat)
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=int(min_cluster_size),
        min_samples=int(min_samples),
        metric="euclidean",
    )
    labels = np.asarray(clusterer.fit_predict(z), dtype=np.int64)
    out = proto.copy()
    out["cluster_id"] = labels
    n_clusters = len({int(x) for x in labels.tolist() if int(x) >= 0})
    n_noise = int(np.sum(labels < 0))
    summary = {
        "feature_names": list(names),
        "n_syllable_prototypes": int(len(out)),
        "n_clusters": n_clusters,
        "n_noise": n_noise,
        "noise_frac": float(n_noise / len(out)) if len(out) else float("nan"),
        "min_cluster_size": min_cluster_size,
        "min_samples": min_samples,
        "zscore_mean": mean.tolist(),
        "zscore_std": std.tolist(),
    }
    return out, summary


def _info_md() -> str:
    return """# INFO — syllable kinematic signatures (NOR)

Grain: one row = ``model × raw_syllable_id`` (pooled over all bouts for that syllable).

## Purpose

ADR-0005: never treat ``raw_syllable_id`` as portable across models. Pool bout kinematics
into a signature, then HDBSCAN syllable prototypes across the 21-model ensemble.

## Signature trio (ADR-0005 analog)

| Column | Bout source |
|--------|-------------|
| `syllable_sig_mean_speed_mps` | `bout_mean_speed_mps` (spot) |
| `syllable_sig_mean_abs_dheading` | `bout_mean_abs_dheading` (kpMS heading) |
| `syllable_sig_mean_nose_tail_m` | `bout_mean_nose_tail_m` (**NOR blob substitute**) |

## Clustering matrix

9 z-scored columns: signature trio + IQR speed / IQR |dheading| / IQR nose–tail +
mean duration / net dheading / straightness. ``cluster_id`` ≥ 0 is a cross-model
physics label; −1 = HDBSCAN noise.

## Not done here

Appending signatures onto the 8.8M bout CSV; n-gram remapping; ethogram Stage III AR-HMM.
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--kinematics-csv", type=Path, default=DEFAULT_KIN)
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Default: sibling simpler_first_syllable_signatures/",
    )
    ap.add_argument("--chunksize", type=int, default=250_000)
    ap.add_argument("--min-cluster-size", type=int, default=5)
    ap.add_argument("--min-samples", type=int, default=3)
    ap.add_argument("--min-bouts", type=int, default=10, help="Drop rare syllables before HDBSCAN")
    args = ap.parse_args(argv)

    kin = args.kinematics_csv
    out = args.out_dir or (kin.parent.parent / "simpler_first_syllable_signatures")
    out.mkdir(parents=True, exist_ok=True)

    sums: dict[tuple, np.ndarray] = {}
    counts: dict[tuple, np.ndarray] = {}
    n_bouts: dict[tuple, int] = {}
    n_rows = 0
    print(f"Pooling from {kin} (chunksize={args.chunksize})", flush=True)
    for chunk in pd.read_csv(kin, usecols=list(READ_COLS), chunksize=int(args.chunksize)):
        accumulate_chunk_sums(chunk, sums, counts, n_bouts, CLUSTER_POOL_COLS)
        n_rows += len(chunk)
        print(f"  rows={n_rows:,} prototypes={len(sums):,}", flush=True)

    proto = prototypes_from_accumulators(sums, counts, n_bouts, CLUSTER_POOL_COLS)
    proto.to_csv(out / "syllable_kinematic_signatures.csv", index=False)
    print(f"Wrote {len(proto)} prototypes", flush=True)

    fit = proto[proto["n_bouts"] >= int(args.min_bouts)].copy()
    clustered, cl_summary = cluster_prototypes_hdbscan(
        fit,
        min_cluster_size=int(args.min_cluster_size),
        min_samples=int(args.min_samples),
    )
    clustered.to_csv(out / "syllable_prototypes_clustered.csv", index=False)

    # Per-cluster: how many models / ss represented
    pos = clustered[clustered["cluster_id"] >= 0]
    if not pos.empty:
        by_c = (
            pos.groupby("cluster_id", sort=True)
            .agg(
                n_prototypes=("raw_syllable_id", "size"),
                n_models=("model", "nunique"),
                n_ss=("ss", "nunique"),
                median_n_bouts=("n_bouts", "median"),
                mean_sig_speed=("syllable_sig_mean_speed_mps", "mean"),
                mean_sig_dheading=("syllable_sig_mean_abs_dheading", "mean"),
                mean_sig_nose_tail=("syllable_sig_mean_nose_tail_m", "mean"),
            )
            .reset_index()
        )
    else:
        by_c = pd.DataFrame()
    by_c.to_csv(out / "cluster_summary.csv", index=False)

    run = {
        "kinematics_csv": str(kin),
        "n_bout_rows_read": n_rows,
        "n_prototypes": int(len(proto)),
        "n_prototypes_fit": int(len(fit)),
        "min_bouts": int(args.min_bouts),
        "signature_cols": list(SIG_OUT_COLS),
        "cluster": cl_summary,
        "n_clusters_with_ge2_models": int((by_c["n_models"] >= 2).sum()) if not by_c.empty else 0,
    }
    (out / "run_summary.json").write_text(json.dumps(run, indent=2), encoding="utf-8")
    info_path = out / "INFO_syllable_signatures.md"
    if not info_path.is_file():
        info_path.write_text(_info_md(), encoding="utf-8")
    print(
        f"HDBSCAN: n_clusters={cl_summary['n_clusters']} "
        f"noise_frac={cl_summary['noise_frac']:.3f} "
        f"multi_model_clusters={run['n_clusters_with_ge2_models']} -> {out}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
