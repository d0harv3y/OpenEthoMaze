"""Slides pack: alphabet-wide richness + Shannon (bits) — cluster-13 layout twin.

Three figure sets per metric (level / trial-step Δ / session-step Δ), each with
six-violin consensus lattice + per-model Kruskal heatmaps (same grids as
``fig_slides_pack`` cluster frame-share).

Levels reconstructed from ``presence_step_deltas_per_animal.csv``
(``{metric}_left`` / ``{metric}_right`` on presence + novelty steps; id_obj
must match — litmus). Session-step Δs from those levels (not the legacy
``BL->condition`` session_paired tokens).

Regen (OpenEthoMaze repo root)::

    uv run python scratch/nor_object_mi/alpha_composition_slides_pack.py --rebuild
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi._pub_style import (  # noqa: E402
    FIGSIZE_SLIDES,
    INK,
    SESSION_SHORT,
    SESSIONS,
    SEX_ORDER,
    apply_style,
    condition_sex_legend_handles,
    fig_legend_and_footnote,
    save_pdf_svg,
    type_scale,
)
from nor_object_mi.cluster13_frame_share import (  # noqa: E402
    SESSION_STEP_LAB,
    SESSION_STEP_NAMES,
    TRIAL_LAB,
    TRIAL_STEP_LAB,
    TRIAL_STEP_NAMES,
    animal_median_frame_share,
    kruskal_by_session_trial_sex,
    kruskal_by_session_trial_step_sex,
    kruskal_by_trial_session_step_sex,
    kruskal_per_model_level,
    kruskal_per_model_session_step,
    kruskal_per_model_trial_step,
    session_step_deltas_from_levels,
    session_step_deltas_model_long,
    short_model_label,
    trial_step_deltas_from_levels,
    trial_step_deltas_model_long,
)
from nor_object_mi.fig_slides_pack import (  # noqa: E402
    NLP_VMAX,
    SEX_LAB,
    _annotate_fm,
    _draw_condition_sex_violins,
    _imshow_model_x,
    _model_x_mats,
    _y_lim_from,
    fig_per_model_kruskal_heatmap,
)
from nor_object_mi.simpler_first_presence import TRIALS  # noqa: E402

DEFAULT_PACK_ROOT = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\slides_pack"
)
DEFAULT_PRESENCE = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_presence_steps\presence_step_deltas_per_animal.csv"
)

METRICS: tuple[str, ...] = ("richness", "shannon_bits")
METRIC_LAB: dict[str, str] = {
    "richness": "richness",
    "shannon_bits": "Shannon (bits)",
}
METRIC_TITLE: dict[str, str] = {
    "richness": "Syllable richness",
    "shannon_bits": "Shannon entropy (bits)",
}
METRIC_DELTA_LAB: dict[str, str] = {
    "richness": "Δ richness",
    "shannon_bits": "Δ Shannon (bits)",
}
METRIC_PACK: dict[str, str] = {
    "richness": "richness",
    "shannon_bits": "shannon",
}


def levels_long_from_presence(deltas: pd.DataFrame, *, metric: str) -> pd.DataFrame:
    """Stack absolute scalar levels for no_obj / id_obj / nvl_obj.

    Presence step supplies left=no_obj, right=id_obj; novelty supplies
    left=id_obj, right=nvl_obj. ``id_obj`` must agree (litmus).
    """
    if metric not in METRICS:
        raise ValueError(f"unknown metric {metric!r}; expected one of {METRICS}")
    left_c = f"{metric}_left"
    right_c = f"{metric}_right"
    need = {
        "model",
        "animal_id",
        "sex",
        "condition",
        "session",
        "step",
        left_c,
        right_c,
    }
    missing = need - set(deltas.columns)
    if missing:
        raise ValueError(f"levels_long_from_presence missing: {sorted(missing)}")

    pres = deltas[deltas["step"] == "no_obj->id_obj"]
    nov = deltas[deltas["step"] == "id_obj->nvl_obj"]
    join_keys = ["model", "animal_id", "sex", "condition", "session"]
    j = pres.merge(nov, on=join_keys, how="inner", suffixes=("_pres", "_nov"))
    if j.empty:
        return pd.DataFrame(columns=[*join_keys, "trial", "p"])

    id_diff = (
        pd.to_numeric(j[f"{right_c}_pres"], errors="coerce")
        - pd.to_numeric(j[f"{left_c}_nov"], errors="coerce")
    ).abs()
    if float(np.nanmax(id_diff.to_numpy(dtype=np.float64))) > 1e-9:
        raise ValueError(f"id_obj {metric} disagrees between presence and novelty steps")

    base = j[join_keys].copy()
    parts = [
        base.assign(trial="no_obj", p=pd.to_numeric(j[f"{left_c}_pres"], errors="coerce")),
        base.assign(trial="id_obj", p=pd.to_numeric(j[f"{right_c}_pres"], errors="coerce")),
        base.assign(trial="nvl_obj", p=pd.to_numeric(j[f"{right_c}_nov"], errors="coerce")),
    ]
    out = pd.concat(parts, ignore_index=True)
    out["trial"] = pd.Categorical(out["trial"], categories=list(TRIALS), ordered=True)
    return out


def build_metric_pack(deltas: pd.DataFrame, *, metric: str) -> dict[str, pd.DataFrame]:
    """Level + trial-step + session-step + per-model Kruskal for one scalar."""
    levels = levels_long_from_presence(deltas, metric=metric)
    med = animal_median_frame_share(levels)
    kr_level = kruskal_by_session_trial_sex(med, col="p")

    trial_model = trial_step_deltas_model_long(levels)
    trial_d = trial_step_deltas_from_levels(levels)
    kr_trial = kruskal_by_session_trial_step_sex(trial_d, col="delta_p")

    session_model = session_step_deltas_model_long(levels)
    session_d = session_step_deltas_from_levels(levels)
    kr_session = kruskal_by_trial_session_step_sex(session_d, col="delta_p")

    models = sorted(str(x) for x in levels["model"].unique())
    return {
        "levels_model": levels,
        "animal_level": med,
        "kruskal_level": kr_level,
        "trial_step_delta": trial_d,
        "kruskal_trial_step": kr_trial,
        "session_step_delta": session_d,
        "kruskal_session_step": kr_session,
        "kruskal_per_model_level": kruskal_per_model_level(levels, col="p"),
        "kruskal_per_model_trial_step": kruskal_per_model_trial_step(trial_model, col="delta_p"),
        "kruskal_per_model_session_step": kruskal_per_model_session_step(session_model, col="delta_p"),
        "model_labels": pd.DataFrame({"model": models, "label": [short_model_label(m) for m in models]}),
        "metric": metric,
    }


def _pack_csv_names(metric: str) -> dict[str, str]:
    p = METRIC_PACK[metric]
    return {
        "animal": f"{p}_animal_level.csv",
        "kruskal": f"{p}_level_kruskal.csv",
        "trial_step": f"{p}_trial_step_delta.csv",
        "trial_step_kr": f"{p}_trial_step_kruskal.csv",
        "session_step": f"{p}_session_step_delta.csv",
        "session_step_kr": f"{p}_session_step_kruskal.csv",
        "model_level_kr": f"{p}_per_model_level_kruskal.csv",
        "model_trial_kr": f"{p}_per_model_trial_step_kruskal.csv",
        "model_session_kr": f"{p}_per_model_session_step_kruskal.csv",
        "model_labels": f"{p}_model_labels.csv",
        "levels_model": f"{p}_levels_model.csv",
    }


def _fig_stem(metric: str, suffix: str) -> str:
    return f"fig_{METRIC_PACK[metric]}_{suffix}"


def _foot_level(metric: str) -> str:
    lab = METRIC_LAB[metric]
    return (
        f"Grain: animal × session × trial. Point = median alphabet-wide {lab} "
        "across 21 kpMS models; whiskers = ±½ across-model IQR (salt), not SEM. "
        "Six violins = condition × sex (F then M). Kruskal within sex; * = BH "
        "q < 0.05 in the 24-cell family. Not cluster frame share; not paired Δ; "
        "not Wilcoxon vs 0."
    )


def _foot_trial(metric: str) -> str:
    lab = METRIC_DELTA_LAB[metric]
    return (
        f"Grain: animal × session × trial_step (prose: phase-step). Point = median "
        f"paired {lab} (right − left trial) across 21 kpMS models; whiskers = ±½ "
        "across-model IQR. Kruskal on Δ ~ condition within sex; * = BH q < 0.05 "
        "in the 24-cell family. Not Wilcoxon vs 0; not raw level."
    )


def _foot_session(metric: str) -> str:
    lab = METRIC_DELTA_LAB[metric]
    return (
        f"Grain: animal × trial × session_step (prose: stage-step). Point = median "
        f"paired {lab} (right − left session) across 21 kpMS models; whiskers = ±½ "
        "across-model IQR. Kruskal on Δ ~ condition within sex; * = BH q < 0.05 "
        "in the 36-cell family. Not Wilcoxon vs 0; not raw level."
    )


FOOT_MODEL_LEVEL = (
    "Per-model Kruskal on level ~ condition within sex. Panel grid: rows = trial "
    "(phase), cols = sex. Heatmap: y = kpMS model, x = session (stage). Color = "
    "−log₁₀(uncorrected p), clip 4; * = BH q < 0.05 within the panel "
    "(model × session)."
)
FOOT_MODEL_TRIAL = (
    "Per-model Kruskal on paired phase-step Δ ~ condition within sex. Panel grid: "
    "rows = trial_step (phase-step), cols = sex. Heatmap: y = kpMS model, "
    "x = session. Color = −log₁₀(p), clip 4; * = BH q < 0.05 within panel."
)
FOOT_MODEL_SESSION = (
    "Per-model Kruskal on paired stage-step Δ ~ condition within sex. Panel grid: "
    "rows = trial (phase), cols = sex. Heatmap: y = kpMS model, x = session_step. "
    "Color = −log₁₀(p), clip 4; * = BH q < 0.05 within panel."
)


def write_pack_csvs(pack: Path, tables: dict[str, pd.DataFrame], *, metric: str) -> None:
    pack.mkdir(parents=True, exist_ok=True)
    names = _pack_csv_names(metric)
    writes = (
        (names["animal"], tables["animal_level"]),
        (names["kruskal"], tables["kruskal_level"]),
        (names["trial_step"], tables["trial_step_delta"]),
        (names["trial_step_kr"], tables["kruskal_trial_step"]),
        (names["session_step"], tables["session_step_delta"]),
        (names["session_step_kr"], tables["kruskal_session_step"]),
        (names["model_level_kr"], tables["kruskal_per_model_level"]),
        (names["model_trial_kr"], tables["kruskal_per_model_trial_step"]),
        (names["model_session_kr"], tables["kruskal_per_model_session_step"]),
        (names["model_labels"], tables["model_labels"]),
        (names["levels_model"], tables["levels_model"]),
    )
    for name, df in writes:
        df.to_csv(pack / name, index=False)
        print(f"wrote {pack / name}  n={len(df)}", flush=True)


def load_pack_csvs(pack: Path, *, metric: str) -> dict[str, pd.DataFrame]:
    names = _pack_csv_names(metric)
    return {
        "animal_level": pd.read_csv(pack / names["animal"]),
        "kruskal_level": pd.read_csv(pack / names["kruskal"]),
        "trial_step_delta": pd.read_csv(pack / names["trial_step"]),
        "kruskal_trial_step": pd.read_csv(pack / names["trial_step_kr"]),
        "session_step_delta": pd.read_csv(pack / names["session_step"]),
        "kruskal_session_step": pd.read_csv(pack / names["session_step_kr"]),
        "kruskal_per_model_level": pd.read_csv(pack / names["model_level_kr"]),
        "kruskal_per_model_trial_step": pd.read_csv(pack / names["model_trial_kr"]),
        "kruskal_per_model_session_step": pd.read_csv(pack / names["model_session_kr"]),
        "model_labels": pd.read_csv(pack / names["model_labels"]),
        "metric": metric,
    }


def fig_level(med: pd.DataFrame, kr: pd.DataFrame, out: Path, *, dest: str, metric: str) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    fig_w, fig_h = FIGSIZE_SLIDES if dest == "slides" else (7.2, 8.0)
    fig = plt.figure(figsize=(fig_w * 1.08, fig_h + 0.8))
    gs = fig.add_gridspec(
        len(TRIALS),
        len(SESSIONS),
        left=0.07,
        right=0.98,
        top=0.88,
        bottom=0.22,
        hspace=0.42,
        wspace=0.30,
    )
    rng = np.random.default_rng(0)
    y_lim = _y_lim_from(med, "p")
    violin_axes: list = []
    for i, trial in enumerate(TRIALS):
        for j, session in enumerate(SESSIONS):
            ax = fig.add_subplot(gs[i, j], sharey=violin_axes[0] if violin_axes else None)
            violin_axes.append(ax)
            panel = med[(med["session"] == session) & (med["trial"] == trial)]
            _draw_condition_sex_violins(
                ax, panel, dest=dest, rng=rng, xlabel=(i == len(TRIALS) - 1), ycol="p"
            )
            ax.set_ylim(*y_lim)
            _annotate_fm(ax, kr, filters={"session": session, "trial": trial}, dest=dest)
            if i == 0:
                ax.set_title(SESSION_SHORT[session], loc="left", fontweight="bold", color=INK)
            if j == 0:
                ax.set_ylabel(f"{TRIAL_LAB[trial]}\n{METRIC_LAB[metric]}")
    fig.suptitle(
        f"{METRIC_TITLE[metric]} by condition × sex  (six violins)",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_legend_and_footnote(fig, condition_sex_legend_handles(dest=dest), _foot_level(metric), dest=dest)
    save_pdf_svg(fig, out / _fig_stem(metric, "level_by_sex"))


def fig_trial_step(med: pd.DataFrame, kr: pd.DataFrame, out: Path, *, dest: str, metric: str) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    fig_w, fig_h = FIGSIZE_SLIDES if dest == "slides" else (7.2, 8.0)
    fig = plt.figure(figsize=(fig_w * 1.08, fig_h + 0.8))
    gs = fig.add_gridspec(
        len(TRIAL_STEP_NAMES),
        len(SESSIONS),
        left=0.07,
        right=0.98,
        top=0.88,
        bottom=0.22,
        hspace=0.42,
        wspace=0.30,
    )
    rng = np.random.default_rng(0)
    y_lim = _y_lim_from(med, "delta_p")
    violin_axes: list = []
    for i, step in enumerate(TRIAL_STEP_NAMES):
        for j, session in enumerate(SESSIONS):
            ax = fig.add_subplot(gs[i, j], sharey=violin_axes[0] if violin_axes else None)
            violin_axes.append(ax)
            panel = med[(med["session"] == session) & (med["trial_step"] == step)]
            _draw_condition_sex_violins(
                ax,
                panel,
                dest=dest,
                rng=rng,
                xlabel=(i == len(TRIAL_STEP_NAMES) - 1),
                ycol="delta_p",
                zero_line=True,
            )
            ax.set_ylim(*y_lim)
            _annotate_fm(ax, kr, filters={"session": session, "trial_step": step}, dest=dest)
            if i == 0:
                ax.set_title(SESSION_SHORT[session], loc="left", fontweight="bold", color=INK)
            if j == 0:
                ax.set_ylabel(f"{TRIAL_STEP_LAB[step]}\n{METRIC_DELTA_LAB[metric]}")
    fig.suptitle(
        f"{METRIC_DELTA_LAB[metric]} by trial-step × condition × sex",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_legend_and_footnote(fig, condition_sex_legend_handles(dest=dest), _foot_trial(metric), dest=dest)
    save_pdf_svg(fig, out / _fig_stem(metric, "trial_step_delta_by_sex"))


def fig_session_step(med: pd.DataFrame, kr: pd.DataFrame, out: Path, *, dest: str, metric: str) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    fig_w = 14.5 if dest == "slides" else 10.0
    fig_h = 7.8 if dest == "slides" else 6.5
    fig = plt.figure(figsize=(fig_w, fig_h))
    gs = fig.add_gridspec(
        len(TRIALS),
        len(SESSION_STEP_NAMES),
        left=0.06,
        right=0.99,
        top=0.88,
        bottom=0.22,
        hspace=0.45,
        wspace=0.28,
    )
    rng = np.random.default_rng(0)
    y_lim = _y_lim_from(med, "delta_p")
    violin_axes: list = []
    for i, trial in enumerate(TRIALS):
        for j, step in enumerate(SESSION_STEP_NAMES):
            ax = fig.add_subplot(gs[i, j], sharey=violin_axes[0] if violin_axes else None)
            violin_axes.append(ax)
            panel = med[(med["trial"] == trial) & (med["session_step"] == step)]
            _draw_condition_sex_violins(
                ax,
                panel,
                dest=dest,
                rng=rng,
                xlabel=(i == len(TRIALS) - 1),
                ycol="delta_p",
                zero_line=True,
            )
            ax.set_ylim(*y_lim)
            _annotate_fm(ax, kr, filters={"trial": trial, "session_step": step}, dest=dest)
            if i == 0:
                ax.set_title(SESSION_STEP_LAB[step], loc="left", fontweight="bold", color=INK)
            if j == 0:
                ax.set_ylabel(f"{TRIAL_LAB[trial]}\n{METRIC_DELTA_LAB[metric]}")
    fig.suptitle(
        f"{METRIC_DELTA_LAB[metric]} by session-step × condition × sex",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_legend_and_footnote(fig, condition_sex_legend_handles(dest=dest), _foot_session(metric), dest=dest)
    save_pdf_svg(fig, out / _fig_stem(metric, "session_step_delta_by_sex"))


def fig_combined_level(
    med: pd.DataFrame,
    kr: pd.DataFrame,
    kr_model: pd.DataFrame,
    labels: pd.DataFrame,
    out: Path,
    *,
    dest: str,
    metric: str,
) -> None:
    """3×4 violins | 3×2 per-model heatmaps (matches pause-share slide layout)."""
    apply_style(dest=dest)
    ts = type_scale(dest)
    fig_w = 18.0 if dest == "slides" else 14.0
    fig_h = 8.2 if dest == "slides" else 7.0
    fig = plt.figure(figsize=(fig_w, fig_h))
    outer = fig.add_gridspec(1, 2, width_ratios=[1.55, 1.0], left=0.05, right=0.93, top=0.88, bottom=0.16, wspace=0.18)
    gs_v = outer[0].subgridspec(len(TRIALS), len(SESSIONS), hspace=0.42, wspace=0.28)
    gs_h = outer[1].subgridspec(len(TRIALS), len(SEX_ORDER), hspace=0.35, wspace=0.12)

    rng = np.random.default_rng(0)
    y_lim = _y_lim_from(med, "p")
    violin_axes: list = []
    for i, trial in enumerate(TRIALS):
        for j, session in enumerate(SESSIONS):
            ax = fig.add_subplot(gs_v[i, j], sharey=violin_axes[0] if violin_axes else None)
            violin_axes.append(ax)
            panel = med[(med["session"] == session) & (med["trial"] == trial)]
            _draw_condition_sex_violins(
                ax, panel, dest=dest, rng=rng, xlabel=(i == len(TRIALS) - 1), ycol="p"
            )
            ax.set_ylim(*y_lim)
            _annotate_fm(ax, kr, filters={"session": session, "trial": trial}, dest=dest)
            if i == 0:
                ax.set_title(SESSION_SHORT[session], loc="left", fontweight="bold", color=INK)
            if j == 0:
                ax.set_ylabel(f"{TRIAL_LAB[trial]}\n{METRIC_LAB[metric]}")

    lab_map = dict(zip(labels["model"].astype(str), labels["label"].astype(str)))
    models = sorted(str(x) for x in kr_model["model"].unique())
    y_labels = [lab_map.get(m, m.split("_")[-1][:12]) for m in models]
    x_labels = [SESSION_SHORT[s] for s in SESSIONS]
    im = None
    for i, trial in enumerate(TRIALS):
        for j, sex in enumerate(SEX_ORDER):
            ax = fig.add_subplot(gs_h[i, j])
            pmat, hits = _model_x_mats(
                kr_model,
                models=models,
                x_values=list(SESSIONS),
                x_col="session",
                row_value=trial,
                row_col="trial",
                sex=sex,
            )
            im = _imshow_model_x(
                ax,
                pmat,
                hits,
                y_labels=y_labels,
                x_labels=x_labels,
                title=SEX_LAB[sex] if i == 0 else "",
                ts=ts,
                show_ylabel=(j == 0),
                ylabel="model" if j == 0 else "",
            )
            if j == 0:
                ax.set_ylabel(f"{TRIAL_LAB[trial]}\nmodel", fontsize=ts["annotation"])

    cax = fig.add_axes([0.945, 0.28, 0.012, 0.45])
    fig.colorbar(im, cax=cax, label="−log₁₀(p)  (clip 4)")
    fig.suptitle(
        f"{METRIC_TITLE[metric]} by condition × sex  (six violins)  ·  "
        f"Per-model Kruskal on {METRIC_LAB[metric]} ~ condition",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_legend_and_footnote(
        fig,
        condition_sex_legend_handles(dest=dest),
        _foot_level(metric) + "  " + FOOT_MODEL_LEVEL,
        dest=dest,
    )
    save_pdf_svg(fig, out / _fig_stem(metric, "level_combined"))


def fig_combined_trial_step(
    med: pd.DataFrame,
    kr: pd.DataFrame,
    kr_model: pd.DataFrame,
    labels: pd.DataFrame,
    out: Path,
    *,
    dest: str,
    metric: str,
) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    fig_w = 18.0 if dest == "slides" else 14.0
    fig_h = 8.2 if dest == "slides" else 7.0
    fig = plt.figure(figsize=(fig_w, fig_h))
    outer = fig.add_gridspec(1, 2, width_ratios=[1.55, 1.0], left=0.05, right=0.93, top=0.88, bottom=0.16, wspace=0.18)
    gs_v = outer[0].subgridspec(len(TRIAL_STEP_NAMES), len(SESSIONS), hspace=0.42, wspace=0.28)
    gs_h = outer[1].subgridspec(len(TRIAL_STEP_NAMES), len(SEX_ORDER), hspace=0.35, wspace=0.12)

    rng = np.random.default_rng(0)
    y_lim = _y_lim_from(med, "delta_p")
    violin_axes: list = []
    for i, step in enumerate(TRIAL_STEP_NAMES):
        for j, session in enumerate(SESSIONS):
            ax = fig.add_subplot(gs_v[i, j], sharey=violin_axes[0] if violin_axes else None)
            violin_axes.append(ax)
            panel = med[(med["session"] == session) & (med["trial_step"] == step)]
            _draw_condition_sex_violins(
                ax,
                panel,
                dest=dest,
                rng=rng,
                xlabel=(i == len(TRIAL_STEP_NAMES) - 1),
                ycol="delta_p",
                zero_line=True,
            )
            ax.set_ylim(*y_lim)
            _annotate_fm(ax, kr, filters={"session": session, "trial_step": step}, dest=dest)
            if i == 0:
                ax.set_title(SESSION_SHORT[session], loc="left", fontweight="bold", color=INK)
            if j == 0:
                ax.set_ylabel(f"{TRIAL_STEP_LAB[step]}\n{METRIC_DELTA_LAB[metric]}")

    lab_map = dict(zip(labels["model"].astype(str), labels["label"].astype(str)))
    models = sorted(str(x) for x in kr_model["model"].unique())
    y_labels = [lab_map.get(m, m.split("_")[-1][:12]) for m in models]
    x_labels = [SESSION_SHORT[s] for s in SESSIONS]
    im = None
    for i, step in enumerate(TRIAL_STEP_NAMES):
        for j, sex in enumerate(SEX_ORDER):
            ax = fig.add_subplot(gs_h[i, j])
            pmat, hits = _model_x_mats(
                kr_model,
                models=models,
                x_values=list(SESSIONS),
                x_col="session",
                row_value=step,
                row_col="trial_step",
                sex=sex,
            )
            im = _imshow_model_x(
                ax,
                pmat,
                hits,
                y_labels=y_labels,
                x_labels=x_labels,
                title=SEX_LAB[sex] if i == 0 else "",
                ts=ts,
                show_ylabel=(j == 0),
                ylabel="",
            )
            if j == 0:
                ax.set_ylabel(f"{TRIAL_STEP_LAB[step]}\nmodel", fontsize=ts["annotation"])

    cax = fig.add_axes([0.945, 0.28, 0.012, 0.45])
    fig.colorbar(im, cax=cax, label="−log₁₀(p)  (clip 4)")
    fig.suptitle(
        f"{METRIC_DELTA_LAB[metric]} by trial-step × condition × sex  ·  "
        f"Per-model Kruskal on phase-step Δ ~ condition",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_legend_and_footnote(
        fig,
        condition_sex_legend_handles(dest=dest),
        _foot_trial(metric) + "  " + FOOT_MODEL_TRIAL,
        dest=dest,
    )
    save_pdf_svg(fig, out / _fig_stem(metric, "trial_step_delta_combined"))


def fig_combined_session_step(
    med: pd.DataFrame,
    kr: pd.DataFrame,
    kr_model: pd.DataFrame,
    labels: pd.DataFrame,
    out: Path,
    *,
    dest: str,
    metric: str,
) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    fig_w = 20.0 if dest == "slides" else 15.0
    fig_h = 8.0 if dest == "slides" else 6.8
    fig = plt.figure(figsize=(fig_w, fig_h))
    outer = fig.add_gridspec(1, 2, width_ratios=[1.9, 1.0], left=0.045, right=0.93, top=0.88, bottom=0.16, wspace=0.14)
    gs_v = outer[0].subgridspec(len(TRIALS), len(SESSION_STEP_NAMES), hspace=0.42, wspace=0.22)
    gs_h = outer[1].subgridspec(len(TRIALS), len(SEX_ORDER), hspace=0.35, wspace=0.12)

    rng = np.random.default_rng(0)
    y_lim = _y_lim_from(med, "delta_p")
    violin_axes: list = []
    for i, trial in enumerate(TRIALS):
        for j, step in enumerate(SESSION_STEP_NAMES):
            ax = fig.add_subplot(gs_v[i, j], sharey=violin_axes[0] if violin_axes else None)
            violin_axes.append(ax)
            panel = med[(med["trial"] == trial) & (med["session_step"] == step)]
            _draw_condition_sex_violins(
                ax,
                panel,
                dest=dest,
                rng=rng,
                xlabel=(i == len(TRIALS) - 1),
                ycol="delta_p",
                zero_line=True,
            )
            ax.set_ylim(*y_lim)
            _annotate_fm(ax, kr, filters={"trial": trial, "session_step": step}, dest=dest)
            if i == 0:
                ax.set_title(SESSION_STEP_LAB[step], loc="left", fontweight="bold", color=INK)
            if j == 0:
                ax.set_ylabel(f"{TRIAL_LAB[trial]}\n{METRIC_DELTA_LAB[metric]}")

    lab_map = dict(zip(labels["model"].astype(str), labels["label"].astype(str)))
    models = sorted(str(x) for x in kr_model["model"].unique())
    y_labels = [lab_map.get(m, m.split("_")[-1][:12]) for m in models]
    x_labels = [SESSION_STEP_LAB[s] for s in SESSION_STEP_NAMES]
    im = None
    for i, trial in enumerate(TRIALS):
        for j, sex in enumerate(SEX_ORDER):
            ax = fig.add_subplot(gs_h[i, j])
            pmat, hits = _model_x_mats(
                kr_model,
                models=models,
                x_values=list(SESSION_STEP_NAMES),
                x_col="session_step",
                row_value=trial,
                row_col="trial",
                sex=sex,
            )
            im = _imshow_model_x(
                ax,
                pmat,
                hits,
                y_labels=y_labels,
                x_labels=x_labels,
                title=SEX_LAB[sex] if i == 0 else "",
                ts=ts,
                show_ylabel=(j == 0),
                ylabel="",
            )
            if j == 0:
                ax.set_ylabel(f"{TRIAL_LAB[trial]}\nmodel", fontsize=ts["annotation"])

    cax = fig.add_axes([0.945, 0.28, 0.012, 0.45])
    fig.colorbar(im, cax=cax, label="−log₁₀(p)  (clip 4)")
    fig.suptitle(
        f"{METRIC_DELTA_LAB[metric]} by session-step × condition × sex  ·  "
        f"Per-model Kruskal on stage-step Δ ~ condition",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_legend_and_footnote(
        fig,
        condition_sex_legend_handles(dest=dest),
        _foot_session(metric) + "  " + FOOT_MODEL_SESSION,
        dest=dest,
    )
    save_pdf_svg(fig, out / _fig_stem(metric, "session_step_delta_combined"))


def write_info_md(pack: Path, *, metric: str) -> None:
    names = _pack_csv_names(metric)
    lab = METRIC_LAB[metric]
    text = f"""# INFO — slides pack: alphabet-wide {lab}

Same three lattices as the HDBSCAN cluster frame-share packs (level /
phase-step Δ / stage-step Δ + per-model Kruskal), on **alphabet-wide**
COUNT/UNCERTAINTY scalars (not a single syllable cluster).

| | |
| --- | --- |
| These files | `{pack.as_posix()}` |
| Dest | slides |
| How regenerated | `uv run python scratch/nor_object_mi/alpha_composition_slides_pack.py --rebuild --metrics {metric}` |

**kpMS** = keypoint-MoSeq. **BH** = Benjamini–Hochberg. **Kruskal** =
Kruskal–Wallis. **Shannon** = abundance uncertainty H = −∑ p log₂ p (bits).

## Questions

1. **Level:** Within sex, does **condition** change {lab} at each
   `session × trial`?
2. **Trial-step** (prose *phase-step*): Within sex, does condition modulate the
   paired Δ across trials inside a session?
3. **Session-step** (prose *stage-step*): Within sex, does condition modulate the
   paired Δ across sessions inside a trial?

## Grain

| Family | Point | Value |
| ------ | ----- | ----- |
| level | animal × session × trial | median {lab} across 21 models |
| trial_step | animal × session × trial_step | median paired Δ across models |
| session_step | animal × trial × session_step | median paired Δ across models |

Whiskers = ±½ IQR across models (salt), not SEM.

**Hit rule:** BH `q_bh < 0.05` within each family's cell grid (level & trial_step:
24; session_step: 36).

**What this is not:** not cluster-13 frame share; not DR; not Wilcoxon vs 0 as
the panel claim.

## Artifacts

| File | Unit |
| ---- | ---- |
| `{names["animal"]}` | animal × session × trial |
| `{names["kruskal"]}` | session × trial × sex |
| `{names["trial_step"]}` | animal × session × trial_step |
| `{names["session_step"]}` | animal × trial × session_step |
| `figures/{_fig_stem(metric, "level_combined")}.{{pdf,svg}}` | violins + per-model heatmap |
| `figures/{_fig_stem(metric, "trial_step_delta_combined")}.{{pdf,svg}}` | phase-step combined |
| `figures/{_fig_stem(metric, "session_step_delta_combined")}.{{pdf,svg}}` | stage-step combined |

## Source (rebuild only)

| Upstream | Use |
| -------- | --- |
| `simpler_first_presence_steps/presence_step_deltas_per_animal.csv` | `{metric}_left` / `{metric}_right` |
"""
    (pack / "INFO_slides_pack.md").write_text(text, encoding="utf-8")
    print(f"wrote {pack / 'INFO_slides_pack.md'}")


def write_figures_md(out: Path, *, metric: str) -> None:
    text = f"""# Figures — {METRIC_LAB[metric]} (slides pack)

Complementary to `../INFO_slides_pack.md`. Dest = slides.

| Stem | Question | Layout | D/I |
| ---- | -------- | ------ | --- |
| `{_fig_stem(metric, "level_combined")}` | Condition × sex on level? | 3×4 violins + 3×2 heatmaps | D + Kruskal |
| `{_fig_stem(metric, "trial_step_delta_combined")}` | Phase-step Δ modulated by condition? | 3×4 + 3×2 | D + Kruskal on Δ |
| `{_fig_stem(metric, "session_step_delta_combined")}` | Stage-step Δ modulated by condition? | 3×6 + 3×2 | D + Kruskal on Δ |
| `{_fig_stem(metric, "level_by_sex")}` | Level only | 3×4 violins | D + Kruskal |
| `{_fig_stem(metric, "per_model_level_kruskal")}` | Per-model level | 3×2 heatmaps | I |

## Regen

```powershell
uv run python scratch/nor_object_mi/alpha_composition_slides_pack.py --rebuild --metrics {metric}
```
"""
    out.mkdir(parents=True, exist_ok=True)
    (out / "FIGURES.md").write_text(text, encoding="utf-8")
    print(f"wrote {out / 'FIGURES.md'}")


def run_one_metric(
    *,
    pack_root: Path,
    presence_csv: Path,
    metric: str,
    dest: str,
    rebuild: bool,
) -> None:
    pack = pack_root / METRIC_PACK[metric]
    out = pack / "figures"
    out.mkdir(parents=True, exist_ok=True)
    names = _pack_csv_names(metric)
    needed = tuple(v for k, v in names.items() if k != "levels_model")
    print(f"=== {metric} -> {pack} ===", flush=True)
    if rebuild or any(not (pack / name).exists() for name in needed):
        print(f"reading {presence_csv} ...", flush=True)
        deltas = pd.read_csv(presence_csv)
        tables = build_metric_pack(deltas, metric=metric)
        write_pack_csvs(pack, tables, metric=metric)
    else:
        tables = load_pack_csvs(pack, metric=metric)

    fig_level(tables["animal_level"], tables["kruskal_level"], out, dest=dest, metric=metric)
    fig_trial_step(
        tables["trial_step_delta"], tables["kruskal_trial_step"], out, dest=dest, metric=metric
    )
    fig_session_step(
        tables["session_step_delta"], tables["kruskal_session_step"], out, dest=dest, metric=metric
    )
    fig_combined_level(
        tables["animal_level"],
        tables["kruskal_level"],
        tables["kruskal_per_model_level"],
        tables["model_labels"],
        out,
        dest=dest,
        metric=metric,
    )
    fig_combined_trial_step(
        tables["trial_step_delta"],
        tables["kruskal_trial_step"],
        tables["kruskal_per_model_trial_step"],
        tables["model_labels"],
        out,
        dest=dest,
        metric=metric,
    )
    fig_combined_session_step(
        tables["session_step_delta"],
        tables["kruskal_session_step"],
        tables["kruskal_per_model_session_step"],
        tables["model_labels"],
        out,
        dest=dest,
        metric=metric,
    )
    fig_per_model_kruskal_heatmap(
        tables["kruskal_per_model_level"],
        tables["model_labels"],
        out,
        dest=dest,
        row_col="trial",
        row_values=list(TRIALS),
        row_lab=TRIAL_LAB,
        x_col="session",
        x_values=list(SESSIONS),
        x_lab=SESSION_SHORT,
        stem=_fig_stem(metric, "per_model_level_kruskal"),
        title=f"Per-model Kruskal on {METRIC_LAB[metric]} ~ condition",
        footnote=FOOT_MODEL_LEVEL,
    )
    fig_per_model_kruskal_heatmap(
        tables["kruskal_per_model_trial_step"],
        tables["model_labels"],
        out,
        dest=dest,
        row_col="trial_step",
        row_values=list(TRIAL_STEP_NAMES),
        row_lab=TRIAL_STEP_LAB,
        x_col="session",
        x_values=list(SESSIONS),
        x_lab=SESSION_SHORT,
        stem=_fig_stem(metric, "per_model_trial_step_kruskal"),
        title=f"Per-model Kruskal on phase-step {METRIC_DELTA_LAB[metric]} ~ condition",
        footnote=FOOT_MODEL_TRIAL,
    )
    fig_per_model_kruskal_heatmap(
        tables["kruskal_per_model_session_step"],
        tables["model_labels"],
        out,
        dest=dest,
        row_col="trial",
        row_values=list(TRIALS),
        row_lab=TRIAL_LAB,
        x_col="session_step",
        x_values=list(SESSION_STEP_NAMES),
        x_lab=SESSION_STEP_LAB,
        stem=_fig_stem(metric, "per_model_session_step_kruskal"),
        title=f"Per-model Kruskal on stage-step {METRIC_DELTA_LAB[metric]} ~ condition",
        footnote=FOOT_MODEL_SESSION,
    )
    write_info_md(pack, metric=metric)
    write_figures_md(out, metric=metric)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pack-root", type=Path, default=DEFAULT_PACK_ROOT)
    ap.add_argument("--presence-csv", type=Path, default=DEFAULT_PRESENCE)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    ap.add_argument(
        "--metrics",
        type=str,
        default=",".join(METRICS),
        help="Comma-separated: richness,shannon_bits",
    )
    ap.add_argument("--rebuild", action="store_true", help="Rebuild pack CSVs from presence deltas")
    args = ap.parse_args(argv)
    metrics = [m.strip() for m in args.metrics.split(",") if m.strip()]
    for m in metrics:
        if m not in METRICS:
            raise SystemExit(f"unknown metric {m!r}; choose from {METRICS}")
    for m in metrics:
        run_one_metric(
            pack_root=args.pack_root,
            presence_csv=args.presence_csv,
            metric=m,
            dest=args.dest,
            rebuild=args.rebuild,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
