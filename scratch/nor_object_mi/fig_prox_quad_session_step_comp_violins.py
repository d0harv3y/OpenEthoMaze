"""Prox/Quad shannon–richness session-step (stage-step) figure pack.

Twin of ``fig_prox_quad_comp_violins`` / ``fig_prox_quad_per_animal_comp_violins``
but on within-animal paired Δ across sessions (PHASE_STEPS).

Layout per figure: 3 rows (fam / nvl / DR) × 6 session_step columns.
Six violins = condition × sex. Trial fixed at nvl_obj.

Campaigns::

    # cohort raw ×21 (min0) + optional locked cluster
    uv run python scratch/nor_object_mi/fig_prox_quad_session_step_comp_violins.py --campaign cohort

    # per-animal paramscan cells ×9
    uv run python scratch/nor_object_mi/fig_prox_quad_session_step_comp_violins.py --campaign per_animal
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
    MUTE,
    SEX_ORDER,
    apply_style,
    condition_sex_legend_handles,
    fig_legend_and_footnote,
    save_pdf_svg,
    text_on_cmap,
    type_scale,
)
from nor_object_mi.cluster13_frame_share import short_model_label  # noqa: E402
from nor_object_mi.fig_prox_quad_comp_violins import (  # noqa: E402
    ELIG,
    ELIG_PM,
    KIND_YLAB,
    KINDS_DEFAULT,
    METRIC_MAP,
    ROLE_LAB,
    ROI_LAB,
    ROLES,
)
from nor_object_mi.fig_slides_pack import (  # noqa: E402
    NLP_VMAX,
    SEX_LAB,
    _annotate_fm,
    _draw_condition_sex_violins,
    _imshow_model_x,
    _model_x_mats,
    _neglog10_p,
    _p_cell_text,
    _y_lim_from,
)
from nor_object_mi.simpler_first_da import apply_bh, apply_bh_grouped  # noqa: E402
from nor_object_mi.fig_prox_quad_comp_violins import min_q_grain_note  # noqa: E402
from nor_object_mi.simpler_first_q1 import kruskal_within_sex  # noqa: E402
from nor_object_mi.simpler_first_session_paired import (  # noqa: E402
    PHASE_STEPS,
    PHASE_STEP_NAMES,
    STEP_LAB,
)

DEFAULT_COHORT_PER_MODEL = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_prox_quad_per_model_min0\per_model_per_animal.csv"
)
DEFAULT_COHORT_QUAD = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_quad_comp_min0\quad_comp_per_animal.csv"
)
DEFAULT_COHORT_PROX = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_prox_comp_min0\prox_comp_per_animal.csv"
)
DEFAULT_COHORT_OUT = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_prox_quad_session_step_figs_min0"
)
DEFAULT_PA_PER_CELL = Path(
    r"D:\sack\datas\impress\nor_per_animal_paramscan"
    r"\_nor_object_mi\simpler_first_prox_quad_per_animal\per_animal_per_cell.csv"
)
DEFAULT_PA_OUT = Path(
    r"D:\sack\datas\impress\nor_per_animal_paramscan"
    r"\_nor_object_mi\simpler_first_prox_quad_per_animal_session_step_figs"
)


def _paired_delta_long(
    df: pd.DataFrame,
    *,
    roi: str,
    kind: str,
    elig_col: str,
    alphabet: str,
    model_col: str | None,
) -> pd.DataFrame:
    """Paired Δ (right−left) for fam/nvl/dr × PHASE_STEPS.

    If ``model_col`` is set, pairs within model; else one alphabet board.
    Eligibility required at both endpoints.
    """
    cols = METRIC_MAP[(roi, kind)]
    need = ["animal_id", "sex", "condition", "session", elig_col, *cols.values()]
    if model_col is not None:
        need.append(model_col)
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise KeyError(f"missing columns for session-step {roi}/{kind}: {missing}")

    sub = df[df[elig_col].astype(bool)].copy()
    join_on = ["animal_id", "sex", "condition"]
    if model_col is not None:
        join_on = [model_col, *join_on]

    rows: list[dict[str, object]] = []
    for step, left, right in PHASE_STEPS:
        L = sub[sub["session"] == left]
        R = sub[sub["session"] == right]
        j = L.merge(R, on=join_on, how="inner", suffixes=("_l", "_r"))
        if j.empty:
            continue
        for role, col in cols.items():
            left_v = pd.to_numeric(j[f"{col}_l"], errors="coerce")
            right_v = pd.to_numeric(j[f"{col}_r"], errors="coerce")
            delta = right_v - left_v
            ok = np.isfinite(delta.to_numpy(dtype=np.float64))
            for i in np.flatnonzero(ok):
                rec: dict[str, object] = {
                    "animal_id": j["animal_id"].iloc[i],
                    "sex": j["sex"].iloc[i],
                    "condition": j["condition"].iloc[i],
                    "session_step": step,
                    "session_left": left,
                    "session_right": right,
                    "role": role,
                    "value": float(delta.iloc[i]),
                    "metric": col,
                    "roi": roi,
                    "kind": kind,
                    "alphabet": alphabet,
                    "iqr_across_models": np.nan,
                }
                if model_col is not None:
                    rec["model"] = j[model_col].iloc[i]
                rows.append(rec)
    return pd.DataFrame(rows)


def consensus_delta_with_salt(per_model_delta: pd.DataFrame) -> pd.DataFrame:
    """Median Δ across models + IQR salt; grain animal × session_step × role."""
    if per_model_delta.empty:
        return per_model_delta.copy()
    keys = ["animal_id", "sex", "condition", "session_step", "role", "metric", "roi", "kind"]
    rows: list[dict[str, object]] = []
    for key, g in per_model_delta.groupby(keys, sort=True):
        aid, sex, condition, step, role, metric, roi, kind = key
        vals = pd.to_numeric(g["value"], errors="coerce").to_numpy(dtype=np.float64)
        vals = vals[np.isfinite(vals)]
        if vals.size == 0:
            continue
        q25, q75 = np.percentile(vals, [25.0, 75.0])
        rows.append(
            {
                "animal_id": aid,
                "sex": sex,
                "condition": condition,
                "session_step": step,
                "role": role,
                "value": float(np.median(vals)),
                "iqr_across_models": float(q75 - q25),
                "n_models": int(vals.size),
                "metric": metric,
                "roi": roi,
                "kind": kind,
                "alphabet": str(g["alphabet"].iloc[0]) + "_consensus_median",
            }
        )
    return pd.DataFrame(rows)


def kruskal_role_session_step(
    long: pd.DataFrame,
    *,
    family: str,
    bh_group_cols: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for step in PHASE_STEP_NAMES:
        for role in ROLES:
            chunk = long[(long["session_step"] == step) & (long["role"] == role)].copy()
            if chunk.empty:
                continue
            tmp = chunk.copy()
            tmp["value"] = pd.to_numeric(tmp["value"], errors="coerce")
            k = kruskal_within_sex(tmp, metric="value").copy()
            k["session_step"] = step
            k["role"] = role
            k["family"] = family
            k["metric"] = str(chunk["metric"].iloc[0]) if len(chunk) else ""
            parts.append(k)
    if not parts:
        return pd.DataFrame()
    tests = pd.concat(parts, ignore_index=True)
    tests = tests[tests["sex"].isin(SEX_ORDER)].reset_index(drop=True)
    if bh_group_cols:
        return apply_bh_grouped(tests, list(bh_group_cols))
    return apply_bh(tests)


def kruskal_per_model_role_session_step(
    per_model_delta: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    parts: list[pd.DataFrame] = []
    for model, mg in per_model_delta.groupby("model", sort=True):
        for step in PHASE_STEP_NAMES:
            for role in ROLES:
                chunk = mg[(mg["session_step"] == step) & (mg["role"] == role)].copy()
                if chunk.empty:
                    continue
                k = kruskal_within_sex(chunk, metric="value").copy()
                k["model"] = model
                k["session_step"] = step
                k["role"] = role
                k["metric"] = str(chunk["metric"].iloc[0])
                k["roi"] = str(chunk["roi"].iloc[0])
                k["kind"] = str(chunk["kind"].iloc[0])
                parts.append(k)
    if not parts:
        return pd.DataFrame(), pd.DataFrame()
    tests = pd.concat(parts, ignore_index=True)
    tests = tests[tests["sex"].isin(SEX_ORDER)].reset_index(drop=True)
    out: list[pd.DataFrame] = []
    for (_model, _role), g in tests.groupby(["model", "role"], sort=True):
        out.append(apply_bh(g))
    tests_bh = pd.concat(out, ignore_index=True)
    labels = pd.DataFrame(
        {"model": sorted(tests_bh["model"].astype(str).unique())}
    ).assign(label=lambda d: d["model"].map(short_model_label))
    return tests_bh, labels


def fig_session_step_violins(
    long: pd.DataFrame,
    kr: pd.DataFrame,
    out: Path,
    *,
    dest: str,
    stem: str,
    title: str,
    footnote: str,
    ylab: str,
) -> Path:
    apply_style(dest=dest)
    ts = type_scale(dest)
    fig_w = 14.5 if dest == "slides" else 10.0
    fig_h = (FIGSIZE_SLIDES[1] + 0.8) if dest == "slides" else 7.2
    fig = plt.figure(figsize=(fig_w, fig_h))
    gs = fig.add_gridspec(
        len(ROLES),
        len(PHASE_STEP_NAMES),
        left=0.06,
        right=0.99,
        top=0.88,
        bottom=0.22,
        hspace=0.45,
        wspace=0.28,
    )
    rng = np.random.default_rng(0)
    # delta_p branch: signed pad from data (+ salt IQR). Match level-pack policy:
    # Δfam and Δnvl share one ylim (same scalar family); ΔDR gets its own so it
    # is not crushed. Within each row, ylim is shared across session-step cols.
    plot_df = long.rename(columns={"value": "delta_p"})
    if "iqr_across_models" not in plot_df.columns:
        plot_df["iqr_across_models"] = np.nan
    y_lim_level = _y_lim_from(plot_df[plot_df["role"].isin(("fam", "nvl"))], "delta_p")
    y_lim_dr = _y_lim_from(plot_df[plot_df["role"] == "dr"], "delta_p")
    role_ylim: dict[str, tuple[float, float]] = {
        "fam": y_lim_level,
        "nvl": y_lim_level,
        "dr": y_lim_dr,
    }
    violin_axes: dict[str, list] = {r: [] for r in ROLES}
    level_share_ax = None
    dr_share_ax = None
    for i, role in enumerate(ROLES):
        y_lo, y_hi = role_ylim[role]
        for j, step in enumerate(PHASE_STEP_NAMES):
            if role == "dr":
                share = dr_share_ax
            else:
                share = level_share_ax
            ax = fig.add_subplot(gs[i, j], sharey=share)
            if role == "dr" and dr_share_ax is None:
                dr_share_ax = ax
            elif role != "dr" and level_share_ax is None:
                level_share_ax = ax
            violin_axes[role].append(ax)
            panel = plot_df[(plot_df["session_step"] == step) & (plot_df["role"] == role)]
            _draw_condition_sex_violins(
                ax,
                panel,
                dest=dest,
                rng=rng,
                xlabel=(i == len(ROLES) - 1),
                ycol="delta_p",
                zero_line=True,
            )
            ax.set_ylim(y_lo, y_hi)
            if not kr.empty:
                _annotate_fm(
                    ax, kr, filters={"session_step": step, "role": role}, dest=dest
                )
            if i == 0:
                ax.set_title(STEP_LAB[step], loc="left", fontweight="bold", color=INK)
            if j == 0:
                ax.set_ylabel(f"Δ {ROLE_LAB[role]}\n{ylab}")
    fig.suptitle(title, fontsize=ts["suptitle"], fontweight="bold", color=INK, y=0.98)
    fig_legend_and_footnote(
        fig,
        condition_sex_legend_handles(dest=dest),
        footnote,
        dest=dest,
    )
    out.mkdir(parents=True, exist_ok=True)
    stem_path = out / stem
    save_pdf_svg(fig, stem_path)
    png = stem_path.with_suffix(".png")
    fig.savefig(png, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {stem_path}.{{pdf,svg,png}}", flush=True)
    return png


def fig_session_step_heatmap(
    kr: pd.DataFrame,
    out: Path,
    *,
    dest: str,
    stem: str,
    title: str,
    footnote: str,
) -> Path:
    apply_style(dest=dest)
    ts = type_scale(dest)
    fig_w = 12.0 if dest == "slides" else 9.0
    fig, axes = plt.subplots(1, len(SEX_ORDER), figsize=(fig_w, 3.8), squeeze=False)
    fig.subplots_adjust(left=0.10, right=0.90, top=0.82, bottom=0.22, wspace=0.25)
    im = None
    for j, sex in enumerate(SEX_ORDER):
        ax = axes[0, j]
        pmat = np.full((len(ROLES), len(PHASE_STEP_NAMES)), np.nan)
        hits = np.zeros_like(pmat, dtype=bool)
        for i, role in enumerate(ROLES):
            for k, step in enumerate(PHASE_STEP_NAMES):
                cell = kr[
                    (kr["sex"] == sex)
                    & (kr["role"] == role)
                    & (kr["session_step"] == step)
                ]
                if len(cell) == 1:
                    pmat[i, k] = float(cell["p"].iloc[0])
                    hits[i, k] = bool(cell["hit_fdr05"].iloc[0])
        nlp = np.vectorize(_neglog10_p, otypes=[float])(pmat)
        im = ax.imshow(nlp, cmap="viridis", vmin=0.0, vmax=NLP_VMAX, aspect="auto")
        ax.set_xticks(range(len(PHASE_STEP_NAMES)))
        ax.set_xticklabels(
            [STEP_LAB[s] for s in PHASE_STEP_NAMES],
            fontsize=ts["annotation"],
            rotation=35,
            ha="right",
        )
        ax.set_yticks(range(len(ROLES)))
        ax.set_yticklabels(
            [f"Δ{ROLE_LAB[r]}" for r in ROLES] if j == 0 else [],
            fontsize=ts["annotation"],
        )
        ax.set_title(SEX_LAB.get(sex, sex), loc="left", fontweight="bold", color=INK)
        for i in range(pmat.shape[0]):
            for k in range(pmat.shape[1]):
                p = pmat[i, k]
                nlp_v = nlp[i, k]
                if not (np.isfinite(p) and np.isfinite(nlp_v)):
                    continue
                mark = "*" if hits[i, k] else ""
                ax.text(
                    k,
                    i,
                    mark + _p_cell_text(p),
                    ha="center",
                    va="center",
                    fontsize=ts["cell"] * 0.85,
                    color=text_on_cmap(nlp_v, vmin=0.0, vmax=NLP_VMAX),
                )
    if im is not None:
        cax = fig.add_axes([0.92, 0.28, 0.015, 0.45])
        cb = fig.colorbar(im, cax=cax)
        cb.set_label("−log₁₀(p)", fontsize=ts["annotation"], color=INK)
        cb.ax.tick_params(labelsize=ts["cell"])
    fig.suptitle(title, fontsize=ts["suptitle"], fontweight="bold", color=INK, y=0.98)
    fig.text(
        0.5, 0.02, footnote, ha="center", va="bottom", fontsize=ts["footnote"], color=MUTE
    )
    out.mkdir(parents=True, exist_ok=True)
    stem_path = out / stem
    save_pdf_svg(fig, stem_path)
    png = stem_path.with_suffix(".png")
    fig.savefig(png, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {stem_path}.{{pdf,svg,png}}", flush=True)
    return png


def fig_per_model_session_step_heatmap(
    kr: pd.DataFrame,
    labels: pd.DataFrame,
    out: Path,
    *,
    dest: str,
    stem: str,
    title: str,
    footnote: str,
) -> Path:
    apply_style(dest=dest)
    ts = type_scale(dest)
    lab_map = dict(zip(labels["model"].astype(str), labels["label"].astype(str)))
    models = sorted(str(x) for x in kr["model"].unique())
    y_labels = [lab_map.get(m, m.split("_")[-1][:12]) for m in models]
    x_labels = [STEP_LAB[s] for s in PHASE_STEP_NAMES]
    n_row = len(ROLES)
    fig_w = 14.0 if dest == "slides" else 10.0
    fig_h = (4.5 * n_row + 0.5) if dest == "slides" else (3.5 * n_row + 0.5)
    fig, axes = plt.subplots(n_row, len(SEX_ORDER), figsize=(fig_w, fig_h), squeeze=False)
    fig.subplots_adjust(left=0.10, right=0.90, top=0.92, bottom=0.08, hspace=0.35, wspace=0.18)
    im = None
    for i, role in enumerate(ROLES):
        for j, sex in enumerate(SEX_ORDER):
            ax = axes[i, j]
            pmat, hits = _model_x_mats(
                kr,
                models=models,
                x_values=list(PHASE_STEP_NAMES),
                x_col="session_step",
                row_value=role,
                row_col="role",
                sex=sex,
            )
            im = _imshow_model_x(
                ax,
                pmat,
                hits,
                y_labels=y_labels,
                x_labels=x_labels,
                title=f"Δ{ROLE_LAB[role]} · {SEX_LAB.get(sex, sex)}",
                ts=ts,
                show_ylabel=(j == 0),
                ylabel="model" if j == 0 else "",
            )
    if im is not None:
        cax = fig.add_axes([0.92, 0.15, 0.015, 0.7])
        cb = fig.colorbar(im, cax=cax)
        cb.set_label("−log₁₀(p)", fontsize=ts["annotation"], color=INK)
    fig.suptitle(title, fontsize=ts["suptitle"], fontweight="bold", color=INK, y=0.98)
    fig.text(
        0.5, 0.01, footnote, ha="center", va="bottom", fontsize=ts["footnote"], color=MUTE
    )
    out.mkdir(parents=True, exist_ok=True)
    stem_path = out / stem
    save_pdf_svg(fig, stem_path)
    png = stem_path.with_suffix(".png")
    fig.savefig(png, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {stem_path}.{{pdf,svg,png}}", flush=True)
    return png


def _point_note(*, alphabet: str, salted: bool) -> str:
    """One-line description of what each violin point is."""
    if salted:
        return (
            "Point = median paired Δ across models; whiskers = ±½ across-model IQR (salt). "
        )
    if alphabet == "cluster_id" or alphabet.startswith("cluster"):
        return "Point = animal on portable cluster_id (pilot model). "
    if alphabet.startswith("raw:"):
        model = alphabet.split(":", 1)[1]
        return f"Point = animal on raw_syllable_id alphabet ({model}). "
    return f"Point = animal on alphabet {alphabet}. "


def _title_mode(*, alphabet: str, salted: bool) -> str:
    if salted:
        return "median+salt"
    if alphabet == "cluster_id" or alphabet.startswith("cluster"):
        return "cluster_id"
    if alphabet.startswith("raw:"):
        return "raw_syllable_id"
    return alphabet


def _foot_violin(
    *,
    alphabet: str,
    roi: str,
    kind: str,
    salted: bool,
    bh_note: str | None = None,
    min_q_note: str | None = None,
) -> str:
    bh = bh_note or (
        "Kruskal on Δ ~ condition within sex; * = BH q < 0.05 in the "
        "36-cell role×session_step×sex family. "
    )
    extra = f" {min_q_note}" if min_q_note else ""
    return (
        f"Grain: animal × session_step × nvl_obj × {ROI_LAB[roi]} ({kind}). "
        "Rows = Δfam / Δnvl / ΔDR. Cols = stage-steps (PHASE_STEPS). "
        "Six violins = condition × sex. "
        + _point_note(alphabet=alphabet, salted=salted)
        + bh
        + f"Alphabet: {alphabet}."
        + extra
    )


def _foot_hm_consensus() -> str:
    return (
        "Kruskal on paired Δ ~ condition within sex. Color = −log₁₀(uncorrected p), "
        "clip 4; * = BH q < 0.05 within the 36-cell family "
        "(role × session_step × sex). Trial fixed at nvl_obj."
    )


def _foot_hm_model(*, y_lab: str) -> str:
    return (
        f"Per-model Kruskal on paired Δ ~ condition within sex. y = {y_lab}. "
        "Panel grid: rows = Δfam|Δnvl|ΔDR, cols = sex. Heatmap x = session_step. "
        "Color = −log₁₀(p), clip 4; * = BH q < 0.05 within model × role "
        "(session_step × sex)."
    )


def run_board(
    *,
    long: pd.DataFrame,
    out: Path,
    dest: str,
    roi: str,
    kind: str,
    tag: str,
    alphabet: str,
    salted: bool,
    per_model_delta: pd.DataFrame | None = None,
    model_ylab: str = "kpMS model",
    bh_group_cols: tuple[str, ...] | None = None,
) -> list[Path]:
    family = f"{tag}-{roi}-{kind}-sessionstep-A"
    kr = kruskal_role_session_step(long, family=family, bh_group_cols=bh_group_cols)
    kr.to_csv(out / f"kruskal_{tag}_{roi}_{kind}_session_step.csv", index=False)
    long.to_csv(out / f"long_{tag}_{roi}_{kind}_session_step.csv", index=False)
    if bh_group_cols == ("sex",):
        bh_note = (
            "Kruskal on Delta ~ condition within sex; * = BH q < 0.05 sex-stratified "
            "(role x session_step within sex; m~18). "
        )
    elif bh_group_cols:
        bh_note = (
            "Kruskal on Δ ~ condition within sex; * = BH q < 0.05 grouped by "
            f"{','.join(bh_group_cols)}. "
        )
    else:
        bh_note = None
    min_q_note = min_q_grain_note(kr, ("sex", "role", "session_step", "metric"))
    paths: list[Path] = []
    paths.append(
        fig_session_step_violins(
            long,
            kr,
            out / "figures",
            dest=dest,
            stem=f"fig_{tag}_{roi}_{kind}_session_step_violins",
            title=(
                f"Δ {KIND_YLAB[kind]} · {ROI_LAB[roi]}  ({alphabet}; "
                f"{_title_mode(alphabet=alphabet, salted=salted)})"
            ),
            footnote=_foot_violin(
                alphabet=alphabet,
                roi=roi,
                kind=kind,
                salted=salted,
                bh_note=bh_note,
                min_q_note=min_q_note,
            ),
            ylab=KIND_YLAB[kind],
        )
    )
    paths.append(
        fig_session_step_heatmap(
            kr,
            out / "figures",
            dest=dest,
            stem=f"fig_{tag}_{roi}_{kind}_session_step_kruskal_heatmap",
            title=(
                f"Kruskal on Δ ~ condition  ({KIND_YLAB[kind]} · {ROI_LAB[roi]} · {tag})"
            ),
            footnote=_foot_hm_consensus(),
        )
    )
    if per_model_delta is not None and salted and not per_model_delta.empty:
        kr_m, labels = kruskal_per_model_role_session_step(per_model_delta)
        if not kr_m.empty:
            kr_m.to_csv(out / f"kruskal_per_model_{roi}_{kind}_session_step.csv", index=False)
            labels.to_csv(out / f"model_labels_{roi}_{kind}_session_step.csv", index=False)
            paths.append(
                fig_per_model_session_step_heatmap(
                    kr_m,
                    labels,
                    out / "figures",
                    dest=dest,
                    stem=f"fig_per_model_{roi}_{kind}_session_step_kruskal_heatmap",
                    title=(
                        f"Per-model Kruskal on Δ ~ condition  "
                        f"({KIND_YLAB[kind]} · {ROI_LAB[roi]})"
                    ),
                    footnote=_foot_hm_model(y_lab=model_ylab),
                )
            )
    return paths


def run_cohort(
    *,
    dest: str,
    out: Path,
    per_model: Path,
    quad: Path,
    prox: Path,
    kinds: tuple[str, ...] = KINDS_DEFAULT,
) -> list[Path]:
    pm = pd.read_csv(per_model)
    preview: list[Path] = []
    for roi, src_path, elig_locked in (
        ("quad", quad, ELIG["quad"]),
        ("prox", prox, ELIG["prox"]),
    ):
        for kind in kinds:
            print(f"=== cohort cluster {roi} {kind} session-step ===", flush=True)
            if src_path.is_file():
                locked = pd.read_csv(src_path)
                long_c = _paired_delta_long(
                    locked,
                    roi=roi,
                    kind=kind,
                    elig_col=elig_locked if elig_locked in locked.columns else ELIG_PM[roi],
                    alphabet="cluster_id",
                    model_col=None,
                )
                preview.extend(
                    run_board(
                        long=long_c,
                        out=out,
                        dest=dest,
                        roi=roi,
                        kind=kind,
                        tag="cluster",
                        alphabet="cluster_id",
                        salted=False,
                    )
                )
            else:
                print(f"  skip cluster: missing {src_path}", flush=True)

            print(f"=== cohort consensus+salt {roi} {kind} session-step ===", flush=True)
            long_m = _paired_delta_long(
                pm,
                roi=roi,
                kind=kind,
                elig_col=ELIG_PM[roi],
                alphabet="raw_syllable_id",
                model_col="model",
            )
            cons = consensus_delta_with_salt(long_m)
            preview.extend(
                run_board(
                    long=cons,
                    out=out,
                    dest=dest,
                    roi=roi,
                    kind=kind,
                    tag="consensus",
                    alphabet="raw_syllable_id_median",
                    salted=True,
                    per_model_delta=long_m,
                    model_ylab="kpMS model (paramscan)",
                )
            )
    return preview


def run_per_animal(
    *,
    dest: str,
    out: Path,
    per_cell: Path,
    kinds: tuple[str, ...] = KINDS_DEFAULT,
) -> list[Path]:
    pc = pd.read_csv(per_cell)
    preview: list[Path] = []
    for roi in ("quad", "prox"):
        for kind in kinds:
            print(f"=== per-animal consensus+salt {roi} {kind} session-step ===", flush=True)
            long_m = _paired_delta_long(
                pc,
                roi=roi,
                kind=kind,
                elig_col=ELIG_PM[roi],
                alphabet="per_animal_raw_syllable_id",
                model_col="model",
            )
            cons = consensus_delta_with_salt(long_m)
            cons = cons.copy()
            cons["alphabet"] = "per_animal_raw_syllable_id_median_x9"
            preview.extend(
                run_board(
                    long=cons,
                    out=out,
                    dest=dest,
                    roi=roi,
                    kind=kind,
                    tag="consensus",
                    alphabet="per_animal_median×9",
                    salted=True,
                    per_model_delta=long_m,
                    model_ylab="paramscan fit cell (s1/s2/ss)",
                )
            )
    return preview


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--campaign",
        choices=("cohort", "per_animal", "both"),
        default="both",
    )
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    ap.add_argument("--cohort-per-model", type=Path, default=DEFAULT_COHORT_PER_MODEL)
    ap.add_argument("--cohort-quad", type=Path, default=DEFAULT_COHORT_QUAD)
    ap.add_argument("--cohort-prox", type=Path, default=DEFAULT_COHORT_PROX)
    ap.add_argument("--cohort-out", type=Path, default=DEFAULT_COHORT_OUT)
    ap.add_argument("--per-animal-csv", type=Path, default=DEFAULT_PA_PER_CELL)
    ap.add_argument("--per-animal-out", type=Path, default=DEFAULT_PA_OUT)
    ap.add_argument(
        "--kinds",
        type=str,
        default=",".join(KINDS_DEFAULT),
        help="Comma-separated kinds: shannon,richness,hill2",
    )
    args = ap.parse_args(argv)
    kinds = tuple(k.strip() for k in args.kinds.split(",") if k.strip())
    for k in kinds:
        if k not in KIND_YLAB:
            raise ValueError(f"unknown kind {k!r}; expected one of {tuple(KIND_YLAB)}")

    if args.campaign in ("cohort", "both"):
        out = args.cohort_out
        out.mkdir(parents=True, exist_ok=True)
        (out / "figures").mkdir(parents=True, exist_ok=True)
        preview = run_cohort(
            dest=args.dest,
            out=out,
            per_model=args.cohort_per_model,
            quad=args.cohort_quad,
            prox=args.cohort_prox,
            kinds=kinds,
        )
        (out / "preview_paths.txt").write_text(
            "\n".join(str(p) for p in preview) + "\n", encoding="utf-8"
        )
        print(f"cohort done -> {out}  ({len(preview)} pngs)", flush=True)

    if args.campaign in ("per_animal", "both"):
        out = args.per_animal_out
        out.mkdir(parents=True, exist_ok=True)
        (out / "figures").mkdir(parents=True, exist_ok=True)
        preview = run_per_animal(
            dest=args.dest,
            out=out,
            per_cell=args.per_animal_csv,
            kinds=kinds,
        )
        (out / "preview_paths.txt").write_text(
            "\n".join(str(p) for p in preview) + "\n", encoding="utf-8"
        )
        print(f"per-animal done -> {out}  ({len(preview)} pngs)", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
