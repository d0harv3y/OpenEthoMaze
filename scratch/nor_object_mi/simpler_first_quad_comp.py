"""QuadComp Family A — quadrant-stratified syllable composition on nvl_obj.

Portable cluster_id on locked pilot model. Object-assigned arena quadrants
(fam_quad / nvl_quad / other). Litmus T1-assay: Wilcoxon vs 0 in noSD @ NOR_TX.
Family A: Kruskal by condition within sex on dr_shannon_quad /
dr_richness_quad (m=4). N=10 exclusive eligibility on both object quads.
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

from nor_object_mi.fam_nvl import fam_nvl_map_for_session  # noqa: E402
from nor_object_mi.join_keys import filter_cohort, iter_joined_sessions  # noqa: E402
from nor_object_mi.quad_comp import (  # noqa: E402
    FAMILY_A_SIZE,
    FAMILY_METRICS,
    FAMILY_SESSIONS_PANEL,
    FAMILY_SEXES,
    GRAIN,
    LEVEL_FAMILY_A_SIZE,
    LEVEL_FAMILY_METRICS,
    LITMUS_T1_ASSAY_CONDITION,
    LITMUS_T1_ASSAY_SESSION,
    MIN_FRAMES_N,
    NOISE_CLUSTER,
    TIME_FAMILY_A_SIZE,
    TIME_FAMILY_METRICS,
    TRIAL,
    assert_family_a_size,
    assert_level_family_a_size,
    assert_time_family_a_size,
    score_quad_composition,
)
from nor_object_mi.simpler_first_da import apply_bh  # noqa: E402
from nor_object_mi.simpler_first_presence import wilcoxon_paired  # noqa: E402
from nor_object_mi.simpler_first_q1 import kruskal_within_sex  # noqa: E402
from nor_object_mi.spot_xy import object_centers_px, spot_xy_px  # noqa: E402
from nor_object_mi.syllable_spatial_heatmap import (  # noqa: E402
    arena_center_px,
    needs_novel_alignment,
    nvl_nearest_hist_locus,
)

MODEL = "paramscan_s1-1e8_s2-1e5_ss-50"
DEFAULT_NOR_H5 = Path(r"D:\sack\datas\impress\my_NOR_results.h5")
DEFAULT_KPMS = Path(r"D:\sack\datas\impress\moseq_251017" rf"\{MODEL}\results.h5")
DEFAULT_PROTO = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_syllable_signatures\syllable_prototypes_clustered.csv"
)
DEFAULT_OUT = Path(
    r"D:\sack\datas\impress\moseq_251017" r"\_nor_object_mi\simpler_first_quad_comp"
)


def _load_cluster_map(proto_csv: Path, model: str) -> dict[int, int]:
    proto = pd.read_csv(proto_csv)
    sub = proto[proto["model"] == model]
    if sub.empty:
        raise ValueError(f"no prototype rows for {model}")
    return {int(r["raw_syllable_id"]): int(r["cluster_id"]) for _, r in sub.iterrows()}


def _map_syllables(raw: np.ndarray, cmap: dict[int, int]) -> tuple[np.ndarray, int]:
    out = np.full(raw.shape, NOISE_CLUSTER, dtype=np.int64)
    n_unmapped = 0
    for i, sid in enumerate(np.asarray(raw, dtype=np.int64).ravel()):
        cid = cmap.get(int(sid))
        if cid is None or int(cid) < 0:
            n_unmapped += 1
        else:
            out[i] = int(cid)
    return out, n_unmapped


def score_joined(
    nor_h5: h5py.File,
    kpms_h5: h5py.File,
    *,
    js,
    cmap: dict[int, int],
    min_frames: int,
) -> dict[str, object] | None:
    if js.trial != TRIAL:
        return None
    if js.session not in FAMILY_SESSIONS_PANEL:
        return None
    if js.animal_id not in nor_h5 or js.raw_session not in nor_h5[js.animal_id]:
        return None
    if js.kpms_key not in kpms_h5:
        return None
    sg = nor_h5[js.animal_id][js.raw_session]
    role_map = fam_nvl_map_for_session(nor_h5, js.animal_id, js.raw_session)
    if not role_map:
        return None
    fam_key = next((k for k, v in role_map.items() if v == "fam"), None)
    nvl_key = next((k for k, v in role_map.items() if v == "nvl"), None)
    if fam_key is None or nvl_key is None:
        return None
    centers = object_centers_px(sg)
    if fam_key not in centers or nvl_key not in centers:
        return None
    try:
        x_px, y_px, valid = spot_xy_px(sg["sleap_data"])
        cx, cy = arena_center_px(sg)
        syll_raw = np.asarray(kpms_h5[js.kpms_key]["syllable"][()], dtype=np.int64).ravel()
    except (KeyError, ValueError, OSError):
        return None
    n = min(len(valid), len(syll_raw), len(x_px), len(y_px))
    if n < 1:
        return None
    syll_c, n_unmapped = _map_syllables(syll_raw[:n], cmap)
    nvl_side = nvl_nearest_hist_locus(
        nor_h5,
        animal_id=js.animal_id,
        session=js.session,
        raw_session=js.raw_session,
        trial=js.trial,
    )
    rotate = needs_novel_alignment(nvl_side)
    scored = score_quad_composition(
        x_px[:n],
        y_px[:n],
        valid[:n],
        syll_c,
        cx=cx,
        cy=cy,
        fam_center_px=centers[fam_key],
        nvl_center_px=centers[nvl_key],
        rotate_180=rotate,
        min_frames=min_frames,
    )
    return {
        "animal_id": str(js.animal_id),
        "sex": str(js.sex),
        "condition": str(js.condition),
        "session": str(js.session),
        "trial": TRIAL,
        "raw_session": str(js.raw_session),
        "model": MODEL,
        "alphabet": "cluster_id",
        "nvl_side": nvl_side,
        "n_unmapped_frames": int(n_unmapped),
        "cx_px": float(cx),
        "cy_px": float(cy),
        **scored,
    }


def collect_per_animal(
    nor_h5: h5py.File,
    kpms_h5: h5py.File,
    *,
    cmap: dict[int, int],
    min_frames: int,
) -> pd.DataFrame:
    kept = set(filter_cohort(nor_h5)["kept_ids"])
    rows: list[dict[str, object]] = []
    for js in iter_joined_sessions(nor_h5, kpms_h5, kept_ids=kept, session=None):
        row = score_joined(
            nor_h5, kpms_h5, js=js, cmap=cmap, min_frames=min_frames
        )
        if row is not None:
            rows.append(row)
    return pd.DataFrame(rows)


def build_litmus_t1_assay(animals: pd.DataFrame) -> pd.DataFrame:
    """Wilcoxon vs 0 on DR cousins + time twin in noSD @ NOR_TX."""
    rows: list[dict[str, object]] = []
    strata = list(FAMILY_SEXES) + ["all"]
    specs = [
        (FAMILY_METRICS, "contrast_eligible", "QuadComp-litmus-T1-assay", "q4_quad_comp_assay"),
        (TIME_FAMILY_METRICS, "time_contrast_eligible", "TimeQuad-litmus-T1-assay", "q4_time_quad_assay"),
    ]
    for metrics, elig_col, family, question in specs:
        sub = animals[
            (animals["session"] == LITMUS_T1_ASSAY_SESSION)
            & (animals["condition"] == LITMUS_T1_ASSAY_CONDITION)
            & (animals[elig_col].astype(bool))
        ].copy()
        for metric in metrics:
            for sex in strata:
                chunk = sub if sex == "all" else sub[sub["sex"] == sex]
                vals = pd.to_numeric(chunk[metric], errors="coerce").to_numpy(dtype=np.float64)
                rec = wilcoxon_paired(vals)
                rows.append(
                    {
                        "session": LITMUS_T1_ASSAY_SESSION,
                        "trial": TRIAL,
                        "condition": LITMUS_T1_ASSAY_CONDITION,
                        "sex": sex,
                        "metric": metric,
                        "litmus": "T1_assay_validity",
                        "family": family,
                        "question": question,
                        "grain": GRAIN.format(session=LITMUS_T1_ASSAY_SESSION),
                        **rec,
                        "hit_p05": bool(
                            np.isfinite(rec["p"]) and float(rec["p"]) < 0.05
                        ),
                    }
                )
    return pd.DataFrame(rows)


def build_family_a_tests(animals: pd.DataFrame) -> pd.DataFrame:
    """Kruskal × QuadComp-A (NOR_TX only); BH over 4 cells."""
    sub = animals[
        (animals["session"] == LITMUS_T1_ASSAY_SESSION)
        & (animals["contrast_eligible"].astype(bool))
    ].copy()
    parts: list[pd.DataFrame] = []
    for metric in FAMILY_METRICS:
        k = kruskal_within_sex(sub, metric=metric).copy()
        k["session"] = LITMUS_T1_ASSAY_SESSION
        k["trial"] = TRIAL
        k["grain"] = GRAIN.format(session=LITMUS_T1_ASSAY_SESSION)
        k["family"] = "QuadComp-A"
        k["question"] = "q5_quad_comp_condition"
        k["litmus"] = "B_condition"
        parts.append(k)
    tests = pd.concat(parts, ignore_index=True)
    tests = tests[tests["sex"].isin(FAMILY_SEXES)].reset_index(drop=True)
    assert_family_a_size(int(pd.to_numeric(tests["p"], errors="coerce").notna().sum()))
    return apply_bh(tests)


def build_time_family_a_tests(animals: pd.DataFrame) -> pd.DataFrame:
    """Kruskal × TimeQuad-A (dr_time_quad only); BH over 2 cells."""
    sub = animals[
        (animals["session"] == LITMUS_T1_ASSAY_SESSION)
        & (animals["time_contrast_eligible"].astype(bool))
    ].copy()
    parts: list[pd.DataFrame] = []
    for metric in TIME_FAMILY_METRICS:
        k = kruskal_within_sex(sub, metric=metric).copy()
        k["session"] = LITMUS_T1_ASSAY_SESSION
        k["trial"] = TRIAL
        k["grain"] = GRAIN.format(session=LITMUS_T1_ASSAY_SESSION)
        k["family"] = "TimeQuad-A"
        k["question"] = "q5_time_quad_condition"
        k["litmus"] = "B_condition"
        parts.append(k)
    tests = pd.concat(parts, ignore_index=True)
    tests = tests[tests["sex"].isin(FAMILY_SEXES)].reset_index(drop=True)
    assert_time_family_a_size(int(pd.to_numeric(tests["p"], errors="coerce").notna().sum()))
    return apply_bh(tests)


def build_level_family_a_tests(animals: pd.DataFrame) -> pd.DataFrame:
    """Kruskal × QuadLevel-A (fam/nvl shannon+richness); BH over 8 cells.

    Declared after user request 2026-10-06 (constituents were panel-only under
    original QuadComp-A). Confirmatory vs prior uncorrected peek.
    """
    sub = animals[
        (animals["session"] == LITMUS_T1_ASSAY_SESSION)
        & (animals["contrast_eligible"].astype(bool))
    ].copy()
    parts: list[pd.DataFrame] = []
    for metric in LEVEL_FAMILY_METRICS:
        k = kruskal_within_sex(sub, metric=metric).copy()
        k["session"] = LITMUS_T1_ASSAY_SESSION
        k["trial"] = TRIAL
        k["grain"] = GRAIN.format(session=LITMUS_T1_ASSAY_SESSION)
        k["family"] = "QuadLevel-A"
        k["question"] = "q5_quad_level_condition"
        k["litmus"] = "B_condition"
        parts.append(k)
    tests = pd.concat(parts, ignore_index=True)
    tests = tests[tests["sex"].isin(FAMILY_SEXES)].reset_index(drop=True)
    assert_level_family_a_size(int(pd.to_numeric(tests["p"], errors="coerce").notna().sum()))
    return apply_bh(tests)


def build_eligibility_summary(animals: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for session in FAMILY_SESSIONS_PANEL:
        for sex in FAMILY_SEXES:
            for condition in ("noSD", "GHSD", "RBSD"):
                g = animals[
                    (animals["session"] == session)
                    & (animals["sex"] == sex)
                    & (animals["condition"] == condition)
                ]
                n = int(len(g))
                n_ok = int(g["contrast_eligible"].astype(bool).sum()) if n else 0
                n_coll = int(g["object_cell_collision"].astype(bool).sum()) if n else 0
                rows.append(
                    {
                        "session": session,
                        "sex": sex,
                        "condition": condition,
                        "n_rows": n,
                        "n_eligible": n_ok,
                        "n_collision": n_coll,
                        "frac_eligible": float(n_ok / n) if n else float("nan"),
                    }
                )
    return pd.DataFrame(rows)


def run(
    nor_h5_path: Path,
    kpms_path: Path,
    proto_csv: Path,
    out_dir: Path,
    *,
    min_frames: int = MIN_FRAMES_N,
) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    cmap = _load_cluster_map(proto_csv, MODEL)
    with h5py.File(nor_h5_path, "r") as nor_h5, h5py.File(kpms_path, "r") as kpms_h5:
        animals = collect_per_animal(
            nor_h5, kpms_h5, cmap=cmap, min_frames=min_frames
        )
    print(f"Scored {len(animals)} animal×session rows", flush=True)
    animals.to_csv(out_dir / "quad_comp_per_animal.csv", index=False)

    elig = build_eligibility_summary(animals)
    elig.to_csv(out_dir / "quad_comp_eligibility.csv", index=False)

    litmus_t1_assay = build_litmus_t1_assay(animals)
    litmus_t1_assay.to_csv(out_dir / "quad_comp_litmus_t1_assay.csv", index=False)
    # Legacy filename for Run notes / prior artifacts
    litmus_t1_assay.to_csv(out_dir / "quad_comp_litmus_a.csv", index=False)

    tests = build_family_a_tests(animals)
    tests.to_csv(out_dir / "quad_comp_tests_long.csv", index=False)

    time_tests = build_time_family_a_tests(animals)
    time_tests.to_csv(out_dir / "time_quad_tests_long.csv", index=False)

    level_tests = build_level_family_a_tests(animals)
    level_tests.to_csv(out_dir / "quad_level_tests_long.csv", index=False)

    n_hit = int(tests["hit_fdr05"].astype(bool).sum()) if not tests.empty else 0
    n_p05 = int(tests["hit_p05"].astype(bool).sum()) if not tests.empty else 0
    t_hit = int(time_tests["hit_fdr05"].astype(bool).sum()) if not time_tests.empty else 0
    t_p05 = int(time_tests["hit_p05"].astype(bool).sum()) if not time_tests.empty else 0
    l_hit = int(level_tests["hit_fdr05"].astype(bool).sum()) if not level_tests.empty else 0
    l_p05 = int(level_tests["hit_p05"].astype(bool).sum()) if not level_tests.empty else 0
    a_hits = (
        int(litmus_t1_assay["hit_p05"].astype(bool).sum()) if not litmus_t1_assay.empty else 0
    )
    a_primary = litmus_t1_assay[
        (litmus_t1_assay["sex"] == "all") & (litmus_t1_assay["metric"].isin(FAMILY_METRICS))
    ]
    a_pass = bool(
        a_primary["hit_p05"].astype(bool).any()
        and (pd.to_numeric(a_primary["median_delta"], errors="coerce") > 0).any()
    )
    a_time = litmus_t1_assay[
        (litmus_t1_assay["sex"] == "all") & (litmus_t1_assay["metric"] == "dr_time_quad")
    ]
    a_time_pass = bool(
        (not a_time.empty)
        and bool(a_time["hit_p05"].astype(bool).any())
        and (pd.to_numeric(a_time["median_delta"], errors="coerce") > 0).any()
    )

    summary: dict[str, object] = {
        "status": "ok",
        "family": "QuadComp-A",
        "family_size": FAMILY_A_SIZE,
        "time_family": "TimeQuad-A",
        "time_family_size": TIME_FAMILY_A_SIZE,
        "level_family": "QuadLevel-A",
        "level_family_size": LEVEL_FAMILY_A_SIZE,
        "model": MODEL,
        "alphabet": "cluster_id",
        "min_frames_n": int(min_frames),
        "n_animal_session_rows": int(len(animals)),
        "n_animals_tx_eligible": int(
            animals[
                (animals["session"] == LITMUS_T1_ASSAY_SESSION)
                & (animals["contrast_eligible"].astype(bool))
            ]["animal_id"].nunique()
        ),
        "n_animals_tx_time_eligible": int(
            animals[
                (animals["session"] == LITMUS_T1_ASSAY_SESSION)
                & (animals["time_contrast_eligible"].astype(bool))
            ]["animal_id"].nunique()
        ),
        "litmus_t1_assay_pass": a_pass,
        "litmus_t1_assay_time_pass": a_time_pass,
        "litmus_t1_assay_n_hit_p05": a_hits,
        # Legacy keys (pre theory-indexed rename)
        "litmus_a_pass": a_pass,
        "litmus_a_time_pass": a_time_pass,
        "litmus_a_n_hit_p05": a_hits,
        "n_hit_fdr05": n_hit,
        "n_hit_p05": n_p05,
        "pass_family_a": bool(n_hit > 0),
        "time_n_hit_fdr05": t_hit,
        "time_n_hit_p05": t_p05,
        "pass_time_family_a": bool(t_hit > 0),
        "level_n_hit_fdr05": l_hit,
        "level_n_hit_p05": l_p05,
        "pass_level_family_a": bool(l_hit > 0),
        "hit_rule": (
            "q_bh < 0.05 within QuadComp-A (4), TimeQuad-A (2), or QuadLevel-A (8) @ NOR_TX"
        ),
        "elapsed_s": float(time.time() - t0),
    }
    if n_hit:
        hits = tests.loc[tests["hit_fdr05"].astype(bool)].copy()
        summary["hits"] = hits[
            [
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
    (out_dir / "run_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2), flush=True)
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--nor-h5", type=Path, default=DEFAULT_NOR_H5)
    ap.add_argument("--kpms-h5", type=Path, default=DEFAULT_KPMS)
    ap.add_argument("--proto-csv", type=Path, default=DEFAULT_PROTO)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--min-frames", type=int, default=MIN_FRAMES_N)
    args = ap.parse_args()
    run(
        args.nor_h5,
        args.kpms_h5,
        args.proto_csv,
        args.out_dir,
        min_frames=args.min_frames,
    )


if __name__ == "__main__":
    main()
