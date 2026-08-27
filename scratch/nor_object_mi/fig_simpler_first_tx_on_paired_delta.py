"""Publication figures for tx-on-paired-delta lattice (Q1-Q4 + extras).

Cross-model consensus heatmaps + n-hit strips + pilot tx-median lollipops
+ scalar / PERMANOVA / arm / consensus-animal / grain-contrast panels.

Reads CSVs listed in INFO_tx_on_paired_delta.md.

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/fig_simpler_first_tx_on_paired_delta.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi._pub_style import (  # noqa: E402
    FIGSIZE_DOUBLE,
    INK,
    MUTE,
    PHASE_SHORT,
    PHASES,
    PILOT_MODEL,
    SEX_ORDER,
    TX_COLOR,
    TX_ORDER,
    apply_style,
    fig_footnote,
    save_pdf_png,
    text_on_cmap,
)

DEFAULT_RUN = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_tx_on_paired_delta"
)
GRAINS = ("full_session", "near_0p10")
GRAIN_LAB = {"full_session": "full session", "near_0p10": "near 0.10 m"}
CONDS = ("no_obj", "identical_obj", "novel_obj")
COND_LAB = {
    "no_obj": "no_obj",
    "identical_obj": "identical",
    "novel_obj": "novel",
}
COND_STEPS = ("no_obj->identical", "identical->novel", "no_obj->novel")
COND_STEP_LAB = {
    "no_obj->identical": "presence",
    "identical->novel": "novelty",
    "no_obj->novel": "span",
}
PHASE_STEPS = ("BL->TX", "TX->REC3hr", "REC3hr->REC11hr", "BL->REC11hr")
PHASE_STEP_LAB = {
    "BL->TX": "BL-TX",
    "TX->REC3hr": "TX-R3",
    "REC3hr->REC11hr": "R3-R11",
    "BL->REC11hr": "BL-R11",
}
MAX_LOLLIPOP = 20
SCALAR_METRICS_COND = (
    "delta_shannon_bits",
    "delta_richness",
    "delta_frac_near",
    "delta_mean_dist_any_m",
    "braycurtis",
)
SCALAR_METRIC_LAB = {
    "delta_shannon_bits": "ΔH",
    "delta_richness": "Δrich",
    "delta_frac_near": "Δfrac_near",
    "delta_mean_dist_any_m": "Δdist",
    "braycurtis": "BC",
}

# Mutated by ``_set_stage_b`` so the same fig helpers serve rank + mean runs.
STAGE_B = "kruskal"
FEET: dict[str, str] = {}


def _feet_for(stage_b: str) -> dict[str, str]:
    """Footnotes / title fragments for rank (Kruskal) vs mean (Welch ANOVA)."""
    if stage_b == "anova":
        sb3 = "Welch ANOVA (Alexander-Govern) by tx"
        arm = "Welch t-test"
        loc = "mean"
        scale = "mean-scale Stage-B (not Kruskal)"
        ag_note = (
            " AG undefined (p NaN) when any tx arm has zero within-group variance."
        )
    else:
        sb3 = "Kruskal by tx"
        arm = "Mann-Whitney"
        loc = "median"
        scale = "rank Stage-B (Kruskal)"
        ag_note = ""
    return {
        "stage_b": stage_b,
        "sb3": sb3,
        "arm": arm,
        "loc": loc,
        "scale": scale,
        "q1": (
            f"Q1: within sex, {sb3} on paired condition-step Δp_k. Primary syllable "
            "hit: BH q < 0.05 within model x grain x weighting x sex x phase x step. Model "
            "consensus: (n_hit_fdr05 / K) ≥ 0.04. Panels = frame_share unless noted. "
            f"Ids within-model only. Analogy-only DA.{ag_note}"
        ),
        "q2": (
            f"Q2: within sex, {sb3} on paired condition-step ΔH. BH family = 3 steps "
            "within phase x sex x metric. Color = frac of 21 models with hit_fdr05. frame_share."
            f"{ag_note}"
        ),
        "q3": (
            f"Q3: within sex, {sb3} on paired phase-step Δp_k. BH within cell. "
            "Consensus ≥4% alphabet. frame_share. Ids within-model only."
            f"{ag_note}"
        ),
        "q4": (
            f"Q4: within sex, {sb3} on paired phase-step ΔH. BH family = 4 phase-steps "
            "within condition x sex x metric. frame_share."
            f"{ag_note}"
        ),
        "scalar": (
            f"Scalar {scale}: {sb3} within sex. Color = frac of 21 models with "
            "hit_fdr05 (smaller BH families). frame_share. Engagement metrics only exist "
            "on full_session x frame_share."
            f"{ag_note}"
        ),
        "perm": (
            "Endpoint PERMANOVA on syllable compositions by tx within sex (Bray-Curtis; "
            "analogy-only). Color = frac of 21 models with hit_fdr05. BH family = 3 conditions "
            "within phase x sex x grain x weighting. Skipped on mean-scale (anova) runs."
        ),
        "arm_foot": (
            f"Arm contrasts: {arm} on paired delta within sex; BH over the 3 tx pairs. "
            "Color = frac of 21 models with hit_fdr05 for that contrast. frame_share."
        ),
        "cons": (
            f"Consensus animal: median delta across models per animal, then one {sb3}. "
            "Color = hit_fdr05 (1/0). Smaller BH families. frame_share."
            f"{ag_note}"
        ),
        "gc": (
            f"Grain contrast: near − full on the same paired delta, then {sb3}. "
            "DA panel uses ≥4% alphabet consensus; scalar panel uses frac hit_fdr05."
            f"{ag_note}"
        ),
        "n_hit": (
            "Per-model count of syllable FDR hits (hit_fdr05) for one grain x frame_share. "
            "Median tick across 21 models. Not the ≥4% alphabet consensus rule."
            f"{ag_note}"
        ),
        "lolli": (
            f"Pilot model only. FDR-hit syllables for one cell; dots are within-sex {loc} "
            "Δp by tx (noSD / GHSD / RBSD). Ids not portable across models. frame_share."
        ),
        "scalar_title_cond": f"Scalars | condition-step tx {sb3} (full session, frame_share)",
        "scalar_title_phase": f"Scalars | phase-step tx {sb3} (full session, frame_share)",
    }


def _set_stage_b(stage_b: str) -> None:
    global STAGE_B, FEET
    if stage_b not in ("kruskal", "anova"):
        raise ValueError(f"unknown stage_b={stage_b!r}")
    STAGE_B = stage_b
    FEET = _feet_for(stage_b)


def _infer_stage_b(run: Path, tests: pd.DataFrame) -> str:
    """Prefer run_summary.json, then test column, then folder name."""
    summary = run / "run_summary.json"
    if summary.exists():
        try:
            payload = json.loads(summary.read_text(encoding="utf-8"))
            sb = str(payload.get("stage_b", "")).lower()
            if sb in ("kruskal", "anova"):
                return sb
        except (OSError, ValueError, TypeError):
            pass
    if not tests.empty and "test" in tests.columns:
        vals = set(tests["test"].astype(str).str.lower().unique())
        if vals & {"welch_anova", "anova"}:
            return "anova"
        if vals & {"kruskal"}:
            return "kruskal"
    name = run.name.lower()
    if "parametric" in name or "anova" in name or "welch" in name:
        return "anova"
    return "kruskal"


_set_stage_b("kruskal")


def _as_bool(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s
    return s.astype(str).str.lower().isin(("true", "1"))


def _read_csv_maybe(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _frame_share(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "weighting" not in df.columns:
        return df
    return df[df["weighting"] == "frame_share"].copy()


def _annotate(ax, mat: np.ndarray, *, fmt: str = "{:.2f}", fontsize: float = 6.5) -> None:
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            v = mat[i, j]
            if np.isfinite(v):
                ax.text(
                    j,
                    i,
                    fmt.format(v),
                    ha="center",
                    va="center",
                    fontsize=fontsize,
                    color=text_on_cmap(v),
                )


def _sex_lab(sex: str) -> str:
    return "female" if sex == "F" else "male"


def _pick_row(sub: pd.DataFrame, **filters: object) -> pd.Series | None:
    m = sub
    for k, v in filters.items():
        if k not in m.columns:
            return None
        m = m[m[k] == v]
    if len(m) >= 1:
        return m.iloc[0]
    return None


def fig_q1_agreement(agr: pd.DataFrame, out: Path) -> None:
    apply_style()
    agr = _frame_share(agr)
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 6.6), constrained_layout=True)
    im = None
    for r, grain in enumerate(GRAINS):
        for c, sex in enumerate(SEX_ORDER):
            ax = axes[r, c]
            sub = agr[(agr["grain"] == grain) & (agr["sex"] == sex)]
            mat = np.full((len(PHASES), len(COND_STEPS)), np.nan)
            for i, ph in enumerate(PHASES):
                for j, st in enumerate(COND_STEPS):
                    row = _pick_row(sub, phase_layer=ph, step=st)
                    if row is not None:
                        mat[i, j] = float(row["frac_model_consensus_hit"])
            im = ax.imshow(mat, cmap="viridis", vmin=0.0, vmax=1.0, aspect="auto")
            ax.set_xticks(range(len(COND_STEPS)))
            ax.set_xticklabels(
                [COND_STEP_LAB[s] for s in COND_STEPS], rotation=30, ha="right", fontsize=7
            )
            ax.set_yticks(range(len(PHASES)))
            ax.set_yticklabels([PHASE_SHORT[p] for p in PHASES])
            ax.set_title(
                f"{GRAIN_LAB[grain]}  ·  {_sex_lab(sex)}",
                loc="left",
                fontweight="bold",
                color=INK,
                fontsize=8,
            )
            _annotate(ax, mat, fontsize=6)
    fig.colorbar(
        im,
        ax=axes,
        fraction=0.025,
        pad=0.02,
        label="frac models with ≥4% alphabet FDR-hit",
    )
    fig.suptitle(
        "Q1 · Does tx modulate condition-step syllable shares? (frame_share)",
        fontsize=11,
        fontweight="bold",
        color=INK,
        y=1.02,
    )
    fig_footnote(fig, FEET['q1'], y=-0.05)
    save_pdf_png(fig, out / "fig_tx_q1_da_condition_agreement")


def fig_q2_agreement(agr: pd.DataFrame, out: Path) -> None:
    apply_style()
    agr = _frame_share(agr)
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 6.6), constrained_layout=True)
    im = None
    for r, grain in enumerate(GRAINS):
        for c, sex in enumerate(SEX_ORDER):
            ax = axes[r, c]
            sub = agr[(agr["grain"] == grain) & (agr["sex"] == sex)]
            mat = np.full((len(PHASES), len(COND_STEPS)), np.nan)
            for i, ph in enumerate(PHASES):
                for j, st in enumerate(COND_STEPS):
                    row = _pick_row(sub, phase_layer=ph, step=st)
                    if row is not None:
                        mat[i, j] = float(row["frac_hit"])
            im = ax.imshow(mat, cmap="viridis", vmin=0.0, vmax=1.0, aspect="auto")
            ax.set_xticks(range(len(COND_STEPS)))
            ax.set_xticklabels(
                [COND_STEP_LAB[s] for s in COND_STEPS], rotation=30, ha="right", fontsize=7
            )
            ax.set_yticks(range(len(PHASES)))
            ax.set_yticklabels([PHASE_SHORT[p] for p in PHASES])
            ax.set_title(
                f"{GRAIN_LAB[grain]}  ·  {_sex_lab(sex)}",
                loc="left",
                fontweight="bold",
                color=INK,
                fontsize=8,
            )
            _annotate(ax, mat, fontsize=6)
    fig.colorbar(im, ax=axes, fraction=0.025, pad=0.02, label="frac models with Shannon FDR hit")
    fig.suptitle(
        "Q2 · Does tx modulate condition-step Shannon ΔH? (frame_share)",
        fontsize=11,
        fontweight="bold",
        color=INK,
        y=1.02,
    )
    fig_footnote(fig, FEET['q2'], y=-0.05)
    save_pdf_png(fig, out / "fig_tx_q2_shannon_condition_agreement")


def fig_q3_agreement(agr: pd.DataFrame, out: Path) -> None:
    apply_style()
    agr = _frame_share(agr)
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 6.6), constrained_layout=True)
    im = None
    for r, grain in enumerate(GRAINS):
        for c, sex in enumerate(SEX_ORDER):
            ax = axes[r, c]
            sub = agr[(agr["grain"] == grain) & (agr["sex"] == sex)]
            mat = np.full((len(CONDS), len(PHASE_STEPS)), np.nan)
            for i, cond in enumerate(CONDS):
                for j, st in enumerate(PHASE_STEPS):
                    row = _pick_row(sub, condition_layer=cond, phase_step=st)
                    if row is not None:
                        mat[i, j] = float(row["frac_model_consensus_hit"])
            im = ax.imshow(mat, cmap="viridis", vmin=0.0, vmax=1.0, aspect="auto")
            ax.set_xticks(range(len(PHASE_STEPS)))
            ax.set_xticklabels(
                [PHASE_STEP_LAB[s] for s in PHASE_STEPS], rotation=30, ha="right", fontsize=7
            )
            ax.set_yticks(range(len(CONDS)))
            ax.set_yticklabels([COND_LAB[x] for x in CONDS])
            ax.set_title(
                f"{GRAIN_LAB[grain]}  ·  {_sex_lab(sex)}",
                loc="left",
                fontweight="bold",
                color=INK,
                fontsize=8,
            )
            _annotate(ax, mat, fontsize=6)
    fig.colorbar(
        im,
        ax=axes,
        fraction=0.025,
        pad=0.02,
        label="frac models with ≥4% alphabet FDR-hit",
    )
    fig.suptitle(
        "Q3 · Does tx modulate phase-step syllable shares? (frame_share)",
        fontsize=11,
        fontweight="bold",
        color=INK,
        y=1.02,
    )
    fig_footnote(fig, FEET['q3'], y=-0.05)
    save_pdf_png(fig, out / "fig_tx_q3_da_phase_agreement")


def fig_q4_agreement(agr: pd.DataFrame, out: Path) -> None:
    apply_style()
    agr = _frame_share(agr)
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 6.6), constrained_layout=True)
    im = None
    for r, grain in enumerate(GRAINS):
        for c, sex in enumerate(SEX_ORDER):
            ax = axes[r, c]
            sub = agr[(agr["grain"] == grain) & (agr["sex"] == sex)]
            mat = np.full((len(CONDS), len(PHASE_STEPS)), np.nan)
            for i, cond in enumerate(CONDS):
                for j, st in enumerate(PHASE_STEPS):
                    row = _pick_row(sub, condition_layer=cond, phase_step=st)
                    if row is not None:
                        mat[i, j] = float(row["frac_hit"])
            im = ax.imshow(mat, cmap="viridis", vmin=0.0, vmax=1.0, aspect="auto")
            ax.set_xticks(range(len(PHASE_STEPS)))
            ax.set_xticklabels(
                [PHASE_STEP_LAB[s] for s in PHASE_STEPS], rotation=30, ha="right", fontsize=7
            )
            ax.set_yticks(range(len(CONDS)))
            ax.set_yticklabels([COND_LAB[x] for x in CONDS])
            ax.set_title(
                f"{GRAIN_LAB[grain]}  ·  {_sex_lab(sex)}",
                loc="left",
                fontweight="bold",
                color=INK,
                fontsize=8,
            )
            _annotate(ax, mat, fontsize=6)
    fig.colorbar(im, ax=axes, fraction=0.025, pad=0.02, label="frac models with Shannon FDR hit")
    fig.suptitle(
        "Q4 · Does tx modulate phase-step Shannon ΔH? (frame_share)",
        fontsize=11,
        fontweight="bold",
        color=INK,
        y=1.02,
    )
    fig_footnote(fig, FEET['q4'], y=-0.05)
    save_pdf_png(fig, out / "fig_tx_q4_shannon_phase_agreement")


def fig_q1_n_hit(tests: pd.DataFrame, out: Path, *, grain: str) -> None:
    apply_style()
    t = _frame_share(tests)
    t = t[t["grain"] == grain].copy()
    t["hit"] = _as_bool(t["hit_fdr05"])
    counts = t.groupby(["model", "phase_layer", "step", "sex"], as_index=False)["hit"].sum()
    rng = np.random.default_rng(0)
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 5.8), sharey=True, constrained_layout=True)
    x = np.arange(len(PHASES))
    for r, sex in enumerate(SEX_ORDER):
        for c, st in enumerate(COND_STEPS):
            ax = axes[r, c]
            ax.set_title(
                f"{COND_STEP_LAB[st]}  ·  {_sex_lab(sex)}",
                loc="left",
                fontweight="bold",
                color=INK,
                fontsize=8,
            )
            for i, ph in enumerate(PHASES):
                ys = counts[
                    (counts["step"] == st)
                    & (counts["phase_layer"] == ph)
                    & (counts["sex"] == sex)
                ]["hit"].to_numpy(dtype=float)
                jitter = rng.normal(0, 0.08, size=ys.size)
                ax.scatter(
                    np.full(ys.shape, i) + jitter,
                    ys,
                    s=11,
                    c="#2f5d8a",
                    alpha=0.75,
                    edgecolors="none",
                )
                if ys.size:
                    ax.plot(
                        [i - 0.22, i + 0.22],
                        [np.median(ys)] * 2,
                        color=INK,
                        lw=1.6,
                        zorder=3,
                    )
            ax.set_xticks(x)
            ax.set_xticklabels([PHASE_SHORT[p] for p in PHASES], fontsize=7)
            ax.axhline(0.0, color="#bbbbbb", lw=0.6, ls="--", zorder=0)
            if c == 0:
                ax.set_ylabel("n FDR-hit syllables / model")
    fig.suptitle(
        f"Q1 · n FDR-hit syllables per model ({GRAIN_LAB[grain]}, frame_share)",
        fontsize=11,
        fontweight="bold",
        color=INK,
        y=1.03,
    )
    fig_footnote(fig, FEET['n_hit'] + f" Grain = {grain}.", y=-0.06)
    save_pdf_png(fig, out / f"fig_tx_q1_n_hit_fdr05_{grain}")


def fig_q3_n_hit(tests: pd.DataFrame, out: Path, *, grain: str) -> None:
    apply_style()
    t = _frame_share(tests)
    t = t[t["grain"] == grain].copy()
    t["hit"] = _as_bool(t["hit_fdr05"])
    counts = t.groupby(["model", "condition_layer", "phase_step", "sex"], as_index=False)["hit"].sum()
    rng = np.random.default_rng(0)
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 5.8), sharey=True, constrained_layout=True)
    x = np.arange(len(PHASE_STEPS))
    for r, sex in enumerate(SEX_ORDER):
        for c, cond in enumerate(CONDS):
            ax = axes[r, c]
            ax.set_title(
                f"{COND_LAB[cond]}  ·  {_sex_lab(sex)}",
                loc="left",
                fontweight="bold",
                color=INK,
                fontsize=8,
            )
            for i, st in enumerate(PHASE_STEPS):
                ys = counts[
                    (counts["condition_layer"] == cond)
                    & (counts["phase_step"] == st)
                    & (counts["sex"] == sex)
                ]["hit"].to_numpy(dtype=float)
                jitter = rng.normal(0, 0.08, size=ys.size)
                ax.scatter(
                    np.full(ys.shape, i) + jitter,
                    ys,
                    s=11,
                    c="#2f5d8a",
                    alpha=0.75,
                    edgecolors="none",
                )
                if ys.size:
                    ax.plot(
                        [i - 0.22, i + 0.22],
                        [np.median(ys)] * 2,
                        color=INK,
                        lw=1.6,
                        zorder=3,
                    )
            ax.set_xticks(x)
            ax.set_xticklabels(
                [PHASE_STEP_LAB[s] for s in PHASE_STEPS], fontsize=6.5, rotation=25, ha="right"
            )
            ax.axhline(0.0, color="#bbbbbb", lw=0.6, ls="--", zorder=0)
            if c == 0:
                ax.set_ylabel("n FDR-hit syllables / model")
    fig.suptitle(
        f"Q3 · n FDR-hit syllables per model ({GRAIN_LAB[grain]}, frame_share)",
        fontsize=11,
        fontweight="bold",
        color=INK,
        y=1.03,
    )
    fig_footnote(fig, FEET['n_hit'] + f" Grain = {grain}.", y=-0.06)
    save_pdf_png(fig, out / f"fig_tx_q3_n_hit_fdr05_{grain}")


def _pick_pilot_cell(agr: pd.DataFrame) -> dict[str, str]:
    """Strongest Q1 consensus cell for the pilot lollipop (frame_share)."""
    agr = _frame_share(agr)
    if agr.empty:
        return {
            "grain": "near_0p10",
            "sex": "M",
            "phase_layer": "NOR_BL",
            "step": "identical->novel",
            "weighting": "frame_share",
        }
    top = agr.sort_values("frac_model_consensus_hit", ascending=False).iloc[0]
    return {
        "grain": str(top["grain"]),
        "sex": str(top["sex"]),
        "phase_layer": str(top["phase_layer"]),
        "step": str(top["step"]),
        "weighting": str(top["weighting"]) if "weighting" in top.index else "frame_share",
    }


def fig_q1_lollipop_pilot(
    tests: pd.DataFrame,
    out: Path,
    *,
    model: str,
    cell: dict[str, str],
) -> None:
    apply_style()
    t = tests[
        (tests["model"] == model)
        & (tests["grain"] == cell["grain"])
        & (tests["sex"] == cell["sex"])
        & (tests["phase_layer"] == cell["phase_layer"])
        & (tests["step"] == cell["step"])
    ].copy()
    if "weighting" in t.columns:
        t = t[t["weighting"] == cell.get("weighting", "frame_share")]
    t["hit"] = _as_bool(t["hit_fdr05"])
    hits = t[t["hit"]].copy()
    loc = FEET.get("loc", "median")
    pref = f"{loc}_"
    # Fall back to medians if mean columns absent (older Kruskal-only tables).
    if loc == "mean" and not all(f"mean_{tx}" in hits.columns for tx in TX_ORDER):
        loc, pref = "median", "median_"
    loc_cols = [f"{pref}{tx}" for tx in TX_ORDER]
    fig, ax = plt.subplots(figsize=FIGSIZE_DOUBLE, constrained_layout=True)
    if hits.empty:
        ax.text(0.5, 0.5, "0 FDR hits in this pilot cell", ha="center", va="center", color=MUTE)
        ax.set_axis_off()
    else:
        hits = hits.assign(
            spread=hits[loc_cols].astype(float).max(axis=1) - hits[loc_cols].astype(float).min(axis=1)
        )
        shown = hits.sort_values("spread", ascending=False).head(MAX_LOLLIPOP)
        shown = shown.sort_values(loc_cols[0])
        y = np.arange(len(shown))
        ax.axvline(0.0, color="#bbbbbb", lw=0.7, ls="--", zorder=0)
        for tx in TX_ORDER:
            col = f"{pref}{tx}"
            d = pd.to_numeric(shown[col], errors="coerce").to_numpy(dtype=float)
            ax.scatter(
                d, y, s=28, c=TX_COLOR[tx], label=tx, zorder=3, edgecolors="white", linewidths=0.4
            )
        for i, (_, row) in enumerate(shown.iterrows()):
            xs = [float(row[f"{pref}{tx}"]) for tx in TX_ORDER]
            ax.plot([min(xs), max(xs)], [i, i], color="#b0b0b0", lw=0.8, zorder=1)
        ax.set_yticks(y)
        ax.set_yticklabels([str(int(i)) for i in shown["raw_syllable_id"]], fontsize=7)
        ax.set_xlabel(f"within-sex {loc} Δp by tx")
        ax.set_ylabel("raw_syllable_id")
        ax.legend(frameon=False, fontsize=8, loc="lower right")
        extra = len(hits) - len(shown)
        note = f"n_hit={len(hits)}" + (f"  top {len(shown)} by tx-spread" if extra > 0 else "")
        ax.text(0.02, 0.98, note, transform=ax.transAxes, va="top", fontsize=7, color=MUTE)
    title_cell = (
        f"{GRAIN_LAB[cell['grain']]} · {_sex_lab(cell['sex'])} · "
        f"{PHASE_SHORT[cell['phase_layer']]} · {COND_STEP_LAB[cell['step']]}"
    )
    fig.suptitle(
        f"Q1 pilot {model}: FDR-hit syllables · {title_cell}",
        fontsize=10,
        fontweight="bold",
        color=INK,
        y=1.02,
    )
    fig_footnote(fig, FEET['lolli'], y=-0.08)
    save_pdf_png(fig, out / "fig_tx_q1_lollipop_pilot")


def fig_scalar_condition_agreement(agr: pd.DataFrame, out: Path) -> None:
    apply_style()
    agr = _frame_share(agr)
    agr = agr[agr["grain"] == "full_session"]
    metrics = [m for m in SCALAR_METRICS_COND if m in set(agr["metric"].astype(str))]
    if not metrics:
        return
    fig, axes = plt.subplots(
        len(metrics), 2, figsize=(7.2, 1.7 * len(metrics) + 0.8), constrained_layout=True
    )
    if len(metrics) == 1:
        axes = np.array([axes])
    im = None
    for r, met in enumerate(metrics):
        for c, sex in enumerate(SEX_ORDER):
            ax = axes[r, c]
            sub = agr[(agr["metric"] == met) & (agr["sex"] == sex)]
            mat = np.full((len(PHASES), len(COND_STEPS)), np.nan)
            for i, ph in enumerate(PHASES):
                for j, st in enumerate(COND_STEPS):
                    row = _pick_row(sub, phase_layer=ph, step=st)
                    if row is not None:
                        mat[i, j] = float(row["frac_hit"])
            im = ax.imshow(mat, cmap="viridis", vmin=0.0, vmax=1.0, aspect="auto")
            ax.set_xticks(range(len(COND_STEPS)))
            ax.set_xticklabels(
                [COND_STEP_LAB[s] for s in COND_STEPS], rotation=30, ha="right", fontsize=6
            )
            ax.set_yticks(range(len(PHASES)))
            ax.set_yticklabels([PHASE_SHORT[p] for p in PHASES], fontsize=6)
            ax.set_title(
                f"{SCALAR_METRIC_LAB.get(met, met)}  ·  {_sex_lab(sex)}",
                loc="left",
                fontweight="bold",
                color=INK,
                fontsize=8,
            )
            _annotate(ax, mat, fontsize=5.5)
    fig.colorbar(im, ax=axes, fraction=0.02, pad=0.02, label="frac models hit_fdr05")
    fig.suptitle(
        FEET['scalar_title_cond'],
        fontsize=11,
        fontweight="bold",
        color=INK,
        y=1.01,
    )
    fig_footnote(fig, FEET['scalar'], y=-0.02)
    save_pdf_png(fig, out / "fig_tx_scalar_condition_agreement")


def fig_scalar_phase_agreement(agr: pd.DataFrame, out: Path) -> None:
    apply_style()
    agr = _frame_share(agr)
    agr = agr[agr["grain"] == "full_session"]
    metrics = [m for m in SCALAR_METRICS_COND if m in set(agr["metric"].astype(str))]
    if not metrics:
        return
    fig, axes = plt.subplots(
        len(metrics), 2, figsize=(7.2, 1.7 * len(metrics) + 0.8), constrained_layout=True
    )
    if len(metrics) == 1:
        axes = np.array([axes])
    im = None
    for r, met in enumerate(metrics):
        for c, sex in enumerate(SEX_ORDER):
            ax = axes[r, c]
            sub = agr[(agr["metric"] == met) & (agr["sex"] == sex)]
            mat = np.full((len(CONDS), len(PHASE_STEPS)), np.nan)
            for i, cond in enumerate(CONDS):
                for j, st in enumerate(PHASE_STEPS):
                    row = _pick_row(sub, condition_layer=cond, phase_step=st)
                    if row is not None:
                        mat[i, j] = float(row["frac_hit"])
            im = ax.imshow(mat, cmap="viridis", vmin=0.0, vmax=1.0, aspect="auto")
            ax.set_xticks(range(len(PHASE_STEPS)))
            ax.set_xticklabels(
                [PHASE_STEP_LAB[s] for s in PHASE_STEPS], rotation=30, ha="right", fontsize=6
            )
            ax.set_yticks(range(len(CONDS)))
            ax.set_yticklabels([COND_LAB[x] for x in CONDS], fontsize=6)
            ax.set_title(
                f"{SCALAR_METRIC_LAB.get(met, met)}  ·  {_sex_lab(sex)}",
                loc="left",
                fontweight="bold",
                color=INK,
                fontsize=8,
            )
            _annotate(ax, mat, fontsize=5.5)
    fig.colorbar(im, ax=axes, fraction=0.02, pad=0.02, label="frac models hit_fdr05")
    fig.suptitle(
        FEET['scalar_title_phase'],
        fontsize=11,
        fontweight="bold",
        color=INK,
        y=1.01,
    )
    fig_footnote(fig, FEET['scalar'], y=-0.02)
    save_pdf_png(fig, out / "fig_tx_scalar_phase_agreement")


def fig_da_bout_count_agreement(agr: pd.DataFrame, out: Path) -> None:
    apply_style()
    if agr.empty or "weighting" not in agr.columns:
        return
    agr = agr[agr["weighting"] == "bout_count"].copy()
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 6.6), constrained_layout=True)
    im = None
    for r, grain in enumerate(GRAINS):
        for c, sex in enumerate(SEX_ORDER):
            ax = axes[r, c]
            sub = agr[(agr["grain"] == grain) & (agr["sex"] == sex)]
            mat = np.full((len(PHASES), len(COND_STEPS)), np.nan)
            for i, ph in enumerate(PHASES):
                for j, st in enumerate(COND_STEPS):
                    row = _pick_row(sub, phase_layer=ph, step=st)
                    if row is not None:
                        mat[i, j] = float(row["frac_model_consensus_hit"])
            im = ax.imshow(mat, cmap="viridis", vmin=0.0, vmax=1.0, aspect="auto")
            ax.set_xticks(range(len(COND_STEPS)))
            ax.set_xticklabels(
                [COND_STEP_LAB[s] for s in COND_STEPS], rotation=30, ha="right", fontsize=7
            )
            ax.set_yticks(range(len(PHASES)))
            ax.set_yticklabels([PHASE_SHORT[p] for p in PHASES])
            ax.set_title(
                f"{GRAIN_LAB[grain]}  ·  {_sex_lab(sex)}",
                loc="left",
                fontweight="bold",
                color=INK,
                fontsize=8,
            )
            _annotate(ax, mat, fontsize=6)
    fig.colorbar(
        im, ax=axes, fraction=0.025, pad=0.02, label="frac models with ≥4% alphabet FDR-hit"
    )
    fig.suptitle(
        "Q1 · DA condition-step consensus (bout_count weighting)",
        fontsize=11,
        fontweight="bold",
        color=INK,
        y=1.02,
    )
    fig_footnote(fig, FEET['q1'] + " This figure is bout_count, not frame_share.", y=-0.05)
    save_pdf_png(fig, out / "fig_tx_q1_da_condition_agreement_bout_count")


def fig_permanova_agreement(tests: pd.DataFrame, out: Path) -> None:
    apply_style()
    t = _frame_share(tests)
    if t.empty:
        return
    t = t.copy()
    t["hit"] = _as_bool(t["hit_fdr05"])
    agr = (
        t.groupby(["grain", "sex", "phase_layer", "condition_layer"], as_index=False)["hit"]
        .mean()
        .rename(columns={"hit": "frac_hit"})
    )
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 6.6), constrained_layout=True)
    im = None
    for r, grain in enumerate(GRAINS):
        for c, sex in enumerate(SEX_ORDER):
            ax = axes[r, c]
            sub = agr[(agr["grain"] == grain) & (agr["sex"] == sex)]
            mat = np.full((len(PHASES), len(CONDS)), np.nan)
            for i, ph in enumerate(PHASES):
                for j, cond in enumerate(CONDS):
                    row = _pick_row(sub, phase_layer=ph, condition_layer=cond)
                    if row is not None:
                        mat[i, j] = float(row["frac_hit"])
            im = ax.imshow(mat, cmap="viridis", vmin=0.0, vmax=1.0, aspect="auto")
            ax.set_xticks(range(len(CONDS)))
            ax.set_xticklabels([COND_LAB[x] for x in CONDS], rotation=30, ha="right", fontsize=7)
            ax.set_yticks(range(len(PHASES)))
            ax.set_yticklabels([PHASE_SHORT[p] for p in PHASES])
            ax.set_title(
                f"{GRAIN_LAB[grain]}  ·  {_sex_lab(sex)}",
                loc="left",
                fontweight="bold",
                color=INK,
                fontsize=8,
            )
            _annotate(ax, mat, fontsize=6)
    fig.colorbar(im, ax=axes, fraction=0.025, pad=0.02, label="frac models PERMANOVA FDR hit")
    fig.suptitle(
        "PERMANOVA · endpoint composition by tx (frame_share)",
        fontsize=11,
        fontweight="bold",
        color=INK,
        y=1.02,
    )
    fig_footnote(fig, FEET['perm'], y=-0.05)
    save_pdf_png(fig, out / "fig_tx_permanova_endpoint_agreement")


def fig_arm_agreement(arm: pd.DataFrame, out: Path, *, metric: str = "delta_shannon_bits") -> None:
    apply_style()
    arm = _frame_share(arm)
    if arm.empty or metric not in set(arm["metric"].astype(str)):
        return
    arm = arm[(arm["metric"] == metric) & (arm["grain"] == "full_session")].copy()
    arm["hit"] = _as_bool(arm["hit_fdr05"])
    contrasts = ("noSD_vs_GHSD", "noSD_vs_RBSD", "GHSD_vs_RBSD")
    agr = (
        arm.groupby(["sex", "phase_layer", "step", "contrast"], as_index=False)["hit"]
        .mean()
        .rename(columns={"hit": "frac_hit"})
    )
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 5.6), constrained_layout=True)
    im = None
    for r, sex in enumerate(SEX_ORDER):
        for c, contrast in enumerate(contrasts):
            ax = axes[r, c]
            sub = agr[(agr["sex"] == sex) & (agr["contrast"] == contrast)]
            mat = np.full((len(PHASES), len(COND_STEPS)), np.nan)
            for i, ph in enumerate(PHASES):
                for j, st in enumerate(COND_STEPS):
                    row = _pick_row(sub, phase_layer=ph, step=st)
                    if row is not None:
                        mat[i, j] = float(row["frac_hit"])
            im = ax.imshow(mat, cmap="viridis", vmin=0.0, vmax=1.0, aspect="auto")
            ax.set_xticks(range(len(COND_STEPS)))
            ax.set_xticklabels(
                [COND_STEP_LAB[s] for s in COND_STEPS], rotation=30, ha="right", fontsize=6
            )
            ax.set_yticks(range(len(PHASES)))
            ax.set_yticklabels([PHASE_SHORT[p] for p in PHASES], fontsize=6)
            ax.set_title(
                f"{contrast}  ·  {_sex_lab(sex)}",
                loc="left",
                fontweight="bold",
                color=INK,
                fontsize=7,
            )
            _annotate(ax, mat, fontsize=5.5)
    fig.colorbar(im, ax=axes, fraction=0.02, pad=0.02, label="frac models arm FDR hit")
    fig.suptitle(
        f"Arm contrasts · condition-step · {SCALAR_METRIC_LAB.get(metric, metric)} (frame_share)",
        fontsize=10,
        fontweight="bold",
        color=INK,
        y=1.02,
    )
    fig_footnote(fig, FEET['arm_foot'], y=-0.05)
    save_pdf_png(fig, out / "fig_tx_arm_contrasts_condition_agreement")


def fig_consensus_animal(tests: pd.DataFrame, out: Path) -> None:
    apply_style()
    t = _frame_share(tests)
    if t.empty:
        return
    t = t[t["grain"] == "full_session"].copy()
    t["hit"] = _as_bool(t["hit_fdr05"]).astype(float)
    metrics = [m for m in SCALAR_METRICS_COND if m in set(t["metric"].astype(str))]
    if not metrics:
        return
    fig, axes = plt.subplots(
        len(metrics), 2, figsize=(7.2, 1.6 * len(metrics) + 0.6), constrained_layout=True
    )
    if len(metrics) == 1:
        axes = np.array([axes])
    im = None
    for r, met in enumerate(metrics):
        for c, sex in enumerate(SEX_ORDER):
            ax = axes[r, c]
            sub = t[(t["metric"] == met) & (t["sex"] == sex)]
            mat = np.full((len(PHASES), len(COND_STEPS)), np.nan)
            for i, ph in enumerate(PHASES):
                for j, st in enumerate(COND_STEPS):
                    row = _pick_row(sub, phase_layer=ph, step=st)
                    if row is not None:
                        mat[i, j] = float(row["hit"])
            im = ax.imshow(mat, cmap="viridis", vmin=0.0, vmax=1.0, aspect="auto")
            ax.set_xticks(range(len(COND_STEPS)))
            ax.set_xticklabels(
                [COND_STEP_LAB[s] for s in COND_STEPS], rotation=30, ha="right", fontsize=6
            )
            ax.set_yticks(range(len(PHASES)))
            ax.set_yticklabels([PHASE_SHORT[p] for p in PHASES], fontsize=6)
            ax.set_title(
                f"{SCALAR_METRIC_LAB.get(met, met)}  ·  {_sex_lab(sex)}",
                loc="left",
                fontweight="bold",
                color=INK,
                fontsize=7,
            )
            _annotate(ax, mat, fmt="{:.0f}", fontsize=5.5)
    fig.colorbar(im, ax=axes, fraction=0.02, pad=0.02, label="hit_fdr05 (1/0)")
    fig.suptitle(
        "Consensus animal · condition-step scalars (full session, frame_share)",
        fontsize=10,
        fontweight="bold",
        color=INK,
        y=1.01,
    )
    fig_footnote(fig, FEET['cons'], y=-0.02)
    save_pdf_png(fig, out / "fig_tx_consensus_animal_condition")


def fig_grain_contrast_scalar(tests: pd.DataFrame, out: Path) -> None:
    apply_style()
    t = _frame_share(tests)
    if t.empty:
        return
    t = t.copy()
    t["hit"] = _as_bool(t["hit_fdr05"])
    preferred = [
        "grain_contrast_delta_shannon_bits",
        "grain_contrast_delta_richness",
        "grain_contrast_braycurtis",
        "delta_shannon_bits",
        "delta_richness",
        "braycurtis",
    ]
    metrics = [m for m in preferred if m in set(t["metric"].astype(str))]
    if not metrics:
        metrics = sorted(set(t["metric"].astype(str)))[:3]
    agr = (
        t.groupby(["sex", "phase_layer", "step", "metric"], as_index=False)["hit"]
        .mean()
        .rename(columns={"hit": "frac_hit"})
    )
    fig, axes = plt.subplots(
        len(metrics), 2, figsize=(7.2, 1.7 * len(metrics) + 0.6), constrained_layout=True
    )
    if len(metrics) == 1:
        axes = np.array([axes])
    im = None
    for r, met in enumerate(metrics):
        for c, sex in enumerate(SEX_ORDER):
            ax = axes[r, c]
            sub = agr[(agr["metric"] == met) & (agr["sex"] == sex)]
            mat = np.full((len(PHASES), len(COND_STEPS)), np.nan)
            for i, ph in enumerate(PHASES):
                for j, st in enumerate(COND_STEPS):
                    row = _pick_row(sub, phase_layer=ph, step=st)
                    if row is not None:
                        mat[i, j] = float(row["frac_hit"])
            im = ax.imshow(mat, cmap="viridis", vmin=0.0, vmax=1.0, aspect="auto")
            ax.set_xticks(range(len(COND_STEPS)))
            ax.set_xticklabels(
                [COND_STEP_LAB[s] for s in COND_STEPS], rotation=30, ha="right", fontsize=6
            )
            ax.set_yticks(range(len(PHASES)))
            ax.set_yticklabels([PHASE_SHORT[p] for p in PHASES], fontsize=6)
            ax.set_title(
                f"{SCALAR_METRIC_LAB.get(met, met)}  ·  {_sex_lab(sex)}",
                loc="left",
                fontweight="bold",
                color=INK,
                fontsize=7,
            )
            _annotate(ax, mat, fontsize=5.5)
    fig.colorbar(im, ax=axes, fraction=0.02, pad=0.02, label="frac models hit_fdr05")
    fig.suptitle(
        "Grain contrast · near − full on condition-step scalars (frame_share)",
        fontsize=10,
        fontweight="bold",
        color=INK,
        y=1.01,
    )
    fig_footnote(fig, FEET['gc'], y=-0.02)
    save_pdf_png(fig, out / "fig_tx_grain_contrast_scalar_condition")


def fig_grain_contrast_da(tests: pd.DataFrame, out: Path) -> None:
    apply_style()
    t = _frame_share(tests)
    if t.empty:
        return
    t = t.copy()
    t["hit"] = _as_bool(t["hit_fdr05"])
    rows = []
    for (model, weighting, sex, phase, step), g in t.groupby(
        ["model", "weighting", "sex", "phase_layer", "step"], sort=True
    ):
        k = int(g["alphabet_k"].iloc[0]) if "alphabet_k" in g.columns else 50
        n_hit = int(g["hit"].sum())
        rows.append(
            {
                "model": model,
                "weighting": weighting,
                "sex": sex,
                "phase_layer": phase,
                "step": step,
                "consensus_hit": (float(n_hit) / float(k) >= 0.04) if k else False,
            }
        )
    agr = pd.DataFrame(rows)
    if agr.empty:
        return
    cell = (
        agr.groupby(["sex", "phase_layer", "step"], as_index=False)["consensus_hit"]
        .mean()
        .rename(columns={"consensus_hit": "frac_hit"})
    )
    fig, axes = plt.subplots(1, 2, figsize=FIGSIZE_DOUBLE, constrained_layout=True)
    im = None
    for c, sex in enumerate(SEX_ORDER):
        ax = axes[c]
        sub = cell[cell["sex"] == sex]
        mat = np.full((len(PHASES), len(COND_STEPS)), np.nan)
        for i, ph in enumerate(PHASES):
            for j, st in enumerate(COND_STEPS):
                row = _pick_row(sub, phase_layer=ph, step=st)
                if row is not None:
                    mat[i, j] = float(row["frac_hit"])
        im = ax.imshow(mat, cmap="viridis", vmin=0.0, vmax=1.0, aspect="auto")
        ax.set_xticks(range(len(COND_STEPS)))
        ax.set_xticklabels(
            [COND_STEP_LAB[s] for s in COND_STEPS], rotation=30, ha="right", fontsize=7
        )
        ax.set_yticks(range(len(PHASES)))
        ax.set_yticklabels([PHASE_SHORT[p] for p in PHASES])
        ax.set_title(_sex_lab(sex), loc="left", fontweight="bold", color=INK, fontsize=9)
        _annotate(ax, mat, fontsize=6)
    fig.colorbar(im, ax=axes, fraction=0.03, pad=0.02, label="frac models ≥4% alphabet")
    fig.suptitle(
        "Grain contrast DA · near − full on condition-step Δp (frame_share)",
        fontsize=11,
        fontweight="bold",
        color=INK,
        y=1.05,
    )
    fig_footnote(fig, FEET['gc'], y=-0.10)
    save_pdf_png(fig, out / "fig_tx_grain_contrast_da_condition")


def _write_figures_md(out: Path) -> None:
    today = date.today().isoformat()
    sb = STAGE_B
    scale = FEET.get("scale", "rank Stage-B")
    loc = FEET.get("loc", "median")
    arm = FEET.get("arm", "Mann-Whitney")
    text = f"""# Figures — tx-on-paired-delta lattice (Q1-Q4 + extras)

Complementary to `INFO_tx_on_paired_delta.md`. Visual-encoding map only.

Stage-B for this figure set: `{sb}` ({scale}).


|                 |                                                                      |
| --------------- | -------------------------------------------------------------------- |
| These files     | next to this `FIGURES.md`                                            |
| Generated       | {today}                                                              |
| How regenerated | `uv run python scratch/nor_object_mi/fig_simpler_first_tx_on_paired_delta.py --run-dir <run>` |


## Core (Q1-Q4, frame_share)


| Stem | Question | Source -> columns | Encoding | D / I |
| ---- | -------- | ----------------- | -------- | ----- |
| `fig_tx_q1_da_condition_agreement` | Q1 model consensus | `tx_da_condition_agreement.csv` -> `frac_model_consensus_hit` | heatmap grain x sex; phase x condition-step | I (cell-level) |
| `fig_tx_q2_shannon_condition_agreement` | Q2 model consensus | `tx_shannon_condition_agreement.csv` -> `frac_hit` | same layout | I |
| `fig_tx_q3_da_phase_agreement` | Q3 model consensus | `tx_da_phase_agreement.csv` -> `frac_model_consensus_hit` | heatmap grain x sex; condition x phase-step | I |
| `fig_tx_q4_shannon_phase_agreement` | Q4 model consensus | `tx_shannon_phase_agreement.csv` -> `frac_hit` | same layout | I |
| `fig_tx_q1_n_hit_fdr05_{{grain}}` | Q1 n hits / model | `tx_da_condition_tests_long.csv` -> `hit_fdr05` | strip + median | I count |
| `fig_tx_q3_n_hit_fdr05_{{grain}}` | Q3 n hits / model | `tx_da_phase_tests_long.csv` -> `hit_fdr05` | strip + median | I count |
| `fig_tx_q1_lollipop_pilot` | Q1 pilot tx locations | tests long -> `{loc}_{{tx}}` on FDR hits | lollipop / range | I set, D locations |


## Extras


| Stem | Extra | Source -> columns | Encoding | D / I |
| ---- | ----- | ----------------- | -------- | ----- |
| `fig_tx_scalar_condition_agreement` | scalar lattice (cond) | `tx_scalar_condition_agreement.csv` -> `frac_hit` | metric x sex; phase x step | I |
| `fig_tx_scalar_phase_agreement` | scalar lattice (phase) | `tx_scalar_phase_agreement.csv` -> `frac_hit` | metric x sex; cond x phase-step | I |
| `fig_tx_q1_da_condition_agreement_bout_count` | bout_count DA | `tx_da_condition_agreement.csv` -> `frac_model_consensus_hit` | grain x sex heatmaps | I |
| `fig_tx_permanova_endpoint_agreement` | PERMANOVA | `tx_permanova_endpoint_tests_long.csv` -> `hit_fdr05` | grain x sex; phase x condition | I |
| `fig_tx_arm_contrasts_condition_agreement` | arm ({arm}) | `tx_arm_contrasts_condition_long.csv` -> `hit_fdr05` | sex x contrast; phase x step | I |
| `fig_tx_consensus_animal_condition` | consensus animal | `tx_consensus_animal_condition_tests_long.csv` -> `hit_fdr05` | metric x sex heatmaps | I |
| `fig_tx_grain_contrast_scalar_condition` | near-full scalars | `tx_grain_contrast_scalar_condition_tests_long.csv` -> `hit_fdr05` | metric x sex | I |
| `fig_tx_grain_contrast_da_condition` | near-full DA | `tx_grain_contrast_da_condition_tests_long.csv` -> >=4% alphabet | sex heatmaps | I |


## Notes

- Pilot model: `{PILOT_MODEL}`. Lollipop cell = strongest Q1 consensus row (frame_share).
- Core Q1-Q4 panels filter to `frame_share`; bout_count has its own DA panel.
- Stage-B is inferred from `run_summary.json` / `test` column / folder name (`kruskal` vs `anova`).
- DA (differential abundance) consensus != Shannon / scalar consensus; do not pool syllable ids across models.
- PDF + SVG written for each stem.
"""
    (out / "FIGURES.md").write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--pilot-model", type=str, default=PILOT_MODEL)
    ap.add_argument(
        "--stage-b",
        choices=("auto", "kruskal", "anova"),
        default="auto",
        help="Footnotes / titles: auto-infer from run, or force rank vs mean",
    )
    args = ap.parse_args(argv)
    run = args.run_dir
    out = args.out_dir or (run / "figures")
    out.mkdir(parents=True, exist_ok=True)

    da_c_agree = _read_csv_maybe(run / "tx_da_condition_agreement.csv")
    sh_c_agree = _read_csv_maybe(run / "tx_shannon_condition_agreement.csv")
    da_p_agree = _read_csv_maybe(run / "tx_da_phase_agreement.csv")
    sh_p_agree = _read_csv_maybe(run / "tx_shannon_phase_agreement.csv")
    da_c = _read_csv_maybe(run / "tx_da_condition_tests_long.csv")
    da_p = _read_csv_maybe(run / "tx_da_phase_tests_long.csv")
    sc_c_agree = _read_csv_maybe(run / "tx_scalar_condition_agreement.csv")
    sc_p_agree = _read_csv_maybe(run / "tx_scalar_phase_agreement.csv")
    perm = _read_csv_maybe(run / "tx_permanova_endpoint_tests_long.csv")
    arm_c = _read_csv_maybe(run / "tx_arm_contrasts_condition_long.csv")
    cons_c = _read_csv_maybe(run / "tx_consensus_animal_condition_tests_long.csv")
    gc_sc = _read_csv_maybe(run / "tx_grain_contrast_scalar_condition_tests_long.csv")
    gc_da = _read_csv_maybe(run / "tx_grain_contrast_da_condition_tests_long.csv")

    stage_b = args.stage_b if args.stage_b != "auto" else _infer_stage_b(run, da_c)
    _set_stage_b(stage_b)

    fig_q1_agreement(da_c_agree, out)
    fig_q2_agreement(sh_c_agree, out)
    fig_q3_agreement(da_p_agree, out)
    fig_q4_agreement(sh_p_agree, out)
    for grain in GRAINS:
        fig_q1_n_hit(da_c, out, grain=grain)
        fig_q3_n_hit(da_p, out, grain=grain)
    cell = _pick_pilot_cell(da_c_agree)
    fig_q1_lollipop_pilot(da_c, out, model=args.pilot_model, cell=cell)

    fig_scalar_condition_agreement(sc_c_agree, out)
    fig_scalar_phase_agreement(sc_p_agree, out)
    fig_da_bout_count_agreement(da_c_agree, out)
    fig_permanova_agreement(perm, out)
    fig_arm_agreement(arm_c, out, metric="delta_shannon_bits")
    fig_consensus_animal(cons_c, out)
    fig_grain_contrast_scalar(gc_sc, out)
    fig_grain_contrast_da(gc_da, out)

    _write_figures_md(out)
    print(f"figures -> {out}")
    print(f"stage_b={stage_b}")
    print(f"pilot lollipop cell: {cell}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
