"""Cluster × locus overviews with mean per-model Kruskal p (models = hidden z).

Sibling to the median-Δp Kruskal overviews:
  - Cell = mean uncorrected Kruskal p across kpMS models
  - * = BH q < 0.05 treating models as the family within that cell
    (default star = majority of models hit)

Regen:
  uv run python scratch/nor_object_mi/fig_cluster_condition_kruskal_mean_model_p.py
  uv run python scratch/nor_object_mi/fig_cluster_condition_kruskal_mean_model_p.py --star any
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.cluster_condition_kruskal import (  # noqa: E402
    attach_cluster_ids as attach_da,
    representative_cluster_ids,
)
from nor_object_mi.cluster_condition_kruskal_session_paired import (  # noqa: E402
    attach_cluster_ids as attach_pp,
)
from nor_object_mi.cluster_condition_mean_model_p import (  # noqa: E402
    StarRule,
    aggregate_mean_p_models_as_family,
    kruskal_per_model_cluster_da,
    kruskal_per_model_cluster_pp,
)
from nor_object_mi.fig_cluster_condition_kruskal_overview import fig_overview  # noqa: E402
from nor_object_mi.fig_cluster_condition_kruskal_session_paired import (  # noqa: E402
    fig_cluster_overview as fig_pp_overview,
)
from nor_object_mi.simpler_first_session_paired import paired_n_by_step  # noqa: E402

DEFAULT_DA = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_da"
)
DEFAULT_PP = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_session_paired"
)
DEFAULT_SIG = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_syllable_signatures"
)
DA_USECOLS = (
    "model",
    "animal_id",
    "sex",
    "condition",
    "step",
    "session",
    "raw_syllable_id",
    "delta_p",
)
PP_USECOLS = (
    "model",
    "animal_id",
    "sex",
    "condition",
    "session_step",
    "trial",
    "raw_syllable_id",
    "delta_p",
)


def _info_md(*, design: str, star: str) -> str:
    return f"""# INFO — cluster overview (mean per-model Kruskal p)

Design: `{design}`. Sibling to the median-Δp-across-models Kruskal overview.

## What changed

Previously: median Δp across 21 alphabets → one Kruskal per cell.
Now: Kruskal **per model**, then cell = **mean uncorrected p**; models are a
hidden z-axis.

## Hit rule

BH (Benjamini–Hochberg) family = the finite model p-values **within that cell**
(only models that carry a mapped syllable for that cluster). Cell `*` when star
rule `{star}` holds on those BH hits, with **absent models scored as non-hits**
against the full ensemble (~21 paramscan models). So majority needs >10.5 hits
out of 21 — a cluster present in only 6 models cannot majority-star.

## Not

Not Wilcoxon vs 0; not alphabet-wide DA FDR; not the panel-wide BH on the
median-Δp overview.
"""


def run_da(
    *,
    da_dir: Path,
    sig_dir: Path,
    dest: str,
    star: StarRule,
    reuse_per_model: bool = True,
) -> dict:
    per_path = da_dir / "cluster_condition_kruskal_per_model.csv"
    if reuse_per_model and per_path.is_file():
        print(f"DA: reuse {per_path.name} ...", flush=True)
        per = pd.read_csv(per_path)
    else:
        print("DA: read + map ...", flush=True)
        proto = pd.read_csv(sig_dir / "syllable_prototypes_clustered.csv")
        rep = representative_cluster_ids(proto, include_noise=True)
        deltas = pd.read_csv(da_dir / "da_syllable_deltas_per_animal.csv", usecols=list(DA_USECOLS))
        mapped = attach_da(deltas, rep)
        print(f"DA: per-model Kruskal ({mapped['model'].nunique()} models) ...", flush=True)
        per = kruskal_per_model_cluster_da(mapped)
        per.to_csv(per_path, index=False)
    print("DA: mean p + BH across models within cell ...", flush=True)
    agg = aggregate_mean_p_models_as_family(
        per,
        ["cluster_id", "session", "step", "sex"],
        star=star,
    )
    if "hit_fdr05_col" not in agg.columns:
        agg["hit_fdr05_col"] = False
    agg.to_csv(da_dir / "cluster_condition_kruskal_mean_model_p.csv", index=False)
    (da_dir / "INFO_cluster_condition_kruskal_mean_model_p.md").write_text(
        _info_md(design="DA presence/novelty/span × phase", star=star), encoding="utf-8"
    )
    fig_overview(
        agg,
        da_dir,
        dest=dest,
        weighting="frame_share",
        stem="fig_cluster_condition_kruskal_overview_mean_model_p",
        suptitle=(
            "Mean per-model Kruskal p (Δp frame_share) ~ tx by cluster × phase  "
            f"(within sex; * = BH among tested models; absent = non-hit vs ensemble, star={star})"
        ),
        footnote_extra=(
            "Cell = mean uncorrected Kruskal p across models that carry the cluster "
            "(hidden z = alphabet; rep syllable = max n_bouts in cluster). "
            f"* = BH q < 0.05 among tested models in the cell; absent models = non-hits "
            f"vs full ensemble (star={star}). "
            "Not median-Δp-then-Kruskal; not panel-wide BH; not Wilcoxon vs 0."
        ),
    )
    summary = {
        "design": "da",
        "star_rule": star,
        "n_clusters": int(agg["cluster_id"].nunique()) if not agg.empty else 0,
        "n_per_model_rows": int(len(per)),
        "n_agg_cells": int(len(agg)),
        "n_hit_fdr05_cells": int(agg["hit_fdr05"].sum()) if not agg.empty else 0,
        "mean_n_hit_models_among_starred": float(
            agg.loc[agg["hit_fdr05"], "n_hit_fdr05_models"].mean()
        )
        if not agg.empty and bool(agg["hit_fdr05"].any())
        else 0.0,
    }
    (da_dir / "cluster_condition_kruskal_mean_model_p_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary


def run_pp(
    *,
    pp_dir: Path,
    sig_dir: Path,
    dest: str,
    star: StarRule,
    reuse_per_model: bool = True,
) -> dict:
    per_path = pp_dir / "session_paired_cluster_condition_kruskal_per_model.csv"
    if reuse_per_model and per_path.is_file():
        print(f"PP: reuse {per_path.name} ...", flush=True)
        per = pd.read_csv(per_path)
        deltas = pd.read_csv(
            pp_dir / "session_paired_da_deltas_per_animal.csv",
            usecols=["session_step", "animal_id"],
        )
        n_map = paired_n_by_step(deltas)
    else:
        print("PP: read + map ...", flush=True)
        proto = pd.read_csv(sig_dir / "syllable_prototypes_clustered.csv")
        rep = representative_cluster_ids(proto, include_noise=True)
        deltas = pd.read_csv(
            pp_dir / "session_paired_da_deltas_per_animal.csv", usecols=list(PP_USECOLS)
        )
        n_map = paired_n_by_step(deltas)
        mapped = attach_pp(deltas, rep)
        print(f"PP: per-model Kruskal ({mapped['model'].nunique()} models) ...", flush=True)
        per = kruskal_per_model_cluster_pp(mapped)
        per.to_csv(per_path, index=False)
    print("PP: mean p + BH across models within cell ...", flush=True)
    agg = aggregate_mean_p_models_as_family(
        per,
        ["cluster_id", "trial", "session_step", "sex"],
        star=star,
    )
    if "hit_fdr05_col" not in agg.columns:
        agg["hit_fdr05_col"] = False
    agg.to_csv(pp_dir / "session_paired_cluster_condition_kruskal_mean_model_p.csv", index=False)
    (pp_dir / "INFO_session_paired_cluster_condition_kruskal_mean_model_p.md").write_text(
        _info_md(design="phase-paired condition × phase step", star=star), encoding="utf-8"
    )
    out = pp_dir / "figures"
    out.mkdir(parents=True, exist_ok=True)
    fig_pp_overview(
        agg,
        out,
        dest=dest,
        n_map=n_map,
        stem="fig_session_paired_cluster_condition_kruskal_overview_mean_model_p",
        suptitle=(
            "Mean per-model paired Kruskal p (Δp frame_share) ~ tx by cluster × phase step  "
            f"(within sex; * = BH among tested models; absent = non-hit vs ensemble, star={star})"
        ),
        footnote_extra=(
            "Cell = mean uncorrected Kruskal p across models that carry the cluster "
            "(hidden z = alphabet). "
            f"* = BH q < 0.05 among tested models; absent models = non-hits vs full "
            f"ensemble (star={star}). "
            "Not median-Δp-then-Kruskal; not panel-wide BH; not Wilcoxon vs 0."
        ),
    )
    summary = {
        "design": "session_paired",
        "star_rule": star,
        "n_clusters": int(agg["cluster_id"].nunique()) if not agg.empty else 0,
        "n_per_model_rows": int(len(per)),
        "n_agg_cells": int(len(agg)),
        "n_hit_fdr05_cells": int(agg["hit_fdr05"].sum()) if not agg.empty else 0,
        "mean_n_hit_models_among_starred": float(
            agg.loc[agg["hit_fdr05"], "n_hit_fdr05_models"].mean()
        )
        if not agg.empty and bool(agg["hit_fdr05"].any())
        else 0.0,
    }
    (pp_dir / "session_paired_cluster_condition_kruskal_mean_model_p_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--da-dir", type=Path, default=DEFAULT_DA)
    ap.add_argument("--pp-dir", type=Path, default=DEFAULT_PP)
    ap.add_argument("--sig-dir", type=Path, default=DEFAULT_SIG)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    ap.add_argument(
        "--star",
        choices=("any", "majority", "all"),
        default="majority",
        help="Cell * when this many models have q_bh<0.05 within the cell family (default: majority)",
    )
    ap.add_argument("--only", choices=("da", "pp", "both"), default="both")
    ap.add_argument(
        "--recompute-kruskal",
        action="store_true",
        help="Ignore cached per-model Kruskal CSVs and recompute",
    )
    args = ap.parse_args(argv)
    star: StarRule = args.star  # type: ignore[assignment]
    reuse = not args.recompute_kruskal
    summaries = []
    if args.only in ("da", "both"):
        summaries.append(
            run_da(
                da_dir=args.da_dir,
                sig_dir=args.sig_dir,
                dest=args.dest,
                star=star,
                reuse_per_model=reuse,
            )
        )
    if args.only in ("pp", "both"):
        summaries.append(
            run_pp(
                pp_dir=args.pp_dir,
                sig_dir=args.sig_dir,
                dest=args.dest,
                star=star,
                reuse_per_model=reuse,
            )
        )
    print(json.dumps(summaries, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
