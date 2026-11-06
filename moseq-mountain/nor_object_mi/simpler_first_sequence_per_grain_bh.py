"""Re-declare BH FDR per grain (m=4) on existing sequence tests_long tables.

Does not recompute Kruskal scalars. Multiplicity only.
See vault: F TransStruct-PerGrain / F NGramSeq-PerGrain / Joint vs Per-Grain FDR.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from simpler_first_da import apply_bh_grouped

ROOT = Path(r"D:/sack/datas/impress/moseq_251017/_nor_object_mi")
OUTDIR = ROOT / "simpler_first_sequence_per_grain_bh"

JOBS = [
    (
        "TransStruct",
        "expanded",
        ROOT
        / "simpler_first_transition_structure_expanded"
        / "transition_structure_expanded_tests_long.csv",
        "TransStruct-PerGrain-Bpanel",
    ),
    (
        "TransStruct",
        "full_grid",
        ROOT
        / "simpler_first_transition_structure_full_grid"
        / "transition_structure_full_grid_tests_long.csv",
        "TransStruct-PerGrain",
    ),
    (
        "NGramSeq",
        "expanded",
        ROOT / "simpler_first_ngram_seq_expanded" / "ngram_seq_expanded_tests_long.csv",
        "NGramSeq-PerGrain-Bpanel",
    ),
    (
        "NGramSeq",
        "full_grid",
        ROOT / "simpler_first_ngram_seq_full_grid" / "ngram_seq_full_grid_tests_long.csv",
        "NGramSeq-PerGrain",
    ),
]


def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    summary: dict = {}
    for kind, panel, path, fam in JOBS:
        df = pd.read_csv(path)
        df = df.rename(columns={"q_bh": "q_bh_joint", "hit_fdr05": "hit_fdr05_joint"})
        out = apply_bh_grouped(df, ["session", "trial"], q_col="q_bh", hit_fdr_col="hit_fdr05")
        out["family"] = fam
        out["multiplicity"] = "per_grain_m4"
        out_path = OUTDIR / f"{kind.lower()}_{panel}_per_grain_tests_long.csv"
        out.to_csv(out_path, index=False)
        g = (
            out.groupby(["session", "trial"], as_index=False)
            .agg(
                n_cells=("p", "size"),
                n_hit_p05=("hit_p05", "sum"),
                n_hit_fdr05=("hit_fdr05", "sum"),
                min_p=("p", "min"),
                min_q=("q_bh", "min"),
            )
            .assign(grain_pass=lambda x: x["n_hit_fdr05"] >= 1)
        )
        g_path = OUTDIR / f"{kind.lower()}_{panel}_per_grain_rollup.csv"
        g.to_csv(g_path, index=False)
        hits = out.loc[
            out["hit_fdr05"], ["session", "trial", "sex", "metric", "p", "q_bh"]
        ].sort_values(["session", "trial", "p"])
        uncorr = out.loc[
            out["hit_p05"], ["session", "trial", "sex", "metric", "p", "q_bh"]
        ].sort_values("p")
        key = f"{kind}_{panel}"
        summary[key] = {
            "n_cells": int(len(out)),
            "n_grains": int(g.shape[0]),
            "n_grains_pass": int(g["grain_pass"].sum()),
            "n_hit_fdr05": int(out["hit_fdr05"].sum()),
            "n_hit_p05": int(out["hit_p05"].sum()),
            "hit_rows": hits.to_dict(orient="records"),
            "uncorr_top": uncorr.head(12).to_dict(orient="records"),
            "tests_out": str(out_path).replace("\\", "/"),
            "rollup_out": str(g_path).replace("\\", "/"),
        }
        print(
            f"{key}: grains_pass {summary[key]['n_grains_pass']}/{summary[key]['n_grains']} "
            f"fdr={summary[key]['n_hit_fdr05']} p05={summary[key]['n_hit_p05']}"
        )
    (OUTDIR / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("wrote", OUTDIR)


if __name__ == "__main__":
    main()
