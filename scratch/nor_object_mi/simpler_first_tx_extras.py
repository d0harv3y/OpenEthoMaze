"""Extras for the tx-on-paired-Δ lattice (items 1–4, 6, 8–10).

Scalar Stage-B Kruskal with smaller BH families, arm pairwise contrasts,
consensus-animal Kruskal, endpoint PERMANOVA by tx, and near−full grain contrast.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd
from scipy import stats

from nor_object_mi.simpler_first_da import apply_bh_grouped
from nor_object_mi.simpler_first_phase_paired import PHASE_STEPS
from nor_object_mi.simpler_first_presence import (
    CONDS,
    PHASES,
    STEPS,
    _paired_delta_table,
)
from nor_object_mi.simpler_first_q1 import SEX_ORDER, TX_ORDER, anova_within_sex, kruskal_within_sex
from nor_object_mi.simpler_first_q2 import permanova_braycurtis

# Composition / COUNT / UNCERTAINTY paired Δs (depend on grain + weighting)
COMPOSITION_METRICS = ("shannon_bits", "richness")
# Engagement: session scalars — identical across composition grain/weighting
ENGAGEMENT_METRICS = ("frac_near", "mean_dist_any_m")
# Paired DIFFERENCE magnitude (already on the paired table)
BC_METRIC = "braycurtis"

ARM_PAIRS: tuple[tuple[str, str, str], ...] = (
    ("noSD", "GHSD", "noSD_vs_GHSD"),
    ("noSD", "RBSD", "noSD_vs_RBSD"),
    ("GHSD", "RBSD", "GHSD_vs_RBSD"),
)

N_PERM_DEFAULT = 199
PERM_SEED = 42
STAGE_B_TESTS = {
    "kruskal": kruskal_within_sex,
    "anova": anova_within_sex,
}


def _stage_b_rows(
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
        for tx in TX_ORDER:
            key = f"mean_{tx}"
            if key in r.index:
                rec[key] = r[key]
        rows.append(rec)
    return rows


def _kruskal_rows(
    dtab: pd.DataFrame,
    *,
    value_col: str,
    metric_name: str,
    question: str,
) -> list[dict[str, object]]:
    """Backward-compatible alias → Stage-B Kruskal."""
    return _stage_b_rows(
        dtab,
        value_col=value_col,
        metric_name=metric_name,
        question=question,
        stage_b="kruskal",
    )


def scalar_metrics_for_cell(*, grain: str, weighting: str) -> tuple[str, ...]:
    """Which paired scalars to Kruskal in this grain×weighting cell."""
    comp = COMPOSITION_METRICS
    # Engagement is session-level; emit once to avoid duplicate identical tests.
    if grain == "full_session" and weighting == "frame_share":
        return comp + ENGAGEMENT_METRICS
    return comp


def run_condition_scalars(
    ac: pd.DataFrame,
    *,
    grain: str,
    weighting: str,
    stage_b: str = "kruskal",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Condition-axis scalar Stage-B (incl. paired BC). BH family = 3 steps / phase×sex×metric."""
    test_parts: list[pd.DataFrame] = []
    delta_parts: list[pd.DataFrame] = []
    metrics = scalar_metrics_for_cell(grain=grain, weighting=weighting)
    if ac.empty:
        return pd.DataFrame(), pd.DataFrame()
    for phase in [p for p, _ in PHASES]:
        sub = ac[ac["phase_layer"] == phase]
        if sub.empty:
            continue
        phase_rows: list[dict[str, object]] = []
        for step, left, right in STEPS:
            scal = _paired_delta_table(
                sub,
                step=step,
                left=left,
                right=right,
                metrics=metrics,
                pair_col="condition_layer",
            )
            if scal.empty:
                continue
            scal = scal.copy()
            scal["phase_layer"] = phase
            scal["grain"] = grain
            scal["weighting"] = weighting
            scal["axis"] = "condition_within_phase"
            delta_parts.append(scal)
            for m in metrics:
                for rec in _stage_b_rows(
                    scal,
                    value_col=f"delta_{m}",
                    metric_name=f"delta_{m}",
                    question=f"tx_on_condition_delta_{m}",
                    stage_b=stage_b,
                ):
                    phase_rows.append(
                        {
                            "phase_layer": phase,
                            "step": step,
                            "left": left,
                            "right": right,
                            "grain": grain,
                            "weighting": weighting,
                            "axis": "condition_within_phase",
                            **rec,
                        }
                    )
            for rec in _stage_b_rows(
                scal,
                value_col=BC_METRIC,
                metric_name=BC_METRIC,
                question="tx_on_condition_paired_BC",
                stage_b=stage_b,
            ):
                phase_rows.append(
                    {
                        "phase_layer": phase,
                        "step": step,
                        "left": left,
                        "right": right,
                        "grain": grain,
                        "weighting": weighting,
                        "axis": "condition_within_phase",
                        **rec,
                    }
                )
        if phase_rows:
            sh_df = pd.DataFrame(phase_rows)
            # Smaller family: steps within phase × sex × metric (size 3)
            sh_df = apply_bh_grouped(sh_df, ("sex", "phase_layer", "metric"))
            test_parts.append(sh_df)
    tests = pd.concat(test_parts, ignore_index=True) if test_parts else pd.DataFrame()
    deltas = pd.concat(delta_parts, ignore_index=True) if delta_parts else pd.DataFrame()
    return tests, deltas


def run_phase_scalars(
    ac: pd.DataFrame,
    *,
    grain: str,
    weighting: str,
    stage_b: str = "kruskal",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Phase-axis scalar Stage-B. BH family = 4 phase-steps / condition×sex×metric."""
    test_parts: list[pd.DataFrame] = []
    delta_parts: list[pd.DataFrame] = []
    metrics = scalar_metrics_for_cell(grain=grain, weighting=weighting)
    if ac.empty:
        return pd.DataFrame(), pd.DataFrame()
    for cond in CONDS:
        sub = ac[ac["condition_layer"] == cond]
        if sub.empty:
            continue
        cond_rows: list[dict[str, object]] = []
        for step, left, right in PHASE_STEPS:
            scal = _paired_delta_table(
                sub,
                step=step,
                left=left,
                right=right,
                metrics=metrics,
                pair_col="phase_layer",
            )
            if scal.empty:
                continue
            scal = scal.copy()
            scal["condition_layer"] = cond
            scal["phase_step"] = step
            scal["grain"] = grain
            scal["weighting"] = weighting
            scal["axis"] = "phase_within_condition"
            delta_parts.append(scal)
            for m in metrics:
                for rec in _stage_b_rows(
                    scal,
                    value_col=f"delta_{m}",
                    metric_name=f"delta_{m}",
                    question=f"tx_on_phase_delta_{m}",
                    stage_b=stage_b,
                ):
                    cond_rows.append(
                        {
                            "condition_layer": cond,
                            "phase_step": step,
                            "left": left,
                            "right": right,
                            "grain": grain,
                            "weighting": weighting,
                            "axis": "phase_within_condition",
                            **rec,
                        }
                    )
            for rec in _stage_b_rows(
                scal,
                value_col=BC_METRIC,
                metric_name=BC_METRIC,
                question="tx_on_phase_paired_BC",
                stage_b=stage_b,
            ):
                cond_rows.append(
                    {
                        "condition_layer": cond,
                        "phase_step": step,
                        "left": left,
                        "right": right,
                        "grain": grain,
                        "weighting": weighting,
                        "axis": "phase_within_condition",
                        **rec,
                    }
                )
        if cond_rows:
            sh_df = pd.DataFrame(cond_rows)
            sh_df = apply_bh_grouped(sh_df, ("sex", "condition_layer", "metric"))
            test_parts.append(sh_df)
    tests = pd.concat(test_parts, ignore_index=True) if test_parts else pd.DataFrame()
    deltas = pd.concat(delta_parts, ignore_index=True) if delta_parts else pd.DataFrame()
    return tests, deltas


def arm_pairwise_contrasts(
    deltas: pd.DataFrame,
    *,
    value_col: str,
    group_cols: Sequence[str],
    stage_b: str = "kruskal",
) -> pd.DataFrame:
    """Within-sex pairwise tx contrasts on paired Δ; BH over the 3 pairs per cell.

    Rank twin: Mann–Whitney. Mean twin (``stage_b='anova'``): Welch t-test.
    """
    need = set(group_cols) | {"sex", "tx", value_col}
    if deltas.empty or any(c not in deltas.columns for c in need):
        return pd.DataFrame()
    use_welch = stage_b == "anova"
    rows: list[dict[str, object]] = []
    keys = list(group_cols) + ["sex"]
    for gkeys, g in deltas.groupby(keys, sort=True):
        if not isinstance(gkeys, tuple):
            gkeys = (gkeys,)
        meta = dict(zip(keys, gkeys))
        by_tx = {
            tx: pd.to_numeric(g.loc[g["tx"] == tx, value_col], errors="coerce")
            .to_numpy(dtype=np.float64)
            for tx in TX_ORDER
        }
        for a, b, label in ARM_PAIRS:
            va = by_tx[a]
            vb = by_tx[b]
            va = va[np.isfinite(va)]
            vb = vb[np.isfinite(vb)]
            if va.size < 2 or vb.size < 2:
                stat_f, p_f = float("nan"), float("nan")
            elif use_welch:
                stat, p = stats.ttest_ind(va, vb, equal_var=False, alternative="two-sided")
                stat_f, p_f = float(stat), float(p)
            else:
                stat, p = stats.mannwhitneyu(va, vb, alternative="two-sided")
                stat_f, p_f = float(stat), float(p)
            rows.append(
                {
                    **meta,
                    "metric": value_col,
                    "contrast": label,
                    "tx_a": a,
                    "tx_b": b,
                    "n_a": int(va.size),
                    "n_b": int(vb.size),
                    "median_a": float(np.median(va)) if va.size else float("nan"),
                    "median_b": float(np.median(vb)) if vb.size else float("nan"),
                    "delta_median": (
                        float(np.median(va) - np.median(vb))
                        if va.size and vb.size
                        else float("nan")
                    ),
                    "mean_a": float(np.mean(va)) if va.size else float("nan"),
                    "mean_b": float(np.mean(vb)) if vb.size else float("nan"),
                    "delta_mean": (
                        float(np.mean(va) - np.mean(vb)) if va.size and vb.size else float("nan")
                    ),
                    "stat": stat_f,
                    "p": p_f,
                    "test": "welch_ttest" if use_welch else "mannwhitneyu",
                    "question": "tx_arm_contrast",
                }
            )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    # Family of 3 arm pairs within the Stage-B cell
    return apply_bh_grouped(out, list(group_cols) + ["sex", "metric"])


def consensus_animal_stage_b(
    deltas: pd.DataFrame,
    *,
    value_cols: Sequence[str],
    hold_col: str,
    step_col: str,
    axis: str,
    stage_b: str = "kruskal",
) -> pd.DataFrame:
    """Median Δ across models per animal, then one within-sex Stage-B by tx."""
    need = {"model", "animal_id", "sex", "tx", "grain", "weighting", hold_col, step_col}
    if deltas.empty or any(c not in deltas.columns for c in need):
        return pd.DataFrame()
    present = [c for c in value_cols if c in deltas.columns]
    if not present:
        return pd.DataFrame()
    keys = ["animal_id", "sex", "tx", "grain", "weighting", hold_col, step_col]
    med = deltas.groupby(keys, as_index=False)[present].median(numeric_only=True)
    n_mod = deltas.groupby(keys)["model"].nunique()
    med["n_models"] = med.set_index(keys).index.map(n_mod)
    rows: list[dict[str, object]] = []
    for (grain, weighting, hold, step), g in med.groupby(
        ["grain", "weighting", hold_col, step_col], sort=True
    ):
        for col in present:
            metric_name = col if col == BC_METRIC or col.startswith("delta_") else f"delta_{col}"
            for rec in _stage_b_rows(
                g,
                value_col=col,
                metric_name=metric_name,
                question="consensus_animal_tx_on_delta",
                stage_b=stage_b,
            ):
                rows.append(
                    {
                        "grain": grain,
                        "weighting": weighting,
                        hold_col: hold,
                        step_col: step,
                        "axis": axis,
                        "n_models": int(g["n_models"].iloc[0]) if len(g) else 0,
                        **rec,
                    }
                )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    # Same smaller families on the consensus table
    if axis == "condition_within_phase":
        return apply_bh_grouped(out, ("sex", hold_col, "metric"))
    return apply_bh_grouped(out, ("sex", hold_col, "metric"))


def consensus_animal_kruskal(
    deltas: pd.DataFrame,
    *,
    value_cols: Sequence[str],
    hold_col: str,
    step_col: str,
    axis: str,
) -> pd.DataFrame:
    """Backward-compatible alias → consensus Stage-B Kruskal."""
    return consensus_animal_stage_b(
        deltas,
        value_cols=value_cols,
        hold_col=hold_col,
        step_col=step_col,
        axis=axis,
        stage_b="kruskal",
    )


def _counts_to_matrix(
    ac: pd.DataFrame,
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """Animal meta + frame/bout-share matrix from ``counts`` dicts."""
    if ac.empty:
        return pd.DataFrame(), np.zeros((0, 0)), np.array([], dtype=np.int64)
    vocab: set[int] = set()
    maps: list[dict[int, float]] = []
    metas: list[dict[str, object]] = []
    for _, r in ac.iterrows():
        c = r["counts"]
        if not isinstance(c, dict):
            c = {}
        cm: dict[int, float] = {}
        for k, v in c.items():
            try:
                sid = int(k)
            except (TypeError, ValueError):
                continue
            fv = float(v)
            if np.isfinite(fv) and fv > 0:
                cm[sid] = fv
        if not cm:
            continue
        vocab.update(cm)
        maps.append(cm)
        metas.append(
            {
                "animal_id": str(r["animal_id"]),
                "sex": str(r["sex"]),
                "tx": str(r["tx"]),
            }
        )
    if not maps:
        return pd.DataFrame(), np.zeros((0, 0)), np.array([], dtype=np.int64)
    syll = np.array(sorted(vocab), dtype=np.int64)
    P = np.zeros((len(maps), syll.size), dtype=np.float64)
    for i, cm in enumerate(maps):
        tot = float(sum(cm.values()))
        if tot <= 0:
            continue
        for j, sid in enumerate(syll):
            P[i, j] = cm.get(int(sid), 0.0) / tot
    return pd.DataFrame(metas), P, syll


def _stable_seed(*parts: object, base: int = PERM_SEED) -> int:
    s = "|".join(str(p) for p in parts)
    acc = 0
    for ch in s:
        acc = (acc * 131 + ord(ch)) % 1_000_003
    return int(base + acc)


def permanova_endpoint_by_tx(
    ac: pd.DataFrame,
    *,
    grain: str,
    weighting: str,
    n_perm: int = N_PERM_DEFAULT,
    seed: int = PERM_SEED,
) -> pd.DataFrame:
    """PERMANOVA on endpoint compositions by tx within sex (analogy-only)."""
    rows: list[dict[str, object]] = []
    if ac.empty:
        return pd.DataFrame()
    for phase in [p for p, _ in PHASES]:
        for cond in CONDS:
            sub = ac[(ac["phase_layer"] == phase) & (ac["condition_layer"] == cond)]
            if sub.empty:
                continue
            meta, P, _syll = _counts_to_matrix(sub)
            if meta.empty or P.shape[0] < 4:
                continue
            for sex in SEX_ORDER:
                mask = meta["sex"].to_numpy() == sex
                if int(mask.sum()) < 4:
                    continue
                groups = meta.loc[mask, "tx"].to_numpy()
                rec = permanova_braycurtis(
                    P[mask],
                    groups,
                    n_perm=n_perm,
                    seed=_stable_seed(phase, cond, sex, grain, weighting, base=seed),
                )
                rows.append(
                    {
                        "phase_layer": phase,
                        "condition_layer": cond,
                        "grain": grain,
                        "weighting": weighting,
                        "sex": sex,
                        "question": "permanova_endpoint_tx",
                        "metric": "braycurtis_composition",
                        **{k: rec[k] for k in ("test", "distance", "F", "p", "n", "n_perm")},
                        **{f"n_{tx}": int(np.sum(groups == tx)) for tx in TX_ORDER},
                    }
                )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    # Smaller family analogue: conditions within phase × sex (size 3)
    return apply_bh_grouped(out, ("sex", "phase_layer", "grain", "weighting"))


def grain_contrast_scalar_deltas(
    deltas_full: pd.DataFrame,
    deltas_near: pd.DataFrame,
    *,
    value_cols: Sequence[str],
    hold_col: str,
    step_col: str,
    axis: str,
    weighting: str,
    stage_b: str = "kruskal",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """near − full on the same paired Δ, then Stage-B by tx (smaller BH families)."""
    if deltas_full.empty or deltas_near.empty:
        return pd.DataFrame(), pd.DataFrame()
    keys = ["animal_id", "sex", "tx", hold_col, step_col]
    present = [c for c in value_cols if c in deltas_full.columns and c in deltas_near.columns]
    if not present:
        return pd.DataFrame(), pd.DataFrame()
    f = deltas_full[keys + present].copy()
    n = deltas_near[keys + present].copy()
    f = f.rename(columns={c: f"{c}_full" for c in present})
    n = n.rename(columns={c: f"{c}_near" for c in present})
    m = f.merge(n, on=keys, how="inner")
    for c in present:
        m[f"grain_contrast_{c}"] = (
            pd.to_numeric(m[f"{c}_near"], errors="coerce")
            - pd.to_numeric(m[f"{c}_full"], errors="coerce")
        )
    m["grain"] = "near_minus_full"
    m["weighting"] = weighting
    m["axis"] = axis
    rows: list[dict[str, object]] = []
    for (hold, step), g in m.groupby([hold_col, step_col], sort=True):
        for c in present:
            col = f"grain_contrast_{c}"
            for rec in _stage_b_rows(
                g,
                value_col=col,
                metric_name=col,
                question="tx_on_near_minus_full_delta",
                stage_b=stage_b,
            ):
                rows.append(
                    {
                        hold_col: hold,
                        step_col: step,
                        "grain": "near_minus_full",
                        "weighting": weighting,
                        "axis": axis,
                        **rec,
                    }
                )
    tests = pd.DataFrame(rows)
    if not tests.empty:
        tests = apply_bh_grouped(tests, ("sex", hold_col, "metric"))
    return tests, m


def grain_contrast_da_deltas(
    da_full: pd.DataFrame,
    da_near: pd.DataFrame,
    *,
    hold_col: str,
    step_col: str,
    axis: str,
    weighting: str,
    stage_b: str = "kruskal",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """near − full on Δp_k, then within-sex Stage-B by tx + BH across syllables."""
    if da_full.empty or da_near.empty:
        return pd.DataFrame(), pd.DataFrame()
    keys = ["animal_id", "sex", "tx", hold_col, step_col, "raw_syllable_id"]
    for df, name in ((da_full, "full"), (da_near, "near")):
        missing = [c for c in keys + ["delta_p"] if c not in df.columns]
        if missing:
            raise ValueError(f"grain_contrast_da missing on {name}: {missing}")
    f = da_full[keys + ["delta_p"]].rename(columns={"delta_p": "delta_p_full"})
    n = da_near[keys + ["delta_p"]].rename(columns={"delta_p": "delta_p_near"})
    m = f.merge(n, on=keys, how="inner")
    m["delta_p"] = (
        pd.to_numeric(m["delta_p_near"], errors="coerce")
        - pd.to_numeric(m["delta_p_full"], errors="coerce")
    )
    m["grain"] = "near_minus_full"
    m["weighting"] = weighting
    m["axis"] = axis
    m["question"] = "tx_on_near_minus_full_delta_p"
    test_parts: list[pd.DataFrame] = []
    for (hold, step), g in m.groupby([hold_col, step_col], sort=True):
        rows: list[dict[str, object]] = []
        for sid, sg in g.groupby("raw_syllable_id", sort=True):
            for rec in _stage_b_rows(
                sg,
                value_col="delta_p",
                metric_name="delta_p_near_minus_full",
                question="tx_on_near_minus_full_delta_p",
                stage_b=stage_b,
            ):
                rows.append(
                    {
                        hold_col: hold,
                        step_col: step,
                        "grain": "near_minus_full",
                        "weighting": weighting,
                        "axis": axis,
                        "raw_syllable_id": int(sid),
                        **rec,
                    }
                )
        if rows:
            cell = apply_bh_grouped(pd.DataFrame(rows), ("sex",))
            test_parts.append(cell)
    tests = pd.concat(test_parts, ignore_index=True) if test_parts else pd.DataFrame()
    return tests, m
