"""Paramscan2026 syllable kinematic signatures + HDBSCAN.

Pools ``_syllable_bout_kinematics/syllable_bout_kinematics.csv`` by
``(model, raw_syllable_id)``, then clusters prototypes across alphabets
(ADR-0005). Same 9-D z-scored space as impress NOR (mcs=5, ms=3).

Regen (after kinematics):

  uv run python scratch/vast_moseq/regen_paramscan2026_signatures.py
  uv run python scratch/nor_object_mi/fig_simpler_first_syllable_signatures.py `
    --run-dir D:/az-sd-vast_paramscan2026/_syllable_signatures
  uv run python scratch/nor_object_mi/fig_duration_heatmap_cluster_cmap.py `
    --desc-dir D:/az-sd-vast_paramscan2026/_syllable_descriptives `
    --sig-dir D:/az-sd-vast_paramscan2026/_syllable_signatures
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

from nor_object_mi.simpler_first_syllable_signatures import (  # noqa: E402
    CLUSTER_POOL_COLS,
    READ_COLS,
    SIG_OUT_COLS,
    accumulate_chunk_sums,
    cluster_prototypes_hdbscan,
    prototypes_from_accumulators,
)

DEFAULT_KIN = Path(
    r"D:\az-sd-vast_paramscan2026\_syllable_bout_kinematics\syllable_bout_kinematics.csv"
)
DEFAULT_OUT = Path(r"D:\az-sd-vast_paramscan2026\_syllable_signatures")


def _info_md(*, n_models: int) -> str:
    return f"""# INFO — paramscan2026 syllable kinematic signatures

Grain: one row = ``model × raw_syllable_id`` (pooled over run-phase bouts).

## Cohort

{n_models} anatomical paramscan alphabets (ct=0.1 dropped) × VAST primary keys.
Upstream: `_syllable_bout_kinematics/` (stimulus-on = `run`).

## Purpose

ADR-0005: never treat `raw_syllable_id` as portable across models. Pool bout
kinematics into a signature, then HDBSCAN prototypes across alphabets.

## Clustering matrix

Same 9 z-scored columns as impress NOR. `cluster_id` ≥ 0 is this fit only; −1 = noise.

## Figures

```powershell
uv run python scratch/nor_object_mi/fig_simpler_first_syllable_signatures.py `
  --run-dir D:\\az-sd-vast_paramscan2026\\_syllable_signatures
uv run python scratch/nor_object_mi/fig_duration_heatmap_cluster_cmap.py `
  --desc-dir D:\\az-sd-vast_paramscan2026\\_syllable_descriptives `
  --sig-dir D:\\az-sd-vast_paramscan2026\\_syllable_signatures
```
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--kinematics-csv", type=Path, default=DEFAULT_KIN)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--chunksize", type=int, default=250_000)
    ap.add_argument("--min-cluster-size", type=int, default=5)
    ap.add_argument("--min-samples", type=int, default=3)
    ap.add_argument("--min-bouts", type=int, default=10)
    args = ap.parse_args(argv)

    kin = args.kinematics_csv
    if not kin.is_file():
        print(f"Missing kinematics CSV: {kin}", flush=True)
        return 1
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    sums: dict[tuple, object] = {}
    counts: dict[tuple, object] = {}
    n_bouts: dict[tuple, int] = {}
    n_rows = 0
    print(f"Pooling from {kin} (chunksize={args.chunksize})", flush=True)
    for chunk in pd.read_csv(kin, usecols=list(READ_COLS), chunksize=int(args.chunksize)):
        accumulate_chunk_sums(chunk, sums, counts, n_bouts, CLUSTER_POOL_COLS)
        n_rows += len(chunk)
        print(f"  rows={n_rows:,} prototypes={len(sums):,}", flush=True)

    proto = prototypes_from_accumulators(sums, counts, n_bouts, CLUSTER_POOL_COLS)
    proto.to_csv(out / "syllable_kinematic_signatures.csv", index=False)
    n_models = int(proto["model"].nunique()) if not proto.empty else 0
    print(f"Wrote {len(proto)} prototypes ({n_models} models)", flush=True)

    fit = proto[proto["n_bouts"] >= int(args.min_bouts)].copy()
    clustered, cl_summary = cluster_prototypes_hdbscan(
        fit,
        min_cluster_size=int(args.min_cluster_size),
        min_samples=int(args.min_samples),
    )
    clustered.to_csv(out / "syllable_prototypes_clustered.csv", index=False)

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
                mean_duration_s=("syllable_mean_duration_s", "mean"),
                mean_straightness=("syllable_mean_straightness", "mean"),
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
        "n_models": n_models,
        "min_bouts": int(args.min_bouts),
        "signature_cols": list(SIG_OUT_COLS),
        "cluster": cl_summary,
        "n_clusters_with_ge2_models": int((by_c["n_models"] >= 2).sum()) if not by_c.empty else 0,
        "n_clusters_all_models": (
            int((by_c["n_models"] >= n_models).sum()) if not by_c.empty and n_models else 0
        ),
    }
    (out / "run_summary.json").write_text(json.dumps(run, indent=2), encoding="utf-8")
    (out / "INFO_syllable_signatures.md").write_text(
        _info_md(n_models=n_models), encoding="utf-8"
    )
    print(
        f"HDBSCAN: n_clusters={cl_summary['n_clusters']} "
        f"noise_frac={cl_summary['noise_frac']:.3f} "
        f"multi_model={run['n_clusters_with_ge2_models']} "
        f"all_models={run['n_clusters_all_models']} -> {out}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
