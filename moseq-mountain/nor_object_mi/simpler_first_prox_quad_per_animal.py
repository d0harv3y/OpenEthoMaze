"""Object-stratified Prox/Quad shannon–richness on animal-local alphabets.

Campaign: ``nor_per_animal_paramscan`` (144 × 9 fits). Each fit has its own
syllable alphabet — DR cousins are within-animal (fam vs nvl masks), so they
remain askable without remapping. Cross-animal Kruskal is exploratory
(#alphabet-bound; ADR-0005 caution).

Compare to locked ``cluster_id`` Prox/Quad and cohort raw ×21 consensus.
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

from nor_object_mi.fam_nvl import fam_nvl_map_for_session  # noqa: E402
from nor_object_mi.join_keys import filter_cohort, parse_kpms_group  # noqa: E402
from nor_object_mi.prox_comp import (  # noqa: E402
    FAMILY_METRICS as PROX_DR_METRICS,
    NEAR_R_M,
    assert_family_a_size as assert_prox_family_a_size,
    score_prox_composition,
)
from nor_object_mi.quad_comp import (  # noqa: E402
    FAMILY_METRICS as QUAD_DR_METRICS,
    FAMILY_SESSIONS_PANEL,
    FAMILY_SEXES,
    LITMUS_A_CONDITION,
    LITMUS_A_SESSION,
    MIN_FRAMES_N,
    TRIAL,
    assert_family_a_size as assert_quad_family_a_size,
    score_quad_composition,
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

_CELL_RE = re.compile(r"(paramscan_.*)")

DEFAULT_NOR_H5 = Path(r"D:\sack\datas\impress\my_NOR_results.h5")
DEFAULT_PER_ANIMAL = Path(r"D:\sack\datas\impress\nor_per_animal_paramscan")
DEFAULT_OUT = Path(
    r"D:\sack\datas\impress\nor_per_animal_paramscan"
    r"\_nor_object_mi\simpler_first_prox_quad_per_animal"
)
DEFAULT_CLUSTER_QUAD = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_quad_comp\quad_comp_per_animal.csv"
)
DEFAULT_CLUSTER_PROX = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_prox_comp\prox_comp_per_animal.csv"
)
DEFAULT_COHORT_RAW = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_prox_quad_per_model\per_model_per_animal.csv"
)

QUAD_LEVEL = (
    "fam_shannon_quad",
    "nvl_shannon_quad",
    "fam_richness_quad",
    "nvl_richness_quad",
    "fam_hill2_quad",
    "nvl_hill2_quad",
)
PROX_LEVEL = (
    "fam_shannon_prox",
    "nvl_shannon_prox",
    "fam_richness_prox",
    "nvl_richness_prox",
    "fam_hill2_prox",
    "nvl_hill2_prox",
)
COMPARE_METRICS = QUAD_DR_METRICS + PROX_DR_METRICS + QUAD_LEVEL + PROX_LEVEL


def cell_of(results_h5: str | Path) -> str:
    name = Path(results_h5).parent.name
    m = _CELL_RE.search(name)
    if not m:
        raise ValueError(f"cannot parse cell from {name!r}")
    tail = m.group(1)
    return tail[tail.index("paramscan_") :]


def _session_wire(raw_session: str) -> str | None:
    """Map NOR1..4_* raw to panel session token."""
    rs = str(raw_session)
    if rs.startswith("NOR1_"):
        return "NOR_BL"
    if rs.startswith("NOR2_"):
        return "NOR_TX"
    if rs.startswith("NOR3_"):
        return "NOR_REC3hr"
    if rs.startswith("NOR4_"):
        return "NOR_REC11hr"
    return None


def _score_key(
    nor_h5: h5py.File,
    kpms_h5: h5py.File,
    *,
    kpms_key: str,
    min_frames: int,
    r_m: float,
) -> dict[str, object] | None:
    try:
        aid, raw = parse_kpms_group(str(kpms_key))
    except ValueError:
        return None
    if not str(raw).endswith("_nvl_obj"):
        return None
    session = _session_wire(raw)
    if session is None or session not in FAMILY_SESSIONS_PANEL:
        return None
    if aid not in nor_h5 or raw not in nor_h5[aid]:
        return None
    if kpms_key not in kpms_h5:
        return None
    ag = nor_h5[aid]
    sg = ag[raw]
    role_map = fam_nvl_map_for_session(nor_h5, aid, raw)
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
        syll = np.asarray(kpms_h5[kpms_key]["syllable"][()], dtype=np.int64).ravel()
    except (KeyError, ValueError, OSError, TypeError):
        return None
    n = min(len(valid), len(valid_d), len(syll), len(x_px), len(d_fam))
    if n < 1:
        return None
    nvl_side = nvl_nearest_hist_locus(
        nor_h5,
        animal_id=aid,
        session=session,
        raw_session=raw,
        trial=TRIAL,
    )
    rotate = needs_novel_alignment(nvl_side)
    quad = score_quad_composition(
        x_px[:n],
        y_px[:n],
        valid[:n],
        syll[:n],
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
        syll[:n],
        r_m=r_m,
        min_frames=min_frames,
    )
    sex = str(ag.attrs.get("sex", "") or "")
    condition = str(ag.attrs.get("condition", "") or ag.attrs.get("tx", "") or "")
    return {
        "animal_id": str(aid),
        "sex": sex,
        "condition": condition,
        "session": session,
        "trial": TRIAL,
        "raw_session": str(raw),
        "alphabet": "per_animal_raw_syllable_id",
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
    }


def _family_tests(
    animals: pd.DataFrame,
    *,
    metrics: tuple[str, ...],
    elig_col: str,
    family: str,
    assert_size,
) -> pd.DataFrame:
    sub = animals[
        (animals["session"] == LITMUS_A_SESSION) & (animals[elig_col].astype(bool))
    ].copy()
    parts: list[pd.DataFrame] = []
    for metric in metrics:
        k = kruskal_within_sex(sub, metric=metric).copy()
        k["session"] = LITMUS_A_SESSION
        k["trial"] = TRIAL
        k["family"] = family
        k["question"] = "q5_prox_quad_per_animal_condition"
        k["litmus"] = "B_condition"
        parts.append(k)
    tests = pd.concat(parts, ignore_index=True)
    tests = tests[tests["sex"].isin(FAMILY_SEXES)].reset_index(drop=True)
    assert_size(int(pd.to_numeric(tests["p"], errors="coerce").notna().sum()))
    return apply_bh(tests)


def _litmus_a(
    animals: pd.DataFrame,
    *,
    metrics: tuple[str, ...],
    elig_col: str,
    family: str,
) -> pd.DataFrame:
    sub = animals[
        (animals["session"] == LITMUS_A_SESSION)
        & (animals["condition"] == LITMUS_A_CONDITION)
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
                    "session": LITMUS_A_SESSION,
                    "trial": TRIAL,
                    "condition": LITMUS_A_CONDITION,
                    "sex": sex,
                    "metric": metric,
                    "litmus": "A_assay_validity",
                    "family": family,
                    **rec,
                    "hit_p05": bool(np.isfinite(rec["p"]) and float(rec["p"]) < 0.05),
                }
            )
    return pd.DataFrame(rows)


def consensus_median(
    per: pd.DataFrame,
    metrics: tuple[str, ...],
    elig_col: str,
) -> pd.DataFrame:
    tx = per[(per["session"] == LITMUS_A_SESSION) & (per[elig_col].astype(bool))].copy()
    rows: list[dict[str, object]] = []
    for (aid, sex, condition), g in tx.groupby(["animal_id", "sex", "condition"], sort=True):
        row: dict[str, object] = {
            "animal_id": aid,
            "sex": sex,
            "condition": condition,
            "session": LITMUS_A_SESSION,
            "trial": TRIAL,
            "alphabet": "per_animal_consensus_median",
            "n_cells": int(g["model"].nunique()),
            elig_col: True,
        }
        for m in metrics:
            row[m] = float(np.nanmedian(pd.to_numeric(g[m], errors="coerce").to_numpy()))
        rows.append(row)
    return pd.DataFrame(rows)


def _spearman(a: np.ndarray, b: np.ndarray) -> tuple[float, int]:
    ok = np.isfinite(a) & np.isfinite(b)
    n = int(ok.sum())
    if n < 5:
        return float("nan"), n
    from scipy import stats

    r, _p = stats.spearmanr(a[ok], b[ok])
    return float(r), n


def compare_boards(
    *,
    per_animal_cons: pd.DataFrame,
    cluster_quad: pd.DataFrame,
    cluster_prox: pd.DataFrame,
    cohort_raw: pd.DataFrame,
) -> pd.DataFrame:
    """Animal-level Spearman of TX scalars across alphabet boards."""

    def _aid(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out["animal_id"] = out["animal_id"].astype(str)
        return out

    per_animal_cons = _aid(per_animal_cons)
    cluster_quad = _aid(cluster_quad)
    cluster_prox = _aid(cluster_prox)
    cohort_raw = _aid(cohort_raw)

    cq = cluster_quad[
        (cluster_quad["session"] == LITMUS_A_SESSION)
        & (cluster_quad["contrast_eligible"].astype(bool))
    ].copy()
    cp = cluster_prox[
        (cluster_prox["session"] == LITMUS_A_SESSION)
        & (cluster_prox["contrast_eligible"].astype(bool))
    ].copy()
    # cohort raw consensus median at TX
    raw_tx = cohort_raw[
        (cohort_raw["session"] == LITMUS_A_SESSION)
        & (cohort_raw["contrast_eligible_quad"].astype(bool)
           | cohort_raw["contrast_eligible_prox"].astype(bool))
    ].copy()
    raw_rows: list[dict[str, object]] = []
    for aid, g in raw_tx.groupby("animal_id", sort=True):
        row: dict[str, object] = {
            "animal_id": aid,
            "sex": g["sex"].iloc[0],
            "condition": g["condition"].iloc[0],
        }
        for m in COMPARE_METRICS:
            if m not in g.columns:
                continue
            elig = (
                "contrast_eligible_quad"
                if m.endswith("_quad")
                else "contrast_eligible_prox"
            )
            vals = pd.to_numeric(g.loc[g[elig].astype(bool), m], errors="coerce")
            row[m] = float(np.nanmedian(vals.to_numpy())) if len(vals) else float("nan")
        raw_rows.append(row)
    raw_cons = pd.DataFrame(raw_rows)

    rows: list[dict[str, object]] = []
    boards = {
        "cluster": pd.merge(
            cq[["animal_id"] + [c for c in COMPARE_METRICS if c in cq.columns]],
            cp[["animal_id"] + [c for c in COMPARE_METRICS if c in cp.columns and c not in cq.columns]],
            on="animal_id",
            how="outer",
        ),
        "cohort_raw_median": raw_cons,
        "per_animal_median": per_animal_cons,
    }
    pairs = (
        ("per_animal_median", "cluster"),
        ("per_animal_median", "cohort_raw_median"),
        ("cohort_raw_median", "cluster"),
    )
    for left, right in pairs:
        L = boards[left].set_index("animal_id")
        R = boards[right].set_index("animal_id")
        common = L.index.intersection(R.index)
        for m in COMPARE_METRICS:
            if m not in L.columns or m not in R.columns:
                continue
            rho, n = _spearman(
                pd.to_numeric(L.loc[common, m], errors="coerce").to_numpy(dtype=float),
                pd.to_numeric(R.loc[common, m], errors="coerce").to_numpy(dtype=float),
            )
            rows.append(
                {
                    "metric": m,
                    "board_a": left,
                    "board_b": right,
                    "spearman_rho": rho,
                    "n_animals": n,
                    "grain": "animal × NOR_TX × nvl_obj",
                }
            )
    return pd.DataFrame(rows)


def run(
    nor_h5_path: Path,
    per_animal_root: Path,
    out_dir: Path,
    *,
    min_frames: int = MIN_FRAMES_N,
    r_m: float = NEAR_R_M,
    progress_every_s: float = 30.0,
    cluster_quad_csv: Path | None = None,
    cluster_prox_csv: Path | None = None,
    cohort_raw_csv: Path | None = None,
) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    last = t0
    results_list = sorted(
        glob.glob(str(per_animal_root / "exp*" / "*" / "anatomical" / "*_paramscan_*" / "results.h5"))
    )
    if not results_list:
        raise FileNotFoundError(f"no per-animal fits under {per_animal_root}")
    cells: dict[str, list[str]] = {}
    for fp in results_list:
        cells.setdefault(cell_of(fp), []).append(fp)
    print(f"{len(results_list)} fits in {len(cells)} cells", flush=True)

    frames: list[pd.DataFrame] = []
    test_parts: list[pd.DataFrame] = []
    litmus_parts: list[pd.DataFrame] = []

    with h5py.File(nor_h5_path, "r") as nor_h5:
        kept = set(filter_cohort(nor_h5)["kept_ids"])
        for i, cell in enumerate(sorted(cells), start=1):
            rows: list[dict[str, object]] = []
            n_skip = 0
            for fp in cells[cell]:
                with h5py.File(fp, "r") as kf:
                    for kpms_key in kf.keys():
                        try:
                            aid, _raw = parse_kpms_group(str(kpms_key))
                        except ValueError:
                            n_skip += 1
                            continue
                        if aid not in kept:
                            n_skip += 1
                            continue
                        rec = _score_key(
                            nor_h5, kf, kpms_key=str(kpms_key), min_frames=min_frames, r_m=r_m
                        )
                        if rec is None:
                            n_skip += 1
                            continue
                        rec["model"] = cell
                        rows.append(rec)
            animals = pd.DataFrame(rows)
            if animals.empty:
                print(f"[{i}/{len(cells)}] {cell}: EMPTY skip={n_skip}", flush=True)
                continue
            frames.append(animals)
            q_tests = _family_tests(
                animals,
                metrics=QUAD_DR_METRICS,
                elig_col="contrast_eligible_quad",
                family="QuadComp-peranimal-A",
                assert_size=assert_quad_family_a_size,
            )
            q_tests["model"] = cell
            p_tests = _family_tests(
                animals,
                metrics=PROX_DR_METRICS,
                elig_col="contrast_eligible_prox",
                family="ProxComp-peranimal-A",
                assert_size=assert_prox_family_a_size,
            )
            p_tests["model"] = cell
            test_parts.extend([q_tests, p_tests])
            q_a = _litmus_a(
                animals,
                metrics=QUAD_DR_METRICS,
                elig_col="contrast_eligible_quad",
                family="QuadComp-peranimal-litmus-A",
            )
            q_a["model"] = cell
            p_a = _litmus_a(
                animals,
                metrics=PROX_DR_METRICS,
                elig_col="contrast_eligible_prox",
                family="ProxComp-peranimal-litmus-A",
            )
            p_a["model"] = cell
            litmus_parts.extend([q_a, p_a])
            n_hit_q = int(q_tests["hit_fdr05"].astype(bool).sum())
            n_hit_p = int(p_tests["hit_fdr05"].astype(bool).sum())
            now = time.time()
            if now - last >= progress_every_s or i == len(cells):
                print(
                    f"[{i}/{len(cells)}] {cell}: rows={len(animals)} "
                    f"quad_fdr={n_hit_q} prox_fdr={n_hit_p} skip={n_skip} "
                    f"elapsed={now - t0:.0f}s",
                    flush=True,
                )
                last = now

    per = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    per.to_csv(out_dir / "per_animal_per_cell.csv", index=False)
    tests = pd.concat(test_parts, ignore_index=True) if test_parts else pd.DataFrame()
    tests.to_csv(out_dir / "per_cell_tests_long.csv", index=False)
    litmus = pd.concat(litmus_parts, ignore_index=True) if litmus_parts else pd.DataFrame()
    litmus.to_csv(out_dir / "per_cell_litmus_a.csv", index=False)

    cons_q = consensus_median(per, QUAD_DR_METRICS + QUAD_LEVEL, "contrast_eligible_quad")
    cons_p = consensus_median(per, PROX_DR_METRICS + PROX_LEVEL, "contrast_eligible_prox")
    cons = cons_q.merge(
        cons_p[
            ["animal_id", "contrast_eligible_prox"]
            + [c for c in PROX_DR_METRICS + PROX_LEVEL if c in cons_p.columns]
        ],
        on="animal_id",
        how="outer",
    )
    if "contrast_eligible_quad" not in cons.columns:
        cons["contrast_eligible_quad"] = False
    cons["contrast_eligible_quad"] = cons["contrast_eligible_quad"].fillna(False).astype(bool)
    if "contrast_eligible_prox" not in cons.columns:
        cons["contrast_eligible_prox"] = False
    cons["contrast_eligible_prox"] = cons["contrast_eligible_prox"].fillna(False).astype(bool)
    cons.to_csv(out_dir / "consensus_per_animal.csv", index=False)

    cq = _family_tests(
        cons,
        metrics=QUAD_DR_METRICS,
        elig_col="contrast_eligible_quad",
        family="QuadComp-peranimal-consensus-A",
        assert_size=assert_quad_family_a_size,
    )
    cp = _family_tests(
        cons,
        metrics=PROX_DR_METRICS,
        elig_col="contrast_eligible_prox",
        family="ProxComp-peranimal-consensus-A",
        assert_size=assert_prox_family_a_size,
    )
    cons_tests = pd.concat([cq, cp], ignore_index=True)
    cons_tests.to_csv(out_dir / "consensus_tests_long.csv", index=False)

    # agreement across cells
    agree_rows: list[dict[str, object]] = []
    for family, g in tests.groupby("family"):
        for model, mg in g.groupby("model"):
            agree_rows.append(
                {
                    "family": family,
                    "model": model,
                    "n_hit_fdr05": int(mg["hit_fdr05"].astype(bool).sum()),
                    "n_hit_p05": int((pd.to_numeric(mg["p"], errors="coerce") < 0.05).sum()),
                    "pass": bool(mg["hit_fdr05"].astype(bool).any()),
                }
            )
    pd.DataFrame(agree_rows).to_csv(out_dir / "cell_agreement.csv", index=False)

    compare = pd.DataFrame()
    cq_path = cluster_quad_csv or DEFAULT_CLUSTER_QUAD
    cp_path = cluster_prox_csv or DEFAULT_CLUSTER_PROX
    raw_path = cohort_raw_csv or DEFAULT_COHORT_RAW
    if cq_path.is_file() and cp_path.is_file() and raw_path.is_file() and not cons.empty:
        compare = compare_boards(
            per_animal_cons=cons,
            cluster_quad=pd.read_csv(cq_path),
            cluster_prox=pd.read_csv(cp_path),
            cohort_raw=pd.read_csv(raw_path),
        )
        compare.to_csv(out_dir / "compare_spearman_across_alphabets.csv", index=False)

    litmus_all = litmus[(litmus["sex"] == "all") & (litmus["metric"].isin(QUAD_DR_METRICS + PROX_DR_METRICS))]
    litmus_hit_rate = (
        float(litmus_all["hit_p05"].astype(bool).mean()) if not litmus_all.empty else float("nan")
    )
    summary: dict[str, object] = {
        "status": "ok",
        "alphabet": "per_animal_raw_syllable_id",
        "n_cells": len(cells),
        "n_fits": len(results_list),
        "min_frames_n": int(min_frames),
        "r_m": float(r_m),
        "n_animal_session_cell_rows": int(len(per)),
        "quad_cells_with_fdr_hit": int(
            sum(1 for r in agree_rows if r["family"] == "QuadComp-peranimal-A" and r["pass"])
        ),
        "prox_cells_with_fdr_hit": int(
            sum(1 for r in agree_rows if r["family"] == "ProxComp-peranimal-A" and r["pass"])
        ),
        "consensus_quad_n_hit_fdr05": int(cq["hit_fdr05"].astype(bool).sum()),
        "consensus_prox_n_hit_fdr05": int(cp["hit_fdr05"].astype(bool).sum()),
        "litmus_a_sex_all_hit_rate": litmus_hit_rate,
        "compare_n_rows": int(len(compare)),
        "note": (
            "exploratory; animal-local alphabets; DR within-animal OK; "
            "locked negatives remain on cluster_id boards"
        ),
        "elapsed_s": float(time.time() - t0),
    }
    if not compare.empty:
        # headline DR rhos vs cluster
        sub = compare[
            (compare["board_a"] == "per_animal_median")
            & (compare["board_b"] == "cluster")
            & (compare["metric"].isin(QUAD_DR_METRICS + PROX_DR_METRICS))
        ]
        summary["spearman_vs_cluster_dr"] = {
            str(r["metric"]): {"rho": float(r["spearman_rho"]), "n": int(r["n_animals"])}
            for _, r in sub.iterrows()
        }
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--nor-h5", type=Path, default=DEFAULT_NOR_H5)
    ap.add_argument("--per-animal-root", type=Path, default=DEFAULT_PER_ANIMAL)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--min-frames", type=int, default=MIN_FRAMES_N)
    ap.add_argument("--r-m", type=float, default=NEAR_R_M)
    ap.add_argument("--cluster-quad-csv", type=Path, default=DEFAULT_CLUSTER_QUAD)
    ap.add_argument("--cluster-prox-csv", type=Path, default=DEFAULT_CLUSTER_PROX)
    ap.add_argument("--cohort-raw-csv", type=Path, default=DEFAULT_COHORT_RAW)
    args = ap.parse_args(argv)
    run(
        args.nor_h5,
        args.per_animal_root,
        args.out_dir,
        min_frames=args.min_frames,
        r_m=args.r_m,
        cluster_quad_csv=args.cluster_quad_csv,
        cluster_prox_csv=args.cluster_prox_csv,
        cohort_raw_csv=args.cohort_raw_csv,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
