"""Slides figures: NOR protocol prologue (mean/interval cousins only).

Narrative order: association → presence → novelty → preference → tx coda.
Reads only CSVs listed in INFO_protocol_prologue.md.

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/fig_simpler_first_protocol_prologue.py --dest slides
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import ListedColormap

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi._pub_style import (  # noqa: E402
    FIGSIZE_SLIDES,
    INK,
    PHASE_SHORT,
    PHASES,
    SEX_MARKER,
    SEX_ORDER,
    TX_COLOR,
    TX_ORDER,
    apply_style,
    fig_footnote,
    fig_legend_and_footnote,
    p_text,
    panel_stats_box,
    save_pdf_svg,
    tx_sex_legend_handles,
    type_scale,
)

DEFAULT_RUN = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_protocol_prologue"
)
STEP_PRESENCE = "no_obj->identical"
STEP_NOVELTY = "identical->novel"

FOOT_ENGAGE = (
    "Points = one animal’s median Δ across 21 kpMS models (consensus); thin whiskers = "
    "±½ IQR of that animal’s Δ across models (across-model dispersion / salt). "
    "Tick = tx mean of consensus medians. Color=tx, shape=sex. One-sample t vs 0 within "
    "sex (F and M; txs pooled within sex). Stats box also shows cohort median IQR. "
    "frac_near: fraction of session frames whose syllable-bout mean spot→nearest-target "
    "distance is < 0.10 m (gate on bout mean, then frame tally). mean_dist_any: "
    "frame-weighted mean of those bout-mean nearest-target distances over the whole "
    "session (no 0.10 m cut). On no_obj, targets are historical loci. Uncorrected. "
    "Not DR; not a treatment claim; not DA; not COUNT/UNCERTAINTY salt."
)


def _begin(dest: str) -> dict[str, float]:
    apply_style(dest=dest)
    return type_scale(dest)


def _as_bool(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s
    return s.astype(str).str.lower().isin(("true", "1"))


def _p_compact(p: float) -> str:
    if not np.isfinite(p):
        return "n/a"
    if p < 1e-4:
        return "<10⁻⁴"
    if p < 0.001:
        return f"{p:.1e}"
    return f"{p:.2f}"


def _lookup_ttest(
    tests: pd.DataFrame,
    *,
    phase: str,
    metric: str,
    sex: str,
    step: str | None = None,
) -> pd.Series | None:
    m = (tests["test"] == "ttest_1samp") & (tests["sex"] == sex) & (tests["metric"] == metric)
    m &= tests["phase_layer"] == phase
    if step is not None:
        m &= tests["step"] == step
    sub = tests[m]
    if len(sub) != 1:
        return None
    return sub.iloc[0]


def _lookup_anova(
    tests: pd.DataFrame,
    *,
    phase: str,
    metric: str,
    sex: str,
    step: str | None = None,
) -> float:
    m = (tests["test"] == "welch_anova") & (tests["metric"] == metric) & (tests["sex"] == sex)
    m &= tests["phase_layer"] == phase
    if step is not None:
        m &= tests["step"] == step
    sub = tests[m]
    if len(sub) != 1:
        return float("nan")
    return float(sub["p"].iloc[0])


def _cohort_iqr(summary: pd.DataFrame | None, *, phase: str, step: str, metric: str) -> float:
    if summary is None or summary.empty:
        return float("nan")
    sub = summary[
        (summary["phase_layer"] == phase)
        & (summary["step"] == step)
        & (summary["metric"] == metric)
    ]
    if len(sub) != 1:
        return float("nan")
    return float(sub["median_of_iqr"].iloc[0])


def _fm_stats_lines(
    tests: pd.DataFrame,
    *,
    phase: str,
    metric: str,
    step: str | None = None,
    cohort_iqr: float | None = None,
) -> list[str]:
    lines = ["one-sample t vs 0"]
    for sex in SEX_ORDER:
        row = _lookup_ttest(tests, phase=phase, metric=metric, sex=sex, step=step)
        if row is None:
            lines.append(f"{sex} n/a")
            continue
        hit = "hit" if bool(row["hit_p05"]) else "miss"
        lines.append(
            f"{sex} n={int(row['n'])}  mean={float(row['mean_delta']):+.2f}  "
            f"{_p_compact(float(row['p']))}  {hit}"
        )
    if cohort_iqr is not None and np.isfinite(cohort_iqr):
        lines.append(f"cohort med IQR={cohort_iqr:.3g}")
    return lines


def _draw_tx_violins(
    ax,
    panel: pd.DataFrame,
    ycol: str,
    rng: np.random.Generator,
    *,
    dest: str,
    iqr_col: str | None = None,
) -> list[int]:
    """Strip + violin by tx. Optional ``iqr_col`` → ±½ IQR whiskers on each point."""
    ts = type_scale(dest)
    positions = list(range(len(TX_ORDER)))
    bodies: list[np.ndarray] = []
    body_pos: list[int] = []
    body_color: list[str] = []
    ns: list[int] = []
    for i, t in enumerate(TX_ORDER):
        sub = panel[panel["tx"] == t]
        y = sub[ycol].to_numpy(dtype=float)
        sex = sub["sex"].to_numpy()
        iqr = (
            sub[iqr_col].to_numpy(dtype=float)
            if iqr_col is not None and iqr_col in sub.columns
            else np.full(y.shape, np.nan)
        )
        finite = np.isfinite(y)
        y = y[finite]
        sex = sex[finite]
        iqr = iqr[finite]
        ns.append(int(y.size))
        if y.size >= 2 and np.unique(y).size >= 2:
            bodies.append(y)
            body_pos.append(i)
            body_color.append(TX_COLOR[t])
        if y.size:
            x = np.full(y.shape, float(i)) + rng.normal(0.0, 0.055, size=y.size)
            half = np.where(np.isfinite(iqr), 0.5 * iqr, np.nan)
            for s in SEX_ORDER:
                m = sex == s
                if not np.any(m):
                    continue
                if np.any(np.isfinite(half[m])):
                    ax.errorbar(
                        x[m],
                        y[m],
                        yerr=np.where(np.isfinite(half[m]), half[m], 0.0),
                        fmt="none",
                        ecolor=TX_COLOR[t],
                        elinewidth=0.7,
                        capsize=0,
                        alpha=0.35,
                        zorder=2,
                    )
                ax.scatter(
                    x[m],
                    y[m],
                    s=ts["scatter"],
                    c=TX_COLOR[t],
                    marker=SEX_MARKER[s],
                    alpha=0.75,
                    edgecolors="none",
                    zorder=3,
                )
            ax.plot(
                [i - 0.22, i + 0.22],
                [float(np.mean(y))] * 2,
                color=INK,
                lw=1.5,
                zorder=4,
            )
    if bodies:
        parts = ax.violinplot(
            bodies,
            positions=body_pos,
            widths=0.78,
            showmeans=False,
            showmedians=False,
            showextrema=False,
        )
        for pc, col in zip(parts["bodies"], body_color):
            pc.set_facecolor(col)
            pc.set_edgecolor("none")
            pc.set_alpha(0.32)
            pc.set_zorder(1)
    ax.set_xticks(positions)
    ax.set_xticklabels([])
    ax.tick_params(axis="x", length=3)
    ax.set_xlim(-0.7, len(TX_ORDER) - 0.3)
    return ns


def _engagement_grid(
    deltas: pd.DataFrame,
    tests: pd.DataFrame,
    out_stem: Path,
    *,
    step: str,
    dest: str,
    suptitle: str,
    footnote: str,
    dispersion: pd.DataFrame | None = None,
    dispersion_summary: pd.DataFrame | None = None,
) -> None:
    ts = _begin(dest)
    rng = np.random.default_rng(0)
    fig, axes = plt.subplots(2, 4, figsize=FIGSIZE_SLIDES, sharex="col", layout="constrained")
    metrics = (
        ("delta_frac_near", "Δ frac_near"),
        ("delta_mean_dist_any_m", "Δ mean_dist_any (m)"),
    )
    join_keys = ["animal_id", "sex", "tx", "phase_layer", "step"]
    for r, (metric, ylab) in enumerate(metrics):
        for c, ph in enumerate(PHASES):
            ax = axes[r, c]
            panel = deltas[(deltas["phase_layer"] == ph) & (deltas["step"] == step)].copy()
            if dispersion is not None and not dispersion.empty:
                dsub = dispersion[
                    (dispersion["phase_layer"] == ph)
                    & (dispersion["step"] == step)
                    & (dispersion["metric"] == metric)
                ][join_keys + ["iqr", "median"]].copy()
                panel = panel.merge(dsub, on=join_keys, how="left", suffixes=("", "_disp"))
                # Prefer dispersion median if present (should match consensus Δ).
                if "median" in panel.columns and panel["median"].notna().any():
                    panel[metric] = panel["median"].where(panel["median"].notna(), panel[metric])
            _draw_tx_violins(
                ax,
                panel,
                metric,
                rng,
                dest=dest,
                iqr_col="iqr" if dispersion is not None else None,
            )
            ax.axhline(0.0, color="#bbbbbb", lw=0.7, ls="--", zorder=0)
            ciqr = _cohort_iqr(dispersion_summary, phase=ph, step=step, metric=metric)
            panel_stats_box(
                ax,
                _fm_stats_lines(
                    tests,
                    phase=ph,
                    metric=metric,
                    step=step,
                    cohort_iqr=ciqr,
                ),
                dest=dest,
            )
            if r == 1:
                ax.set_xlabel(PHASE_SHORT[ph], fontsize=ts["annotation"], color=INK, fontweight="bold")
            if c == 0:
                ax.set_ylabel(ylab)
            if r == 0:
                ax.set_title(f"{'ABCD'[c]}  {PHASE_SHORT[ph]}", loc="left", fontweight="bold", color=INK)
    fig.suptitle(suptitle, fontsize=ts["suptitle"], fontweight="bold", color=INK, y=1.02)
    fig_legend_and_footnote(fig, tx_sex_legend_handles(dest=dest), footnote, dest=dest)
    save_pdf_svg(fig, out_stem)


def fig_presence(
    deltas: pd.DataFrame,
    tests: pd.DataFrame,
    out: Path,
    *,
    dest: str,
    dispersion: pd.DataFrame | None = None,
    dispersion_summary: pd.DataFrame | None = None,
) -> None:
    _engagement_grid(
        deltas,
        tests,
        out / "fig_protocol_presence",
        step=STEP_PRESENCE,
        dest=dest,
        suptitle="Presence: objects appear → more near occupancy / closer spot–target distance",
        footnote="Step no_obj→identical. " + FOOT_ENGAGE,
        dispersion=dispersion,
        dispersion_summary=dispersion_summary,
    )


def fig_novelty(
    deltas: pd.DataFrame,
    tests: pd.DataFrame,
    out: Path,
    *,
    dest: str,
    dispersion: pd.DataFrame | None = None,
    dispersion_summary: pd.DataFrame | None = None,
) -> None:
    _engagement_grid(
        deltas,
        tests,
        out / "fig_protocol_novelty_step",
        step=STEP_NOVELTY,
        dest=dest,
        suptitle="Novelty step is weaker than presence: identical → novel engagement",
        footnote=(
            "Step identical→novel only (dedicated). Same metric definitions, consensus, "
            "and across-model IQR whiskers as the presence figure. Expect miss or TX-skew "
            "— protocol gap, not treatment. "
            + FOOT_ENGAGE
        ),
        dispersion=dispersion,
        dispersion_summary=dispersion_summary,
    )


def fig_dr_preference(animals: pd.DataFrame, tests: pd.DataFrame, out: Path, *, dest: str) -> None:
    ts = _begin(dest)
    rng = np.random.default_rng(0)
    fig, axes = plt.subplots(2, 4, figsize=FIGSIZE_SLIDES, sharex="col", layout="constrained")
    rows = (
        ("dr_original", "original investigation DR"),
        ("dr_object_prox", "object-prox occupancy DR"),
    )
    for r, (metric, ylab) in enumerate(rows):
        for c, ph in enumerate(PHASES):
            ax = axes[r, c]
            panel = animals[animals["phase_layer"] == ph]
            _draw_tx_violins(ax, panel, metric, rng, dest=dest)
            ax.axhline(0.0, color="#bbbbbb", lw=0.7, ls="--", zorder=0)
            panel_stats_box(ax, _fm_stats_lines(tests, phase=ph, metric=metric), dest=dest)
            if r == 1:
                ax.set_xlabel(PHASE_SHORT[ph], fontsize=ts["annotation"], color=INK, fontweight="bold")
            if c == 0:
                ax.set_ylabel(ylab)
            if r == 0:
                ax.set_title(f"{'ABCD'[c]}  {PHASE_SHORT[ph]}", loc="left", fontweight="bold", color=INK)
    fig.suptitle(
        "Novel preference: DR > 0 on novel_obj (original investigation and object-prox)",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
        y=1.02,
    )
    fig_legend_and_footnote(
        fig,
        tx_sex_legend_handles(dest=dest),
        (
            "Grain animal × phase × novel_obj. Top: original investigation DR "
            "(nose/forelimb T; no kpMS consensus). Bottom: object-prox occupancy DR "
            "(spot bout-mean < 0.10 m; animal median across 21 kpMS models). "
            "One-sample t vs 0 within sex. DR normalizes (T_nvl−T_fam)/(T_nvl+T_fam); "
            "paired t on raw T_nvl vs T_fam (absolute seconds) is a different claim "
            "(in tests table, not plotted). Uncorrected. Not presence step; not DA."
        ),
        dest=dest,
    )
    save_pdf_svg(fig, out / "fig_protocol_dr_preference")


def fig_bout_clocks(
    clocks: pd.DataFrame,
    assoc: pd.DataFrame,
    out: Path,
    *,
    dest: str,
) -> None:
    """Movement-bout clock vs syllable-bout clock (n and duration)."""
    ts = _begin(dest)
    rng = np.random.default_rng(0)
    fig, axes = plt.subplots(2, 4, figsize=FIGSIZE_SLIDES, layout="constrained")
    rows = (
        ("n_move_bouts", "n_syll_bouts", "n_move_vs_n_syll", "n bouts"),
        (
            "median_move_duration_s",
            "median_syll_duration_s",
            "dur_move_vs_dur_syll",
            "median duration (s)",
        ),
    )
    for r, (xcol, ycol, contrast, ylab) in enumerate(rows):
        for c, ph in enumerate(PHASES):
            ax = axes[r, c]
            panel = clocks[clocks["phase_layer"] == ph]
            x = panel[xcol].to_numpy(dtype=float)
            y = panel[ycol].to_numpy(dtype=float)
            tx = panel["tx"].to_numpy()
            sex = panel["sex"].to_numpy()
            ok = np.isfinite(x) & np.isfinite(y)
            x, y, tx, sex = x[ok], y[ok], tx[ok], sex[ok]
            jitter = rng.normal(0.0, 0.02 * (np.nanmax(x) - np.nanmin(x) + 1e-6), size=x.size)
            for t in TX_ORDER:
                for s in SEX_ORDER:
                    m = (tx == t) & (sex == s)
                    if not np.any(m):
                        continue
                    ax.scatter(
                        x[m] + jitter[m],
                        y[m],
                        s=ts["scatter"],
                        c=TX_COLOR[t],
                        marker=SEX_MARKER[s],
                        alpha=0.75,
                        edgecolors="none",
                        zorder=3,
                    )
            if r == 1:
                ax.set_xlabel(PHASE_SHORT[ph], fontsize=ts["annotation"], color=INK, fontweight="bold")
            if c == 0:
                ax.set_ylabel(f"syllable  ·  {ylab}")
            if r == 0:
                ax.set_title(f"{'ABCD'[c]}  {PHASE_SHORT[ph]}", loc="left", fontweight="bold", color=INK)
            ax.set_xlabel(
                ("movement  ·  " + ylab) if r == 1 else "",
                fontsize=ts["annotation"],
                color=INK,
            )
            if r == 1:
                ax.set_xlabel(
                    f"movement · {ylab}\n{PHASE_SHORT[ph]}",
                    fontsize=ts["annotation"],
                    color=INK,
                    fontweight="bold",
                )
            lines = ["Pearson r (within sex)"]
            for s in SEX_ORDER:
                row = assoc[
                    (assoc["phase_layer"] == ph)
                    & (assoc["sex"] == s)
                    & (assoc["contrast"] == contrast)
                ]
                if len(row) != 1:
                    lines.append(f"{s} n/a")
                    continue
                rv = float(row["pearson_r"].iloc[0])
                hit = "hit" if bool(_as_bool(row["hit_p05"]).iloc[0]) else "miss"
                lines.append(
                    f"{s} n={int(row['n'].iloc[0])}  r={rv:.2f}  "
                    f"{_p_compact(float(row['p'].iloc[0]))}  {hit}"
                )
            panel_stats_box(ax, lines, dest=dest)
    fig.suptitle(
        "Two clocks: movement bouts (fore hysteresis) vs syllable bouts (kpMS labels)",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
        y=1.02,
    )
    fig_legend_and_footnote(
        fig,
        tx_sex_legend_handles(dest=dest),
        (
            "Top: bout counts. Bottom: median bout duration. X = IMPRESS movement "
            "bouts; Y = kpMS syllable bouts (locked ss-50 model in the clocks run). "
            "Different segmenters — not paired events. Syllable NOR ladders have "
            "count/duration only (no bout speed or immobile). Session immobile and "
            "movement bout speed/distance live in protocol_clock_association "
            "(move_litmus vs session ambulation), not plotted here. Pearson within "
            "sex. Uncorrected. Not DR; not DA."
        ),
        dest=dest,
    )
    save_pdf_svg(fig, out / "fig_protocol_bout_clocks")


def fig_bout_clocks(
    clocks: pd.DataFrame,
    assoc: pd.DataFrame,
    out: Path,
    *,
    dest: str,
) -> None:
    """Movement-bout clock vs syllable-bout clock (n and duration)."""
    ts = _begin(dest)
    rng = np.random.default_rng(0)
    fig, axes = plt.subplots(2, 4, figsize=FIGSIZE_SLIDES, layout="constrained")
    rows = (
        ("n_move_bouts", "n_syll_bouts", "n_move_vs_n_syll", "n bouts"),
        (
            "median_move_duration_s",
            "median_syll_duration_s",
            "dur_move_vs_dur_syll",
            "median duration (s)",
        ),
    )
    for r, (xcol, ycol, contrast, metric_lab) in enumerate(rows):
        for c, ph in enumerate(PHASES):
            ax = axes[r, c]
            panel = clocks[clocks["phase_layer"] == ph]
            x = panel[xcol].to_numpy(dtype=float)
            y = panel[ycol].to_numpy(dtype=float)
            tx = panel["tx"].to_numpy()
            sex = panel["sex"].to_numpy()
            ok = np.isfinite(x) & np.isfinite(y)
            x, y, tx, sex = x[ok], y[ok], tx[ok], sex[ok]
            span = float(np.nanmax(x) - np.nanmin(x)) if x.size else 1.0
            jitter = rng.normal(0.0, 0.02 * (span + 1e-6), size=x.size)
            for t in TX_ORDER:
                for s in SEX_ORDER:
                    m = (tx == t) & (sex == s)
                    if not np.any(m):
                        continue
                    ax.scatter(
                        x[m] + jitter[m],
                        y[m],
                        s=ts["scatter"],
                        c=TX_COLOR[t],
                        marker=SEX_MARKER[s],
                        alpha=0.75,
                        edgecolors="none",
                        zorder=3,
                    )
            if c == 0:
                ax.set_ylabel(f"syllable · {metric_lab}")
            if r == 0:
                ax.set_title(f"{'ABCD'[c]}  {PHASE_SHORT[ph]}", loc="left", fontweight="bold", color=INK)
            if r == 1:
                ax.set_xlabel(
                    f"movement · {metric_lab}\n{PHASE_SHORT[ph]}",
                    fontsize=ts["annotation"],
                    color=INK,
                    fontweight="bold",
                )
            lines = ["Pearson r (within sex)"]
            for s in SEX_ORDER:
                row = assoc[
                    (assoc["phase_layer"] == ph)
                    & (assoc["sex"] == s)
                    & (assoc["contrast"] == contrast)
                ]
                if len(row) != 1:
                    lines.append(f"{s} n/a")
                    continue
                rv = float(row["pearson_r"].iloc[0])
                hit = "hit" if bool(_as_bool(row["hit_p05"]).iloc[0]) else "miss"
                lines.append(
                    f"{s} n={int(row['n'].iloc[0])}  r={rv:.2f}  "
                    f"{_p_compact(float(row['p'].iloc[0]))}  {hit}"
                )
            panel_stats_box(ax, lines, dest=dest)
    fig.suptitle(
        "Two clocks: movement bouts (fore hysteresis) vs syllable bouts (kpMS labels)",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
        y=1.02,
    )
    fig_legend_and_footnote(
        fig,
        tx_sex_legend_handles(dest=dest),
        (
            "Top: bout counts. Bottom: median bout duration. X = IMPRESS movement "
            "bouts; Y = kpMS syllable bouts (locked ss-50 model). Different "
            "segmenters — not paired events. Syllable NOR ladders have count/"
            "duration only (no bout speed or immobile). Movement bout speed/"
            "distance vs session ambulation is in protocol_clock_association "
            "(move_litmus), not this stem. Pearson within sex. Uncorrected. "
            "Not DR; not DA."
        ),
        dest=dest,
    )
    save_pdf_svg(fig, out / "fig_protocol_bout_clocks")


def fig_dr_association(animals: pd.DataFrame, assoc: pd.DataFrame, out: Path, *, dest: str) -> None:
    """Primary association: original investigation DR vs object-prox DR."""
    ts = _begin(dest)
    rng = np.random.default_rng(0)
    fig, axes = plt.subplots(1, 4, figsize=FIGSIZE_SLIDES, sharex=True, sharey=True, layout="constrained")
    agr = assoc[
        (assoc["contrast"] == "original_vs_object_prox") & (assoc["sex"].isin(list(SEX_ORDER)))
    ]
    for i, ph in enumerate(PHASES):
        ax = axes[i]
        panel = animals[animals["phase_layer"] == ph]
        x = panel["dr_original"].to_numpy(dtype=float)
        y = panel["dr_object_prox"].to_numpy(dtype=float)
        tx = panel["tx"].to_numpy()
        sex = panel["sex"].to_numpy()
        ok = np.isfinite(x) & np.isfinite(y)
        x, y, tx, sex = x[ok], y[ok], tx[ok], sex[ok]
        jitter = rng.normal(0.0, 0.008, size=x.size)
        for t in TX_ORDER:
            for s in SEX_ORDER:
                m = (tx == t) & (sex == s)
                if not np.any(m):
                    continue
                ax.scatter(
                    x[m] + jitter[m],
                    y[m],
                    s=ts["scatter"],
                    c=TX_COLOR[t],
                    marker=SEX_MARKER[s],
                    alpha=0.75,
                    edgecolors="none",
                    zorder=3,
                )
        ax.plot([-1.05, 1.05], [-1.05, 1.05], color="#bbbbbb", lw=0.8, ls="--", zorder=0)
        ax.set_xlim(-1.08, 1.08)
        ax.set_ylim(-1.08, 1.08)
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlabel(PHASE_SHORT[ph], fontsize=ts["annotation"], color=INK, fontweight="bold")
        if i == 0:
            ax.set_ylabel("object-prox DR")
        ax.set_title(f"{'ABCD'[i]}  {PHASE_SHORT[ph]}", loc="left", fontweight="bold", color=INK)
        lines = ["Pearson r (within sex)"]
        for s in SEX_ORDER:
            row = agr[(agr["phase_layer"] == ph) & (agr["sex"] == s)]
            if len(row) != 1:
                lines.append(f"{s} n/a")
                continue
            r = float(row["pearson_r"].iloc[0])
            hit = "hit" if bool(_as_bool(row["hit_p05"]).iloc[0]) else "miss"
            lines.append(f"{s} n={int(row['n'].iloc[0])}  r={r:.2f}  {_p_compact(float(row['p'].iloc[0]))}  {hit}")
        panel_stats_box(ax, lines, dest=dest)
    fig.suptitle(
        "Same preference axis: original investigation DR vs syllable object-prox DR",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
        y=1.02,
    )
    fig_legend_and_footnote(
        fig,
        tx_sex_legend_handles(dest=dest),
        (
            "X = original investigation DR (first analysis; nose/forelimb T). "
            "Y = object-prox occupancy DR from syllable bout clocks (median across "
            "21 kpMS models). Pearson r and p are within sex (txs pooled within sex). "
            "Shows syllable-based preference tracks the original readout. Not bout "
            "clocks; not treatment; not DA."
        ),
        dest=dest,
    )
    save_pdf_svg(fig, out / "fig_protocol_dr_association")


def fig_tx_coda(
    dr_tests: pd.DataFrame,
    pr_tests: pd.DataFrame,
    out: Path,
    *,
    dest: str,
) -> None:
    """Welch ANOVA by tx — hit/miss encoding (not −log₁₀(p))."""
    ts = _begin(dest)
    fig, axes = plt.subplots(1, 3, figsize=FIGSIZE_SLIDES, layout="constrained")
    panels = (
        (dr_tests, "dr_original", None, "Original DR"),
        (pr_tests, "delta_frac_near", STEP_PRESENCE, "Presence Δ frac_near"),
        (pr_tests, "delta_frac_near", STEP_NOVELTY, "Novelty Δ frac_near"),
    )
    cmap = ListedColormap(["#e8e8e8", "#1b9e77"])
    for ax, (tests, metric, step, title) in zip(axes, panels):
        mat = np.zeros((len(PHASES), len(SEX_ORDER)))
        for i, ph in enumerate(PHASES):
            for j, sex in enumerate(SEX_ORDER):
                p = _lookup_anova(tests, phase=ph, metric=metric, sex=sex, step=step)
                mat[i, j] = 1.0 if (np.isfinite(p) and p < 0.05) else 0.0
        ax.imshow(mat, cmap=cmap, vmin=0.0, vmax=1.0, aspect="auto")
        ax.set_xticks(range(len(SEX_ORDER)))
        ax.set_xticklabels(list(SEX_ORDER))
        ax.set_yticks(range(len(PHASES)))
        ax.set_yticklabels([PHASE_SHORT[p] for p in PHASES])
        ax.set_title(title, loc="left", fontweight="bold", color=INK)
        for i in range(mat.shape[0]):
            for j in range(mat.shape[1]):
                p = _lookup_anova(
                    tests,
                    phase=PHASES[i],
                    metric=metric,
                    sex=SEX_ORDER[j],
                    step=step,
                )
                ax.text(
                    j,
                    i,
                    _p_compact(p),
                    ha="center",
                    va="center",
                    fontsize=ts["cell"],
                    color=INK if mat[i, j] < 0.5 else "white",
                )
    fig.suptitle(
        "Treatment coda: Welch ANOVA across tx (mostly miss)",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
        y=1.02,
    )
    fig_footnote(
        fig,
        (
            "Cell color = hit (teal, p<0.05) vs miss (gray) for within-sex Welch ANOVA "
            "(Alexander–Govern) across tx; cell text = p. Presence/novelty scalars are "
            "consensus medians across 21 kpMS models; original DR is investigation "
            "export. This is the treatment question — not protocol one-sample t. "
            "Uncorrected. Not DA."
        ),
        y=-0.08,
    )
    save_pdf_svg(fig, out / "fig_protocol_tx_coda")


def write_figures_md(out: Path) -> None:
    text = """# Figures — NOR protocol prologue (mean/interval)

Complementary to `INFO_protocol_prologue.md`. Dest = slides.


|                 |                         |
| --------------- | ----------------------- |
| These files     | `simpler_first_protocol_prologue/figures/` |
| Dest            | `slides` |
| Story order     | DR association → bout clocks → presence → novelty → preference → tx coda |
| How regenerated | `uv run python scratch/nor_object_mi/fig_simpler_first_protocol_prologue.py --dest slides` |


---

## Artifact map


| Stem | Question clause | Source → columns | Encoding | D / I |
| ---- | --------------- | ---------------- | -------- | ----- |
| `fig_protocol_dr_association` | Syllable object-prox DR tracks original investigation DR | animals + `protocol_dr_association.csv` | scatter; Pearson within sex | D + I |
| `fig_protocol_bout_clocks` | Movement vs syllable bout clocks (n, duration) | `protocol_clock_metrics_per_animal.csv` + `protocol_clock_association.csv` | 2×4 scatter; Pearson within sex | D + I |
| `fig_protocol_presence` | Objects appear → engagement | consensus deltas + across-model IQR; t within sex | violin + ±½IQR whiskers; F/M t box | D + I |
| `fig_protocol_novelty_step` | Novelty step weaker | same; `identical->novel` | same | D + I |
| `fig_protocol_dr_preference` | DR > 0 (original + object-prox) | DR animals; t within sex | 2×4 violin | D + I |
| `fig_protocol_tx_coda` | Tx arms mostly miss | Welch ANOVA | hit/miss + p text | I |


---

## Notes

- Protocol hit rule: within-sex (`F`,`M`) one-sample t; txs pooled within sex.
- Consensus: presence/novelty and object-prox DR = median across 21 kpMS models; original DR = investigation export; syllable clock n/duration = locked ss-50 model.
- Presence/novelty whiskers: ±½ across-model IQR from `protocol_presence_across_model_dispersion.csv` (engagement only).
- Syllable NOR ladders have **no** bout speed/immobile; those kinematics are movement/session only (`move_litmus` in clock association CSV).
- What these are not: DR↔ambulation negctrl; tx primary pack; rank tests; DA.

---

## Regen

```powershell
uv run python scratch/nor_object_mi/fig_simpler_first_protocol_prologue.py --dest slides
```
"""
    (out / "FIGURES.md").write_text(text, encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    args = ap.parse_args(argv)
    dest = args.dest
    run = args.run_dir
    out = args.out_dir or (run / "figures")
    out.mkdir(parents=True, exist_ok=True)

    animals = pd.read_csv(run / "protocol_dr_per_animal.csv")
    dr_tests = pd.read_csv(run / "protocol_dr_tests_long.csv")
    assoc = pd.read_csv(run / "protocol_dr_association.csv")
    clocks = pd.read_csv(run / "protocol_clock_metrics_per_animal.csv")
    clock_assoc = pd.read_csv(run / "protocol_clock_association.csv")
    deltas = pd.read_csv(run / "protocol_presence_deltas_per_animal.csv")
    pr_tests = pd.read_csv(run / "protocol_presence_tests_long.csv")
    disp = pd.read_csv(run / "protocol_presence_across_model_dispersion.csv")
    disp_sum = pd.read_csv(run / "protocol_presence_across_model_dispersion_summary.csv")

    # Story order
    fig_dr_association(animals, assoc, out, dest=dest)
    fig_bout_clocks(clocks, clock_assoc, out, dest=dest)
    fig_presence(
        deltas,
        pr_tests,
        out,
        dest=dest,
        dispersion=disp,
        dispersion_summary=disp_sum,
    )
    fig_novelty(
        deltas,
        pr_tests,
        out,
        dest=dest,
        dispersion=disp,
        dispersion_summary=disp_sum,
    )
    fig_dr_preference(animals, dr_tests, out, dest=dest)
    fig_tx_coda(dr_tests, pr_tests, out, dest=dest)
    write_figures_md(out)

    stale = list(out.glob("fig_protocol_assoc_negctrl.*"))
    for path in stale:
        path.unlink()
        print(f"removed stale {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
