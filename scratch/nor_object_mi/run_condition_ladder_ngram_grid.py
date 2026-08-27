"""Fan out n-gram condition-ladder runs; stack Kruskal long table.

Jobs: models × phases × pattern_len × {raw, clean}.
Reuses existing syllable ``ladder_bout_features.csv`` when present
(``condition_ladder*`` / ``*_clean``), then expands to n-grams with
top-M + OTHER and span-mean distances.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

_SCRATCH_ROOT = Path(__file__).resolve().parents[1]
if str(_SCRATCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRATCH_ROOT))

from nor_object_mi.condition_ladder import LADDER_TEST_FIELDS, ladder_tests_long  # noqa: E402
from nor_object_mi.ngram_decisions import DEFAULT_TOP_M  # noqa: E402

PHASE_OUT_TAG = {
    "NOR_TX": "condition_ladder",
    "NOR_BL": "condition_ladder_NOR_BL",
    "NOR_REC3hr": "condition_ladder_NOR_REC3hr",
    "NOR_REC11hr": "condition_ladder_NOR_REC11hr",
}

TEST_FIELDS = [
    "model",
    "phase_layer",
    "pattern_len",
    "cleanup",
    "top_m",
    *LADDER_TEST_FIELDS,
    "out_dir",
    "status",
]


def _load_ladder_csv(path: Path) -> list[dict[str, object]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _kruskal_rows(
    *,
    model: str,
    phase: str,
    pattern_len: int,
    cleanup: str,
    top_m: int,
    out_dir: Path,
) -> list[dict[str, object]]:
    ladder_path = out_dir / "mi_ladder_per_animal.csv"
    if not ladder_path.exists():
        return [
            {
                "model": model,
                "phase_layer": phase,
                "pattern_len": pattern_len,
                "cleanup": cleanup,
                "top_m": top_m,
                "panel": "",
                "step": "",
                "sex": "",
                "test": "kruskal",
                "stat": "",
                "p": "",
                "n_noSD": "",
                "n_GHSD": "",
                "n_RBSD": "",
                "median_delta_noSD": "",
                "median_delta_GHSD": "",
                "median_delta_RBSD": "",
                "out_dir": str(out_dir),
                "status": "missing_ladder_csv",
            }
        ]
    rows = _load_ladder_csv(ladder_path)
    long_rows = ladder_tests_long(rows)
    with (out_dir / "ladder_tests_long.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(LADDER_TEST_FIELDS), extrasaction="ignore")
        w.writeheader()
        for r in long_rows:
            w.writerow(r)
    out: list[dict[str, object]] = []
    for r in long_rows:
        out.append(
            {
                "model": model,
                "phase_layer": phase,
                "pattern_len": pattern_len,
                "cleanup": cleanup,
                "top_m": top_m,
                **r,
                "out_dir": str(out_dir),
                "status": "ok",
            }
        )
    return out


def _bout_csv_for(art_model: Path, phase: str, cleanup: str) -> Path | None:
    tag = PHASE_OUT_TAG.get(phase, f"condition_ladder_{phase}")
    if cleanup == "clean":
        tag = f"{tag}_clean"
    path = art_model / tag / "ladder_bout_features.csv"
    return path if path.exists() else None


def _run_one(
    *,
    repo: Path,
    nor_h5: Path,
    results_h5: Path,
    art_model: Path,
    out_dir: Path,
    phase: str,
    pattern_len: int,
    cleanup: str,
    top_m: int,
    max_span_frames: int | None,
    bin_edges: Path,
    n_perm: int,
    seed: int,
    skip_existing: bool,
) -> list[dict[str, object]]:
    model = results_h5.parent.name
    ladder_csv = out_dir / "mi_ladder_per_animal.csv"
    if skip_existing and ladder_csv.exists():
        return _kruskal_rows(
            model=model,
            phase=phase,
            pattern_len=pattern_len,
            cleanup=cleanup,
            top_m=top_m,
            out_dir=out_dir,
        )

    bout_csv = _bout_csv_for(art_model, phase, cleanup)
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(repo / "scratch" / "nor_object_mi" / "run_condition_ladder_ngram.py"),
        "--nor-h5",
        str(nor_h5),
        "--kpms-results",
        str(results_h5),
        "--out-dir",
        str(out_dir),
        "--phase-layer",
        phase,
        "--pattern-len",
        str(pattern_len),
        "--top-m",
        str(top_m),
        "--n-perm",
        str(n_perm),
        "--seed",
        str(seed),
        "--bin-edges-json",
        str(bin_edges),
    ]
    if max_span_frames is not None:
        cmd.extend(["--max-span-frames", str(max_span_frames)])
    if bout_csv is not None:
        cmd.extend(["--reuse-bout-csv", str(bout_csv)])
    elif cleanup == "clean":
        cmd.extend(["--min-bout-frames", "3"])

    proc = subprocess.run(cmd, cwd=str(repo), capture_output=True, text=True)
    if proc.returncode != 0 or not ladder_csv.exists():
        err = (proc.stderr or proc.stdout or "")[-500:]
        return [
            {
                "model": model,
                "phase_layer": phase,
                "pattern_len": pattern_len,
                "cleanup": cleanup,
                "top_m": top_m,
                "panel": "",
                "step": "",
                "sex": "",
                "test": "kruskal",
                "stat": "",
                "p": "",
                "n_noSD": "",
                "n_GHSD": "",
                "n_RBSD": "",
                "median_delta_noSD": "",
                "median_delta_GHSD": "",
                "median_delta_RBSD": "",
                "out_dir": str(out_dir),
                "status": f"failed_rc={proc.returncode}:{err}",
            }
        ]
    return _kruskal_rows(
        model=model,
        phase=phase,
        pattern_len=pattern_len,
        cleanup=cleanup,
        top_m=top_m,
        out_dir=out_dir,
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--ensemble-root",
        type=Path,
        default=Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"),
    )
    ap.add_argument(
        "--nor-h5",
        type=Path,
        default=Path(r"C:\Users\admin\Documents\work\sack\datas\impress\my_NOR_results.h5"),
    )
    ap.add_argument("--repo", type=Path, default=Path(r"C:\Users\admin\code\OpenEthoMaze"))
    ap.add_argument("--bin-edges-json", type=Path, default=None)
    ap.add_argument(
        "--phases",
        nargs="+",
        default=["NOR_BL", "NOR_TX", "NOR_REC3hr", "NOR_REC11hr"],
    )
    ap.add_argument("--pattern-lens", nargs="+", type=int, default=[2, 3])
    ap.add_argument("--cleanups", nargs="+", default=["raw", "clean"])
    ap.add_argument("--top-m", type=int, default=DEFAULT_TOP_M)
    ap.add_argument("--max-span-frames", type=int, default=None)
    ap.add_argument("--n-perm", type=int, default=100)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument(
        "--models",
        nargs="*",
        default=None,
        help="Optional subset of paramscan_* names",
    )
    args = ap.parse_args(argv)

    art_root = args.ensemble_root / "_nor_object_mi"
    ref_edges = args.bin_edges_json or (
        art_root / "paramscan_s1-1e8_s2-1e5_ss-50" / "bin_edges.json"
    )
    if not ref_edges.exists():
        # fall back to condition_ladder edges
        alt = (
            art_root
            / "paramscan_s1-1e8_s2-1e5_ss-50"
            / "condition_ladder"
            / "bin_edges.json"
        )
        if alt.exists():
            ref_edges = alt
        else:
            raise SystemExit(f"missing frozen edges: {ref_edges}")

    models = sorted(
        [
            p
            for p in args.ensemble_root.iterdir()
            if p.is_dir() and p.name.startswith("paramscan_") and (p / "results.h5").exists()
        ],
        key=lambda p: p.name,
    )
    if args.models:
        wanted = set(args.models)
        models = [m for m in models if m.name in wanted]

    jobs: list[tuple[Path, Path, str, int, str, Path]] = []
    for model_dir in models:
        art_model = art_root / model_dir.name
        for phase in args.phases:
            for n in args.pattern_lens:
                for cleanup in args.cleanups:
                    tag = (
                        f"{PHASE_OUT_TAG.get(phase, f'condition_ladder_{phase}')}"
                        f"_ngram_n{n}_top{int(args.top_m)}"
                    )
                    if cleanup == "clean":
                        tag = f"{tag}_clean"
                    out_dir = art_model / tag
                    jobs.append(
                        (model_dir / "results.h5", art_model, phase, int(n), cleanup, out_dir)
                    )

    print(
        f"jobs={len(jobs)} models={len(models)} phases={args.phases} "
        f"n={args.pattern_lens} cleanups={args.cleanups} top_m={args.top_m} "
        f"workers={args.workers}"
    )
    print(f"frozen_edges={ref_edges}")

    all_rows: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = {
            ex.submit(
                _run_one,
                repo=args.repo,
                nor_h5=args.nor_h5,
                results_h5=results_h5,
                art_model=art_model,
                out_dir=out_dir,
                phase=phase,
                pattern_len=pattern_len,
                cleanup=cleanup,
                top_m=int(args.top_m),
                max_span_frames=args.max_span_frames,
                bin_edges=ref_edges,
                n_perm=int(args.n_perm),
                seed=int(args.seed),
                skip_existing=bool(args.skip_existing),
            ): (results_h5.parent.name, phase, pattern_len, cleanup)
            for results_h5, art_model, phase, pattern_len, cleanup, out_dir in jobs
        }
        done = 0
        for fut in as_completed(futs):
            done += 1
            model, phase, n, cleanup = futs[fut]
            rows = fut.result()
            all_rows.extend(rows)
            ok = sum(1 for r in rows if r.get("status") == "ok")
            st = rows[0].get("status") if rows else "empty"
            print(
                f"[{done}/{len(jobs)}] {model} {phase} n={n} {cleanup} "
                f"kruskal_ok={ok} status={st}",
                flush=True,
            )

    out_csv = art_root / "condition_ladder_ngram_tests_long.csv"
    rows_sorted = sorted(
        all_rows,
        key=lambda r: (
            str(r.get("model", "")),
            str(r.get("phase_layer", "")),
            int(r.get("pattern_len", 0) or 0),
            str(r.get("cleanup", "")),
            str(r.get("test", "")),
            str(r.get("panel", "")),
            str(r.get("step", "")),
            str(r.get("sex", "")),
        ),
    )
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=TEST_FIELDS, extrasaction="ignore")
        w.writeheader()
        for row in rows_sorted:
            w.writerow(row)

    n_ok = sum(1 for r in rows_sorted if r.get("status") == "ok")
    n_fail = sum(1 for r in rows_sorted if r.get("status") != "ok")
    n_sig = sum(
        1
        for r in rows_sorted
        if r.get("status") == "ok"
        and r.get("p") not in ("", None)
        and float(r["p"]) < 0.05  # type: ignore[arg-type]
    )
    summary = {
        "n_rows": len(rows_sorted),
        "n_ok": n_ok,
        "n_fail_rows": n_fail,
        "n_p_lt_0.05": n_sig,
        "n_jobs": len(jobs),
        "n_models": len(models),
        "phases": list(args.phases),
        "pattern_lens": list(args.pattern_lens),
        "cleanups": list(args.cleanups),
        "top_m": int(args.top_m),
        "max_span_frames": args.max_span_frames,
        "path": str(out_csv),
    }
    summary_json = art_root / "condition_ladder_ngram_tests_long_summary.json"
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if n_ok > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
