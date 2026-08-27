"""Fan out condition-ladder runs; stack within-sex tx Kruskal into a long table.

For each paramscan model × phase, runs ``run_condition_ladder.py`` (or reuses an
existing ``mi_ladder_per_animal.csv``) and writes a long-form CSV of Kruskal
tests matching the ladder-plot annotations.
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

PHASE_OUT_TAG = {
    "NOR_TX": "condition_ladder",
    "NOR_BL": "condition_ladder_NOR_BL",
    "NOR_REC3hr": "condition_ladder_NOR_REC3hr",
    "NOR_REC11hr": "condition_ladder_NOR_REC11hr",
}

TEST_FIELDS = [
    "model",
    "phase_layer",
    "cleanup",
    *LADDER_TEST_FIELDS,
    "out_dir",
    "status",
]


def _load_ladder_csv(path: Path) -> list[dict[str, object]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _tests_from_ladder(
    *,
    model: str,
    phase: str,
    out_dir: Path,
    cleanup: str,
) -> list[dict[str, object]]:
    ladder_path = out_dir / "mi_ladder_per_animal.csv"
    if not ladder_path.exists():
        return [
            {
                "model": model,
                "phase_layer": phase,
                "cleanup": cleanup,
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
                "cleanup": cleanup,
                **r,
                "out_dir": str(out_dir),
                "status": "ok",
            }
        )
    return out


def _kruskal_from_ladder(
    *,
    model: str,
    phase: str,
    out_dir: Path,
    cleanup: str = "raw",
) -> list[dict[str, object]]:
    return _tests_from_ladder(model=model, phase=phase, out_dir=out_dir, cleanup=cleanup)


def _run_one(
    *,
    repo: Path,
    nor_h5: Path,
    results_h5: Path,
    out_dir: Path,
    phase: str,
    bin_edges: Path,
    n_perm: int,
    seed: int,
    skip_existing: bool,
    min_bout_frames: int | None,
) -> list[dict[str, object]]:
    model = results_h5.parent.name
    ladder_csv = out_dir / "mi_ladder_per_animal.csv"
    if skip_existing and ladder_csv.exists():
        cleanup = "clean" if min_bout_frames is not None else "raw"
        return _kruskal_from_ladder(
            model=model, phase=phase, out_dir=out_dir, cleanup=cleanup
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(repo / "scratch" / "nor_object_mi" / "run_condition_ladder.py"),
        "--nor-h5",
        str(nor_h5),
        "--kpms-results",
        str(results_h5),
        "--out-dir",
        str(out_dir),
        "--phase-layer",
        phase,
        "--n-perm",
        str(n_perm),
        "--seed",
        str(seed),
        "--bin-edges-json",
        str(bin_edges),
    ]
    if min_bout_frames is not None:
        cmd.extend(["--min-bout-frames", str(min_bout_frames)])
    proc = subprocess.run(cmd, cwd=str(repo), capture_output=True, text=True)
    if proc.returncode != 0 or not ladder_csv.exists():
        return [
            {
                "model": model,
                "phase_layer": phase,
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
                "status": f"failed_rc={proc.returncode}",
            }
        ]
    cleanup = "clean" if min_bout_frames is not None else "raw"
    return _kruskal_from_ladder(model=model, phase=phase, out_dir=out_dir, cleanup=cleanup)


def main() -> int:
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
    ap.add_argument(
        "--bin-edges-json",
        type=Path,
        default=None,
        help="Default: ref model novelty bin_edges.json",
    )
    ap.add_argument(
        "--phases",
        nargs="+",
        default=["NOR_BL", "NOR_TX", "NOR_REC3hr", "NOR_REC11hr"],
    )
    ap.add_argument("--n-perm", type=int, default=100)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument(
        "--skip-existing",
        action="store_true",
        help="Reuse existing mi_ladder_per_animal.csv when present",
    )
    ap.add_argument(
        "--min-bout-frames",
        type=int,
        default=None,
        help="Absorb short syllable bouts before MI",
    )
    ap.add_argument(
        "--out-suffix",
        type=str,
        default="",
        help="Appended to condition_ladder out-dir tags (e.g. _clean)",
    )
    args = ap.parse_args()

    art_root = args.ensemble_root / "_nor_object_mi"
    ref_edges = args.bin_edges_json or (
        art_root / "paramscan_s1-1e8_s2-1e5_ss-50" / "bin_edges.json"
    )
    if not ref_edges.exists():
        raise SystemExit(f"missing frozen edges: {ref_edges}")

    suffix = args.out_suffix
    if args.min_bout_frames is not None and not suffix:
        suffix = "_clean"

    models = sorted(
        [
            p
            for p in args.ensemble_root.iterdir()
            if p.is_dir() and p.name.startswith("paramscan_") and (p / "results.h5").exists()
        ],
        key=lambda p: p.name,
    )

    jobs: list[tuple[Path, str, Path]] = []
    for model_dir in models:
        for phase in args.phases:
            tag = PHASE_OUT_TAG.get(phase, f"condition_ladder_{phase}") + suffix
            out_dir = art_root / model_dir.name / tag
            jobs.append((model_dir / "results.h5", phase, out_dir))

    print(
        f"jobs={len(jobs)} models={len(models)} phases={args.phases} "
        f"workers={args.workers} min_bout_frames={args.min_bout_frames} suffix={suffix!r}"
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
                out_dir=out_dir,
                phase=phase,
                bin_edges=ref_edges,
                n_perm=args.n_perm,
                seed=args.seed,
                skip_existing=args.skip_existing,
                min_bout_frames=args.min_bout_frames,
            ): (results_h5.parent.name, phase)
            for results_h5, phase, out_dir in jobs
        }
        done = 0
        for fut in as_completed(futs):
            done += 1
            model, phase = futs[fut]
            rows = fut.result()
            all_rows.extend(rows)
            ok = sum(1 for r in rows if r.get("status") == "ok")
            print(f"[{done}/{len(jobs)}] {model} {phase} kruskal_rows={ok}")

    out_name = (
        "condition_ladder_tests_long_clean.csv"
        if suffix
        else "condition_ladder_tests_long_syllable_raw.csv"
    )
    out_csv = art_root / out_name
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    rows_sorted = sorted(
        all_rows,
        key=lambda r: (
            str(r.get("model", "")),
            str(r.get("phase_layer", "")),
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
    n_sig = sum(
        1
        for r in rows_sorted
        if r.get("status") == "ok" and r.get("p") not in ("", None) and float(r["p"]) < 0.05  # type: ignore[arg-type]
    )
    print(f"wrote {out_csv}  rows={len(rows_sorted)} ok={n_ok} p<0.05={n_sig}")
    # also dump a tiny json summary
    summary = {
        "n_rows": len(rows_sorted),
        "n_ok": n_ok,
        "n_p_lt_0.05": n_sig,
        "n_models": len(models),
        "phases": list(args.phases),
        "min_bout_frames": args.min_bout_frames,
        "out_suffix": suffix,
        "path": str(out_csv),
        "note": "Prefer restack_condition_ladder_long.py for merged syllable+ngram table",
    }
    summary_json = out_csv.with_name(out_csv.stem + "_summary.json")
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
