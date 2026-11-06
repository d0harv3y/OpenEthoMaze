"""Q5 SideMass Family A — per-animal nvl-side geometry on nvl_obj.

Reads NOR H5 spot xy (no kpMS). Aligns fam-left via rot180 when needed,
scores frac_nvl_side + mean_signed_x_m, Kruskal by condition within sex,
BH FDR over the pre-declared 16-cell family.
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

from nor_object_mi.join_keys import filter_cohort, iter_nor_sessions  # noqa: E402
from nor_object_mi.side_mass import (  # noqa: E402
    FAMILY_A_SIZE,
    FAMILY_METRICS,
    FAMILY_SESSIONS,
    FAMILY_SEXES,
    GRAIN,
    TRIAL,
    assert_family_a_size,
    side_mass_from_xy,
)
from nor_object_mi.simpler_first_da import apply_bh  # noqa: E402
from nor_object_mi.simpler_first_q1 import kruskal_within_sex  # noqa: E402
from nor_object_mi.spot_xy import pixels_per_meter, spot_xy_px  # noqa: E402
from nor_object_mi.syllable_spatial_heatmap import (  # noqa: E402
    arena_center_px,
    needs_novel_alignment,
    nvl_nearest_hist_locus,
)

DEFAULT_NOR_H5 = Path(r"D:\sack\datas\impress\my_NOR_results.h5")
DEFAULT_OUT = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_side_mass"
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
) -> dict[str, object] | None:
    if trial != TRIAL:
        return None
    if animal_id not in nor_h5 or raw_session not in nor_h5[animal_id]:
        return None
    sg = nor_h5[animal_id][raw_session]
    if "sleap_data" not in sg:
        return None
    try:
        x_px, y_px, valid = spot_xy_px(sg["sleap_data"])
        cx, cy = arena_center_px(sg)
        ppm = pixels_per_meter(sg)
    except (KeyError, ValueError, OSError):
        return None
    nvl_side = nvl_nearest_hist_locus(
        nor_h5,
        animal_id=animal_id,
        session=session,
        raw_session=raw_session,
        trial=trial,
    )
    rotate = needs_novel_alignment(nvl_side)
    mass = side_mass_from_xy(
        x_px,
        y_px,
        valid,
        cx=cx,
        cy=cy,
        ppm=ppm,
        rotate_180=rotate,
    )
    if not np.isfinite(mass["frac_nvl_side"]):
        return None
    return {
        "animal_id": str(animal_id),
        "sex": str(sex),
        "condition": str(condition),
        "session": str(session),
        "trial": TRIAL,
        "raw_session": str(raw_session),
        "nvl_side": nvl_side,
        "rotate_180": bool(rotate),
        "n_valid": int(mass["n_valid"]),
        "frac_nvl_side": float(mass["frac_nvl_side"]),
        "frac_fam_side": float(mass["frac_fam_side"]),
        "mean_signed_x_m": float(mass["mean_signed_x_m"]),
        "ppm": float(ppm),
        "cx_px": float(cx),
        "cy_px": float(cy),
    }


def collect_per_animal(nor_h5: h5py.File) -> pd.DataFrame:
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
        )
        if row is not None:
            rows.append(row)
    return pd.DataFrame(rows)


def build_family_a_tests(animals: pd.DataFrame) -> pd.DataFrame:
    """Kruskal × Family A cells; BH over the full 16-row table."""
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
            k["grain"] = GRAIN.format(session=session)
            k["family"] = "SideMass-A"
            k["question"] = "q5_side_mass_condition"
            parts.append(k)
    if not parts:
        return pd.DataFrame()
    tests = pd.concat(parts, ignore_index=True)
    # Keep only declared sexes (kruskal_within_sex already emits F/M).
    tests = tests[tests["sex"].isin(FAMILY_SEXES)].reset_index(drop=True)
    n_finite = int(pd.to_numeric(tests["p"], errors="coerce").notna().sum())
    assert_family_a_size(n_finite)
    return apply_bh(tests)


def run(nor_h5_path: Path, out_dir: Path) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    print(f"Opening {nor_h5_path}", flush=True)
    with h5py.File(nor_h5_path, "r") as nor_h5:
        animals = collect_per_animal(nor_h5)
    print(f"Scored {len(animals)} animal×session rows in {time.time() - t0:.1f}s", flush=True)
    animals_path = out_dir / "side_mass_per_animal.csv"
    animals.to_csv(animals_path, index=False)

    tests = build_family_a_tests(animals)
    tests_path = out_dir / "side_mass_tests_long.csv"
    tests.to_csv(tests_path, index=False)

    n_hit = int(tests["hit_fdr05"].astype(bool).sum()) if not tests.empty else 0
    n_p05 = int(tests["hit_p05"].astype(bool).sum()) if not tests.empty else 0
    summary: dict[str, object] = {
        "status": "ok",
        "family": "SideMass-A",
        "family_size": FAMILY_A_SIZE,
        "n_animal_session_rows": int(len(animals)),
        "n_animals": int(animals["animal_id"].nunique()) if len(animals) else 0,
        "n_rotate_180": int(animals["rotate_180"].astype(bool).sum()) if len(animals) else 0,
        "n_hit_fdr05": n_hit,
        "n_hit_p05": n_p05,
        "pass_family_a": bool(n_hit > 0),
        "metrics": list(FAMILY_METRICS),
        "sessions": list(FAMILY_SESSIONS),
        "sexes": list(FAMILY_SEXES),
        "trial": TRIAL,
        "nor_h5": str(nor_h5_path),
        "alignment": "fam_left_via_rot180",
        "hit_rule": "q_bh < 0.05 within SideMass-A (16 Kruskal cells)",
        "elapsed_s": float(time.time() - t0),
    }
    if n_hit > 0:
        hits = tests.loc[tests["hit_fdr05"].astype(bool)].copy()
        summary["hits"] = hits[
            ["session", "sex", "metric", "p", "q_bh", "n", "median_noSD", "median_GHSD", "median_RBSD"]
        ].to_dict(orient="records")
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("n_hit_fdr05", "n_hit_p05", "pass_family_a")}, indent=2), flush=True)
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--nor-h5", type=Path, default=DEFAULT_NOR_H5)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    if not args.nor_h5.is_file():
        print(f"NOR H5 missing: {args.nor_h5}", file=sys.stderr)
        return 1
    run(args.nor_h5, args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
