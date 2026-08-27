"""Overview: 4 Kruskal heatmaps (cluster × phase) by sex × step.

Panels: F presence, F novelty, M presence, M novelty.
BH family = cluster × phase within each panel.

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/fig_cluster_tx_kruskal_overview.py
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
    PHASE_SHORT,
    PHASES,
    SEX_ORDER,
    apply_style,
    fig_footnote,
    save_pdf_png,
    text_on_cmap,
    type_scale,
)
from nor_object_mi.cluster13_tx_delta import STEP_LAB, STEPS
from nor_object_mi.cluster_tx_kruskal import (  # noqa: E402
    animal_delta_p_by_model,
    animal_median_delta_p_by_cluster,
    attach_cluster_ids,
    attach_model_cluster_deltas,
    cluster_syllable_ids,
    kruskal_by_cluster_phase_step_sex,
    kruskal_by_model_phase_step_sex,
    representative_cluster_ids,
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
    "tx",
    "step",
    "phase_layer",
    "raw_syllable_id",
    "delta_p",
)
NLP_VMAX = 4.0
PANELS = (
    ("F", "no_obj->identical", "Female · presence"),
    ("F", "identical->novel", "Female · novelty"),
    ("F", "no_obj->novel", "Female · span"),
    ("M", "no_obj->identical", "Male · presence"),
    ("M", "identical->novel", "Male · novelty"),
    ("M", "no_obj->novel", "Male · span"),
)


def _weighting_label(weighting: str) -> str:
    if weighting == "bout_count":
        return "bout_count (one vote per bout)"
    return "frame_share (sum bout_frames)"


def _info_md(*, weighting: str) -> str:
    return f"""# INFO — cluster × phase Kruskal overview

Four heatmaps: Kruskal–Wallis rank test of animal median Δp ~ tx, **within sex**,
one panel per sex × step (presence / novelty / span).

**Composition weighting:** `{weighting}` — {_weighting_label(weighting)}.

## Grain

- Row = HDBSCAN `cluster_id` ≥ 0 (55 this fit).
- Column = protocol phase (`NOR_BL` … `NOR_REC11hr`).
- Per model × cluster: representative `raw_syllable_id` = max `n_bouts` in that cluster.
- Per animal × cluster × phase × step: median Δp across kpMS models.

## BH family

220 cells per panel (55 clusters × 4 phases). Not alphabet-wide DA FDR.

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
) -> tuple[np.ndarray, np.ndarray]:
    pmat = np.full((len(row_ids), len(PHASES)), np.nan)
    hits = np.zeros((len(row_ids), len(PHASES)), dtype=bool)
    sub = kr[(kr["sex"] == sex) & (kr["step"] == step)]
    id_to_i = {rid: i for i, rid in enumerate(row_ids)}
    for row in sub.itertuples(index=False):
        key = getattr(row, row_col)
        i = id_to_i.get(key)
        if i is None:
            continue
        try:
            j = PHASES.index(str(row.phase_layer))
        except ValueError:
            continue
        pmat[i, j] = float(row.p)
        hits[i, j] = bool(row.hit_fdr05)
    return pmat, hits


def _cluster_phase_mats(
    kr: pd.DataFrame,
    cluster_ids: list[int],
    *,
    sex: str,
    step: str,
) -> tuple[np.ndarray, np.ndarray]:
    return _row_phase_mats(kr, cluster_ids, "cluster_id", sex=sex, step=step)


def _imshow_row_phase(
    ax,
    pmat: np.ndarray,
    hits: np.ndarray,
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
    ax.set_xticks(range(len(PHASES)))
    ax.set_xticklabels([PHASE_SHORT[p] for p in PHASES], fontsize=ts["annotation"])
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
            if not annotate_all_p and not hits[i, j]:
                continue
            mark = "*" if hits[i, j] else ""
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


def _imshow_cluster_phase(
    ax,
    pmat: np.ndarray,
    hits: np.ndarray,
    cluster_ids: list[int],
    *,
    title: str,
    ts: dict,
    show_ylabel: bool,
) -> object:
    return _imshow_row_phase(
        ax,
        pmat,
        hits,
        [str(c) for c in cluster_ids],
        title=title,
        ts=ts,
        ylabel="cluster_id",
        show_ylabel=show_ylabel,
    )


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


def fig_overview(kr: pd.DataFrame, out: Path, *, dest: str, weighting: str) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    cluster_ids = sorted(int(x) for x in kr["cluster_id"].unique())
    fig_h = 16.0 if dest == "slides" else 12.0
    fig_w = 20.0 if dest == "slides" else 14.0
    fig, axes = plt.subplots(2, 3, figsize=(fig_w, fig_h), constrained_layout=False)
    fig.subplots_adjust(left=0.06, right=0.93, top=0.93, bottom=0.08, hspace=0.28, wspace=0.12)
    im = None
    for k, (ax, (sex, step, title)) in enumerate(zip(axes.ravel(), PANELS)):
        pmat, hits = _cluster_phase_mats(kr, cluster_ids, sex=sex, step=step)
        im = _imshow_cluster_phase(
            ax,
            pmat,
            hits,
            cluster_ids,
            title=title,
            ts=ts,
            show_ylabel=(k in (0, 3)),
        )
    cax = fig.add_axes([0.94, 0.35, 0.012, 0.35])
    fig.colorbar(im, cax=cax, label="−log₁₀(p)  (clip 4)")
    fig.suptitle(
        f"Kruskal Δp ({weighting}) ~ tx by cluster × phase  (within sex; * = BH q < 0.05 in panel)",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_footnote(
        fig,
        (
            f"Δp weighting = {weighting} ({_weighting_label(weighting)}). "
            "Row = HDBSCAN cluster_id (representative syllable per model = max n_bouts in cluster). "
            "Cell = Kruskal on animal median Δp across 21 alphabets. Color = −log₁₀(uncorrected p); "
            "text only on FDR hits (*). BH family = 55 clusters × 4 phases within each sex × step panel "
            "(220 tests/panel; presence / novelty / span). Not Wilcoxon vs 0; not alphabet-wide DA FDR."
        ),
        fontsize=ts["footnote"],
        y=0.01,
        color=MUTE,
    )
    save_pdf_png(fig, out / "fig_cluster_tx_kruskal_overview")


def _info_cluster13_model_md(*, weighting: str) -> str:
    return f"""# INFO — cluster-13 model × phase Kruskal overview

Same 6-panel layout as `fig_cluster_tx_kruskal_overview` (F/M × presence/novelty/span),
but rows = kpMS **model** (each model's cluster-13 syllable(s), merged when a model
has >1 prototype in cluster 13).

**Composition weighting:** `{weighting}` — {_weighting_label(weighting)}.

## Merge rule

When a model has multiple `raw_syllable_id` in cluster 13, animal Δp = **median**
across those syllables (within model × animal × phase × step × tx).

This run: `paramscan_s1-1e8_s2-1e5_ss-50` has ids 4 and 9.

## BH family

84 cells per panel (21 models × 4 phases). Not alphabet-wide DA FDR.
"""


def fig_cluster13_model_overview(
    kr: pd.DataFrame,
    _cmap: pd.DataFrame,
    out: Path,
    *,
    dest: str,
    weighting: str,
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
        pmat, hits = _row_phase_mats(kr, models, "model", sex=sex, step=step)
        im = _imshow_row_phase(
            ax,
            pmat,
            hits,
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
    fig.suptitle(
        f"Kruskal Δp ({weighting}) ~ tx by model × phase  "
        "(cluster 13 syllable; within sex; * = BH q < 0.05)",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_footnote(
        fig,
        (
            f"Δp weighting = {weighting} ({_weighting_label(weighting)}). "
            "Row = full kpMS model name (cluster-13 syllable; ss-50 merges ids 4+9 by median Δp). "
            "Cell text = uncorrected Kruskal p; * = BH q < 0.05 within the 84-cell panel "
            "(21 models × 4 phases; presence / novelty / span). Color = −log₁₀(p). "
            "Not Wilcoxon vs 0; not alphabet-wide DA FDR."
        ),
        fontsize=ts["footnote"],
        y=0.01,
        color=MUTE,
    )
    save_pdf_png(fig, out / "fig_cluster13_model_tx_kruskal_overview")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--da-dir", type=Path, default=DEFAULT_DA)
    ap.add_argument("--sig-dir", type=Path, default=DEFAULT_SIG)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument(
        "--weighting",
        choices=("frame_share", "bout_count"),
        default=None,
        help="Label/INFO only; deltas come from --da-dir (default: run_summary.json or path name)",
    )
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    args = ap.parse_args(argv)

    out = args.out_dir or args.da_dir
    weighting = _resolve_weighting(args.da_dir, args.weighting)
    print(f"reading prototypes + animal deltas (weighting={weighting}) ...", flush=True)
    proto = pd.read_csv(args.sig_dir / "syllable_prototypes_clustered.csv")
    rep = representative_cluster_ids(proto)
    deltas = pd.read_csv(args.da_dir / "da_syllable_deltas_per_animal.csv", usecols=list(DELTA_USECOLS))
    mapped = attach_cluster_ids(deltas, rep)
    print(f"mapped rows {len(mapped)}; clusters {rep['cluster_id'].nunique()}", flush=True)
    med = animal_median_delta_p_by_cluster(mapped)
    kr = kruskal_by_cluster_phase_step_sex(med)
    med.to_csv(out / "cluster_animal_median_delta_p.csv", index=False)
    kr.to_csv(out / "cluster_tx_kruskal.csv", index=False)
    rep.to_csv(out / "cluster_representative_ids.csv", index=False)
    (out / "INFO_cluster_tx_kruskal.md").write_text(_info_md(weighting=weighting), encoding="utf-8")
    fig_overview(kr, out, dest=args.dest, weighting=weighting)
    summary = {
        "weighting": weighting,
        "n_clusters": int(rep["cluster_id"].nunique()),
        "n_rep_rows": int(len(rep)),
        "n_animal_cells": int(len(med)),
        "n_kruskal_cells": int(len(kr)),
        "n_kruskal_fdr_by_panel": {
            f"{sex}_{STEP_LAB[step]}": int(
                kr[(kr["sex"] == sex) & (kr["step"] == step)]["hit_fdr05"].sum()
            )
            for sex in SEX_ORDER
            for step in STEPS
        },
        "bh_family_per_panel": "cluster x phase within sex x step",
    }
    (out / "cluster_tx_kruskal_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)

    print("cluster 13 model-level ...", flush=True)
    cmap13 = cluster_syllable_ids(proto, cluster_id=13)
    mapped13 = attach_model_cluster_deltas(deltas, cmap13)
    med13 = animal_delta_p_by_model(mapped13)
    kr13 = kruskal_by_model_phase_step_sex(med13)
    med13.to_csv(out / "cluster13_model_animal_delta_p.csv", index=False)
    kr13.to_csv(out / "cluster13_model_tx_kruskal.csv", index=False)
    cmap13.to_csv(out / "cluster13_syllable_map.csv", index=False)
    (out / "INFO_cluster13_model_tx_kruskal.md").write_text(
        _info_cluster13_model_md(weighting=weighting), encoding="utf-8"
    )
    fig_cluster13_model_overview(kr13, cmap13, out, dest=args.dest, weighting=weighting)
    multi = cmap13.groupby("model").size()
    summary13 = {
        "weighting": weighting,
        "cluster_id": 13,
        "n_models": int(cmap13["model"].nunique()),
        "n_syllable_rows": int(len(cmap13)),
        "models_multi_syllable": {
            str(m): int(n) for m, n in multi[multi > 1].items()
        },
        "n_kruskal_cells": int(len(kr13)),
        "n_kruskal_fdr_by_panel": {
            f"{sex}_{STEP_LAB[step]}": int(
                kr13[(kr13["sex"] == sex) & (kr13["step"] == step)]["hit_fdr05"].sum()
            )
            for sex in SEX_ORDER
            for step in STEPS
        },
        "bh_family_per_panel": "model x phase within sex x step",
        "merge_rule": "median delta_p across cluster-13 syllables per model",
    }
    (out / "cluster13_model_tx_kruskal_summary.json").write_text(
        json.dumps(summary13, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary13, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
