"""Mine bout n-grams (max_n=5) for all impress paramscan models, raw + clean."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

_SCRATCH_ROOT = Path(__file__).resolve().parents[1]
if str(_SCRATCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRATCH_ROOT))

from nor_object_mi.ngram_decisions import (  # noqa: E402
    DEFAULT_MIN_BOUT_FRAMES_CLEAN,
    MAX_N_MINE,
)
from nor_object_mi.ngram_table import mine_results_h5  # noqa: E402

FIELDS = [
    "pattern_json",
    "pattern_len",
    "count",
    "n_trials",
    "mean_span_frames",
]


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in FIELDS})


def _one(
    *,
    model_dir: Path,
    out_root: Path,
    tag: str,
    min_bout_frames: int | None,
    max_n: int,
    max_span_frames: int | None,
    min_count: int,
) -> dict[str, object]:
    results = model_dir / "results.h5"
    out_dir = out_root / model_dir.name / tag
    out_dir.mkdir(parents=True, exist_ok=True)
    rows, summary = mine_results_h5(
        results,
        max_n=max_n,
        min_bout_frames=min_bout_frames,
        max_span_frames=max_span_frames,
        min_count=min_count,
    )
    _write_csv(out_dir / "ngram_counts.csv", rows)
    summary = {
        **summary,
        "model": model_dir.name,
        "tag": tag,
        "status": "ok",
        "out_dir": str(out_dir),
    }
    (out_dir / "mine_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--kpms-root",
        type=Path,
        default=Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"),
    )
    p.add_argument(
        "--out-root",
        type=Path,
        default=None,
        help="Default: <kpms-root>/_ngram_mine",
    )
    p.add_argument("--max-n", type=int, default=MAX_N_MINE)
    p.add_argument(
        "--max-span-frames",
        type=int,
        default=None,
        help="Optional span cap applied during mining (usually leave unset; filter later)",
    )
    p.add_argument("--min-count", type=int, default=2)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--skip-raw", action="store_true")
    p.add_argument("--skip-clean", action="store_true")
    p.add_argument(
        "--clean-min-bout-frames",
        type=int,
        default=DEFAULT_MIN_BOUT_FRAMES_CLEAN,
    )
    p.add_argument(
        "--models",
        nargs="*",
        default=None,
        help="Optional subset of paramscan_* directory names",
    )
    args = p.parse_args(argv)

    kpms_root = args.kpms_root
    out_root = args.out_root or (kpms_root / "_ngram_mine")
    out_root.mkdir(parents=True, exist_ok=True)

    models = sorted(
        [
            d
            for d in kpms_root.iterdir()
            if d.is_dir() and d.name.startswith("paramscan_") and (d / "results.h5").is_file()
        ]
    )
    if args.models:
        wanted = set(args.models)
        models = [d for d in models if d.name in wanted]

    jobs: list[tuple[Path, str, int | None]] = []
    for mdir in models:
        if not args.skip_raw:
            jobs.append((mdir, "raw", None))
        if not args.skip_clean:
            jobs.append((mdir, "clean", int(args.clean_min_bout_frames)))

    summaries: list[dict[str, object]] = []
    print(f"n_jobs={len(jobs)} out_root={out_root}", flush=True)

    def _run(job: tuple[Path, str, int | None]) -> dict[str, object]:
        mdir, tag, min_bout = job
        print(f"mine {mdir.name} {tag}", flush=True)
        return _one(
            model_dir=mdir,
            out_root=out_root,
            tag=tag,
            min_bout_frames=min_bout,
            max_n=int(args.max_n),
            max_span_frames=args.max_span_frames,
            min_count=int(args.min_count),
        )

    if args.workers <= 1:
        for job in jobs:
            summaries.append(_run(job))
    else:
        with ThreadPoolExecutor(max_workers=int(args.workers)) as ex:
            futs = {ex.submit(_run, job): job for job in jobs}
            for fut in as_completed(futs):
                summaries.append(fut.result())

    summaries.sort(key=lambda s: (str(s.get("model", "")), str(s.get("tag", ""))))
    (out_root / "grid_summary.json").write_text(
        json.dumps({"n": len(summaries), "runs": summaries}, indent=2),
        encoding="utf-8",
    )
    # long coverage-ish table
    cov_path = out_root / "mine_grid_long.csv"
    with cov_path.open("w", newline="", encoding="utf-8") as f:
        fields = [
            "model",
            "tag",
            "n_recordings",
            "n_bouts",
            "n_patterns",
            "max_n",
            "min_bout_frames",
            "max_span_frames",
            "status",
            "out_dir",
        ]
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for s in summaries:
            w.writerow({k: s.get(k, "") for k in fields})
    print(json.dumps({"status": "ok", "n": len(summaries), "out_root": str(out_root)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
