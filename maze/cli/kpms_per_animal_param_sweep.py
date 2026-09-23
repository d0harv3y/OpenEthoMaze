"""
Per-animal NOR param-scan: 9 models per ``exp*/{animal_id}/`` leaf.

Discovers SLEAP sidecars under ``--data-root`` (full NOR ladder: NO/ID/NVL OBJ ×
NOR1–4), mirrors that tree under ``--output-root``, and runs anatomical kpMS fits
with κ1 fixed (default 1e7), κ2 ∈ {1e4, 10**4.5, 1e5}, K ∈ {50,75,100}, ct=0.2.

Model dirs are tagged ``{animal_id}_paramscan_s1-*_s2-*_ss-*_ct-*``.

Example (PowerShell, overnight CPU)::

    $env:JAX_PLATFORMS = "cpu"
    uv run maze-kpms-per-animal-param-sweep `
      --data-root "D:\\nor vids\\standard format" `
      --output-root "F:\\nor_per_animal_paramscan" `
      --force-new `
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

from maze.kpms.nor_slp_manifest import (
    NorAnimalBundle,
    discover_nor_animal_bundles,
    write_animal_manifest_csv,
)
from maze.kpms.paramscan import (
    NOR_NUM_STATES,
    NOR_PER_ANIMAL_CONF_THRESHOLD,
    NOR_PER_ANIMAL_STAGE1_KAPPA,
    NOR_STAGE2_KAPPA,
    ParamscanJob,
    animal_paramscan_model_name,
    iter_nor_per_animal_paramscan_grid,
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


def _animal_project_dir(output_root: Path, bundle: NorAnimalBundle) -> Path:
    return output_root / bundle.cohort / bundle.animal_id


def _model_dir(project_dir: Path, model_name: str) -> Path:
    return project_dir / "anatomical" / model_name


def _log_path(project_dir: Path, model_name: str) -> Path:
    return project_dir / "fit_logs" / f"{model_name}.log"


def _fit_complete(model_dir: Path) -> bool:
    return (model_dir / "fit_summary.json").is_file() and (model_dir / "results.h5").is_file()


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


def _build_fit_cmd(
    *,
    args: argparse.Namespace,
    project_dir: Path,
    manifest_csv: Path,
    model_name: str,
    job: ParamscanJob,
) -> list[str]:
    cmd = [
        "uv",
        "run",
        "maze-kpms-fit",
        "--project-dir",
        str(project_dir),
        "--manifest-csv",
        str(manifest_csv),
        "--model-name",
        model_name,
        "--max-trials",
        "0",
        "--random-seed",
        str(args.random_seed),
        "--balance-by",
        "animal_id",
        "--pose-stream",
        "anatomical",
        "--no-enrich-labels",
        "--stage1-kappa",
        str(job.stage1_kappa),
        "--stage2-kappa",
        str(job.stage2_kappa),
        "--num-states",
        str(job.num_states),
        "--conf-threshold",
        str(job.conf_threshold),
    ]
    if args.force_new:
        cmd.append("--force-new")
    if args.float32:
        cmd.append("--float32")
    return cmd


def _run_one_model(
    *,
    args: argparse.Namespace,
    project_dir: Path,
    manifest_csv: Path,
    animal_id: str,
    job: ParamscanJob,
) -> tuple[str, int, Path]:
    model_name = animal_paramscan_model_name(animal_id, job)
    log_path = _log_path(project_dir, model_name)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    model_dir = _model_dir(project_dir, model_name)

    if args.skip_complete and _fit_complete(model_dir):
        print(f"SKIP (fit complete): {model_name}")
        return model_name, 0, log_path

    cmd = _build_fit_cmd(
        args=args,
        project_dir=project_dir,
        manifest_csv=manifest_csv,
        model_name=model_name,
        job=job,
    )
    print(f"=== [{datetime.now().isoformat(timespec='seconds')}] fit {model_name} ===")
    if args.dry_run:
        print("DRY_RUN:", " ".join(cmd))
        return model_name, 0, log_path

    stop_watch = threading.Event()
    watcher = threading.Thread(
        target=_tail_watch,
        args=(log_path, model_name, stop_watch),
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
        print(f"FAILED: {model_name} exit {status}; log: {log_path}", file=sys.stderr)
    else:
        print(f"OK: {model_name}")
    return model_name, status, log_path


def _filter_bundles(
    bundles: list[NorAnimalBundle],
    *,
    cohorts: list[str] | None,
    animal_ids: list[str] | None,
) -> list[NorAnimalBundle]:
    out = bundles
    if cohorts:
        want = {c.lower() for c in cohorts}
        out = [b for b in out if b.cohort.lower() in want]
    if animal_ids:
        want_ids = {a.strip() for a in animal_ids}
        out = [b for b in out if b.animal_id in want_ids]
    return out


def _write_global_plan(
    output_root: Path,
    bundles: list[NorAnimalBundle],
    jobs: list[ParamscanJob],
    args: argparse.Namespace,
) -> Path:
    out = output_root / "per_animal_paramscan_plan.json"
    output_root.mkdir(parents=True, exist_ok=True)
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "data_root": str(args.data_root),
        "output_root": str(output_root),
        "n_animals": len(bundles),
        "n_jobs_per_animal": len(jobs),
        "n_fits_total": len(bundles) * len(jobs),
        "stage1_kappa": args.stage1_kappa,
        "stage2_kappa": list(args.stage2_kappa),
        "num_states": list(args.num_states),
        "conf_threshold": args.conf_threshold,
        "animals": [
            {
                "cohort": b.cohort,
                "animal_id": b.animal_id,
                "n_recordings": len(b.recordings),
                "project_dir": str(_animal_project_dir(output_root, b)),
            }
            for b in bundles
        ],
        "jobs": [
            asdict(j) | {"model_name_suffix": j.model_name} for j in jobs
        ],
    }
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Per-animal NOR kpMS param scan: mirror exp*/ID* under --output-root "
            "and fit 9 anatomical models per animal (κ1 fixed, κ2×K grid)."
        )
    )
    p.add_argument(
        "--data-root",
        type=Path,
        required=True,
        help=r'NOR tree root, e.g. "D:\nor vids\standard format"',
    )
    p.add_argument(
        "--output-root",
        type=Path,
        required=True,
        help=r"Mirror root on F: (or elsewhere); writes exp*/ID*/anatomical/…",
    )
    p.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="OpenEthoMaze repo root for uv run (default: auto-detect)",
    )
    p.add_argument("--cohort", type=str, nargs="+", default=None, metavar="EXP")
    p.add_argument("--animal-id", type=str, nargs="+", default=None, metavar="ID")
    p.add_argument("--random-seed", type=int, default=42)
    p.add_argument(
        "--stage1-kappa",
        type=float,
        default=NOR_PER_ANIMAL_STAGE1_KAPPA,
    )
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
        default=NOR_PER_ANIMAL_CONF_THRESHOLD,
    )
    p.add_argument("--fit-workers", type=int, default=1)
    p.add_argument("--float32", action="store_true")
    p.add_argument("--force-new", action="store_true")
    p.add_argument(
        "--skip-complete",
        action="store_true",
        help="Skip models with fit_summary.json + results.h5 already present",
    )
    p.add_argument("--continue-on-error", action="store_true", default=True)
    p.add_argument("--no-continue-on-error", action="store_false", dest="continue_on_error")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--discover-only",
        action="store_true",
        help="Write manifests + plan JSON then exit (no fits)",
    )
    ns = p.parse_args(argv)
    ns.repo_root = ns.repo_root or _repo_root_from_here()
    return ns


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    bundles = _filter_bundles(
        discover_nor_animal_bundles(args.data_root),
        cohorts=args.cohort,
        animal_ids=args.animal_id,
    )
    if not bundles:
        raise SystemExit(f"No NOR animal bundles under {args.data_root}")

    jobs = list(
        iter_nor_per_animal_paramscan_grid(
            stage1_kappa=args.stage1_kappa,
            stage2_values=tuple(args.stage2_kappa),
            num_states_values=tuple(args.num_states),
            conf_threshold=args.conf_threshold,
        )
    )
    plan_path = _write_global_plan(args.output_root, bundles, jobs, args)

    print(f"Repo:            {args.repo_root}")
    print(f"Data root:       {args.data_root}")
    print(f"Output root:     {args.output_root}")
    print(f"Animals:         {len(bundles)}")
    print(f"Jobs / animal:   {len(jobs)}")
    print(f"Fits total:      {len(bundles) * len(jobs)}")
    print(f"Stage1 κ:        {args.stage1_kappa}")
    print(f"Stage2 κ grid:   {list(args.stage2_kappa)}")
    print(f"num_states:      {list(args.num_states)}")
    print(f"conf_threshold:  {args.conf_threshold}")
    print(f"Plan:            {plan_path}")
    print("Pose stream:     anatomical (SLEAP-only manifests)")
    print()

    # Prepare per-animal project dirs + manifests first.
    prepared: list[tuple[NorAnimalBundle, Path, Path]] = []
    for bundle in bundles:
        project_dir = _animal_project_dir(args.output_root, bundle)
        project_dir.mkdir(parents=True, exist_ok=True)
        manifest_csv = write_animal_manifest_csv(
            bundle, project_dir / "trial_manifest.csv"
        )
        animal_plan = {
            "cohort": bundle.cohort,
            "animal_id": bundle.animal_id,
            "n_recordings": len(bundle.recordings),
            "manifest_csv": str(manifest_csv),
            "models": [
                animal_paramscan_model_name(bundle.animal_id, job) for job in jobs
            ],
        }
        (project_dir / "paramscan_animal_plan.json").write_text(
            json.dumps(animal_plan, indent=2) + "\n", encoding="utf-8"
        )
        print(
            f"  {bundle.cohort}/{bundle.animal_id}: "
            f"{len(bundle.recordings)} recordings → {manifest_csv}"
        )
        prepared.append((bundle, project_dir, manifest_csv))

    if args.discover_only:
        print("\n--discover-only: manifests written; skipping fits.")
        return

    work: list[tuple[NorAnimalBundle, Path, Path, ParamscanJob]] = []
    for bundle, project_dir, manifest_csv in prepared:
        for job in jobs:
            work.append((bundle, project_dir, manifest_csv, job))

    failed: list[str] = []
    ok = 0

    def _submit(
        item: tuple[NorAnimalBundle, Path, Path, ParamscanJob],
    ) -> tuple[str, int]:
        bundle, project_dir, manifest_csv, job = item
        name, status, _ = _run_one_model(
            args=args,
            project_dir=project_dir,
            manifest_csv=manifest_csv,
            animal_id=bundle.animal_id,
            job=job,
        )
        return name, status

    with ThreadPoolExecutor(max_workers=max(1, args.fit_workers)) as pool:
        futures = {pool.submit(_submit, item): item for item in work}
        for fut in as_completed(futures):
            name, status = fut.result()
            if status == 0:
                ok += 1
            else:
                failed.append(name)
                if not args.continue_on_error:
                    pool.shutdown(wait=False, cancel_futures=True)
                    raise SystemExit(status)

    print(f"\nfit phase: {ok}/{len(work)} succeeded.")
    if failed:
        print(f"Failed ({len(failed)}):", ", ".join(sorted(failed)), file=sys.stderr)
        if not args.continue_on_error:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
