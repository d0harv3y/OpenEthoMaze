"""VAST DA figures: trial-step and session-step volcano ladders.

Wire names follow ``docs/vocab/PROTOCOL-STRATA.md``:
  session · trial_window · trial_step · session_step
(not ``phase_layer`` / ``sessions as phases``).

Stratified: one figure per strain×tx condition (sex = marker; filled = FDR).
Pooled x ∈ [−0.08, 0.12]; stratified x ∈ [−0.1, 0.2].

Regen:
  uv run python scratch/vast_moseq/fig_da_trial_windows.py \\
    --da-dir D:/az-sd-vast_paramscan2026/_da_trial_windows \\
    --sig-dir D:/az-sd-vast_paramscan2026/_syllable_signatures \\
    --pause-cluster 40
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi._pub_style import (  # noqa: E402
    FIGSIZE_DOUBLE,
    INK,
    MUTE,
    SEX_MARKER,
    SEX_ORDER,
    apply_style,
    fig_footnote,
    save_pdf_png,
    type_scale,
)
from nor_object_mi.fig_simpler_first_syllable_signatures import (  # noqa: E402
    add_cluster_id_colorbar,
    build_cluster_color_lookup,
    colors_for_cluster_ids,
)
from vast_moseq.cohort_meta import STRAIN_ORDER, TX_ORDER  # noqa: E402
from vast_moseq.vast_da_strat import da_tests_cohort_strat_from_deltas  # noqa: E402

DEFAULT_DA = Path(r"D:\sack\AZ-SD-VAST-moseq\_da_trial_windows")
DEFAULT_SIG = Path(r"D:\sack\AZ-SD-VAST-moseq\syllable_signatures")

SESSIONS = ("S01", "S02", "S03", "S04", "S05")
TRIAL_WINDOWS = ("early_t1-3", "mid_t4-6", "late_t7-9")
TRIAL_WINDOW_LAB = {
    "early_t1-3": "early T1–3",
    "mid_t4-6": "mid T4–6",
    "late_t7-9": "late T7–9",
}
TRIAL_STEPS = (
    ("mid_early", "mid−early"),
    ("late_mid", "late−mid"),
    ("late_early", "late−early"),
)
SESSION_STEPS = (
    ("S02-S01", "S02−S01"),
    ("S03-S02", "S03−S02"),
    ("S04-S03", "S04−S03"),
    ("S05-S04", "S05−S04"),
    ("S05-S01", "S05−S01"),
)

Y_CLIP = 4.0
X_LIM_POOLED = (-0.08, 0.12)
X_LIM_STRAT = (-0.1, 0.2)
GREY_SQ = "#9a9a9a"

# 4 strain×tx arms — Okabe–Ito-ish categorical (colorblind-safer than 2×2 overlays).
STX_ORDER: tuple[str, ...] = (
    "wt·n/a",
    "wt·RBSF-1",
    "tg·n/a",
    "tg·RBSF-1",
)
STX_STEM = {
    "wt·n/a": "wt_na",
    "wt·RBSF-1": "wt_RBSF-1",
    "tg·n/a": "tg_na",
    "tg·RBSF-1": "tg_RBSF-1",
}
STX_COLOR = {
    "wt·n/a": "#0072B2",  # blue
    "wt·RBSF-1": "#E69F00",  # orange
    "tg·n/a": "#009E73",  # bluish green
    "tg·RBSF-1": "#CC79A7",  # reddish purple
}
STRAIN_COLOR = {"wt": "#009E73", "tg": "#CC79A7"}
TX_EDGE = {"RBSF-1": "#333333", "n/a": "#888888"}


def stx_label(strain: object, tx: object) -> str:
    return f"{str(strain)}·{str(tx)}"


def _as_bool(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s
    return s.astype(str).str.lower().isin(("true", "1", "yes"))


def _alias_wire(df: pd.DataFrame) -> pd.DataFrame:
    """Accept legacy ``phase_layer`` / ``condition_layer`` or wire ``session`` / ``trial_window``."""
    out = df.copy()
    if "session" not in out.columns and "phase_layer" in out.columns:
        out = out.rename(columns={"phase_layer": "session"})
    if "trial_window" not in out.columns and "condition_layer" in out.columns:
        out = out.rename(columns={"condition_layer": "trial_window"})
    if "trial_step" not in out.columns and "step" in out.columns:
        # legacy trial-window DA used bare ``step``
        if "session_step" not in out.columns:
            out = out.rename(columns={"step": "trial_step"})
    return out


def _volcano_xy(tests: pd.DataFrame) -> pd.DataFrame:
    t = _alias_wire(tests)
    if "hit_fdr05" in t.columns:
        t["hit"] = _as_bool(t["hit_fdr05"])
    else:
        t["hit"] = False
    t["p"] = pd.to_numeric(t["p"], errors="coerce")
    t["median_delta_p"] = pd.to_numeric(t["median_delta_p"], errors="coerce")
    t = t[np.isfinite(t["p"]) & (t["p"] > 0) & np.isfinite(t["median_delta_p"])]
    t["neglog10_p"] = np.minimum(-np.log10(t["p"].to_numpy(dtype=float)), Y_CLIP)
    if {"strain", "tx"}.issubset(t.columns):
        t["stx"] = [stx_label(a, b) for a, b in zip(t["strain"], t["tx"], strict=True)]
    return t


def _attach_cluster(tests: pd.DataFrame, sig: pd.DataFrame) -> pd.DataFrame:
    out = tests.merge(
        sig[["model", "raw_syllable_id", "cluster_id"]],
        on=["model", "raw_syllable_id"],
        how="left",
    )
    out["cluster_id"] = pd.to_numeric(out["cluster_id"], errors="coerce").fillna(-1).astype(int)
    return out


def _build_cluster_lookup(
    sig: pd.DataFrame,
) -> tuple[dict[int, tuple[float, float, float, float]], list[int], object | None]:
    summary = (
        sig[sig["cluster_id"] >= 0]
        .groupby("cluster_id", as_index=False)
        .agg(n_prototypes=("raw_syllable_id", "size"))
    )
    if summary.empty:
        return {}, [], None
    lookup, cluster_ids, listed = build_cluster_color_lookup(summary)
    return lookup, cluster_ids, listed


def _scatter_pooled_cluster_squares(
    ax,
    cell: pd.DataFrame,
    *,
    lookup: dict[int, tuple[float, float, float, float]],
    miss_s: float,
    hit_s: float,
) -> None:
    """Pooled: edge/fill = cluster_id; grey = noise; filled = FDR hit."""
    for is_hit, s, z in ((False, miss_s, 2), (True, hit_s, 3)):
        sub = cell[cell["hit"] == is_hit]
        if sub.empty:
            continue
        cols = colors_for_cluster_ids(sub["cluster_id"], lookup) if lookup else GREY_SQ
        ax.scatter(
            sub["median_delta_p"],
            sub["neglog10_p"],
            s=s,
            marker="s",
            facecolors=cols if is_hit else "none",
            edgecolors=cols,
            linewidths=0.65 if not is_hit else 0.45,
            alpha=0.88 if is_hit else 0.72,
            zorder=z,
            rasterized=True,
        )


def _scatter_pooled_grey_ghost(
    ax,
    cell: pd.DataFrame,
    *,
    miss_s: float,
    hit_s: float,
) -> None:
    for is_hit, s, alpha, z in ((False, miss_s, 0.20, 1), (True, hit_s, 0.32, 2)):
        sub = cell[cell["hit"] == is_hit]
        if sub.empty:
            continue
        ax.scatter(
            sub["median_delta_p"],
            sub["neglog10_p"],
            s=s,
            marker="s",
            facecolors=GREY_SQ if is_hit else "none",
            edgecolors=GREY_SQ,
            linewidths=0.55 if not is_hit else 0.4,
            alpha=alpha,
            zorder=z,
            rasterized=True,
        )


def _scatter_strat_stx(
    ax,
    cell: pd.DataFrame,
    *,
    pt_s: float,
) -> None:
    """4 strain×tx colors; sex = marker; filled = FDR hit; open = not."""
    for stx in STX_ORDER:
        c = STX_COLOR[stx]
        for sex in SEX_ORDER:
            mk = SEX_MARKER[sex]
            sub = cell[(cell["stx"] == stx) & (cell["sex"] == sex)]
            if sub.empty:
                continue
            for is_hit, z in ((False, 4), (True, 5)):
                g = sub[sub["hit"] == is_hit]
                if g.empty:
                    continue
                ax.scatter(
                    g["median_delta_p"],
                    g["neglog10_p"],
                    s=pt_s,
                    marker=mk,
                    facecolors=c if is_hit else "none",
                    edgecolors=c,
                    linewidths=0.55,
                    alpha=0.9,
                    zorder=z,
                    rasterized=True,
                )


def _draw_pooled_to_strat_ladders(
    ax,
    pooled: pd.DataFrame,
    strat: pd.DataFrame,
    *,
    line_alpha: float = 0.16,
    lw: float = 0.35,
) -> None:
    if pooled.empty or strat.empty:
        return
    keys = ["model", "raw_syllable_id"]
    p = pooled.drop_duplicates(keys).set_index(keys)
    for key, g in strat.groupby(keys, sort=False):
        if key not in p.index:
            continue
        x0 = float(p.loc[key, "median_delta_p"])
        y0 = float(p.loc[key, "neglog10_p"])
        xs = g["median_delta_p"].to_numpy(dtype=float)
        ys = g["neglog10_p"].to_numpy(dtype=float)
        ax.plot(
            np.column_stack([np.full(xs.shape, x0), xs]).T,
            np.column_stack([np.full(ys.shape, y0), ys]).T,
            color="#9a9a9a",
            lw=lw,
            alpha=line_alpha,
            zorder=3,
            solid_capstyle="round",
        )


def _pooled_legend_handles(*, dest: str) -> list[Line2D]:
    ms = 8 if dest == "slides" else 6
    return [
        Line2D(
            [0],
            [0],
            marker="s",
            color="none",
            markerfacecolor=GREY_SQ,
            markeredgecolor=GREY_SQ,
            markersize=ms,
            label="noise / unclustered",
        ),
        Line2D(
            [0],
            [0],
            marker="s",
            color="none",
            markerfacecolor="none",
            markeredgecolor=INK,
            markersize=ms,
            label="open = not FDR",
        ),
        Line2D(
            [0],
            [0],
            marker="s",
            color="none",
            markerfacecolor=INK,
            markeredgecolor=INK,
            markersize=ms,
            label="filled = FDR q<0.05",
        ),
    ]


def _strat_legend_handles(*, dest: str, stx: str) -> list[Line2D]:
    ms = 8 if dest == "slides" else 6
    c = STX_COLOR[stx]
    handles: list[Line2D] = [
        Line2D(
            [0],
            [0],
            marker="s",
            color="none",
            markerfacecolor=GREY_SQ,
            markeredgecolor=GREY_SQ,
            markersize=ms,
            alpha=0.35,
            label="pooled ghost □",
        ),
    ]
    for sex in SEX_ORDER:
        handles.append(
            Line2D(
                [0],
                [0],
                marker=SEX_MARKER[sex],
                color="none",
                markerfacecolor=c,
                markeredgecolor=c,
                markersize=ms,
                label=f"sex={sex}",
            )
        )
    handles.extend(
        [
            Line2D(
                [0],
                [0],
                marker="o",
                color="none",
                markerfacecolor=c,
                markeredgecolor=c,
                markersize=ms,
                label="filled = FDR q<0.05",
            ),
            Line2D(
                [0],
                [0],
                marker="o",
                color="none",
                markerfacecolor="none",
                markeredgecolor=c,
                markersize=ms,
                label="open = not FDR",
            ),
        ]
    )
    return handles


def _style_volcano_ax(
    ax,
    *,
    xlabel: bool,
    ylabel: str | None,
    title: str | None,
    ts,
    xlim: tuple[float, float],
) -> None:
    ax.axvline(0, color=MUTE, lw=0.7, ls="--", zorder=0)
    ax.set_xlim(*xlim)
    ax.set_ylim(-0.05, Y_CLIP + 0.12)
    if title:
        ax.set_title(title, fontsize=ts["annotation"], color=INK)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=ts["annotation"])
    if xlabel:
        ax.set_xlabel("median Δp", fontsize=ts["annotation"])


def load_or_build_strat_tests(
    da: Path,
    *,
    stem: str = "da_syllable_tests_strat_long.csv",
    delta_stem: str = "da_syllable_deltas_per_animal.csv",
    rebuild: bool = False,
) -> pd.DataFrame:
    dest = da / stem
    if dest.is_file() and not rebuild:
        return _alias_wire(pd.read_csv(dest, keep_default_na=False))
    delta_path = da / delta_stem
    if not delta_path.exists():
        raise FileNotFoundError(f"Need {delta_path} to build stratified DA tests")
    print(f"building stratified Wilcoxon from {delta_path.name} ...", flush=True)
    dtab = _alias_wire(pd.read_csv(delta_path, keep_default_na=False))
    tests = da_tests_cohort_strat_from_deltas(dtab, progress=True)
    tests.to_csv(dest, index=False)
    print(f"wrote {dest}  rows={len(tests)}", flush=True)
    return _alias_wire(tests)


def fig_volcano_ladder_trial_steps_pooled(
    pooled: pd.DataFrame,
    sig: pd.DataFrame,
    out: Path,
    *,
    dest: str = "slides",
) -> None:
    """Rows = trial_step, cols = session."""
    apply_style(dest=dest)
    ts = type_scale(dest)
    lookup, cluster_ids, listed = _build_cluster_lookup(sig)
    p_xy = _attach_cluster(_volcano_xy(pooled), sig)
    miss_s = 14 if dest == "slides" else 9
    hit_s = 24 if dest == "slides" else 14

    fig, axes = plt.subplots(
        3,
        5,
        figsize=(FIGSIZE_DOUBLE[0] * 1.15, FIGSIZE_DOUBLE[1] * 1.1),
        sharex=True,
        sharey=True,
    )
    for r, (step, slab) in enumerate(TRIAL_STEPS):
        for c, session in enumerate(SESSIONS):
            ax = axes[r, c]
            step_col = "trial_step" if "trial_step" in p_xy.columns else "step"
            pc = p_xy[(p_xy[step_col] == step) & (p_xy["session"] == session)]
            if pc.empty:
                ax.set_axis_off()
                continue
            _scatter_pooled_cluster_squares(
                ax, pc, lookup=lookup, miss_s=miss_s, hit_s=hit_s
            )
            n_fdr = int(pc["hit"].sum())
            ax.text(
                0.98,
                0.02,
                f"n={len(pc)}\nFDR={n_fdr}",
                transform=ax.transAxes,
                ha="right",
                va="bottom",
                fontsize=7,
                color=INK,
            )
            _style_volcano_ax(
                ax,
                xlabel=(r == 2),
                ylabel=f"{slab}\n−log10(p)" if c == 0 else None,
                title=session if r == 0 else None,
                ts=ts,
                xlim=X_LIM_POOLED,
            )

    fig.suptitle(
        "DA · trial-steps · pooled · sessions across columns",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    if listed is not None and cluster_ids:
        add_cluster_id_colorbar(fig, axes[0, -1], cluster_ids, listed, dest=dest)
    fig.legend(
        handles=_pooled_legend_handles(dest=dest),
        loc="lower center",
        ncol=3,
        frameon=False,
        fontsize=7,
        bbox_to_anchor=(0.5, -0.02),
    )
    fig_footnote(
        fig,
        "Trial-step DA (early/mid/late trial windows within session). "
        "Pooled Wilcoxon. Square color = HDBSCAN cluster_id; grey = noise. "
        "Filled = BH q<0.05 within model×session×trial_step. Interval = run only.",
        fontsize=ts["footnote"],
    )
    save_pdf_png(fig, out / "fig_da_volcano_ladder_overlay_trial_steps")


def fig_volcano_ladder_trial_steps_stratified(
    pooled: pd.DataFrame,
    strat: pd.DataFrame,
    sig: pd.DataFrame,
    out: Path,
    *,
    stx: str,
    dest: str = "slides",
) -> None:
    """One condition (strain×tx); grey pooled underlay; sex = marker."""
    if stx not in STX_COLOR:
        raise ValueError(f"unknown stx {stx!r}; expected one of {STX_ORDER}")
    apply_style(dest=dest)
    ts = type_scale(dest)
    p_xy = _attach_cluster(_volcano_xy(pooled), sig)
    s_xy = _attach_cluster(_volcano_xy(strat), sig)
    s_xy = s_xy[s_xy["stx"] == stx]
    pt_s = 22 if dest == "slides" else 14
    c = STX_COLOR[stx]

    fig, axes = plt.subplots(
        3,
        5,
        figsize=(FIGSIZE_DOUBLE[0] * 1.15, FIGSIZE_DOUBLE[1] * 1.15),
        sharex=True,
        sharey=True,
    )
    for r, (step, slab) in enumerate(TRIAL_STEPS):
        for c_i, session in enumerate(SESSIONS):
            ax = axes[r, c_i]
            step_col = "trial_step" if "trial_step" in p_xy.columns else "step"
            pc = p_xy[(p_xy[step_col] == step) & (p_xy["session"] == session)]
            sc = s_xy[(s_xy[step_col] == step) & (s_xy["session"] == session)]
            if pc.empty and sc.empty:
                ax.set_axis_off()
                continue
            _scatter_pooled_grey_ghost(ax, pc, miss_s=pt_s * 0.7, hit_s=pt_s * 0.85)
            _draw_pooled_to_strat_ladders(ax, pc, sc)
            _scatter_strat_stx(ax, sc, pt_s=pt_s)
            n_fdr_s = int(sc["hit"].sum()) if len(sc) else 0
            ax.text(
                0.98,
                0.02,
                f"n={len(sc)}\nFDR={n_fdr_s}",
                transform=ax.transAxes,
                ha="right",
                va="bottom",
                fontsize=6.5,
                color=c,
            )
            _style_volcano_ax(
                ax,
                xlabel=(r == 2),
                ylabel=f"{slab}\n−log10(p)" if c_i == 0 else None,
                title=session if r == 0 else None,
                ts=ts,
                xlim=X_LIM_STRAT,
            )

    fig.suptitle(
        f"DA · trial-steps · {stx} · grey pooled underlay",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig.legend(
        handles=_strat_legend_handles(dest=dest, stx=stx),
        loc="lower center",
        ncol=4,
        frameon=False,
        fontsize=7,
        bbox_to_anchor=(0.5, -0.04),
    )
    fig_footnote(
        fig,
        f"Trial-step DA · condition={stx}. Grey ghost = pooled Wilcoxon. "
        "Overlay = sex-stratified Wilcoxon in this strain×tx arm. "
        "Filled = BH q<0.05. Interval = run only.",
        fontsize=ts["footnote"],
    )
    save_pdf_png(fig, out / f"fig_da_volcano_ladder_stratified_trial_steps_{STX_STEM[stx]}")


def fig_volcano_ladder_session_steps_pooled(
    pooled: pd.DataFrame,
    sig: pd.DataFrame,
    out: Path,
    *,
    dest: str = "slides",
) -> None:
    """Rows = session_step, cols = trial_window."""
    apply_style(dest=dest)
    ts = type_scale(dest)
    lookup, cluster_ids, listed = _build_cluster_lookup(sig)
    p_xy = _attach_cluster(_volcano_xy(pooled), sig)
    miss_s = 14 if dest == "slides" else 9
    hit_s = 24 if dest == "slides" else 14

    fig, axes = plt.subplots(
        len(SESSION_STEPS),
        len(TRIAL_WINDOWS),
        figsize=(FIGSIZE_DOUBLE[0] * 0.95, FIGSIZE_DOUBLE[1] * 1.35),
        sharex=True,
        sharey=True,
    )
    for r, (step, slab) in enumerate(SESSION_STEPS):
        for c, tw in enumerate(TRIAL_WINDOWS):
            ax = axes[r, c]
            pc = p_xy[(p_xy["session_step"] == step) & (p_xy["trial_window"] == tw)]
            if pc.empty:
                ax.set_axis_off()
                continue
            _scatter_pooled_cluster_squares(
                ax, pc, lookup=lookup, miss_s=miss_s, hit_s=hit_s
            )
            n_fdr = int(pc["hit"].sum())
            ax.text(
                0.98,
                0.02,
                f"n={len(pc)}\nFDR={n_fdr}",
                transform=ax.transAxes,
                ha="right",
                va="bottom",
                fontsize=7,
                color=INK,
            )
            _style_volcano_ax(
                ax,
                xlabel=(r == len(SESSION_STEPS) - 1),
                ylabel=f"{slab}\n−log10(p)" if c == 0 else None,
                title=TRIAL_WINDOW_LAB[tw] if r == 0 else None,
                ts=ts,
                xlim=X_LIM_POOLED,
            )

    fig.suptitle(
        "DA · session-steps · pooled · trial windows across columns",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    if listed is not None and cluster_ids:
        add_cluster_id_colorbar(fig, axes[0, -1], cluster_ids, listed, dest=dest)
    fig.legend(
        handles=_pooled_legend_handles(dest=dest),
        loc="lower center",
        ncol=3,
        frameon=False,
        fontsize=7,
        bbox_to_anchor=(0.5, -0.02),
    )
    fig_footnote(
        fig,
        "Session-step DA (paired sessions, trial window held). "
        "Pooled Wilcoxon. Filled = BH q<0.05 within model×trial_window×session_step. "
        "Interval = run only.",
        fontsize=ts["footnote"],
    )
    save_pdf_png(fig, out / "fig_da_volcano_ladder_overlay_session_steps")


def fig_volcano_ladder_session_steps_stratified(
    pooled: pd.DataFrame,
    strat: pd.DataFrame,
    sig: pd.DataFrame,
    out: Path,
    *,
    stx: str,
    dest: str = "slides",
) -> None:
    if stx not in STX_COLOR:
        raise ValueError(f"unknown stx {stx!r}; expected one of {STX_ORDER}")
    apply_style(dest=dest)
    ts = type_scale(dest)
    p_xy = _attach_cluster(_volcano_xy(pooled), sig)
    s_xy = _attach_cluster(_volcano_xy(strat), sig)
    s_xy = s_xy[s_xy["stx"] == stx]
    pt_s = 22 if dest == "slides" else 14
    c = STX_COLOR[stx]

    fig, axes = plt.subplots(
        len(SESSION_STEPS),
        len(TRIAL_WINDOWS),
        figsize=(FIGSIZE_DOUBLE[0] * 0.95, FIGSIZE_DOUBLE[1] * 1.4),
        sharex=True,
        sharey=True,
    )
    for r, (step, slab) in enumerate(SESSION_STEPS):
        for c_i, tw in enumerate(TRIAL_WINDOWS):
            ax = axes[r, c_i]
            pc = p_xy[(p_xy["session_step"] == step) & (p_xy["trial_window"] == tw)]
            sc = s_xy[(s_xy["session_step"] == step) & (s_xy["trial_window"] == tw)]
            if pc.empty and sc.empty:
                ax.set_axis_off()
                continue
            _scatter_pooled_grey_ghost(ax, pc, miss_s=pt_s * 0.7, hit_s=pt_s * 0.85)
            _draw_pooled_to_strat_ladders(ax, pc, sc)
            _scatter_strat_stx(ax, sc, pt_s=pt_s)
            n_fdr_s = int(sc["hit"].sum()) if len(sc) else 0
            ax.text(
                0.98,
                0.02,
                f"n={len(sc)}\nFDR={n_fdr_s}",
                transform=ax.transAxes,
                ha="right",
                va="bottom",
                fontsize=6.5,
                color=c,
            )
            _style_volcano_ax(
                ax,
                xlabel=(r == len(SESSION_STEPS) - 1),
                ylabel=f"{slab}\n−log10(p)" if c_i == 0 else None,
                title=TRIAL_WINDOW_LAB[tw] if r == 0 else None,
                ts=ts,
                xlim=X_LIM_STRAT,
            )

    fig.suptitle(
        f"DA · session-steps · {stx} · grey pooled underlay",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig.legend(
        handles=_strat_legend_handles(dest=dest, stx=stx),
        loc="lower center",
        ncol=4,
        frameon=False,
        fontsize=7,
        bbox_to_anchor=(0.5, -0.03),
    )
    fig_footnote(
        fig,
        f"Session-step DA · condition={stx}. Grey ghost = pooled. "
        "Overlay = sex-stratified Wilcoxon in this strain×tx arm. "
        "Filled = BH q<0.05. Interval = run only.",
        fontsize=ts["footnote"],
    )
    save_pdf_png(fig, out / f"fig_da_volcano_ladder_stratified_session_steps_{STX_STEM[stx]}")


def fig_cluster_delta(
    med: pd.DataFrame,
    sliced: pd.DataFrame,
    out: Path,
    *,
    cluster_id: int,
    dest: str = "slides",
) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    med = _alias_wire(med)
    sliced = _alias_wire(sliced) if not sliced.empty else sliced
    rng = np.random.default_rng(0)
    fig, axes = plt.subplots(
        6, 5, figsize=(FIGSIZE_DOUBLE[0] * 1.1, FIGSIZE_DOUBLE[1] * 2.0), sharey=True
    )
    sex_rows = (("F", 0, 1, 2), ("M", 3, 4, 5))
    step_col = "trial_step" if "trial_step" in med.columns else "step"
    for sex, r0, _r1, _r2 in sex_rows:
        for r, (step, slab) in enumerate(TRIAL_STEPS):
            ax_row = r0 + r
            for c, session in enumerate(SESSIONS):
                ax = axes[ax_row, c]
                sub = med[
                    (med[step_col] == step)
                    & (med["session"] == session)
                    & (med["sex"] == sex)
                ]
                if sub.empty:
                    ax.set_axis_off()
                    continue
                for si, strain in enumerate(STRAIN_ORDER):
                    for tx in TX_ORDER:
                        g = sub[(sub["strain"] == strain) & (sub["tx"] == tx)]
                        if g.empty:
                            continue
                        x = np.full(len(g), si + (0.15 if tx == "n/a" else -0.15))
                        x = x + rng.normal(0, 0.03, size=len(g))
                        y = pd.to_numeric(g["delta_p"], errors="coerce").to_numpy(dtype=float)
                        ax.errorbar(
                            float(np.nanmedian(x)),
                            float(np.nanmedian(y)),
                            yerr=float(np.nanstd(y)) if len(y) > 1 else 0.0,
                            fmt="none",
                            ecolor=MUTE,
                            elinewidth=0.8,
                            capsize=2,
                            zorder=2,
                        )
                        ax.scatter(
                            x,
                            y,
                            s=28,
                            marker="o" if tx == "RBSF-1" else "s",
                            facecolors=STRAIN_COLOR[strain],
                            edgecolors=TX_EDGE[tx],
                            linewidths=0.7,
                            alpha=0.85,
                            zorder=3,
                        )
                ax.axhline(0, color=MUTE, lw=0.7, ls="--")
                if ax_row == r0 and c == 0:
                    ax.set_ylabel(f"{sex}\n{slab}\nΔp", fontsize=7)
                elif c == 0:
                    ax.set_ylabel(slab, fontsize=7)
                if ax_row == r0:
                    ax.set_title(session, fontsize=ts["annotation"])
                ax.set_xticks([0, 1])
                ax.set_xticklabels(["wt", "tg"], fontsize=7)

    fig.suptitle(
        f"Pause syllable Δp · trial-steps · cluster {cluster_id} "
        f"(sex rows; fill=strain, marker=tx)",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    save_pdf_png(fig, out / f"fig_cluster{cluster_id}_session_delta")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--da-dir", type=Path, default=DEFAULT_DA)
    ap.add_argument("--sig-dir", type=Path, default=DEFAULT_SIG)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--pause-cluster", type=int, default=13)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    args = ap.parse_args(argv)

    da = args.da_dir
    out = args.out_dir or (da / "figures")
    out.mkdir(parents=True, exist_ok=True)
    sig = pd.read_csv(args.sig_dir / "syllable_prototypes_clustered.csv")

    # Trial-step tables (legacy filenames still accepted).
    trial_tests = _alias_wire(
        pd.read_csv(da / "da_syllable_tests_long.csv", keep_default_na=False)
    )
    if "trial_step" not in trial_tests.columns and "step" in trial_tests.columns:
        trial_tests = trial_tests.rename(columns={"step": "trial_step"})
    trial_strat = load_or_build_strat_tests(da)
    if "trial_step" not in trial_strat.columns and "step" in trial_strat.columns:
        trial_strat = trial_strat.rename(columns={"step": "trial_step"})

    fig_volcano_ladder_trial_steps_pooled(trial_tests, sig, out, dest=args.dest)
    for stx in STX_ORDER:
        fig_volcano_ladder_trial_steps_stratified(
            trial_tests, trial_strat, sig, out, stx=stx, dest=args.dest
        )

    sess_tests_path = da / "da_session_step_tests_long.csv"
    if sess_tests_path.is_file():
        sess_tests = _alias_wire(pd.read_csv(sess_tests_path, keep_default_na=False))
        sess_strat = load_or_build_strat_tests(
            da,
            stem="da_session_step_tests_strat_long.csv",
            delta_stem="da_session_step_deltas_per_animal.csv",
        )
        fig_volcano_ladder_session_steps_pooled(sess_tests, sig, out, dest=args.dest)
        for stx in STX_ORDER:
            fig_volcano_ladder_session_steps_stratified(
                sess_tests, sess_strat, sig, out, stx=stx, dest=args.dest
            )
    else:
        print(f"skip session-step figs (missing {sess_tests_path.name})", flush=True)

    med_path = da / f"cluster{args.pause_cluster}_animal_median_delta_p.csv"
    sliced_path = da / f"cluster{args.pause_cluster}_sliced_tests.csv"
    if med_path.is_file():
        med = pd.read_csv(med_path, keep_default_na=False)
        sliced = (
            pd.read_csv(sliced_path, keep_default_na=False)
            if sliced_path.is_file()
            else pd.DataFrame()
        )
        if not sliced.empty:
            for col in ("hold_sex", "hold_strain", "hold_tx"):
                if col in sliced.columns:
                    sliced[col] = sliced[col].fillna("")
        fig_cluster_delta(med, sliced, out, cluster_id=int(args.pause_cluster), dest=args.dest)
    print(f"wrote figures -> {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
