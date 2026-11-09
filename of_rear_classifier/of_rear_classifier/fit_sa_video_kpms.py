"""Per-video keypoint-MoSeq fit on SuperAnimal OF (CPU-friendly, no shared alphabet).

Each recording gets its own ``project_dir`` / model. Syllable ids are **local**
to that video — fine for bout labeling (Goal B), not for cross-session ethograms.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from of_rear_classifier.export_sa_kpms import sa_h5_to_coordinates
from of_rear_classifier.sa_kpms_skeleton import SA_KPMS_BODY_PARTS, SA_KPMS_EDGES
from of_rear_classifier.syllable_bouts import bouts_from_syllable_sequence, save_bout_table


@dataclass(frozen=True)
class FitSaVideoConfig:
    """Per-video fit knobs. Syllable ids are local to this recording only."""

    ar_iters: int = 50
    full_iters: int = 50
    fps: float = 30.0
    likelihood_min: float = 0.3
    latent_dim: int | None = None  # None → PCA 90% var heuristic, capped at 8
    kappa_ar: float = 1e8  # stage-1 stickiness (maze FitConfig default scale)
    kappa_full: float = 1e4  # stage-2 bout-length dial (~400 ms target ballpark)
    save_every_n_iters: int = 25
    generate_progress_plots: bool = False
    individual: str = "animal0"
    anterior_bodyparts: tuple[str, ...] = ("nose",)
    posterior_bodyparts: tuple[str, ...] = ("tail_base",)


def stem_from_sa_h5(h5: Path) -> str:
    name = h5.name
    if "_superanimal" in name:
        return name.split("_superanimal", 1)[0]
    return h5.stem


def discover_sa_h5s(h5_dir: Path | str, *, glob_pat: str = "*superanimal*.h5") -> list[Path]:
    return sorted(Path(h5_dir).glob(glob_pat))


def results_exist(project_dir: Path | str, model_name: str = "model") -> bool:
    root = Path(project_dir) / model_name
    return (root / "results.h5").is_file() and (root / "syllable_bouts.csv").is_file()


def fit_sa_video(
    h5_path: Path | str,
    project_dir: Path | str,
    *,
    cfg: FitSaVideoConfig | None = None,
    model_name: str = "model",
) -> dict:
    """Fit one SA-TVM recording; write results.h5 + syllable_bouts.csv. Returns summary dict."""
    import keypoint_moseq as kpms

    cfg = cfg or FitSaVideoConfig()
    h5_path = Path(h5_path)
    project_dir = Path(project_dir)
    project_dir.mkdir(parents=True, exist_ok=True)
    recording_id = stem_from_sa_h5(h5_path)
    t0 = time.perf_counter()

    print(f"[{recording_id}] loading keypoints from {h5_path.name}", flush=True)
    coords, conf, bodyparts = sa_h5_to_coordinates(
        h5_path,
        individual=cfg.individual,
        body_parts=SA_KPMS_BODY_PARTS,
        likelihood_min=cfg.likelihood_min,
    )
    coordinates = {recording_id: coords}
    confidences = {recording_id: conf}

    skeleton = [list(e) for e in SA_KPMS_EDGES]
    kpms.setup_project(
        str(project_dir),
        overwrite=True,
        video_dir=str(h5_path.parent),
        bodyparts=list(bodyparts),
        use_bodyparts=list(bodyparts),
        skeleton=skeleton,
        fps=float(cfg.fps),
        anterior_bodyparts=list(cfg.anterior_bodyparts),
        posterior_bodyparts=list(cfg.posterior_bodyparts),
    )

    def config():
        return kpms.load_config(str(project_dir))

    print(f"[{recording_id}] T={coords.shape[0]} K={coords.shape[1]} format_data…", flush=True)
    data, metadata = kpms.format_data(coordinates, confidences, **config())

    # Skip interactive noise_calibration — use config defaults (batch/CPU).
    print(f"[{recording_id}] PCA…", flush=True)
    pca = kpms.fit_pca(**data, **config())
    kpms.save_pca(pca, str(project_dir))
    explained = np.cumsum(pca.explained_variance_ratio_)
    n90 = int(np.searchsorted(explained, 0.9) + 1)
    # Floor at 4: OF PCA often hits 90% by dim 2 (mostly centroid), which underfits syllables.
    # Cap scales with skeleton size (was 8 for 9-kp; 12 for Sturman 13-kp).
    _latent_cap = min(12, max(4, coords.shape[1] - 1))
    latent_dim = cfg.latent_dim if cfg.latent_dim is not None else min(max(n90, 4), _latent_cap)
    kpms.update_config(str(project_dir), latent_dim=int(latent_dim))
    print(f"[{recording_id}] latent_dim={latent_dim} (90% var ~{n90})", flush=True)

    try:
        sig = float(kpms.estimate_sigmasq_loc(data["Y"], data["mask"], filter_size=int(cfg.fps)))
        kpms.update_config(str(project_dir), sigmasq_loc=float(sig))
    except Exception as exc:  # noqa: BLE001
        print(f"[{recording_id}] estimate_sigmasq_loc skipped: {exc}", flush=True)

    model = kpms.init_model(data, pca=pca, **config())
    model = kpms.update_hypparams(model, kappa=float(cfg.kappa_ar))

    print(f"[{recording_id}] AR-HMM fit iters={cfg.ar_iters} κ={cfg.kappa_ar:g}…", flush=True)
    model, model_name = kpms.fit_model(
        model,
        data,
        metadata,
        project_dir=str(project_dir),
        model_name=model_name,
        num_iters=int(cfg.ar_iters),
        ar_only=True,
        parallel_message_passing=False,
        generate_progress_plots=cfg.generate_progress_plots,
        save_every_n_iters=int(cfg.save_every_n_iters),
        verbose=True,
    )

    model = kpms.update_hypparams(model, kappa=float(cfg.kappa_full))
    print(f"[{recording_id}] full model fit iters={cfg.full_iters} κ={cfg.kappa_full:g}…", flush=True)
    model, model_name = kpms.fit_model(
        model,
        data,
        metadata,
        project_dir=str(project_dir),
        model_name=model_name,
        num_iters=int(cfg.full_iters),
        ar_only=False,
        parallel_message_passing=False,
        generate_progress_plots=cfg.generate_progress_plots,
        save_every_n_iters=int(cfg.save_every_n_iters),
        verbose=True,
    )

    print(f"[{recording_id}] extract_results…", flush=True)
    results = kpms.extract_results(
        model,
        metadata,
        project_dir=str(project_dir),
        model_name=model_name,
        save_results=True,
    )
    syll = np.asarray(results[recording_id]["syllable"]).reshape(-1)
    bouts = bouts_from_syllable_sequence(syll)
    bout_path = project_dir / model_name / "syllable_bouts.csv"
    save_bout_table(bouts, bout_path)

    summary = {
        "recording_id": recording_id,
        "h5": str(h5_path),
        "project_dir": str(project_dir),
        "model_name": model_name,
        "n_frames": int(coords.shape[0]),
        "n_keypoints": int(coords.shape[1]),
        "latent_dim": int(latent_dim),
        "ar_iters": int(cfg.ar_iters),
        "full_iters": int(cfg.full_iters),
        "kappa_ar": float(cfg.kappa_ar),
        "kappa_full": float(cfg.kappa_full),
        "n_bouts": int(len(bouts)),
        "n_unique_syllables": int(len(np.unique(syll))),
        "bout_csv": str(bout_path),
        "seconds": float(time.perf_counter() - t0),
    }
    (project_dir / model_name / "fit_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2), flush=True)
    return summary


def _limit_blas_threads() -> None:
    """Keep each worker from oversubscribing CPU when many processes run."""
    for key in (
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
    ):
        os.environ.setdefault(key, "1")


def _fit_one_worker(job: dict) -> dict:
    """Process-pool entry: one video. ``job`` must be pickle-friendly."""
    _limit_blas_threads()
    h5 = Path(job["h5"])
    project_dir = Path(job["project_dir"])
    cfg = FitSaVideoConfig(**job["cfg"])
    model_name = str(job["model_name"])
    i, n = int(job["index"]), int(job["total"])
    rid = stem_from_sa_h5(h5)
    print(f"\n=== [{i}/{n}] {rid} (pid={os.getpid()}) ===", flush=True)
    try:
        return fit_sa_video(h5, project_dir, cfg=cfg, model_name=model_name)
    except Exception as exc:  # noqa: BLE001 — keep cohort going
        print(f"[{rid}] FAILED: {exc}", flush=True)
        return {"recording_id": rid, "h5": str(h5), "error": str(exc)}


def fit_sa_cohort(
    h5_dir: Path | str,
    out_root: Path | str,
    *,
    cfg: FitSaVideoConfig | None = None,
    model_name: str = "model",
    skip_existing: bool = True,
    only: list[str] | None = None,
    glob_pat: str = "*superanimal*.h5",
    workers: int = 1,
) -> list[dict]:
    """Fit each SA H5 under ``h5_dir`` into ``out_root/<recording_id>/`` (own alphabet).

    ``workers>1`` uses a process pool (one video per process). On 128 GB hosts,
    ~8–16 concurrent 20 min OF fits is a sensible start (see WEEKEND_KPMS.md).
    """
    from concurrent.futures import ProcessPoolExecutor, as_completed
    from dataclasses import asdict

    cfg = cfg or FitSaVideoConfig()
    h5_dir = Path(h5_dir)
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    paths = discover_sa_h5s(h5_dir, glob_pat=glob_pat)
    if only:
        want = {s.strip() for s in only}
        paths = [p for p in paths if stem_from_sa_h5(p) in want]
    if not paths:
        raise FileNotFoundError(f"no SA H5 under {h5_dir} matching {glob_pat} (only={only})")

    workers = max(1, int(workers))
    summaries: list[dict] = []
    jobs: list[dict] = []
    for i, h5 in enumerate(paths, start=1):
        rid = stem_from_sa_h5(h5)
        project_dir = out_root / rid
        if skip_existing and results_exist(project_dir, model_name):
            print(f"[{rid}] skip — results already at {project_dir / model_name}", flush=True)
            summaries.append(
                {
                    "recording_id": rid,
                    "h5": str(h5),
                    "project_dir": str(project_dir),
                    "skipped": True,
                    "bout_csv": str(project_dir / model_name / "syllable_bouts.csv"),
                }
            )
            continue
        jobs.append(
            {
                "h5": str(h5),
                "project_dir": str(project_dir),
                "cfg": asdict(cfg),
                "model_name": model_name,
                "index": i,
                "total": len(paths),
            }
        )

    if workers == 1 or len(jobs) <= 1:
        for job in jobs:
            summaries.append(_fit_one_worker(job))
    else:
        print(f"spawning {min(workers, len(jobs))} workers for {len(jobs)} fits…", flush=True)
        with ProcessPoolExecutor(max_workers=min(workers, len(jobs))) as pool:
            futs = [pool.submit(_fit_one_worker, job) for job in jobs]
            for fut in as_completed(futs):
                summaries.append(fut.result())

    man_path = out_root / "cohort_manifest.json"
    man_path.write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    print(f"\nwrote {man_path} ({len(summaries)} entries)", flush=True)
    return summaries
