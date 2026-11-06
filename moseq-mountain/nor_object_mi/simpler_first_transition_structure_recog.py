"""TransStruct questions on recognition-phase fits (moseq_recog_260915).

Pooled recognition-only kpMS (9 models): same 4-cell design at NOR_TX x
nvl_obj with (a) portable cluster_id alphabet (primary analog) and (b) raw
syllable alphabet (exploratory analog). Laplace alpha=1.0, min 20 bouts,
Kruskal by condition within sex, BH within each model x alphabet family.

Status: follow-up readout, not a lock. The locked negative stands on the
full-ladder cluster run ([[Q5 Transition Structure Honesty Pass]]).
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
    MIN_BOUTS,
    score_animals,
)

DEFAULT_NOR_H5 = Path(r"D:\sack\datas\impress\my_NOR_results.h5")
DEFAULT_RECOG = Path(r"D:\sack\datas\impress\moseq_recog_260915\anatomical")
DEFAULT_PROTO = DEFAULT_RECOG / "_nor_object_mi" / "simpler_first_syllable_signatures" / "syllable_prototypes_clustered.csv"
DEFAULT_OUT = Path(r"D:\sack\datas\impress\moseq_recog_260915" r"\anatomical\_nor_object_mi\simpler_first_transition_structure")


def discover_recog_models(root: Path) -> list[tuple[str, Path]]:
    out = []
    for p in sorted(root.glob("paramscan_*")):
        r = p / "results.h5"
        if p.is_dir() and r.is_file():
            out.append((p.name, r))
    return out


def load_cluster_map(proto_csv: Path, *, model: str) -> dict[int, int]:
    proto = pd.read_csv(proto_csv)
    sub = proto[proto["model"] == model]
    if sub.empty:
        raise ValueError(f"no prototype rows for model {model!r}")
    return {int(r["raw_syllable_id"]): int(r["cluster_id"]) for _, r in sub.iterrows()}


def collect_model_seqs(
    nor_h5: h5py.File,
    kpms_h5: h5py.File,
    cluster_map: dict[int, int] | None,
    *,
    min_bouts: int = MIN_BOUTS,
) -> tuple[dict[str, np.ndarray], dict[str, dict[str, str]], list[int], int, int]:
    kept = set(filter_cohort(nor_h5)["kept_ids"])
    seqs: dict[str, np.ndarray] = {}
    meta: dict[str, dict[str, str]] = {}
    n_skip_short = 0
    n_unmapped = 0
    for js in iter_joined_sessions(nor_h5, kpms_h5, kept_ids=kept, session=FAMILY_SESSION):
        if js.trial != FAMILY_TRIAL:
            continue
        try:
            syll = kpms_h5[js.kpms_key]["syllable"][()]
        except (KeyError, OSError):
            continue
        labels, _, _ = rle_labels(np.asarray(syll, dtype=np.int64).ravel())
        labs = labels.tolist()
        if cluster_map is not None:
            mapped = []
            for sid in labs:
                cid = cluster_map.get(int(sid))
                if cid is None:
                    n_unmapped += 1
                else:
                    mapped.append(int(cid))
            labs = mapped
        else:
            labs = [int(x) for x in labs]
        if len(labs) < min_bouts:
            n_skip_short += 1
            continue
        seqs[js.animal_id] = np.asarray(labs, dtype=np.int64)
        meta[js.animal_id] = {
            "sex": js.sex,
            "condition": js.condition,
            "session": js.session,
            "trial": js.trial,
            "model": "",
        }
    states = sorted({int(x) for labs in seqs.values() for x in labs.tolist()})
    return seqs, meta, states, n_skip_short, n_unmapped


def run(nor_h5_path: Path, recog_root: Path, proto_csv: Path, out_dir: Path) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    models = discover_recog_models(recog_root)
    if not models:
        raise ValueError(f"no recog models under {recog_root}")
    animal_frames: dict[str, list[pd.DataFrame]] = {"cluster_id": [], "raw_syllable_id": []}
    test_frames: dict[str, list[pd.DataFrame]] = {"cluster_id": [], "raw_syllable_id": []}
    notes: dict[str, dict[str, int]] = {}
    with h5py.File(nor_h5_path, "r") as nor_h5:
        for model, results in models:
            cmap = load_cluster_map(proto_csv, model=model)
            with h5py.File(results, "r") as kpms_h5:
                seqs_c, meta_c, states_c, skip_c, unmap_c = collect_model_seqs(nor_h5, kpms_h5, cmap)
                seqs_r, meta_r, states_r, skip_r, _ = collect_model_seqs(nor_h5, kpms_h5, None)
            notes[model] = {
                "n_cluster_states": len(states_c),
                "n_raw_states": len(states_r),
                "n_skip_short": int(skip_c + skip_r),
                "n_unmapped": int(unmap_c),
            }
            for alphabet, seqs, meta, states in (
                ("cluster_id", seqs_c, meta_c, states_c),
                ("raw_syllable_id", seqs_r, meta_r, states_r),
            ):
                if not seqs:
                    continue
                animals = score_animals(seqs, meta, states, alpha=LAPLACE_ALPHA, model=model, alphabet=alphabet)
                animal_frames[alphabet].append(animals)
                parts = []
                for metric in FAMILY_METRICS:
                    k = kruskal_within_sex(animals, metric=metric).copy()
                    k["session"] = FAMILY_SESSION
                    k["trial"] = FAMILY_TRIAL
                    k["model"] = model
                    k["alphabet"] = alphabet
                    k["grain"] = GRAIN + (" [recog fit]" if alphabet == "cluster_id" else " [recog fit, raw, exploratory]")
                    k["family"] = "TransStruct-recog" if alphabet == "cluster_id" else "TransStruct-recog-raw"
                    k["question"] = "q5_transition_structure_recog"
                    parts.append(k)
                tests = pd.concat(parts, ignore_index=True)
                tests = tests[tests["sex"].isin(FAMILY_SEXES)].reset_index(drop=True)
                test_frames[alphabet].append(apply_bh(tests))
            print(f"{model}: cluster_states={len(states_c)} raw_states={len(states_r)}", flush=True)

    summary: dict[str, object] = {"status": "ok", "n_models": len(models), "per_model_notes": notes}
    for alphabet, stem in (("cluster_id", "recog_cluster"), ("raw_syllable_id", "recog_raw")):
        animals_all = pd.concat(animal_frames[alphabet], ignore_index=True) if animal_frames[alphabet] else pd.DataFrame()
        tests_all = pd.concat(test_frames[alphabet], ignore_index=True) if test_frames[alphabet] else pd.DataFrame()
        animals_all.to_csv(out_dir / f"transition_structure_{stem}_per_animal.csv", index=False)
        tests_all.to_csv(out_dir / f"transition_structure_{stem}_tests_long.csv", index=False)
        n_hit = int(tests_all["hit_fdr05"].astype(bool).sum()) if not tests_all.empty else 0
        summary[f"{stem}_n_hits"] = n_hit
        summary[f"{stem}_n_rows"] = int(len(tests_all))
        print(f"{stem}: {n_hit} within-model hits / {len(tests_all)} cells", flush=True)
    summary["elapsed_s"] = float(time.time() - t0)
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--nor-h5", type=Path, default=DEFAULT_NOR_H5)
    ap.add_argument("--recog-root", type=Path, default=DEFAULT_RECOG)
    ap.add_argument("--prototypes-csv", type=Path, default=DEFAULT_PROTO)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    for label, p in (("nor-h5", args.nor_h5), ("prototypes-csv", args.prototypes_csv)):
        if not p.is_file():
            print(f"{label} missing: {p}", file=sys.stderr)
            return 1
    run(args.nor_h5, args.recog_root, args.prototypes_csv, args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
