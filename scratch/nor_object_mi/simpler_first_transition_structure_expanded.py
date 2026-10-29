"""Family TransStruct-B — bout-transition structure at expanded grains.

Portable cluster alphabet (same pilot model as TransStruct-A). Grains locked
before peeking; single BH family over all cells. Does not re-include
``NOR_TX`` × ``nvl_obj`` (TransStruct-A).

Regenerate (OpenEthoMaze repo root, PowerShell):

  uv run python scratch/nor_object_mi/simpler_first_transition_structure_expanded.py
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
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
from nor_object_mi.simpler_first_transition_structure import (  # noqa: E402
    MODEL,
    bout_cluster_labels,
    load_cluster_map,
)
from nor_object_mi.transition_structure import (  # noqa: E402
    FAMILY_METRICS,
    FAMILY_SEXES,
    FAMILY_B_SIZE,
    LAPLACE_ALPHA,
    MIN_BOUTS,
    TRANSSTRUCT_B_GRAINS,
    TRIAL_ORDER,
    assert_family_b_size,
    conditional_entropy_next_given_current,
    pooled_reference_P,
    score_animals,
    total_variation,
    transition_matrix,
)

DEFAULT_NOR_H5 = Path(r"D:\sack\datas\impress\my_NOR_results.h5")
DEFAULT_KPMS = Path(r"D:\sack\datas\impress\moseq_251017" rf"\{MODEL}\results.h5")
DEFAULT_PROTO = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_syllable_signatures\syllable_prototypes_clustered.csv"
)
DEFAULT_OUT = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_transition_structure_expanded"
)


def _bout_labels_for_js(
    js,
    kpms_h5: h5py.File,
    cluster_map: dict[int, int],
) -> tuple[np.ndarray | None, int]:
    try:
        syll = kpms_h5[js.kpms_key]["syllable"][()]
    except (KeyError, OSError):
        return None, 0
    labs, n_unmapped = bout_cluster_labels(syll, cluster_map)
    return labs, int(n_unmapped)


def collect_grain_sequences(
    nor_h5: h5py.File,
    kpms_h5: h5py.File,
    kept: set[str],
    cluster_map: dict[int, int],
    *,
    session: str,
    trial: str,
    min_bouts: int,
) -> tuple[dict[str, np.ndarray], dict[str, dict[str, str]], int, int]:
    """Return seqs, meta, n_skip_short, n_unmapped_tot for one grain."""
    seqs: dict[str, np.ndarray] = {}
    meta: dict[str, dict[str, str]] = {}
    n_skip_short = 0
    n_unmapped_tot = 0

    if trial == "full_session":
        by_animal: dict[str, dict[str, np.ndarray]] = defaultdict(dict)
        meta_stub: dict[str, dict[str, str]] = {}
        for js in iter_joined_sessions(nor_h5, kpms_h5, kept_ids=kept, session=session):
            labs, n_um = _bout_labels_for_js(js, kpms_h5, cluster_map)
            if labs is None:
                continue
            n_unmapped_tot += n_um
            by_animal[js.animal_id][js.trial] = labs
            meta_stub[js.animal_id] = {"sex": js.sex, "condition": js.condition}
        for aid, trial_map in by_animal.items():
            parts: list[np.ndarray] = []
            for tr in TRIAL_ORDER:
                if tr in trial_map:
                    parts.append(trial_map[tr])
            if not parts:
                continue
            cat = np.concatenate(parts)
            if cat.size < min_bouts:
                n_skip_short += 1
                continue
            seqs[aid] = cat
            meta[aid] = {
                **meta_stub[aid],
                "session": session,
                "trial": trial,
            }
        return seqs, meta, n_skip_short, n_unmapped_tot

    for js in iter_joined_sessions(nor_h5, kpms_h5, kept_ids=kept, session=session):
        if js.trial != trial:
            continue
        labs, n_um = _bout_labels_for_js(js, kpms_h5, cluster_map)
        if labs is None:
            continue
        n_unmapped_tot += n_um
        if labs.size < min_bouts:
            n_skip_short += 1
            continue
        seqs[js.animal_id] = labs
        meta[js.animal_id] = {
            "sex": js.sex,
            "condition": js.condition,
            "session": session,
            "trial": trial,
        }
    return seqs, meta, n_skip_short, n_unmapped_tot


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

    all_animals: list[pd.DataFrame] = []
    grain_stats: list[dict[str, object]] = []
    with h5py.File(nor_h5_path, "r") as nor_h5, h5py.File(kpms_path, "r") as kpms_h5:
        kept = set(filter_cohort(nor_h5)["kept_ids"])
        for session, trial in TRANSSTRUCT_B_GRAINS:
            seqs, meta, n_skip, n_um = collect_grain_sequences(
                nor_h5,
                kpms_h5,
                kept,
                cluster_map,
                session=session,
                trial=trial,
                min_bouts=min_bouts,
            )
            if not seqs:
                print(f"grain {session} x {trial}: 0 animals", flush=True)
                grain_stats.append(
                    {
                        "session": session,
                        "trial": trial,
                        "n_animals": 0,
                        "n_skip_short": n_skip,
                        "n_unmapped_bouts": n_um,
                    }
                )
                continue
            df = score_animals(
                seqs,
                meta,
                states,
                alpha=alpha,
                model=model,
                alphabet="cluster_id",
            )
            df["grain"] = f"animal × {session} × {trial}"
            if trial == "full_session":
                df["grain_note"] = (
                    "concat bouts no_obj→id_obj→nvl_obj; inter-trial boundary is one transition"
                )
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
            print(f"grain {session} x {trial}: {len(df)} animals", flush=True)

    animals = pd.concat(all_animals, ignore_index=True) if all_animals else pd.DataFrame()
    animals.to_csv(out_dir / "transition_structure_expanded_per_animal.csv", index=False)

    parts: list[pd.DataFrame] = []
    for session, trial in TRANSSTRUCT_B_GRAINS:
        sub = animals[(animals["session"] == session) & (animals["trial"] == trial)]
        if sub.empty:
            for metric in FAMILY_METRICS:
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
        for metric in FAMILY_METRICS:
            k = kruskal_within_sex(sub, metric=metric)
            k = k.copy()
            k["session"] = session
            k["trial"] = trial
            k["grain"] = f"animal × {session} × {trial}"
            k["family"] = "TransStruct-B"
            k["question"] = "q5_transition_structure_expanded_grain"
            parts.append(k)
    tests = pd.concat(parts, ignore_index=True)
    tests = tests[tests["sex"].isin(FAMILY_SEXES)].reset_index(drop=True)
    n_finite = int(pd.to_numeric(tests["p"], errors="coerce").notna().sum())
    assert_family_b_size(n_finite)
    tests = apply_bh(tests)
    tests.to_csv(out_dir / "transition_structure_expanded_tests_long.csv", index=False)

    n_hit = int(tests["hit_fdr05"].astype(bool).sum())
    n_p05 = int(tests["hit_p05"].astype(bool).sum())
    summary: dict[str, object] = {
        "status": "ok",
        "family": "TransStruct-B",
        "family_size": FAMILY_B_SIZE,
        "grains": [{"session": s, "trial": t} for s, t in TRANSSTRUCT_B_GRAINS],
        "model": model,
        "alphabet": "cluster_id",
        "n_states": len(states),
        "alpha_laplace": float(alpha),
        "min_bouts": int(min_bouts),
        "n_rows_per_animal": int(len(animals)),
        "grain_stats": grain_stats,
        "n_hit_fdr05": n_hit,
        "n_hit_p05": n_p05,
        "pass_family_b": bool(n_hit > 0),
        "hit_rule": f"q_bh < 0.05 within TransStruct-B ({FAMILY_B_SIZE} Kruskal cells)",
        "elapsed_s": float(time.time() - t0),
    }
    if n_hit > 0:
        hits = tests.loc[tests["hit_fdr05"].astype(bool)].copy()
        summary["hits"] = hits[
            ["sex", "metric", "session", "trial", "p", "q_bh", "median_noSD", "median_GHSD", "median_RBSD"]
        ].to_dict(orient="records")
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                k: summary[k]
                for k in ("n_hit_fdr05", "n_hit_p05", "pass_family_b", "family_size")
            },
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
    run(
        args.nor_h5,
        args.kpms_results,
        args.prototypes_csv,
        args.out_dir,
        model=args.model,
        min_bouts=int(args.min_bouts),
        alpha=float(args.alpha),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
