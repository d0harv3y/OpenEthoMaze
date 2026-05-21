from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import h5py
import keypoint_moseq as kpms
import numpy as np
from jax_moseq.utils.debugging import convert_data_precision

from ..pipeline.run_provenance import provenance_envelope, provenance_run, sha256_file
from .io import ensure_dir, write_json, write_selected_manifest
from .fit_config import KpmsFitRunConfig, subset_config_from_fit_run
from .manifest_subset import (
    SubsetConfig,
    filter_manifests,
    load_manifests,
    sample_representative_subset,
)
from .preprocess import KpmsPreprocessConfig, build_kpms_inputs


@dataclass(frozen=True)
class FitConfig:
    """kpMS fit hyperparameters for ORM v1."""

    seed: int = 42
    pca_num_frames: int = 1_000_000
    num_states: int = 100
    latent_dim: int = 5
    nlags: int = 5

    stage1_kappa: float = 1e7
    stage2_kappa: float = 1e4
    stage1_ar_only_iters: int = 50
    stage2_full_iters: int = 200
    alpha: float = 5.7
    gamma: float = 1e3
    s0_scale: float = 0.01
    k0_scale: float = 10.0
    save_every: int = 50
    conf_threshold: float = 0.2
    reindex_syllables: bool = True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fit keypoint-MoSeq model from ORM manifest subset."
    )
    parser.add_argument("--manifest-csv", type=str, default=None)
    parser.add_argument("--project-dir", type=str, required=True)
    parser.add_argument("--model-name", type=str, default="orm_kpms_fit")
    parser.add_argument("--max-trials", type=int, default=300)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--include-habituation", action="store_true")
    parser.add_argument("--exclude-experimental", action="store_true")
    parser.add_argument(
        "--balance-by",
        type=str,
        default="sex,tx,phase,strain",
        help=(
            "Comma-separated TrialManifest fields for stratified subsampling "
            "(default: sex,tx,cohort,phase). See maze.kpms.manifest_subset.BALANCE_COLUMN_CHOICES."
        ),
    )
    parser.add_argument(
        "--no-enrich-labels",
        action="store_true",
        help="When using --manifest-csv, do not fill blank sex/tx from inputs/treatment_labels.csv",
    )
    parser.add_argument(
        "--force-new",
        action="store_true",
        help=(
            "Delete an existing checkpoint.h5 for this model before fitting. "
            "Use when reusing --model-name after changing the manifest or subset."
        ),
    )
    return parser.parse_args()


def _prepare_checkpoint_path(checkpoint_path: Path, data: dict, *, force_new: bool) -> None:
    """Avoid stale data/ in checkpoint.h5 (kpms only writes data on first create).

    If the file already exists from a prior run, on-disk `data/mask` can disagree
    with the new model snapshots and break `reindex_syllables_in_checkpoint`.
    """
    if not checkpoint_path.is_file():
        return
    if force_new:
        checkpoint_path.unlink()
        print(f"Removed {checkpoint_path} (--force-new).")
        return
    with h5py.File(checkpoint_path, "r") as f:
        disk_shape = f["data"]["mask"].shape
    cur_shape = np.asarray(data["mask"]).shape
    if disk_shape != cur_shape:
        checkpoint_path.unlink()
        print(
            "Removed stale checkpoint.h5: on-disk data/mask shape "
            f"{disk_shape} != current {cur_shape}. "
            "keypoint_moseq does not refresh the data group when the file already exists."
        )


def run_kpms_fit(cfg: KpmsFitRunConfig) -> Path:
    """
    Fit a keypoint-MoSeq model from a manifest subset.

    Writes ``<project_dir>/<model_name>/`` (checkpoint, results, fit_summary.json)
    and a provenance sidecar under ``<project_dir>/provenance/``.

    Returns:
        Path to the model output directory.

    Raises:
        RuntimeError: No trials selected or no usable trajectories after preprocess.
    """
    project_dir = Path(cfg.project_dir)
    ensure_dir(project_dir)
    subset_cfg = subset_config_from_fit_run(cfg)
    prov_inputs = {
        "project_dir": str(project_dir),
        "model_name": cfg.model_name,
        "manifest_csv": str(cfg.manifest_csv) if cfg.manifest_csv else None,
        "force_new": bool(cfg.force_new),
        "subset_config": asdict(subset_cfg),
    }
    if subset_cfg.manifest_csv and Path(subset_cfg.manifest_csv).is_file():
        prov_inputs["manifest_csv_sha256"] = sha256_file(subset_cfg.manifest_csv)

    pre_cfg = KpmsPreprocessConfig()
    fit_cfg = FitConfig(seed=cfg.random_seed)

    with provenance_run("kpms_fit", project_dir, prov_inputs) as prov:
        _run_fit_body(
            project_dir=project_dir,
            model_name=cfg.model_name,
            force_new=cfg.force_new,
            subset_cfg=subset_cfg,
            pre_cfg=pre_cfg,
            fit_cfg=fit_cfg,
            prov=prov,
        )
    return project_dir / cfg.model_name


def fit_run_config_from_args(args: argparse.Namespace) -> KpmsFitRunConfig:
    """Map :func:`parse_args` namespace to :class:`KpmsFitRunConfig`."""
    balance_cols = tuple(c.strip() for c in str(args.balance_by).split(",") if c.strip())
    return KpmsFitRunConfig(
        project_dir=Path(args.project_dir),
        model_name=args.model_name,
        manifest_csv=Path(args.manifest_csv) if args.manifest_csv else None,
        max_trials=args.max_trials,
        random_seed=args.random_seed,
        include_habituation=args.include_habituation,
        exclude_experimental=args.exclude_experimental,
        balance_columns=balance_cols,
        enrich_from_treatment_labels=not args.no_enrich_labels,
        force_new=bool(args.force_new),
    )


def main() -> None:
    run_kpms_fit(fit_run_config_from_args(parse_args()))


def _run_fit_body(
    *,
    project_dir: Path,
    model_name: str,
    force_new: bool,
    subset_cfg: SubsetConfig,
    pre_cfg: KpmsPreprocessConfig,
    fit_cfg: FitConfig,
    prov: dict,
) -> None:
    manifests = load_manifests(subset_cfg)
    manifests = filter_manifests(manifests, subset_cfg)
    manifests = sample_representative_subset(
        manifests,
        max_trials=subset_cfg.max_trials,
        random_seed=subset_cfg.random_seed,
        balance_columns=subset_cfg.balance_columns,
    )
    if not manifests:
        raise RuntimeError("No trials selected for kpMS fitting.")

    model_out = project_dir / model_name
    ensure_dir(model_out)
    write_selected_manifest(model_out / "selected_trials.csv", manifests)

    coordinates, confidences, bodyparts, skipped = build_kpms_inputs(manifests, pre_cfg)
    if not coordinates:
        raise RuntimeError("No usable trajectories after preprocessing.")

    data, metadata = kpms.format_data(
        coordinates,
        confidences,
        bodyparts=bodyparts,
    )
    data = convert_data_precision(data, x64=True)

    _prepare_checkpoint_path(model_out / "checkpoint.h5", data, force_new=force_new)

    def _idx(name: str, fallback: int) -> list[int]:
        try:
            return [bodyparts.index(name)]
        except ValueError:
            return [fallback]

    anterior_idxs = _idx("nose", 0)
    posterior_idxs = _idx("tail", max(0, len(bodyparts) - 1))

    trans_hypparams = {
        "num_states": fit_cfg.num_states,
        "gamma": fit_cfg.gamma,
        "alpha": fit_cfg.alpha,
        "kappa": float(fit_cfg.stage1_kappa),
    }
    ar_hypparams = {
        "latent_dim": fit_cfg.latent_dim,
        "nlags": fit_cfg.nlags,
        "S_0_scale": fit_cfg.s0_scale,
        "K_0_scale": fit_cfg.k0_scale,
    }
    obs_hypparams = {"sigmasq_0": 0.1, "sigmasq_C": 0.1, "nu_sigma": 1e5, "nu_s": 5}
    cen_hypparams = {"sigmasq_loc": 0.5}

    model = kpms.init_model(
        data=data,
        seed=fit_cfg.seed,
        whiten=True,
        PCA_fitting_num_frames=fit_cfg.pca_num_frames,
        anterior_idxs=anterior_idxs,
        posterior_idxs=posterior_idxs,
        conf_threshold=fit_cfg.conf_threshold,
        fix_heading=False,
        verbose=True,
        trans_hypparams=trans_hypparams,
        ar_hypparams=ar_hypparams,
        obs_hypparams=obs_hypparams,
        cen_hypparams=cen_hypparams,
        error_estimator={"slope": -0.5, "intercept": 0.25},
    )

    model, model_name = kpms.fit_model(
        model,
        data,
        metadata,
        project_dir=str(project_dir),
        model_name=model_name,
        num_iters=fit_cfg.stage1_ar_only_iters,
        start_iter=0,
        verbose=True,
        ar_only=True,
        save_every_n_iters=fit_cfg.save_every,
        generate_progress_plots=False,
        parallel_message_passing=None,
    )

    model = kpms.update_hypparams(model, kappa=float(fit_cfg.stage2_kappa))
    model, fitted_name = kpms.fit_model(
        model,
        data,
        metadata,
        project_dir=str(project_dir),
        model_name=model_name,
        num_iters=fit_cfg.stage1_ar_only_iters + fit_cfg.stage2_full_iters,
        start_iter=fit_cfg.stage1_ar_only_iters,
        verbose=True,
        ar_only=False,
        save_every_n_iters=fit_cfg.save_every,
        generate_progress_plots=False,
        parallel_message_passing=None,
    )

    if fit_cfg.reindex_syllables:
        kpms.reindex_syllables_in_checkpoint(str(project_dir), fitted_name)
        model, data, metadata, _ = kpms.load_checkpoint(str(project_dir), fitted_name)

    kpms.extract_results(model, metadata, str(project_dir), fitted_name)

    summary = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "project_dir": str(project_dir),
        "model_name": fitted_name,
        "n_selected_trials": len(manifests),
        "n_used_recordings": len(coordinates),
        "n_skipped_recordings": len(skipped),
        "skipped_examples": skipped[:20],
        "subset_config": asdict(subset_cfg),
        "preprocess_config": asdict(pre_cfg),
        "fit_config": asdict(fit_cfg),
        "checkpoint_path": str(project_dir / fitted_name / "checkpoint.h5"),
        "results_path": str(project_dir / fitted_name / "results.h5"),
        "run_provenance": provenance_envelope(
            operation="kpms_fit",
            inputs=prov.get("inputs", {}),
            outputs={
                "n_selected_trials": len(manifests),
                "n_used_recordings": len(coordinates),
                "model_name": fitted_name,
            },
            started_at=prov.get("started_at"),
            finished_at=prov.get("finished_at"),
        ),
    }
    prov["outputs"] = {
        "n_selected_trials": len(manifests),
        "n_used_recordings": len(coordinates),
        "model_name": fitted_name,
        "fit_summary": str(project_dir / fitted_name / "fit_summary.json"),
    }
    write_json(project_dir / fitted_name / "fit_summary.json", summary)
    print(f"Done. Model: {fitted_name}")


if __name__ == "__main__":
    main()
