"""Q5 TransStruct Family A — bout-transition structure at NOR_TX x nvl_obj.

Portable alphabet: HDBSCAN ``cluster_id`` (via syllable_prototypes_clustered.csv)
on the locked pilot kpMS model. Per-animal P(next | current) with Laplace
smoothing; primary = total-variation distance to sex-pooled noSD reference P;
companion = H(next | current) bits. Kruskal by condition within sex; BH FDR
over the pre-declared 4-cell TransStruct-A family.

Bout stream = RLE labels (consecutive bouts differ by construction; raw
diagonal counts are zero — diagonal mass in P is Laplace smoothing only).
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

from nor_object_mi.join_keys import filter_cohort, iter_joined_sessions  # noqa: E402
from nor_object_mi.simpler_first_da import apply_bh  # noqa: E402
from nor_object_mi.simpler_first_q1 import kruskal_within_sex  # noqa: E402
from nor_object_mi.syllable_cleanup import rle_labels  # noqa: E402
from nor_object_mi.transition_structure import (  # noqa: E402
    FAMILY_A_SIZE,
    FAMILY_METRICS,
    FAMILY_SEXES,
    FAMILY_SESSION,
    FAMILY_TRIAL,
    GRAIN,
    LAPLACE_ALPHA,
    MIN_BOUTS,
    assert_family_a_size,
    conditional_entropy_next_given_current,
    pooled_reference_P,
    total_variation,
    transition_matrix,
)

MODEL = "paramscan_s1-1e8_s2-1e5_ss-50"

DEFAULT_NOR_H5 = Path(r"D:\sack\datas\impress\my_NOR_results.h5")
DEFAULT_KPMS = Path(r"D:\sack\datas\impress\moseq_251017" rf"\{MODEL}\results.h5")
DEFAULT_PROTO = Path(r"D:\sack\datas\impress\moseq_251017" r"\_nor_object_mi\simpler_first_syllable_signatures\syllable_prototypes_clustered.csv")
DEFAULT_OUT = Path(r"D:\sack\datas\impress\moseq_251017" r"\_nor_object_mi\simpler_first_transition_structure")


def load_cluster_map(proto_csv: Path, *, model: str) -> dict[int, int]:
    proto = pd.read_csv(proto_csv)
    sub = proto[proto["model"] == model].copy()
    if sub.empty:
        raise ValueError(f"no prototype rows for model {model!r} in {proto_csv}")
    mapping: dict[int, int] = {}
    for _, r in sub.iterrows():
        mapping[int(r["raw_syllable_id"])] = int(r["cluster_id"])
    return mapping


def bout_cluster_labels(
    syll: np.ndarray,
    cluster_map: dict[int, int],
) -> tuple[np.ndarray, int]:
    """RLE bout labels remapped to cluster_id. Returns (labels, n_unmapped)."""
    labels, _, _ = rle_labels(np.asarray(syll, dtype=np.int64).ravel())
    out: list[int] = []
    n_unmapped = 0
    for sid in labels.tolist():
        cid = cluster_map.get(int(sid))
        if cid is None:
            n_unmapped += 1
            continue
        out.append(int(cid))
    return np.asarray(out, dtype=np.int64), n_unmapped


def run(
    nor_h5_path: Path,
    kpms_path: Path,
    proto_csv: Path,
    out_dir: Path,
    *,
    model: str = MODEL,
    min_bouts: int = MIN_BOUTS,
    alpha: float = LAPLACE_ALPHA,
) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    cluster_map = load_cluster_map(proto_csv, model=model)
    states = sorted(set(cluster_map.values()))
    print(f"alphabet: {len(states)} cluster states, model={model}", flush=True)

    kept_rows: list[dict[str, object]] = []
    seq_store: dict[str, np.ndarray] = {}
    meta_store: dict[str, dict[str, str]] = {}
    with h5py.File(nor_h5_path, "r") as nor_h5, h5py.File(kpms_path, "r") as kpms_h5:
        kept = set(filter_cohort(nor_h5)["kept_ids"])
        n_unmapped_tot = 0
        n_skip_short = 0
        for js in iter_joined_sessions(nor_h5, kpms_h5, kept_ids=kept, session=FAMILY_SESSION):
            if js.trial != FAMILY_TRIAL:
                continue
            try:
                syll = kpms_h5[js.kpms_key]["syllable"][()]
            except (KeyError, OSError):
                continue
            labs, n_unmapped = bout_cluster_labels(syll, cluster_map)
            n_unmapped_tot += int(n_unmapped)
            if len(labs) < min_bouts:
                n_skip_short += 1
                continue
            P, C = transition_matrix(labs, states, alpha=alpha)
            H = conditional_entropy_next_given_current(P, C)
            kept_rows.append(
                {
                    "animal_id": js.animal_id,
                    "sex": js.sex,
                    "condition": js.condition,
                    "session": FAMILY_SESSION,
                    "trial": FAMILY_TRIAL,
                    "kpms_key": js.kpms_key,
                    "raw_session": js.raw_session,
                    "model": model,
                    "alphabet": "cluster_id",
                    "n_states": len(states),
                    "n_bouts": int(len(labs)),
                    "n_transitions": int(len(labs) - 1),
                    "n_unmapped_bouts": int(n_unmapped),
                    "H_next_given_curr": float(H),
                }
            )
            seq_store[js.animal_id] = labs
            meta_store[js.animal_id] = {"sex": js.sex, "condition": js.condition}

    animals = pd.DataFrame(kept_rows)
    print(f"Scored {len(animals)} animals in {time.time() - t0:.1f}s", flush=True)

    # Sex-pooled noSD references at the same grain.
    refs: dict[str, np.ndarray] = {}
    ref_counts: dict[str, float] = {}
    ref_n: dict[str, int] = {}
    for sex in FAMILY_SEXES:
        ref_seqs = [seq_store[aid] for aid, m in meta_store.items() if m["sex"] == sex and m["condition"] == "noSD" and aid in seq_store]
        if not ref_seqs:
            raise ValueError(f"no noSD sequences for sex {sex!r}")
        P_ref, C_ref = pooled_reference_P(ref_seqs, states, alpha=alpha)
        refs[sex] = P_ref
        ref_counts[sex] = float(C_ref.sum())
        ref_n[sex] = len(ref_seqs)

    tv_list: list[float] = []
    for _, r in animals.iterrows():
        labs = seq_store[str(r["animal_id"])]
        P, _ = transition_matrix(labs, states, alpha=alpha)
        tv_list.append(total_variation(P, refs[str(r["sex"])]))
    animals["trans_dist_to_nosd_ref"] = np.asarray(tv_list, dtype=np.float64)

    animals.to_csv(out_dir / "transition_structure_per_animal.csv", index=False)

    parts: list[pd.DataFrame] = []
    for metric in FAMILY_METRICS:
        k = kruskal_within_sex(animals, metric=metric)
        k = k.copy()
        k["session"] = FAMILY_SESSION
        k["trial"] = FAMILY_TRIAL
        k["grain"] = GRAIN
        k["family"] = "TransStruct-A"
        k["question"] = "q5_transition_structure_condition"
        parts.append(k)
    tests = pd.concat(parts, ignore_index=True)
    tests = tests[tests["sex"].isin(FAMILY_SEXES)].reset_index(drop=True)
    n_finite = int(pd.to_numeric(tests["p"], errors="coerce").notna().sum())
    assert_family_a_size(n_finite)
    tests = apply_bh(tests)
    tests.to_csv(out_dir / "transition_structure_tests_long.csv", index=False)

    n_hit = int(tests["hit_fdr05"].astype(bool).sum())
    n_p05 = int(tests["hit_p05"].astype(bool).sum())
    summary: dict[str, object] = {
        "status": "ok",
        "family": "TransStruct-A",
        "family_size": FAMILY_A_SIZE,
        "model": model,
        "alphabet": "cluster_id",
        "n_states": len(states),
        "states": states,
        "alpha_laplace": float(alpha),
        "distance": "total_variation_0.5_L1_full_matrix",
        "min_bouts": int(min_bouts),
        "n_animals": int(animals["animal_id"].nunique()) if len(animals) else 0,
        "n_skip_short": int(n_skip_short),
        "n_unmapped_bouts_total": int(n_unmapped_tot),
        "ref_n_animals": ref_n,
        "ref_n_transitions": ref_counts,
        "n_hit_fdr05": n_hit,
        "n_hit_p05": n_p05,
        "pass_family_a": bool(n_hit > 0),
        "metrics": list(FAMILY_METRICS),
        "sexes": list(FAMILY_SEXES),
        "session": FAMILY_SESSION,
        "trial": FAMILY_TRIAL,
        "nor_h5": str(nor_h5_path),
        "kpms_results": str(kpms_path),
        "prototypes_csv": str(proto_csv),
        "rle_note": "consecutive bouts differ by construction; raw diagonal counts are zero",
        "hit_rule": "q_bh < 0.05 within TransStruct-A (4 Kruskal cells)",
        "elapsed_s": float(time.time() - t0),
    }
    if n_hit > 0:
        hits = tests.loc[tests["hit_fdr05"].astype(bool)].copy()
        summary["hits"] = hits[["sex", "metric", "p", "q_bh", "n", "median_noSD", "median_GHSD", "median_RBSD"]].to_dict(orient="records")
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {k: summary[k] for k in ("n_hit_fdr05", "n_hit_p05", "pass_family_a", "family_size")},
            indent=2,
        ),
        flush=True,
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--nor-h5", type=Path, default=DEFAULT_NOR_H5)
    ap.add_argument("--kpms-results", type=Path, default=DEFAULT_KPMS)
    ap.add_argument("--prototypes-csv", type=Path, default=DEFAULT_PROTO)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--model", type=str, default=MODEL)
    ap.add_argument("--min-bouts", type=int, default=MIN_BOUTS)
    ap.add_argument("--alpha", type=float, default=LAPLACE_ALPHA)
    args = ap.parse_args(argv)
    for label, p in (
        ("nor-h5", args.nor_h5),
        ("kpms-results", args.kpms_results),
        ("prototypes-csv", args.prototypes_csv),
    ):
        if not p.is_file():
            print(f"{label} missing: {p}", file=sys.stderr)
            return 1
    run(args.nor_h5, args.kpms_results, args.prototypes_csv, args.out_dir, model=args.model, min_bouts=int(args.min_bouts), alpha=float(args.alpha))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
