"""Prox/Quad shannon–richness violins + Kruskal heatmaps.

Layout per figure: 3 rows (fam / nvl / DR) × 4 session columns = 12 panels.
Six violins = condition × sex. Object-stratified scores are trial=nvl_obj only
(phase≈trial does not give a 3-row grid here).

Alphabets:
  - portable ``cluster_id`` (locked pilot model)
  - single-model ``raw:<model>`` (one animal point per grain; no salt)
  - median across 21 raw models + ±½ IQR salt whiskers

Regen::

    uv run python scratch/nor_object_mi/fig_prox_quad_comp_violins.py
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
    SESSION_SHORT,
    SESSIONS,
    SEX_ORDER,
    apply_style,
    condition_sex_legend_handles,
    fig_legend_and_footnote,
    save_pdf_svg,
    text_on_cmap,
    type_scale,
)
from nor_object_mi.cluster13_frame_share import short_model_label  # noqa: E402
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
from nor_object_mi.simpler_first_q1 import kruskal_within_sex  # noqa: E402

DEFAULT_QUAD = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_quad_comp\quad_comp_per_animal.csv"
)
DEFAULT_PROX = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_prox_comp\prox_comp_per_animal.csv"
)
DEFAULT_PER_MODEL = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_prox_quad_per_model\per_model_per_animal.csv"
)
DEFAULT_OUT = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_prox_quad_comp_figs"
)

ROLES: tuple[str, ...] = ("fam", "nvl", "dr")
ROLE_LAB: dict[str, str] = {"fam": "fam", "nvl": "nvl", "dr": "DR"}
METRIC_MAP: dict[tuple[str, str], dict[str, str]] = {
    ("quad", "shannon"): {
        "fam": "fam_shannon_quad",
        "nvl": "nvl_shannon_quad",
        "dr": "dr_shannon_quad",
    },
    ("quad", "richness"): {
        "fam": "fam_richness_quad",
        "nvl": "nvl_richness_quad",
        "dr": "dr_richness_quad",
    },
    ("prox", "shannon"): {
        "fam": "fam_shannon_prox",
        "nvl": "nvl_shannon_prox",
        "dr": "dr_shannon_prox",
    },
    ("prox", "richness"): {
        "fam": "fam_richness_prox",
        "nvl": "nvl_richness_prox",
        "dr": "dr_richness_prox",
    },
    ("quad", "hill2"): {
        "fam": "fam_hill2_quad",
        "nvl": "nvl_hill2_quad",
        "dr": "dr_hill2_quad",
    },
    ("prox", "hill2"): {
        "fam": "fam_hill2_prox",
        "nvl": "nvl_hill2_prox",
        "dr": "dr_hill2_prox",
    },
}
ELIG: dict[str, str] = {"quad": "contrast_eligible", "prox": "contrast_eligible"}
ELIG_PM: dict[str, str] = {
    "quad": "contrast_eligible_quad",
    "prox": "contrast_eligible_prox",
}
KIND_YLAB: dict[str, str] = {
    "shannon": "Shannon (bits)",
    "richness": "richness",
    "hill2": "Hill q=2 (eff. n)",
}
ROI_LAB: dict[str, str] = {"quad": "quadrant", "prox": "0.10 m prox"}
KINDS_DEFAULT: tuple[str, ...] = ("shannon", "richness", "hill2")


def _long_from_wide(
    df: pd.DataFrame,
    *,
    roi: str,
    kind: str,
    elig_col: str,
    alphabet: str,
) -> pd.DataFrame:
    cols = METRIC_MAP[(roi, kind)]
    need = ["animal_id", "sex", "condition", "session", elig_col, *cols.values()]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise KeyError(f"missing columns for {roi}/{kind}: {missing}")
    sub = df[df[elig_col].astype(bool)].copy()
    parts: list[pd.DataFrame] = []
    for role, col in cols.items():
        p = sub[["animal_id", "sex", "condition", "session"]].copy()
        p["role"] = role
        p["value"] = pd.to_numeric(sub[col], errors="coerce")
        p["metric"] = col
        p["roi"] = roi
        p["kind"] = kind
        p["alphabet"] = alphabet
        p["iqr_across_models"] = np.nan
        parts.append(p)
    out = pd.concat(parts, ignore_index=True)
    return out[np.isfinite(out["value"].to_numpy(dtype=np.float64))].reset_index(drop=True)


def consensus_with_salt(
    per_model: pd.DataFrame,
    *,
    roi: str,
    kind: str,
) -> pd.DataFrame:
    """Median across models + IQR salt; all sessions; eligible rows only."""
    elig = ELIG_PM[roi]
    cols = METRIC_MAP[(roi, kind)]
    need = ["animal_id", "sex", "condition", "session", "model", elig, *cols.values()]
    missing = [c for c in need if c not in per_model.columns]
    if missing:
        raise KeyError(f"per-model missing {missing}")
    sub = per_model[per_model[elig].astype(bool)].copy()
    rows: list[dict[str, object]] = []
    keys = ["animal_id", "sex", "condition", "session"]
    for key, g in sub.groupby(keys, sort=True):
        aid, sex, condition, session = key
        for role, col in cols.items():
            vals = pd.to_numeric(g[col], errors="coerce").to_numpy(dtype=np.float64)
            vals = vals[np.isfinite(vals)]
            if vals.size == 0:
                continue
            q25, q75 = np.percentile(vals, [25.0, 75.0])
            rows.append(
                {
                    "animal_id": aid,
                    "sex": sex,
                    "condition": condition,
                    "session": session,
                    "role": role,
                    "value": float(np.median(vals)),
                    "iqr_across_models": float(q75 - q25),
                    "n_models": int(vals.size),
                    "metric": col,
                    "roi": roi,
                    "kind": kind,
                    "alphabet": "raw_syllable_id_consensus_median",
                }
            )
    return pd.DataFrame(rows)


def kruskal_role_session(
    long: pd.DataFrame,
    *,
    family: str,
    bh_group_cols: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """Kruskal value ~ condition within sex; BH over role × session × sex (or grouped)."""
    parts: list[pd.DataFrame] = []
    for session in SESSIONS:
        for role in ROLES:
            chunk = long[(long["session"] == session) & (long["role"] == role)].copy()
            if chunk.empty:
                continue
            tmp = chunk.copy()
            tmp["value"] = pd.to_numeric(tmp["value"], errors="coerce")
            k = kruskal_within_sex(tmp, metric="value").copy()
            k["session"] = session
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


def min_q_grain_note(kr: pd.DataFrame, grain_cols: tuple[str, ...]) -> str:
    """One-line min BH q + grain for violin footnotes."""
    if kr.empty or "q_bh" not in kr.columns:
        return "min BH q: n/a."
    q = pd.to_numeric(kr["q_bh"], errors="coerce")
    ok = np.isfinite(q.to_numpy(dtype=np.float64))
    if not np.any(ok):
        return "min BH q: n/a."
    i = int(np.nanargmin(q.to_numpy(dtype=np.float64)))
    row = kr.iloc[i]
    bits = [f"{c}={row[c]}" for c in grain_cols if c in kr.columns]
    return f"min BH q={float(q.iloc[i]):.3f} at {', '.join(bits)}."


def kruskal_per_model_role_session(
    per_model: pd.DataFrame,
    *,
    roi: str,
    kind: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    elig = ELIG_PM[roi]
    cols = METRIC_MAP[(roi, kind)]
    sub = per_model[per_model[elig].astype(bool)].copy()
    parts: list[pd.DataFrame] = []
    for model, mg in sub.groupby("model", sort=True):
        for session in SESSIONS:
            for role, col in cols.items():
                chunk = mg[mg["session"] == session].copy()
                if chunk.empty or col not in chunk.columns:
                    continue
                tmp = chunk.rename(columns={col: "value"})
                k = kruskal_within_sex(tmp, metric="value").copy()
                k["model"] = model
                k["session"] = session
                k["role"] = role
                k["metric"] = col
                k["roi"] = roi
                k["kind"] = kind
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


def fig_violins(
    long: pd.DataFrame,
    kr: pd.DataFrame,
    out: Path,
    *,
    dest: str,
    stem: str,
    title: str,
    footnote: str,
    ylab: str,
    zero_line: bool = False,
) -> Path:
    apply_style(dest=dest)
    ts = type_scale(dest)
    fig_w, fig_h = FIGSIZE_SLIDES if dest == "slides" else (7.2, 8.0)
    fig = plt.figure(figsize=(fig_w * 1.08, fig_h + 0.8))
    gs = fig.add_gridspec(
        len(ROLES),
        len(SESSIONS),
        left=0.07,
        right=0.98,
        top=0.88,
        bottom=0.22,
        hspace=0.42,
        wspace=0.30,
    )
    rng = np.random.default_rng(0)
    plot_df = long.rename(columns={"value": "p"})
    if "iqr_across_models" not in plot_df.columns:
        plot_df["iqr_across_models"] = np.nan
    # Share y within fam/nvl; DR gets its own scale (contrast, not bits/count).
    y_lim_level = _y_lim_from(plot_df[plot_df["role"].isin(("fam", "nvl"))], "p")
    # DR cousins are bounded contrasts on [-1, 1]
    y_lim_dr = (-1.0, 1.0)
    violin_axes: dict[str, list] = {r: [] for r in ROLES}
    for i, role in enumerate(ROLES):
        for j, session in enumerate(SESSIONS):
            share = violin_axes[role][0] if violin_axes[role] else None
            ax = fig.add_subplot(gs[i, j], sharey=share)
            violin_axes[role].append(ax)
            panel = plot_df[(plot_df["session"] == session) & (plot_df["role"] == role)]
            _draw_condition_sex_violins(
                ax,
                panel,
                dest=dest,
                rng=rng,
                xlabel=(i == len(ROLES) - 1),
                ycol="p",
                zero_line=(zero_line and role == "dr"),
            )
            ax.set_ylim(*(y_lim_dr if role == "dr" else y_lim_level))
            if not kr.empty:
                _annotate_fm(ax, kr, filters={"session": session, "role": role}, dest=dest)
            if i == 0:
                ax.set_title(SESSION_SHORT[session], loc="left", fontweight="bold", color=INK)
            if j == 0:
                ax.set_ylabel(f"{ROLE_LAB[role]}\n{ylab}")
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
    fig.savefig(stem_path.with_suffix(".png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {stem_path}.{{pdf,svg,png}}", flush=True)
    return stem_path.with_suffix(".png")


def fig_consensus_heatmap(
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
    fig_w = 10.0 if dest == "slides" else 7.2
    fig, axes = plt.subplots(1, len(SEX_ORDER), figsize=(fig_w, 3.8), squeeze=False)
    fig.subplots_adjust(left=0.12, right=0.92, top=0.82, bottom=0.22, wspace=0.25)
    im = None
    for j, sex in enumerate(SEX_ORDER):
        ax = axes[0, j]
        pmat = np.full((len(ROLES), len(SESSIONS)), np.nan)
        hits = np.zeros_like(pmat, dtype=bool)
        for i, role in enumerate(ROLES):
            for k, session in enumerate(SESSIONS):
                cell = kr[
                    (kr["sex"] == sex) & (kr["role"] == role) & (kr["session"] == session)
                ]
                if len(cell) == 1:
                    pmat[i, k] = float(cell["p"].iloc[0])
                    hits[i, k] = bool(cell["hit_fdr05"].iloc[0])
        nlp = np.vectorize(_neglog10_p, otypes=[float])(pmat)
        im = ax.imshow(nlp, cmap="viridis", vmin=0.0, vmax=NLP_VMAX, aspect="auto")
        ax.set_xticks(range(len(SESSIONS)))
        ax.set_xticklabels(
            [SESSION_SHORT[s] for s in SESSIONS],
            fontsize=ts["annotation"],
            rotation=35,
            ha="right",
        )
        ax.set_yticks(range(len(ROLES)))
        ax.set_yticklabels(
            [ROLE_LAB[r] for r in ROLES] if j == 0 else [],
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
        cax = fig.add_axes([0.93, 0.28, 0.015, 0.45])
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
    fig.savefig(stem_path.with_suffix(".png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {stem_path}.{{pdf,svg,png}}", flush=True)
    return stem_path.with_suffix(".png")


def fig_per_model_heatmap(
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
    x_labels = [SESSION_SHORT[s] for s in SESSIONS]
    n_row = len(ROLES)
    fig_w = 12.0 if dest == "slides" else 9.0
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
                x_values=list(SESSIONS),
                x_col="session",
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
                title=f"{ROLE_LAB[role]} · {SEX_LAB.get(sex, sex)}",
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
            "Point = median across 21 kpMS models; whiskers = ±½ across-model IQR (salt). "
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
        "Kruskal within sex; * = BH q < 0.05 in the 24-cell role×session×sex family. "
    )
    extra = f" {min_q_note}" if min_q_note else ""
    return (
        f"Grain: animal × session × nvl_obj × {ROI_LAB[roi]} ({kind}). "
        "Rows = fam / nvl / DR (not trial — object scores are recognition-trial only). "
        "Cols = session. Six violins = condition × sex. "
        + _point_note(alphabet=alphabet, salted=salted)
        + bh
        + f"Alphabet: {alphabet}."
        + extra
    )


def _foot_hm_consensus() -> str:
    return (
        "Kruskal on level/DR ~ condition within sex. Color = −log₁₀(uncorrected p), "
        "clip 4; * = BH q < 0.05 within the 24-cell family (role × session × sex). "
        "Trial fixed at nvl_obj."
    )


def _foot_hm_model() -> str:
    return (
        "Per-model Kruskal on level/DR ~ condition within sex. Panel grid: rows = "
        "fam|nvl|DR, cols = sex. Heatmap: y = kpMS model, x = session. "
        "Color = −log₁₀(p), clip 4; * = BH q < 0.05 within model × role (session × sex)."
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
    per_model: pd.DataFrame | None = None,
    bh_group_cols: tuple[str, ...] | None = None,
) -> list[Path]:
    family = f"{tag}-{roi}-{kind}-A"
    kr = kruskal_role_session(long, family=family, bh_group_cols=bh_group_cols)
    kr.to_csv(out / f"kruskal_{tag}_{roi}_{kind}.csv", index=False)
    long.to_csv(out / f"long_{tag}_{roi}_{kind}.csv", index=False)
    if bh_group_cols == ("sex",):
        bh_note = (
            "Kruskal within sex; * = BH q < 0.05 sex-stratified "
            "(role x session within sex; m~12). "
        )
    elif bh_group_cols:
        bh_note = (
            f"Kruskal within sex; * = BH q < 0.05 grouped by {','.join(bh_group_cols)}. "
        )
    else:
        bh_note = None
    min_q_note = min_q_grain_note(kr, ("sex", "role", "session", "metric"))
    paths: list[Path] = []
    paths.append(
        fig_violins(
            long,
            kr,
            out / "figures",
            dest=dest,
            stem=f"fig_{tag}_{roi}_{kind}_violins",
            title=(
                f"{KIND_YLAB[kind]} · {ROI_LAB[roi]}  ({alphabet}; "
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
            zero_line=True,
        )
    )
    paths.append(
        fig_consensus_heatmap(
            kr,
            out / "figures",
            dest=dest,
            stem=f"fig_{tag}_{roi}_{kind}_kruskal_heatmap",
            title=f"Kruskal ~ condition  ({KIND_YLAB[kind]} · {ROI_LAB[roi]} · {tag})",
            footnote=_foot_hm_consensus(),
        )
    )
    if per_model is not None and salted:
        kr_m, labels = kruskal_per_model_role_session(per_model, roi=roi, kind=kind)
        if not kr_m.empty:
            kr_m.to_csv(out / f"kruskal_per_model_{roi}_{kind}.csv", index=False)
            labels.to_csv(out / f"model_labels_{roi}_{kind}.csv", index=False)
            paths.append(
                fig_per_model_heatmap(
                    kr_m,
                    labels,
                    out / "figures",
                    dest=dest,
                    stem=f"fig_per_model_{roi}_{kind}_kruskal_heatmap",
                    title=(
                        f"Per-model Kruskal ~ condition  "
                        f"({KIND_YLAB[kind]} · {ROI_LAB[roi]})"
                    ),
                    footnote=_foot_hm_model(),
                )
            )
    return paths


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--quad-csv", type=Path, default=DEFAULT_QUAD)
    ap.add_argument("--prox-csv", type=Path, default=DEFAULT_PROX)
    ap.add_argument("--per-model-csv", type=Path, default=DEFAULT_PER_MODEL)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
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

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "figures").mkdir(parents=True, exist_ok=True)

    quad = pd.read_csv(args.quad_csv)
    prox = pd.read_csv(args.prox_csv)
    if "contrast_eligible" not in quad.columns:
        raise KeyError("quad_comp_per_animal missing contrast_eligible")
    if "contrast_eligible" not in prox.columns:
        raise KeyError("prox_comp_per_animal missing contrast_eligible")

    per_model = pd.read_csv(args.per_model_csv)
    preview: list[Path] = []

    for roi, src, elig in (
        ("quad", quad, ELIG["quad"]),
        ("prox", prox, ELIG["prox"]),
    ):
        for kind in kinds:
            print(f"=== cluster {roi} {kind} ===", flush=True)
            long_c = _long_from_wide(
                src, roi=roi, kind=kind, elig_col=elig, alphabet="cluster_id"
            )
            preview.extend(
                run_board(
                    long=long_c,
                    out=out,
                    dest=args.dest,
                    roi=roi,
                    kind=kind,
                    tag="cluster",
                    alphabet="cluster_id",
                    salted=False,
                )
            )
            print(f"=== consensus+salt {roi} {kind} ===", flush=True)
            long_m = consensus_with_salt(per_model, roi=roi, kind=kind)
            preview.extend(
                run_board(
                    long=long_m,
                    out=out,
                    dest=args.dest,
                    roi=roi,
                    kind=kind,
                    tag="consensus",
                    alphabet="raw_syllable_id_median",
                    salted=True,
                    per_model=per_model,
                )
            )

    index = out / "preview_paths.txt"
    index.write_text("\n".join(str(p) for p in preview) + "\n", encoding="utf-8")
    print(f"done -> {out}  ({len(preview)} preview pngs)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
