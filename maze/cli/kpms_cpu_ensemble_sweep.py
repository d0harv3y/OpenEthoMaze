"""
CPU-native kpMS ensemble fit + apply sweep (Windows-friendly).

Orchestrates anatomical / blob / fused × multiple seeds with parallel workers,
``JAX_PLATFORMS=cpu``, larger fit cohorts (default 160 trials), and a post-run
watchdog that flags incomplete fits (e.g. fused/seed_005 GPU-OOM partial checkpoint).

Usage (128GB lab box, from repo root after ``uv sync --extra kpms``):

    uv run maze-kpms-cpu-ensemble-sweep ^
      --project-dir C:\\Users\\admin\\Documents\\work\\sack\\test ^
      --manifest-csv C:\\Users\\admin\\Documents\\work\\sack\\test\\trial_manifest_kpms_tracking_wsl.csv ^
      --max-trials 160 ^
      --fit-workers 3 ^
      --apply-workers 2

Phases: ``--phase fit``, ``--phase apply``, or ``--phase all`` (default).
Watchdog only: ``--watchdog-only``.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from maze.kpms.ensemble_watchdog import (
    diagnose_ensemble,
    print_watchdog_summary,
    write_watchdog_report,
)
from maze.kpms.project_paths import POSE_STREAM_CHOICES

DEFAULT_SEEDS = (5, 13, 42, 67, 111)
DEFAULT_STREAMS = POSE_STREAM_CHOICES
OOM_WATCH_PATTERNS = (
    "RESOURCE_EXHAUSTED",
    "Out of memory",
    "MemoryError",
    "Killed",
    "XlaRuntimeError",
)


@dataclass(frozen=True)
class SweepJob:
    stream: str
    seed: int
    phase: str  # "fit" | "apply"

    @property
    def model_name(self) -> str:
        return f"seed_{self.seed:03d}"

    @property
    def model_id(self) -> str:
        return f"{self.stream}/{self.model_name}"

    @property
    def log_name(self) -> str:
        return f"{self.stream}_{self.model_name}.log"


def _repo_root_from_here() -> Path:
    return Path(__file__).resolve().parents[2]


def _model_dir(project_dir: Path, job: SweepJob) -> Path:
    return project_dir / job.stream / job.model_name


def _log_path(project_dir: Path, job: SweepJob) -> Path:
    subdir = "fit_logs" if job.phase == "fit" else "apply_logs"
    return project_dir / subdir / job.log_name


def _fit_complete(model_dir: Path) -> bool:
    return (model_dir / "fit_summary.json").is_file() and (model_dir / "results.h5").is_file()


def _apply_complete(model_dir: Path) -> bool:
    return (model_dir / "results_apply.h5").is_file() and (
        model_dir / "apply_summary.json"
    ).is_file()


def _tail_watch(log_path: Path, model_id: str, stop_event: threading.Event) -> None:
    """Print live clues when a log file grows with failure signatures."""
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
    # Avoid accidental GPU use on hybrid boxes.
    env.setdefault("CUDA_VISIBLE_DEVICES", "")
    return env


def _build_fit_cmd(args: argparse.Namespace, job: SweepJob) -> list[str]:
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
        str(job.seed),
        "--balance-by",
        args.balance_by,
        "--pose-stream",
        job.stream,
        "--no-enrich-labels",
    ]
    if args.force_new:
        cmd.append("--force-new")
    if args.float32:
        cmd.append("--float32")
    return cmd


def _build_apply_cmd(args: argparse.Namespace, job: SweepJob) -> list[str]:
    cmd = [
        "uv",
        "run",
        "maze-kpms-apply",
        "--project-dir",
        str(args.project_dir),
        "--manifest-csv",
        str(args.manifest_csv),
        "--model-name",
        job.model_name,
        "--pose-stream",
        job.stream,
        "--num-iters",
        str(args.apply_iters),
        "--apply-chunk-size",
        str(args.apply_chunk_size),
        "--no-enrich-labels",
    ]
    return cmd


def _run_job(
    args: argparse.Namespace,
    job: SweepJob,
) -> tuple[SweepJob, int, Path]:
    log_path = _log_path(args.project_dir, job)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    model_dir = _model_dir(args.project_dir, job)

    if job.phase == "fit":
        if args.skip_complete and _fit_complete(model_dir):
            print(f"SKIP (fit complete): {job.model_id}")
            return job, 0, log_path
        cmd = _build_fit_cmd(args, job)
    else:
        if not (model_dir / "checkpoint.h5").is_file():
            print(f"SKIP (no checkpoint): {job.model_id}", file=sys.stderr)
            return job, 2, log_path
        if args.skip_complete and _apply_complete(model_dir):
            print(f"SKIP (apply complete): {job.model_id}")
            return job, 0, log_path
        cmd = _build_apply_cmd(args, job)

    print(f"=== [{datetime.now().isoformat(timespec='seconds')}] {job.phase} {job.model_id} ===")
    if args.dry_run:
        print("DRY_RUN:", " ".join(cmd))
        return job, 0, log_path

    stop_watch = threading.Event()
    watcher = threading.Thread(
        target=_tail_watch,
        args=(log_path, job.model_id, stop_watch),
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
        print(f"FAILED: {job.model_id} exit {status}; log: {log_path}", file=sys.stderr)
    else:
        print(f"OK: {job.model_id}")
    return job, status, log_path


def _iter_jobs(
    streams: tuple[str, ...],
    seeds: tuple[int, ...],
    phase: str,
) -> list[SweepJob]:
    jobs: list[SweepJob] = []
    for stream in streams:
        for seed in seeds:
            jobs.append(SweepJob(stream=stream, seed=seed, phase=phase))
    return jobs


def _run_phase(
    args: argparse.Namespace,
    jobs: list[SweepJob],
) -> list[tuple[SweepJob, int]]:
    workers = args.fit_workers if jobs[0].phase == "fit" else args.apply_workers
    results: list[tuple[SweepJob, int]] = []
    failed: list[str] = []

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(_run_job, args, job): job for job in jobs}
        for fut in as_completed(futures):
            job, status, _log = fut.result()
            results.append((job, status))
            if status != 0:
                failed.append(job.model_id)
                if not args.continue_on_error:
                    pool.shutdown(wait=False, cancel_futures=True)
                    raise SystemExit(status)

    phase = jobs[0].phase if jobs else "?"
    ok = sum(1 for _, st in results if st == 0)
    print(f"\n{phase} phase: {ok}/{len(jobs)} succeeded.")
    if failed:
        print(f"Failed ({len(failed)}):", ", ".join(sorted(failed)), file=sys.stderr)
        if not args.continue_on_error:
            raise SystemExit(1)
    return results


def _run_watchdog(args: argparse.Namespace) -> None:
    reports = diagnose_ensemble(
        args.project_dir,
        streams=args.streams,
        seeds=args.seeds,
    )
    out_path = args.project_dir / "ensemble_watchdog_report.json"
    write_watchdog_report(reports, out_path)
    print_watchdog_summary(reports)
    print(f"\nWatchdog report: {out_path}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="CPU kpMS ensemble fit/apply sweep with parallel seeds and watchdog."
    )
    p.add_argument("--project-dir", type=Path, required=True, help="kpMS root (parent of stream dirs)")
    p.add_argument("--manifest-csv", type=Path, required=True)
    p.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="OpenEthoMaze repo root for uv run (default: auto-detect)",
    )
    p.add_argument("--max-trials", type=int, default=160)
    p.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=list(DEFAULT_SEEDS),
        metavar="N",
    )
    p.add_argument(
        "--streams",
        type=str,
        nargs="+",
        choices=POSE_STREAM_CHOICES,
        default=list(DEFAULT_STREAMS),
    )
    p.add_argument("--fit-workers", type=int, default=2, help="Parallel fit subprocesses")
    p.add_argument("--apply-workers", type=int, default=2, help="Parallel apply subprocesses")
    p.add_argument(
        "--balance-by",
        type=str,
        default="sex,tx,strain,session,exit_number",
    )
    p.add_argument("--float32", action="store_true", help="Pass --float32 to maze-kpms-fit")
    p.add_argument("--force-new", action="store_true", help="Pass --force-new to maze-kpms-fit")
    p.add_argument("--apply-iters", type=int, default=100)
    p.add_argument(
        "--apply-chunk-size",
        type=int,
        default=1,
        help="Manifest rows per apply batch (1 recommended on CPU)",
    )
    p.add_argument(
        "--phase",
        choices=("fit", "apply", "all", "watchdog"),
        default="all",
    )
    p.add_argument(
        "--skip-complete",
        action="store_true",
        help="Skip jobs whose outputs already exist (fit_summary or apply_summary)",
    )
    p.add_argument("--continue-on-error", action="store_true", default=True)
    p.add_argument("--no-continue-on-error", action="store_false", dest="continue_on_error")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--watchdog-only",
        action="store_true",
        help="Only run ensemble watchdog on existing artifacts",
    )
    ns = p.parse_args(argv)
    ns.repo_root = ns.repo_root or _repo_root_from_here()
    ns.streams = tuple(ns.streams)
    ns.seeds = tuple(ns.seeds)
    return ns


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.watchdog_only or args.phase == "watchdog":
        _run_watchdog(args)
        return

    print(f"Repo:        {args.repo_root}")
    print(f"Project dir: {args.project_dir}")
    print(f"Manifest:    {args.manifest_csv}")
    print(f"Max trials:  {args.max_trials}")
    print(f"Streams:     {', '.join(args.streams)}")
    print(f"Seeds:       {', '.join(str(s) for s in args.seeds)}")
    print("JAX_PLATFORMS=cpu (via subprocess env)")
    print()

    if args.phase in ("fit", "all"):
        fit_jobs = _iter_jobs(args.streams, args.seeds, "fit")
        _run_phase(args, fit_jobs)

    if args.phase in ("apply", "all"):
        apply_jobs = _iter_jobs(args.streams, args.seeds, "apply")
        _run_phase(args, apply_jobs)

    _run_watchdog(args)


if __name__ == "__main__":
    main()
