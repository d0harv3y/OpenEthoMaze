"""Exploratory: NGramSeq cells with raw alphabets (ladder) + recog fits.

Same 2 scalars (pair MI + bigram richness) at fixed per-model budgets,
BH within each model (4-cell family). Descriptive global BH included.
No lock language: the locked verdict stands on the pilot cluster run.
"""

from __future__ import annotations

import argparse
import glob
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
    FAMILY_METRICS,
    FAMILY_SEXES,
    MIN_TRANSITIONS_FLOOR,
    SEED,
    score_budgeted_animals,
)
from nor_object_mi.simpler_first_da import apply_bh, benjamini_hochberg  # noqa: E402
from nor_object_mi.simpler_first_q1 import kruskal_within_sex  # noqa: E402
from nor_object_mi.syllable_cleanup import rle_labels  # noqa: E402

SESSION = "NOR_TX"
TRIAL = "nvl_obj"

DEFAULT_NOR_H5 = Path(r"D:\sack\datas\impress\my_NOR_results.h5")
DEFAULT_LADDER = Path(r"D:\sack\datas\impress\moseq_251017")
DEFAULT_LADDER_PROTO = DEFAULT_LADDER / "_nor_object_mi" / "simpler_first_syllable_signatures" / "syllable_prototypes_clustered.csv"
DEFAULT_RECOG = Path(r"D:\sack\datas\impress\moseq_recog_260915\anatomical")
DEFAULT_RECOG_PROTO = DEFAULT_RECOG / "_nor_object_mi" / "simpler_first_syllable_signatures" / "syllable_prototypes_clustered.csv"
DEFAULT_OUT_LADDER = DEFAULT_LADDER / "_nor_object_mi" / "simpler_first_ngram_seq_raw"
DEFAULT_OUT_RECOG = DEFAULT_RECOG / "_nor_object_mi" / "simpler_first_ngram_seq"


def collect(nor_h5, kpms_h5, cluster_map=None):
    kept = set(filter_cohort(nor_h5)["kept_ids"])
    seqs, meta = {}, {}
    n_unmapped = 0
    for js in iter_joined_sessions(nor_h5, kpms_h5, kept_ids=kept, session=SESSION):
        if js.trial != TRIAL:
            continue
        try:
            syll = kpms_h5[js.kpms_key]["syllable"][()]
        except (KeyError, OSError):
            continue
        labels, _, _ = rle_labels(np.asarray(syll, dtype=np.int64).ravel())
        labs = []
        for sid in labels.tolist():
            if cluster_map is not None:
                cid = cluster_map.get(int(sid))
                if cid is None:
                    n_unmapped += 1
                else:
                    labs.append(int(cid))
            else:
                labs.append(int(sid))
        if len(labs) < 2:
            continue
        seqs[js.animal_id] = np.asarray(labs, dtype=np.int64)
        meta[js.animal_id] = {"sex": js.sex, "condition": js.condition}
    states = sorted({int(x) for v in seqs.values() for x in v.tolist()})
    return seqs, meta, states, n_unmapped


def run_grid(nor_h5_path, models, proto_csv, out_dir, tag, want_cluster):
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    proto = pd.read_csv(proto_csv) if want_cluster else None
    animal_frames, test_frames, notes = [], [], {}
    with h5py.File(nor_h5_path, "r") as nor_h5:
        for model, results in models:
            with h5py.File(results, "r") as kh:
                seqs_r, meta_r, states_r, _ = collect(nor_h5, kh, None)
                jobs = [("raw_syllable_id", seqs_r, meta_r, states_r)]
                if want_cluster:
                    assert proto is not None
                    sub = proto[proto["model"] == model]
                    cmap = {int(r["raw_syllable_id"]): int(r["cluster_id"]) for _, r in sub.iterrows()}
                    seqs_c, meta_c, states_c, unmap = collect(nor_h5, kh, cmap)
                    jobs.append(("cluster_id", seqs_c, meta_c, states_c))
                    notes[model] = {"raw_states": len(states_r), "cluster_states": len(states_c), "unmapped": int(unmap)}
                else:
                    notes[model] = {"raw_states": len(states_r)}
                for alphabet, seqs, meta, states in jobs:
                    M = int(min(len(v) - 1 for v in seqs.values()))
                    if M < MIN_TRANSITIONS_FLOOR:
                        print(f"{model} {alphabet}: SKIP M={M}", flush=True)
                        continue
                    animals = score_budgeted_animals(seqs, meta, states, M, SEED, model=model, alphabet=alphabet)
                    animal_frames.append(animals)
                    parts = []
                    for metric in FAMILY_METRICS:
                        k = kruskal_within_sex(animals, metric=metric).copy()
                        k["session"] = SESSION
                        k["trial"] = TRIAL
                        k["model"] = model
                        k["alphabet"] = alphabet
                        k["family"] = f"NGramSeq-{tag}"
                        parts.append(k)
                    tests = pd.concat(parts, ignore_index=True)
                    tests = tests[tests["sex"].isin(FAMILY_SEXES)].reset_index(drop=True)
                    test_frames.append(apply_bh(tests))
            n_hit = int(test_frames[-1]["hit_fdr05"].astype(bool).sum()) if test_frames else 0
            print(f"{model}: M={M} hits={n_hit}", flush=True)

    animals_all = pd.concat(animal_frames, ignore_index=True) if animal_frames else pd.DataFrame()
    tests_all = pd.concat(test_frames, ignore_index=True) if test_frames else pd.DataFrame()
    if not tests_all.empty:
        p = pd.to_numeric(tests_all["p"], errors="coerce").to_numpy(dtype=float)
        qg = np.full(len(p), np.nan)
        ok = np.isfinite(p)
        qg[ok] = np.asarray(benjamini_hochberg(p[ok].tolist()), dtype=float)
        tests_all["q_bh_global"] = qg
    animals_all.to_csv(out_dir / "ngram_seq_grid_per_animal.csv", index=False)
    tests_all.to_csv(out_dir / "ngram_seq_grid_tests_long.csv", index=False)
    summary = {
        "status": "ok",
        "kind": "exploratory",
        "tag": tag,
        "n_models": len(models),
        "n_hit_within": int(tests_all["hit_fdr05"].astype(bool).sum()) if not tests_all.empty else 0,
        "n_hit_global": int(((tests_all["q_bh_global"] < 0.05).fillna(False)).sum()) if not tests_all.empty else 0,
        "per_model_notes": notes,
        "elapsed_s": float(time.time() - t0),
    }
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("n_hit_within", "n_hit_global")}, indent=2), flush=True)
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--nor-h5", type=Path, default=DEFAULT_NOR_H5)
    ap.add_argument("--which", choices=["ladder", "recog"], required=True)
    args = ap.parse_args(argv)
    if args.which == "ladder":
        models = [(Path(p).parent.name, Path(p)) for p in sorted(glob.glob(str(DEFAULT_LADDER / "paramscan_*" / "results.h5")))]
        run_grid(args.nor_h5, models, DEFAULT_LADDER_PROTO, DEFAULT_OUT_LADDER, "raw", False)
    else:
        models = [(p.name, p / "results.h5") for p in sorted(DEFAULT_RECOG.glob("paramscan_*")) if (p / "results.h5").is_file()]
        run_grid(args.nor_h5, models, DEFAULT_RECOG_PROTO, DEFAULT_OUT_RECOG, "recog", True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
