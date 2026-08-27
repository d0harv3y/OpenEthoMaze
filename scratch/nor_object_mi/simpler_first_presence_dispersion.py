"""Write across-model dispersion tables from an existing presence deltas CSV.

Does not re-run bout ladders. Reads ``presence_step_deltas_per_animal.csv`` and
writes dispersion (+ optional within-ss) tables next to it.

Regen:
  uv run python scratch/nor_object_mi/simpler_first_presence_dispersion.py
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

from nor_object_mi.simpler_first_presence import (  # noqa: E402
    across_model_dispersion,
    across_model_dispersion_by_ss,
    across_model_dispersion_summary,
)

DEFAULT_DELTAS = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_presence_steps\presence_step_deltas_per_animal.csv"
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--deltas", type=Path, default=DEFAULT_DELTAS)
    ap.add_argument("--out-dir", type=Path, default=None)
    args = ap.parse_args(argv)

    out = args.out_dir or args.deltas.parent
    out.mkdir(parents=True, exist_ok=True)
    deltas = pd.read_csv(args.deltas)

    disp = across_model_dispersion(deltas)
    summary = across_model_dispersion_summary(disp)
    disp_ss = across_model_dispersion_by_ss(deltas)
    summary_ss = across_model_dispersion_summary(disp_ss) if not disp_ss.empty else pd.DataFrame()

    disp.to_csv(out / "presence_step_across_model_dispersion.csv", index=False)
    summary.to_csv(out / "presence_step_across_model_dispersion_summary.csv", index=False)
    if not disp_ss.empty:
        disp_ss.to_csv(out / "presence_step_across_model_dispersion_by_ss.csv", index=False)
        summary_ss.to_csv(out / "presence_step_across_model_dispersion_by_ss_summary.csv", index=False)

    # Patch INFO artifact map if present (append rows once).
    info = out / "INFO_presence_steps.md"
    if info.exists():
        text = info.read_text(encoding="utf-8")
        marker = "presence_step_across_model_dispersion.csv"
        if marker not in text:
            insert = (
                "| `presence_step_across_model_dispersion.csv` | animal × phase × step × metric | "
                "across-model median/IQR/MAD/sd of Δ |\n"
                "| `presence_step_across_model_dispersion_summary.csv` | phase × step × metric | "
                "cohort median of per-animal IQR/MAD |\n"
                "| `presence_step_across_model_dispersion_by_ss.csv` | + `ss` stratum | "
                "same, models pooled only within alphabet size |\n"
                "| `presence_step_across_model_dispersion_by_ss_summary.csv` | phase × step × metric × ss | "
                "within-ss cohort salt |\n"
            )
            needle = "| `presence_step_consensus_tests.csv`"
            if needle in text:
                # insert after consensus row block — find the consensus line and append after it
                lines = text.splitlines(keepends=True)
                out_lines: list[str] = []
                for line in lines:
                    out_lines.append(line)
                    if line.startswith("| `presence_step_consensus_tests.csv`"):
                        out_lines.append(insert)
                info.write_text("".join(out_lines), encoding="utf-8")
            salt = (
                "\n\n## Across-model dispersion (salt on consensus)\n\n"
                "For each animal × phase × step × metric, summarize the distribution of "
                "that animal’s paired Δ across kpMS models.\n\n"
                "| Column | Role |\n"
                "| ------ | ---- |\n"
                "| `median` | consensus location (same as median-across-models used in consensus tests) |\n"
                "| `iqr`, `mad` | **primary** across-model dispersion (grain of salt) |\n"
                "| `sd`, `var` | companions (variance language); prefer IQR/MAD on slides |\n"
                "| `iqr_over_abs_median` | relative dispersion |\n"
                "| `magnitude_commensurate_across_models` | True for engagement (`frac_near`, "
                "`mean_dist`); False for COUNT/UNCERTAINTY when pooling all `ss` |\n\n"
                "Engagement salt: use full-grid IQR/MAD. COUNT/UNCERTAINTY: prefer "
                "`*_by_ss*` tables (fixed alphabet) or decision stability "
                "(`frac_hit` / `frac_sign_agree` in the agreement table) — do not treat "
                "pooled Shannon/richness IQR across different K as a precision claim.\n"
            )
            if "## Across-model dispersion" not in text:
                # re-read after possible map patch
                text2 = info.read_text(encoding="utf-8")
                if "## Across-model dispersion" not in text2:
                    # insert before ## Regen if present
                    if "## Regen" in text2:
                        text2 = text2.replace("## Regen", salt + "\n## Regen", 1)
                    else:
                        text2 = text2.rstrip() + salt + "\n"
                    info.write_text(text2, encoding="utf-8")

    payload = {
        "n_animal_metric_rows": int(len(disp)),
        "n_summary_rows": int(len(summary)),
        "n_by_ss_rows": int(len(disp_ss)),
        "path": str(out),
        "deltas": str(args.deltas),
    }
    print(json.dumps(payload, indent=2))
    eng = summary[summary["magnitude_commensurate_across_models"] == True]  # noqa: E712
    if not eng.empty:
        print("\n=== engagement salt (median of per-animal IQR) ===", flush=True)
        print(
            eng[
                [
                    "phase_layer",
                    "step",
                    "metric",
                    "median_of_median",
                    "median_of_iqr",
                    "median_of_mad",
                    "median_of_iqr_over_abs_median",
                ]
            ].to_string(index=False),
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
