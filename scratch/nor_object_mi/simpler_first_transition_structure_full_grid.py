"""Family TransStruct-C — bout-transition at the complete NOR level grid.

All 4 sessions x 3 trials = 12 grains; 2 metrics x 2 sex = 48 BH cells.
Excludes synthetic ``full_session`` concat (that lives in TransStruct-B only).

  uv run python scratch/nor_object_mi/simpler_first_transition_structure_full_grid.py
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import h5py
import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.join_keys import filter_cohort, iter_joined_sessions  # noqa: E402
from nor_object_mi.simpler_first_da import apply_bh  # noqa: E402
from nor_object_mi.simpler_first_q1 import kruskal_within_sex  # noqa: E402
from nor_object_mi.simpler_first_transition_structure import (  # noqa: E402
    MODEL,
    bout_cluster_labels,
    load_cluster_map,
)
from nor_object_mi.transition_structure import (  # noqa: E402
    FAMILY_C_SIZE,
    FAMILY_METRICS,
    FAMILY_SEXES,
    LAPLACE_ALPHA,
    MIN_BOUTS,
    TRANSSTRUCT_C_GRAINS,
    assert_family_c_size,
    score_animals,
)

DEFAULT_NOR_H5 = Path(r"D:\sack\datas\impress\my_NOR_results.h5")
DEFAULT_KPMS = Path(r"D:\sack\datas\impress\moseq_251017" rf"\{MODEL}\results.h5")
DEFAULT_PROTO = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_syllable_signatures\syllable_prototypes_clustered.csv"
)
DEFAULT_OUT = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_transition_structure_full_grid"
)


def collect_level(
    nor_h5: h5py.File,
    kpms_h5: h5py.File,
    kept: set[str],
    cluster_map: dict[int, int],
    *,
    session: str,
    trial: str,
    min_bouts: int,
) -> tuple[dict[str, object], dict[str, dict[str, str]], int, int]:
    seqs: dict[str, object] = {}
    meta: dict[str, dict[str, str]] = {}
    n_skip = 0
    n_um = 0
    for js in iter_joined_sessions(nor_h5, kpms_h5, kept_ids=kept, session=session):
        if js.trial != trial:
            continue
        try:
            syll = kpms_h5[js.kpms_key]["syllable"][()]
        except (KeyError, OSError):
            continue
        labs, n_u = bout_cluster_labels(syll, cluster_map)
        n_um += int(n_u)
        if labs.size < min_bouts:
            n_skip += 1
            continue
        seqs[js.animal_id] = labs
        meta[js.animal_id] = {
            "sex": js.sex,
            "condition": js.condition,
            "session": session,
            "trial": trial,
        }
    return seqs, meta, n_skip, n_um


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
    print(f"TransStruct-C: {len(TRANSSTRUCT_C_GRAINS)} grains, K={len(states)}", flush=True)

    all_animals: list[pd.DataFrame] = []
    grain_stats: list[dict[str, object]] = []
    with h5py.File(nor_h5_path, "r") as nor_h5, h5py.File(kpms_path, "r") as kpms_h5:
        kept = set(filter_cohort(nor_h5)["kept_ids"])
        for session, trial in TRANSSTRUCT_C_GRAINS:
            seqs, meta, n_skip, n_um = collect_level(
                nor_h5,
                kpms_h5,
                kept,
                cluster_map,
                session=session,
                trial=trial,
                min_bouts=min_bouts,
            )
            if not seqs:
                grain_stats.append(
                    {"session": session, "trial": trial, "n_animals": 0, "n_skip_short": n_skip}
                )
                print(f"  {session} x {trial}: 0", flush=True)
                continue
            df = score_animals(
                seqs, meta, states, alpha=alpha, model=model, alphabet="cluster_id"
            )
            df["grain"] = f"animal × {session} × {trial}"
            all_animals.append(df)
            grain_stats.append(
                {
                    "session": session,
                    "trial": trial,
                    "n_animals": int(len(df)),
                    "n_skip_short": n_skip,
                    "n_unmapped_bouts": n_um,
                }
            )
            print(f"  {session} x {trial}: {len(df)}", flush=True)

    animals = pd.concat(all_animals, ignore_index=True) if all_animals else pd.DataFrame()
    animals.to_csv(out_dir / "transition_structure_full_grid_per_animal.csv", index=False)

    parts: list[pd.DataFrame] = []
    for session, trial in TRANSSTRUCT_C_GRAINS:
        sub = animals[(animals["session"] == session) & (animals["trial"] == trial)]
        for metric in FAMILY_METRICS:
            if sub.empty:
                for sex in FAMILY_SEXES:
                    parts.append(
                        pd.DataFrame(
                            [
                                {
                                    "sex": sex,
                                    "metric": metric,
                                    "session": session,
                                    "trial": trial,
                                    "p": float("nan"),
                                    "test": "kruskal",
                                }
                            ]
                        )
                    )
                continue
            k = kruskal_within_sex(sub, metric=metric).copy()
            k["session"] = session
            k["trial"] = trial
            k["grain"] = f"animal × {session} × {trial}"
            k["family"] = "TransStruct-C"
            k["question"] = "q5_transition_structure_full_level_grid"
            parts.append(k)
    tests = pd.concat(parts, ignore_index=True)
    tests = tests[tests["sex"].isin(FAMILY_SEXES)].reset_index(drop=True)
    n_finite = int(pd.to_numeric(tests["p"], errors="coerce").notna().sum())
    assert_family_c_size(n_finite)
    tests = apply_bh(tests)
    tests.to_csv(out_dir / "transition_structure_full_grid_tests_long.csv", index=False)

    n_hit = int(tests["hit_fdr05"].astype(bool).sum())
    n_p05 = int(tests["hit_p05"].astype(bool).sum())
    summary: dict[str, object] = {
        "status": "ok",
        "family": "TransStruct-C",
        "family_size": FAMILY_C_SIZE,
        "n_grains": len(TRANSSTRUCT_C_GRAINS),
        "grains": [{"session": s, "trial": t} for s, t in TRANSSTRUCT_C_GRAINS],
        "grain_stats": grain_stats,
        "model": model,
        "alphabet": "cluster_id",
        "n_hit_fdr05": n_hit,
        "n_hit_p05": n_p05,
        "pass_family_c": bool(n_hit > 0),
        "hit_rule": f"q_bh < 0.05 within TransStruct-C ({FAMILY_C_SIZE} cells)",
        "elapsed_s": float(time.time() - t0),
    }
    if n_hit > 0:
        hits = tests.loc[tests["hit_fdr05"].astype(bool)].copy()
        summary["hits"] = hits[
            ["sex", "metric", "session", "trial", "p", "q_bh", "median_noSD", "median_GHSD", "median_RBSD"]
        ].to_dict(orient="records")
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("n_hit_fdr05", "n_hit_p05", "pass_family_c", "family_size")}, indent=2), flush=True)
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
