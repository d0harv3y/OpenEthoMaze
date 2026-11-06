"""Exploratory: NGramSeq MI + richness on per-animal fits (9 cells).

Animal-local alphabets: MI/richness are computable per animal (no pooled
reference needed), but their scales depend on K_used, which varies per
animal — so K-balance by condition is reported alongside, and any hit with
unbalanced K is uninterpretable as structure. Per-cell M budget (min
transitions), seed 7. BH within cell (4 cells). No lock language.
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

from nor_object_mi.join_keys import parse_kpms_group  # noqa: E402
from nor_object_mi.ngram_structure import (  # noqa: E402
    FAMILY_METRICS,
    FAMILY_SEXES,
    SEED,
    score_budgeted_animals,
)
from nor_object_mi.simpler_first_da import apply_bh  # noqa: E402
from nor_object_mi.simpler_first_q1 import kruskal_within_sex  # noqa: E402
from nor_object_mi.syllable_cleanup import rle_labels  # noqa: E402

DEFAULT_NOR_H5 = Path(r"D:\sack\datas\impress\my_NOR_results.h5")
DEFAULT_PER_ANIMAL = Path(r"D:\sack\datas\impress\nor_per_animal_paramscan")
DEFAULT_OUT = DEFAULT_PER_ANIMAL / "_nor_object_mi" / "simpler_first_ngram_seq"


def run(nor_h5_path: Path, per_animal_root: Path, out_dir: Path) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    results_list = sorted(glob.glob(str(per_animal_root / "exp*" / "*" / "anatomical" / "*_paramscan_*" / "results.h5")))
    cells: dict[str, list[str]] = {}
    for fp in results_list:
        folder = Path(fp).parent.name
        cells.setdefault(folder[folder.index("paramscan_") :], []).append(fp)
    print(f"{len(results_list)} fits in {len(cells)} cells", flush=True)

    animal_rows, test_rows, notes = [], [], {}
    with h5py.File(nor_h5_path, "r") as nor_h5:
        for cell in sorted(cells):
            seqs, meta = {}, {}
            n_skip = 0
            for fp in cells[cell]:
                with h5py.File(fp, "r") as kf:
                    target = None
                    for k in kf.keys():
                        try:
                            aid, raw = parse_kpms_group(str(k))
                        except ValueError:
                            continue
                        if raw == "NOR2_nvl_obj":
                            target = (aid, str(k))
                            break
                    if target is None:
                        n_skip += 1
                        continue
                    aid, key = target
                    if aid not in nor_h5 or "NOR2_nvl_obj" not in nor_h5[aid]:
                        n_skip += 1
                        continue
                    ag = nor_h5[aid]
                    sg = ag["NOR2_nvl_obj"]
                    if str(sg.attrs.get("session", "") or sg.attrs.get("phase_layer", "")) != "NOR_TX":
                        n_skip += 1
                        continue
                    z = kf[key]["syllable"][()]
                    labs, _, _ = rle_labels(np.asarray(z, dtype=np.int64).ravel())
                    if len(labs) < 2:
                        n_skip += 1
                        continue
                    seqs[aid] = np.asarray(labs.tolist(), dtype=np.int64)
                    meta[aid] = {
                        "sex": str(ag.attrs.get("sex", "") or ""),
                        "condition": str(ag.attrs.get("condition", "") or ag.attrs.get("tx", "") or ""),
                    }
            M = int(min(len(v) - 1 for v in seqs.values()))
            states = sorted({int(x) for v in seqs.values() for x in v.tolist()})
            animals = score_budgeted_animals(seqs, meta, states, M, SEED, model=cell, alphabet="per_animal_raw_syllable_id")
            animal_rows.append(animals)
            parts = []
            for metric in FAMILY_METRICS:
                k = kruskal_within_sex(animals, metric=metric).copy()
                k["session"] = "NOR_TX"
                k["trial"] = "nvl_obj"
                k["model"] = cell
                k["grain"] = f"animal × NOR_TX × nvl_obj (per-animal alphabet, M={M})"
                k["family"] = "NGramSeq-peranimal"
                parts.append(k)
            tests = pd.concat(parts, ignore_index=True)
            tests = tests[tests["sex"].isin(FAMILY_SEXES)].reset_index(drop=True)
            tests = apply_bh(tests)
            test_rows.append(tests)
            kmed = animals.groupby("condition")["n_states_used"].median().to_dict()
            notes[cell] = {"M": M, "n": len(animals), "skip": n_skip, "K_med_by_condition": {str(k): float(v) for k, v in kmed.items()}}
            print(f"{cell}: M={M} hits={int(tests['hit_fdr05'].astype(bool).sum())} K_med={kmed}", flush=True)

    animals_all = pd.concat(animal_rows, ignore_index=True)
    tests_all = pd.concat(test_rows, ignore_index=True)
    animals_all.to_csv(out_dir / "ngram_seq_per_animal_models.csv", index=False)
    tests_all.to_csv(out_dir / "ngram_seq_per_animal_tests_long.csv", index=False)
    n_hit = int(tests_all["hit_fdr05"].astype(bool).sum())
    summary = {
        "status": "ok",
        "kind": "exploratory",
        "n_cells": len(cells),
        "n_hit_fdr05": n_hit,
        "cells": notes,
        "elapsed_s": float(time.time() - t0),
    }
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"n_hit_fdr05": n_hit}, indent=2), flush=True)
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--nor-h5", type=Path, default=DEFAULT_NOR_H5)
    ap.add_argument("--per-animal-root", type=Path, default=DEFAULT_PER_ANIMAL)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    run(args.nor_h5, args.per_animal_root, args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
