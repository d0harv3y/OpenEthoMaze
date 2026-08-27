"""
CPU param-scan sweep: NOR s2 × ss grid + conf_threshold (27 full fits).

Runs ``maze-kpms-fit`` for each ``paramscan_s1-*_s2-*_ss-*_ct-*`` combo on
anatomical pose only. Intended for weekend CPU boxes (``JAX_PLATFORMS=cpu``).

Example (gerstner VAST full cohort, PowerShell)::

    uv run maze-kpms-param-sweep ^
      --project-dir C:\\Users\\admin\\Documents\\work\\sack\\vast_paramscan ^
      --manifest-csv C:\\Users\\admin\\Documents\\work\\sack\\gerstner_vast_fit\\gerstner_trial_manifest_kpms_fit.csv ^
      --max-trials 0 ^
      --include-habituation ^
      --fit-workers 1 ^
      --force-new ^
      --skip-complete
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from maze.kpms.paramscan import (
    DEFAULT_STAGE1_KAPPA,
    NOR_NUM_STATES,
    NOR_STAGE2_KAPPA,
    VAST_CONF_THRESHOLDS,
    ParamscanJob,
    iter_vast_conf_paramscan_grid,
)

OOM_WATCH_PATTERNS = (
    "RESOURCE_EXHAUSTED",
    "Out of memory",
    "MemoryError",
    "Killed",
    "XlaRuntimeError",
)


def _repo_root_from_here() -> Path:
    return Path(__file__).resolve().parents[2]


def _model_dir(project_dir: Path, job: ParamscanJob) -> Path:
    return project_dir / "anatomical" / job.model_name


def _log_path(project_dir: Path, job: ParamscanJob) -> Path:
    return project_dir / "fit_logs" / f"{job.model_name}.log"


def _fit_complete(model_dir: Path) -> bool:
    return (model_dir / "fit_summary.json").is_file() and (model_dir / "results.h5").is_file()


def _tail_watch(log_path: Path, model_id: str, stop_event: threading.Event) -> None:
    last_size = 0
    while not stop_event.is_set():
        if not log_path.is_file():
            time.sleep(2.0)
            continue
        try:
            size = log_path.stat().st_size
            if size > last_size:
                text = log_path.read_text(encoding="utf-8", errors="replace")
                new_text = text[last_size:]
                last_size = size
                for pattern in OOM_WATCH_PATTERNS:
                    if pattern in new_text:
                        print(
                            f"[watchdog] {model_id}: saw '{pattern}' in log — "
                            f"see {log_path}",
                            flush=True,
                        )
                        break
        except OSError:
            pass
        time.sleep(5.0)


def _base_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("JAX_PLATFORMS", "cpu")
    env.setdefault("XLA_PYTHON_CLIENT_PREALLOCATE", "false")
    env.setdefault("CUDA_VISIBLE_DEVICES", "")
    env.setdefault("OMP_NUM_THREADS", "1")
    env.setdefault("MKL_NUM_THREADS", "1")
    env.setdefault("OPENBLAS_NUM_THREADS", "1")
    env.setdefault("NUMEXPR_NUM_THREADS", "1")
    env.setdefault("TF_NUM_INTRAOP_THREADS", "1")
    env.setdefault("TF_NUM_INTEROP_THREADS", "1")
    return env


def _build_fit_cmd(args: argparse.Namespace, job: ParamscanJob) -> list[str]:
    cmd = [
        "uv",
        "run",
        "maze-kpms-fit",
        "--project-dir",
        str(args.project_dir),
        "--manifest-csv",
        str(args.manifest_csv),
        "--model-name",
        job.model_name,
        "--max-trials",
        str(args.max_trials),
        "--random-seed",
        str(args.random_seed),
        "--balance-by",
        args.balance_by,
        "--pose-stream",
        "anatomical",
        "--stage1-kappa",
        str(job.stage1_kappa),
        "--stage2-kappa",
        str(job.stage2_kappa),
        "--num-states",
        str(job.num_states),
        "--conf-threshold",
        str(job.conf_threshold),
    ]
    if args.include_habituation:
        cmd.append("--include-habituation")
    if args.exclude_experimental:
        cmd.append("--exclude-experimental")
    if args.no_enrich_labels:
        cmd.append("--no-enrich-labels")
    if args.force_new:
        cmd.append("--force-new")
    if args.float32:
        cmd.append("--float32")
    return cmd


def _run_job(args: argparse.Namespace, job: ParamscanJob) -> tuple[ParamscanJob, int, Path]:
    log_path = _log_path(args.project_dir, job)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    model_dir = _model_dir(args.project_dir, job)

    if args.skip_complete and _fit_complete(model_dir):
        print(f"SKIP (fit complete): {job.model_name}")
        return job, 0, log_path

    cmd = _build_fit_cmd(args, job)
    print(f"=== [{datetime.now().isoformat(timespec='seconds')}] fit {job.model_name} ===")
    if args.dry_run:
        print("DRY_RUN:", " ".join(cmd))
        return job, 0, log_path

    stop_watch = threading.Event()
    watcher = threading.Thread(
        target=_tail_watch,
        args=(log_path, job.model_name, stop_watch),
        daemon=True,
    )
    watcher.start()

    env = _base_env()
    with log_path.open("w", encoding="utf-8") as log_file:
        log_file.write(f"# cmd: {' '.join(cmd)}\n")
        log_file.write(f"# started: {datetime.now().isoformat(timespec='seconds')}\n\n")
        log_file.flush()
        proc = subprocess.run(
            cmd,
            cwd=str(args.repo_root),
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            check=False,
        )
    stop_watch.set()
    watcher.join(timeout=1.0)

    status = proc.returncode
    if status != 0:
        print(f"FAILED: {job.model_name} exit {status}; log: {log_path}", file=sys.stderr)
    else:
        print(f"OK: {job.model_name}")
    return job, status, log_path


def _iter_jobs(args: argparse.Namespace) -> list[ParamscanJob]:
    return list(
        iter_vast_conf_paramscan_grid(
            stage1_kappa=args.stage1_kappa,
            stage2_values=tuple(args.stage2_kappa),
            num_states_values=tuple(args.num_states),
            conf_thresholds=tuple(args.conf_threshold),
        )
    )


def _write_sweep_plan(args: argparse.Namespace, jobs: list[ParamscanJob]) -> Path:
    out = args.project_dir / "paramscan_sweep_plan.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "n_jobs": len(jobs),
        "project_dir": str(args.project_dir),
        "manifest_csv": str(args.manifest_csv),
        "max_trials": args.max_trials,
        "stage1_kappa": args.stage1_kappa,
        "stage2_kappa": list(args.stage2_kappa),
        "num_states": list(args.num_states),
        "conf_threshold": list(args.conf_threshold),
        "jobs": [asdict(j) | {"model_name": j.model_name} for j in jobs],
    }
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "CPU kpMS param scan: NOR stage2_kappa × num_states × conf_threshold "
            "(default 27 anatomical full fits)."
        )
    )
    p.add_argument("--project-dir", type=Path, required=True, help="kpMS root (parent of anatomical/)")
    p.add_argument("--manifest-csv", type=Path, required=True)
    p.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="OpenEthoMaze repo root for uv run (default: auto-detect)",
    )
    p.add_argument(
        "--max-trials",
        type=int,
        default=0,
        help="0 = all manifest rows after filters (full cohort)",
    )
    p.add_argument("--random-seed", type=int, default=42)
    p.add_argument(
        "--balance-by",
        type=str,
        default="sex,tx,phase,strain",
    )
    p.add_argument("--include-habituation", action="store_true")
    p.add_argument("--exclude-experimental", action="store_true")
    p.add_argument("--no-enrich-labels", action="store_true")
    p.add_argument("--stage1-kappa", type=float, default=DEFAULT_STAGE1_KAPPA)
    p.add_argument(
        "--stage2-kappa",
        type=float,
        nargs="+",
        default=list(NOR_STAGE2_KAPPA),
        metavar="KAPPA",
    )
    p.add_argument(
        "--num-states",
        type=int,
        nargs="+",
        default=list(NOR_NUM_STATES),
        metavar="K",
    )
    p.add_argument(
        "--conf-threshold",
        type=float,
        nargs="+",
        default=list(VAST_CONF_THRESHOLDS),
        metavar="CONF",
    )
    p.add_argument("--fit-workers", type=int, default=1, help="Parallel fit subprocesses")
    p.add_argument("--float32", action="store_true", help="Pass --float32 to maze-kpms-fit")
    p.add_argument("--force-new", action="store_true", help="Pass --force-new to maze-kpms-fit")
    p.add_argument(
        "--skip-complete",
        action="store_true",
        help="Skip jobs whose fit_summary.json + results.h5 already exist",
    )
    p.add_argument("--continue-on-error", action="store_true", default=True)
    p.add_argument("--no-continue-on-error", action="store_false", dest="continue_on_error")
    p.add_argument("--dry-run", action="store_true")
    ns = p.parse_args(argv)
    ns.repo_root = ns.repo_root or _repo_root_from_here()
    return ns


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    jobs = _iter_jobs(args)
    plan_path = _write_sweep_plan(args, jobs)

    print(f"Repo:           {args.repo_root}")
    print(f"Project dir:    {args.project_dir}")
    print(f"Manifest:       {args.manifest_csv}")
    print(f"Max trials:     {args.max_trials}")
    print(f"Stage1 κ:       {args.stage1_kappa}")
    print(f"Stage2 κ grid:  {list(args.stage2_kappa)}")
    print(f"num_states:     {list(args.num_states)}")
    print(f"conf_threshold: {list(args.conf_threshold)}")
    print(f"Jobs:           {len(jobs)}")
    print(f"Sweep plan:     {plan_path}")
    print("Pose stream:    anatomical only")
    print("JAX_PLATFORMS=cpu (via subprocess env)")
    print()

    results: list[tuple[ParamscanJob, int]] = []
    failed: list[str] = []

    with ThreadPoolExecutor(max_workers=max(1, args.fit_workers)) as pool:
        futures = {pool.submit(_run_job, args, job): job for job in jobs}
        for fut in as_completed(futures):
            job, status, _log = fut.result()
            results.append((job, status))
            if status != 0:
                failed.append(job.model_name)
                if not args.continue_on_error:
                    pool.shutdown(wait=False, cancel_futures=True)
                    raise SystemExit(status)

    ok = sum(1 for _, st in results if st == 0)
    print(f"\nfit phase: {ok}/{len(jobs)} succeeded.")
    if failed:
        print(f"Failed ({len(failed)}):", ", ".join(sorted(failed)), file=sys.stderr)
        if not args.continue_on_error:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
