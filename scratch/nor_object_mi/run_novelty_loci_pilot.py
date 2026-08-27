"""CLI: novelty fam/nvl MI with independent spatial loci A/B on novel_obj."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import h5py
import numpy as np

_SCRATCH_ROOT = Path(__file__).resolve().parents[1]
if str(_SCRATCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRATCH_ROOT))

from nor_object_mi.bout_table import BOUT_FIELDS, build_bout_rows  # noqa: E402
from nor_object_mi.compute_mi import compute_novelty_loci_mi  # noqa: E402
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
    p.add_argument("--n-perm", type=int, default=100)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--bin-edges-json",
        type=Path,
        default=None,
        help="Reuse frozen shared dist edges from novelty pilot",
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
        bout_rows, bout_summary = build_bout_rows(
            nor_h5,
            kpms_h5,
            sessions,
            condition_layers=("novel_obj", "identical_obj"),
        )
        _write_csv(out_dir / "object_bout_features_loci.csv", list(BOUT_FIELDS), bout_rows)
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

        mi_rows, delta_rows, group_tests, bin_edges = compute_novelty_loci_mi(
            bout_rows,
            n_bins=args.n_bins,
            n_perm=args.n_perm,
            seed=args.seed,
            bin_edges_payload=bin_edges_payload,
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
        _write_csv(out_dir / "mi_per_animal_novelty_loci.csv", mi_fields, mi_rows)

        delta_fields = [
            "animal_id",
            "sex",
            "tx",
            "cohort",
            "phase_layer",
            "nvl_nearest_hist_locus",
            "excess_fam",
            "excess_nvl",
            "delta_excess_nvl_minus_fam",
            "excess_locus_a",
            "excess_locus_b",
            "delta_excess_locus_b_minus_a",
            "excess_nvl_side_hist",
            "excess_other_hist",
            "delta_excess_nvl_side_minus_other",
            "mi_mm_fam",
            "mi_mm_nvl",
            "mi_mm_locus_a",
            "mi_mm_locus_b",
            "n_bouts",
        ]
        _write_csv(out_dir / "mi_delta_novelty_loci_per_animal.csv", delta_fields, delta_rows)

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
        _write_csv(out_dir / "group_novelty_loci_tests.csv", group_fields, group_tests)

        nov = [float(r["delta_excess_nvl_minus_fam"]) for r in delta_rows]
        spa = [float(r["delta_excess_locus_b_minus_a"]) for r in delta_rows]
        nvl_side = [float(r["delta_excess_nvl_side_minus_other"]) for r in delta_rows]
        tag_counts = {"a": 0, "b": 0}
        for r in delta_rows:
            t = str(r.get("nvl_nearest_hist_locus", ""))
            if t in tag_counts:
                tag_counts[t] += 1

        def _wil(factor: str) -> object | None:
            hit = next((t for t in group_tests if t.get("factor") == factor), None)
            return None if hit is None else hit.get("p")

        snapshot = {
            "status": "ok",
            "phase_layer": args.phase_layer,
            "n_animals": len(delta_rows),
            "nvl_nearest_hist_locus_counts": tag_counts,
            "novelty": {
                "median_delta": float(np.median(nov)) if nov else None,
                "frac_gt0": float(np.mean(np.asarray(nov) > 0)) if nov else None,
                "wilcoxon_p": _wil("novelty_paired"),
            },
            "spatial_hist": {
                "median_delta": float(np.median(spa)) if spa else None,
                "frac_gt0": float(np.mean(np.asarray(spa) > 0)) if spa else None,
                "wilcoxon_p": _wil("spatial_paired"),
            },
            "nvl_side_hist": {
                "median_delta": float(np.median(nvl_side)) if nvl_side else None,
                "frac_gt0": float(np.mean(np.asarray(nvl_side) > 0)) if nvl_side else None,
                "wilcoxon_p": _wil("nvl_side_paired"),
            },
        }
        summary = {
            **snapshot,
            "question": (
                "novelty Δ (nvl−fam) vs hist-locus Δ (B−A) vs nvl-side hist Δ "
                "(excess at hist locus nearest session nvl − other)"
            ),
            "locus_policy": "hist_2means_x_order_fixed",
            "n_bins": args.n_bins,
            "n_perm": args.n_perm,
            "seed": args.seed,
            "n_bout_rows": len(bout_rows),
            "group_tests": group_tests,
            "bout_summary": bout_summary,
            "cohort": {
                "n_kept": cohort["n_kept"],
                "dropped_non_animal_ids": cohort["dropped_non_animal_ids"],
            },
        }
        (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(snapshot, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
