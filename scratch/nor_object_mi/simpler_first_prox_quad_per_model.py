"""Per-model (raw_syllable_id) QuadComp + ProxComp composition boards.

Exploratory secondary alphabet after the locked ``cluster_id`` runs.
BH within each model (4-cell ProxComp-A / QuadComp-A analogs). Consensus =
median across models of animal-level DR cousins, then one Kruskal board.
Time twins are alphabet-free — not re-grid here (see locked Quad/Prox runs).

ADR-0005: raw ids are model-local; do not pool alphabets across models.
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

from nor_object_mi.bout_kinematics import discover_paramscan_models  # noqa: E402
from nor_object_mi.fam_nvl import fam_nvl_map_for_session  # noqa: E402
from nor_object_mi.join_keys import filter_cohort, iter_joined_sessions  # noqa: E402
from nor_object_mi.prox_comp import (  # noqa: E402
    FAMILY_METRICS as PROX_DR_METRICS,
    FAMILY_A_SIZE as PROX_FAMILY_SIZE,
    NEAR_R_M,
    assert_family_a_size as assert_prox_family_a_size,
    score_prox_composition,
)
from nor_object_mi.quad_comp import (  # noqa: E402
    FAMILY_METRICS as QUAD_DR_METRICS,
    FAMILY_A_SIZE as QUAD_FAMILY_SIZE,
    FAMILY_SESSIONS_PANEL,
    FAMILY_SEXES,
    LITMUS_T1_ASSAY_CONDITION,
    LITMUS_T1_ASSAY_SESSION,
    MIN_FRAMES_N,
    TRIAL,
    assert_family_a_size as assert_quad_family_a_size,
    score_quad_composition,
)

QUAD_LEVEL_METRICS: tuple[str, ...] = (
    "fam_shannon_quad",
    "nvl_shannon_quad",
    "fam_richness_quad",
    "nvl_richness_quad",
    "fam_hill2_quad",
    "nvl_hill2_quad",
)
PROX_LEVEL_METRICS: tuple[str, ...] = (
    "fam_shannon_prox",
    "nvl_shannon_prox",
    "fam_richness_prox",
    "nvl_richness_prox",
    "fam_hill2_prox",
    "nvl_hill2_prox",
)
from nor_object_mi.simpler_first_da import apply_bh  # noqa: E402
from nor_object_mi.simpler_first_presence import wilcoxon_paired  # noqa: E402
from nor_object_mi.simpler_first_q1 import kruskal_within_sex  # noqa: E402
from nor_object_mi.spot_xy import object_centers_px, role_distances_m, spot_xy_px  # noqa: E402
from nor_object_mi.syllable_spatial_heatmap import (  # noqa: E402
    arena_center_px,
    needs_novel_alignment,
    nvl_nearest_hist_locus,
)

DEFAULT_NOR_H5 = Path(r"D:\sack\datas\impress\my_NOR_results.h5")
DEFAULT_ENSEMBLE = Path(r"D:\sack\datas\impress\moseq_251017")
DEFAULT_OUT = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_prox_quad_per_model"
)


def _score_one(
    nor_h5: h5py.File,
    kpms_h5: h5py.File,
    *,
    js,
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
        d_fam, d_nvl, valid_d = role_distances_m(sg, role_map)
        syll = np.asarray(kpms_h5[js.kpms_key]["syllable"][()], dtype=np.int64).ravel()
    except (KeyError, ValueError, OSError):
        return None
    n = min(len(valid), len(valid_d), len(syll), len(x_px), len(d_fam))
    if n < 1:
        return None
    # Raw alphabet: use syllable ids as labels (model-local).
    syll_raw = syll[:n]
    nvl_side = nvl_nearest_hist_locus(
        nor_h5,
        animal_id=js.animal_id,
        session=js.session,
        raw_session=js.raw_session,
        trial=js.trial,
    )
    rotate = needs_novel_alignment(nvl_side)
    quad = score_quad_composition(
        x_px[:n],
        y_px[:n],
        valid[:n],
        syll_raw,
        cx=cx,
        cy=cy,
        fam_center_px=centers[fam_key],
        nvl_center_px=centers[nvl_key],
        rotate_180=rotate,
        min_frames=min_frames,
    )
    prox = score_prox_composition(
        d_fam[:n],
        d_nvl[:n],
        valid_d[:n],
        syll_raw,
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
        "alphabet": "raw_syllable_id",
        "nvl_side": nvl_side,
        "contrast_eligible_quad": bool(quad["contrast_eligible"]),
        "dr_shannon_quad": float(quad["dr_shannon_quad"]),
        "dr_richness_quad": float(quad["dr_richness_quad"]),
        "dr_hill2_quad": float(quad["dr_hill2_quad"]),
        "fam_shannon_quad": float(quad["fam_shannon_quad"]),
        "nvl_shannon_quad": float(quad["nvl_shannon_quad"]),
        "fam_richness_quad": float(quad["fam_richness_quad"]),
        "nvl_richness_quad": float(quad["nvl_richness_quad"]),
        "fam_hill2_quad": float(quad["fam_hill2_quad"]),
        "nvl_hill2_quad": float(quad["nvl_hill2_quad"]),
        "n_frames_fam_quad": float(quad["n_frames_fam_quad"]),
        "n_frames_nvl_quad": float(quad["n_frames_nvl_quad"]),
        "object_cell_collision": bool(quad["object_cell_collision"]),
        "contrast_eligible_prox": bool(prox["contrast_eligible"]),
        "dr_shannon_prox": float(prox["dr_shannon_prox"]),
        "dr_richness_prox": float(prox["dr_richness_prox"]),
        "dr_hill2_prox": float(prox["dr_hill2_prox"]),
        "fam_shannon_prox": float(prox["fam_shannon_prox"]),
        "nvl_shannon_prox": float(prox["nvl_shannon_prox"]),
        "fam_richness_prox": float(prox["fam_richness_prox"]),
        "nvl_richness_prox": float(prox["nvl_richness_prox"]),
        "fam_hill2_prox": float(prox["fam_hill2_prox"]),
        "nvl_hill2_prox": float(prox["nvl_hill2_prox"]),
        "n_frames_fam_prox": float(prox["n_frames_fam_prox"]),
        "n_frames_nvl_prox": float(prox["n_frames_nvl_prox"]),
        "n_spot_both_prox": float(prox["n_spot_both_prox"]),
        "dr_time_prox": float(prox["dr_time_prox"]),
        "time_contrast_eligible": bool(prox["time_contrast_eligible"]),
    }


def collect_model(
    nor_h5: h5py.File,
    kpms_h5: h5py.File,
    *,
    model: str,
    min_frames: int,
    r_m: float,
) -> pd.DataFrame:
    kept = set(filter_cohort(nor_h5)["kept_ids"])
    rows: list[dict[str, object]] = []
    for js in iter_joined_sessions(nor_h5, kpms_h5, kept_ids=kept, session=None):
        row = _score_one(nor_h5, kpms_h5, js=js, min_frames=min_frames, r_m=r_m)
        if row is not None:
            row["model"] = model
            rows.append(row)
    return pd.DataFrame(rows)


def _family_tests(
    animals: pd.DataFrame,
    *,
    metrics: tuple[str, ...],
    elig_col: str,
    family: str,
    question: str,
    assert_size,
) -> pd.DataFrame:
    sub = animals[
        (animals["session"] == LITMUS_T1_ASSAY_SESSION) & (animals[elig_col].astype(bool))
    ].copy()
    parts: list[pd.DataFrame] = []
    for metric in metrics:
        k = kruskal_within_sex(sub, metric=metric).copy()
        k["session"] = LITMUS_T1_ASSAY_SESSION
        k["trial"] = TRIAL
        k["family"] = family
        k["question"] = question
        k["litmus"] = "B_condition"
        parts.append(k)
    tests = pd.concat(parts, ignore_index=True)
    tests = tests[tests["sex"].isin(FAMILY_SEXES)].reset_index(drop=True)
    assert_size(int(pd.to_numeric(tests["p"], errors="coerce").notna().sum()))
    return apply_bh(tests)


def _litmus_t1_assay(
    animals: pd.DataFrame,
    *,
    metrics: tuple[str, ...],
    elig_col: str,
    family: str,
) -> pd.DataFrame:
    sub = animals[
        (animals["session"] == LITMUS_T1_ASSAY_SESSION)
        & (animals["condition"] == LITMUS_T1_ASSAY_CONDITION)
        & (animals[elig_col].astype(bool))
    ].copy()
    rows: list[dict[str, object]] = []
    for metric in metrics:
        for sex in list(FAMILY_SEXES) + ["all"]:
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
                    **rec,
                    "hit_p05": bool(np.isfinite(rec["p"]) and float(rec["p"]) < 0.05),
                }
            )
    return pd.DataFrame(rows)


def consensus_animal_table(per: pd.DataFrame, metrics: tuple[str, ...], elig_col: str) -> pd.DataFrame:
    """Median across models of eligible animal×session metric values."""
    tx = per[(per["session"] == LITMUS_T1_ASSAY_SESSION) & (per[elig_col].astype(bool))].copy()
    rows: list[dict[str, object]] = []
    for (aid, sex, condition), g in tx.groupby(["animal_id", "sex", "condition"], sort=True):
        row: dict[str, object] = {
            "animal_id": aid,
            "sex": sex,
            "condition": condition,
            "session": LITMUS_T1_ASSAY_SESSION,
            "trial": TRIAL,
            "alphabet": "raw_syllable_id_consensus_median",
            "n_models": int(g["model"].nunique()),
            elig_col: True,
        }
        for m in metrics:
            row[m] = float(np.nanmedian(pd.to_numeric(g[m], errors="coerce").to_numpy()))
        rows.append(row)
    return pd.DataFrame(rows)


def run(
    nor_h5_path: Path,
    ensemble_root: Path,
    out_dir: Path,
    *,
    min_frames: int = MIN_FRAMES_N,
    r_m: float = NEAR_R_M,
    progress_every_s: float = 30.0,
    models: list[str] | None = None,
) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    if models is None:
        models = discover_paramscan_models(ensemble_root)
    else:
        models = list(models)
    if not models:
        raise FileNotFoundError(f"no paramscan models under {ensemble_root}")
    t0 = time.time()
    last = t0
    frames: list[pd.DataFrame] = []
    test_parts: list[pd.DataFrame] = []
    litmus_parts: list[pd.DataFrame] = []

    with h5py.File(nor_h5_path, "r") as nor_h5:
        for i, model in enumerate(models, start=1):
            results = ensemble_root / model / "results.h5"
            with h5py.File(results, "r") as kpms_h5:
                animals = collect_model(
                    nor_h5, kpms_h5, model=model, min_frames=min_frames, r_m=r_m
                )
            if animals.empty:
                print(f"[{i}/{len(models)}] {model}: empty", flush=True)
                continue
            frames.append(animals)
            q_tests = _family_tests(
                animals,
                metrics=QUAD_DR_METRICS,
                elig_col="contrast_eligible_quad",
                family="QuadComp-raw-A",
                question="q5_quad_comp_raw_condition",
                assert_size=assert_quad_family_a_size,
            )
            q_tests["model"] = model
            p_tests = _family_tests(
                animals,
                metrics=PROX_DR_METRICS,
                elig_col="contrast_eligible_prox",
                family="ProxComp-raw-A",
                question="q5_prox_comp_raw_condition",
                assert_size=assert_prox_family_a_size,
            )
            p_tests["model"] = model
            test_parts.extend([q_tests, p_tests])
            q_a = _litmus_t1_assay(
                animals,
                metrics=QUAD_DR_METRICS,
                elig_col="contrast_eligible_quad",
                family="QuadComp-raw-litmus-T1-assay",
            )
            q_a["model"] = model
            p_a = _litmus_t1_assay(
                animals,
                metrics=PROX_DR_METRICS,
                elig_col="contrast_eligible_prox",
                family="ProxComp-raw-litmus-T1-assay",
            )
            p_a["model"] = model
            litmus_parts.extend([q_a, p_a])
            n_hit_q = int(q_tests["hit_fdr05"].astype(bool).sum())
            n_hit_p = int(p_tests["hit_fdr05"].astype(bool).sum())
            now = time.time()
            if now - last >= progress_every_s or i == len(models):
                print(
                    f"[{i}/{len(models)}] {model}: rows={len(animals)} "
                    f"quad_fdr={n_hit_q} prox_fdr={n_hit_p} "
                    f"elapsed={now - t0:.0f}s",
                    flush=True,
                )
                last = now

    per = pd.concat(frames, ignore_index=True)
    per.to_csv(out_dir / "per_model_per_animal.csv", index=False)
    tests = pd.concat(test_parts, ignore_index=True)
    tests.to_csv(out_dir / "per_model_tests_long.csv", index=False)
    litmus = pd.concat(litmus_parts, ignore_index=True)
    litmus.to_csv(out_dir / "per_model_litmus_t1_assay.csv", index=False)
    litmus.to_csv(out_dir / "per_model_litmus_a.csv", index=False)

    # Consensus boards (separate BH families)
    cons_q = consensus_animal_table(
        per, QUAD_DR_METRICS + QUAD_LEVEL_METRICS, "contrast_eligible_quad"
    )
    cons_p = consensus_animal_table(
        per, PROX_DR_METRICS + PROX_LEVEL_METRICS, "contrast_eligible_prox"
    )
    cons_q.to_csv(out_dir / "consensus_quad_per_animal.csv", index=False)
    cons_p.to_csv(out_dir / "consensus_prox_per_animal.csv", index=False)
    cq = _family_tests(
        cons_q,
        metrics=QUAD_DR_METRICS,
        elig_col="contrast_eligible_quad",
        family="QuadComp-raw-consensus-A",
        question="q5_quad_comp_raw_consensus",
        assert_size=assert_quad_family_a_size,
    )
    cp = _family_tests(
        cons_p,
        metrics=PROX_DR_METRICS,
        elig_col="contrast_eligible_prox",
        family="ProxComp-raw-consensus-A",
        question="q5_prox_comp_raw_consensus",
        assert_size=assert_prox_family_a_size,
    )
    cons_tests = pd.concat([cq, cp], ignore_index=True)
    cons_tests.to_csv(out_dir / "consensus_tests_long.csv", index=False)

    # Model agreement: models with ≥1 FDR hit in each family
    agree_rows = []
    for family, g in tests.groupby("family"):
        for model, mg in g.groupby("model"):
            agree_rows.append(
                {
                    "family": family,
                    "model": model,
                    "n_hit_fdr05": int(mg["hit_fdr05"].astype(bool).sum()),
                    "n_hit_p05": int(mg["hit_p05"].astype(bool).sum()),
                    "pass": bool(mg["hit_fdr05"].astype(bool).any()),
                }
            )
    agree = pd.DataFrame(agree_rows)
    agree.to_csv(out_dir / "model_agreement.csv", index=False)

    n_models = int(per["model"].nunique())
    summary = {
        "status": "ok",
        "alphabet": "raw_syllable_id",
        "n_models": n_models,
        "n_animal_session_model_rows": int(len(per)),
        "quad_models_with_fdr_hit": int(
            agree[(agree["family"] == "QuadComp-raw-A") & agree["pass"]].shape[0]
        ),
        "prox_models_with_fdr_hit": int(
            agree[(agree["family"] == "ProxComp-raw-A") & agree["pass"]].shape[0]
        ),
        "consensus_quad_n_hit_fdr05": int(cq["hit_fdr05"].astype(bool).sum()),
        "consensus_prox_n_hit_fdr05": int(cp["hit_fdr05"].astype(bool).sum()),
        "litmus_t1_assay_sex_all_hit_rate_quad": float(
            litmus[
                (litmus["family"] == "QuadComp-raw-litmus-T1-assay")
                & (litmus["sex"] == "all")
            ]["hit_p05"]
            .astype(bool)
            .mean()
        )
        if not litmus.empty
        else float("nan"),
        "litmus_t1_assay_sex_all_hit_rate_prox": float(
            litmus[
                (litmus["family"] == "ProxComp-raw-litmus-T1-assay")
                & (litmus["sex"] == "all")
            ]["hit_p05"]
            .astype(bool)
            .mean()
        )
        if not litmus.empty
        else float("nan"),
        "litmus_a_sex_all_hit_rate_quad": float(
            litmus[
                (litmus["family"] == "QuadComp-raw-litmus-T1-assay")
                & (litmus["sex"] == "all")
            ]["hit_p05"]
            .astype(bool)
            .mean()
        )
        if not litmus.empty
        else float("nan"),
        "litmus_a_sex_all_hit_rate_prox": float(
            litmus[
                (litmus["family"] == "ProxComp-raw-litmus-T1-assay")
                & (litmus["sex"] == "all")
            ]["hit_p05"]
            .astype(bool)
            .mean()
        )
        if not litmus.empty
        else float("nan"),
        "note": "exploratory; locked negatives stand on cluster_id boards",
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
    ap.add_argument("--ensemble-root", type=Path, default=DEFAULT_ENSEMBLE)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--min-frames", type=int, default=MIN_FRAMES_N)
    ap.add_argument("--r-m", type=float, default=NEAR_R_M)
    ap.add_argument(
        "--models",
        type=str,
        default="",
        help="Comma-separated model folder names; default = all paramscan_*",
    )
    args = ap.parse_args()
    model_list = [m.strip() for m in args.models.split(",") if m.strip()] or None
    run(
        args.nor_h5,
        args.ensemble_root,
        args.out_dir,
        min_frames=args.min_frames,
        r_m=args.r_m,
        models=model_list,
    )


if __name__ == "__main__":
    main()
