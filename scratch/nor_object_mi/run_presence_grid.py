"""Fan out presence MI across all paramscan models × NOR_BL/NOR_TX.

Uses frozen dist_any bin edges from the reference pilot so models are comparable.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


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
    min_bout_frames: int | None,
) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(repo / "scratch" / "nor_object_mi" / "run_presence_pilot.py"),
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
    summary_path = out_dir / "run_summary.json"
    ok = proc.returncode == 0 and summary_path.exists()
    row: dict[str, object] = {
        "model": results_h5.parent.name,
        "phase_layer": phase,
        "returncode": proc.returncode,
        "out_dir": str(out_dir),
    }
    if ok:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        row["status"] = summary.get("status", "ok")
        row["n_delta_animals"] = summary.get("n_delta_animals")
        med = summary.get("median_excess_by_presence") or {}
        row["median_excess_present"] = med.get("present")
        row["median_excess_absent"] = med.get("absent")
        row["median_delta"] = summary.get("median_delta_present_minus_absent")
        # pull wilcoxon from group tests
        tests = summary.get("group_tests") or []
        wil = next((t for t in tests if t.get("factor") == "presence_paired"), None)
        row["wilcoxon_p"] = None if wil is None else wil.get("p")
        tx_k = next(
            (
                t
                for t in tests
                if t.get("factor") == "tx"
                and t.get("sex_stratum") == "all"
                and t.get("test") == "kruskal"
            ),
            None,
        )
        row["tx_kruskal_p"] = None if tx_k is None else tx_k.get("p")
    else:
        row["status"] = "failed"
        row["stderr_tail"] = (proc.stderr or "")[-500:]
    return row


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
    ap.add_argument(
        "--repo",
        type=Path,
        default=Path(r"C:\Users\admin\code\OpenEthoMaze"),
    )
    ap.add_argument(
        "--bin-edges-json",
        type=Path,
        default=None,
        help="Default: reference model presence/bin_edges_dist_any.json",
    )
    ap.add_argument("--phases", nargs="+", default=["NOR_BL", "NOR_TX"])
    ap.add_argument("--n-perm", type=int, default=100)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip jobs whose run_summary.json already exists",
    )
    ap.add_argument(
        "--min-bout-frames",
        type=int,
        default=None,
        help="Absorb short syllable bouts before MI (written under *_clean tags)",
    )
    ap.add_argument(
        "--out-suffix",
        type=str,
        default="",
        help="Appended to presence out-dir tags (e.g. _clean)",
    )
    args = ap.parse_args()

    art_root = args.ensemble_root / "_nor_object_mi"
    ref_edges = args.bin_edges_json or (
        art_root / "paramscan_s1-1e8_s2-1e5_ss-50" / "presence" / "bin_edges_dist_any.json"
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

    def _tag(phase: str) -> str:
        base = "presence" if phase == "NOR_TX" else f"presence_{phase}"
        return f"{base}{suffix}"

    jobs: list[tuple[Path, str, Path]] = []
    for model_dir in models:
        for phase in args.phases:
            out_dir = art_root / model_dir.name / _tag(phase)
            if args.skip_existing and (out_dir / "run_summary.json").exists():
                continue
            jobs.append((model_dir / "results.h5", phase, out_dir))

    print(
        f"jobs={len(jobs)} models={len(models)} phases={args.phases} "
        f"workers={args.workers} min_bout_frames={args.min_bout_frames} suffix={suffix!r}"
    )
    print(f"frozen_edges={ref_edges}")

    rows: list[dict[str, object]] = []
    # Also collect skip-existing summaries
    if args.skip_existing:
        for model_dir in models:
            for phase in args.phases:
                out_dir = art_root / model_dir.name / _tag(phase)
                summary_path = out_dir / "run_summary.json"
                if not summary_path.exists():
                    continue
                if any(j[2] == out_dir for j in jobs):
                    continue
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                med = summary.get("median_excess_by_presence") or {}
                tests = summary.get("group_tests") or []
                wil = next((t for t in tests if t.get("factor") == "presence_paired"), None)
                tx_k = next(
                    (
                        t
                        for t in tests
                        if t.get("factor") == "tx"
                        and t.get("sex_stratum") == "all"
                        and t.get("test") == "kruskal"
                    ),
                    None,
                )
                rows.append(
                    {
                        "model": model_dir.name,
                        "phase_layer": phase,
                        "returncode": 0,
                        "out_dir": str(out_dir),
                        "status": summary.get("status", "ok"),
                        "n_delta_animals": summary.get("n_delta_animals"),
                        "median_excess_present": med.get("present"),
                        "median_excess_absent": med.get("absent"),
                        "median_delta": summary.get("median_delta_present_minus_absent"),
                        "wilcoxon_p": None if wil is None else wil.get("p"),
                        "tx_kruskal_p": None if tx_k is None else tx_k.get("p"),
                    }
                )

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
                min_bout_frames=args.min_bout_frames,
            ): (results_h5, phase)
            for results_h5, phase, out_dir in jobs
        }
        done = 0
        for fut in as_completed(futs):
            done += 1
            row = fut.result()
            rows.append(row)
            print(
                f"[{done}/{len(jobs)}] {row['model']} {row['phase_layer']} "
                f"status={row.get('status')} median_delta={row.get('median_delta')} "
                f"wilcoxon_p={row.get('wilcoxon_p')}"
            )

    summary_name = "presence_grid_summary_clean.csv" if suffix else "presence_grid_summary.csv"
    out_csv = args.ensemble_root / "_nor_object_mi" / summary_name
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "model",
        "phase_layer",
        "status",
        "returncode",
        "n_delta_animals",
        "median_excess_present",
        "median_excess_absent",
        "median_delta",
        "wilcoxon_p",
        "tx_kruskal_p",
        "out_dir",
    ]
    rows_sorted = sorted(rows, key=lambda r: (str(r.get("model")), str(r.get("phase_layer"))))
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in rows_sorted:
            w.writerow(row)

    # quick tallies
    ok = [r for r in rows_sorted if r.get("status") == "ok"]
    print(f"wrote {out_csv}  ok={len(ok)}/{len(rows_sorted)}")
    for phase in args.phases:
        sub = [r for r in ok if r.get("phase_layer") == phase]
        if not sub:
            continue
        sig = sum(1 for r in sub if r.get("wilcoxon_p") is not None and float(r["wilcoxon_p"]) < 0.05)
        pos = sum(1 for r in sub if r.get("median_delta") is not None and float(r["median_delta"]) > 0)
        print(f"{phase}: models={len(sub)} median_delta>0={pos} wilcoxon_p<0.05={sig}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
