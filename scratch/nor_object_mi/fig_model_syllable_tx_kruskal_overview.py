"""Per-model Kruskal overview: raw_syllable_id × phase (4 panels by sex × step).

One figure per kpMS model. Δp from `da_syllable_deltas_per_animal.csv`
(frame_share and/or bout_count sibling folders).

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/fig_model_syllable_tx_kruskal_overview.py --weighting both
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi._pub_style import (  # noqa: E402
    INK,
    MUTE,
    SEX_ORDER,
    apply_style,
    fig_footnote,
    save_png,
    type_scale,
)
from nor_object_mi.cluster13_tx_delta import STEP_LAB, STEPS
from nor_object_mi.cluster_tx_kruskal import (  # noqa: E402
    filter_presence_novelty,
    kruskal_by_syllable_phase_step_sex,
)
from nor_object_mi.fig_cluster_tx_kruskal_overview import (  # noqa: E402
    PANELS,
    _imshow_row_phase,
    _row_phase_mats,
)

DEFAULT_FRAME = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_da"
)
DEFAULT_BOUT = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_da_bout_count"
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
WEIGHTING_LABEL = {
    "frame_share": "frame_share (sum bout_frames)",
    "bout_count": "bout_count (one vote per bout)",
}


def _info_md(*, weighting: str) -> str:
    return f"""# INFO — per-model syllable × phase Kruskal overview

Four heatmaps per kpMS model: Kruskal–Wallis of animal Δp_k ~ tx, **within sex**,
one panel per sex × step (presence / novelty / span).

**Composition weighting:** `{weighting}` — {WEIGHTING_LABEL[weighting]}.

## Grain

- Row = `raw_syllable_id` (model-local; not portable across alphabets).
- Column = protocol phase (`NOR_BL` … `NOR_REC11hr`).
- One animal Δp per model × syllable × phase × step × tx (no cross-model median).

## BH family

`n_syllables × 4` phases per panel (within sex × step). Not alphabet-wide DA FDR.
Every cell shows uncorrected Kruskal p; `*` marks BH hits.

## Outputs

| File | Role |
|------|------|
| `model_syllable_tx_kruskal.csv` | all models long |
| `fig_model_syllable_tx_kruskal_<model>.{{pdf,svg,png}}` | one overview per model |
"""


def fig_model_overview(
    kr: pd.DataFrame,
    out_stem: Path,
    *,
    model: str,
    weighting: str,
    dest: str,
) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    sylls = sorted(int(x) for x in kr["raw_syllable_id"].unique())
    n = len(sylls)
    # Dense grids: shrink cell labels so every p fits.
    ts = {**ts, "cell": max(3.5, float(ts["cell"]) * min(1.0, 40.0 / max(n, 1)))}
    fig_h = max(10.0, 0.18 * n + 4.0) if dest == "slides" else max(8.0, 0.14 * n + 3.0)
    fig_w = 20.0 if dest == "slides" else 14.0
    fig, axes = plt.subplots(2, 3, figsize=(fig_w, fig_h), constrained_layout=False)
    fig.subplots_adjust(left=0.06, right=0.93, top=0.93, bottom=0.07, hspace=0.28, wspace=0.12)
    im = None
    for k, (ax, (sex, step, title)) in enumerate(zip(axes.ravel(), PANELS)):
        pmat, hits = _row_phase_mats(kr, sylls, "raw_syllable_id", sex=sex, step=step)
        im = _imshow_row_phase(
            ax,
            pmat,
            hits,
            [str(s) for s in sylls],
            title=title,
            ts=ts,
            ylabel="raw_syllable_id",
            show_ylabel=(k in (0, 3)),
            annotate_all_p=True,
            ytick_fontsize=max(5.0, ts["cell"] * 0.9),
        )
    cax = fig.add_axes([0.94, 0.35, 0.012, 0.35])
    fig.colorbar(im, cax=cax, label="−log₁₀(p)  (clip 4)")
    fig.suptitle(
        f"Kruskal Δp ({weighting}) ~ tx · {model}\n"
        f"syllable × phase (within sex; * = BH q < 0.05 in panel)",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_footnote(
        fig,
        (
            f"Δp weighting = {weighting} ({WEIGHTING_LABEL[weighting]}). "
            f"Rows = {n} raw_syllable_id in this alphabet. "
            "Cell text = uncorrected Kruskal p; * = BH q < 0.05 within the panel "
            "(syllables × 4 phases; presence / novelty / span). Color = −log₁₀(p). "
            "Ids not portable across models."
        ),
        fontsize=ts["footnote"],
        y=0.01,
        color=MUTE,
    )
    stem = Path(out_stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(stem.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(stem.with_suffix(".svg"), bbox_inches="tight")
    print(f"wrote {stem.with_suffix('.pdf')}", flush=True)
    print(f"wrote {stem.with_suffix('.svg')}", flush=True)
    save_png(fig, stem)


def redraw_from_csv(
    da_dir: Path,
    *,
    weighting: str,
    dest: str,
    models: list[str] | None,
) -> int:
    out = da_dir / "model_syllable_tx_kruskal"
    csv_path = out / "model_syllable_tx_kruskal.csv"
    if not csv_path.is_file():
        raise SystemExit(f"missing {csv_path}; run without --figures-only first")
    long = pd.read_csv(csv_path)
    all_models = sorted(str(m) for m in long["model"].unique())
    if models:
        want = set(models)
        all_models = [m for m in all_models if m in want]
        missing = want - set(all_models)
        if missing:
            raise SystemExit(f"models not in csv: {sorted(missing)}")
    (out / "INFO_model_syllable_tx_kruskal.md").write_text(
        _info_md(weighting=weighting), encoding="utf-8"
    )
    for i, model in enumerate(all_models, start=1):
        print(f"  redraw [{i}/{len(all_models)}] {model}", flush=True)
        kr = long[long["model"] == model]
        stem = out / f"fig_model_syllable_tx_kruskal_{model}"
        fig_model_overview(kr, stem, model=model, weighting=weighting, dest=dest)
    return len(all_models)


def run_one_da_dir(
    da_dir: Path,
    *,
    weighting: str,
    dest: str,
    models: list[str] | None,
) -> dict[str, object]:
    out = da_dir / "model_syllable_tx_kruskal"
    out.mkdir(parents=True, exist_ok=True)
    (out / "INFO_model_syllable_tx_kruskal.md").write_text(
        _info_md(weighting=weighting), encoding="utf-8"
    )
    print(f"reading deltas from {da_dir} (weighting={weighting}) ...", flush=True)
    deltas = pd.read_csv(da_dir / "da_syllable_deltas_per_animal.csv", usecols=list(DELTA_USECOLS))
    deltas = filter_presence_novelty(deltas)
    all_models = sorted(str(m) for m in deltas["model"].unique())
    if models:
        want = set(models)
        all_models = [m for m in all_models if m in want]
        missing = want - set(all_models)
        if missing:
            raise SystemExit(f"models not in deltas: {sorted(missing)}")
    kr_parts: list[pd.DataFrame] = []
    panel_hits: dict[str, dict[str, int]] = {}
    for i, model in enumerate(all_models, start=1):
        print(f"  [{i}/{len(all_models)}] {model}", flush=True)
        sub = deltas[deltas["model"] == model]
        kr = kruskal_by_syllable_phase_step_sex(sub)
        kr.insert(0, "model", model)
        kr_parts.append(kr)
        stem = out / f"fig_model_syllable_tx_kruskal_{model}"
        fig_model_overview(kr, stem, model=model, weighting=weighting, dest=dest)
        panel_hits[model] = {
            f"{sex}_{STEP_LAB[step]}": int(
                kr[(kr["sex"] == sex) & (kr["step"] == step)]["hit_fdr05"].sum()
            )
            for sex in SEX_ORDER
            for step in STEPS
        }
    long = pd.concat(kr_parts, ignore_index=True) if kr_parts else pd.DataFrame()
    long.to_csv(out / "model_syllable_tx_kruskal.csv", index=False)
    summary = {
        "weighting": weighting,
        "da_dir": str(da_dir),
        "n_models": len(all_models),
        "models": all_models,
        "n_kruskal_rows": int(len(long)),
        "n_fdr_hits_by_model_panel": panel_hits,
        "bh_family_per_panel": "syllable x phase within sex x step",
        "out_dir": str(out),
    }
    (out / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"weighting": weighting, "n_models": len(all_models), "out": str(out)}, indent=2))
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--weighting",
        choices=("frame_share", "bout_count", "both"),
        default="both",
    )
    ap.add_argument("--frame-dir", type=Path, default=DEFAULT_FRAME)
    ap.add_argument("--bout-dir", type=Path, default=DEFAULT_BOUT)
    ap.add_argument(
        "--model",
        action="append",
        default=None,
        help="Restrict to model name(s); repeatable. Default: all models in deltas.",
    )
    ap.add_argument(
        "--figures-only",
        action="store_true",
        help="Redraw from existing model_syllable_tx_kruskal.csv (skip Kruskal)",
    )
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    args = ap.parse_args(argv)

    weightings = (
        ("frame_share", "bout_count") if args.weighting == "both" else (args.weighting,)
    )
    for w in weightings:
        da = args.frame_dir if w == "frame_share" else args.bout_dir
        if args.figures_only:
            n = redraw_from_csv(da, weighting=w, dest=args.dest, models=args.model)
            print(json.dumps({"weighting": w, "n_redrawn": n}, indent=2), flush=True)
        else:
            run_one_da_dir(da, weighting=w, dest=args.dest, models=args.model)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
