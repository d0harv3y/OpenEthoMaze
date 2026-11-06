"""Q5 NGramSeq Family A — fixed-budget pair-sequence structure at NOR_TX x nvl_obj.

Portable cluster_id alphabet on the locked pilot model. Per-animal M-pair
resample (seeded); pair MI + bigram richness; Kruskal by condition within
sex; BH FDR over the pre-declared 4-cell NGramSeq-A family. No pooled
reference: counts cannot launder into signal by construction.
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
from nor_object_mi.ngram_structure import (  # noqa: E402
    FAMILY_A_SIZE,
    FAMILY_METRICS,
    FAMILY_SEXES,
    GRAIN,
    MIN_TRANSITIONS_FLOOR,
    SEED,
    assert_family_a_size,
    bigram_richness_from_counts,
    pair_mi_from_counts,
    resample_pairs,
)
from nor_object_mi.simpler_first_da import apply_bh  # noqa: E402
from nor_object_mi.simpler_first_q1 import kruskal_within_sex  # noqa: E402
from nor_object_mi.syllable_cleanup import rle_labels  # noqa: E402

MODEL = "paramscan_s1-1e8_s2-1e5_ss-50"
SESSION = "NOR_TX"
TRIAL = "nvl_obj"

DEFAULT_NOR_H5 = Path(r"D:\sack\datas\impress\my_NOR_results.h5")
DEFAULT_KPMS = Path(r"D:\sack\datas\impress\moseq_251017" rf"\{MODEL}\results.h5")
DEFAULT_PROTO = Path(r"D:\sack\datas\impress\moseq_251017" r"\_nor_object_mi\simpler_first_syllable_signatures\syllable_prototypes_clustered.csv")
DEFAULT_OUT = Path(r"D:\sack\datas\impress\moseq_251017" r"\_nor_object_mi\simpler_first_ngram_seq")


def run(nor_h5_path: Path, kpms_path: Path, proto_csv: Path, out_dir: Path) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    proto = pd.read_csv(proto_csv)
    sub = proto[proto["model"] == MODEL]
    if sub.empty:
        raise ValueError(f"no prototype rows for {MODEL}")
    cmap = {int(r["raw_syllable_id"]): int(r["cluster_id"]) for _, r in sub.iterrows()}
    states = sorted(set(cmap.values()))

    seqs: dict[str, np.ndarray] = {}
    meta: dict[str, dict[str, str]] = {}
    n_unmapped = 0
    with h5py.File(nor_h5_path, "r") as nor_h5, h5py.File(kpms_path, "r") as kpms_h5:
        kept = set(filter_cohort(nor_h5)["kept_ids"])
        for js in iter_joined_sessions(nor_h5, kpms_h5, kept_ids=kept, session=SESSION):
            if js.trial != TRIAL:
                continue
            try:
                syll = kpms_h5[js.kpms_key]["syllable"][()]
            except (KeyError, OSError):
                continue
            labels, _, _ = rle_labels(np.asarray(syll, dtype=np.int64).ravel())
            mapped = []
            for sid in labels.tolist():
                cid = cmap.get(int(sid))
                if cid is None:
                    n_unmapped += 1
                else:
                    mapped.append(int(cid))
            if len(mapped) < 2:
                continue
            seqs[js.animal_id] = np.asarray(mapped, dtype=np.int64)
            meta[js.animal_id] = {"sex": js.sex, "condition": js.condition}

    M = int(min(len(v) - 1 for v in seqs.values()))
    if M < MIN_TRANSITIONS_FLOOR:
        raise ValueError(f"budget M={M} below floor {MIN_TRANSITIONS_FLOOR}")
    rng = np.random.default_rng(SEED)
    rows = []
    for aid, labs in seqs.items():
        C = resample_pairs(labs, states, M, rng)
        rows.append(
            {
                "animal_id": aid,
                "sex": meta[aid]["sex"],
                "condition": meta[aid]["condition"],
                "session": SESSION,
                "trial": TRIAL,
                "model": MODEL,
                "alphabet": "cluster_id",
                "n_states": len(states),
                "n_transitions_used": M,
                "pair_MI": float(pair_mi_from_counts(C)),
                "bigram_richness": int(bigram_richness_from_counts(C)),
            }
        )
    animals = pd.DataFrame(rows)
    print(f"Scored {len(animals)} animals, M={M}", flush=True)
    animals.to_csv(out_dir / "ngram_seq_per_animal.csv", index=False)

    parts = []
    for metric in FAMILY_METRICS:
        k = kruskal_within_sex(animals, metric=metric).copy()
        k["session"] = SESSION
        k["trial"] = TRIAL
        k["grain"] = GRAIN
        k["family"] = "NGramSeq-A"
        k["question"] = "q5_ngram_seq_condition"
        parts.append(k)
    tests = pd.concat(parts, ignore_index=True)
    tests = tests[tests["sex"].isin(FAMILY_SEXES)].reset_index(drop=True)
    assert_family_a_size(int(pd.to_numeric(tests["p"], errors="coerce").notna().sum()))
    tests = apply_bh(tests)
    tests.to_csv(out_dir / "ngram_seq_tests_long.csv", index=False)

    n_hit = int(tests["hit_fdr05"].astype(bool).sum())
    n_p05 = int(tests["hit_p05"].astype(bool).sum())
    summary: dict[str, object] = {
        "status": "ok",
        "family": "NGramSeq-A",
        "family_size": FAMILY_A_SIZE,
        "model": MODEL,
        "alphabet": "cluster_id",
        "budget_M": M,
        "seed": SEED,
        "n_animals": int(len(animals)),
        "n_unmapped_bouts": int(n_unmapped),
        "n_hit_fdr05": n_hit,
        "n_hit_p05": n_p05,
        "pass_family_a": bool(n_hit > 0),
        "hit_rule": "q_bh < 0.05 within NGramSeq-A (4 Kruskal cells)",
        "elapsed_s": float(time.time() - t0),
    }
    if n_hit:
        hits = tests.loc[tests["hit_fdr05"].astype(bool)].copy()
        summary["hits"] = hits[["sex", "metric", "p", "q_bh", "n", "median_noSD", "median_GHSD", "median_RBSD"]].to_dict(orient="records")
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"n_hit_fdr05": n_hit, "n_hit_p05": n_p05, "M": M}, indent=2), flush=True)
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--nor-h5", type=Path, default=DEFAULT_NOR_H5)
    ap.add_argument("--kpms-results", type=Path, default=DEFAULT_KPMS)
    ap.add_argument("--prototypes-csv", type=Path, default=DEFAULT_PROTO)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    for label, p in (("nor-h5", args.nor_h5), ("kpms-results", args.kpms_results), ("prototypes-csv", args.prototypes_csv)):
        if not p.is_file():
            print(f"{label} missing: {p}", file=sys.stderr)
            return 1
    run(args.nor_h5, args.kpms_results, args.prototypes_csv, args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
