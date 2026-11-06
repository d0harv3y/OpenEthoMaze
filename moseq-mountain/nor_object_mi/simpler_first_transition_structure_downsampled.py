"""Decisive confound check: fixed-transition downsampled TransStruct rerun (recog).

TV distance with Laplace smoothing is count-dependent (fewer transitions ->
nearer-uniform P -> farther from reference). This rerun fixes the transition
budget per model (M = min transitions across kept animals), resampling pairs
without replacement (seeded), rebuilding P and the noSD reference from the
same budget, then repeating the 4-cell Kruskal + within-model BH.

If the TV hits were transition structure, they survive. If they were count
laundering, they vanish. H is recomputed on the same budget as a control.
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
    FAMILY_METRICS,
    FAMILY_SEXES,
    FAMILY_SESSION,
    FAMILY_TRIAL,
    GRAIN,
    LAPLACE_ALPHA,
    conditional_entropy_next_given_current,
    row_stochastic_with_laplace,
    total_variation,
)

DEFAULT_NOR_H5 = Path(r"D:\sack\datas\impress\my_NOR_results.h5")
DEFAULT_RECOG = Path(r"D:\sack\datas\impress\moseq_recog_260915\anatomical")
DEFAULT_PROTO = DEFAULT_RECOG / "_nor_object_mi" / "simpler_first_syllable_signatures" / "syllable_prototypes_clustered.csv"
DEFAULT_OUT = DEFAULT_RECOG / "_nor_object_mi" / "simpler_first_transition_structure_downsampled"
SEED = 7


def run(nor_h5_path: Path, recog_root: Path, proto_csv: Path, out_dir: Path) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    proto = pd.read_csv(proto_csv)
    rng = np.random.default_rng(SEED)
    animal_frames: list[pd.DataFrame] = []
    test_frames: list[pd.DataFrame] = []
    model_rows = sorted(p for p in recog_root.glob("paramscan_*") if (p / "results.h5").is_file())
    summary_models: dict[str, dict[str, object]] = {}
    with h5py.File(nor_h5_path, "r") as nor_h5:
        kept = set(filter_cohort(nor_h5)["kept_ids"])
        for mp in model_rows:
            model = mp.name
            cmap = {int(r["raw_syllable_id"]): int(r["cluster_id"]) for _, r in proto[proto["model"] == model].iterrows()}
            states = sorted(set(cmap.values()))
            seqs: dict[str, np.ndarray] = {}
            meta: dict[str, dict[str, str]] = {}
            with h5py.File(mp / "results.h5", "r") as kpms_h5:
                for js in iter_joined_sessions(nor_h5, kpms_h5, kept_ids=kept, session=FAMILY_SESSION):
                    if js.trial != FAMILY_TRIAL:
                        continue
                    try:
                        syll = kpms_h5[js.kpms_key]["syllable"][()]
                    except (KeyError, OSError):
                        continue
                    labels, _, _ = rle_labels(np.asarray(syll, dtype=np.int64).ravel())
                    mapped = [cmap[int(s)] for s in labels.tolist() if int(s) in cmap]
                    if len(mapped) < 2:
                        continue
                    seqs[js.animal_id] = np.asarray(mapped, dtype=np.int64)
                    meta[js.animal_id] = {"sex": js.sex, "condition": js.condition}
            if not seqs:
                continue
            M = int(min(len(v) - 1 for v in seqs.values()))
            # Fixed-budget pair resampling per animal.
            sampled: dict[str, np.ndarray] = {}
            C_used: dict[str, np.ndarray] = {}
            for aid, labs in seqs.items():
                n_pairs = len(labs) - 1
                idx = rng.choice(n_pairs, size=M, replace=False)
                C = np.zeros((len(states), len(states)))
                sidx = {s: i for i, s in enumerate(states)}
                for j in idx:
                    C[sidx[int(labs[j])], sidx[int(labs[j + 1])]] += 1.0
                C_used[aid] = C
                sampled[aid] = labs
            refs = {}
            for sex in FAMILY_SEXES:
                pool = np.zeros((len(states), len(states)))
                for aid, C in C_used.items():
                    if meta[aid]["sex"] == sex and meta[aid]["condition"] == "noSD":
                        pool += C
                refs[sex] = row_stochastic_with_laplace(pool, alpha=LAPLACE_ALPHA)
            rows = []
            for aid, C in C_used.items():
                P = row_stochastic_with_laplace(C, alpha=LAPLACE_ALPHA)
                rows.append(
                    {
                        "animal_id": aid,
                        "sex": meta[aid]["sex"],
                        "condition": meta[aid]["condition"],
                        "session": FAMILY_SESSION,
                        "trial": FAMILY_TRIAL,
                        "model": model,
                        "alphabet": "cluster_id",
                        "n_states": len(states),
                        "n_transitions_used": M,
                        "H_next_given_curr": float(conditional_entropy_next_given_current(P, C)),
                        "trans_dist_to_nosd_ref": float(total_variation(P, refs[meta[aid]["sex"]])),
                    }
                )
            animals = pd.DataFrame(rows)
            animal_frames.append(animals)
            parts = []
            for metric in FAMILY_METRICS:
                k = kruskal_within_sex(animals, metric=metric).copy()
                k["session"] = FAMILY_SESSION
                k["trial"] = FAMILY_TRIAL
                k["model"] = model
                k["grain"] = GRAIN + f" [recog fit, downsampled M={M}]"
                k["family"] = "TransStruct-recog-downsampled"
                parts.append(k)
            tests = apply_bh(pd.concat(parts, ignore_index=True).query("sex in @FAMILY_SEXES").reset_index(drop=True))
            test_frames.append(tests)
            n_hit = int(tests["hit_fdr05"].astype(bool).sum())
            summary_models[model] = {"M": M, "n": len(animals), "hits": n_hit}
            print(f"{model}: M={M} hits={n_hit}", flush=True)

    animals_all = pd.concat(animal_frames, ignore_index=True)
    tests_all = pd.concat(test_frames, ignore_index=True)
    animals_all.to_csv(out_dir / "transition_structure_downsampled_per_animal.csv", index=False)
    tests_all.to_csv(out_dir / "transition_structure_downsampled_tests_long.csv", index=False)
    n_hit = int(tests_all["hit_fdr05"].astype(bool).sum())
    summary = {
        "status": "ok",
        "kind": "confound_check",
        "seed": SEED,
        "n_models": len(summary_models),
        "n_hit_fdr05": n_hit,
        "models": summary_models,
        "elapsed_s": float(time.time() - t0),
    }
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"n_hit_fdr05": n_hit}, indent=2), flush=True)
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--nor-h5", type=Path, default=DEFAULT_NOR_H5)
    ap.add_argument("--recog-root", type=Path, default=DEFAULT_RECOG)
    ap.add_argument("--prototypes-csv", type=Path, default=DEFAULT_PROTO)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    run(args.nor_h5, args.recog_root, args.prototypes_csv, args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
