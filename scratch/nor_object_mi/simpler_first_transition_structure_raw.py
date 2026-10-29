"""Exploratory: TransStruct-A cells with raw_syllable_id alphabet, per model.

Same 4-cell design as the locked TransStruct-A (TV distance to sex-pooled noSD
reference + H(next | current), Kruskal by condition within sex at NOR_TX x
nvl_obj, Laplace alpha=1.0, min 20 bouts) but with each model's **raw**
syllable ids as the alphabet instead of portable cluster_id.

Status is **exploratory / methods**: raw ids are not portable across models
(see ADR-0005 lineage), states differ per model, and large alphabets (ss-100)
make P sparse. BH is applied **within each model** (4-cell family, matching
the locked rule); `q_bh_global` over all 21x4 cells is descriptive. No lock
language: the locked negative stands on the cluster-alphabet run.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import h5py
import numpy as np
import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.bout_kinematics import discover_paramscan_models  # noqa: E402
from nor_object_mi.join_keys import filter_cohort, iter_joined_sessions  # noqa: E402
from nor_object_mi.simpler_first_da import apply_bh  # noqa: E402
from nor_object_mi.simpler_first_q1 import kruskal_within_sex  # noqa: E402
from nor_object_mi.syllable_cleanup import rle_labels  # noqa: E402
from nor_object_mi.transition_structure import (  # noqa: E402
    FAMILY_METRICS,
    FAMILY_SEXES,
    FAMILY_SESSION,
    FAMILY_TRIAL,
    GRAIN,
    LAPLACE_ALPHA,
    MIN_BOUTS,
    conditional_entropy_next_given_current,
    pooled_reference_P,
    total_variation,
    transition_matrix,
)

DEFAULT_NOR_H5 = Path(r"D:\sack\datas\impress\my_NOR_results.h5")
DEFAULT_ENSEMBLE = Path(r"D:\sack\datas\impress\moseq_251017")
DEFAULT_OUT = Path(r"D:\sack\datas\impress\moseq_251017" r"\_nor_object_mi\simpler_first_transition_structure_raw")


def score_model(
    nor_h5: h5py.File,
    kpms_h5: h5py.File,
    *,
    model: str,
    min_bouts: int = MIN_BOUTS,
    alpha: float = LAPLACE_ALPHA,
) -> tuple[pd.DataFrame, list[str]]:
    """Per-animal TransStruct scalars with raw-syllable alphabet. Two passes."""
    kept = set(filter_cohort(nor_h5)["kept_ids"])
    seqs: dict[str, np.ndarray] = {}
    meta: dict[str, dict[str, str]] = {}
    n_skip_short = 0
    for js in iter_joined_sessions(nor_h5, kpms_h5, kept_ids=kept, session=FAMILY_SESSION):
        if js.trial != FAMILY_TRIAL:
            continue
        try:
            syll = kpms_h5[js.kpms_key]["syllable"][()]
        except (KeyError, OSError):
            continue
        labels, _, _ = rle_labels(np.asarray(syll, dtype=np.int64).ravel())
        if len(labels) < min_bouts:
            n_skip_short += 1
            continue
        seqs[js.animal_id] = labels
        meta[js.animal_id] = {
            "sex": js.sex,
            "condition": js.condition,
            "kpms_key": js.kpms_key,
            "raw_session": js.raw_session,
        }
    if not seqs:
        return pd.DataFrame(), [f"n_skip_short={n_skip_short}"]
    states = sorted({int(x) for labs in seqs.values() for x in labs.tolist()})
    refs: dict[str, np.ndarray] = {}
    ref_info: dict[str, str] = {}
    for sex in FAMILY_SEXES:
        ref_seqs = [labs for aid, labs in seqs.items() if meta[aid]["sex"] == sex and meta[aid]["condition"] == "noSD"]
        if not ref_seqs:
            raise ValueError(f"model {model}: no noSD sequences for sex {sex!r}")
        P_ref, C_ref = pooled_reference_P(ref_seqs, states, alpha=alpha)
        refs[sex] = P_ref
        ref_info[sex] = f"n={len(ref_seqs)},trans={float(C_ref.sum()):.0f}"
    rows: list[dict[str, object]] = []
    for aid, labs in seqs.items():
        P, C = transition_matrix(labs, states, alpha=alpha)
        rows.append(
            {
                "animal_id": aid,
                "sex": meta[aid]["sex"],
                "condition": meta[aid]["condition"],
                "session": FAMILY_SESSION,
                "trial": FAMILY_TRIAL,
                "kpms_key": meta[aid]["kpms_key"],
                "raw_session": meta[aid]["raw_session"],
                "model": model,
                "alphabet": "raw_syllable_id",
                "n_states": len(states),
                "n_bouts": int(len(labs)),
                "n_transitions": int(len(labs) - 1),
                "H_next_given_curr": float(conditional_entropy_next_given_current(P, C)),
                "trans_dist_to_nosd_ref": float(total_variation(P, refs[meta[aid]["sex"]])),
            }
        )
    animals = pd.DataFrame(rows)
    notes = [f"n_skip_short={n_skip_short}", f"ref_F={ref_info.get('F')}", f"ref_M={ref_info.get('M')}"]
    return animals, notes


def run_grid(
    nor_h5_path: Path,
    ensemble_root: Path,
    out_dir: Path,
    *,
    min_bouts: int = MIN_BOUTS,
    alpha: float = LAPLACE_ALPHA,
) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    models = discover_paramscan_models(ensemble_root)
    if not models:
        raise ValueError(f"no paramscan models under {ensemble_root}")
    all_animals: list[pd.DataFrame] = []
    all_tests: list[pd.DataFrame] = []
    per_model_notes: dict[str, list[str]] = {}
    with h5py.File(nor_h5_path, "r") as nor_h5:
        for model in models:
            results = ensemble_root / model / "results.h5"
            with h5py.File(results, "r") as kpms_h5:
                animals, notes = score_model(nor_h5, kpms_h5, model=model, min_bouts=min_bouts, alpha=alpha)
            per_model_notes[model] = notes
            if animals.empty:
                continue
            all_animals.append(animals)
            parts: list[pd.DataFrame] = []
            for metric in FAMILY_METRICS:
                k = kruskal_within_sex(animals, metric=metric).copy()
                k["session"] = FAMILY_SESSION
                k["trial"] = FAMILY_TRIAL
                k["model"] = model
                k["alphabet"] = "raw_syllable_id"
                k["grain"] = GRAIN + " [raw alphabet, exploratory]"
                k["family"] = "TransStruct-A-raw"
                k["question"] = "q5_transition_structure_condition_raw_exploratory"
                parts.append(k)
            tests = pd.concat(parts, ignore_index=True)
            tests = tests[tests["sex"].isin(FAMILY_SEXES)].reset_index(drop=True)
            tests = apply_bh(tests)  # within-model 4-cell family
            all_tests.append(tests)
            n_hit = int(tests["hit_fdr05"].astype(bool).sum())
            print(f"{model}: n={len(animals)} states={int(animals['n_states'].iloc[0])} hits={n_hit}", flush=True)

    animals_all = pd.concat(all_animals, ignore_index=True) if all_animals else pd.DataFrame()
    tests_all = pd.concat(all_tests, ignore_index=True) if all_tests else pd.DataFrame()
    # Descriptive global BH over all model x cell rows (not the claim gate).
    if not tests_all.empty:
        from nor_object_mi.simpler_first_da import benjamini_hochberg  # noqa: E402

        p = pd.to_numeric(tests_all["p"], errors="coerce").to_numpy(dtype=np.float64)
        qg = np.full(p.shape, np.nan)
        ok = np.isfinite(p)
        if np.any(ok):
            qg[ok] = np.asarray(benjamini_hochberg(p[ok].tolist()), dtype=np.float64)
        tests_all["q_bh_global"] = qg
        tests_all["hit_fdr05_global"] = np.isfinite(qg) & (qg < 0.05)

    animals_all.to_csv(out_dir / "transition_structure_raw_per_animal.csv", index=False)
    tests_all.to_csv(out_dir / "transition_structure_raw_tests_long.csv", index=False)

    n_hit_within = int(tests_all["hit_fdr05"].astype(bool).sum()) if not tests_all.empty else 0
    n_hit_global = int(tests_all["hit_fdr05_global"].astype(bool).sum()) if not tests_all.empty else 0
    models_with_hit = sorted(tests_all.loc[tests_all["hit_fdr05"].astype(bool), "model"].unique().tolist()) if not tests_all.empty else []
    summary: dict[str, object] = {
        "status": "ok",
        "family": "TransStruct-A-raw",
        "kind": "exploratory",
        "n_models": len(models),
        "n_animals_per_model": int(animals_all.groupby("model")["animal_id"].nunique().median()) if not animals_all.empty else 0,
        "n_test_rows": int(len(tests_all)),
        "n_hit_fdr05_within_model": n_hit_within,
        "n_hit_fdr05_global": n_hit_global,
        "models_with_within_model_hit": models_with_hit,
        "alpha_laplace": float(alpha),
        "distance": "total_variation_0.5_L1_full_matrix",
        "min_bouts": int(min_bouts),
        "hit_rule_note": "q_bh within-model 4-cell family; q_bh_global descriptive only; no lock language",
        "nor_h5": str(nor_h5_path),
        "ensemble_root": str(ensemble_root),
        "per_model_notes": per_model_notes,
        "elapsed_s": float(time.time() - t0),
    }
    if models_with_hit:
        hits = tests_all.loc[tests_all["hit_fdr05"].astype(bool)].copy()
        summary["hits"] = hits[["model", "sex", "metric", "p", "q_bh", "n", "median_noSD", "median_GHSD", "median_RBSD"]].to_dict(orient="records")
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {k: summary[k] for k in ("n_hit_fdr05_within_model", "n_hit_fdr05_global", "models_with_within_model_hit")},
            indent=2,
        ),
        flush=True,
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--nor-h5", type=Path, default=DEFAULT_NOR_H5)
    ap.add_argument("--ensemble-root", type=Path, default=DEFAULT_ENSEMBLE)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--min-bouts", type=int, default=MIN_BOUTS)
    ap.add_argument("--alpha", type=float, default=LAPLACE_ALPHA)
    args = ap.parse_args(argv)
    if not args.nor_h5.is_file():
        print(f"nor-h5 missing: {args.nor_h5}", file=sys.stderr)
        return 1
    if not args.ensemble_root.is_dir():
        print(f"ensemble-root missing: {args.ensemble_root}", file=sys.stderr)
        return 1
    run_grid(args.nor_h5, args.ensemble_root, args.out_dir, min_bouts=int(args.min_bouts), alpha=float(args.alpha))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
