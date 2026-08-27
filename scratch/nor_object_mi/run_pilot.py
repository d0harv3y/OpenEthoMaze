"""CLI: NOR_TX object-distance MI pilot on one kpMS paramscan model."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import h5py
import numpy as np

_SCRATCH_ROOT = Path(__file__).resolve().parents[1]
if str(_SCRATCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRATCH_ROOT))

from nor_object_mi.bout_table import BOUT_FIELDS, build_bout_rows  # noqa: E402
from nor_object_mi.compute_mi import compute_pilot_mi  # noqa: E402
from nor_object_mi.join_keys import filter_cohort, iter_joined_sessions  # noqa: E402


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--nor-h5", type=Path, required=True)
    p.add_argument("--kpms-results", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--phase-layer", type=str, default="NOR_TX")
    p.add_argument("--n-bins", type=int, default=5)
    p.add_argument("--n-perm", type=int, default=200)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args(argv)

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    with h5py.File(args.nor_h5, "r") as nor_h5, h5py.File(args.kpms_results, "r") as kpms_h5:
        cohort = filter_cohort(nor_h5)
        (out_dir / "cohort_filter.json").write_text(json.dumps(cohort, indent=2), encoding="utf-8")
        kept = set(cohort["kept_ids"])  # type: ignore[arg-type]

        sessions = list(
            iter_joined_sessions(
                nor_h5,
                kpms_h5,
                kept_ids=kept,
                phase_layer=args.phase_layer,
            )
        )
        join_rows = [
            {
                "kpms_key": s.kpms_key,
                "animal_id": s.animal_id,
                "raw_session": s.raw_session,
                "phase_layer": s.phase_layer,
                "condition_layer": s.condition_layer,
                "tx": s.tx,
                "sex": s.sex,
                "cohort": s.cohort,
            }
            for s in sessions
        ]
        _write_csv(
            out_dir / "session_join.csv",
            [
                "kpms_key",
                "animal_id",
                "raw_session",
                "phase_layer",
                "condition_layer",
                "tx",
                "sex",
                "cohort",
            ],
            join_rows,
        )

        bout_rows, bout_summary = build_bout_rows(
            nor_h5,
            kpms_h5,
            sessions,
            condition_layers=("novel_obj", "identical_obj"),
        )
        _write_csv(out_dir / "object_bout_features.csv", list(BOUT_FIELDS), bout_rows)
        (out_dir / "bout_build_summary.json").write_text(
            json.dumps(bout_summary, indent=2), encoding="utf-8"
        )

        if not bout_rows:
            summary = {
                "status": "failed",
                "reason": "no bout rows",
                "phase_layer": args.phase_layer,
                "n_joined_sessions": len(sessions),
                "cohort": {
                    "n_kept": cohort["n_kept"],
                    "n_dropped_non_animal": cohort["n_dropped_non_animal"],
                    "dropped_non_animal_ids": cohort["dropped_non_animal_ids"],
                    "n_dropped_blank_tx_or_sex": cohort["n_dropped_blank_tx_or_sex"],
                    "dropped_blank": cohort["dropped_blank"],
                },
                "bout_summary": bout_summary,
            }
            (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
            print(json.dumps(summary, indent=2))
            return 1

        mi_rows, delta_rows, group_tests, bin_edges = compute_pilot_mi(
            bout_rows,
            n_bins=args.n_bins,
            n_perm=args.n_perm,
            seed=args.seed,
        )
        (out_dir / "bin_edges.json").write_text(json.dumps(bin_edges, indent=2), encoding="utf-8")

        mi_fields = [
            "animal_id",
            "sex",
            "tx",
            "cohort",
            "phase_layer",
            "stim_var",
            "mi_type",
            "n_bouts",
            "H_stim",
            "H_syll",
            "mi_raw",
            "mi_mm",
            "null_circ_mean",
            "null_circ_p",
            "excess",
        ]
        _write_csv(out_dir / "mi_per_animal.csv", mi_fields, mi_rows)

        delta_fields = [
            "animal_id",
            "sex",
            "tx",
            "cohort",
            "phase_layer",
            "excess_fam",
            "excess_nvl",
            "delta_excess_nvl_minus_fam",
            "mi_mm_fam",
            "mi_mm_nvl",
            "n_bouts_fam",
            "n_bouts_nvl",
        ]
        _write_csv(out_dir / "mi_delta_per_animal.csv", delta_fields, delta_rows)

        group_fields = [
            "sex_stratum",
            "factor",
            "level_a",
            "level_b",
            "n_a",
            "n_b",
            "median_a",
            "median_b",
            "stat",
            "p",
            "test",
            "metric",
        ]
        _write_csv(out_dir / "group_delta_tests.csv", group_fields, group_tests)

        by_tx: dict[str, list[float]] = defaultdict(list)
        by_sex_tx: dict[str, list[float]] = defaultdict(list)
        for r in delta_rows:
            tx = str(r["tx"])
            sex = str(r["sex"])
            val = float(r["delta_excess_nvl_minus_fam"])
            by_tx[tx].append(val)
            by_sex_tx[f"{sex}|{tx}"].append(val)
        tx_medians = {k: float(np.median(v)) for k, v in sorted(by_tx.items())}
        sex_tx_medians = {k: float(np.median(v)) for k, v in sorted(by_sex_tx.items())}

        summary = {
            "status": "ok",
            "phase_layer": args.phase_layer,
            "kpms_results": str(args.kpms_results),
            "nor_h5": str(args.nor_h5),
            "n_bins": args.n_bins,
            "n_perm": args.n_perm,
            "seed": args.seed,
            "keypoint": "spot (mean nose,neck,spine)",
            "cohort": {
                "n_kept": cohort["n_kept"],
                "kept_ids": cohort["kept_ids"],
                "n_dropped_non_animal": cohort["n_dropped_non_animal"],
                "dropped_non_animal_ids": cohort["dropped_non_animal_ids"],
                "n_dropped_blank_tx_or_sex": cohort["n_dropped_blank_tx_or_sex"],
                "dropped_blank": cohort["dropped_blank"],
            },
            "n_joined_sessions": len(sessions),
            "n_novel_obj_sessions": sum(1 for s in sessions if s.condition_layer == "novel_obj"),
            "n_bout_rows": len(bout_rows),
            "n_mi_rows": len(mi_rows),
            "n_delta_animals": len(delta_rows),
            "tx_median_delta_excess": tx_medians,
            "sex_tx_median_delta_excess": sex_tx_medians,
            "group_tests": group_tests,
            "bout_summary": bout_summary,
        }
        (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(
            json.dumps(
                {
                    "status": summary["status"],
                    "n_kept": cohort["n_kept"],
                    "dropped_non_animal_ids": cohort["dropped_non_animal_ids"],
                    "n_bout_rows": len(bout_rows),
                    "n_delta_animals": len(delta_rows),
                    "tx_median_delta_excess": tx_medians,
                    "sex_tx_median_delta_excess": sex_tx_medians,
                    "group_tests": group_tests,
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
