"""Restack ladder tests (Wilcoxon + Kruskal) from existing mi_ladder_per_animal.csv.

Merges syllable and n-gram runs into one long table:

  …/moseq_251017/_nor_object_mi/condition_ladder_tests_long.csv

Wilcoxon rows: pooled (sex=all) and within-sex (F/M) on step Δ vs 0.
Kruskal rows: within-sex tx contrast on step Δ (existing long tables).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

_SCRATCH_ROOT = Path(__file__).resolve().parents[1]
if str(_SCRATCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRATCH_ROOT))

from nor_object_mi.condition_ladder import (  # noqa: E402
    LADDER_TEST_FIELDS,
    ladder_tests_long,
)

_OUT_DIR_RE = re.compile(
    r"^condition_ladder"
    r"(?:_(?P<phase>NOR_BL|NOR_REC3hr|NOR_REC11hr))?"
    r"(?:_ngram_n(?P<n>\d+)_top(?P<top>\d+))?"
    r"(?P<clean>_clean)?$"
)

META_FIELDS = (
    "model",
    "phase_layer",
    "symbol_kind",
    "pattern_len",
    "cleanup",
    "top_m",
)

LONG_FIELDS = (
    *META_FIELDS,
    *LADDER_TEST_FIELDS,
    "out_dir",
    "status",
)


def parse_out_dir_name(name: str) -> dict[str, object] | None:
    m = _OUT_DIR_RE.match(name)
    if not m:
        return None
    phase = m.group("phase") or "NOR_TX"
    n = m.group("n")
    top = m.group("top")
    cleanup = "clean" if m.group("clean") else "raw"
    if n is not None:
        return {
            "phase_layer": phase,
            "symbol_kind": "ngram",
            "pattern_len": int(n),
            "cleanup": cleanup,
            "top_m": int(top) if top is not None else "",
        }
    return {
        "phase_layer": phase,
        "symbol_kind": "syllable",
        "pattern_len": 1,
        "cleanup": cleanup,
        "top_m": "",
    }


def _load_csv(path: Path) -> list[dict[str, object]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def restack(art_root: Path) -> tuple[list[dict[str, object]], dict[str, object]]:
    rows_out: list[dict[str, object]] = []
    n_runs = 0
    n_missing = 0
    for model_dir in sorted(art_root.glob("paramscan_*")):
        if not model_dir.is_dir():
            continue
        model = model_dir.name
        for out_dir in sorted(model_dir.glob("condition_ladder*")):
            if not out_dir.is_dir():
                continue
            meta = parse_out_dir_name(out_dir.name)
            if meta is None:
                continue
            ladder_path = out_dir / "mi_ladder_per_animal.csv"
            n_runs += 1
            if not ladder_path.exists():
                n_missing += 1
                rows_out.append(
                    {
                        "model": model,
                        **meta,
                        "panel": "",
                        "step": "",
                        "sex": "",
                        "test": "",
                        "stat": "",
                        "p": "",
                        "n": "",
                        "median_delta": "",
                        "frac_delta_gt0": "",
                        "n_noSD": "",
                        "n_GHSD": "",
                        "n_RBSD": "",
                        "median_delta_noSD": "",
                        "median_delta_GHSD": "",
                        "median_delta_RBSD": "",
                        "out_dir": str(out_dir),
                        "status": "missing_ladder_csv",
                    }
                )
                continue
            ladder_rows = _load_csv(ladder_path)
            tests = ladder_tests_long(ladder_rows)
            # refresh per-run artifacts
            with (out_dir / "ladder_step_tests.csv").open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(LADDER_TEST_FIELDS), extrasaction="ignore")
                w.writeheader()
                for r in tests:
                    if r["test"] == "wilcoxon_signed_rank":
                        w.writerow(r)
            with (out_dir / "ladder_within_sex_tx_kruskal.csv").open(
                "w", newline="", encoding="utf-8"
            ) as f:
                w = csv.DictWriter(f, fieldnames=list(LADDER_TEST_FIELDS), extrasaction="ignore")
                w.writeheader()
                for r in tests:
                    if r["test"] == "kruskal":
                        w.writerow(r)
            with (out_dir / "ladder_tests_long.csv").open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(LADDER_TEST_FIELDS), extrasaction="ignore")
                w.writeheader()
                for r in tests:
                    w.writerow(r)
            for r in tests:
                rows_out.append(
                    {
                        "model": model,
                        **meta,
                        **r,
                        "out_dir": str(out_dir),
                        "status": "ok",
                    }
                )
    summary = {
        "n_runs": n_runs,
        "n_missing": n_missing,
        "n_rows": len(rows_out),
        "n_wilcoxon": sum(1 for r in rows_out if r.get("test") == "wilcoxon_signed_rank"),
        "n_kruskal": sum(1 for r in rows_out if r.get("test") == "kruskal"),
    }
    return rows_out, summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--art-root",
        type=Path,
        default=Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017\_nor_object_mi"),
    )
    ap.add_argument("--out-csv", type=Path, default=None)
    args = ap.parse_args(argv)
    out_csv = args.out_csv or (args.art_root / "condition_ladder_tests_long.csv")
    rows, summary = restack(args.art_root)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(LONG_FIELDS), extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    summary_path = out_csv.with_name(out_csv.stem + "_summary.json")
    summary = {
        **summary,
        "out_csv": str(out_csv),
        "tests": {
            "wilcoxon_signed_rank": "pooled (sex=all) + within-sex step Δ vs 0",
            "kruskal": "within-sex tx contrast on step Δ",
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
