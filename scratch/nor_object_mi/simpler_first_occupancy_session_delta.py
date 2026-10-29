"""BL→TX object-prox occupancy session Δ (Q5 OccSessDelta Family A).

Consensus animal = median across kpMS models of frac_near_* at each session,
then paired Δ = TX − BL; Kruskal by condition within sex; BH over 4 cells.
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

from nor_object_mi.simpler_first_da import apply_bh  # noqa: E402
from nor_object_mi.simpler_first_object_prox import (  # noqa: E402
    animal_median_across_models,
)
from nor_object_mi.simpler_first_q1 import kruskal_within_sex  # noqa: E402

FAMILY_METRICS: tuple[str, ...] = ("delta_frac_near_nvl", "delta_frac_near_fam")
FAMILY_SEXES: tuple[str, ...] = ("F", "M")
FAMILY_A_SIZE: int = len(FAMILY_METRICS) * len(FAMILY_SEXES)
SESSION_STEP = "BL->TX"
LEFT_SESSION = "NOR_BL"
RIGHT_SESSION = "NOR_TX"
TRIAL = "nvl_obj"
GRAIN = "animal × BL→TX × nvl_obj × object_prox_r=0.10m (median across models)"

DEFAULT_ANIMALS = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_object_prox_0p10\object_prox_metrics_per_animal.csv"
)
DEFAULT_OUT = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_occupancy_session_delta"
)


def paired_occupancy_delta(consensus: pd.DataFrame) -> pd.DataFrame:
    """One row per animal: BL→TX Δ of frac_near_nvl / frac_near_fam."""
    need = {
        "animal_id",
        "sex",
        "condition",
        "session",
        "frac_near_nvl",
        "frac_near_fam",
    }
    missing = need - set(consensus.columns)
    if missing:
        raise KeyError(f"consensus missing {sorted(missing)}")
    bl = consensus[consensus["session"] == LEFT_SESSION].copy()
    tx = consensus[consensus["session"] == RIGHT_SESSION].copy()
    keys = ["animal_id", "sex", "condition"]
    m = bl.merge(
        tx[keys + ["frac_near_nvl", "frac_near_fam"]],
        on=keys,
        how="inner",
        suffixes=("_bl", "_tx"),
    )
    out = m[keys].copy()
    out["session_step"] = SESSION_STEP
    out["left"] = LEFT_SESSION
    out["right"] = RIGHT_SESSION
    out["trial"] = TRIAL
    out["frac_near_nvl_bl"] = m["frac_near_nvl_bl"]
    out["frac_near_nvl_tx"] = m["frac_near_nvl_tx"]
    out["frac_near_fam_bl"] = m["frac_near_fam_bl"]
    out["frac_near_fam_tx"] = m["frac_near_fam_tx"]
    out["delta_frac_near_nvl"] = m["frac_near_nvl_tx"] - m["frac_near_nvl_bl"]
    out["delta_frac_near_fam"] = m["frac_near_fam_tx"] - m["frac_near_fam_bl"]
    if "n_models" in bl.columns:
        nm = bl[["animal_id", "n_models"]].drop_duplicates(subset=["animal_id"])
        out = out.merge(nm, on="animal_id", how="left")
    return out.reset_index(drop=True)


def build_family_a_tests(deltas: pd.DataFrame) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for metric in FAMILY_METRICS:
        k = kruskal_within_sex(deltas, metric=metric)
        k = k.copy()
        k["session_step"] = SESSION_STEP
        k["left"] = LEFT_SESSION
        k["right"] = RIGHT_SESSION
        k["trial"] = TRIAL
        k["grain"] = GRAIN
        k["family"] = "OccSessDelta-A"
        k["question"] = "q5_occupancy_session_delta_condition"
        parts.append(k)
    tests = pd.concat(parts, ignore_index=True)
    tests = tests[tests["sex"].isin(FAMILY_SEXES)].reset_index(drop=True)
    n_finite = int(pd.to_numeric(tests["p"], errors="coerce").notna().sum())
    if n_finite != FAMILY_A_SIZE:
        raise AssertionError(f"OccSessDelta-A expects {FAMILY_A_SIZE} finite-p cells, got {n_finite}")
    return apply_bh(tests)


def run(animals_csv: Path, out_dir: Path) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(animals_csv)
    consensus = animal_median_across_models(raw)
    deltas = paired_occupancy_delta(consensus)
    deltas.to_csv(out_dir / "occupancy_session_delta_per_animal.csv", index=False)
    tests = build_family_a_tests(deltas)
    tests.to_csv(out_dir / "occupancy_session_delta_tests_long.csv", index=False)

    n_hit = int(tests["hit_fdr05"].astype(bool).sum())
    n_p05 = int(tests["hit_p05"].astype(bool).sum())
    summary: dict[str, object] = {
        "status": "ok",
        "family": "OccSessDelta-A",
        "family_size": FAMILY_A_SIZE,
        "session_step": SESSION_STEP,
        "n_animals": int(deltas["animal_id"].nunique()),
        "n_hit_fdr05": n_hit,
        "n_hit_p05": n_p05,
        "pass_family_a": bool(n_hit > 0),
        "metrics": list(FAMILY_METRICS),
        "peek_caveat": (
            "Uncorrected Kruskal p on delta_frac_near_nvl inspected in chat "
            "before family declaration; BH q is the claim gate."
        ),
        "animals_csv": str(animals_csv),
        "hit_rule": "q_bh < 0.05 within OccSessDelta-A (4 Kruskal cells)",
    }
    if n_hit > 0:
        hits = tests.loc[tests["hit_fdr05"].astype(bool)]
        summary["hits"] = hits[
            ["sex", "metric", "p", "q_bh", "n", "median_noSD", "median_GHSD", "median_RBSD"]
        ].to_dict(orient="records")
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("n_hit_fdr05", "n_hit_p05", "pass_family_a")}, indent=2))
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--animals-csv", type=Path, default=DEFAULT_ANIMALS)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    if not args.animals_csv.is_file():
        print(f"missing {args.animals_csv}", file=sys.stderr)
        return 1
    run(args.animals_csv, args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
