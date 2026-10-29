"""Q5 BoutGrammar Family A — novel-prox visit grammar on nvl_obj.

NOR H5 only (spot distances + movement_bouts). Kruskal by condition within
sex; BH FDR over the pre-declared 24-cell family.
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

from nor_object_mi.bout_grammar import (  # noqa: E402
    FAMILY_A_SIZE,
    FAMILY_METRICS,
    FAMILY_SESSIONS,
    FAMILY_SEXES,
    GRAIN,
    NEAR_R_M,
    TRIAL,
    assert_family_a_size,
    bout_grammar_from_masks,
    immobile_mask_from_spans,
    near_mask,
)
from nor_object_mi.bout_kinematics import (  # noqa: E402
    immobile_spans_from_movement,
    movement_bout_spans,
    session_fps,
)
from nor_object_mi.fam_nvl import fam_nvl_map_for_session  # noqa: E402
from nor_object_mi.join_keys import filter_cohort, iter_nor_sessions  # noqa: E402
from nor_object_mi.simpler_first_da import apply_bh  # noqa: E402
from nor_object_mi.simpler_first_q1 import kruskal_within_sex  # noqa: E402
from nor_object_mi.spot_xy import role_distances_m  # noqa: E402

DEFAULT_NOR_H5 = Path(r"D:\sack\datas\impress\my_NOR_results.h5")
DEFAULT_OUT = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_bout_grammar"
)


def score_session(
    nor_h5: h5py.File,
    *,
    animal_id: str,
    raw_session: str,
    session: str,
    trial: str,
    sex: str,
    condition: str,
    r_m: float = NEAR_R_M,
) -> dict[str, object] | None:
    if trial != TRIAL:
        return None
    if animal_id not in nor_h5 or raw_session not in nor_h5[animal_id]:
        return None
    sg = nor_h5[animal_id][raw_session]
    role_map = fam_nvl_map_for_session(nor_h5, animal_id, raw_session)
    if not role_map:
        return None
    try:
        _d_fam, d_nvl, valid = role_distances_m(sg, role_map)
        fps = session_fps(sg)
        move = movement_bout_spans(sg, node="spot")
    except (KeyError, ValueError, OSError):
        return None
    n_frames = int(valid.shape[0])
    immobile = immobile_mask_from_spans(
        n_frames,
        immobile_spans_from_movement(move, n_frames),
    )
    near = near_mask(d_nvl, valid, r_m=r_m)
    # Align immobile length if movement spans used a different n
    if immobile.shape[0] != near.shape[0]:
        n = min(immobile.shape[0], near.shape[0])
        immobile = immobile[:n]
        near = near[:n]
    g = bout_grammar_from_masks(near, immobile, fps=fps)
    return {
        "animal_id": str(animal_id),
        "sex": str(sex),
        "condition": str(condition),
        "session": str(session),
        "trial": TRIAL,
        "raw_session": str(raw_session),
        "r_m": float(r_m),
        "fps": float(fps),
        "n_frames": n_frames,
        "n_nvl_entries": float(g["n_nvl_entries"]),
        "mean_nvl_visit_dur_s": float(g["mean_nvl_visit_dur_s"]),
        "median_nvl_visit_dur_s": float(g["median_nvl_visit_dur_s"]),
        "total_nvl_near_s": float(g["total_nvl_near_s"]),
        "frac_still_near_nvl": float(g["frac_still_near_nvl"]),
        "n_near_frames": int(g["n_near_frames"]),
    }


def collect_per_animal(nor_h5: h5py.File, *, r_m: float = NEAR_R_M) -> pd.DataFrame:
    kept = set(filter_cohort(nor_h5)["kept_ids"])
    rows: list[dict[str, object]] = []
    for js in iter_nor_sessions(nor_h5, kept_ids=kept):
        if js.session not in FAMILY_SESSIONS:
            continue
        if js.trial != TRIAL:
            continue
        row = score_session(
            nor_h5,
            animal_id=js.animal_id,
            raw_session=js.raw_session,
            session=js.session,
            trial=js.trial,
            sex=js.sex,
            condition=js.condition,
            r_m=r_m,
        )
        if row is not None:
            rows.append(row)
    return pd.DataFrame(rows)


def build_family_a_tests(animals: pd.DataFrame) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for session in FAMILY_SESSIONS:
        sub = animals[animals["session"] == session]
        if sub.empty:
            continue
        for metric in FAMILY_METRICS:
            k = kruskal_within_sex(sub, metric=metric)
            k = k.copy()
            k["session"] = session
            k["trial"] = TRIAL
            k["r_m"] = float(sub["r_m"].iloc[0]) if "r_m" in sub.columns else NEAR_R_M
            k["grain"] = GRAIN.format(session=session, r=NEAR_R_M)
            k["family"] = "BoutGrammar-A"
            k["question"] = "q5_bout_grammar_condition"
            parts.append(k)
    if not parts:
        return pd.DataFrame()
    tests = pd.concat(parts, ignore_index=True)
    tests = tests[tests["sex"].isin(FAMILY_SEXES)].reset_index(drop=True)
    n_finite = int(pd.to_numeric(tests["p"], errors="coerce").notna().sum())
    assert_family_a_size(n_finite)
    return apply_bh(tests)


def run(nor_h5_path: Path, out_dir: Path, *, r_m: float = NEAR_R_M) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    print(f"Opening {nor_h5_path}", flush=True)
    with h5py.File(nor_h5_path, "r") as nor_h5:
        animals = collect_per_animal(nor_h5, r_m=r_m)
    print(f"Scored {len(animals)} animal×session rows in {time.time() - t0:.1f}s", flush=True)
    animals.to_csv(out_dir / "bout_grammar_per_animal.csv", index=False)

    tests = build_family_a_tests(animals)
    tests.to_csv(out_dir / "bout_grammar_tests_long.csv", index=False)

    n_hit = int(tests["hit_fdr05"].astype(bool).sum()) if not tests.empty else 0
    n_p05 = int(tests["hit_p05"].astype(bool).sum()) if not tests.empty else 0
    summary: dict[str, object] = {
        "status": "ok",
        "family": "BoutGrammar-A",
        "family_size": FAMILY_A_SIZE,
        "r_m": float(r_m),
        "n_animal_session_rows": int(len(animals)),
        "n_animals": int(animals["animal_id"].nunique()) if len(animals) else 0,
        "n_hit_fdr05": n_hit,
        "n_hit_p05": n_p05,
        "pass_family_a": bool(n_hit > 0),
        "metrics": list(FAMILY_METRICS),
        "sessions": list(FAMILY_SESSIONS),
        "sexes": list(FAMILY_SEXES),
        "trial": TRIAL,
        "nor_h5": str(nor_h5_path),
        "hit_rule": "q_bh < 0.05 within BoutGrammar-A (24 Kruskal cells)",
        "design": "level Kruskal by condition within sex (not TX-BL four_mask)",
        "elapsed_s": float(time.time() - t0),
    }
    if n_hit > 0:
        hits = tests.loc[tests["hit_fdr05"].astype(bool)].copy()
        summary["hits"] = hits[
            [
                "session",
                "sex",
                "metric",
                "p",
                "q_bh",
                "n",
                "median_noSD",
                "median_GHSD",
                "median_RBSD",
            ]
        ].to_dict(orient="records")
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
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--r-m", type=float, default=NEAR_R_M)
    args = ap.parse_args(argv)
    if not args.nor_h5.is_file():
        print(f"NOR H5 missing: {args.nor_h5}", file=sys.stderr)
        return 1
    run(args.nor_h5, args.out_dir, r_m=float(args.r_m))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
