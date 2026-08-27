"""Paired between-phase contrasts holding condition_layer fixed.

Question (plain): within the same animal, does engagement or syllable composition
change from BL → TX → REC, *in the same condition* (empty / identical / novel)?

Not the presence-step design (that pairs conditions inside one phase).
Not the old phase grid (that was independent-groups tx Kruskal / PERMANOVA
inside each phase).

Association: paired / repeated (same animal, two phases).
Grain: animal × condition_layer (full session; spot bout-means).

Phase steps: BL→TX, TX→REC3hr, REC3hr→REC11hr, BL→REC11hr.
REC pairing uses animals present in both phases (~72 vs ~144 at BL/TX).

Operations: same scalar families as presence (frac_near, mean dist, COUNT,
UNCERTAINTY, descriptive BC) plus DA (Wilcoxon on Δp_k, BH within
model × condition × phase-step).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.simpler_first_da import (  # noqa: E402
    consistency_phase_pairs,
    da_tests_from_deltas,
    paired_da_deltas,
    syllable_persistence,
)
from nor_object_mi.simpler_first_presence import (  # noqa: E402
    CONDS,
    PHASES,
    TX_STRATUM_ALL,
    TX_STRATUM_CONTROL,
    _paired_delta_table,
    build_animal_condition_table,
    tests_from_dtab,
    wilcoxon_control_arm_rows,
    wilcoxon_paired,
)
from nor_object_mi.simpler_first_q1 import LOCKED, SEX_ORDER, kruskal_within_sex  # noqa: E402

NEAR_R_M = 0.10
SCALAR_METRICS = ("frac_near", "mean_dist_any_m", "richness", "shannon_bits")
PHASE_STEPS: tuple[tuple[str, str, str], ...] = (
    ("BL->TX", "NOR_BL", "NOR_TX"),
    ("TX->REC3hr", "NOR_TX", "NOR_REC3hr"),
    ("REC3hr->REC11hr", "NOR_REC3hr", "NOR_REC11hr"),
    ("BL->REC11hr", "NOR_BL", "NOR_REC11hr"),
)


def load_animal_condition_all_phases(art: Path, *, r_m: float = NEAR_R_M) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for phase, tag in PHASES:
        bout_csv = art / tag / "ladder_bout_features.csv"
        if not bout_csv.exists():
            continue
        bouts = pd.read_csv(bout_csv)
        parts.append(build_animal_condition_table(bouts, phase_layer=phase, r_m=r_m))
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


def run_model_phase_paired(
    ac: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Scalar tests + DA for one model's animal × phase × condition table."""
    if ac.empty:
        empty = pd.DataFrame()
        return empty, empty, empty, empty
    scalar_test_rows: list[dict[str, object]] = []
    scalar_delta_parts: list[pd.DataFrame] = []
    da_test_parts: list[pd.DataFrame] = []
    da_delta_parts: list[pd.DataFrame] = []

    for cond in CONDS:
        sub = ac[ac["condition_layer"] == cond]
        if sub.empty:
            continue
        for step, left, right in PHASE_STEPS:
            dtab = _paired_delta_table(
                sub,
                step=step,
                left=left,
                right=right,
                metrics=SCALAR_METRICS,
                pair_col="phase_layer",
            )
            if dtab.empty:
                continue
            dtab = dtab.copy()
            dtab["condition_layer"] = cond
            dtab["phase_step"] = step
            scalar_delta_parts.append(dtab)
            for m in SCALAR_METRICS:
                rec = wilcoxon_paired(dtab[f"delta_{m}"].to_numpy())
                scalar_test_rows.append(
                    {
                        "condition_layer": cond,
                        "phase_step": step,
                        "left": left,
                        "right": right,
                        "sex": "all",
                        "metric": m,
                        "question": "S0" if m in {"frac_near", "mean_dist_any_m"} else "S1_S2",
                        **rec,
                        "hit_p05": bool(np.isfinite(rec["p"]) and float(rec["p"]) < 0.05),
                        "tx_stratum": TX_STRATUM_ALL,
                    }
                )
            bc = dtab["braycurtis"].to_numpy(dtype=np.float64)
            bc = bc[np.isfinite(bc)]
            scalar_test_rows.append(
                {
                    "condition_layer": cond,
                    "phase_step": step,
                    "left": left,
                    "right": right,
                    "sex": "all",
                    "metric": "braycurtis_paired",
                    "question": "S1_S2_DIFFERENCE",
                    "n": int(bc.size),
                    "median_delta": float(np.median(bc)) if bc.size else float("nan"),
                    "frac_gt0": float(np.mean(bc > 0)) if bc.size else float("nan"),
                    "stat": "",
                    "p": "",
                    "test": "descriptive_median_BC",
                    "hit_p05": False,
                    "tx_stratum": TX_STRATUM_ALL,
                }
            )
            for sex in SEX_ORDER:
                sex_sub = dtab[dtab["sex"] == sex]
                for m in SCALAR_METRICS:
                    rec = wilcoxon_paired(sex_sub[f"delta_{m}"].to_numpy())
                    scalar_test_rows.append(
                        {
                            "condition_layer": cond,
                            "phase_step": step,
                            "left": left,
                            "right": right,
                            "sex": sex,
                            "metric": m,
                            "question": "S0" if m in {"frac_near", "mean_dist_any_m"} else "S1_S2",
                            **rec,
                            "hit_p05": bool(np.isfinite(rec["p"]) and float(rec["p"]) < 0.05),
                            "tx_stratum": TX_STRATUM_ALL,
                        }
                    )
            scalar_test_rows.extend(
                wilcoxon_control_arm_rows(
                    dtab,
                    SCALAR_METRICS,
                    extra={
                        "condition_layer": cond,
                        "phase_step": step,
                        "left": left,
                        "right": right,
                    },
                )
            )
            for m in SCALAR_METRICS:
                k = kruskal_within_sex(
                    pd.DataFrame(
                        {
                            "sex": dtab["sex"].to_numpy(),
                            "tx": dtab["tx"].to_numpy(),
                            m: dtab[f"delta_{m}"].to_numpy(),
                        }
                    ),
                    metric=m,
                )
                for _, r in k.iterrows():
                    scalar_test_rows.append(
                        {
                            "condition_layer": cond,
                            "phase_step": step,
                            "left": left,
                            "right": right,
                            "sex": r["sex"],
                            "metric": f"delta_{m}",
                            "question": "tx_on_paired_delta",
                            "n": r["n"],
                            "median_delta": "",
                            "frac_gt0": "",
                            "stat": r["stat"],
                            "p": r["p"],
                            "test": "kruskal",
                            "hit_p05": bool(pd.notna(r["p"]) and float(r["p"]) < 0.05),
                            "tx_stratum": TX_STRATUM_ALL,
                            "median_noSD": r["median_noSD"],
                            "median_GHSD": r["median_GHSD"],
                            "median_RBSD": r["median_RBSD"],
                        }
                    )

            da_dtab = paired_da_deltas(
                sub, step=step, left=left, right=right, pair_col="phase_layer"
            )
            if da_dtab.empty:
                continue
            da_tests = da_tests_from_deltas(da_dtab)
            da_tests.insert(0, "condition_layer", cond)
            da_tests.insert(1, "phase_step", step)
            da_tests.insert(2, "left", left)
            da_tests.insert(3, "right", right)
            da_test_parts.append(da_tests)
            da_dtab = da_dtab.copy()
            da_dtab["condition_layer"] = cond
            da_dtab["phase_step"] = step
            da_delta_parts.append(da_dtab)

    scalar_tests = pd.DataFrame(scalar_test_rows)
    scalar_deltas = (
        pd.concat(scalar_delta_parts, ignore_index=True) if scalar_delta_parts else pd.DataFrame()
    )
    da_tests = pd.concat(da_test_parts, ignore_index=True) if da_test_parts else pd.DataFrame()
    da_deltas = pd.concat(da_delta_parts, ignore_index=True) if da_delta_parts else pd.DataFrame()
    return scalar_tests, scalar_deltas, da_tests, da_deltas


def agreement_table(tests: pd.DataFrame) -> pd.DataFrame:
    """Fraction of models with hit + sign agreement (sex=all Wilcoxon)."""
    sub = tests[
        (tests["sex"].isin(("all", "all")))
        & (tests["test"] == "wilcoxon_signed_rank")
        & (~tests["metric"].astype(str).str.startswith("delta_"))
        & (tests["metric"] != "braycurtis_paired")
    ].copy()
    if "tx_stratum" in sub.columns:
        sub = sub[sub["tx_stratum"] == TX_STRATUM_ALL]
    if sub.empty:
        return pd.DataFrame()
    rows = []
    for (cond, step, metric), g in sub.groupby(
        ["condition_layer", "phase_step", "metric"], sort=True
    ):
        n = int(len(g))
        n_hit = int(g["hit_p05"].sum())
        signs = np.sign(pd.to_numeric(g["median_delta"], errors="coerce").to_numpy(dtype=float))
        signs = signs[np.isfinite(signs) & (signs != 0)]
        if signs.size:
            maj = int(np.sign(np.sum(signs)))
            n_agree_sign = int(np.sum(signs == maj))
        else:
            maj = 0
            n_agree_sign = 0
        rows.append(
            {
                "condition_layer": cond,
                "phase_step": step,
                "metric": metric,
                "n_models": n,
                "n_hit_p05": n_hit,
                "frac_hit": float(n_hit / n) if n else float("nan"),
                "median_of_median_delta": float(pd.to_numeric(g["median_delta"]).median()),
                "sign_majority": maj,
                "n_models_agree_sign": n_agree_sign,
                "frac_sign_agree": float(n_agree_sign / signs.size) if signs.size else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def agreement_table_noSD_by_sex(tests: pd.DataFrame) -> pd.DataFrame:
    """Cross-model agreement for Wilcoxon on Δ, tx=noSD, within sex."""
    sub = tests[
        (tests["sex"].isin(SEX_ORDER))
        & (tests["test"] == "wilcoxon_signed_rank")
        & (~tests["metric"].astype(str).str.startswith("delta_"))
        & (tests["metric"] != "braycurtis_paired")
    ].copy()
    if "tx_stratum" in sub.columns:
        sub = sub[sub["tx_stratum"] == TX_STRATUM_CONTROL]
    if sub.empty:
        return pd.DataFrame()
    rows = []
    for (cond, step, metric, sex), g in sub.groupby(
        ["condition_layer", "phase_step", "metric", "sex"], sort=True
    ):
        n = int(len(g))
        n_hit = int(g["hit_p05"].sum())
        signs = np.sign(pd.to_numeric(g["median_delta"], errors="coerce").to_numpy(dtype=float))
        signs = signs[np.isfinite(signs) & (signs != 0)]
        if signs.size:
            maj = int(np.sign(np.sum(signs)))
            n_agree_sign = int(np.sum(signs == maj))
        else:
            maj = 0
            n_agree_sign = 0
        rows.append(
            {
                "condition_layer": cond,
                "phase_step": step,
                "metric": metric,
                "sex": sex,
                "tx_stratum": TX_STRATUM_CONTROL,
                "n_models": n,
                "n_hit_p05": n_hit,
                "frac_hit": float(n_hit / n) if n else float("nan"),
                "median_of_median_delta": float(pd.to_numeric(g["median_delta"]).median()),
                "sign_majority": maj,
                "n_models_agree_sign": n_agree_sign,
                "frac_sign_agree": float(n_agree_sign / signs.size) if signs.size else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def _copy_dictionary(out: Path) -> None:
    tag = "phase_paired"
    src = Path(__file__).with_name(f"INFO_{tag}.md")
    if not src.exists():
        return
    text = src.read_text(encoding="utf-8")
    today = date.today().isoformat()
    text, _n = re.subn(
        r"(?m)^(\|\s*Generated\s*\|\s*)\d{4}-\d{2}-\d{2}(\s*\|)\s*$",
        rf"\g<1>{today}\2",
        text,
        count=1,
    )
    (out / f"INFO_{tag}.md").write_text(text, encoding="utf-8")
    legacy = out / "DATA_DICTIONARY.md"
    if legacy.exists():
        legacy.unlink()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    root = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017")
    ap.add_argument("--ensemble-root", type=Path, default=root)
    ap.add_argument(
        "--model",
        type=str,
        default=None,
        help="Single model; default = all paramscan_* with bout CSVs",
    )
    ap.add_argument("--r-m", type=float, default=NEAR_R_M)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument(
        "--skip-deltas",
        action="store_true",
        help="Skip per-animal scalar delta CSV",
    )
    ap.add_argument(
        "--write-da-deltas",
        action="store_true",
        help="Write per-animal × syllable DA Δp CSV (large)",
    )
    ap.add_argument(
        "--from-deltas",
        action="store_true",
        help="Rebuild scalar tests from phase_paired_deltas_per_animal.csv (no bout reload)",
    )
    args = ap.parse_args(argv)

    art_root = args.ensemble_root / "_nor_object_mi"
    out = args.out_dir or (art_root / "simpler_first_phase_paired")
    out.mkdir(parents=True, exist_ok=True)
    _copy_dictionary(out)

    if args.from_deltas:
        delta_path = out / "phase_paired_deltas_per_animal.csv"
        if not delta_path.exists():
            raise SystemExit(f"missing {delta_path}")
        print(f"rebuild scalar tests from {delta_path}", flush=True)
        d = pd.read_csv(delta_path)
        delta_cols = [c for c in d.columns if c.startswith("delta_")]
        metrics = tuple(c[len("delta_") :] for c in delta_cols)
        rows: list[dict[str, object]] = []
        for (model, cond, pstep), g in d.groupby(
            ["model", "condition_layer", "phase_step"], sort=False
        ):
            recs = tests_from_dtab(
                g,
                metrics=metrics,
                keys={
                    "condition_layer": cond,
                    "phase_step": pstep,
                    "left": g["left"].iloc[0],
                    "right": g["right"].iloc[0],
                },
            )
            for r in recs:
                r["model"] = model
            rows.extend(recs)
        tests_df = pd.DataFrame(rows)
        tests_path = out / "phase_paired_tests_long.csv"
        tests_df.to_csv(tests_path, index=False)
        agree = agreement_table(tests_df)
        agree_path = out / "phase_paired_agreement_by_model.csv"
        if not agree.empty:
            agree.to_csv(agree_path, index=False)
        agree_ctrl = agreement_table_noSD_by_sex(tests_df)
        agree_ctrl_path = out / "phase_paired_agreement_noSD_by_sex.csv"
        if not agree_ctrl.empty:
            agree_ctrl.to_csv(agree_ctrl_path, index=False)
        models = sorted(tests_df["model"].unique().tolist())
        payload = {
            "n_models": len(models),
            "models": models,
            "n_scalar_test_rows": int(len(tests_df)),
            "tests_path": str(tests_path),
            "agreement_path": str(agree_path),
            "agreement_noSD_by_sex_path": str(agree_ctrl_path),
            "hit_rule_scalars": (
                "companion: sex=all Wilcoxon on paired delta, p<0.05, txs pooled"
            ),
            "hit_rule_evolution_primary": (
                "Wilcoxon on paired delta, tx=noSD, within sex, p<0.05 (tx_stratum=noSD)"
            ),
            "rebuilt_from_deltas": str(delta_path),
        }
        (out / "run_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps({"path": str(out), "n_models": len(models), "n_scalar_test_rows": int(len(tests_df))}, indent=2))
        return 0

    if args.model:
        models = [args.model]
    else:
        models = sorted(
            p.name
            for p in art_root.glob("paramscan_*")
            if p.is_dir()
            and any((p / tag / "ladder_bout_features.csv").exists() for _, tag in PHASES)
        )

    all_scalar_tests: list[pd.DataFrame] = []
    all_scalar_deltas: list[pd.DataFrame] = []
    all_da_tests: list[pd.DataFrame] = []
    all_da_deltas: list[pd.DataFrame] = []
    n_jobs = len(models)
    for i, model in enumerate(models, start=1):
        art = art_root / model
        print(f"[{i}/{n_jobs}] {model}", flush=True)
        ac = load_animal_condition_all_phases(art, r_m=float(args.r_m))
        if ac.empty:
            print(f"  MISSING bouts for {model}", flush=True)
            continue
        scalar_tests, scalar_deltas, da_tests, da_deltas = run_model_phase_paired(ac)
        if not scalar_tests.empty:
            scalar_tests.insert(0, "model", model)
            all_scalar_tests.append(scalar_tests)
        if not args.skip_deltas and not scalar_deltas.empty:
            scalar_deltas.insert(0, "model", model)
            all_scalar_deltas.append(scalar_deltas)
        if not da_tests.empty:
            da_tests.insert(0, "model", model)
            all_da_tests.append(da_tests)
        if args.write_da_deltas and not da_deltas.empty:
            da_deltas.insert(0, "model", model)
            all_da_deltas.append(da_deltas)

    tests_df = pd.concat(all_scalar_tests, ignore_index=True) if all_scalar_tests else pd.DataFrame()
    da_df = pd.concat(all_da_tests, ignore_index=True) if all_da_tests else pd.DataFrame()
    tests_path = out / "phase_paired_tests_long.csv"
    da_path = out / "phase_paired_da_tests_long.csv"
    tests_df.to_csv(tests_path, index=False)
    da_df.to_csv(da_path, index=False)
    if all_scalar_deltas:
        pd.concat(all_scalar_deltas, ignore_index=True).to_csv(
            out / "phase_paired_deltas_per_animal.csv", index=False
        )
    if all_da_deltas:
        pd.concat(all_da_deltas, ignore_index=True).to_csv(
            out / "phase_paired_da_deltas_per_animal.csv", index=False
        )

    agree = agreement_table(tests_df)
    agree_path = out / "phase_paired_agreement_by_model.csv"
    if not agree.empty:
        agree.to_csv(agree_path, index=False)
    agree_ctrl = agreement_table_noSD_by_sex(tests_df)
    agree_ctrl_path = out / "phase_paired_agreement_noSD_by_sex.csv"
    if not agree_ctrl.empty:
        agree_ctrl.to_csv(agree_ctrl_path, index=False)

    da_pairs = consistency_phase_pairs(
        da_df, facet_col="phase_step", group_cols=("model", "condition_layer")
    )
    da_persist = syllable_persistence(
        da_df, facet_col="phase_step", group_cols=("model", "condition_layer")
    )
    da_pair_path = out / "phase_paired_da_consistency_step_pairs.csv"
    da_persist_path = out / "phase_paired_da_syllable_persistence.csv"
    if not da_pairs.empty:
        da_pairs.to_csv(da_pair_path, index=False)
    if not da_persist.empty:
        da_persist.to_csv(da_persist_path, index=False)

    payload = {
        "n_models": len(models),
        "models": models,
        "r_m": float(args.r_m),
        "conditions": list(CONDS),
        "phase_steps": [s for s, _a, _b in PHASE_STEPS],
        "n_scalar_test_rows": int(len(tests_df)),
        "n_da_test_rows": int(len(da_df)),
        "n_da_hit_fdr05": int(da_df["hit_fdr05"].sum()) if not da_df.empty else 0,
        "tests_path": str(tests_path),
        "da_tests_path": str(da_path),
        "agreement_path": str(agree_path),
        "agreement_noSD_by_sex_path": str(agree_ctrl_path),
        "hit_rule_scalars": (
            "companion: sex=all Wilcoxon on paired delta, p<0.05, txs pooled"
        ),
        "hit_rule_evolution_primary": (
            "Wilcoxon on paired delta, tx=noSD, within sex, p<0.05 (tx_stratum=noSD)"
        ),
        "hit_rule_da": (
            "sex=all Wilcoxon on paired Δp_k, BH FDR q<0.05 within model × condition × phase-step"
        ),
        "pairing": "same animal, two phases, condition_layer held fixed",
        "id_portability": "raw_syllable_id aligned within a kpMS model; not across models",
        "pilot_model_note": str(LOCKED["model"]),
        "agreement": agree.to_dict(orient="records") if not agree.empty else [],
    }
    (out / "run_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if not agree.empty:
        print("\n=== cross-model agreement (sex=all Wilcoxon, condition held) ===", flush=True)
        show = agree.copy()
        show["frac_hit"] = show["frac_hit"].map(lambda x: f"{x:.2f}")
        print(
            show[
                [
                    "condition_layer",
                    "phase_step",
                    "metric",
                    "n_hit_p05",
                    "n_models",
                    "frac_hit",
                    "median_of_median_delta",
                    "sign_majority",
                ]
            ].to_string(index=False),
            flush=True,
        )
    print(
        json.dumps(
            {
                "path": str(out),
                "n_models": len(models),
                "n_scalar_test_rows": int(len(tests_df)),
                "n_da_test_rows": int(len(da_df)),
            },
            indent=2,
        )
    )
    return 0


run_model_phase_paired = run_model_phase_paired
SCALAR_METRICS = SCALAR_METRICS
PHASE_STEPS = PHASE_STEPS
NEAR_R_M = NEAR_R_M
agreement_table = agreement_table
load_animal_condition_all_phases = load_animal_condition_all_phases


if __name__ == "__main__":
    raise SystemExit(main())
