"""Tx-on-paired-Δ lattice: DA + scalars + extras within sex.

Core: DA on Δp_k; scalars on ΔH / Δrichness / engagement / paired BC across
condition-steps (within phase) and phase-steps (within condition).

Extras: COUNT, paired BC, engagement, consensus-animal, arm contrasts,
bout_count weighting, endpoint PERMANOVA, near−full grain contrast.

Stage A: within-animal paired Δ. Stage B: within-sex Kruskal (default) or ANOVA by tx.
DA BH: syllables within cell. Scalar BH: smaller families (3 steps / phase or
4 phase-steps / condition), per metric.
"""

from __future__ import annotations

import argparse
import json
import math
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
    apply_bh_grouped,
    paired_da_deltas,
)
from nor_object_mi.simpler_first_phase_paired import PHASE_STEPS  # noqa: E402
from nor_object_mi.simpler_first_presence import (  # noqa: E402
    CONDS,
    GRAINS,
    NEAR_R_M,
    PHASES,
    STEPS,
    WEIGHTINGS,
    build_animal_condition_table,
)
from nor_object_mi.simpler_first_q1 import LOCKED, anova_within_sex, kruskal_within_sex  # noqa: E402
from nor_object_mi.simpler_first_tx_extras import (  # noqa: E402
    BC_METRIC,
    COMPOSITION_METRICS,
    ENGAGEMENT_METRICS,
    N_PERM_DEFAULT,
    arm_pairwise_contrasts,
    consensus_animal_stage_b,
    grain_contrast_da_deltas,
    grain_contrast_scalar_deltas,
    permanova_endpoint_by_tx,
    run_condition_scalars,
    run_phase_scalars,
)

ALPHABET_FRAC = 0.04
CONDITION_STEPS = tuple(s for s, _a, _b in STEPS)
STAGE_B_TESTS = {
    "kruskal": kruskal_within_sex,
    "anova": anova_within_sex,
}


def model_alphabet_k(model: str) -> int:
    m = re.search(r"ss-(\d+)", str(model))
    if not m:
        raise ValueError(f"cannot parse alphabet size from model name: {model!r}")
    return int(m.group(1))


def da_consensus_min_hits(k: int, *, frac: float = ALPHABET_FRAC) -> int:
    """Minimum FDR-hit syllables for a model cell to count as consensus-positive."""
    return int(math.ceil(frac * float(k) - 1e-12))


def da_cell_consensus_hit(n_hit_fdr05: int, k: int, *, frac: float = ALPHABET_FRAC) -> bool:
    if k <= 0:
        return False
    return (float(n_hit_fdr05) / float(k)) >= float(frac)


def discover_models(art_root: Path) -> list[str]:
    """Prefer live paramscan_* under art_root; fall back to archive/."""

    def _scan(root: Path) -> list[str]:
        return sorted(
            p.name
            for p in root.glob("paramscan_*")
            if p.is_dir()
            and any((p / tag / "ladder_bout_features.csv").exists() for _, tag in PHASES)
        )

    models = _scan(art_root)
    if models:
        return models
    archived = art_root / "archive"
    if archived.is_dir():
        return _scan(archived)
    return []


def model_art_dir(art_root: Path, model: str) -> Path:
    live = art_root / model
    if live.is_dir():
        return live
    return art_root / "archive" / model


def load_animal_condition_all_phases(
    art: Path,
    *,
    r_m: float = NEAR_R_M,
    grain: str = "full_session",
    weighting: str = "frame_share",
) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for phase, tag in PHASES:
        bout_csv = art / tag / "ladder_bout_features.csv"
        if not bout_csv.exists():
            continue
        bouts = pd.read_csv(bout_csv)
        parts.append(
            build_animal_condition_table(
                bouts, phase_layer=phase, r_m=r_m, grain=grain, weighting=weighting
            )
        )
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


def _stage_b_rows_from_animal_delta(
    dtab: pd.DataFrame,
    *,
    value_col: str,
    metric_name: str,
    question: str,
    stage_b: str = "kruskal",
) -> list[dict[str, object]]:
    if dtab.empty or value_col not in dtab.columns:
        return []
    if stage_b not in STAGE_B_TESTS:
        raise ValueError(f"unknown stage_b={stage_b!r}; expected one of {tuple(STAGE_B_TESTS)}")
    animals = pd.DataFrame(
        {
            "sex": dtab["sex"].to_numpy(),
            "tx": dtab["tx"].to_numpy(),
            value_col: pd.to_numeric(dtab[value_col], errors="coerce").to_numpy(dtype=np.float64),
        }
    )
    k = STAGE_B_TESTS[stage_b](animals, metric=value_col)
    rows: list[dict[str, object]] = []
    for _, r in k.iterrows():
        rec: dict[str, object] = {
            "sex": str(r["sex"]),
            "metric": metric_name,
            "question": question,
            "test": str(r["test"]),
            "stat": r["stat"],
            "p": r["p"],
            "n": r["n"],
            "n_noSD": r["n_noSD"],
            "n_GHSD": r["n_GHSD"],
            "n_RBSD": r["n_RBSD"],
            "median_noSD": r["median_noSD"],
            "median_GHSD": r["median_GHSD"],
            "median_RBSD": r["median_RBSD"],
        }
        for tx in ("noSD", "GHSD", "RBSD"):
            key = f"mean_{tx}"
            if key in r.index:
                rec[key] = r[key]
        rows.append(rec)
    return rows


def _kruskal_rows_from_animal_delta(
    dtab: pd.DataFrame,
    *,
    value_col: str,
    metric_name: str,
    question: str,
) -> list[dict[str, object]]:
    return _stage_b_rows_from_animal_delta(
        dtab,
        value_col=value_col,
        metric_name=metric_name,
        question=question,
        stage_b="kruskal",
    )


def da_tx_stage_b_from_deltas(
    dtab: pd.DataFrame, *, question: str, stage_b: str = "kruskal"
) -> pd.DataFrame:
    """Per-syllable within-sex Stage-B on delta_p (no BH yet)."""
    if dtab.empty:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for sid, g in dtab.groupby("raw_syllable_id", sort=True):
        for rec in _stage_b_rows_from_animal_delta(
            g,
            value_col="delta_p",
            metric_name="delta_p",
            question=question,
            stage_b=stage_b,
        ):
            rows.append({"raw_syllable_id": int(sid), **rec})
    return pd.DataFrame(rows)


def da_tx_kruskal_from_deltas(dtab: pd.DataFrame, *, question: str) -> pd.DataFrame:
    """Backward-compatible alias -> Stage-B Kruskal on delta_p."""
    return da_tx_stage_b_from_deltas(dtab, question=question, stage_b="kruskal")


def run_condition_da(
    ac: pd.DataFrame, *, grain: str, weighting: str, stage_b: str = "kruskal"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Q1 DA Stage-B for condition steps. Returns ``(tests, deltas)``."""
    da_parts: list[pd.DataFrame] = []
    da_delta_parts: list[pd.DataFrame] = []
    if ac.empty:
        return pd.DataFrame(), pd.DataFrame()
    for phase in [p for p, _ in PHASES]:
        sub = ac[ac["phase_layer"] == phase]
        if sub.empty:
            continue
        for step, left, right in STEPS:
            da_dtab = paired_da_deltas(
                sub, step=step, left=left, right=right, pair_col="condition_layer"
            )
            if da_dtab.empty:
                continue
            dtab = da_dtab.copy()
            dtab["phase_layer"] = phase
            dtab["grain"] = grain
            dtab["weighting"] = weighting
            dtab["axis"] = "condition_within_phase"
            dtab["question"] = "Q1_tx_on_condition_delta_p"
            da_delta_parts.append(dtab)
            da_tests = da_tx_stage_b_from_deltas(
                da_dtab, question="Q1_tx_on_condition_delta_p", stage_b=stage_b
            )
            if da_tests.empty:
                continue
            da_tests = apply_bh_grouped(da_tests, ("sex",))
            da_tests.insert(0, "phase_layer", phase)
            da_tests.insert(1, "step", step)
            da_tests.insert(2, "left", left)
            da_tests.insert(3, "right", right)
            da_tests.insert(4, "grain", grain)
            da_tests.insert(5, "weighting", weighting)
            da_tests.insert(6, "axis", "condition_within_phase")
            da_parts.append(da_tests)
    da_df = pd.concat(da_parts, ignore_index=True) if da_parts else pd.DataFrame()
    da_deltas = (
        pd.concat(da_delta_parts, ignore_index=True) if da_delta_parts else pd.DataFrame()
    )
    return da_df, da_deltas


def run_phase_da(
    ac: pd.DataFrame, *, grain: str, weighting: str, stage_b: str = "kruskal"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Q3 DA Kruskal for phase steps. Returns ``(tests, deltas)``."""
    da_parts: list[pd.DataFrame] = []
    da_delta_parts: list[pd.DataFrame] = []
    if ac.empty:
        return pd.DataFrame(), pd.DataFrame()
    for cond in CONDS:
        sub = ac[ac["condition_layer"] == cond]
        if sub.empty:
            continue
        for step, left, right in PHASE_STEPS:
            da_dtab = paired_da_deltas(
                sub, step=step, left=left, right=right, pair_col="phase_layer"
            )
            if da_dtab.empty:
                continue
            dtab = da_dtab.copy()
            dtab["condition_layer"] = cond
            dtab["phase_step"] = step
            dtab["grain"] = grain
            dtab["weighting"] = weighting
            dtab["axis"] = "phase_within_condition"
            dtab["question"] = "Q3_tx_on_phase_delta_p"
            da_delta_parts.append(dtab)
            da_tests = da_tx_stage_b_from_deltas(
                da_dtab, question="Q3_tx_on_phase_delta_p", stage_b=stage_b
            )
            if da_tests.empty:
                continue
            da_tests = apply_bh_grouped(da_tests, ("sex",))
            da_tests.insert(0, "condition_layer", cond)
            da_tests.insert(1, "phase_step", step)
            da_tests.insert(2, "left", left)
            da_tests.insert(3, "right", right)
            da_tests.insert(4, "grain", grain)
            da_tests.insert(5, "weighting", weighting)
            da_tests.insert(6, "axis", "phase_within_condition")
            da_parts.append(da_tests)
    da_df = pd.concat(da_parts, ignore_index=True) if da_parts else pd.DataFrame()
    da_deltas = (
        pd.concat(da_delta_parts, ignore_index=True) if da_delta_parts else pd.DataFrame()
    )
    return da_df, da_deltas


# Back-compat aliases used by unit tests
def run_condition_axis(ac: pd.DataFrame, *, grain: str, weighting: str = "frame_share", stage_b: str = "kruskal"):
    da, da_d = run_condition_da(ac, grain=grain, weighting=weighting, stage_b=stage_b)
    sc, sc_d = run_condition_scalars(ac, grain=grain, weighting=weighting, stage_b=stage_b)
    return da, sc, da_d, sc_d


def run_phase_axis(ac: pd.DataFrame, *, grain: str, weighting: str = "frame_share", stage_b: str = "kruskal"):
    da, da_d = run_phase_da(ac, grain=grain, weighting=weighting, stage_b=stage_b)
    sc, sc_d = run_phase_scalars(ac, grain=grain, weighting=weighting, stage_b=stage_b)
    return da, sc, da_d, sc_d


def agreement_da(
    tests: pd.DataFrame,
    *,
    hold_col: str,
    step_col: str,
) -> pd.DataFrame:
    """Cross-model consensus for DA Kruskal cells (no id matching)."""
    need = {hold_col, step_col, "grain", "sex", "model", "hit_fdr05", "raw_syllable_id"}
    if tests.empty or any(c not in tests.columns for c in need):
        return pd.DataFrame()
    group_cols = ["grain", "sex", hold_col, step_col]
    if "weighting" in tests.columns:
        group_cols = ["grain", "weighting", "sex", hold_col, step_col]
    rows: list[dict[str, object]] = []
    for keys, g in tests.groupby(group_cols, sort=True):
        if not isinstance(keys, tuple):
            keys = (keys,)
        meta = dict(zip(group_cols, keys))
        model_hits = 0
        n_models = 0
        hit_fracs: list[float] = []
        for model, mg in g.groupby("model", sort=True):
            n_models += 1
            k = model_alphabet_k(str(model))
            n_hit = int(mg["hit_fdr05"].astype(bool).sum())
            frac = float(n_hit) / float(k) if k else float("nan")
            hit_fracs.append(frac)
            if da_cell_consensus_hit(n_hit, k):
                model_hits += 1
        rows.append(
            {
                **meta,
                "n_models": n_models,
                "n_model_consensus_hit": model_hits,
                "frac_model_consensus_hit": (
                    float(model_hits / n_models) if n_models else float("nan")
                ),
                "alphabet_frac_threshold": ALPHABET_FRAC,
                "median_hit_frac_of_alphabet": float(np.nanmedian(hit_fracs)) if hit_fracs else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def agreement_shannon(
    tests: pd.DataFrame,
    *,
    hold_col: str,
    step_col: str,
) -> pd.DataFrame:
    need = {hold_col, step_col, "grain", "sex", "model", "hit_fdr05"}
    if tests.empty or any(c not in tests.columns for c in need):
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    group_cols = ["grain", "sex", hold_col, step_col]
    for keys, g in tests.groupby(group_cols, sort=True):
        if not isinstance(keys, tuple):
            keys = (keys,)
        meta = dict(zip(group_cols, keys))
        n = int(g["model"].nunique())
        # one row per model expected
        n_hit = int(g.groupby("model")["hit_fdr05"].any().sum())
        rows.append(
            {
                **meta,
                "n_models": n,
                "n_hit_fdr05": n_hit,
                "frac_hit": float(n_hit / n) if n else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def _copy_dictionary(out: Path) -> None:
    tag = "tx_on_paired_delta"
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
    # Point "These files" at the actual out folder name.
    folder = out.name
    text, _n2 = re.subn(
        r"(simpler_first_tx_on_paired_delta)(_parametric)?/",
        f"{folder}/",
        text,
        count=1,
    )
    (out / f"INFO_{tag}.md").write_text(text, encoding="utf-8")


def agreement_scalar(
    tests: pd.DataFrame,
    *,
    hold_col: str,
    step_col: str,
) -> pd.DataFrame:
    need = {hold_col, step_col, "grain", "weighting", "sex", "metric", "model", "hit_fdr05"}
    if tests.empty or any(c not in tests.columns for c in need):
        # allow missing weighting for older tables
        need.discard("weighting")
        if tests.empty or any(c not in tests.columns for c in need):
            return pd.DataFrame()
    group_cols = ["grain", "sex", hold_col, step_col, "metric"]
    if "weighting" in tests.columns:
        group_cols = ["grain", "weighting", "sex", hold_col, step_col, "metric"]
    rows: list[dict[str, object]] = []
    for keys, g in tests.groupby(group_cols, sort=True):
        if not isinstance(keys, tuple):
            keys = (keys,)
        meta = dict(zip(group_cols, keys))
        n = int(g["model"].nunique())
        n_hit = int(g.groupby("model")["hit_fdr05"].any().sum())
        rows.append(
            {
                **meta,
                "n_models": n,
                "n_hit_fdr05": n_hit,
                "frac_hit": float(n_hit / n) if n else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def _tag_model(df: pd.DataFrame, model: str, *, alphabet: bool) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out.insert(0, "model", model)
    if alphabet:
        out["alphabet_k"] = model_alphabet_k(model)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    root = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017")
    ap.add_argument("--ensemble-root", type=Path, default=root)
    ap.add_argument("--model", type=str, default=None)
    ap.add_argument("--r-m", type=float, default=NEAR_R_M)
    ap.add_argument(
        "--grain",
        choices=list(GRAINS) + ["both"],
        default="both",
    )
    ap.add_argument(
        "--weighting",
        choices=list(WEIGHTINGS) + ["both"],
        default="both",
        help="Composition representation: frame_share and/or bout_count",
    )
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--skip-deltas", action="store_true")
    ap.add_argument(
        "--stage-b",
        choices=("kruskal", "anova"),
        default="kruskal",
        help="Stage-B within-sex test: Kruskal (rank) or Welch ANOVA / Alexander-Govern (mean)",
    )
    ap.add_argument("--skip-permanova", action="store_true")
    ap.add_argument("--n-perm", type=int, default=N_PERM_DEFAULT)
    args = ap.parse_args(argv)

    art_root = args.ensemble_root / "_nor_object_mi"
    if args.out_dir is not None:
        out = args.out_dir
    elif args.stage_b == "anova":
        out = art_root / "simpler_first_tx_on_paired_delta_parametric"
    else:
        out = art_root / "simpler_first_tx_on_paired_delta"
    out.mkdir(parents=True, exist_ok=True)
    _copy_dictionary(out)

    grains = list(GRAINS) if args.grain == "both" else [args.grain]
    weightings = list(WEIGHTINGS) if args.weighting == "both" else [args.weighting]
    models = [args.model] if args.model else discover_models(art_root)
    write_deltas = not bool(args.skip_deltas)
    stage_b = str(args.stage_b)
    skip_permanova = bool(args.skip_permanova) or stage_b == "anova"

    buckets: dict[str, list[pd.DataFrame]] = {k: [] for k in (
        "da_cond", "sc_cond", "da_phase", "sc_phase",
        "da_cond_d", "sc_cond_d", "da_phase_d", "sc_phase_d",
        "perm", "gc_sc_cond", "gc_sc_phase", "gc_da_cond", "gc_da_phase",
        "gc_sc_cond_d", "gc_sc_phase_d", "gc_da_cond_d", "gc_da_phase_d",
        "arm_cond", "arm_phase",
        "cons_cond", "cons_phase",
    )}

    n_jobs = max(len(models) * len(grains) * len(weightings), 1)
    done = 0
    # Cache ac by (model, grain, weighting) for grain-contrast after both grains
    ac_cache: dict[tuple[str, str, str], pd.DataFrame] = {}
    da_d_cache: dict[tuple[str, str, str], tuple[pd.DataFrame, pd.DataFrame]] = {}
    sc_d_cache: dict[tuple[str, str, str], tuple[pd.DataFrame, pd.DataFrame]] = {}

    for model in models:
        art = model_art_dir(art_root, model)
        for weighting in weightings:
            for grain in grains:
                done += 1
                print(
                    f"[{done}/{n_jobs}] {model} grain={grain} weighting={weighting}",
                    flush=True,
                )
                ac = load_animal_condition_all_phases(
                    art, r_m=float(args.r_m), grain=grain, weighting=weighting
                )
                if ac.empty:
                    print(f"  MISSING bouts for {model}", flush=True)
                    continue
                ac_cache[(model, grain, weighting)] = ac
                da_c, da_c_d = run_condition_da(
                    ac, grain=grain, weighting=weighting, stage_b=stage_b
                )
                da_p, da_p_d = run_phase_da(
                    ac, grain=grain, weighting=weighting, stage_b=stage_b
                )
                sc_c, sc_c_d = run_condition_scalars(
                    ac, grain=grain, weighting=weighting, stage_b=stage_b
                )
                sc_p, sc_p_d = run_phase_scalars(
                    ac, grain=grain, weighting=weighting, stage_b=stage_b
                )
                da_d_cache[(model, grain, weighting)] = (da_c_d, da_p_d)
                sc_d_cache[(model, grain, weighting)] = (sc_c_d, sc_p_d)

                for df, key, alphabet in (
                    (da_c, "da_cond", True),
                    (sc_c, "sc_cond", False),
                    (da_p, "da_phase", True),
                    (sc_p, "sc_phase", False),
                ):
                    tagged = _tag_model(df, model, alphabet=alphabet)
                    if not tagged.empty:
                        buckets[key].append(tagged)
                # Always keep animal deltas in memory (arm / consensus / grain contrast).
                for df, key in (
                    (da_c_d, "da_cond_d"),
                    (sc_c_d, "sc_cond_d"),
                    (da_p_d, "da_phase_d"),
                    (sc_p_d, "sc_phase_d"),
                ):
                    tagged = _tag_model(df, model, alphabet=False)
                    if not tagged.empty:
                        buckets[key].append(tagged)

                if not skip_permanova:
                    perm = permanova_endpoint_by_tx(
                        ac, grain=grain, weighting=weighting, n_perm=int(args.n_perm)
                    )
                    tagged = _tag_model(perm, model, alphabet=False)
                    if not tagged.empty:
                        buckets["perm"].append(tagged)

            # Grain contrast once both grains exist for this weighting
            if "full_session" in grains and "near_0p10" in grains:
                key_f = (model, "full_session", weighting)
                key_n = (model, "near_0p10", weighting)
                if key_f in sc_d_cache and key_n in sc_d_cache:
                    sc_f_c, sc_f_p = sc_d_cache[key_f]
                    sc_n_c, sc_n_p = sc_d_cache[key_n]
                    value_cols = [
                        f"delta_{m}" for m in COMPOSITION_METRICS
                    ] + [BC_METRIC]
                    # engagement only on frame_share full — skip in grain contrast
                    t_c, d_c = grain_contrast_scalar_deltas(
                        sc_f_c,
                        sc_n_c,
                        value_cols=value_cols,
                        hold_col="phase_layer",
                        step_col="step",
                        axis="condition_within_phase",
                        weighting=weighting,
                        stage_b=stage_b,
                    )
                    t_p, d_p = grain_contrast_scalar_deltas(
                        sc_f_p,
                        sc_n_p,
                        value_cols=value_cols,
                        hold_col="condition_layer",
                        step_col="phase_step",
                        axis="phase_within_condition",
                        weighting=weighting,
                        stage_b=stage_b,
                    )
                    for df, key in (
                        (_tag_model(t_c, model, alphabet=False), "gc_sc_cond"),
                        (_tag_model(t_p, model, alphabet=False), "gc_sc_phase"),
                    ):
                        if not df.empty:
                            buckets[key].append(df)
                    if write_deltas:
                        for df, key in (
                            (_tag_model(d_c, model, alphabet=False), "gc_sc_cond_d"),
                            (_tag_model(d_p, model, alphabet=False), "gc_sc_phase_d"),
                        ):
                            if not df.empty:
                                buckets[key].append(df)
                if key_f in da_d_cache and key_n in da_d_cache:
                    da_f_c, da_f_p = da_d_cache[key_f]
                    da_n_c, da_n_p = da_d_cache[key_n]
                    # phase_step column: DA phase deltas use step + phase_step
                    for side, hold, step, axis, bkey, dkey in (
                        (
                            (da_f_c, da_n_c),
                            "phase_layer",
                            "step",
                            "condition_within_phase",
                            "gc_da_cond",
                            "gc_da_cond_d",
                        ),
                        (
                            (da_f_p, da_n_p),
                            "condition_layer",
                            "phase_step",
                            "phase_within_condition",
                            "gc_da_phase",
                            "gc_da_phase_d",
                        ),
                    ):
                        left_d, right_d = side
                        if "phase_step" not in left_d.columns and step == "phase_step":
                            left_d = left_d.copy()
                            right_d = right_d.copy()
                            if "step" in left_d.columns:
                                left_d["phase_step"] = left_d["step"]
                                right_d["phase_step"] = right_d["step"]
                        t, d = grain_contrast_da_deltas(
                            left_d,
                            right_d,
                            hold_col=hold,
                            step_col=step,
                            axis=axis,
                            weighting=weighting,
                        stage_b=stage_b,
                        )
                        tagged_t = _tag_model(t, model, alphabet=True)
                        if not tagged_t.empty:
                            buckets[bkey].append(tagged_t)
                        if write_deltas:
                            tagged_d = _tag_model(d, model, alphabet=False)
                            if not tagged_d.empty:
                                buckets[dkey].append(tagged_d)

    def _cat(key: str) -> pd.DataFrame:
        return pd.concat(buckets[key], ignore_index=True) if buckets[key] else pd.DataFrame()

    da_cond = _cat("da_cond")
    sc_cond = _cat("sc_cond")
    da_phase = _cat("da_phase")
    sc_phase = _cat("sc_phase")
    da_cond_d = _cat("da_cond_d")
    sc_cond_d = _cat("sc_cond_d")
    da_phase_d = _cat("da_phase_d")
    sc_phase_d = _cat("sc_phase_d")
    perm = _cat("perm")
    gc_sc_cond = _cat("gc_sc_cond")
    gc_sc_phase = _cat("gc_sc_phase")
    gc_da_cond = _cat("gc_da_cond")
    gc_da_phase = _cat("gc_da_phase")

    # Arm contrasts on scalar animal deltas (not per-syllable)
    arm_cond_parts: list[pd.DataFrame] = []
    arm_phase_parts: list[pd.DataFrame] = []
    if not sc_cond_d.empty:
        cols = [c for c in sc_cond_d.columns if c.startswith("delta_") or c == BC_METRIC]
        for col in cols:
            arm_cond_parts.append(
                arm_pairwise_contrasts(
                    sc_cond_d,
                    value_col=col,
                    group_cols=("model", "grain", "weighting", "phase_layer", "step"),
                    stage_b=stage_b,
                )
            )
    if not sc_phase_d.empty:
        cols = [c for c in sc_phase_d.columns if c.startswith("delta_") or c == BC_METRIC]
        for col in cols:
            arm_phase_parts.append(
                arm_pairwise_contrasts(
                    sc_phase_d,
                    value_col=col,
                    group_cols=("model", "grain", "weighting", "condition_layer", "phase_step"),
                    stage_b=stage_b,
                )
            )
    arm_cond = pd.concat(arm_cond_parts, ignore_index=True) if arm_cond_parts else pd.DataFrame()
    arm_phase = pd.concat(arm_phase_parts, ignore_index=True) if arm_phase_parts else pd.DataFrame()

    # Consensus animal (scalars only; ids not portable for DA)
    value_cols_c = [
        c for c in sc_cond_d.columns if c.startswith("delta_") or c == BC_METRIC
    ] if not sc_cond_d.empty else []
    value_cols_p = [
        c for c in sc_phase_d.columns if c.startswith("delta_") or c == BC_METRIC
    ] if not sc_phase_d.empty else []
    cons_cond = consensus_animal_stage_b(
        sc_cond_d,
        value_cols=value_cols_c,
        hold_col="phase_layer",
        step_col="step",
        axis="condition_within_phase",
        stage_b=stage_b,
    ) if value_cols_c else pd.DataFrame()
    cons_phase = consensus_animal_stage_b(
        sc_phase_d,
        value_cols=value_cols_p,
        hold_col="condition_layer",
        step_col="phase_step",
        axis="phase_within_condition",
        stage_b=stage_b,
    ) if value_cols_p else pd.DataFrame()

    # Shannon views for figure back-compat
    sh_cond = (
        sc_cond[sc_cond["metric"] == "delta_shannon_bits"].copy()
        if not sc_cond.empty
        else pd.DataFrame()
    )
    sh_phase = (
        sc_phase[sc_phase["metric"] == "delta_shannon_bits"].copy()
        if not sc_phase.empty
        else pd.DataFrame()
    )

    paths = {
        "da_condition": out / "tx_da_condition_tests_long.csv",
        "scalar_condition": out / "tx_scalar_condition_tests_long.csv",
        "shannon_condition": out / "tx_shannon_condition_tests_long.csv",
        "da_phase": out / "tx_da_phase_tests_long.csv",
        "scalar_phase": out / "tx_scalar_phase_tests_long.csv",
        "shannon_phase": out / "tx_shannon_phase_tests_long.csv",
        "da_condition_agree": out / "tx_da_condition_agreement.csv",
        "scalar_condition_agree": out / "tx_scalar_condition_agreement.csv",
        "shannon_condition_agree": out / "tx_shannon_condition_agreement.csv",
        "da_phase_agree": out / "tx_da_phase_agreement.csv",
        "scalar_phase_agree": out / "tx_scalar_phase_agreement.csv",
        "shannon_phase_agree": out / "tx_shannon_phase_agreement.csv",
        "da_condition_deltas": out / "tx_da_condition_deltas_per_animal.csv",
        "scalar_condition_deltas": out / "tx_scalar_condition_deltas_per_animal.csv",
        "da_phase_deltas": out / "tx_da_phase_deltas_per_animal.csv",
        "scalar_phase_deltas": out / "tx_scalar_phase_deltas_per_animal.csv",
        "permanova_endpoint": out / "tx_permanova_endpoint_tests_long.csv",
        "arm_condition": out / "tx_arm_contrasts_condition_long.csv",
        "arm_phase": out / "tx_arm_contrasts_phase_long.csv",
        "consensus_condition": out / "tx_consensus_animal_condition_tests_long.csv",
        "consensus_phase": out / "tx_consensus_animal_phase_tests_long.csv",
        "grain_contrast_scalar_condition": out / "tx_grain_contrast_scalar_condition_tests_long.csv",
        "grain_contrast_scalar_phase": out / "tx_grain_contrast_scalar_phase_tests_long.csv",
        "grain_contrast_da_condition": out / "tx_grain_contrast_da_condition_tests_long.csv",
        "grain_contrast_da_phase": out / "tx_grain_contrast_da_phase_tests_long.csv",
    }

    da_cond.to_csv(paths["da_condition"], index=False)
    sc_cond.to_csv(paths["scalar_condition"], index=False)
    sh_cond.to_csv(paths["shannon_condition"], index=False)
    da_phase.to_csv(paths["da_phase"], index=False)
    sc_phase.to_csv(paths["scalar_phase"], index=False)
    sh_phase.to_csv(paths["shannon_phase"], index=False)
    perm.to_csv(paths["permanova_endpoint"], index=False)
    arm_cond.to_csv(paths["arm_condition"], index=False)
    arm_phase.to_csv(paths["arm_phase"], index=False)
    cons_cond.to_csv(paths["consensus_condition"], index=False)
    cons_phase.to_csv(paths["consensus_phase"], index=False)
    gc_sc_cond.to_csv(paths["grain_contrast_scalar_condition"], index=False)
    gc_sc_phase.to_csv(paths["grain_contrast_scalar_phase"], index=False)
    gc_da_cond.to_csv(paths["grain_contrast_da_condition"], index=False)
    gc_da_phase.to_csv(paths["grain_contrast_da_phase"], index=False)

    if write_deltas:
        da_cond_d.to_csv(paths["da_condition_deltas"], index=False)
        sc_cond_d.to_csv(paths["scalar_condition_deltas"], index=False)
        da_phase_d.to_csv(paths["da_phase_deltas"], index=False)
        sc_phase_d.to_csv(paths["scalar_phase_deltas"], index=False)
        # drop legacy shannon-only delta names if present
        for legacy in (
            out / "tx_shannon_condition_deltas_per_animal.csv",
            out / "tx_shannon_phase_deltas_per_animal.csv",
        ):
            if legacy.exists():
                legacy.unlink()

    # Agreement: include weighting in DA group if present
    agree_da_c = agreement_da(da_cond, hold_col="phase_layer", step_col="step")
    agree_da_p = agreement_da(da_phase, hold_col="condition_layer", step_col="phase_step")
    agree_sc_c = agreement_scalar(sc_cond, hold_col="phase_layer", step_col="step")
    agree_sc_p = agreement_scalar(sc_phase, hold_col="condition_layer", step_col="phase_step")
    agree_sh_c = agreement_scalar(sh_cond, hold_col="phase_layer", step_col="step")
    agree_sh_p = agreement_scalar(sh_phase, hold_col="condition_layer", step_col="phase_step")
    for df, path in (
        (agree_da_c, paths["da_condition_agree"]),
        (agree_da_p, paths["da_phase_agree"]),
        (agree_sc_c, paths["scalar_condition_agree"]),
        (agree_sc_p, paths["scalar_phase_agree"]),
        (agree_sh_c, paths["shannon_condition_agree"]),
        (agree_sh_p, paths["shannon_phase_agree"]),
    ):
        if not df.empty:
            df.to_csv(path, index=False)

    def _n_hit(df: pd.DataFrame) -> int:
        return int(df["hit_fdr05"].sum()) if not df.empty and "hit_fdr05" in df.columns else 0

    payload = {
        "n_models": len(models),
        "models": models,
        "grains": grains,
        "weightings": weightings,
        "r_m": float(args.r_m),
        "n_perm": int(args.n_perm),
        "condition_steps": list(CONDITION_STEPS),
        "phase_steps": [s for s, _a, _b in PHASE_STEPS],
        "composition_metrics": list(COMPOSITION_METRICS),
        "engagement_metrics": list(ENGAGEMENT_METRICS),
        "bc_metric": BC_METRIC,
        "alphabet_frac_threshold": ALPHABET_FRAC,
        "scalar_bh_family_condition": "3 steps within model×grain×weighting×sex×phase×metric",
        "scalar_bh_family_phase": "4 phase-steps within model×grain×weighting×sex×condition×metric",
        "da_bh_family": "syllables within model×grain×weighting×sex×hold×step",
        "n_q1_rows": int(len(da_cond)),
        "n_scalar_condition_rows": int(len(sc_cond)),
        "n_q3_rows": int(len(da_phase)),
        "n_scalar_phase_rows": int(len(sc_phase)),
        "n_q1_hit_fdr05": _n_hit(da_cond),
        "n_scalar_condition_hit_fdr05": _n_hit(sc_cond),
        "n_q3_hit_fdr05": _n_hit(da_phase),
        "n_scalar_phase_hit_fdr05": _n_hit(sc_phase),
        "n_permanova_rows": int(len(perm)),
        "n_permanova_hit_fdr05": _n_hit(perm),
        "n_arm_condition_rows": int(len(arm_cond)),
        "n_arm_phase_rows": int(len(arm_phase)),
        "n_consensus_condition_rows": int(len(cons_cond)),
        "n_consensus_phase_rows": int(len(cons_phase)),
        "n_grain_contrast_da_condition_rows": int(len(gc_da_cond)),
        "n_grain_contrast_da_phase_rows": int(len(gc_da_phase)),
        "wrote_deltas": write_deltas,
        "n_da_condition_delta_rows": int(len(da_cond_d)),
        "n_scalar_condition_delta_rows": int(len(sc_cond_d)),
        "n_da_phase_delta_rows": int(len(da_phase_d)),
        "n_scalar_phase_delta_rows": int(len(sc_phase_d)),
        "paths": {k: str(v) for k, v in paths.items()},
        "id_portability": "raw_syllable_id within one kpMS model only; consensus is cell-level",
        "pilot_model_note": str(LOCKED["model"]),
        "near_empty_policy": (
            "n_near==0 → empty composition / NaN Shannon; animal dropped from that Δ "
            "(no min-frame floor otherwise)"
        ),
        "stage_b": stage_b,
        "extras": ["1_COUNT", "2_paired_BC", "3_engagement", "4_consensus_animal",
                   "6_arm_contrasts", "8_bout_count", "9_permanova", "10_near_minus_full"],
    }
    (out / "run_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "path": str(out),
                "n_models": len(models),
                "grains": grains,
                "weightings": weightings,
                "wrote_deltas": write_deltas,
                "n_q1_rows": int(len(da_cond)),
                "n_scalar_condition_rows": int(len(sc_cond)),
                "n_q3_rows": int(len(da_phase)),
                "n_scalar_phase_rows": int(len(sc_phase)),
                "n_permanova_rows": int(len(perm)),
                "n_arm_condition_rows": int(len(arm_cond)),
                "n_consensus_condition_rows": int(len(cons_cond)),
                "n_grain_contrast_da_condition_rows": int(len(gc_da_cond)),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
