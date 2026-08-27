"""CLI: object-presence MI pilot (identical_obj vs no_obj pseudo-loci)."""

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

from nor_object_mi.bout_table import BOUT_FIELDS, build_presence_bout_rows  # noqa: E402
from nor_object_mi.join_keys import filter_cohort, iter_joined_sessions  # noqa: E402
from nor_object_mi.presence_mi import compute_presence_mi  # noqa: E402


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
    p.add_argument("--n-perm", type=int, default=100)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--bin-edges-json",
        type=Path,
        default=None,
        help="Reuse frozen dist_any edges (shared across models/phases)",
    )
    p.add_argument(
        "--min-bout-frames",
        type=int,
        default=None,
        help="Absorb syllable bouts shorter than this (frames); default: no cleanup",
    )
    args = p.parse_args(argv)

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    with h5py.File(args.nor_h5, "r") as nor_h5, h5py.File(args.kpms_results, "r") as kpms_h5:
        cohort = filter_cohort(nor_h5)
        (out_dir / "cohort_filter.json").write_text(json.dumps(cohort, indent=2), encoding="utf-8")
        kept = set(cohort["kept_ids"])  # type: ignore[arg-type]

        sessions = list(
            iter_joined_sessions(nor_h5, kpms_h5, kept_ids=kept, phase_layer=args.phase_layer)
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
            if s.condition_layer in {"identical_obj", "no_obj"}
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

        bout_rows, bout_summary = build_presence_bout_rows(
            nor_h5,
            kpms_h5,
            sessions,
            min_bout_frames=args.min_bout_frames,
        )
        _write_csv(out_dir / "presence_bout_features.csv", list(BOUT_FIELDS), bout_rows)
        (out_dir / "bout_build_summary.json").write_text(
            json.dumps(bout_summary, indent=2), encoding="utf-8"
        )

        if not bout_rows:
            summary = {"status": "failed", "reason": "no bout rows", "bout_summary": bout_summary}
            (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
            print(json.dumps(summary, indent=2))
            return 1

        bin_edges_payload = None
        if args.bin_edges_json is not None:
            bin_edges_payload = json.loads(args.bin_edges_json.read_text(encoding="utf-8"))

        mi_rows, delta_rows, group_tests, bin_edges = compute_presence_mi(
            bout_rows,
            n_bins=args.n_bins,
            n_perm=args.n_perm,
            seed=args.seed,
            bin_edges_payload=bin_edges_payload,
        )
        (out_dir / "bin_edges_dist_any.json").write_text(
            json.dumps(bin_edges, indent=2), encoding="utf-8"
        )

        mi_fields = [
            "animal_id",
            "sex",
            "tx",
            "cohort",
            "phase_layer",
            "condition_layer",
            "object_presence",
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
        _write_csv(out_dir / "mi_per_animal_presence.csv", mi_fields, mi_rows)

        delta_fields = [
            "animal_id",
            "sex",
            "tx",
            "cohort",
            "phase_layer",
            "excess_present",
            "excess_absent",
            "delta_excess_present_minus_absent",
            "mi_mm_present",
            "mi_mm_absent",
            "n_bouts_present",
            "n_bouts_absent",
        ]
        _write_csv(out_dir / "mi_delta_presence_per_animal.csv", delta_fields, delta_rows)

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
        _write_csv(out_dir / "group_presence_tests.csv", group_fields, group_tests)

        by_presence: dict[str, list[float]] = defaultdict(list)
        for r in mi_rows:
            by_presence[str(r["object_presence"])].append(float(r["excess"]))
        excess_medians = {k: float(np.median(v)) for k, v in sorted(by_presence.items())}
        delta_median = (
            float(np.median([float(r["delta_excess_present_minus_absent"]) for r in delta_rows]))
            if delta_rows
            else float("nan")
        )

        summary = {
            "status": "ok",
            "question": "excess_I(dist_any) with vs without object presence",
            "phase_layer": args.phase_layer,
            "dist_any": "nearest of two loci; no_obj uses animal×phase pseudo-loci from id+nvl centers",
            "n_bins": args.n_bins,
            "n_perm": args.n_perm,
            "seed": args.seed,
            "min_bout_frames": args.min_bout_frames,
            "n_bout_rows": len(bout_rows),
            "n_delta_animals": len(delta_rows),
            "median_excess_by_presence": excess_medians,
            "median_delta_present_minus_absent": delta_median,
            "group_tests": group_tests,
            "bout_summary": bout_summary,
            "cohort": {
                "n_kept": cohort["n_kept"],
                "dropped_non_animal_ids": cohort["dropped_non_animal_ids"],
            },
        }
        (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(
            json.dumps(
                {
                    "status": "ok",
                    "n_delta_animals": len(delta_rows),
                    "median_excess_by_presence": excess_medians,
                    "median_delta_present_minus_absent": delta_median,
                    "group_tests": [g for g in group_tests if g.get("factor") in {"presence_paired", "tx", "sex"}][
                        :8
                    ],
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
