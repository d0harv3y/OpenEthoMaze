"""ProxComp — exclusive 0.10 m prox syllable composition + time twin.

cluster_id alphabet. Litmus T1-assay Wilcoxon vs 0 in noSD @ NOR_TX.

Default: sealed ProxComp-A joint BH on shannon+richness (m=4).

``--per-scalar-families``: new 2026-10-08 contract — one BH family per DR cousin
(shannon / richness / hill2), each m=2 (F,M). Writes a separate out dir; does not
overwrite sealed ProxComp-A lava.
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
from nor_object_mi.prox_comp import (  # noqa: E402
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
    NEAR_R_M,
    NOISE_CLUSTER,
    PER_SCALAR_FAMILY_METRICS,
    PER_SCALAR_FAMILY_NAME,
    PER_SCALAR_FAMILY_SIZE,
    TIME_FAMILY_A_SIZE,
    TIME_FAMILY_METRICS,
    TRIAL,
    assert_family_a_size,
    assert_level_family_a_size,
    assert_per_scalar_family_sizes,
    assert_time_family_a_size,
    score_prox_composition,
)
from nor_object_mi.simpler_first_da import apply_bh, apply_bh_grouped  # noqa: E402
from nor_object_mi.simpler_first_presence import wilcoxon_paired  # noqa: E402
from nor_object_mi.simpler_first_q1 import kruskal_within_sex  # noqa: E402
from nor_object_mi.spot_xy import role_distances_m  # noqa: E402

MODEL = "paramscan_s1-1e8_s2-1e5_ss-50"
DEFAULT_NOR_H5 = Path(r"D:\sack\datas\impress\my_NOR_results.h5")
DEFAULT_KPMS = Path(r"D:\sack\datas\impress\moseq_251017" rf"\{MODEL}\results.h5")
DEFAULT_PROTO = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_syllable_signatures\syllable_prototypes_clustered.csv"
)
DEFAULT_OUT = Path(
    r"D:\sack\datas\impress\moseq_251017" r"\_nor_object_mi\simpler_first_prox_comp"
)
DEFAULT_OUT_PER_SCALAR = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_prox_comp_per_scalar_fams"
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
    r_m: float,
) -> dict[str, object] | None:
    if js.trial != TRIAL or js.session not in FAMILY_SESSIONS_PANEL:
        return None
    if js.animal_id not in nor_h5 or js.raw_session not in nor_h5[js.animal_id]:
        return None
    if js.kpms_key not in kpms_h5:
        return None
    sg = nor_h5[js.animal_id][js.raw_session]
    role_map = fam_nvl_map_for_session(nor_h5, js.animal_id, js.raw_session)
    if not role_map:
        return None
    try:
        d_fam, d_nvl, valid = role_distances_m(sg, role_map)
        syll_raw = np.asarray(kpms_h5[js.kpms_key]["syllable"][()], dtype=np.int64).ravel()
    except (KeyError, ValueError, OSError):
        return None
    n = min(len(valid), len(syll_raw), len(d_fam), len(d_nvl))
    if n < 1:
        return None
    syll_c, n_unmapped = _map_syllables(syll_raw[:n], cmap)
    scored = score_prox_composition(
        d_fam[:n],
        d_nvl[:n],
        valid[:n],
        syll_c,
        r_m=r_m,
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
        "n_unmapped_frames": int(n_unmapped),
        **scored,
    }


def collect_per_animal(
    nor_h5: h5py.File,
    kpms_h5: h5py.File,
    *,
    cmap: dict[int, int],
    min_frames: int,
    r_m: float,
) -> pd.DataFrame:
    kept = set(filter_cohort(nor_h5)["kept_ids"])
    rows: list[dict[str, object]] = []
    for js in iter_joined_sessions(nor_h5, kpms_h5, kept_ids=kept, session=None):
        row = score_joined(
            nor_h5, kpms_h5, js=js, cmap=cmap, min_frames=min_frames, r_m=r_m
        )
        if row is not None:
            rows.append(row)
    return pd.DataFrame(rows)


def build_litmus_t1_assay(
    animals: pd.DataFrame,
    *,
    contrast_metrics: tuple[str, ...] = FAMILY_METRICS,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    strata = list(FAMILY_SEXES) + ["all"]
    specs = [
        (
            contrast_metrics,
            "contrast_eligible",
            "ProxComp-litmus-T1-assay",
            "q4_prox_comp_assay",
        ),
        (TIME_FAMILY_METRICS, "time_contrast_eligible", "TimeProx-litmus-T1-assay", "q4_time_prox_assay"),
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
        k["family"] = "ProxComp-A"
        k["question"] = "q5_prox_comp_condition"
        k["litmus"] = "B_condition"
        parts.append(k)
    tests = pd.concat(parts, ignore_index=True)
    tests = tests[tests["sex"].isin(FAMILY_SEXES)].reset_index(drop=True)
    assert_family_a_size(int(pd.to_numeric(tests["p"], errors="coerce").notna().sum()))
    return apply_bh(tests)


def build_per_scalar_family_tests(animals: pd.DataFrame) -> pd.DataFrame:
    """Kruskal × condition within sex; BH independently within each metric (m=2)."""
    sub = animals[
        (animals["session"] == LITMUS_T1_ASSAY_SESSION)
        & (animals["contrast_eligible"].astype(bool))
    ].copy()
    parts: list[pd.DataFrame] = []
    for metric in PER_SCALAR_FAMILY_METRICS:
        k = kruskal_within_sex(sub, metric=metric).copy()
        k["session"] = LITMUS_T1_ASSAY_SESSION
        k["trial"] = TRIAL
        k["grain"] = GRAIN.format(session=LITMUS_T1_ASSAY_SESSION)
        k["family"] = PER_SCALAR_FAMILY_NAME[metric]
        k["question"] = "q5_prox_comp_per_scalar_condition"
        k["litmus"] = "B_condition"
        parts.append(k)
    tests = pd.concat(parts, ignore_index=True)
    tests = tests[tests["sex"].isin(FAMILY_SEXES)].reset_index(drop=True)
    counts = {
        str(m): int(
            pd.to_numeric(tests.loc[tests["metric"] == m, "p"], errors="coerce")
            .notna()
            .sum()
        )
        for m in PER_SCALAR_FAMILY_METRICS
    }
    assert_per_scalar_family_sizes(counts)
    return apply_bh_grouped(tests, ["metric"])


def build_time_family_a_tests(animals: pd.DataFrame) -> pd.DataFrame:
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
        k["family"] = "TimeProx-A"
        k["question"] = "q5_time_prox_condition"
        k["litmus"] = "B_condition"
        parts.append(k)
    tests = pd.concat(parts, ignore_index=True)
    tests = tests[tests["sex"].isin(FAMILY_SEXES)].reset_index(drop=True)
    assert_time_family_a_size(int(pd.to_numeric(tests["p"], errors="coerce").notna().sum()))
    return apply_bh(tests)


def build_level_family_a_tests(animals: pd.DataFrame) -> pd.DataFrame:
    """Kruskal × ProxLevel-A; BH over 8 cells (user-authorized 2026-10-06)."""
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
        k["family"] = "ProxLevel-A"
        k["question"] = "q5_prox_level_condition"
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
                n_tok = int(g["time_contrast_eligible"].astype(bool).sum()) if n else 0
                rows.append(
                    {
                        "session": session,
                        "sex": sex,
                        "condition": condition,
                        "n_rows": n,
                        "n_eligible_comp": n_ok,
                        "n_eligible_time": n_tok,
                        "frac_eligible_comp": float(n_ok / n) if n else float("nan"),
                        "frac_eligible_time": float(n_tok / n) if n else float("nan"),
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
    r_m: float = NEAR_R_M,
    per_scalar_families: bool = False,
) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    cmap = _load_cluster_map(proto_csv, MODEL)
    with h5py.File(nor_h5_path, "r") as nor_h5, h5py.File(kpms_path, "r") as kpms_h5:
        animals = collect_per_animal(
            nor_h5, kpms_h5, cmap=cmap, min_frames=min_frames, r_m=r_m
        )
    print(f"Scored {len(animals)} animal×session rows", flush=True)
    animals.to_csv(out_dir / "prox_comp_per_animal.csv", index=False)
    build_eligibility_summary(animals).to_csv(
        out_dir / "prox_comp_eligibility.csv", index=False
    )
    litmus_metrics = (
        PER_SCALAR_FAMILY_METRICS if per_scalar_families else FAMILY_METRICS
    )
    litmus_t1_assay = build_litmus_t1_assay(animals, contrast_metrics=litmus_metrics)
    litmus_t1_assay.to_csv(out_dir / "prox_comp_litmus_t1_assay.csv", index=False)
    litmus_t1_assay.to_csv(out_dir / "prox_comp_litmus_a.csv", index=False)
    if per_scalar_families:
        tests = build_per_scalar_family_tests(animals)
        tests.to_csv(out_dir / "prox_comp_tests_long.csv", index=False)
        family_label = "ProxComp-per-scalar"
        family_size = PER_SCALAR_FAMILY_SIZE
        n_families = len(PER_SCALAR_FAMILY_METRICS)
    else:
        tests = build_family_a_tests(animals)
        tests.to_csv(out_dir / "prox_comp_tests_long.csv", index=False)
        family_label = "ProxComp-A"
        family_size = FAMILY_A_SIZE
        n_families = 1
    time_tests = build_time_family_a_tests(animals)
    time_tests.to_csv(out_dir / "time_prox_tests_long.csv", index=False)

    level_tests = build_level_family_a_tests(animals)
    level_tests.to_csv(out_dir / "prox_level_tests_long.csv", index=False)

    n_hit = int(tests["hit_fdr05"].astype(bool).sum()) if not tests.empty else 0
    t_hit = int(time_tests["hit_fdr05"].astype(bool).sum()) if not time_tests.empty else 0
    l_hit = int(level_tests["hit_fdr05"].astype(bool).sum()) if not level_tests.empty else 0
    assay_metrics = (
        PER_SCALAR_FAMILY_METRICS if per_scalar_families else FAMILY_METRICS
    )
    a_primary = litmus_t1_assay[
        (litmus_t1_assay["sex"] == "all") & (litmus_t1_assay["metric"].isin(assay_metrics))
    ]
    a_pass = bool(
        a_primary["hit_p05"].astype(bool).any()
        and (pd.to_numeric(a_primary["median_delta"], errors="coerce") > 0).any()
    )
    a_time = litmus_t1_assay[
        (litmus_t1_assay["sex"] == "all") & (litmus_t1_assay["metric"] == "dr_time_prox")
    ]
    a_time_pass = bool(
        (not a_time.empty)
        and bool(a_time["hit_p05"].astype(bool).any())
        and (pd.to_numeric(a_time["median_delta"], errors="coerce") > 0).any()
    )
    per_family_hits: dict[str, int] = {}
    if per_scalar_families and not tests.empty:
        for metric in PER_SCALAR_FAMILY_METRICS:
            fam = PER_SCALAR_FAMILY_NAME[metric]
            sub = tests[tests["metric"] == metric]
            per_family_hits[fam] = int(sub["hit_fdr05"].astype(bool).sum())
    summary: dict[str, object] = {
        "status": "ok",
        "family": family_label,
        "family_size": family_size,
        "n_scalar_families": n_families,
        "per_scalar_families": bool(per_scalar_families),
        "per_family_n_hit_fdr05": per_family_hits,
        "time_family": "TimeProx-A",
        "time_family_size": TIME_FAMILY_A_SIZE,
        "level_family": "ProxLevel-A",
        "level_family_size": LEVEL_FAMILY_A_SIZE,
        "model": MODEL,
        "alphabet": "cluster_id",
        "r_m": float(r_m),
        "min_frames_n": int(min_frames),
        "n_animal_session_rows": int(len(animals)),
        "litmus_t1_assay_pass": a_pass,
        "litmus_t1_assay_time_pass": a_time_pass,
        "litmus_a_pass": a_pass,
        "litmus_a_time_pass": a_time_pass,
        "n_hit_fdr05": n_hit,
        "pass_family_a": bool(n_hit > 0),
        "time_n_hit_fdr05": t_hit,
        "pass_time_family_a": bool(t_hit > 0),
        "level_n_hit_fdr05": l_hit,
        "pass_level_family_a": bool(l_hit > 0),
        "elapsed_s": float(time.time() - t0),
    }
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
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--min-frames", type=int, default=MIN_FRAMES_N)
    ap.add_argument("--r-m", type=float, default=NEAR_R_M)
    ap.add_argument(
        "--per-scalar-families",
        action="store_true",
        help="BH independently per DR cousin (shannon/richness/hill2); new out dir",
    )
    args = ap.parse_args()
    out = args.out_dir
    if out is None:
        out = DEFAULT_OUT_PER_SCALAR if args.per_scalar_families else DEFAULT_OUT
    run(
        args.nor_h5,
        args.kpms_h5,
        args.proto_csv,
        out,
        min_frames=args.min_frames,
        r_m=args.r_m,
        per_scalar_families=bool(args.per_scalar_families),
    )


if __name__ == "__main__":
    main()
