"""CLI: condition ladder on n-gram symbols (top-M + OTHER, span-mean stim).

Reuses ladder bout rows (or builds them), expands to n-gram occurrences with
mean distance over the span, remaps to top-M + OTHER, then runs the same
excess-MI / Wilcoxon / Kruskal ladder as syllable bouts.

Knobs (pseudo-reduce without re-mining kpMS):
  --pattern-len N          analyze a single order (1..max_n mined upstream)
  --max-span-frames S      drop occurrences with span > S frames
  --top-m M                alphabet size before OTHER
  --min-bout-frames K      absorb short syllable bouts before bout table build
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import h5py

_SCRATCH_ROOT = Path(__file__).resolve().parents[1]
if str(_SCRATCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRATCH_ROOT))

from nor_object_mi.bout_table import BOUT_FIELDS, build_ladder_bout_rows  # noqa: E402
from nor_object_mi.condition_ladder import (  # noqa: E402
    LADDER_TEST_FIELDS,
    compute_ladder_mi,
    ladder_tests_long,
    ladder_wilcoxon_steps,
    summarize_side_tags,
)
from nor_object_mi.join_keys import filter_cohort, iter_joined_sessions  # noqa: E402
from nor_object_mi.ngram_decisions import DEFAULT_TOP_M  # noqa: E402
from nor_object_mi.ngram_table import (  # noqa: E402
    NGRAM_OCC_FIELDS,
    assign_top_m_other,
    ngram_rows_from_bout_rows,
)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})


def _load_bout_csv(path: Path) -> list[dict[str, object]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--nor-h5", type=Path, required=True)
    p.add_argument("--kpms-results", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--phase-layer", type=str, default="NOR_TX")
    p.add_argument("--pattern-len", type=int, required=True, help="n-gram order to analyze")
    p.add_argument("--top-m", type=int, default=DEFAULT_TOP_M)
    p.add_argument("--max-span-frames", type=int, default=None)
    p.add_argument("--n-bins", type=int, default=5)
    p.add_argument("--n-perm", type=int, default=100)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--bin-edges-json", type=Path, default=None)
    p.add_argument(
        "--min-bout-frames",
        type=int,
        default=None,
        help="Absorb syllable bouts shorter than this before building bout table",
    )
    p.add_argument(
        "--reuse-bout-csv",
        type=Path,
        default=None,
        help="Skip bout rebuild; reuse an existing ladder_bout_features.csv",
    )
    args = p.parse_args(argv)

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.reuse_bout_csv is not None:
        bout_rows = _load_bout_csv(args.reuse_bout_csv)
        bout_summary = {"status": "reused", "path": str(args.reuse_bout_csv), "n_rows": len(bout_rows)}
    else:
        with h5py.File(args.nor_h5, "r") as nor_h5, h5py.File(args.kpms_results, "r") as kpms_h5:
            cohort = filter_cohort(nor_h5)
            (out_dir / "cohort_filter.json").write_text(
                json.dumps(cohort, indent=2), encoding="utf-8"
            )
            kept = set(cohort["kept_ids"])  # type: ignore[arg-type]
            sessions = list(
                iter_joined_sessions(
                    nor_h5, kpms_h5, kept_ids=kept, phase_layer=args.phase_layer
                )
            )
            bout_rows, bout_summary = build_ladder_bout_rows(
                nor_h5,
                kpms_h5,
                sessions,
                min_bout_frames=args.min_bout_frames,
            )
            _write_csv(out_dir / "ladder_bout_features.csv", list(BOUT_FIELDS), bout_rows)

    (out_dir / "bout_build_summary.json").write_text(
        json.dumps(bout_summary, indent=2), encoding="utf-8"
    )
    if not bout_rows:
        print(json.dumps({"status": "failed", "reason": "no bout rows"}, indent=2))
        return 1

    ngram_rows = ngram_rows_from_bout_rows(
        bout_rows,
        pattern_len=int(args.pattern_len),
        max_span_frames=args.max_span_frames,
    )
    ngram_rows, alphabet = assign_top_m_other(ngram_rows, top_m=int(args.top_m))
    _write_csv(out_dir / "ladder_ngram_features.csv", list(NGRAM_OCC_FIELDS), ngram_rows)
    (out_dir / "ngram_alphabet.json").write_text(
        json.dumps(
            {
                **alphabet,
                "pattern_len": int(args.pattern_len),
                "max_span_frames": args.max_span_frames,
                "min_bout_frames": args.min_bout_frames,
                "stim": "span_mean_distance_boutframe_weighted",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    bin_edges_payload = None
    if args.bin_edges_json is not None:
        bin_edges_payload = json.loads(args.bin_edges_json.read_text(encoding="utf-8"))

    mi_rows, ladder_rows, bin_edges = compute_ladder_mi(
        ngram_rows,
        n_bins=args.n_bins,
        n_perm=args.n_perm,
        seed=args.seed,
        bin_edges_payload=bin_edges_payload,
        symbol_field="pattern_id",
        order_field="ngram_index",
    )
    (out_dir / "bin_edges.json").write_text(json.dumps(bin_edges, indent=2), encoding="utf-8")

    _write_csv(
        out_dir / "mi_per_animal_ladder.csv",
        [
            "animal_id",
            "sex",
            "tx",
            "cohort",
            "phase_layer",
            "condition_layer",
            "stim_var",
            "channel",
            "n_bouts",
            "H_stim",
            "H_syll",
            "mi_raw",
            "mi_mm",
            "null_circ_mean",
            "null_circ_p",
            "excess",
        ],
        mi_rows,
    )
    ladder_fields = [
        "animal_id",
        "sex",
        "tx",
        "cohort",
        "phase_layer",
        "nvl_nearest_hist_locus",
        "fam_nearest_hist_locus",
        "excess_no_obj_fam_side",
        "excess_no_obj_nvl_side",
        "excess_identical_fam_side",
        "excess_identical_nvl_side",
        "excess_fam",
        "excess_nvl",
        "delta_identical_minus_no_obj_fam",
        "delta_identical_minus_no_obj_nvl",
        "delta_fam_minus_identical",
        "delta_nvl_minus_identical",
        "delta_nvl_minus_fam",
    ]
    # use whatever keys ladder_rows actually have
    if ladder_rows:
        ladder_fields = list(ladder_rows[0].keys())
    _write_csv(out_dir / "mi_ladder_per_animal.csv", ladder_fields, ladder_rows)

    steps = ladder_wilcoxon_steps(ladder_rows)
    tests = ladder_tests_long(ladder_rows)
    _write_csv(
        out_dir / "ladder_step_tests.csv",
        list(LADDER_TEST_FIELDS),
        [r for r in tests if r["test"] == "wilcoxon_signed_rank"],
    )
    _write_csv(
        out_dir / "ladder_within_sex_tx_kruskal.csv",
        list(LADDER_TEST_FIELDS),
        [r for r in tests if r["test"] == "kruskal"],
    )
    _write_csv(out_dir / "ladder_tests_long.csv", list(LADDER_TEST_FIELDS), tests)
    side = summarize_side_tags(ngram_rows)
    summary = {
        "status": "ok",
        "phase_layer": args.phase_layer,
        "pattern_len": int(args.pattern_len),
        "top_m": int(args.top_m),
        "max_span_frames": args.max_span_frames,
        "min_bout_frames": args.min_bout_frames,
        "n_bout_rows": len(bout_rows),
        "n_ngram_rows": len(ngram_rows),
        "n_ladder_animals": len(ladder_rows),
        "side_tags": side,
        "symbol_field": "pattern_id",
        "stim": "span_mean_distance_boutframe_weighted",
        "step_tests_pooled": steps,
    }
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
