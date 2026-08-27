"""Q1 + Q2 across NOR phases (BL / TX / REC3hr / REC11hr) on the pilot model.

Hope pattern: tx Kruskal / PERMANOVA quiet at baseline; possible hits at TX or recovery.
Same grain: animal × novel_obj window; raw bouts; within-sex tests.
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

from nor_object_mi.simpler_first_q1 import (  # noqa: E402
    LOCKED,
    animal_delta_prox,
    judge_q1,
    kruskal_within_sex,
)
from nor_object_mi.simpler_first_q2 import (  # noqa: E402
    compositions_from_bouts,
    judge_q2,
    permanova_within_sex,
)

# User shorthand NOR_REC3 / NOR_REC11 → stored phase_layer names
PHASES: tuple[tuple[str, str], ...] = (
    ("NOR_BL", "condition_ladder_NOR_BL"),
    ("NOR_TX", "condition_ladder"),
    ("NOR_REC3hr", "condition_ladder_NOR_REC3hr"),
    ("NOR_REC11hr", "condition_ladder_NOR_REC11hr"),
)


def _row_from_kruskal(phase: str, question: str, metric: str, r: pd.Series) -> dict[str, object]:
    return {
        "phase_layer": phase,
        "question": question,
        "metric": metric,
        "operation": {
            "delta_prox": "proximity (not composition ladder)",
            "richness": "COUNT",
            "shannon_bits": "UNCERTAINTY",
        }.get(metric, metric),
        "sex": r["sex"],
        "test": r["test"],
        "stat": r["stat"],
        "p": r["p"],
        "n": r["n"],
        "n_noSD": r["n_noSD"],
        "n_GHSD": r["n_GHSD"],
        "n_RBSD": r["n_RBSD"],
        "median_noSD": r["median_noSD"],
        "median_GHSD": r["median_GHSD"],
        "median_RBSD": r["median_RBSD"],
        "F": "",
        "n_perm": "",
        "hit_p05": bool(pd.notna(r["p"]) and float(r["p"]) < 0.05),
    }


def run_phase(bout_csv: Path, phase: str) -> tuple[list[dict[str, object]], dict[str, object]]:
    bouts = pd.read_csv(bout_csv)
    long_rows: list[dict[str, object]] = []

    # Q1
    animals = animal_delta_prox(bouts, phase_layer=phase, condition_layer="novel_obj")
    k1 = kruskal_within_sex(animals, metric="delta_prox")
    v1 = judge_q1(k1)
    for _, r in k1.iterrows():
        long_rows.append(_row_from_kruskal(phase, "q1", "delta_prox", r))

    # Q2
    meta, P, syll_ids = compositions_from_bouts(
        bouts, phase_layer=phase, condition_layer="novel_obj"
    )
    k_rich = kruskal_within_sex(meta, metric="richness")
    k_h = kruskal_within_sex(meta, metric="shannon_bits")
    perm = permanova_within_sex(meta, P)
    v2 = judge_q2(k_rich, k_h, perm)
    for _, r in k_rich.iterrows():
        long_rows.append(_row_from_kruskal(phase, "q2", "richness", r))
    for _, r in k_h.iterrows():
        long_rows.append(_row_from_kruskal(phase, "q2", "shannon_bits", r))
    for _, r in perm.iterrows():
        long_rows.append(
            {
                "phase_layer": phase,
                "question": "q2",
                "metric": "braycurtis_composition",
                "operation": "DIFFERENCE+TEST analogy-only",
                "sex": r["sex"],
                "test": "permanova",
                "stat": "",
                "p": r["p"],
                "n": r["n"],
                "n_noSD": r["n_noSD"],
                "n_GHSD": r["n_GHSD"],
                "n_RBSD": r["n_RBSD"],
                "median_noSD": "",
                "median_GHSD": "",
                "median_RBSD": "",
                "F": r["F"],
                "n_perm": r["n_perm"],
                "hit_p05": bool(pd.notna(r["p"]) and float(r["p"]) < 0.05),
            }
        )

    hope = "baseline_should_be_quiet" if phase == "NOR_BL" else "tx_or_recovery_may_hit"
    summary = {
        "phase_layer": phase,
        "bout_csv": str(bout_csv),
        "n_animals_q1": int(len(animals)),
        "n_animals_q2": int(len(meta)),
        "n_syllables": int(syll_ids.size),
        "hope": hope,
        "q1": v1["q1"],
        "q1_hit_sexes": v1["q1_hit_sexes"],
        "q2": v2["q2"],
        "q2_richness_hit_sexes": v2["q2_richness_hit_sexes"],
        "q2_shannon_hit_sexes": v2["q2_shannon_hit_sexes"],
        "q2_permanova_hit_sexes": v2["q2_permanova_hit_sexes"],
        "pattern_ok": (
            (v1["q1"] == "miss" and v2["q2"] in {"miss", "miss_richness_only"})
            if phase == "NOR_BL"
            else None
        ),
    }
    return long_rows, summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    root = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017")
    ap.add_argument("--ensemble-root", type=Path, default=root)
    ap.add_argument("--model", type=str, default=str(LOCKED["model"]))
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=None,
    )
    args = ap.parse_args(argv)
    art = args.ensemble_root / "_nor_object_mi" / args.model
    out = args.out_dir or (
        args.ensemble_root / "_nor_object_mi" / "simpler_first_phase_grid"
    )
    out.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, object]] = []
    summaries: list[dict[str, object]] = []
    for phase, tag in PHASES:
        bout_csv = art / tag / "ladder_bout_features.csv"
        if not bout_csv.exists():
            summaries.append(
                {"phase_layer": phase, "status": "missing_bout_csv", "bout_csv": str(bout_csv)}
            )
            print(f"MISSING {phase}: {bout_csv}", flush=True)
            continue
        print(f"running {phase} …", flush=True)
        rows, summary = run_phase(bout_csv, phase)
        all_rows.extend(rows)
        summaries.append({"status": "ok", **summary})

    long_df = pd.DataFrame(all_rows)
    long_path = out / "q1_q2_phase_tests_long.csv"
    long_df.to_csv(long_path, index=False)
    summary = {
        "model": args.model,
        "cleanup": "raw",
        "condition_layer": "novel_obj",
        "phases": [p for p, _ in PHASES],
        "n_test_rows": int(len(long_df)),
        "per_phase": summaries,
        "path": str(long_path),
        "hope": "BL quiet; TX or REC3/REC11 may show tx hits",
    }
    (out / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Compact console table
    if not long_df.empty:
        show = long_df.copy()
        show["p"] = show["p"].map(lambda x: f"{float(x):.3g}" if pd.notna(x) and x != "" else "")
        cols = ["phase_layer", "question", "metric", "sex", "test", "p", "hit_p05"]
        print(show[cols].to_string(index=False))
    print(json.dumps({"path": str(long_path), "per_phase": summaries}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
