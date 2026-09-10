"""Overview: Kruskal heatmaps (cluster × phase) by sex × step.

Panel BH family = cluster × phase within each sex × step panel.
Column BH family = clusters within each sex × step × phase.

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/fig_cluster_condition_kruskal_overview.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi._pub_style import (  # noqa: E402
    INK,
    MUTE,
    SESSION_SHORT,
    SESSIONS,
    SEX_ORDER,
    apply_style,
    fig_footnote,
    save_pdf_png,
    text_on_cmap,
    type_scale,
)
from nor_object_mi.cluster13_condition_delta import STEP_LAB, STEPS
from nor_object_mi.cluster_condition_kruskal import (  # noqa: E402
    animal_delta_p_by_model,
    animal_median_delta_p_by_cluster,
    attach_cluster_ids,
    attach_model_cluster_deltas,
    cluster_syllable_ids,
    clusters_with_any_hit,
    kruskal_by_cluster_session_step_sex,
    kruskal_by_model_session_step_sex,
    order_cluster_ids,
    representative_cluster_ids,
)
from nor_object_mi.fig_cluster_condition_kruskal_common import (  # noqa: E402
    cluster_y_labels,
    fdr_mark,
    fig_hit_cooccurrence,
    summarize_hit_clusters,
)

DEFAULT_DA = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_da"
)
DEFAULT_SIG = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_syllable_signatures"
)
DELTA_USECOLS = (
    "model",
    "animal_id",
    "sex",
    "condition",
    "step",
    "session",
    "raw_syllable_id",
    "delta_p",
)
NLP_VMAX = 4.0
PANELS = (
    ("F", "no_obj->id_obj", "Female · presence"),
    ("F", "id_obj->nvl_obj", "Female · novelty"),
    ("F", "no_obj->nvl_obj", "Female · span"),
    ("M", "no_obj->id_obj", "Male · presence"),
    ("M", "id_obj->nvl_obj", "Male · novelty"),
    ("M", "no_obj->nvl_obj", "Male · span"),
)


def _weighting_label(weighting: str) -> str:
    if weighting == "bout_count":
        return "bout_count (one vote per bout)"
    return "frame_share (sum bout_frames)"


def _info_md(*, weighting: str) -> str:
    return f"""# INFO — cluster × phase Kruskal overview

Six heatmaps: Kruskal–Wallis rank test of animal median Δp ~ tx, **within sex**,
one panel per sex × step (presence / novelty / span). Rows include HDBSCAN noise (−1).

**Composition weighting:** `{weighting}` — {_weighting_label(weighting)}.

## Grain

- Row = HDBSCAN `cluster_id` (≥ 0) plus noise (−1).
- Column = protocol phase (`NOR_BL` … `NOR_REC11hr`).
- Per model × cluster: representative `raw_syllable_id` = max `n_bouts` in that cluster.

## BH families

- **Panel** (`q_bh` / `hit_fdr05`): cluster × phase within each sex × step panel.
- **Column** (`q_bh_col` / `hit_fdr05_col`): clusters within each sex × step × phase.
  Marks: `*` = panel FDR; `†` = column-only FDR.

## Inputs

| File | Role |
|------|------|
| `simpler_first_syllable_signatures/syllable_prototypes_clustered.csv` | cluster map |
| `da_syllable_deltas_per_animal.csv` | animal Δp (`{weighting}`) |
"""


def _p_cell_text(p: float) -> str:
    if not np.isfinite(p):
        return ""
    if p < 1e-4:
        return "<10⁻⁴"
    if p < 0.001:
        return f"{p:.1e}"
    return f"{p:.3f}"


def _neglog10_p(p: float) -> float:
    if not np.isfinite(p) or p <= 0:
        return float("nan")
    return float(min(NLP_VMAX, max(0.0, -np.log10(p))))


def _row_phase_mats(
    kr: pd.DataFrame,
    row_ids: list,
    row_col: str,
    *,
    sex: str,
    step: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    pmat = np.full((len(row_ids), len(SESSIONS)), np.nan)
    hits = np.zeros((len(row_ids), len(SESSIONS)), dtype=bool)
    hits_col = np.zeros((len(row_ids), len(SESSIONS)), dtype=bool)
    sub = kr[(kr["sex"] == sex) & (kr["step"] == step)]
    id_to_i = {rid: i for i, rid in enumerate(row_ids)}
    has_col = "hit_fdr05_col" in sub.columns
    for row in sub.itertuples(index=False):
        key = getattr(row, row_col)
        i = id_to_i.get(key)
        if i is None:
            continue
        try:
            j = SESSIONS.index(str(row.session))
        except ValueError:
            continue
        pmat[i, j] = float(row.p)
        hits[i, j] = bool(row.hit_fdr05)
        if has_col:
            hits_col[i, j] = bool(row.hit_fdr05_col)
    return pmat, hits, hits_col


def _imshow_row_phase(
    ax,
    pmat: np.ndarray,
    hits: np.ndarray,
    hits_col: np.ndarray,
    y_labels: list[str],
    *,
    title: str,
    ts: dict,
    ylabel: str,
    show_ylabel: bool,
    annotate_all_p: bool = False,
    ytick_fontsize: float | None = None,
) -> object:
    nlp = np.vectorize(_neglog10_p, otypes=[float])(pmat)
    im = ax.imshow(nlp, cmap="viridis", vmin=0.0, vmax=NLP_VMAX, aspect="auto")
    ax.set_xticks(range(len(SESSIONS)))
    ax.set_xticklabels([SESSION_SHORT[p] for p in SESSIONS], fontsize=ts["annotation"])
    ax.set_yticks(range(len(y_labels)))
    yfs = float(ytick_fontsize if ytick_fontsize is not None else ts["cell"])
    if show_ylabel:
        ax.set_yticklabels(y_labels, fontsize=yfs, ha="right")
        ax.set_ylabel(ylabel)
        ax.tick_params(axis="y", pad=2)
    else:
        ax.set_yticklabels([])
    ax.set_title(title, loc="left", fontweight="bold", color=INK, fontsize=ts["annotation"])
    for i in range(pmat.shape[0]):
        for j in range(pmat.shape[1]):
            p = pmat[i, j]
            nlp_v = nlp[i, j]
            if not np.isfinite(p) or not np.isfinite(nlp_v):
                continue
            mark = fdr_mark(bool(hits[i, j]), bool(hits_col[i, j]))
            if not annotate_all_p and not mark:
                continue
            ax.text(
                j,
                i,
                mark + _p_cell_text(p),
                ha="center",
                va="center",
                fontsize=ts["cell"],
                color=text_on_cmap(nlp_v, vmin=0.0, vmax=NLP_VMAX),
            )
    return im


def _resolve_weighting(da_dir: Path, weighting: str | None) -> str:
    if weighting:
        return weighting
    summary_path = da_dir / "run_summary.json"
    if summary_path.is_file():
        meta = json.loads(summary_path.read_text(encoding="utf-8"))
        w = meta.get("weighting")
        if isinstance(w, str) and w:
            return w
    name = da_dir.name.lower()
    if "bout_count" in name:
        return "bout_count"
    return "frame_share"


def fig_overview(
    kr: pd.DataFrame,
    out: Path,
    *,
    dest: str,
    weighting: str,
    stem: str = "fig_cluster_condition_kruskal_overview",
    suptitle: str | None = None,
    footnote_extra: str | None = None,
) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    cluster_ids = order_cluster_ids(kr["cluster_id"])
    y_labels = cluster_y_labels(cluster_ids)
    n_row = len(cluster_ids)
    fig_h = 16.0 if dest == "slides" else 12.0
    fig_w = 20.0 if dest == "slides" else 14.0
    fig, axes = plt.subplots(2, 3, figsize=(fig_w, fig_h), constrained_layout=False)
    fig.subplots_adjust(left=0.06, right=0.93, top=0.93, bottom=0.08, hspace=0.28, wspace=0.12)
    im = None
    for k, (ax, (sex, step, title)) in enumerate(zip(axes.ravel(), PANELS)):
        pmat, hits, hits_col = _row_phase_mats(kr, cluster_ids, "cluster_id", sex=sex, step=step)
        im = _imshow_row_phase(
            ax,
            pmat,
            hits,
            hits_col,
            y_labels,
            title=title,
            ts=ts,
            ylabel="cluster_id",
            show_ylabel=(k in (0, 3)),
        )
    cax = fig.add_axes([0.94, 0.35, 0.012, 0.35])
    fig.colorbar(im, cax=cax, label="−log₁₀(p)  (clip 4)")
    fig.suptitle(
        suptitle
        or (
            f"Kruskal Δp ({weighting}) ~ tx by cluster × phase  "
            "(within sex; * = panel BH; † = column BH)"
        ),
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    foot = footnote_extra or (
        f"Δp weighting = {weighting} ({_weighting_label(weighting)}). "
        f"Row = HDBSCAN cluster_id incl. noise ({n_row} rows; rep syllable = max n_bouts). "
        "Cell = Kruskal on animal median Δp across 21 alphabets. Color = −log₁₀(uncorrected p). "
        f"* = panel BH q < 0.05 ({n_row} clusters × 4 phases within sex × step). "
        "† = column BH q < 0.05 (clusters within sex × step × phase). "
        "Not Wilcoxon vs 0; not alphabet-wide DA FDR."
    )
    fig_footnote(fig, foot, fontsize=ts["footnote"], y=0.01, color=MUTE)
    save_pdf_png(fig, out / stem)


def _info_cluster_model_md(*, weighting: str, cluster_id: int) -> str:
    return f"""# INFO — cluster-{cluster_id} model × phase Kruskal overview

Same 6-panel layout as `fig_cluster_condition_kruskal_overview`, rows = kpMS **model**
(each model's cluster-{cluster_id} syllable(s), median-merged when >1).

**Composition weighting:** `{weighting}` — {_weighting_label(weighting)}.

## BH family

model × phase within each sex × step panel. Drilldown only for clusters with
panel or column FDR hits on the all-cluster overview (cluster 13 always kept).
"""


def fig_cluster_model_overview(
    kr: pd.DataFrame,
    out: Path,
    *,
    dest: str,
    weighting: str,
    cluster_id: int,
) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    models = sorted(str(x) for x in kr["model"].unique())
    fig_h = 13.5 if dest == "slides" else 10.0
    fig_w = 26.0 if dest == "slides" else 18.0
    fig, axes = plt.subplots(2, 3, figsize=(fig_w, fig_h), constrained_layout=False)
    fig.subplots_adjust(left=0.28, right=0.92, top=0.93, bottom=0.08, hspace=0.32, wspace=0.14)
    im = None
    for k, (ax, (sex, step, title)) in enumerate(zip(axes.ravel(), PANELS)):
        pmat, hits, _hits_col = _row_phase_mats(kr, models, "model", sex=sex, step=step)
        hits_col = np.zeros_like(hits)
        im = _imshow_row_phase(
            ax,
            pmat,
            hits,
            hits_col,
            models,
            title=title,
            ts=ts,
            ylabel="model",
            show_ylabel=(k in (0, 3)),
            annotate_all_p=True,
            ytick_fontsize=ts["cell"] * 0.85,
        )
    cax = fig.add_axes([0.93, 0.35, 0.01, 0.35])
    fig.colorbar(im, cax=cax, label="−log₁₀(p)  (clip 4)")
    lab = "noise" if cluster_id < 0 else str(cluster_id)
    fig.suptitle(
        f"Kruskal Δp ({weighting}) ~ tx by model × phase  "
        f"(cluster {lab}; within sex; * = BH q < 0.05)",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_footnote(
        fig,
        (
            f"Δp weighting = {weighting} ({_weighting_label(weighting)}). "
            f"Row = kpMS model (cluster {lab} syllable; multi-id models median-merged). "
            f"Cell text = uncorrected Kruskal p; * = BH q < 0.05 within the "
            f"{len(models) * len(SESSIONS)}-cell panel. Color = −log₁₀(p)."
        ),
        fontsize=ts["footnote"],
        y=0.01,
        color=MUTE,
    )
    save_pdf_png(fig, out / f"fig_cluster{lab}_model_condition_kruskal_overview")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--da-dir", type=Path, default=DEFAULT_DA)
    ap.add_argument("--sig-dir", type=Path, default=DEFAULT_SIG)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument(
        "--weighting",
        choices=("frame_share", "bout_count"),
        default=None,
        help="Label/INFO only; deltas come from --da-dir",
    )
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    ap.add_argument(
        "--skip-drilldowns",
        action="store_true",
        help="Skip per-hit-cluster model overview figures",
    )
    args = ap.parse_args(argv)

    out = args.out_dir or args.da_dir
    weighting = _resolve_weighting(args.da_dir, args.weighting)
    print(f"reading prototypes + animal deltas (weighting={weighting}) ...", flush=True)
    proto = pd.read_csv(args.sig_dir / "syllable_prototypes_clustered.csv")
    rep = representative_cluster_ids(proto, include_noise=True)
    deltas = pd.read_csv(args.da_dir / "da_syllable_deltas_per_animal.csv", usecols=list(DELTA_USECOLS))
    mapped = attach_cluster_ids(deltas, rep)
    print(f"mapped rows {len(mapped)}; clusters {rep['cluster_id'].nunique()}", flush=True)
    med = animal_median_delta_p_by_cluster(mapped)
    kr = kruskal_by_cluster_session_step_sex(med)
    med.to_csv(out / "cluster_animal_median_delta_p.csv", index=False)
    kr.to_csv(out / "cluster_condition_kruskal.csv", index=False)
    rep.to_csv(out / "cluster_representative_ids.csv", index=False)
    (out / "INFO_cluster_condition_kruskal.md").write_text(_info_md(weighting=weighting), encoding="utf-8")
    fig_overview(kr, out, dest=args.dest, weighting=weighting)

    hit_sum = summarize_hit_clusters(kr)
    print("hit co-occurrence ...", flush=True)
    hit_mat, jac = fig_hit_cooccurrence(
        kr,
        out,
        stem="fig_cluster_condition_kruskal_hit_cooccurrence",
        dest=args.dest,
        panel_cols=("sex", "step"),
        locus_col="session",
        locus_order=SESSIONS,
        title=f"Cluster FDR hit co-occurrence (panel BH; Δp={weighting})",
        footnote=(
            "Left: binary panel FDR hits (hit_fdr05) across sex × step × phase. "
            "Right: Jaccard of those hit sets between clusters (incl. noise). "
            "Column-wise FDR († on overview) is exploratory and not used here."
        ),
        hit_col="hit_fdr05",
    )
    hit_mat.to_csv(out / "cluster_condition_kruskal_hit_loci.csv")
    jac.to_csv(out / "cluster_condition_kruskal_hit_jaccard.csv")

    summary = {
        "weighting": weighting,
        "n_clusters": int(rep["cluster_id"].nunique()),
        "n_rep_rows": int(len(rep)),
        "n_animal_cells": int(len(med)),
        "n_kruskal_cells": int(len(kr)),
        "include_noise": True,
        "n_kruskal_fdr_by_panel": {
            f"{sex}_{STEP_LAB[step]}": int(
                kr[(kr["sex"] == sex) & (kr["step"] == step)]["hit_fdr05"].sum()
            )
            for sex in SEX_ORDER
            for step in STEPS
        },
        "n_kruskal_fdr_col_by_panel": {
            f"{sex}_{STEP_LAB[step]}": int(
                kr[(kr["sex"] == sex) & (kr["step"] == step)]["hit_fdr05_col"].sum()
            )
            for sex in SEX_ORDER
            for step in STEPS
        },
        "bh_family_per_panel": "cluster x phase within sex x step",
        "bh_family_per_column": "cluster within sex x step x phase",
        "n_hit_fdr05_panel": hit_sum["n_hit_fdr05_panel"],
        "n_hit_fdr05_col": hit_sum["n_hit_fdr05_col"],
        "clusters_panel_hit": hit_sum["clusters_panel_hit"],
        "clusters_col_only_hit": hit_sum["clusters_col_only_hit"],
        "clusters_any_hit": hit_sum["clusters_any_hit"],
    }
    (out / "cluster_condition_kruskal_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)

    print("cluster 13 model-level ...", flush=True)
    cmap13 = cluster_syllable_ids(proto, cluster_id=13)
    mapped13 = attach_model_cluster_deltas(deltas, cmap13)
    med13 = animal_delta_p_by_model(mapped13)
    kr13 = kruskal_by_model_session_step_sex(med13)
    med13.to_csv(out / "cluster13_model_animal_delta_p.csv", index=False)
    kr13.to_csv(out / "cluster13_model_condition_kruskal.csv", index=False)
    cmap13.to_csv(out / "cluster13_syllable_map.csv", index=False)
    (out / "INFO_cluster13_model_condition_kruskal.md").write_text(
        _info_cluster_model_md(weighting=weighting, cluster_id=13), encoding="utf-8"
    )
    fig_cluster_model_overview(kr13, out, dest=args.dest, weighting=weighting, cluster_id=13)

    drill_ids = [c for c in clusters_with_any_hit(kr) if c != 13]
    if not args.skip_drilldowns and drill_ids:
        drill_dir = out / "cluster_model_drilldowns"
        drill_dir.mkdir(parents=True, exist_ok=True)
        for cid in drill_ids:
            print(f"model drilldown cluster {cid} ...", flush=True)
            cmap = cluster_syllable_ids(proto, cluster_id=cid)
            mapped_m = attach_model_cluster_deltas(deltas, cmap)
            med_m = animal_delta_p_by_model(mapped_m)
            kr_m = kruskal_by_model_session_step_sex(med_m)
            lab = "noise" if cid < 0 else str(cid)
            med_m.to_csv(drill_dir / f"cluster{lab}_model_animal_delta_p.csv", index=False)
            kr_m.to_csv(drill_dir / f"cluster{lab}_model_condition_kruskal.csv", index=False)
            cmap.to_csv(drill_dir / f"cluster{lab}_syllable_map.csv", index=False)
            fig_cluster_model_overview(
                kr_m, drill_dir, dest=args.dest, weighting=weighting, cluster_id=cid
            )
        summary["model_drilldown_clusters"] = drill_ids
        (out / "cluster_condition_kruskal_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
