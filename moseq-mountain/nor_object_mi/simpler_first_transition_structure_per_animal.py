"""TransStruct questions on per-animal fits (nor_per_animal_paramscan).

Each animal x hyperparameter cell has its OWN syllable alphabet, so
cross-animal transition matrices are incommensurable: TV distance to a pooled
reference is UNDEFINED here (never computed). Askable per animal x cell:

- H_next_given_curr (bits) — comparable across animals up to alphabet size;
- H_norm = H / log2(K_used) (efficiency) — size-adjusted companion;
- n_states_used / n_bouts — descriptive QC (not in family).

Design: NOR_TX x nvl_obj (NOR2 NVL OBJ), Laplace alpha=1.0, min 20 bouts,
Kruskal H / H_norm by condition within sex, BH within each hyperparameter
cell (2 metrics x F/M = 4 cells). 9 cells total. Exploratory, not a lock.
"""

from __future__ import annotations

import argparse
import glob
import json
import re
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
from nor_object_mi.simpler_first_da import apply_bh  # noqa: E402
from nor_object_mi.simpler_first_q1 import kruskal_within_sex  # noqa: E402
from nor_object_mi.syllable_cleanup import rle_labels  # noqa: E402
from nor_object_mi.transition_structure import (  # noqa: E402
    FAMILY_SEXES,
    LAPLACE_ALPHA,
    MIN_BOUTS,
    conditional_entropy_next_given_current,
    count_transitions,
    row_stochastic_with_laplace,
)

_CELL_RE = re.compile(r"(paramscan_.*)")

DEFAULT_NOR_H5 = Path(r"D:\sack\datas\impress\my_NOR_results.h5")
DEFAULT_PER_ANIMAL = Path(r"D:\sack\datas\impress\nor_per_animal_paramscan")
DEFAULT_OUT = Path(r"D:\sack\datas\impress\nor_per_animal_paramscan" r"\_nor_object_mi\simpler_first_transition_structure")

METRICS: tuple[str, ...] = ("H_next_given_curr", "H_norm")


def cell_of(results_h5: str) -> str:
    name = Path(results_h5).parent.name
    m = _CELL_RE.search(name)
    if not m:
        raise ValueError(f"cannot parse cell from {name!r}")
    tail = m.group(1)
    return tail[tail.index("paramscan_") :]


def entropy_of_labels(labs: np.ndarray, *, alpha: float = LAPLACE_ALPHA) -> tuple[float, float, int]:
    states = sorted(int(x) for x in np.unique(labs))
    C = count_transitions(labs, states)
    P = row_stochastic_with_laplace(C, alpha=alpha)
    H = conditional_entropy_next_given_current(P, C)
    K = len(states)
    Hn = float(H / np.log2(K)) if K > 1 and np.isfinite(H) else float("nan")
    return float(H), float(Hn), int(K)


def run(nor_h5_path: Path, per_animal_root: Path, out_dir: Path) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    results_list = sorted(glob.glob(str(per_animal_root / "exp*" / "*" / "anatomical" / "*_paramscan_*" / "results.h5")))
    if not results_list:
        raise ValueError(f"no per-animal fits under {per_animal_root}")
    cells: dict[str, list[str]] = {}
    for fp in results_list:
        cells.setdefault(cell_of(fp), []).append(fp)
    print(f"{len(results_list)} fits in {len(cells)} cells", flush=True)

    animal_rows: list[pd.DataFrame] = []
    test_rows: list[pd.DataFrame] = []
    with h5py.File(nor_h5_path, "r") as nor_h5:
        for cell in sorted(cells):
            rows: list[dict[str, object]] = []
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
                    sess = str(sg.attrs.get("session", "") or sg.attrs.get("phase_layer", "") or "")
                    if sess != "NOR_TX":
                        n_skip += 1
                        continue
                    z = kf[key]["syllable"][()]
                    labs, _, _ = rle_labels(np.asarray(z, dtype=np.int64).ravel())
                    if len(labs) < MIN_BOUTS:
                        n_skip += 1
                        continue
                    H, Hn, K = entropy_of_labels(labs)
                    rows.append(
                        {
                            "animal_id": aid,
                            "sex": str(ag.attrs.get("sex", "") or ""),
                            "condition": str(ag.attrs.get("condition", "") or ag.attrs.get("tx", "") or ""),
                            "session": "NOR_TX",
                            "trial": "nvl_obj",
                            "model": cell,
                            "alphabet": "per_animal_raw_syllable_id",
                            "n_states_used": K,
                            "n_bouts": int(len(labs)),
                            "n_transitions": int(len(labs) - 1),
                            "H_next_given_curr": H,
                            "H_norm": Hn,
                        }
                    )
            animals = pd.DataFrame(rows)
            if animals.empty:
                print(f"{cell}: EMPTY (skip={n_skip})", flush=True)
                continue
            animal_rows.append(animals)
            parts = []
            for metric in METRICS:
                k = kruskal_within_sex(animals, metric=metric).copy()
                k["session"] = "NOR_TX"
                k["trial"] = "nvl_obj"
                k["model"] = cell
                k["alphabet"] = "per_animal_raw_syllable_id"
                k["grain"] = "animal × NOR_TX × nvl_obj (per-animal alphabet; TV undefined)"
                k["family"] = "TransStruct-peranimal"
                k["question"] = "q5_transition_structure_per_animal_exploratory"
                parts.append(k)
            tests = pd.concat(parts, ignore_index=True)
            tests = tests[tests["sex"].isin(FAMILY_SEXES)].reset_index(drop=True)
            tests = apply_bh(tests)
            test_rows.append(tests)
            n_hit = int(tests["hit_fdr05"].astype(bool).sum())
            print(f"{cell}: n={len(animals)} K_med={float(animals['n_states_used'].median()):.0f} hits={n_hit} skip={n_skip}", flush=True)

    animals_all = pd.concat(animal_rows, ignore_index=True) if animal_rows else pd.DataFrame()
    tests_all = pd.concat(test_rows, ignore_index=True) if test_rows else pd.DataFrame()
    animals_all.to_csv(out_dir / "transition_structure_per_animal_models.csv", index=False)
    tests_all.to_csv(out_dir / "transition_structure_per_animal_tests_long.csv", index=False)
    n_hit = int(tests_all["hit_fdr05"].astype(bool).sum()) if not tests_all.empty else 0
    hits = tests_all.loc[tests_all["hit_fdr05"].astype(bool)].copy() if n_hit else pd.DataFrame()
    summary: dict[str, object] = {
        "status": "ok",
        "family": "TransStruct-peranimal",
        "kind": "exploratory",
        "n_cells": len(cells),
        "n_fits": len(results_list),
        "n_animal_cell_rows": int(len(animals_all)),
        "n_test_rows": int(len(tests_all)),
        "n_hit_fdr05": n_hit,
        "tv_note": "TV distance undefined for per-animal alphabets; never computed",
        "hit_rule": "q_bh < 0.05 within each hyperparameter cell (4 Kruskal cells)",
        "elapsed_s": float(time.time() - t0),
    }
    if n_hit:
        summary["hits"] = hits[["model", "sex", "metric", "p", "q_bh", "n", "median_noSD", "median_GHSD", "median_RBSD"]].to_dict(orient="records")
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"n_hit_fdr05": n_hit, "n_cells": len(cells)}, indent=2), flush=True)
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--nor-h5", type=Path, default=DEFAULT_NOR_H5)
    ap.add_argument("--per-animal-root", type=Path, default=DEFAULT_PER_ANIMAL)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    if not args.nor_h5.is_file():
        print(f"nor-h5 missing: {args.nor_h5}", file=sys.stderr)
        return 1
    run(args.nor_h5, args.per_animal_root, args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
