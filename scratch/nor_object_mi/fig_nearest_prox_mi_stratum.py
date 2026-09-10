"""Figures: nearest-prox MI stratified by sex × tx × phase.

Layout: one row per sex (F / M); x = tx, y = phase; cell shows median + n.
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
    CONDITION_ORDER,
    apply_style,
    fig_footnote,
    save_pdf_png,
    text_on_cmap,
)
from nor_object_mi.nearest_prox_mi import (  # noqa: E402
    DEFAULT_MODEL,
    LabelKind,
    default_ensemble_out_dir,
    default_out_dir,
)

ROOT = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017")
ART_ROOT = ROOT / "_nor_object_mi"

LABEL_TITLES: dict[LabelKind, str] = {
    "syllable": "syllable",
    "cluster": "cluster",
}


def metric_spec(label_kind: LabelKind) -> dict[str, dict[str, str | float]]:
    label = LABEL_TITLES[label_kind]
    return {
        "mi_mm": {
            "col": "median_mi_mm",
            "cbar": "median I_mm (bits)",
            "title": f"I({label}; nearest object) — median I_mm",
            "vmax_default": 0.20,
        },
        "excess": {
            "col": "median_excess",
            "cbar": "median excess I (bits)",
            "title": f"I({label}; nearest object) — median excess I",
            "vmax_default": 0.10,
        },
    }


def _cell_lookup(summary: pd.DataFrame, *, phase: str, sex: str, condition: str) -> tuple[float, int]:
    row = summary[(summary.session == phase) & (summary.sex == sex) & (summary.condition == condition)]
    if len(row) != 1:
        return float("nan"), 0
    r = row.iloc[0]
    return float(r["median_mi_mm" if "mi_mm" in str(r.index) else summary.columns[summary.columns.str.startswith("median_")][0]]), int(r["n_animals"])


def fig_heatmap_stratum(
    summary: pd.DataFrame,
    out: Path,
    *,
    metric: str,
    label_kind: LabelKind = "syllable",
    ensemble: bool = False,
    n_models: int | None = None,
) -> None:
    spec = metric_spec(label_kind)[metric]
    col = str(spec["col"])
    apply_style()
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 5.4), sharex=True)

    vals: list[float] = []
    for sex in SEX_ORDER:
        for ph in SESSIONS:
            for condition in CONDITION_ORDER:
                row = summary[(summary.session == ph) & (summary.sex == sex) & (summary.condition == condition)]
                if len(row) == 1:
                    v = float(row.iloc[0][col])
                    if np.isfinite(v):
                        vals.append(v)
    vmax = max(float(spec["vmax_default"]), max(vals) if vals else float(spec["vmax_default"]))
    vmin = 0.0 if metric == "mi_mm" else min(0.0, min(vals) if vals else 0.0)

    im = None
    tx_labels = list(CONDITION_ORDER)
    phase_labels = [SESSION_SHORT[p] for p in SESSIONS]

    for ax, sex in zip(axes, SEX_ORDER, strict=True):
        mat = np.full((len(SESSIONS), len(tx_labels)), np.nan)
        n_mat = np.zeros((len(SESSIONS), len(tx_labels)), dtype=np.int64)
        for i, ph in enumerate(SESSIONS):
            for j, tx in enumerate(tx_labels):
                row = summary[(summary.session == ph) & (summary.sex == sex) & (summary.condition == condition)]
                if len(row) == 1:
                    mat[i, j] = float(row.iloc[0][col])
                    n_mat[i, j] = int(row.iloc[0]["n_animals"])
        im = ax.imshow(mat, aspect="auto", cmap="viridis", vmin=vmin, vmax=vmax, origin="upper")
        ax.set_xticks(range(len(tx_labels)))
        ax.set_xticklabels(tx_labels)
        ax.set_xlabel("Treatment (condition)")
        ax.set_yticks(range(len(SESSIONS)))
        ax.set_yticklabels(phase_labels)
        ax.set_ylabel("Phase")
        ax.set_title(f"{sex} — female" if sex == "F" else f"{sex} — male", fontweight="bold", color=INK, loc="left")
        for i in range(len(SESSIONS)):
            for j in range(len(tx_labels)):
                v = mat[i, j]
                n = int(n_mat[i, j])
                if not np.isfinite(v) or n <= 0:
                    continue
                ax.text(
                    j,
                    i,
                    f"{v:.3f}\nn={n}",
                    ha="center",
                    va="center",
                    fontsize=8,
                    linespacing=1.15,
                    color=text_on_cmap(v, cmap="viridis", vmin=vmin, vmax=vmax),
                )

    assert im is not None
    cbar = fig.colorbar(im, ax=axes.ravel().tolist(), shrink=0.88, pad=0.02)
    cbar.set_label(str(spec["cbar"]))

    title = str(spec["title"])
    if ensemble:
        n = n_models or 21
        title += f" — consensus ({n} models)"
    fig.suptitle(title, fontweight="bold", color=INK, y=1.02)
    grain = f"median across {n_models} kpMS models" if ensemble else "median across animals"
    fig_footnote(
        fig,
        f"Cell = {grain}; nvl_obj bouts; nearest {{fam, nvl, neither}} at 0.10 m; "
        f"label={label_kind}.",
        y=-0.01,
        color=MUTE,
    )
    stem = out / f"fig_nearest_prox_{metric}_stratum_heat"
    save_pdf_png(fig, stem)
    fig.savefig(stem.with_suffix(".png"), dpi=180, bbox_inches="tight")
    plt.close(fig)


def fig_agreement_kruskal(agreement: pd.DataFrame, out: Path, *, n_models: int = 21) -> None:
    """Frac of models with within-sex Kruskal p < 0.05 (phase × metric, F|M panels)."""
    apply_style()
    metrics = ("mi_mm", "excess")
    metric_labels = ("I_mm", "excess I")
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 5.0), sharey=True)

    im = None
    for ax, sex in zip(axes, SEX_ORDER, strict=True):
        mat = np.full((len(SESSIONS), len(metrics)), np.nan)
        sub = agreement[agreement.sex == sex]
        for i, ph in enumerate(SESSIONS):
            for j, met in enumerate(metrics):
                row = sub[(sub.session == ph) & (sub.metric == met)]
                if len(row) == 1:
                    mat[i, j] = float(row.iloc[0]["frac_hit"])
        im = ax.imshow(mat, aspect="auto", cmap="viridis", vmin=0.0, vmax=1.0, origin="upper")
        ax.set_xticks(range(len(metrics)))
        ax.set_xticklabels(metric_labels)
        ax.set_xlabel("Metric")
        ax.set_yticks(range(len(SESSIONS)))
        ax.set_yticklabels([SESSION_SHORT[p] for p in SESSIONS])
        ax.set_ylabel("Phase")
        ax.set_title(f"{sex} — female" if sex == "F" else f"{sex} — male", fontweight="bold", color=INK, loc="left")
        for i in range(len(SESSIONS)):
            for j in range(len(metrics)):
                v = mat[i, j]
                if not np.isfinite(v):
                    continue
                n_hit = sub[(sub.session == SESSIONS[i]) & (sub.metric == metrics[j])]
                nh = int(n_hit.iloc[0]["n_hit_p05"]) if len(n_hit) == 1 else 0
                ax.text(
                    j,
                    i,
                    f"{v:.2f}\n{nh}/{n_models}",
                    ha="center",
                    va="center",
                    fontsize=8,
                    linespacing=1.15,
                    color=text_on_cmap(v, cmap="viridis", vmin=0.0, vmax=1.0),
                )

    assert im is not None
    cbar = fig.colorbar(im, ax=axes.ravel().tolist(), shrink=0.88, pad=0.02)
    cbar.set_label(f"frac of {n_models} models with Kruskal p < 0.05")
    fig.suptitle(
        "Cross-model agreement: tx modulates I(cluster; nearest)?",
        fontweight="bold",
        color=INK,
        y=1.02,
    )
    fig_footnote(
        fig,
        "Within-sex Kruskal on mi_mm / excess across tx, computed per kpMS model.",
        y=-0.02,
        color=MUTE,
    )
    stem = out / "fig_nearest_prox_tx_kruskal_agreement"
    save_pdf_png(fig, stem)
    fig.savefig(stem.with_suffix(".png"), dpi=180, bbox_inches="tight")
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, default=None)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument(
        "--ensemble",
        action="store_true",
        help="Read simpler_first_nearest_prox_cluster_mi__ensemble outputs",
    )
    ap.add_argument(
        "--label",
        choices=("syllable", "cluster"),
        default="syllable",
        help="Must match the run that produced mi_stratum_summary.csv",
    )
    args = ap.parse_args(argv)

    label_kind: LabelKind = args.label  # type: ignore[assignment]
    if args.ensemble:
        label_kind = "cluster"
    if args.run_dir:
        run = args.run_dir
    elif args.ensemble:
        run = default_ensemble_out_dir(ART_ROOT, label_kind="cluster")
    else:
        run = default_out_dir(ART_ROOT, args.model, label_kind=label_kind)
    fig_dir = run / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    summary = pd.read_csv(run / "mi_stratum_summary.csv")

    n_models = None
    summary_path = run / "run_summary.json"
    if summary_path.exists():
        blob = json.loads(summary_path.read_text(encoding="utf-8"))
        n_models = blob.get("n_models")

    fig_heatmap_stratum(
        summary,
        fig_dir,
        metric="mi_mm",
        label_kind=label_kind,
        ensemble=args.ensemble,
        n_models=int(n_models) if n_models else None,
    )
    fig_heatmap_stratum(
        summary,
        fig_dir,
        metric="excess",
        label_kind=label_kind,
        ensemble=args.ensemble,
        n_models=int(n_models) if n_models else None,
    )
    agree_path = run / "mi_stratum_agreement_by_model.csv"
    if agree_path.exists():
        agreement = pd.read_csv(agree_path)
        fig_agreement_kruskal(agreement, fig_dir, n_models=int(n_models or 21))
    print(f"wrote figures under {fig_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
