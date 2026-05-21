"""
Apply a trained keypoint-MoSeq checkpoint to SLEAP data listed in a trial manifest CSV.

Uses the same ORM preprocessing as :mod:`maze.kpms.fit` (:func:`build_kpms_inputs`).
Trial selection supports optional ``--animal-id`` / ``--session`` / ``--trial`` filters
(semantics aligned with ``scripts/legacy_db.py``).
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Optional

import numpy as np
import pandas as pd

from ..pipeline.io.file_discovery import TrialManifest
from ..pipeline.run_provenance import provenance_envelope, provenance_run, sha256_file
from .io import ensure_dir, write_json
from .apply_run_config import KpmsApplyRunConfig
from .manifest_subset import SubsetConfig, filter_manifests, load_manifests
from .preprocess import KpmsPreprocessConfig, build_kpms_inputs

_REPO_ROOT = Path(__file__).resolve().parents[2]
# Default manifest path (legacy_db sync output under repo outputs/legacy/).
DEFAULT_MANIFEST_CSV = _REPO_ROOT / "outputs" / "legacy" / "trial_manifest_legacy.csv"

DEFAULT_RESULTS_NAME = "results_apply.h5"


def expand_filter_arg(vals: Optional[list[str]]) -> Optional[list[str]]:
    """Split comma/space-separated tokens (same idea as ``legacy_db._expand_filter_arg``)."""
    if not vals:
        return None
    out: list[str] = []
    for v in vals:
        out.extend(x.strip() for x in str(v).replace(",", " ").split() if x.strip())
    return out if out else None


def filter_manifests_by_trial_selectors(
    manifests: list[TrialManifest],
    animal_ids: Optional[list[str]],
    sessions: Optional[list[str]],
    trials: Optional[list[str]],
) -> list[TrialManifest]:
    """Keep trials whose id/session/trial appear in the given lists (AND across dimensions)."""
    out = list(manifests)
    if animal_ids:
        out = [m for m in out if m.animal_id in animal_ids]
    if sessions:
        out = [m for m in out if m.session in sessions]
    if trials:
        out = [m for m in out if m.trial in trials]
    return out


@dataclass(frozen=True)
class ApplyManifestLoadStats:
    """Counts at each filtering stage (for diagnostics when no trials match)."""

    n_csv_rows: int
    n_after_sleap_and_phase: int
    n_after_animal_session_trial: int


def load_manifests_for_apply(
    manifest_csv: Path,
    *,
    include_habituation: bool = False,
    include_experimental: bool = True,
    enrich_from_treatment_labels: bool = True,
    animal_ids: Optional[list[str]] = None,
    sessions: Optional[list[str]] = None,
    trials: Optional[list[str]] = None,
) -> tuple[list[TrialManifest], ApplyManifestLoadStats]:
    """
    Load CSV, enrich labels, apply phase/sleap filters, then optional id/session/trial filters.
    """
    cfg = SubsetConfig(
        manifest_csv=manifest_csv,
        require_sleap=True,
        include_habituation=include_habituation,
        include_experimental=include_experimental,
        enrich_from_treatment_labels=enrich_from_treatment_labels,
    )
    manifests = load_manifests(cfg)
    n_csv = len(manifests)
    manifests = filter_manifests(manifests, cfg)
    n_after_base = len(manifests)
    manifests = filter_manifests_by_trial_selectors(manifests, animal_ids, sessions, trials)
    n_after_sel = len(manifests)
    stats = ApplyManifestLoadStats(
        n_csv_rows=n_csv,
        n_after_sleap_and_phase=n_after_base,
        n_after_animal_session_trial=n_after_sel,
    )
    return (
        sorted(manifests, key=lambda m: (m.animal_id, m.session, m.trial)),
        stats,
    )


def interpolate_nans(arr: np.ndarray) -> np.ndarray:
    """Linearly interpolate NaNs along time for each keypoint dimension."""
    arr_interp = arr.copy()
    for k in range(arr.shape[1]):
        for d in range(arr.shape[2]):
            series = pd.Series(arr[:, k, d])
            arr_interp[:, k, d] = series.interpolate(limit_direction="both").to_numpy()
    return arr_interp


def interpolate_nans_in_coordinates(coordinates: MutableMapping[str, np.ndarray]) -> None:
    """Replace each 3D trajectory array with a NaN-interpolated copy."""
    for k, v in list(coordinates.items()):
        if isinstance(v, np.ndarray) and v.ndim == 3:
            coordinates[k] = interpolate_nans(v)


def filter_low_confidence_fragments(
    coordinates: MutableMapping[str, np.ndarray],
    confidences: MutableMapping[str, np.ndarray],
    *,
    conf_thresh: float,
    min_points: int,
    min_fragment: int,
) -> None:
    """Drop or trim recordings using per-frame keypoint count."""
    for key in list(coordinates.keys()):
        conf = confidences.get(key, None)
        if conf is None:
            continue
        valid = (conf >= conf_thresh).sum(axis=1) >= min_points
        if int(valid.sum()) < min_fragment:
            del coordinates[key]
            del confidences[key]
            continue
        if int(valid.sum()) < len(valid):
            coordinates[key] = coordinates[key][valid]
            confidences[key] = conf[valid]


@dataclass(frozen=True)
class KpmsApplyConfig:
    """Apply-stage settings (post-preprocessing, passed through to keypoint_moseq)."""

    num_iters: int = 100
    conf_threshold: float = 0.2
    min_points_per_frame: int = 3
    min_fragment_frames: int = 4
    parallel_message_passing: bool = False
    reindex_syllables_before_load: bool = True
    error_estimator: Mapping[str, float] = field(
        default_factory=lambda: {"slope": -0.5, "intercept": 0.25}
    )
    verbose: bool = True
    overwrite_results: bool = True


def _anterior_posterior_idxs(bodyparts: list) -> tuple[list[int], list[int]]:
    bp = list(bodyparts)
    try:
        anterior = [bp.index("nose")]
    except ValueError:
        anterior = [0]
    try:
        posterior = [bp.index("tail")]
    except ValueError:
        posterior = [1] if len(bp) > 1 else [0]
    return anterior, posterior


def apply_kpms_checkpoint_from_manifests(
    project_dir: Path | str,
    model_name: str,
    manifests: list[TrialManifest],
    cfg: KpmsApplyConfig | None = None,
    preprocess_config: KpmsPreprocessConfig | None = None,
    results_path: Path | str | None = None,
    *,
    manifest_csv: Path | str | None = None,
) -> dict[str, Any]:
    """
    Preprocess all selected trials like ``fit.py``, then run a single ``apply_model`` call.

    Writes one HDF5 (default: ``<project_dir>/<model_name>/results_apply.h5``).
    """
    import keypoint_moseq as kpms

    cfg = cfg or KpmsApplyConfig()
    pre_cfg = preprocess_config or KpmsPreprocessConfig()
    project_dir = Path(project_dir)

    if not manifests:
        raise RuntimeError("No trials selected for kpMS apply (empty manifest list).")

    coordinates, confidences, bodyparts, skipped = build_kpms_inputs(manifests, pre_cfg)
    bodyparts_list = list(bodyparts)

    if cfg.verbose:
        print(
            f"kpMS apply: {len(manifests)} manifest row(s), "
            f"{len(coordinates)} recording(s) after preprocess, {len(skipped)} skipped"
        )

    if not coordinates:
        raise RuntimeError("No usable trajectories after preprocessing; nothing to apply.")

    # interpolate_nans_in_coordinates(coordinates)
    # filter_low_confidence_fragments(
    #     coordinates,
    #     confidences,
    #     conf_thresh=cfg.conf_threshold,
    #     min_points=cfg.min_points_per_frame,
    #     min_fragment=cfg.min_fragment_frames,
    # )
    # if not coordinates:
    #     raise RuntimeError("No recordings left after confidence / fragment filtering.")

    data, metadata = kpms.format_data(
        coordinates,
        confidences,
        bodyparts=bodyparts_list,
    )
    from jax_moseq.utils.debugging import convert_data_precision

    data = convert_data_precision(data, x64=True)

    if cfg.reindex_syllables_before_load:
        kpms.reindex_syllables_in_checkpoint(str(project_dir), model_name)

    model, _, _, _ = kpms.load_checkpoint(str(project_dir), model_name)

    if results_path is None:
        results_path = project_dir / model_name / DEFAULT_RESULTS_NAME
    results_path = Path(results_path)
    ensure_dir(results_path.parent)

    anterior_idxs, posterior_idxs = _anterior_posterior_idxs(bodyparts_list)

    kpms.apply_model(
        model,
        data,
        metadata,
        project_dir=str(project_dir),
        model_name=model_name,
        results_path=str(results_path),
        num_iters=cfg.num_iters,
        conf_threshold=cfg.conf_threshold,
        anterior_idxs=anterior_idxs,
        posterior_idxs=posterior_idxs,
        error_estimator=dict(cfg.error_estimator),
        parallel_message_passing=cfg.parallel_message_passing,
        verbose=cfg.verbose,
        overwrite=cfg.overwrite_results,
    )

    manifest_csv_path = Path(manifest_csv) if manifest_csv else None
    prov_inputs: dict[str, Any] = {
        "project_dir": str(project_dir),
        "model_name": model_name,
        "manifest_csv": str(manifest_csv_path) if manifest_csv_path else None,
        "n_manifest_rows": len(manifests),
    }
    if manifest_csv_path is not None and manifest_csv_path.is_file():
        prov_inputs["manifest_csv_sha256"] = sha256_file(manifest_csv_path)

    summary = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "project_dir": str(project_dir),
        "model_name": model_name,
        "results_path": str(results_path),
        "n_manifest_rows": len(manifests),
        "trial_keys_applied": sorted(coordinates.keys()),
        "n_recordings_after_preprocess": len(coordinates),
        "n_skipped_preprocess": len(skipped),
        "skipped_preprocess_examples": skipped[:50],
        "apply_config": asdict(cfg),
        "preprocess_config": asdict(pre_cfg),
        "run_provenance": provenance_envelope(
            operation="kpms_apply",
            inputs=prov_inputs,
            outputs={
                "n_manifest_rows": len(manifests),
                "n_recordings_after_preprocess": len(coordinates),
                "results_path": str(results_path),
            },
        ),
    }
    write_json(project_dir / model_name / "apply_summary.json", summary)
    if cfg.verbose:
        print(f"Wrote {results_path}")
    return summary


def _filter_tuple_to_list(ids: Optional[tuple[str, ...]]) -> Optional[list[str]]:
    return list(ids) if ids else None


def apply_run_config_from_args(args: argparse.Namespace) -> KpmsApplyRunConfig:
    """Map :func:`parse_args` namespace to :class:`KpmsApplyRunConfig`."""
    aids = expand_filter_arg(args.animal_id)
    sess = expand_filter_arg(args.session)
    tr = expand_filter_arg(args.trial)
    return KpmsApplyRunConfig(
        project_dir=Path(args.project_dir),
        model_name=args.model_name,
        manifest_csv=Path(args.manifest_csv),
        results_path=Path(args.results_path) if args.results_path else None,
        animal_ids=tuple(aids) if aids else None,
        sessions=tuple(sess) if sess else None,
        trials=tuple(tr) if tr else None,
        include_habituation=args.include_habituation,
        exclude_experimental=args.exclude_experimental,
        enrich_from_treatment_labels=not args.no_enrich_labels,
        num_iters=args.num_iters,
        reindex_syllables_before_load=not args.no_reindex,
        verbose=not args.quiet,
        overwrite_results=not args.no_overwrite_results,
    )


def run_kpms_apply(cfg: KpmsApplyRunConfig) -> dict[str, Any]:
    """
    Apply a keypoint-MoSeq checkpoint to trials from a manifest CSV.

    Writes ``<project_dir>/<model_name>/results_apply.h5`` (unless overridden),
    ``apply_summary.json``, and a provenance sidecar under ``<project_dir>/provenance/``.

    Returns:
        Summary dict (same shape as :func:`apply_kpms_checkpoint_from_manifests`).

    Raises:
        FileNotFoundError: Manifest CSV missing.
        RuntimeError: No trials match filters or no usable trajectories after preprocess.
    """
    manifest_csv = Path(cfg.manifest_csv)
    if not manifest_csv.is_file():
        raise FileNotFoundError(f"Manifest CSV not found: {manifest_csv}")

    animal_ids = _filter_tuple_to_list(cfg.animal_ids)
    sessions = _filter_tuple_to_list(cfg.sessions)
    trials = _filter_tuple_to_list(cfg.trials)
    manifests, stats = load_manifests_for_apply(
        manifest_csv,
        include_habituation=cfg.include_habituation,
        include_experimental=not cfg.exclude_experimental,
        enrich_from_treatment_labels=cfg.enrich_from_treatment_labels,
        animal_ids=animal_ids,
        sessions=sessions,
        trials=trials,
    )
    if not manifests:
        raise RuntimeError(
            "No trials match filters. "
            f"manifest={manifest_csv} "
            f"(rows={stats.n_csv_rows}, after sleap+phase={stats.n_after_sleap_and_phase}, "
            f"after id/session/trial={stats.n_after_animal_session_trial}). "
            "Apply requires non-empty sleap_path and (by default) experimental phase. "
            f"Filters: animal_id={animal_ids!r} session={sessions!r} trial={trials!r}. "
            "Use --manifest-csv pointing at a CSV that lists your trials; "
            "animal_id/session/trial must match those columns exactly (including spacing/case)."
        )

    apply_cfg = KpmsApplyConfig(
        num_iters=cfg.num_iters,
        reindex_syllables_before_load=cfg.reindex_syllables_before_load,
        verbose=cfg.verbose,
        overwrite_results=cfg.overwrite_results,
    )
    project_dir = Path(cfg.project_dir)
    prov_inputs = {
        "project_dir": str(project_dir),
        "model_name": cfg.model_name,
        "manifest_csv": str(manifest_csv),
        "manifest_csv_sha256": sha256_file(manifest_csv),
        "load_stats": asdict(stats),
    }
    with provenance_run("kpms_apply", project_dir, prov_inputs) as prov:
        summary = apply_kpms_checkpoint_from_manifests(
            project_dir,
            cfg.model_name,
            manifests,
            cfg=apply_cfg,
            results_path=cfg.results_path,
            manifest_csv=manifest_csv,
        )
        prov["outputs"] = {
            "n_manifest_rows": summary.get("n_manifest_rows"),
            "n_recordings_after_preprocess": summary.get("n_recordings_after_preprocess"),
            "results_path": summary.get("results_path"),
            "apply_summary": str(project_dir / cfg.model_name / "apply_summary.json"),
        }
    return summary


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Apply a keypoint-MoSeq checkpoint to trials from a manifest CSV "
        "(ORM preprocessing matches maze.kpms.fit)."
    )
    p.add_argument(
        "--manifest-csv",
        type=str,
        default=str(DEFAULT_MANIFEST_CSV),
        help=f"Trial manifest CSV (default: {DEFAULT_MANIFEST_CSV})",
    )
    p.add_argument("--project-dir", type=str, required=True)
    p.add_argument("--model-name", type=str, required=True)
    p.add_argument(
        "--results-path",
        type=str,
        default=None,
        help=f"Output HDF5 path (default: <project-dir>/<model-name>/{DEFAULT_RESULTS_NAME})",
    )
    p.add_argument("--animal-id", type=str, nargs="*", default=None, help="Animal ID(s)")
    p.add_argument("--session", type=str, nargs="*", default=None, help="Session(s), e.g. S01")
    p.add_argument("--trial", type=str, nargs="*", default=None, help="Trial(s), e.g. T01")
    p.add_argument("--include-habituation", action="store_true")
    p.add_argument("--exclude-experimental", action="store_true")
    p.add_argument(
        "--no-enrich-labels",
        action="store_true",
        help="Do not fill blank sex/tx from inputs/treatment_labels.csv",
    )
    p.add_argument("--num-iters", type=int, default=100)
    p.add_argument("--no-reindex", action="store_true", help="Skip reindex_syllables_in_checkpoint")
    p.add_argument(
        "--no-overwrite-results",
        action="store_true",
        help="Pass overwrite=False to apply_model (fails if results file already has these keys)",
    )
    p.add_argument("--quiet", action="store_true")
    return p.parse_args()


def main() -> None:
    run_kpms_apply(apply_run_config_from_args(parse_args()))


if __name__ == "__main__":
    main()
