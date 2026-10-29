"""Slides pack: paired Bray–Curtis (abundance difference) — step lattices only.

**Not** a non-step level pack: BC needs two compositions. Level options deferred:
(1) BC to a reference composition; (2) among-animal β / PERMANOVA.

Ships trial-step (phase-step) + session-step (stage-step) consensus violins and
per-model Kruskal heatmaps, same grids as richness/Shannon step figures.

Sources:
- trial-step: ``presence_step_deltas_per_animal.csv`` column ``braycurtis``
- session-step: ``session_paired_deltas_per_animal.csv`` column ``braycurtis``
  (legacy ``BL->condition`` tokens remapped to ``BL->TX``)

Regen (OpenEthoMaze repo root)::

    uv run python scratch/nor_object_mi/braycurtis_slides_pack.py --rebuild
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
from nor_object_mi.cluster13_condition_delta import _iqr  # noqa: E402
from nor_object_mi.cluster13_frame_share import (  # noqa: E402
    SESSION_STEP_LAB,
    SESSION_STEP_NAMES,
    TRIAL_LAB,
    TRIAL_STEP_LAB,
    TRIAL_STEP_NAMES,
    kruskal_by_session_trial_step_sex,
    kruskal_by_trial_session_step_sex,
    kruskal_per_model_session_step,
    kruskal_per_model_trial_step,
    short_model_label,
)
from nor_object_mi.fig_slides_pack import (  # noqa: E402
    SEX_LAB,
    _annotate_fm,
    _draw_condition_sex_violins,
    _imshow_model_x,
    _model_x_mats,
    _y_lim_from,
    fig_per_model_kruskal_heatmap,
)
from nor_object_mi.simpler_first_presence import TRIALS  # noqa: E402

DEFAULT_PACK = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\slides_pack\braycurtis"
)
DEFAULT_PRESENCE = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_presence_steps\presence_step_deltas_per_animal.csv"
)
DEFAULT_SESSION = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_session_paired\session_paired_deltas_per_animal.csv"
)

# Legacy session_paired wrote TX as ``condition`` in step tokens.
SESSION_STEP_ALIAS: dict[str, str] = {
    "BL->condition": "BL->TX",
    "condition->REC3hr": "TX->REC3hr",
    "condition->REC11hr": "TX->REC11hr",
}

YCOL = "bc"
METRIC_LAB = "Bray–Curtis"
METRIC_TITLE = "Bray–Curtis (abundance difference)"

FOOT_TRIAL = (
    "Grain: animal × session × trial_step (prose: phase-step). Point = median "
    "paired Bray–Curtis dissimilarity BC(left trial, right trial) across 21 "
    "kpMS models; whiskers = ±½ across-model IQR (salt). Six violins = "
    "condition × sex. Kruskal on BC ~ condition within sex; * = BH q < 0.05 in "
    "the 24-cell family. Not a signed Δ of a level scalar; not Wilcoxon vs 0; "
    "not DA. Level BC deferred (reference composition / among-animal β)."
)
FOOT_SESSION = (
    "Grain: animal × trial × session_step (prose: stage-step). Point = median "
    "paired Bray–Curtis BC(left session, right session) across 21 kpMS models; "
    "whiskers = ±½ across-model IQR. Kruskal on BC ~ condition within sex; "
    "* = BH q < 0.05 in the 36-cell family. Not signed level Δ; not Wilcoxon "
    "vs 0; not DA. Level BC deferred."
)
FOOT_MODEL_TRIAL = (
    "Per-model Kruskal on paired phase-step Bray–Curtis ~ condition within sex. "
    "Panel grid: rows = trial_step, cols = sex. Heatmap: y = kpMS model, "
    "x = session. Color = −log₁₀(p), clip 4; * = BH q < 0.05 within panel."
)
FOOT_MODEL_SESSION = (
    "Per-model Kruskal on paired stage-step Bray–Curtis ~ condition within sex. "
    "Panel grid: rows = trial, cols = sex. Heatmap: y = kpMS model, "
    "x = session_step. Color = −log₁₀(p), clip 4; * = BH q < 0.05 within panel."
)

PACK_CSV = {
    "trial_step": "bc_trial_step.csv",
    "trial_step_kr": "bc_trial_step_kruskal.csv",
    "session_step": "bc_session_step.csv",
    "session_step_kr": "bc_session_step_kruskal.csv",
    "model_trial_kr": "bc_per_model_trial_step_kruskal.csv",
    "model_session_kr": "bc_per_model_session_step_kruskal.csv",
    "model_labels": "bc_model_labels.csv",
    "trial_model": "bc_trial_step_model.csv",
    "session_model": "bc_session_step_model.csv",
}


def remap_session_step(series: pd.Series) -> pd.Series:
    """Map legacy ``*condition*`` tokens onto wire ``*TX*`` session_step names."""
    s = series.astype(str)
    return s.map(lambda x: SESSION_STEP_ALIAS.get(x, x))


def _animal_median_bc(
    model_long: pd.DataFrame,
    *,
    group_keys: list[str],
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for key_vals, g in model_long.groupby(group_keys, sort=True, observed=True):
        key_map = dict(zip(group_keys, key_vals if isinstance(key_vals, tuple) else (key_vals,)))
        v = pd.to_numeric(g[YCOL], errors="coerce").to_numpy(dtype=np.float64)
        v = v[np.isfinite(v)]
        rows.append(
            {
                **key_map,
                YCOL: float(np.median(v)) if v.size else float("nan"),
                "iqr_across_models": _iqr(v),
                "n_models": int(g["model"].nunique()) if "model" in g.columns else int(v.size),
                "n_finite": int(v.size),
            }
        )
    return pd.DataFrame(rows)


def load_trial_step_model(presence_csv: Path) -> pd.DataFrame:
    """Model-grain trial-step BC from presence paired table."""
    usecols = [
        "model",
        "animal_id",
        "sex",
        "condition",
        "session",
        "step",
        "braycurtis",
    ]
    raw = pd.read_csv(presence_csv, usecols=usecols)
    out = raw[raw["step"].isin(TRIAL_STEP_NAMES)].copy()
    out = out.rename(columns={"step": "trial_step", "braycurtis": YCOL})
    out["trial_step"] = pd.Categorical(out["trial_step"], categories=list(TRIAL_STEP_NAMES), ordered=True)
    out["session"] = pd.Categorical(out["session"], categories=list(SESSIONS), ordered=True)
    return out.reset_index(drop=True)


def load_session_step_model(session_csv: Path) -> pd.DataFrame:
    """Model-grain session-step BC; remap legacy condition tokens → TX."""
    usecols = [
        "model",
        "animal_id",
        "sex",
        "condition",
        "trial",
        "session_step",
        "braycurtis",
    ]
    raw = pd.read_csv(session_csv, usecols=usecols)
    out = raw.copy()
    out["session_step"] = remap_session_step(out["session_step"])
    out = out[out["session_step"].isin(SESSION_STEP_NAMES)].copy()
    out = out.rename(columns={"braycurtis": YCOL})
    unknown = sorted(set(out["session_step"].astype(str)) - set(SESSION_STEP_NAMES))
    if unknown:
        raise ValueError(f"unexpected session_step after remap: {unknown}")
    out["session_step"] = pd.Categorical(out["session_step"], categories=list(SESSION_STEP_NAMES), ordered=True)
    out["trial"] = pd.Categorical(out["trial"], categories=list(TRIALS), ordered=True)
    return out.reset_index(drop=True)


def build_bc_pack(*, presence_csv: Path, session_csv: Path) -> dict[str, pd.DataFrame]:
    trial_model = load_trial_step_model(presence_csv)
    session_model = load_session_step_model(session_csv)

    trial_med = _animal_median_bc(
        trial_model,
        group_keys=["animal_id", "sex", "condition", "session", "trial_step"],
    )
    trial_med["session"] = pd.Categorical(trial_med["session"], categories=list(SESSIONS), ordered=True)
    trial_med["trial_step"] = pd.Categorical(
        trial_med["trial_step"], categories=list(TRIAL_STEP_NAMES), ordered=True
    )

    session_med = _animal_median_bc(
        session_model,
        group_keys=["animal_id", "sex", "condition", "trial", "session_step"],
    )
    session_med["trial"] = pd.Categorical(session_med["trial"], categories=list(TRIALS), ordered=True)
    session_med["session_step"] = pd.Categorical(
        session_med["session_step"], categories=list(SESSION_STEP_NAMES), ordered=True
    )

    # Kruskal helpers expect col name; pass YCOL via rename to delta_p for reuse,
    # or call with col=YCOL — kruskal_by_* accept col=.
    kr_trial = kruskal_by_session_trial_step_sex(trial_med, col=YCOL)
    kr_session = kruskal_by_trial_session_step_sex(session_med, col=YCOL)

    # per-model helpers expect delta_p column name in some paths — check signatures.
    trial_for_pm = trial_model.rename(columns={YCOL: "delta_p"})
    session_for_pm = session_model.rename(columns={YCOL: "delta_p"})
    kr_model_trial = kruskal_per_model_trial_step(trial_for_pm, col="delta_p")
    kr_model_session = kruskal_per_model_session_step(session_for_pm, col="delta_p")

    models = sorted(set(trial_model["model"].astype(str)) | set(session_model["model"].astype(str)))
    return {
        "trial_step_model": trial_model,
        "session_step_model": session_model,
        "trial_step_delta": trial_med,
        "session_step_delta": session_med,
        "kruskal_trial_step": kr_trial,
        "kruskal_session_step": kr_session,
        "kruskal_per_model_trial_step": kr_model_trial,
        "kruskal_per_model_session_step": kr_model_session,
        "model_labels": pd.DataFrame({"model": models, "label": [short_model_label(m) for m in models]}),
    }


def write_pack_csvs(pack: Path, tables: dict[str, pd.DataFrame]) -> None:
    pack.mkdir(parents=True, exist_ok=True)
    writes = (
        (PACK_CSV["trial_step"], tables["trial_step_delta"]),
        (PACK_CSV["trial_step_kr"], tables["kruskal_trial_step"]),
        (PACK_CSV["session_step"], tables["session_step_delta"]),
        (PACK_CSV["session_step_kr"], tables["kruskal_session_step"]),
        (PACK_CSV["model_trial_kr"], tables["kruskal_per_model_trial_step"]),
        (PACK_CSV["model_session_kr"], tables["kruskal_per_model_session_step"]),
        (PACK_CSV["model_labels"], tables["model_labels"]),
        (PACK_CSV["trial_model"], tables["trial_step_model"]),
        (PACK_CSV["session_model"], tables["session_step_model"]),
    )
    for name, df in writes:
        df.to_csv(pack / name, index=False)
        print(f"wrote {pack / name}  n={len(df)}", flush=True)


def load_pack_csvs(pack: Path) -> dict[str, pd.DataFrame]:
    return {
        "trial_step_delta": pd.read_csv(pack / PACK_CSV["trial_step"]),
        "kruskal_trial_step": pd.read_csv(pack / PACK_CSV["trial_step_kr"]),
        "session_step_delta": pd.read_csv(pack / PACK_CSV["session_step"]),
        "kruskal_session_step": pd.read_csv(pack / PACK_CSV["session_step_kr"]),
        "kruskal_per_model_trial_step": pd.read_csv(pack / PACK_CSV["model_trial_kr"]),
        "kruskal_per_model_session_step": pd.read_csv(pack / PACK_CSV["model_session_kr"]),
        "model_labels": pd.read_csv(pack / PACK_CSV["model_labels"]),
    }


def fig_trial_step(med: pd.DataFrame, kr: pd.DataFrame, out: Path, *, dest: str) -> None:
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
    y_lim = _y_lim_from(med, YCOL)
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
                ycol=YCOL,
                zero_line=False,
            )
            ax.set_ylim(*y_lim)
            _annotate_fm(ax, kr, filters={"session": session, "trial_step": step}, dest=dest)
            if i == 0:
                ax.set_title(SESSION_SHORT[session], loc="left", fontweight="bold", color=INK)
            if j == 0:
                ax.set_ylabel(f"{TRIAL_STEP_LAB[step]}\n{METRIC_LAB}")
    fig.suptitle(
        f"{METRIC_TITLE} by trial-step × condition × sex",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_legend_and_footnote(fig, condition_sex_legend_handles(dest=dest), FOOT_TRIAL, dest=dest)
    save_pdf_svg(fig, out / "fig_bc_trial_step_by_sex")


def fig_session_step(med: pd.DataFrame, kr: pd.DataFrame, out: Path, *, dest: str) -> None:
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
    y_lim = _y_lim_from(med, YCOL)
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
                ycol=YCOL,
                zero_line=False,
            )
            ax.set_ylim(*y_lim)
            _annotate_fm(ax, kr, filters={"trial": trial, "session_step": step}, dest=dest)
            if i == 0:
                ax.set_title(SESSION_STEP_LAB[step], loc="left", fontweight="bold", color=INK)
            if j == 0:
                ax.set_ylabel(f"{TRIAL_LAB[trial]}\n{METRIC_LAB}")
    fig.suptitle(
        f"{METRIC_TITLE} by session-step × condition × sex",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_legend_and_footnote(fig, condition_sex_legend_handles(dest=dest), FOOT_SESSION, dest=dest)
    save_pdf_svg(fig, out / "fig_bc_session_step_by_sex")


def fig_combined_trial_step(
    med: pd.DataFrame,
    kr: pd.DataFrame,
    kr_model: pd.DataFrame,
    labels: pd.DataFrame,
    out: Path,
    *,
    dest: str,
) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    fig_w = 18.0 if dest == "slides" else 14.0
    fig_h = 8.2 if dest == "slides" else 7.0
    fig = plt.figure(figsize=(fig_w, fig_h))
    outer = fig.add_gridspec(
        1, 2, width_ratios=[1.55, 1.0], left=0.05, right=0.93, top=0.88, bottom=0.16, wspace=0.18
    )
    gs_v = outer[0].subgridspec(len(TRIAL_STEP_NAMES), len(SESSIONS), hspace=0.42, wspace=0.28)
    gs_h = outer[1].subgridspec(len(TRIAL_STEP_NAMES), len(SEX_ORDER), hspace=0.35, wspace=0.12)

    rng = np.random.default_rng(0)
    y_lim = _y_lim_from(med, YCOL)
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
                ycol=YCOL,
                zero_line=False,
            )
            ax.set_ylim(*y_lim)
            _annotate_fm(ax, kr, filters={"session": session, "trial_step": step}, dest=dest)
            if i == 0:
                ax.set_title(SESSION_SHORT[session], loc="left", fontweight="bold", color=INK)
            if j == 0:
                ax.set_ylabel(f"{TRIAL_STEP_LAB[step]}\n{METRIC_LAB}")

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
        f"{METRIC_TITLE} by trial-step × condition × sex  ·  Per-model Kruskal",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_legend_and_footnote(
        fig,
        condition_sex_legend_handles(dest=dest),
        FOOT_TRIAL + "  " + FOOT_MODEL_TRIAL,
        dest=dest,
    )
    save_pdf_svg(fig, out / "fig_bc_trial_step_combined")


def fig_combined_session_step(
    med: pd.DataFrame,
    kr: pd.DataFrame,
    kr_model: pd.DataFrame,
    labels: pd.DataFrame,
    out: Path,
    *,
    dest: str,
) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    fig_w = 20.0 if dest == "slides" else 15.0
    fig_h = 8.0 if dest == "slides" else 6.8
    fig = plt.figure(figsize=(fig_w, fig_h))
    outer = fig.add_gridspec(
        1, 2, width_ratios=[1.9, 1.0], left=0.045, right=0.93, top=0.88, bottom=0.16, wspace=0.14
    )
    gs_v = outer[0].subgridspec(len(TRIALS), len(SESSION_STEP_NAMES), hspace=0.42, wspace=0.22)
    gs_h = outer[1].subgridspec(len(TRIALS), len(SEX_ORDER), hspace=0.35, wspace=0.12)

    rng = np.random.default_rng(0)
    y_lim = _y_lim_from(med, YCOL)
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
                ycol=YCOL,
                zero_line=False,
            )
            ax.set_ylim(*y_lim)
            _annotate_fm(ax, kr, filters={"trial": trial, "session_step": step}, dest=dest)
            if i == 0:
                ax.set_title(SESSION_STEP_LAB[step], loc="left", fontweight="bold", color=INK)
            if j == 0:
                ax.set_ylabel(f"{TRIAL_LAB[trial]}\n{METRIC_LAB}")

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
        f"{METRIC_TITLE} by session-step × condition × sex  ·  Per-model Kruskal",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_legend_and_footnote(
        fig,
        condition_sex_legend_handles(dest=dest),
        FOOT_SESSION + "  " + FOOT_MODEL_SESSION,
        dest=dest,
    )
    save_pdf_svg(fig, out / "fig_bc_session_step_combined")


def write_info_md(pack: Path) -> None:
    text = f"""# INFO — slides pack: paired Bray–Curtis (abundance difference)

Step lattices only (trial-step / session-step). **No level figure** — Bray–Curtis
is a DIFFERENCE between two compositions; a single `session × trial` cell has one
share vector.

| | |
| --- | --- |
| These files | `{pack.as_posix()}` |
| Dest | slides |
| How regenerated | `uv run python scratch/nor_object_mi/braycurtis_slides_pack.py --rebuild` |

**BC** = Bray–Curtis dissimilarity (SciPy `braycurtis` on non-negative share /
count vectors; on probability vectors BC = ½ ∑ |p − q|).
**kpMS** = keypoint-MoSeq. **BH** = Benjamini–Hochberg. **Kruskal** =
Kruskal–Wallis.

## Questions

1. **Trial-step** (prose *phase-step*): Within sex, does **condition** modulate
   how far apart the left vs right trial compositions are (BC)?
2. **Session-step** (prose *stage-step*): Within sex, does condition modulate
   BC across sessions inside a trial?

## Deferred (circle back)

1. **Reference BC (level-ish):** BC(animal composition, fixed reference) in a
   cell — e.g. cohort / noSD centroid. Different claim: atypicality, not a step move.
2. **Among-animal β:** PERMANOVA / pairwise BC within a cell — group partition
   on compositions, not a per-animal violin of paired BC.

## Grain

| Family | Point | Value |
| ------ | ----- | ----- |
| trial_step | animal × session × trial_step | median BC(left, right) across 21 models |
| session_step | animal × trial × session_step | median BC(left, right) across 21 models |

Whiskers = ±½ IQR across models (salt), not SEM.

**Hit rule:** BH `q_bh < 0.05` (trial_step: 24 cells; session_step: 36).

**What this is not:** not richness/Shannon; not signed Δp / DA; not Wilcoxon vs 0
as the panel claim; not a standing “level BC.”

## Artifacts

| File | Unit |
| ---- | ---- |
| `bc_trial_step.csv` | animal × session × trial_step |
| `bc_session_step.csv` | animal × trial × session_step |
| `figures/fig_bc_trial_step_combined.{{pdf,svg}}` | phase-step violins + heatmaps |
| `figures/fig_bc_session_step_combined.{{pdf,svg}}` | stage-step violins + heatmaps |

## Source (rebuild only)

| Upstream | Use |
| -------- | --- |
| `simpler_first_presence_steps/presence_step_deltas_per_animal.csv` | `braycurtis` × trial steps |
| `simpler_first_session_paired/session_paired_deltas_per_animal.csv` | `braycurtis` × session steps (`BL->condition` → `BL->TX`) |
"""
    (pack / "INFO_slides_pack.md").write_text(text, encoding="utf-8")
    print(f"wrote {pack / 'INFO_slides_pack.md'}")


def write_figures_md(out: Path) -> None:
    text = """# Figures — Bray–Curtis paired (slides pack)

Complementary to `../INFO_slides_pack.md`. Dest = slides. **No level combined.**

| Stem | Question | Layout | D/I |
| ---- | -------- | ------ | --- |
| `fig_bc_trial_step_combined` | Phase-step BC modulated by condition? | 3×4 + 3×2 | D + Kruskal |
| `fig_bc_session_step_combined` | Stage-step BC modulated by condition? | 3×6 + 3×2 | D + Kruskal |
| `fig_bc_trial_step_by_sex` | Trial-step only | 3×4 violins | D + Kruskal |
| `fig_bc_session_step_by_sex` | Session-step only | 3×6 violins | D + Kruskal |
| `fig_bc_per_model_trial_step_kruskal` | Per-model phase-step | 3×2 heatmaps | I |
| `fig_bc_per_model_session_step_kruskal` | Per-model stage-step | 3×2 heatmaps | I |

## Regen

```powershell
uv run python scratch/nor_object_mi/braycurtis_slides_pack.py --rebuild
```
"""
    out.mkdir(parents=True, exist_ok=True)
    (out / "FIGURES.md").write_text(text, encoding="utf-8")
    print(f"wrote {out / 'FIGURES.md'}")


def run(*, pack: Path, presence_csv: Path, session_csv: Path, dest: str, rebuild: bool) -> None:
    out = pack / "figures"
    out.mkdir(parents=True, exist_ok=True)
    needed = (
        PACK_CSV["trial_step"],
        PACK_CSV["trial_step_kr"],
        PACK_CSV["session_step"],
        PACK_CSV["session_step_kr"],
        PACK_CSV["model_trial_kr"],
        PACK_CSV["model_session_kr"],
        PACK_CSV["model_labels"],
    )
    print(f"=== braycurtis -> {pack} ===", flush=True)
    if rebuild or any(not (pack / name).exists() for name in needed):
        tables = build_bc_pack(presence_csv=presence_csv, session_csv=session_csv)
        write_pack_csvs(pack, tables)
    else:
        tables = load_pack_csvs(pack)

    fig_trial_step(tables["trial_step_delta"], tables["kruskal_trial_step"], out, dest=dest)
    fig_session_step(tables["session_step_delta"], tables["kruskal_session_step"], out, dest=dest)
    fig_combined_trial_step(
        tables["trial_step_delta"],
        tables["kruskal_trial_step"],
        tables["kruskal_per_model_trial_step"],
        tables["model_labels"],
        out,
        dest=dest,
    )
    fig_combined_session_step(
        tables["session_step_delta"],
        tables["kruskal_session_step"],
        tables["kruskal_per_model_session_step"],
        tables["model_labels"],
        out,
        dest=dest,
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
        stem="fig_bc_per_model_trial_step_kruskal",
        title=f"Per-model Kruskal on phase-step {METRIC_LAB} ~ condition",
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
        stem="fig_bc_per_model_session_step_kruskal",
        title=f"Per-model Kruskal on stage-step {METRIC_LAB} ~ condition",
        footnote=FOOT_MODEL_SESSION,
    )
    write_info_md(pack)
    write_figures_md(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pack", type=Path, default=DEFAULT_PACK)
    ap.add_argument("--presence-csv", type=Path, default=DEFAULT_PRESENCE)
    ap.add_argument("--session-csv", type=Path, default=DEFAULT_SESSION)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    ap.add_argument("--rebuild", action="store_true")
    args = ap.parse_args(argv)
    run(
        pack=args.pack,
        presence_csv=args.presence_csv,
        session_csv=args.session_csv,
        dest=args.dest,
        rebuild=args.rebuild,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
